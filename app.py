import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="e-PdP Tracker SMK Kinarut", layout="wide")

# --- 1. SAMBUNGAN GOOGLE SHEETS ---
# Pastikan URL Sheet diletakkan di bahagian Secrets Streamlit Cloud
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
    
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                match_nama = re.search(r"NAMA GURU\s*:\s*(.*)", text)
                nama_guru = match_nama.group(1).split("GURU KELAS")[0].strip() if match_nama else "Unknown"
                table = page.extract_table()
                if not table: continue
                for row in table:
                    hari = row[0].strip().upper() if row[0] else ""
                    if hari in ["ISNIN", "SELASA", "RABU", "KHAMIS", "JUMAAT"]:
                        for i in range(1, len(row)):
                            if row[i] and row[i].strip():
                                mula, tamat = (PETA_JUMAAT if hari == "JUMAAT" else PETA_BIASA).get(i, ("-","-"))
                                slot_id = f"{nama_guru}_{hari}_{i}"
                                all_data.append({
                                    "id": slot_id, 
                                    "Guru": nama_guru, 
                                    "Hari": hari, 
                                    "Isi": row[i].replace("\n", " "), 
                                    "Masa": f"{mula}-{tamat}"
                                })
        return pd.DataFrame(all_data)
    except Exception as e:
        st.error(f"Gagal membaca PDF: {e}")
        return pd.DataFrame()

# --- UTAMA ---
st.title("📊 e-PdP Tracker SMK Kinarut")

