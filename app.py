import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="e-PdP Tracker SMK Kinarut", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# Inisialisasi memori sementara jika belum ada
if 'rekod_temp' not in st.session_state:
    st.session_state.rekod_temp = {}

# --- FUNGSI EKSTRAK PDF ---
@st.cache_data
def muat_data_pdf(file_path):
    all_data = []
    # Peta Masa Standard
    PETA_BIASA = {1:("6:40","7:00"), 2:("7:00","7:30"), 3:("7:30","8:00"), 4:("8:00","8:30"), 5:("8:30","9:00"), 6:("9:00","9:30"), 7:("9:30","10:00"), 8:("10:00","10:30"), 9:("10:30","11:00"), 10:("11:00","11:30"), 11:("11:30","12:00"), 12:("12:00","12:30"), 13:("12:30","1:00"), 14:("1:00","1:30"), 15:("1:30","2:00"), 16:("2:00","2:30"), 17:("2:30","3:00")}
    PETA_JUMAAT = {1:("6:40","7:10"), 2:("7:10","7:40"), 3:("7:40","8:10"), 4:("8:10","8:40"), 5:("8:40","9:10"), 6:("9:10","9:40"), 7:("9:40","10:10"), 8:("10:10","10:40"), 9:("10:40","11:10"), 10:("11:10","11:40"), 11:("11:40","12:10"), 12:("12:10","12:40")}
    
    if not os.path.exists(file_path): return pd.DataFrame()

    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                # Ekstrak Nama Guru
                match_nama = re.search(r"NAMA GURU\s*:\s*(.*)", text)
                nama_guru = match_nama.group(1).split("GURU KELAS")[0].strip() if match_nama else "Unknown"
                
                table = page.extract_table()
                if not table: continue
                
                for row in table:
                    hari = str(row[0]).strip().upper() if row[0] else ""
                    if hari in ["ISNIN", "SELASA", "RABU", "KHAMIS", "JUMAAT"]:
                        for i in range(1, len(row)):
                            isi_raw = row[i]
                            if isi_raw and str(isi_raw).strip() != "":
                                isi_bersih = str(isi_raw).replace("\n", " ").strip()
                                
                                # Abaikan slot REHAT atau teks kosong
                                if len(isi_bersih) > 3 and "REHAT" not in isi_bersih.upper():
                                    # LOGIK KIRA MINIT: Mencari waktu dlm teks (cth: 07:10-08:10)
                                    minit_pdp = 30 # Nilai asas
                                    times = re.findall(r"(\d{1,2}[:.]\d{2})", isi_bersih)
                                    if len(times) >= 2:
                                        try:
                                            t1 = datetime.strptime(times[0].replace('.', ':'), '%H:%M')
                                            t2 = datetime.strptime(times[1].replace('.', ':'), '%H:%M')
                                            minit_pdp = int((t2 - t1).total_seconds() / 60)
                                        except: minit_pdp = 30
                                    
                                    mula, tamat = (PETA_JUMAAT if hari == "JUMAAT" else PETA_BIASA).get(i, ("-","-"))
                                    all_data.append({
                                        "id": f"{nama_guru}_{hari}_{i}",
                                        "Guru": nama_guru,
                                        "Hari": hari,
                                        "Subjek_Kelas": isi_bersih,
                                        "Masa": f"{mula}-{tamat}",
                                        "Minit": minit_pdp
                                    })
        return pd.DataFrame(all_data)
    except: return pd.DataFrame()

# --- ANTARAMUKA (UI) ---
st.title("📊 e-PdP Tracker SMK Kinarut")
df_jadual = muat_data_pdf("Tracker.pdf")

tab1, tab2 = st.tabs(["📝 Rekod Kehadiran", "📈 Analisis & Laporan"])

