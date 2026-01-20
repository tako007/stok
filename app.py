import streamlit as st
import pandas as pd
import requests, base64, os, hashlib
from io import StringIO
from datetime import date

# --------------------------------------------------
# TEST LIST
# --------------------------------------------------
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
EXPIRED = "data/expired.csv"
DELETED = "data/deleted.csv"

def headers():
    return {"Authorization": f"token {TOKEN}"}

def load_csv(path):
    r = requests.get(f"https://api.github.com/repos/{REPO}/contents/{path}", headers=headers())
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
exp_df, exp_sha = load_csv(EXPIRED)
del_df, del_sha = load_csv(DELETED)

today = pd.to_datetime(date.today())
df["son_kullanma_tarihi"] = pd.to_datetime(df["son_kullanma_tarihi"])

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
# UI - ADD FORM
# --------------------------------------------------
st.set_page_config(layout="wide")
st.title("📦 Kit Stok Takip")

with st.form("add"):
    c1, c2, c3, c4 = st.columns(4)
    lot = c1.text_input("Lot numarası")
    test = c2.selectbox("Test", TEST_LIST)
    adet = c3.number_input("Test sayısı", min_value=1, step=1)
    skt = c4.date_input("Son Kullanma Tarihi", min_value=date.today())

    if st.form_submit_button("Kaydet"):
        dup = df[(df["lot_numarasi"] == lot) & (df["test"] == test)]
        if not dup.empty:
            st.error("❌ Aynı test + lot zaten var")
            st.stop()

        df = pd.concat([df, pd.DataFrame([{
            "lot_numarasi": lot,
            "test": test,
            "test_sayisi": adet,
            "son_kullanma_tarihi": skt
        }])], ignore_index=True)

        save_csv(df, sha, CSV, "Yeni kit eklendi")
        st.success("Kayıt eklendi")
        st.rerun()

# --------------------------------------------------
# ACTIVE TABLE (REAL TABLE)
# --------------------------------------------------
st.subheader("🟢 Aktif Kitler")

view = df.copy()
view["kalan_gun"] = (view["son_kullanma_tarihi"] - today).dt.days
view["Sil"] = False

edited = st.data_editor(
    view,
    use_container_width=True,
    disabled=["lot_numarasi", "test", "test_sayisi", "son_kullanma_tarihi", "kalan_gun"],
    column_config={
        "Sil": st.column_config.CheckboxColumn("Sil"),
        "kalan_gun": st.column_config.NumberColumn("Kalan Gün")
    }
)

if st.button("Seçilenleri Sil"):
    to_delete = edited[edited["Sil"] == True]

    if to_delete.empty:
        st.warning("Silmek için kayıt seçmedin")
    else:
        for _, row in to_delete.iterrows():
            del_df = pd.concat(
                [del_df, row.drop(["Sil", "kalan_gun"]).to_frame().T],
                ignore_index=True
            )
            df = df.drop(
                df[
                    (df["lot_numarasi"] == row["lot_numarasi"]) &
                    (df["test"] == row["test"])
                ].index
            )

        save_csv(del_df, del_sha, DELETED, "Kit silindi")
        save_csv(df, sha, CSV, "Kit silindi")
        st.success(f"{len(to_delete)} kayıt silindi")
        st.rerun()

# --------------------------------------------------
# EXPIRED & DELETED TABLES
# --------------------------------------------------
st.divider()
st.subheader("🔴 Tarihi Geçmiş Kitler")
st.dataframe(exp_df, use_container_width=True)

st.divider()
st.subheader("⚫ Silinen Kitler")
st.dataframe(del_df, use_container_width=True)

# --------------------------------------------------
# FOOTER
# --------------------------------------------------
if st.button("Çıkış"):
    st.session_state.auth = False
    st.rerun()