try:
    # Memuatkan data dari PDF
    df_jadual = muat_data_pdf("Tracker.pdf")
    
    # --- TAB MENU ---
    tab_rekod, tab_analisis = st.tabs(["📝 Rekod Kehadiran", "📈 Analisis & Laporan"])

    with tab_rekod:
        if df_jadual.empty:
            st.warning("Sila pastikan fail 'Guru 26Jan.pdf' ada dalam folder aplikasi.")
        else:
            col_side1, col_side2 = st.columns([1, 3])
            
            with col_side1:
                pilihan_guru = st.selectbox("Pilih Nama Guru:", df_jadual['Guru'].unique())
                hari_ini = st.radio("Pilih Hari:", ["ISNIN", "SELASA", "RABU", "KHAMIS", "JUMAAT"])
                tarikh_pantau = st.date_input("Tarikh Pantau:", datetime.now())
                if st.button("🗑️ Kosongkan Semua Tanda"):
                    st.session_state.rekod_temp = {}
                    st.rerun()

            with col_side2:
                jadual_guru = df_jadual[(df_jadual['Guru'] == pilihan_guru) & (df_jadual['Hari'] == hari_ini)]
                if jadual_guru.empty:
                    st.info("Tiada kelas pada hari ini.")
                else:
                    st.subheader(f"Jadual {pilihan_guru} ({hari_ini})")
                    grid = st.columns(3)
                    for idx, row in enumerate(jadual_guru.itertuples()):
                        with grid[idx % 3]:
                            is_selected = row.id in st.session_state.rekod_temp
                            status_color = "🔴" if is_selected else "🟢"
                            with st.expander(f"{status_color} {row.Masa}", expanded=True):
                                st.write(f"**{row.Isi}**")
                                if is_selected:
                                    if st.button("Batal", key=row.id):
                                        del st.session_state.rekod_temp[row.id]
                                        st.rerun()
                                else:
                                    if st.button("Tanda Tidak Hadir", key=row.id):
                                        st.session_state.rekod_temp[row.id] = {
                                            "Tarikh": tarikh_pantau.strftime("%Y-%m-%d"),
                                            "Nama Guru": row.Guru,
                                            "Hari": row.Hari,
                                            "Masa": row.Masa,
                                            "Subjek/Kelas": row.Isi,
                                            "Masa Rekod": datetime.now().strftime("%H:%M:%S")
                                        }
                                        st.rerun()

            # BUTANG SIMPAN KE GOOGLE SHEETS
            if st.session_state.rekod_temp:
                st.divider()
                df_to_save = pd.DataFrame(list(st.session_state.rekod_temp.values()))
                st.write("### Senarai Untuk Dihantar:")
                st.table(df_to_save)
                
                if st.button("🚀 HANTAR LAPORAN SEKARANG"):
                    try:
                        # 1. AMBIL data sedia ada dari Google Sheets
                        existing_data = conn.read()
                        
                        # 2. GABUNGKAN data lama dengan data baru (Append)
                        if existing_data is not None and not existing_data.empty:
                            # Bersihkan sebarang baris kosong (jika ada)
                            existing_data = existing_data.dropna(how='all')
                            updated_data = pd.concat([existing_data, df_to_save], ignore_index=True)
                        else:
                            updated_data = df_to_save
                        
                        # 3. SIMPAN semula semua data yang telah digabungkan
                        conn.update(data=updated_data)
                        
                        # Kosongkan memori sementara selepas berjaya
                        st.session_state.rekod_temp = {}
                        st.success("Rekod berjaya ditambah ke dalam pangkalan data!")
                        st.balloons()
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Gagal mengemaskini Google Sheets: {e}")


    with tab_analisis:
        st.header("📈 Analisis Ketidakhadiran Strategik")
        
        # Ambil data terkini dari Google Sheets
        df_full = conn.read()
        
        if df_full is not None and not df_full.empty:
            # Pastikan nama kolum dibersihkan (buang ruang kosong jika ada)
            df_full.columns = df_full.columns.str.strip()
            
            # Tukar Tarikh kepada format datetime yang betul
            df_full['Tarikh'] = pd.to_datetime(df_full['Tarikh'], errors='coerce')
            
            # Buang baris yang tarikhnya rosak
            df_full = df_full.dropna(subset=['Tarikh'])

            # Bahagian Filter Tarikh
            min_date = df_full['Tarikh'].min().date()
            max_date = df_full['Tarikh'].max().date()
            
            julat = st.date_input("Julat Analisis:", [min_date, max_date])
            
            if len(julat) == 2:
                mula_t, tamat_t = julat
                mask = (df_full['Tarikh'].dt.date >= mula_t) & (df_full['Tarikh'].dt.date <= tamat_t)
                df_filtered = df_full.loc[mask].copy()

                if not df_filtered.empty:
                    # 1. ANALISIS JAM GURU
                    st.subheader("📊 Jam PdP Terbiar mengikut Guru")
                    guru_stats = df_filtered['Nama Guru'].value_counts().reset_index()
                    guru_stats.columns = ['Nama Guru', 'Slot']
                    guru_stats['Jam'] = (guru_stats['Slot'] * 30) / 60
                    st.bar_chart(data=guru_stats, x='Nama Guru', y='Jam')
                    
                    st.divider()

                    # 2. ANALISIS KELAS & SUBJEK (GABUNGAN)
                    col_an1, col_an2 = st.columns(2)
                    
                    # Logik Ekstrak Kelas (Ambil nombor dan huruf, cth: 4A, 5 SN)
                    # Kita guna str.extract untuk cari corak kelas
                    df_filtered['Kelas_Hanya'] = df_filtered['Subjek/Kelas'].str.extract(r'(\d\s*[A-Z]+)')
                    df_filtered['Kelas_Hanya'] = df_filtered['Kelas_Hanya'].fillna("Lain-lain")
                    
                    with col_an1:
                        st.subheader("🏫 Kelas Paling Terkesan")
                        kelas_stats = df_filtered.groupby('Kelas_Hanya').size().reset_index(name='Slot')
                        kelas_stats['Jam'] = (kelas_stats['Slot'] * 30) / 60
                        st.bar_chart(data=kelas_stats.sort_values('Jam', ascending=False), x='Kelas_Hanya', y='Jam', color="#ff4b4b")
                    
                    with col_an2:
                        st.subheader("📖 Subjek Paling Terkesan")
                        # Ambil teks sebelum nombor pertama sebagai Subjek
                        df_filtered['Subjek_Hanya'] = df_filtered['Subjek/Kelas'].str.split(r'\d').str[0].str.strip()
                        sub_stats = df_filtered.groupby('Subjek_Hanya').size().reset_index(name='Slot')
                        sub_stats['Jam'] = (sub_stats['Slot'] * 30) / 60
                        st.bar_chart(data=sub_stats.sort_values('Jam', ascending=False), x='Subjek_Hanya', y='Jam', color="#0083B8")

                    st.divider()
                    st.subheader("📋 Senarai Rekod Terperinci")
                    # Tunjukkan tarikh dalam format yang mudah dibaca
                    df_display = df_filtered.copy()
                    df_display['Tarikh'] = df_display['Tarikh'].dt.strftime('%d/%m/%Y')
                    st.dataframe(df_display.sort_values('Tarikh', ascending=False), use_container_width=True)
                else:
                    st.warning("Tiada rekod ditemui untuk julat tarikh tersebut.")
        else:
            st.info("Pangkalan data Google Sheets masih kosong. Sila hantar laporan di tab 'Rekod Kehadiran' terlebih dahulu.")

except Exception as e:
    st.error(f"Ralat sistem: {e}")

