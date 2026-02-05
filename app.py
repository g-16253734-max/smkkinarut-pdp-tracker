import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time

# --- KONFIGURASI ---
st.set_page_config(page_title="e-PdP Tracker SMK Kinarut", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

if 'rekod_temp' not in st.session_state:
    st.session_state.rekod_temp = {}

# --- FUNGSI EKSTRAK PDF ---
@st.cache_data
def muat_data_pdf(file_path):
    all_data = []
    PETA_BIASA = {1:("6:40","7:00"), 2:("7:00","7:30"), 3:("7:30","8:00"), 4:("8:00","8:30"), 5:("8:30","9:00"), 6:("9:00","9:30"), 7:("9:30","10:00"), 8:("10:00","10:30"), 9:("10:30","11:00"), 10:("11:00","11:30"), 11:("11:30","12:00"), 12:("12:00","12:30"), 13:("12:30","1:00"), 14:("1:00","1:30"), 15:("1:30","2:00"), 16:("2:00","2:30"), 17:("2:30","3:00")}
    PETA_JUMAAT = {1:("6:40","7:10"), 2:("7:10","7:40"), 3:("7:40","8:10"), 4:("8:10","8:40"), 5:("8:40","9:10"), 6:("9:10","9:40"), 7:("9:40","10:10"), 8:("10:10","10:40"), 9:("10:40","11:10"), 10:("11:10","11:40"), 11:("11:40","12:10"), 12:("12:10","12:40")}
    
    if not os.path.exists(file_path): return pd.DataFrame()

    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
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
                                if len(isi_bersih) > 3 and "REHAT" not in isi_bersih.upper():
                                    
                                    # LOGIK KIRA MINIT:
                                    # Jika dalam teks ada range masa (cth: 10:10-11:10), kita kira beza masanya
                                    minit_pdp = 30 # Default
                                    times = re.findall(r"(\d{1,2}[:.]\d{2})", isi_bersih)
                                    if len(times) >= 2:
                                        try:
                                            fmt = '%H:%M' if ':' in times[0] else '%H.%M'
                                            t1 = datetime.strptime(times[0].replace('.', ':'), '%H:%M')
                                            t2 = datetime.strptime(times[1].replace('.', ':'), '%H:%M')
                                            minit_pdp = int((t2 - t1).total_seconds() / 60)
                                        except: minit_pdp = 30
                                    
                                    mula, tamat = (PETA_JUMAAT if hari == "JUMAAT" else PETA_BIASA).get(i, ("-","-"))
                                    all_data.append({
                                        "id": f"{nama_guru}_{hari}_{i}",
                                        "Guru": nama_guru,
                                        "Hari": hari,
                                        "Isi": isi_bersih,
                                        "Masa": f"{mula}-{tamat}",
                                        "Minit": minit_pdp
                                    })
        return pd.DataFrame(all_data)
    except: return pd.DataFrame()

# --- UI UTAMA ---
st.title("📊 e-PdP Tracker SMK Kinarut")
df_jadual = muat_data_pdf("Tracker.pdf")

tab1, tab2 = st.tabs(["📝 Rekod Kehadiran", "📈 Analisis & Laporan"])

with tab1:
    if not df_jadual.empty:
        col1, col2 = st.columns([1, 3])
        with col1:
            pilihan_guru = st.selectbox("Guru:", sorted(df_jadual['Guru'].unique()))
            hari_pilihan = st.radio("Hari:", ["ISNIN", "SELASA", "RABU", "KHAMIS", "JUMAAT"])
            tarikh = st.date_input("Tarikh:", datetime.now())
        
        with col2:
            filtered = df_jadual[(df_jadual['Guru'] == pilihan_guru) & (df_jadual['Hari'] == hari_pilihan)]
            grid = st.columns(2)
            for idx, row in enumerate(filtered.itertuples()):
                with grid[idx % 2]:
                    if st.button(f"🔴 {row.Masa} | {row.Isi}", key=row.id):
                        st.session_state.rekod_temp[row.id] = {
                            "Tarikh": tarikh.strftime("%Y-%m-%d"),
                            "Nama Guru": row.Guru,
                            "Subjek/Kelas": row.Isi,
                            "Minit": row.Minit,
                            "Masa Rekod": datetime.now().strftime("%H:%M")
                        }
        
        if st.session_state.rekod_temp:
            st.table(pd.DataFrame(list(st.session_state.rekod_temp.values())))
            if st.button("🚀 SIMPAN KE GOOGLE SHEETS"):
                existing = conn.read(ttl=0)
                df_new = pd.DataFrame(list(st.session_state.rekod_temp.values()))
                updated = pd.concat([existing, df_new], ignore_index=True).drop_duplicates()
                conn.update(data=updated)
                st.session_state.rekod_temp = {}
                st.success("Tersimpan!")
                time.sleep(1); st.rerun()

with tab2:
    st.header("📈 Analisis PdP Terbiar")
    df_full = conn.read(ttl=0)
    if df_full is not None and not df_full.empty:
        # 1. Analisis Jam mengikut Guru
        st.subheader("Total Jam Terbiar (Guru)")
        sum_guru = df_full.groupby('Nama Guru')['Minit'].sum() / 60
        st.bar_chart(sum_guru)
        
        # 2. Analisis mengikut Subjek/Kelas
        st.subheader("Kerap Terbiar mengikut Subjek/Kelas")
        sum_class = df_full['Subjek/Kelas'].value_counts()
        st.bar_chart(sum_class)
        
        st.dataframe(df_full)
    else:
        st.info("Tiada data analisis.")
