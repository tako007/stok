import streamlit as st
import pandas as pd
import requests
import base64
import os
from io import StringIO
from datetime import date

# --------------------------------------------------
# BASIC AUTH AYARLARI (PoC amaçlı)
# --------------------------------------------------
VALID_USERNAME = "mutdhlab"
VALID_PASSWORD = "12345MUTDH"

# --------------------------------------------------
# Session state
# --------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# --------------------------------------------------
# LOGIN EKRANI
# --------------------------------------------------
def login():
    st.title("🔐 Giriş Yap")

    with st.form("login_form"):
        username = st.text_input("Kullanıcı Adı")
        password = st.text_input("Şifre", type="password")
        submit = st.form_submit_button("Giriş")

    if submit:
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            st.session_state.authenticated = True
            st.success("Giriş başarılı")
            st.rerun()
        else:
            st.error("Kullanıcı adı veya şifre yanlış")

# --------------------------------------------------
# GITHUB AYARLARI
# --------------------------------------------------
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = os.getenv("GITHUB_REPO")
CSV_PATH = os.getenv("CSV_PATH")
BRANCH = "main"

API_URL = f"https://api.github.com/repos/{REPO}/contents/{CSV_PATH}"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# --------------------------------------------------
# CSV OKU
# --------------------------------------------------
def load_csv():
    r = requests.get(API_URL, headers=HEADERS)
    r.raise_for_status()
    data = r.json()

    content = base64.b64decode(data["content"]).decode("utf-8")
    df = pd.read_csv(StringIO(content))
    return df, data["sha"]

# --------------------------------------------------
# CSV GÜNCELLE
# --------------------------------------------------
def update_csv(df, sha):
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    encoded = base64.b64encode(csv_bytes).decode("utf-8")

    payload = {
        "message": "Yeni stok kaydı eklendi",
        "content": encoded,
        "sha": sha,
        "branch": BRANCH
    }

    r = requests.put(API_URL, headers=HEADERS, json=payload)
    r.raise_for_status()

# --------------------------------------------------
# AUTH KONTROLÜ
# --------------------------------------------------
if not st.session_state.authenticated:
    login()
    st.stop()

# --------------------------------------------------
# UYGULAMA (LOGIN SONRASI)
# --------------------------------------------------
st.set_page_config(page_title="Stok Takip", layout="wide")
st.title("📦 Stok Takip Sistemi")

with st.form("stok_formu"):
    col1, col2, col3 = st.columns(3)

    with col1:
        lot_no = st.text_input("Lot Numarası")

    with col2:
        test = st.text_input("Test")

    with col3:
        son_kullanim = st.date_input(
            "Son Kullanma Tarihi",
            min_value=date.today()
        )

    kaydet = st.form_submit_button("Kaydet")

if kaydet:
    if not lot_no or not test:
        st.error("Lot numarası ve test alanı zorunlu")
    else:
        try:
            df, sha = load_csv()

            yeni_kayit = {
                "lot_numarasi": lot_no,
                "test": test,
                "son_kullanma_tarihi": son_kullanim
            }

            df = pd.concat([df, pd.DataFrame([yeni_kayit])], ignore_index=True)
            update_csv(df, sha)

            st.success("Kayıt başarıyla eklendi")
            st.rerun()

        except Exception as e:
            st.error("Bir hata oluştu")
            st.code(str(e))

st.divider()
st.subheader("📊 Mevcut Stoklar")

try:
    df, _ = load_csv()
    st.dataframe(df, use_container_width=True)
except:
    st.warning("Veri yüklenemedi")

# --------------------------------------------------
# ÇIKIŞ
# --------------------------------------------------
if st.button("Çıkış Yap"):
    st.session_state.authenticated = False
    st.rerun()
