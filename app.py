import streamlit as st
import pandas as pd
import requests
import base64
import os
import hashlib
from io import StringIO
from datetime import date

# --------------------------------------------------
# AUTH AYARLARI (Secrets'tan)
# --------------------------------------------------
AUTH_USERNAME = os.getenv("AUTH_USERNAME")
AUTH_PASSWORD_HASH = os.getenv("AUTH_PASSWORD_HASH")

# --------------------------------------------------
# Session
# --------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# --------------------------------------------------
# LOGIN
# --------------------------------------------------
def login():
    st.title("🔐 Giriş Yap")

    with st.form("login_form"):
        username = st.text_input("Kullanıcı Adı")
        password = st.text_input("Şifre", type="password")
        submit = st.form_submit_button("Giriş")

    if submit:
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        if username == AUTH_USERNAME and password_hash == AUTH_PASSWORD_HASH:
            st.session_state.authenticated = True
            st.success("Giriş başarılı")
            st.rerun()
        else:
            st.error("Kullanıcı adı veya şifre yanlış")

# --------------------------------------------------
# AUTH CHECK
# --------------------------------------------------
if not st.session_state.authenticated:
    login()
    st.stop()

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
    encoded = base64.b64encode(df.to_csv(index=False).encode()).decode()

    payload = {
        "message": "Yeni stok kaydı eklendi",
        "content": encoded,
        "sha": sha,
        "branch": BRANCH
    }

    r = requests.put(API_URL, headers=HEADERS, json=payload)
    r.raise_for_status()

# --------------------------------------------------
# UI
# --------------------------------------------------
st.set_page_config(page_title="Stok Takip", layout="wide")
st.title("📦 Stok Takip Sistemi")

with st.form("stok_formu"):
    c1, c2, c3 = st.columns(3)

    with c1:
        lot_no = st.text_input("Lot Numarası")

    with c2:
        test = st.text_input("Test")

    with c3:
        son_kullanim = st.date_input("Son Kullanma Tarihi", min_value=date.today())

    kaydet = st.form_submit_button("Kaydet")

if kaydet:
    if not lot_no or not test:
        st.error("Lot numarası ve test zorunlu")
    else:
        df, sha = load_csv()
        df = pd.concat([df, pd.DataFrame([{
            "lot_numarasi": lot_no,
            "test": test,
            "son_kullanma_tarihi": son_kullanim
        }])], ignore_index=True)

        update_csv(df, sha)
        st.success("Kayıt eklendi")
        st.rerun()

st.divider()
st.subheader("📊 Mevcut Stoklar")
df, _ = load_csv()
st.dataframe(df, use_container_width=True)

if st.button("Çıkış Yap"):
    st.session_state.authenticated = False
    st.rerun()
