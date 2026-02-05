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
                        
                        # KITA HANYA AMBIL DATA JIKA KOTAK ITU ADA TULISAN SAHAJA
                        for i in range(1, len(row)):
                            isi_raw = row[i]
                            
                            if isi_raw and str(isi_raw).strip() != "":
                                isi_bersih = str(isi_raw).replace("\n", " ").strip()
                                
                                # Tambahan: Jika kotak itu cuma ada "-" atau "REHAT", kita abaikan
                                if len(isi_bersih) > 2 and isi_bersih.lower() != "none":
                                    mula, tamat = (PETA_JUMAAT if hari == "JUMAAT" else PETA_BIASA).get(i, ("-","-"))
                                    slot_id = f"{nama_guru}_{hari}_{i}"
                                    
                                    all_data.append({
                                        "id": slot_id, 
                                        "Guru": nama_guru, 
                                        "Hari": hari, 
                                        "Isi": isi_bersih, 
                                        "Masa": f"{mula}-{tamat}"
                                    })
                                    
        return pd.DataFrame(all_data)
    except Exception as e:
        return pd.DataFrame()
