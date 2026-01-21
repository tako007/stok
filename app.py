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
            if u == AUTH_USERNAME and hashlib.sha256(p.encode()).hexdigest() == AUTH_PASSWORD_HASH:
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
        json={"message": msg, "content": content, "sha": sha}
    ).raise_for_status()

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------
df, sha = load_csv(CSV)
del_df, del_sha = load_csv(DELETED)

df["son_kullanma_tarihi"] = pd.to_datetime(df["son_kullanma_tarihi"], errors="coerce")
today = pd.Timestamp.today().normalize()

# --------------------------------------------------
# FILTER
# --------------------------------------------------
st.title("📦 Kit Stok Takip")

selected_tests = st.multiselect(
    "Teste göre filtrele",
    options=sorted(df["test"].dropna().unique())
)

view = df.copy()
if selected_tests:
    view = view[view["test"].isin(selected_tests)]

view["kalan_gun"] = (view["son_kullanma_tarihi"] - today).dt.days

# --------------------------------------------------
# HEADER
# --------------------------------------------------
st.subheader("🟢 Aktif Kitler")

h = st.columns([2, 3, 1, 2, 1, 0.7])
h[0].markdown("**Lot**")
h[1].markdown("**Test**")
h[2].markdown("**Adet**")
h[3].markdown("**SKT**")
h[4].markdown("**Kalan Gün**")
h[5].markdown("")

st.divider()

# --------------------------------------------------
# ROWS
# --------------------------------------------------
for _, row in view.iterrows():
    c = st.columns([2, 3, 1, 2, 1, 0.7])

    c[0].write(row["lot_numarasi"])
    c[1].write(row["test"])
    c[2].write(row["test_sayisi"])
    c[3].write(row["son_kullanma_tarihi"].date())
    c[4].write(int(row["kalan_gun"]))

    if c[5].button("🗑️", key=f"del_{row['lot_numarasi']}_{row['test']}"):
        del_df = pd.concat([del_df, row.to_frame().T], ignore_index=True)

        df = df.drop(
            df[
                (df["lot_numarasi"] == row["lot_numarasi"]) &
                (df["test"] == row["test"])
            ].index
        )

        save_csv(del_df, del_sha, DELETED, "Kit silindi")
        save_csv(df, sha, CSV, "Kit silindi")
        st.rerun()

# --------------------------------------------------
# TOTAL (FILTERED)
# --------------------------------------------------
st.divider()
toplam = view["test_sayisi"].sum()

st.info(
    f"🔢 Seçili filtreye göre toplam test sayısı: **{int(toplam)}**"
)

# --------------------------------------------------
# LOGOUT
# --------------------------------------------------
if st.button("Çıkış"):
    st.session_state.auth = False
    st.rerun()
