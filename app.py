import streamlit as st
import os
import zipfile
import shutil
import time
import concurrent.futures
from bs4 import BeautifulSoup, NavigableString
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

# Fungsi internal untuk menerjemahkan string teks tunggal + Filter Anti-Instruksi
def translate_single_string(text, translator):
    try:
        if not text or not text.strip() or len(text.strip()) <= 2:
            return text
        
        # Filter awal dari prompt sistem
        teks_lowered = text.lower()
        kata_kunci_blokir = ["must be written", "never output", "system prompt", "instruction", "harus ditulis", "jangan pernah"]
        if any(keyword in teks_lowered for keyword in kata_kunci_blokir):
            return ""
            
        translated = translator.translate(text)
        
        # Filter setelah terjemah
        translated_lowered = translated.lower()
        if any(keyword in translated_lowered for keyword in kata_kunci_blokir):
            return ""
            
        return translated
    except Exception as e:
        if "429" in str(e):
            time.sleep(2)
        return text

if uploaded_file is not None:
    session_id = str(int(time.time() * 1000))
    file_asli = f"temp_{session_id}_{uploaded_file.name}"
    nama_unduhan = "TERJEMAHAN_" + uploaded_file.name

    st.success(f"File '{uploaded_file.name}' berhasil dimuat!")

    if st.button("🚀 Mulai Terjemahkan"):
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
            
            # --- PERBAIKAN TOTAL: Kembali menyasar objek text node langsung ---
            nodes_to_translate = []
            texts_to_translate = []
            
            for text_node in soup.find_all(string=True):
                # Lewati skrip, gaya, komentar, atau teks kosong
                if text_node.parent.name in ['script', 'style'] or isinstance(text_node, NavigableString) == False:
                    continue
                
                teks_mentah = str(text_node).strip()
                if len(teksmentah := teks_mentah) > 2:
                    nodes_to_translate.append(text_node)
                    texts_to_translate.append(teksmentah)
            
            perubahan = False
            
            if texts_to_translate:
                # Menggunakan max_workers=5 agar aman dari blokir Google web
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    results = list(executor.map(lambda t: translate_single_string(t, translator), texts_to_translate))
                
                # Masukkan kembali teks ke node objek aslinya
                for node, teks_baru in zip(nodes_to_translate, results):
                    if teks_baru is not None:
                        if teks_baru == "":
                            node.extract() # Hapus total jika terdeteksi instruksi sistem raksasa
                        elif teks_baru != str(node):
                            # Trik utama: Ganti isi string objek NavigableString langsung di tempatnya
                            node.replace_with(NavigableString(teks_baru))
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
        
        if os.path.exists(file_baru):
            os.remove(file_baru)
