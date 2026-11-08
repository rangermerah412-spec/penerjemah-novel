import streamlit as st
import os
import zipfile
import shutil
import time
import concurrent.futures
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

# Setel konfigurasi halaman dasar
st.set_page_config(page_title="Translator EPUB", page_icon="📖")

st.title("📖 Penerjemah Novel EPUB (EN/KO ➡️ ID)")
st.write("Terjemahkan novel ratusan bab dari Bahasa Inggris atau Korea ke Bahasa Indonesia langsung dari HP Anda.")

# Pilihan Bahasa Asal Novel
bahasa_asal = st.selectbox(
    "Pilih Bahasa Asal Novel:",
    options=["auto", "en", "ko"],
    format_func=lambda x: {"auto": "Deteksi Otomatis (Rekomendasi)", "en": "Inggris (English)", "ko": "Korea (한국어)"}[x]
)

st.info("💡 Bahasa tujuan otomatis ke: **Bahasa Indonesia**")

# Area Unggah File EPUB di HP
uploaded_file = st.file_uploader("Unggah file EPUB novel Anda:", type=["epub"])

# Fungsi internal untuk menerjemahkan satu node teks (Target Thread)
def translate_node(text_node, translator):
    if text_node.parent.name in ['script', 'style'] or not text_node.strip():
        return False
    
    teks_asli = text_node.strip()
    if len(teks_asli) > 2:
        try:
            teks_terjemahan = translator.translate(teks_asli)
            text_node.replace_with(teks_terjemahan)
            return True
        except Exception as e:
            # Jika terkena Rate Limit (Error 429), beri jeda sedikit agar server tenang
            if "429" in str(e):
                time.sleep(2)
            return False
    return False

if uploaded_file is not None:
    file_asli = uploaded_file.name
    st.success(f"File '{file_asli}' berhasil dimuat!")

    # Tombol Eksekusi
    if st.button("🚀 Mulai Terjemahkan"):
        extract_dir = "temp_epub_extracted"
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir)

        with open(file_asli, "wb") as f:
            f.write(uploaded_file.getbuffer())

        with zipfile.ZipFile(file_asli, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        translator = GoogleTranslator(source=bahasa_asal, target='id')

        # Membuat daftar penampung file menggunakan fungsi list() agar aman
        files_to_translate = list()
        for root, dirs, files_in_dir in os.walk(extract_dir):
            for file in files_in_dir:
                if file.lower().endswith(('.html', '.xhtml', '.htm')):
                    files_to_translate.append(os.path.join(root, file))
        files_to_translate.sort()

        total_file = len(files_to_translate)
        progress_bar = st.progress(0)
        status_text = st.empty()

        for index, file_path in enumerate(files_to_translate):
            nama_bab = os.path.basename(file_path)
            status_text.text(f"⏳ Menerjemahkan: {nama_bab} ({index+1}/{total_file})")
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            
            nodes = soup.find_all(string=True)
            perubahan = False
            
            # --- BAGIAN OPTIMASI MULTITHREADING ---
            # max_workers=10 berarti menerjemahkan hingga 10 baris teks sekaligus secara bersamaan
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                # Kirim semua node teks di bab ini ke dalam antrean thread pool
                futures = [executor.submit(translate_node, node, translator) for node in nodes]
                
                # Cek jika ada minimal satu teks yang berhasil diubah
                for future in concurrent.futures.as_completed(futures):
                    if future.result():
                        perubahan = True
            # --------------------------------------
            
            if perubahan:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(str(soup))
            
            progress_bar.progress((index + 1) / total_file)

        status_text.text("📦 Menyusun kembali file buku...")
        
        file_baru = "TERJEMAHAN_" + file_asli
        with zipfile.ZipFile(file_baru, 'w') as zip_write:
            mimetype_path = os.path.join(extract_dir, 'mimetype')
            if os.path.exists(mimetype_path):
                zip_write.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)
            
            for root, dirs, files_in_dir in os.walk(extract_dir):
                for file in files_in_dir:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, extract_dir)
                    if arcname == 'mimetype':
                        continue
                    zip_write.write(file_path, arcname, compress_type=zipfile.ZIP_DEFLATED)

        shutil.rmtree(extract_dir)
        os.remove(file_asli)

        status_text.text("🎉 Proses penerjemahan selesai!")
        
        with open(file_baru, "rb") as f:
            st.download_button(
                label="📥 Unduh File EPUB Bahasa Indonesia",
                data=f,
                file_name=file_baru,
                mime="application/epub+zip"
            )
