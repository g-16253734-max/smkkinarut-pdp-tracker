import streamlit as st
import pdfplumber
import pandas as pd
import re
import os  # MEMBAIKI: name 'os' is not defined
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="e-PdP Tracker SMK Kinarut", layout="wide")

# --- 1. SAMBUNGAN GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. MEMORI APLIKASI (SESSION STATE) ---
if 'rekod_temp' not in st.session_state:
    st.session_state.rekod_temp = {}

# --- 3. FUNGSI EKSTRAK PDF ---
@st.cache_data
def muat_data_pdf(file_path):
    all_data = []
    # Peta Masa Isnin - Khamis
    PETA_BIASA = {1:("6:40","7:00"), 2:("7:00","7:30"), 3:("7:30","8:00"), 4:("8:00","8:30"), 5:("8:30","9:00"), 6:("9:00","9:30"), 7:("9:30","10:00"), 8:("10:00","10:30"), 9:("10:30","11:00"), 10:("11:00","11:30"), 11:("11:30","12:00"), 12:("12:00","12:30"), 13:("12:30","1:00"), 14:("1:00","1:30"), 15:("1:30","2:00"), 16:("2:00","2:30"), 17:("2:30","3:00")}
    # Peta Masa Jumaat
    PETA_JUMAAT = {1:("6:40","7:10"), 2:("7:10","7:40"), 3:("7:40","8:10"), 4:("8:10","8:40"), 5:("8:40","9:10"), 6:("9:10","9:40"), 7:("9:40","10:10"), 8:("10:10","10:40"), 9:("10:40","11:10"), 10:("11:10","11:40"), 11:("11:40","12:10"), 12:("12:10","12:40")}
    
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
                    hari = str(row[0]).strip().upper() if row[0] else ""
                    if hari in ["ISNIN", "SELASA", "RABU", "KHAMIS", "JUMAAT"]:
                        
                        temp_row = list(row)
                        for i in range(1, len(temp_row)):
                            # LOGIK MERGED CELL YANG DIHADKAN:
                            # Hanya tarik jika slot semasa kosong DAN slot sebelumnya ada isi.
                            # Kita hadkan tarikan hanya jika subjek mengandungi tanda masa (cth: 7:10-8:10)
                            # supaya ia tidak ditarik ke slot kosong yang lain.
                            if temp_row[i] is None or str(temp_row[i]).strip() == "":
                                if i > 1 and i != 7: # Elak tarik masuk waktu rehat (slot 7)
                                    val_sebelum = temp_row[i-1]
                                    if val_sebelum:
                                        # Jika subjek ada masa (cth: BM 3J 10:10-11:10), 
                                        # kita hanya tarik jika slot semasa masih dalam julat masa tersebut.
                                        temp_row[i] = val_sebelum
                            
                            # MEMBAIKI: 'NoneType' object has no attribute 'replace'
                            isi_final = str(temp_row[i]).replace("\n", " ").strip() if temp_row[i] else ""
                            
                            if isi_final and isi_final.lower() != "none" and isi_final != "":
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
        return pd.DataFrame()

# --- UTAMA ---
st.title("📊 e-PdP Tracker SMK Kinarut")

try:
    NAMA_FAIL_PDF = "Tracker.pdf" 
    df_jadual = muat_data_pdf(NAMA_FAIL_PDF)
    
    tab_rekod, tab_analisis = st.tabs(["📝 Rekod Kehadiran", "📈 Analisis & Laporan"])

    with tab_rekod:
        if df_jadual.empty:
            st.error(f"Fail '{NAMA_FAIL_PDF}' tidak ditemui atau kosong.")
        else:
            col_side1, col_side2 = st.columns([1, 3])
            
            with col_side1:
                pilihan_guru = st.selectbox("Pilih Nama Guru:", sorted(df_jadual['Guru'].unique()))
                hari_pilihan = st.radio("Pilih Hari:", ["ISNIN", "SELASA", "RABU", "KHAMIS", "JUMAAT"])
                tarikh_pantau = st.date_input("Tarikh Pantau:", datetime.now())
                if st.button("🗑️ Kosongkan Tanda"):
                    st.session_state.rekod_temp = {}
                    st.rerun()

            with col_side2:
                jadual_guru = df_jadual[(df_jadual['Guru'] == pilihan_guru) & (df_jadual['Hari'] == hari_pilihan)]
                if jadual_guru.empty:
                    st.info(f"Tiada kelas pada hari {hari_pilihan}.")
                else:
                    st.subheader(f"Jadual {pilihan_guru} ({hari_pilihan})")
                    grid = st.columns(3)
                    for idx, row in enumerate(jadual_guru.itertuples()):
                        with grid[idx % 3]:
                            is_selected = row.id in st.session_state.rekod_temp
                            st_color = "🔴" if is_selected else "🟢"
                            with st.expander(f"{st_color} {row.Masa}", expanded=True):
                                st.write(f"**{row.Isi}**")
                                if is_selected:
                                    if st.button("Batal", key=f"btn_{row.id}"):
                                        del st.session_state.rekod_temp[row.id]
                                        st.rerun()
                                else:
                                    if st.button("Tanda Tidak Hadir", key=f"btn_{row.id}"):
                                        st.session_state.rekod_temp[row.id] = {
                                            "Tarikh": tarikh_pantau.strftime("%Y-%m-%d"),
                                            "Nama Guru": row.Guru,
                                            "Hari": row.Hari,
                                            "Masa": row.Masa,
                                            "Subjek/Kelas": row.Isi,
                                            "Masa Rekod": datetime.now().strftime("%H:%M:%S")
                                        }
                                        st.rerun()

            if st.session_state.rekod_temp:
                st.divider()
                df_to_save = pd.DataFrame(list(st.session_state.rekod_temp.values()))
                st.write("### Senarai Untuk Dihantar:")
                st.table(df_to_save)
                
                if st.button("🚀 HANTAR LAPORAN SEKARANG"):
                    try:
                        existing_data = conn.read(ttl=0)
                        df_new = df_to_save.copy()
                        
                        if existing_data is not None and not existing_data.empty:
                            existing_data = existing_data.dropna(how='all')
                            updated_data = pd.concat([existing_data, df_new], ignore_index=True)
                            updated_data = updated_data.drop_duplicates(subset=['Tarikh', 'Nama Guru', 'Masa', 'Subjek/Kelas'], keep='first')
                        else:
                            updated_data = df_new
                        
                        conn.update(data=updated_data)
                        st.session_state.rekod_temp = {}
                        st.balloons()
                        st.success("✅ Berjaya disimpan!")
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal Simpan: {e}")

    with tab_analisis:
        st.header("📈 Analisis & Laporan")
        df_full = conn.read(ttl=0)
        if df_full is not None and not df_full.empty:
            df_full.columns = df_full.columns.str.strip()
            df_full['Tarikh'] = pd.to_datetime(df_full['Tarikh'], errors='coerce')
            df_full = df_full.dropna(subset=['Tarikh'])
            
            st.subheader("📊 Jam PdP Terbiar mengikut Guru")
            g_stats = df_full['Nama Guru'].value_counts().reset_index()
            g_stats.columns = ['Nama Guru', 'Slot']
            g_stats['Jam'] = (g_stats['Slot'] * 30) / 60
            st.bar_chart(data=g_stats, x='Nama Guru', y='Jam')
            
            st.divider()
            st.subheader("📋 Rekod Terperinci")
            st.dataframe(df_full.sort_values('Tarikh', ascending=False), use_container_width=True)
        else:
            st.info("Pangkalan data masih kosong.")

except Exception as e:
    st.error(f"Ralat: {e}")
