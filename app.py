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

# Fungsi internal untuk menerjemahkan string teks tunggal
def translate_single_string(text, translator):
    try:
        return translator.translate(text)
    except Exception as e:
        if "429" in str(e):
            time.sleep(2)
        # Jika gagal, kembalikan teks asli agar novel tidak kosong
        return text

if uploaded_file is not None:
    # Menggunakan timestamp unik agar nama file tidak bentrok antarpengguna
    session_id = str(int(time.time() * 1000))
    file_asli = f"temp_{session_id}_{uploaded_file.name}"
    nama_unduhan = "TERJEMAHAN_" + uploaded_file.name

    st.success(f"File '{uploaded_file.name}' berhasil dimuat!")

    # Tombol Eksekusi
    if st.button("🚀 Mulai Terjemahkan"):
        # Membuat folder ekstrak yang unik untuk setiap user
        extract_dir = f"temp_epub_{session_id}"
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir)

        with open(file_asli, "wb") as f:
            f.write(uploaded_file.getbuffer())

        with zipfile.ZipFile(file_asli, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        translator = GoogleTranslator(source=bahasa_asal, target='id')

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
            
            # 1. Kumpulkan semua node teks valid dan teks aslinya
            valid_nodes = []
            texts_to_translate = []
            
            for text_node in soup.find_all(string=True):
                if text_node.parent.name in ['script', 'style'] or not text_node.strip():
                    continue
                teks_asli = text_node.strip()
                if len(teks_asli) > 2:
                    valid_nodes.append(text_node)
                    texts_to_translate.append(teks_asli)
            
            perubahan = False
            
            # 2. Jalankan Multithreading jika ada teks
            if texts_to_translate:
                # max_workers=8 adalah batas aman terbaik untuk Google Translate gratisan
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    results = list(executor.map(lambda t: translate_single_string(t, translator), texts_to_translate))
                
                # 3. Masukkan kembali hasil terjemahan secara berurutan
                for node, teks_baru in zip(valid_nodes, results):
                    if teks_baru and teks_baru != node.strip():
                        node.replace_with(teks_baru)
                        perubahan = True
            
            if perubahan:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(str(soup))
            
            progress_bar.progress((index + 1) / total_file)

        status_text.text("📦 Menyusun kembali file buku...")
        
        file_baru = f"out_{session_id}.epub"
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

        # Bersihkan file dan folder temporary milik user ini
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        if os.path.exists(file_asli):
            os.remove(file_asli)

        status_text.text("🎉 Proses penerjemahan selesai!")
        
        with open(file_baru, "rb") as f:
            st.download_button(
                label="📥 Unduh File EPUB Bahasa Indonesia",
                data=f,
                file_name=nama_unduhan,
                mime="application/epub+zip"
            )
        
        # Hapus file output setelah tombol download siap dimuat ke memori browser
        if os.path.exists(file_baru):
            os.remove(file_baru)
