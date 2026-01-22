import streamlit as st
import pandas as pd
import requests, base64, os, hashlib
from io import StringIO
from datetime import date
from twilio.rest import Client

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(layout="wide", page_title="Kit Stok Takip")

# --------------------------------------------------
# CONFIG & SECRETS
# --------------------------------------------------
TEST_LIST = [
    "Glukoz (Serum/Plazma)", "Üre (Serum/Plazma)", "Kreatinin (Serum/Plazma)",
    "ALT (Serum/Plazma)", "AST (Serum/Plazma)", "Etanol (Serum/Plazma)",
    "TSH", "Vitamin B12"
]

AUTH_USERNAME = os.getenv("AUTH_USERNAME")
AUTH_PASSWORD_HASH = os.getenv("AUTH_PASSWORD_HASH")
TOKEN = os.getenv("GITHUB_TOKEN")
REPO = os.getenv("GITHUB_REPO")
CSV_PATH = os.getenv("CSV_PATH")
EXPIRED_PATH = "data/expired.csv"
DELETED_PATH = "data/deleted.csv"

# --------------------------------------------------
# AUTH
# --------------------------------------------------
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Giriş")
    with st.form("login"):
        u = st.text_input("Kullanıcı adı")
        p = st.text_input("Şifre", type="password")
        if st.form_submit_button("Giriş"):
            if u == AUTH_USERNAME and hashlib.sha256(p.encode()).hexdigest() == AUTH_PASSWORD_HASH:
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("Hatalı kullanıcı adı veya şifre")
    st.stop()

# --------------------------------------------------
# GITHUB FUNCTIONS
# --------------------------------------------------
def get_headers():
    return {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}

def load_csv(path):
    try:
        r = requests.get(f"https://api.github.com/repos/{REPO}/contents/{path}", headers=get_headers())
        r.raise_for_status()
        j = r.json()
        df = pd.read_csv(StringIO(base64.b64decode(j["content"]).decode()))
        if "son_kullanma_tarihi" in df.columns:
            df["son_kullanma_tarihi"] = pd.to_datetime(df["son_kullanma_tarihi"], errors="coerce")
        return df, j["sha"]
    except:
        return pd.DataFrame(), None

def save_csv(df, sha, path, msg):
    content = base64.b64encode(df.to_csv(index=False).encode()).decode()
    payload = {"message": msg, "content": content, "sha": sha}
    r = requests.put(f"https://api.github.com/repos/{REPO}/contents/{path}", headers=get_headers(), json=payload)
    r.raise_for_status()
    return r.json()["content"]["sha"]

# --------------------------------------------------
# INITIAL DATA LOAD
# --------------------------------------------------
df, sha = load_csv(CSV_PATH)
exp_df, exp_sha = load_csv(EXPIRED_PATH)
del_df, del_sha = load_csv(DELETED_PATH)
today = pd.Timestamp.today().normalize()

# --------------------------------------------------
# AUTO-PROCESSING (EXPIRED & ALERTS)
# --------------------------------------------------
updated_main = False

if not df.empty:
    # SKT Geçenleri Taşı
    expired_mask = df["son_kullanma_tarihi"] < today
    if expired_mask.any():
        expired_rows = df[expired_mask].copy()
        exp_df = pd.concat([exp_df, expired_rows], ignore_index=True)
        df = df[~expired_mask].copy()
        exp_sha = save_csv(exp_df, exp_sha, EXPIRED_PATH, "Auto-expired move")
        updated_main = True

    # Değişiklik varsa ana dosyayı kaydet
    if updated_main:
        sha = save_csv(df, sha, CSV_PATH, "Main cleanup")

# --------------------------------------------------
# UI - HEADER & ADD FORM
# --------------------------------------------------
st.title("📦 Kit Stok Yönetim Paneli")

with st.expander("➕ Yeni Kit Girişi Yap"):
    with st.form("add_form"):
        c1, c2, c3, c4 = st.columns(4)
        lot = c1.text_input("Lot No")
        test = c2.selectbox("Test", TEST_LIST)
        adet = c3.number_input("Adet", min_value=1)
        skt = c4.date_input("SKT")
        if st.form_submit_button("Ekle"):
            new_row = pd.DataFrame([{"lot_numarasi": lot, "test": test, "test_sayisi": adet, 
                                     "son_kullanma_tarihi": pd.to_datetime(skt), "uyari_gonderildi": False}])
            df = pd.concat([df, new_row], ignore_index=True)
            save_csv(df, sha, CSV_PATH, f"Eklendi: {lot}")
            st.success("Kaydedildi!")
            st.rerun()

# --------------------------------------------------
# UI - TABS (EXPIRED & DELETED BURADA)
# --------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📋 Mevcut Stok", "🕒 SKT Geçenler", "🗑️ Silinenler"])

with tab1:
    if not df.empty:
        df["kalan_gun"] = (df["son_kullanma_tarihi"] - today).dt.days
        # Silme işlemi için seçim kutusu
        to_delete = st.selectbox("Silmek istediğiniz kiti seçin (Lot)", df["lot_numarasi"].tolist(), index=None, placeholder="Lot seçiniz...")
        if st.button("Seçili Kiti Sil"):
            if to_delete:
                row_to_del = df[df["lot_numarasi"] == to_delete]
                del_df = pd.concat([del_df, row_to_del], ignore_index=True)
                df = df[df["lot_numarasi"] != to_delete]
                
                # Önce Deleted listesini kaydet, sonra Main'i
                new_del_sha = save_csv(del_df, del_sha, DELETED_PATH, "Manüel silme")
                save_csv(df, sha, CSV_PATH, "Stoktan çıkarıldı")
                st.warning(f"{to_delete} lot numaralı kit silindi.")
                st.rerun()
        
        st.dataframe(df.sort_values("son_kullanma_tarihi"), use_container_width=True)
    else:
        st.write("Stok boş.")

with tab2:
    st.subheader("Süresi Dolan Kitler")
    if not exp_df.empty:
        st.dataframe(exp_df, use_container_width=True)
    else:
        st.info("Süresi dolmuş kit bulunmuyor.")

with tab3:
    st.subheader("Sistemden Silinen Kayıtlar")
    if not del_df.empty:
        st.dataframe(del_df, use_container_width=True)
    else:
        st.info("Silinmiş kayıt bulunmuyor.")

# Logout
if st.sidebar.button("Çıkış Yap"):
    st.session_state.auth = False
    st.rerun()
