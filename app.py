import streamlit as st
import pandas as pd
import requests, base64, os, hashlib
from io import StringIO
from datetime import date
from twilio.rest import Client

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(layout="wide")

# --------------------------------------------------
# TEST LIST
# --------------------------------------------------
TEST_LIST = [
    "Glukoz (Serum/Plazma)",
    "Üre (Serum/Plazma)",
    "Kreatinin (Serum/Plazma)",
    "ALT (Serum/Plazma)",
    "AST (Serum/Plazma)",
    "Etanol (Serum/Plazma)",
    "TSH",
    "Vitamin B12"
]

# --------------------------------------------------
# AUTH
# --------------------------------------------------
AUTH_USERNAME = os.getenv("AUTH_USERNAME")
AUTH_PASSWORD_HASH = os.getenv("AUTH_PASSWORD_HASH")

if "auth" not in st.session_state:
    st.session_state.auth = False

def login():
    st.title("🔐 Giriş")
    with st.form("login"):
        u = st.text_input("Kullanıcı adı")
        p = st.text_input("Şifre", type="password")
        if st.form_submit_button("Giriş"):
            if (
                u == AUTH_USERNAME
                and hashlib.sha256(p.encode()).hexdigest() == AUTH_PASSWORD_HASH
            ):
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("Hatalı kullanıcı adı veya şifre")

if not st.session_state.auth:
    login()
    st.stop()

# --------------------------------------------------
# GITHUB
# --------------------------------------------------
TOKEN = os.getenv("GITHUB_TOKEN")
REPO = os.getenv("GITHUB_REPO")
CSV = os.getenv("CSV_PATH")
EXPIRED = "data/expired.csv"
DELETED = "data/deleted.csv"

def headers():
    return {"Authorization": f"token {TOKEN}"}

def load_csv(path):
    r = requests.get(
        f"https://api.github.com/repos/{REPO}/contents/{path}",
        headers=headers()
    )
    r.raise_for_status()
    j = r.json()
    df = pd.read_csv(StringIO(base64.b64decode(j["content"]).decode()))
    return df, j["sha"]

def save_csv(df, sha, path, msg):
    content = base64.b64encode(df.to_csv(index=False).encode()).decode()
    requests.put(
        f"https://api.github.com/repos/{REPO}/contents/{path}",
        headers=headers(),
        json={
            "message": msg,
            "content": content,
            "sha": sha
        }
    ).raise_for_status()

# --------------------------------------------------
# TWILIO WHATSAPP (KRİTİK KISIM)
# --------------------------------------------------
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# Twilio WhatsApp Sandbox numarası (SABİT)
TWILIO_FROM = "whatsapp:+14155238886"

# KENDİ NUMARAN – whatsapp: ÖNEK ŞART
TWILIO_TO = "whatsapp:+905373554189"

def send_whatsapp(msg):
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN]):
        return

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    client.messages.create(
        body=msg,
        from_=TWILIO_FROM,
        to=TWILIO_TO
    )

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------
df, sha = load_csv(CSV)
exp_df, exp_sha = load_csv(EXPIRED)
del_df, del_sha = load_csv(DELETED)

def normalize_dates(d):
    d["son_kullanma_tarihi"] = pd.to_datetime(
        d["son_kullanma_tarihi"], errors="coerce"
    )
    return d

df = normalize_dates(df)
exp_df = normalize_dates(exp_df)
del_df = normalize_dates(del_df)

today = pd.Timestamp.today().normalize()

# --------------------------------------------------
# ALERT LOGIC (5 GÜN)
# --------------------------------------------------
if "uyari_gonderildi" not in df.columns:
    df["uyari_gonderildi"] = False

alert_df = df[
    ((df["son_kullanma_tarihi"] - today).dt.days <= 5) &
    ((df["son_kullanma_tarihi"] - today).dt.days >= 0) &
    (df["uyari_gonderildi"] == False)
]

for _, row in alert_df.iterrows():
    kalan = (row["son_kullanma_tarihi"] - today).days

    mesaj = (
        "⚠️ KİT SKT UYARISI\n\n"
        f"Test: {row['test']}\n"
        f"Lot: {row['lot_numarasi']}\n"
        f"Kalan gün: {kalan}\n"
        f"SKT: {row['son_kullanma_tarihi'].date()}"
    )

    send_whatsapp(mesaj)

    df.loc[
        (df["lot_numarasi"] == row["lot_numarasi"]) &
        (df["test"] == row["test"]),
        "uyari_gonderildi"
    ] = True

save_csv(df, sha, CSV, "SKT WhatsApp uyarıları işlendi")

# --------------------------------------------------
# MOVE EXPIRED
# --------------------------------------------------
expired = df[df["son_kullanma_tarihi"] < today]

if not expired.empty:
    exp_df = pd.concat([exp_df, expired], ignore_index=True)
    df = df[df["son_kullanma_tarihi"] >= today]
    save_csv(exp_df, exp_sha, EXPIRED, "Expired eklendi")
    save_csv(df, sha, CSV, "Expired çıkarıldı")

# --------------------------------------------------
# UI – ADD KIT
# --------------------------------------------------
st.title("📦 Kit Stok Takip")

with st.form("add"):
    c1, c2, c3, c4 = st.columns(4)
    lot = c1.text_input("Lot")
    test = c2.selectbox("Test", TEST_LIST)
    adet = c3.number_input("Adet", min_value=1, step=1)
    skt = c4.date_input("SKT", min_value=date.today())

    if st.form_submit_button("Kaydet"):
        df = pd.concat([df, pd.DataFrame([{
            "lot_numarasi": lot,
            "test": test,
            "test_sayisi": adet,
            "son_kullanma_tarihi": skt,
            "uyari_gonderildi": False
        }])], ignore_index=True)

        save_csv(df, sha, CSV, "Yeni kit eklendi")
        st.success("Eklendi")
        st.rerun()

# --------------------------------------------------
# TABLE
# --------------------------------------------------
view = df.copy()
view["kalan_gun"] = (view["son_kullanma_tarihi"] - today).dt.days
st.dataframe(view, use_container_width=True)

# --------------------------------------------------
# LOGOUT
# --------------------------------------------------
if st.button("Çıkış"):
    st.session_state.auth = False
    st.rerun()
