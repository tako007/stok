import streamlit as st
import pandas as pd
import requests, base64, os, hashlib
from io import StringIO
from datetime import date
from twilio.rest import Client

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(layout="centered", page_title="Kit Stok Takip")

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

# --------------------------------------------------
# AUTH
# --------------------------------------------------
if "auth" not in st.session_state:
    st.session_state.auth = False

def login():
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

if not st.session_state.auth:
    login()
    st.stop()

# --------------------------------------------------
# GITHUB FUNCTIONS (409 CONFLICT FIX)
# --------------------------------------------------
def get_headers():
    return {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}

def load_csv(path):
    r = requests.get(f"https://api.github.com/repos/{REPO}/contents/{path}", headers=get_headers())
    r.raise_for_status()
    j = r.json()
    df = pd.read_csv(StringIO(base64.b64decode(j["content"]).decode()))
    if "son_kullanma_tarihi" in df.columns:
        df["son_kullanma_tarihi"] = pd.to_datetime(df["son_kullanma_tarihi"], errors="coerce")
    return df, j["sha"]

def save_csv(df, sha, path, msg):
    """Dosyayı kaydeder ve GitHub'dan gelen YENİ SHA değerini döndürür."""
    content = base64.b64encode(df.to_csv(index=False).encode()).decode()
    payload = {"message": msg, "content": content, "sha": sha}
    r = requests.put(f"https://api.github.com/repos/{REPO}/contents/{path}", headers=get_headers(), json=payload)
    r.raise_for_status()
    return r.json()["content"]["sha"]

# --------------------------------------------------
# TWILIO
# --------------------------------------------------
def send_sms(msg):
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    f = os.getenv("TWILIO_FROM")
    t = os.getenv("TWILIO_TO")
    if all([sid, token, f, t]):
        try:
            Client(sid, token).messages.create(body=msg, from_=f, to=t)
        except Exception as e:
            st.error(f"SMS Hatası: {e}")

# --------------------------------------------------
# MAIN DATA PROCESSING
# --------------------------------------------------
# 1. Veriyi yükle
df, sha = load_csv(CSV_PATH)
exp_df, exp_sha = load_csv(EXPIRED_PATH)
today = pd.Timestamp.today().normalize()

# 2. Otomatik İşlemler (Sıralı SHA Güncelleme)
needs_save = False

# A) Uyarı Mantığı
if "uyari_gonderildi" not in df.columns:
    df["uyari_gonderildi"] = False

alert_df = df[((df["son_kullanma_tarihi"] - today).dt.days <= 5) & (df["uyari_gonderildi"] == False)]

if not alert_df.empty:
    for idx, row in alert_df.iterrows():
        kalan = (row["son_kullanma_tarihi"] - today).days
        send_sms(f"⚠️ KIT UYARISI: {row['test']} için {kalan} gün kaldı! SKT: {row['son_kullanma_tarihi'].date()}")
        df.at[idx, "uyari_gonderildi"] = True
    needs_save = True

# B) SKT Geçenleri Taşıma
expired_mask = df["son_kullanma_tarihi"] < today
if expired_mask.any():
    expired_rows = df[expired_mask].copy()
    exp_df = pd.concat([exp_df, expired_rows], ignore_index=True)
    df = df[~expired_mask].copy()
    
    # Expired dosyasını güncelle
    exp_sha = save_csv(exp_df, exp_sha, EXPIRED_PATH, "Expired listesi guncellendi")
    needs_save = True

# C) Eğer bir değişiklik olduysa ana tabloyu kaydet (YENİ SHA İLE)
if needs_save:
    sha = save_csv(df, sha, CSV_PATH, "SKT ve Uyari güncellemeleri yapildi")

# --------------------------------------------------
# UI
# --------------------------------------------------
st.title("📦 Kit Stok Takip")

with st.form("add_new"):
    st.subheader("Yeni Kit Ekle")
    c1, c2, c3, c4 = st.columns(4)
    lot = c1.text_input("Lot")
    test = c2.selectbox("Test", TEST_LIST)
    adet = c3.number_input("Adet", min_value=1)
    skt = c4.date_input("SKT", min_value=date.today())
    
    if st.form_submit_button("Kaydet"):
        new_row = pd.DataFrame([{
            "lot_numarasi": lot, "test": test, "test_sayisi": adet,
            "son_kullanma_tarihi": pd.to_datetime(skt), "uyari_gonderildi": False
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        # Form içindeki kayıt her zaman en güncel sha'yı kullanır
        save_csv(df, sha, CSV_PATH, f"Yeni Kit: {test}")
        st.success("Başarıyla eklendi!")
        st.rerun()

# Görünüm
st.divider()
view = df.copy()
view["kalan_gun"] = (view["son_kullanma_tarihi"] - today).dt.days
st.dataframe(view.sort_values("son_kullanma_tarihi"), use_container_width=True)

if st.button("Çıkış Yap"):
    st.session_state.auth = False
    st.rerun()
