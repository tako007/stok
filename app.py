
# ---- imports ----
import streamlit as st
import pandas as pd
import requests, base64, os, hashlib
from io import StringIO
from datetime import date

# ---- TEST LIST ----
TEST_LIST = [
    "Alanin aminotransferaz (ALT) (Serum/Plazma)",
    "Albümin (Serum/Plazma)",
    "Alkalen fosfataz (Serum/Plazma)",
    "Amilaz (Serum/Plazma)",
    "Antistreptolizin O (ASO)",
    "Aspartat aminotransferaz (AST) (Serum/Plazma)",
    "Bilirubin, direkt (Serum/Plazma)",
    "Bilirubin, total (Serum/Plazma)",
    "C reaktif protein (CRP)",
    "Demir (Serum/Plazma)",
    "Demir bağlama kapasitesi",
    "Etanol (Serum/Plazma)",
    "Fosfor (Serum/Plazma)",
    "Gamma glutamil transferaz (GGT) (Serum/Plazma)",
    "Glukoz (Serum/Plazma)",
    "HDL kolesterol",
    "Kalsiyum (Serum/Plazma)",
    "Klorür (Serum/Plazma)",
    "Kolesterol (Serum/Plazma)",
    "Kreatin kinaz (Serum/Plazma)",
    "Kreatinin (Serum/Plazma)",
    "Laktat dehidrogenaz (Serum/Plazma)",
    "LDL kolesterol (Direkt)",
    "Magnezyum (Serum/Plazma)",
    "Potasyum (Serum/Plazma)",
    "Protein (Serum/Plazma)",
    "Romatoid faktör (RF)",
    "Sodyum (Serum/Plazma)",
    "Trigliserid (Serum/Plazma)",
    "Üre (Serum/Plazma)",
    "Ürik asit (Serum/Plazma)",
    "Glike hemoglobin (Hb A1c)",
    "Anti HBs",
    "Anti HCV",
    "Anti HIV",
    "HBsAg",
    "25-Hidroksi vitamin D",
    "Estradiol (E2)",
    "Ferritin (Serum/Plazma)",
    "Folat (Serum/Plazma)",
    "FSH",
    "İnsülin",
    "CK-MB",
    "LH",
    "Parathormon (PTH)",
    "Prolaktin",
    "PSA total",
    "Serbest T3",
    "Serbest T4",
    "Total HCG",
    "Troponin I",
    "TSH",
    "Vitamin B12"
]




# ---- AUTH ----
AUTH_USERNAME = os.getenv("AUTH_USERNAME")
AUTH_PASSWORD_HASH = os.getenv("AUTH_PASSWORD_HASH")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def login():
    st.title("🔐 Giriş")
    with st.form("login"):
        u = st.text_input("Kullanıcı adı")
        p = st.text_input("Şifre", type="password")
        if st.form_submit_button("Giriş"):
            if u == AUTH_USERNAME and hashlib.sha256(p.encode()).hexdigest() == AUTH_PASSWORD_HASH:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Hatalı bilgi")

if not st.session_state.authenticated:
    login()
    st.stop()

# ---- GITHUB ----
TOKEN = os.getenv("GITHUB_TOKEN")
REPO = os.getenv("GITHUB_REPO")
CSV = os.getenv("CSV_PATH")
EXPIRED = "data/expired.csv"

def gh_headers():
    return {"Authorization": f"token {TOKEN}"}

def load(path):
    r = requests.get(f"https://api.github.com/repos/{REPO}/contents/{path}", headers=gh_headers())
    r.raise_for_status()
    j = r.json()
    df = pd.read_csv(StringIO(base64.b64decode(j["content"]).decode()))
    return df, j["sha"]

def save(df, sha, path, msg):
    content = base64.b64encode(df.to_csv(index=False).encode()).decode()
    requests.put(
        f"https://api.github.com/repos/{REPO}/contents/{path}",
        headers=gh_headers(),
        json={"message": msg, "content": content, "sha": sha}
    ).raise_for_status()

# ---- LOAD DATA ----
df, sha = load(CSV)
exp_df, exp_sha = load(EXPIRED)

# ---- EXPIRED MOVE ----
today = pd.to_datetime(date.today())
df["son_kullanma_tarihi"] = pd.to_datetime(df["son_kullanma_tarihi"], errors="coerce")

expired_rows = df[df["son_kullanma_tarihi"] < today]
if not expired_rows.empty:
    exp_df = pd.concat([exp_df, expired_rows])
    df = df[df["son_kullanma_tarihi"] >= today]
    save(exp_df, exp_sha, EXPIRED, "Expired kit eklendi")
    save(df, sha, CSV, "Expired kit çıkarıldı")

# ---- UI ----
st.title("📦 Kit Stok Takip")

with st.form("add"):
    c1, c2, c3, c4 = st.columns(4)
    lot = c1.text_input("Lot")
    test = c2.selectbox("Test", TEST_LIST)
    adet = c3.number_input("Test sayısı", min_value=1, step=1)
    skt = c4.date_input("SKT")
    if st.form_submit_button("Kaydet"):
        df = pd.concat([df, pd.DataFrame([{
            "lot_numarasi": lot,
            "test": test,
            "test_sayisi": adet,
            "son_kullanma_tarihi": skt
        }])])
        save(df, sha, CSV, "Yeni kit eklendi")
        st.rerun()

# ---- FILTER ----
filter_test = st.selectbox("Test filtresi", ["Tümü"] + TEST_LIST)
if filter_test != "Tümü":
    view = df[df["test"] == filter_test]
else:
    view = df

st.dataframe(view)

st.info(f"Toplam test sayısı: {view['test_sayisi'].sum()}")

if st.button("Çıkış"):
    st.session_state.authenticated = False
    st.rerun()

