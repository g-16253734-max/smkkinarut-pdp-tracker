import streamlit as st
import pdfplumber
import pandas as pd
import re
import os
from datetime import datetime

st.set_page_config(page_title="e-PdP Tracker SMK Kinarut", layout="wide")

# --- 1. MEMORI APLIKASI ---
if 'rekod_temp' not in st.session_state:
    st.session_state.rekod_temp = {} # Guna dict supaya boleh simpan info tambahan

# Nama fail untuk simpan rekod kekal
FAIL_REKOD = "Rekod_Ketidakhadiran_Guru.xlsx"

@st.cache_data
def muat_data_pdf(file_path):
    all_data = []
    PETA_BIASA = {1:("6:40","7:00"), 2:("7:00","7:30"), 3:("7:30","8:00"), 4:("8:00","8:30"), 5:("8:30","9:00"), 6:("9:00","9:30"), 7:("9:30","10:00"), 8:("10:00","10:30"), 9:("10:30","11:00"), 10:("11:00","11:30"), 11:("11:30","12:00"), 12:("12:00","12:30"), 13:("12:30","1:00"), 14:("1:00","1:30"), 15:("1:30","2:00"), 16:("2:00","2:30"), 17:("2:30","3:00")}
    PETA_JUMAAT = {1:("6:40","7:10"), 2:("7:10","7:40"), 3:("7:40","8:10"), 4:("8:10","8:40"), 5:("8:40","9:10"), 6:("9:10","9:40"), 7:("9:40","10:10"), 8:("10:10","10:40"), 9:("10:40","11:10"), 10:("11:10","11:40"), 11:("11:40","12:10"), 12:("12:10","12:40")}
    
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
                            all_data.append({"id": slot_id, "Guru": nama_guru, "Hari": hari, "Isi": row[i].replace("\n", " "), "Masa": f"{mula}-{tamat}"})
    return pd.DataFrame(all_data)

# --- FUNGSI SIMPAN KE EXCEL ---
def simpan_ke_excel(data_baru):
    if os.path.exists(FAIL_REKOD):
        df_lama = pd.read_excel(FAIL_REKOD)
        df_final = pd.concat([df_lama, data_baru], ignore_index=True)
    else:
        df_final = data_baru
    df_final.to_excel(FAIL_REKOD, index=False)

# --- UI ---
st.title("📊 e-PdP Tracker SMK Kinarut")

try:
    df = muat_data_pdf("Tracker.pdf")
    
    with st.sidebar:
        st.header("Konfigurasi")
        pilihan_guru = st.selectbox("Pilih Nama Guru:", df['Guru'].unique())
        hari_ini = st.radio("Pilih Hari:", ["ISNIN", "SELASA", "RABU", "KHAMIS", "JUMAAT"])
        tarikh_pantau = st.date_input("Tarikh Pemantauan:", datetime.now())
        
        if st.button("🗑️ Kosongkan Tanda"):
            st.session_state.rekod_temp = {}
            st.rerun()

    jadual_individu = df[(df['Guru'] == pilihan_guru) & (df['Hari'] == hari_ini)]
    st.subheader(f"Jadual: {pilihan_guru}")

    if jadual_individu.empty:
        st.info("Tiada kelas.")
    else:
        cols = st.columns(3)
        for index, row in enumerate(jadual_individu.itertuples()):
            with cols[index % 3]:
                is_selected = row.id in st.session_state.rekod_temp
                box_color = "🔴" if is_selected else "🟢"
                
                with st.expander(f"{box_color} {row.Masa}", expanded=True):
                    st.write(f"**{row.Isi}**")
                    if is_selected:
                        if st.button("Batalkan", key=row.id):
                            del st.session_state.rekod_temp[row.id]
                            st.rerun()
                    else:
                        if st.button("Tanda Tidak Hadir", key=row.id):
                            st.session_state.rekod_temp[row.id] = {
                                "Tarikh": tarikh_pantau.strftime("%d/%m/%Y"),
                                "Nama Guru": row.Guru,
                                "Hari": row.Hari,
                                "Masa": row.Masa,
                                "Subjek/Kelas": row.Isi,
                                "Masa Rekod": datetime.now().strftime("%H:%M:%S")
                            }
                            st.rerun()

    # --- BUTANG HANTAR ---
    st.divider()
    if st.session_state.rekod_temp:
        st.write("### Senarai Bakal Dilaporkan:")
        df_temp = pd.DataFrame(list(st.session_state.rekod_temp.values()))
        st.table(df_temp)
        
        if st.button("🚀 HANTAR & SIMPAN LAPORAN"):
            simpan_ke_excel(df_temp)
            st.session_state.rekod_temp = {} # Kosongkan selepas simpan
            st.success("Rekod telah disimpan ke dalam fail Excel!")
            st.balloons()
            
    # Papar butang muat turun fail rekod jika wujud
    if os.path.exists(FAIL_REKOD):
        with open(FAIL_REKOD, "rb") as f:
            st.download_button("📥 Muat Turun Fail Rekod (Excel)", f, file_name=FAIL_REKOD)

except Exception as e:
    st.error(f"Ralat: {e}")
    