with tab1:
    if not df_jadual.empty:
        col1, col2 = st.columns([1, 2.5])
        with col1:
            pilihan_guru = st.selectbox("Pilih Nama Guru:", sorted(df_jadual['Guru'].unique()))
            hari_pilihan = st.radio("Pilih Hari:", ["ISNIN", "SELASA", "RABU", "KHAMIS", "JUMAAT"])
            tarikh = st.date_input("Tarikh Pantauan:", datetime.now())
        
        with col2:
            filtered = df_jadual[(df_jadual['Guru'] == pilihan_guru) & (df_jadual['Hari'] == hari_pilihan)]
            if filtered.empty:
                st.info("Tiada jadual untuk hari ini.")
            else:
                st.subheader(f"Jadual: {pilihan_guru}")
                for row in filtered.itertuples():
                    is_recorded = row.id in st.session_state.rekod_temp
                    
                    # --- PAPARAN BARU YANG LEBIH BERSIH ---
                    if is_recorded:
                        # Tunjuk "BATAL" dan nama kelas sahaja bila sudah ditekan
                        label_btn = f"🔴 BATAL: {row.Subjek_Kelas}"
                        tipe_btn = "primary"
                    else:
                        # Buang row.Masa di depan, hanya tunjuk Subjek/Kelas dan Tanda Tidak Hadir
                        label_btn = f"🟢 {row.Subjek_Kelas} - Tanda Tidak Hadir"
                        tipe_btn = "secondary"
                    
                    if st.button(label_btn, key=row.id, use_container_width=True, type=tipe_btn):
                        if is_recorded:
                            del st.session_state.rekod_temp[row.id]
                        else:
                            st.session_state.rekod_temp[row.id] = {
                                "Tarikh": tarikh.strftime("%Y-%m-%d"),
                                "Nama Guru": row.Guru,
                                "Subjek_Kelas": row.Subjek_Kelas,
                                "Minit": row.Minit,
                                "Waktu_Rekod": datetime.now().strftime("%H:%M")
                            }
                        st.rerun()
        
        # Bahagian Pengesahan dan Penghantaran
        if st.session_state.rekod_temp:
            st.divider()
            st.write("### Senarai Laporan Sementara")
            df_preview = pd.DataFrame(list(st.session_state.rekod_temp.values()))
            st.table(df_preview)
            
            if st.button("🚀 HANTAR KE GOOGLE SHEETS", type="primary", use_container_width=True):
                try:
                    # Baca data sedia ada
                    try:
                        existing_data = conn.read(ttl=0)
                    except:
                        existing_data = pd.DataFrame()

                    # Gabung data (Append)
                    if existing_data is not None and not existing_data.empty:
                        updated_data = pd.concat([existing_data, df_preview], ignore_index=True).drop_duplicates()
                    else:
                        updated_data = df_preview

                    conn.update(data=updated_data)
                    st.session_state.rekod_temp = {}
                    st.balloons()
                    st.success("Data berjaya disimpan ke Google Sheets!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Ralat simpanan: {e}")

with tab2:
    st.header("📈 Analisis PdP Terbiar")
    try:
        df_full = conn.read(ttl=0)
        if df_full is not None and not df_full.empty and 'Minit' in df_full.columns:
            df_full['Minit'] = pd.to_numeric(df_full['Minit'], errors='coerce').fillna(0)
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Jumlah Jam (Guru)")
                sum_guru = df_full.groupby('Nama Guru')['Minit'].sum() / 60
                st.bar_chart(sum_guru)
            with c2:
                st.subheader("Kekerapan (Subjek/Kelas)")
                sum_class = df_full['Subjek_Kelas'].value_counts()
                st.bar_chart(sum_class)
                
            st.divider()
            st.subheader("Log Rekod Penuh")
            st.dataframe(df_full.sort_values('Tarikh', ascending=False), use_container_width=True)
        else:
            st.info("Sila masukkan data pertama untuk melihat analisis.")
    except:
        st.info("Sila masukkan data pertama untuk melihat analisis.")

