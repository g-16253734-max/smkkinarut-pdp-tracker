import streamlit as st
import pdfplumber
import pandas as pd
import re
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="e-PdP Tracker SMK Kinarut", layout="wide")

# --- 1. SAMBUNGAN GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. MEMORI APLIKASI ---
if 'rekod_temp' not in st.session_state:
    st.session_state.rekod_temp = {}

@st.cache_data
def muat_data_pdf(file_path):
    all_data = []
    # Peta Masa (Ikut struktur slot 1-17)
    PETA_BIASA = {1:("6:40","7:00"), 2:("7:00","7:30"), 3:("7:30","8:00"), 4:("8:00","8:30"), 5:("8:30","9:00"), 6:("9:00","9:30"), 7:("9:30","10:00"), 8:("10:00","10:30"), 9:("10:30","11:00"), 10:("11:00","11:30"), 11:("11:30","12:00"), 12:("12:00","12:30"), 13:("12:30","1:00"), 14:("1:00","1:30"), 15:("1:30","2:00"), 16:("2:00","2:30"), 17:("2:30","3:00")}
    PETA_JUMAAT = {1:("6:40","7:10"), 2:("7:10","7:40"), 3:("7:40","8:10"), 4:("8:10","8:40"), 5:("8:40","9:10"), 6:("9:10","9:40"), 7:("9:40","10:10"), 8:("10:10","10:40"), 9:("10:40","11:10"), 10:("11:10","11:40"), 11:("11:40","12:10"), 12:("12:10","12:40")}
    
    # Check jika fail wujud sebelum buka
    if not os.path.exists(file_path):
        return pd.DataFrame()

    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text: continue
                
                match_nama = re.search(r"NAMA GURU\s*:\s*(.*)", text)
                nama_guru = match_nama.group(1).split("GURU KELAS")[0].strip() if match_nama else "Unknown"
                
                table = page.extract_table()
                if not table: continue
                
                for row in table:
                    # Pastikan row[0] tidak None sebelum strip
                    hari = str(row[0]).strip().upper() if row[0] else ""
                    
                    if hari in ["ISNIN", "SELASA", "RABU", "KHAMIS", "JUMAAT"]:
                        # Salin baris untuk proses merged cells
                        temp_row = list(row)
                        
                        for i in range(1, len(temp_row)):
                            val = temp_row[i]
                            
                            # Jika slot KOSONG, cuba tengok slot sebelah kiri
                            if val is None or str(val).strip() == "":
                                if i > 1 and i != 7: # i != 7 untuk elak tarik subjek masuk ke waktu REHAT
                                    val_sebelum = temp_row[i-1]
                                    if val_sebelum:
                                        temp_row[i] = val_sebelum
                            
                            # Ambil nilai yang sudah diproses
                            isi_final = str(temp_row[i]).replace("\n", " ").strip() if temp_row[i] else ""
                            
                            if isi_final:
                                mula, tamat = (PETA_JUMAAT if hari == "JUMAAT" else PETA_BIASA).get(i, ("-","-"))
                                slot_id = f"{nama_guru}_{hari}_{i}"
                                all_data.append({
                                    "id": slot_id, 
                                    "Guru": nama_guru, 
                                    "Hari": hari, 
                                    "Isi": isi_final, 
                                    "Masa": f"{mula}-{tamat}"
                                })
                                
        return pd.DataFrame(all_data)
    except Exception as e:
        # Kita print ralat sebenar di terminal/logs untuk rujukan
        print(f"Error reading PDF: {e}")
        return pd.DataFrame()
        
# --- UTAMA ---
st.title("📊 e-PdP Tracker SMK Kinarut")

try:
    df_jadual = muat_data_pdf("Tracker.pdf")
    tab_rekod, tab_analisis = st.tabs(["📝 Rekod Kehadiran", "📈 Analisis & Laporan"])

    with tab_rekod:
        if df_jadual.empty:
            st.error("Fail 'Tracker.pdf' tidak ditemui atau kosong.")
        else:
            col_side1, col_side2 = st.columns([1, 3])
            with col_side1:
                pilihan_guru = st.selectbox("Pilih Guru:", df_jadual['Guru'].unique())
                pilihan_hari = st.radio("Hari:", ["ISNIN", "SELASA", "RABU", "KHAMIS", "JUMAAT"])
                tarikh_p = st.date_input("Tarikh Pantau:", datetime.now())
                if st.button("🗑️ Kosongkan"):
                    st.session_state.rekod_temp = {}
                    st.rerun()

            with col_side2:
                jadual = df_jadual[(df_jadual['Guru'] == pilihan_guru) & (df_jadual['Hari'] == pilihan_hari)]
                if jadual.empty:
                    st.info("Tiada kelas.")
                else:
                    grid = st.columns(3)
                    for idx, row in enumerate(jadual.itertuples()):
                        with grid[idx % 3]:
                            is_sel = row.id in st.session_state.rekod_temp
                            if st.button(f"{'🔴' if is_sel else '🟢'} {row.Masa}\n{row.Isi}", key=row.id):
                                if is_sel: del st.session_state.rekod_temp[row.id]
                                else:
                                    st.session_state.rekod_temp[row.id] = {
                                        "Tarikh": tarikh_p.strftime("%Y-%m-%d"),
                                        "Nama Guru": row.Guru, "Hari": row.Hari,
                                        "Masa": row.Masa, "Subjek/Kelas": row.Isi,
                                        "Masa Rekod": datetime.now().strftime("%H:%M:%S")
                                    }
                                st.rerun()

            if st.session_state.rekod_temp:
                st.divider()
                df_send = pd.DataFrame(list(st.session_state.rekod_temp.values()))
                st.table(df_send)
                if st.button("🚀 HANTAR SEKARANG"):
                    # AMBIL DATA LAMA (ttl=0 penting!)
                    old_data = conn.read(ttl=0)
                    new_data = pd.concat([old_data, df_send], ignore_index=True).dropna(how='all')
                    conn.update(data=new_data)
                    st.session_state.rekod_temp = {}
                    st.success("Berjaya disimpan!")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()

    with tab_analisis:
        df_full = conn.read(ttl=0)
        if df_full is not None and not df_full.empty:
            df_full.columns = df_full.columns.str.strip()
            df_full['Tarikh'] = pd.to_datetime(df_full['Tarikh'], errors='coerce')
            df_full = df_full.dropna(subset=['Tarikh'])
            
            # Analisis Ringkas
            st.subheader("📊 Statistik Jam PdP Terbiar")
            guru_stats = df_full['Nama Guru'].value_counts().reset_index()
            guru_stats.columns = ['Nama Guru', 'Slot']
            guru_stats['Jam'] = (guru_stats['Slot'] * 30) / 60
            st.bar_chart(data=guru_stats, x='Nama Guru', y='Jam')
            
            st.subheader("📋 Rekod Penuh")
            st.dataframe(df_full.sort_values('Tarikh', ascending=False))
        else:
            st.info("Tiada data dalam Google Sheets.")

except Exception as e:
    st.error(f"Ralat: {e}")