# --- BAHAGIAN ANALISIS STRATEGIK (MINGGUAN/BULANAN) ---
st.divider()
st.header("📈 Analisis Ketidakhadiran Berkala")

if os.path.exists(FAIL_REKOD):
    df_full = pd.read_excel(FAIL_REKOD)
    
    # Tukar kolom Tarikh ke format datetime supaya boleh ditapis
    df_full['Tarikh_DT'] = pd.to_datetime(df_full['Tarikh'], format='%d/%m/%Y')
    
    # 1. Tapis mengikut Julat Tarikh
    col_tgl1, col_tgl2 = st.columns(2)
    with col_tgl1:
        mula = st.date_input("Dari Tarikh:", df_full['Tarikh_DT'].min())
    with col_tgl2:
        tamat = st.date_input("Hingga Tarikh:", df_full['Tarikh_DT'].max())
    
    mask = (df_full['Tarikh_DT'] >= pd.Timestamp(mula)) & (df_full['Tarikh_DT'] <= pd.Timestamp(tamat))
    df_filtered = df_full.loc[mask]

    if not df_filtered.empty:
        # --- PAPARAN TAB ANALISIS ---
        tab1, tab2, tab3 = st.tabs(["📊 Rumusan Guru", "🏫 Analisis Kelas", "📅 Rekod Penuh"])

        with tab1:
            st.subheader("Analisis Beban PdP Terbiar mengikut Guru")
            
            # 1. Kira jumlah slot
            analisis_guru = df_filtered['Nama Guru'].value_counts().reset_index()
            analisis_guru.columns = ['Nama Guru', 'Jumlah Slot']
            
            # 2. Tambah kolom Jumlah Minit dan Jumlah Jam
            # Formula: Slot * 30 minit / 60 minit = Jam
            analisis_guru['Jumlah Jam'] = (analisis_guru['Jumlah Slot'] * 30) / 60
            
            # 3. Papar Graf mengikut Jam
            st.bar_chart(data=analisis_guru, x='Nama Guru', y='Jumlah Jam')
            
            # 4. Papar Jadual dengan info lebih detail
            st.table(analisis_guru.sort_values(by='Jumlah Jam', ascending=False))
            
            st.write(f"💡 *Nota: Pengiraan adalah berdasarkan anggapan 1 slot = 30 minit.*")

        with tab2:
            st.subheader("🏫 Analisis Impak Strategik (Kelas & Subjek)")

            # Sediakan data: Asingkan Subjek dan Kelas daripada teks "Subjek/Kelas"
            # Kita guna regex ringkas untuk ambil kod kelas (cth: 4A, 1B)
            def ekstrak_info(teks):
                match = re.search(r'(\d[A-Z\s]+)', teks)
                kelas = match.group(1).strip() if match else "Lain-lain"
                subjek = teks.split(kelas)[0].strip() if match else teks
                return pd.Series([subjek, kelas])

            df_filtered[['Subjek_Nama', 'Kelas_Nama']] = df_filtered['Subjek/Kelas'].apply(ekstrak_info)

            # --- BAHAGIAN A: ANALISIS KELAS (GABUNG SEMUA SUBJEK) ---
            st.markdown("### 1. Kelas Paling Terkesan (Semua Subjek)")
            analisis_kelas_jam = df_filtered.groupby('Kelas_Nama').size().reset_index(name='Slot')
            analisis_kelas_jam['Total Jam'] = (analisis_kelas_jam['Slot'] * 30) / 60
            analisis_kelas_jam = analisis_kelas_jam.sort_values(by='Total Jam', ascending=False)

            st.bar_chart(data=analisis_kelas_jam, x='Kelas_Nama', y='Total Jam')
            st.dataframe(analisis_kelas_jam[['Kelas_Nama', 'Total Jam']], use_container_width=True, hide_index=True)
            
            st.info("💡 *Kelas di atas adalah kelas yang paling banyak kehilangan waktu PdP secara keseluruhan (gabungan semua subjek).*")

            st.divider()

            # --- BAHAGIAN B: ANALISIS SUBJEK (GABUNG SEMUA KELAS) ---
            st.markdown("### 2. Subjek Paling Terkesan (Semua Kelas)")
            analisis_subjek_jam = df_filtered.groupby('Subjek_Nama').size().reset_index(name='Slot')
            analisis_subjek_jam['Total Jam'] = (analisis_subjek_jam['Slot'] * 30) / 60
            analisis_subjek_jam = analisis_subjek_jam.sort_values(by='Total Jam', ascending=False)

            st.bar_chart(data=analisis_subjek_jam, x='Subjek_Nama', y='Total Jam', color="#ff4b4b")
            st.dataframe(analisis_subjek_jam[['Subjek_Nama', 'Total Jam']], use_container_width=True, hide_index=True)

            st.warning("⚠️ *Subjek di atas menunjukkan keciciran jam mengajar yang tinggi merentasi seluruh sekolah.*")

        with tab3:
            st.subheader("Senarai Terperinci")
            st.dataframe(df_filtered.drop(columns=['Tarikh_DT']), use_container_width=True)
    else:
        st.warning("Tiada rekod dijumpai dalam julat tarikh tersebut.")
else:
    st.info("Sila hantar laporan pertama anda untuk melihat analisis.")