import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import time

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="e-PdP Tracker SMK Kinarut", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

def waktu_sekarang():
    return datetime.now() + timedelta(hours=8)

if 'rekod_temp' not in st.session_state:
    st.session_state.rekod_temp = {}

# --- FUNGSI EKSTRAK PDF ---
@st.cache_data
def muat_data_pdf(file_path):
    all_data = []
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
                                    minit_pdp = 30 
                                    times = re.findall(r"(\d{1,2}[:.]\d{2})", isi_bersih)
                                    if len(times) >= 2:
                                        try:
                                            t1 = datetime.strptime(times[0].replace('.', ':'), '%H:%M')
                                            t2 = datetime.strptime(times[1].replace('.', ':'), '%H:%M')
                                            diff = int((t2 - t1).total_seconds() / 60)
                                            if diff < 0: diff += 720
                                            minit_pdp = diff
                                        except: minit_pdp = 30
                                    
                                    all_data.append({
                                        "id": f"{nama_guru}_{hari}_{i}_{isi_bersih[:10]}",
                                        "Guru": nama_guru,
                                        "Hari": hari,
                                        "Subjek_Kelas_Raw": isi_bersih,
                                        "Minit": minit_pdp
                                    })
        return pd.DataFrame(all_data)
    except: return pd.DataFrame()

# --- FUNGSI PEMBERSIHAN ---
def proses_teks_pdp(teks):
    teks_bersih = re.sub(r'\d{1,2}[:.]\d{2}', '', teks)
    teks_bersih = re.sub(r'[-\s/:.]+$', '', teks_bersih).strip()
    # Detect Kelas (1-6 followed by letter/word)
    match = re.search(r"(.*?)\s+([1-6][A-Z\s].*)", teks_bersih)
    if match:
        subjek = match.group(1).strip()
        kelas = match.group(2).strip()
        if not subjek: 
             parts = teks_bersih.split(kelas)
             subjek = parts[0].strip() if parts[0] else "Subjek"
        return subjek, kelas
    return teks_bersih, "Lain-lain"

# --- UI ---
st.title("📊 e-PdP Tracker SMK Kinarut")
df_jadual = muat_data_pdf("Tracker.pdf")

tab1, tab2 = st.tabs(["📝 Rekod Kehadiran", "📈 Analisis & Laporan"])

with tab1:
    if not df_jadual.empty:
        col1, col2 = st.columns([1, 2.5])
        with col1:
            tarikh_pilih = st.date_input("Pilih Tarikh Pantauan:", waktu_sekarang())
            hari_map = {"Monday": "ISNIN", "Tuesday": "SELASA", "Wednesday": "RABU", "Thursday": "KHAMIS", "Friday": "JUMAAT", "Saturday": "SABTU", "Sunday": "AHAD"}
            hari_auto = hari_map.get(tarikh_pilih.strftime("%A"))
            st.info(f"Hari: **{hari_auto}**")
            senarai_guru = ["-- Pilih Nama Guru --"] + sorted(df_jadual['Guru'].unique().tolist())
            pilihan_guru = st.selectbox("Pilih Nama Guru:", senarai_guru)
        
        with col2:
            if pilihan_guru != "-- Pilih Nama Guru --":
                filtered = df_jadual[(df_jadual['Guru'] == pilihan_guru) & (df_jadual['Hari'] == hari_auto)]
                if filtered.empty:
                    st.warning(f"Tiada jadual untuk {pilihan_guru} pada hari {hari_auto}.")
                else:
                    st.subheader(f"Jadual: {pilihan_guru} ({hari_auto})")
                    for row in filtered.itertuples():
                        is_recorded = row.id in st.session_state.rekod_temp
                        label_btn = f"🔴 BATAL: {row.Subjek_Kelas_Raw}" if is_recorded else f"🟢 {row.Subjek_Kelas_Raw} - Tanda Tidak Hadir"
                        tipe_btn = "primary" if is_recorded else "secondary"
                        
                        if st.button(label_btn, key=row.id, use_container_width=True, type=tipe_btn):
                            if is_recorded:
                                del st.session_state.rekod_temp[row.id]
                            else:
                                subjek_saja, kelas_saja = proses_teks_pdp(row.Subjek_Kelas_Raw)
                                st.session_state.rekod_temp[row.id] = {
                                    "Tarikh": tarikh_pilih.strftime("%d/%m/%Y"),
                                    "Hari": hari_auto, # <-- DAH TAMBAH SEMULA
                                    "Nama Guru": row.Guru,
                                    "Subjek": subjek_saja,
                                    "Kelas": kelas_saja,
                                    "Minit": row.Minit,
                                    "Waktu_Rekod": (datetime.now() + timedelta(hours=8)).strftime("%H:%M"), # <-- DAH TAMBAH SEMULA
                                    "Subjek_Kelas": row.Subjek_Kelas_Raw
                                }
                            st.rerun()

        if st.session_state.rekod_temp:
            st.divider()
            st.write("### 📋 Laporan Sementara")
            df_temp_view = pd.DataFrame(list(st.session_state.rekod_temp.values()))
            st.table(df_temp_view[['Tarikh', 'Hari', 'Nama Guru', 'Subjek', 'Kelas', 'Minit']]) # Papar Hari juga
            
            if st.button("🚀 HANTAR KE GOOGLE SHEETS", type="primary", use_container_width=True):
                df_to_save = pd.DataFrame(list(st.session_state.rekod_temp.values()))
                try:
                    try:
                        existing = conn.read(ttl=0)
                        updated = pd.concat([existing, df_to_save], ignore_index=True).drop_duplicates()
                    except:
                        updated = df_to_save
                    conn.update(data=updated)
                    st.session_state.rekod_temp = {}
                    st.balloons(); st.success("Data berjaya disimpan!"); time.sleep(1); st.rerun()
                except Exception as e:
                    st.error(f"Ralat: {e}")

with tab2:
    st.header("📈 Analisis PdP Terbiar")
    try:
        df_full = conn.read(ttl=0)
        if df_full is not None and not df_full.empty:
            df_full['Minit'] = pd.to_numeric(df_full['Minit'], errors='coerce').fillna(0)
            
            # --- CARTA ---
            colA, colB, colC = st.columns(3)
            with colA:
                st.subheader("👤 By Guru")
                st.bar_chart(df_full.groupby('Nama Guru')['Minit'].sum() / 60)
            with colB:
                st.subheader("📚 By Subjek")
                # Cuci sisa angka pada subjek untuk graf sahaja
                df_full['Subjek_Graf'] = df_full['Subjek'].str.replace(r'\d+', '', regex=True).str.strip()
                st.bar_chart(df_full.groupby('Subjek_Graf')['Minit'].sum() / 60)
            with colC:
                st.subheader("🏫 By Kelas")
                st.bar_chart(df_full.groupby('Kelas')['Minit'].sum() / 60)
                
            st.divider()
            st.write("### 📄 Data Mentah (Lengkap)")
            # Sembunyikan kolum teknikal Subjek_Kelas sahaja
            if 'Subjek_Kelas' in df_full.columns:
                df_display = df_full.drop(columns=['Subjek_Kelas'])
                # Jika ada kolum Subjek_Graf, buang juga dari paparan table
                if 'Subjek_Graf' in df_display.columns:
                    df_display = df_display.drop(columns=['Subjek_Graf'])
            else:
                df_display = df_full
            
            st.dataframe(df_display.sort_values(['Tarikh', 'Waktu_Rekod'], ascending=[False, False]), use_container_width=True)
    except Exception as e:
        st.info("Sila masukkan data baru dahulu.")
