import streamlit as st
import pandas as pd
import requests, base64, os, hashlib
from io import StringIO
from datetime import date
from twilio.rest import Client

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Kit Stok Takip", layout="centered")

# --------------------------------------------------
# TEST LIST & SECRETS
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
# AUTH LOGIC
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
# GITHUB API FUNCTIONS (IMPROVED)
# --------------------------------------------------
def get_headers():
    return {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}

def load_csv(path):
    """Dosyayı indirir, DataFrame ve güncel SHA döner."""
    try:
        r = requests.get(f"https://api.github.com/repos/{REPO}/contents/{path}", headers=get_headers())
        r.raise_for_status()
        j = r.json()
        df = pd.read_csv(StringIO(base64.b64decode(j["content"]).decode()))
        # Tarih kolonunu hemen Timestamp'e çevir
        if "son_kullanma_tarihi" in df.columns:
            df["son_kullanma_tarihi"] = pd.to_datetime(df["son_kullanma_tarihi"], errors="coerce")
        return df, j["sha"]
    except Exception as e:
        st.error(f"Dosya yükleme hatası ({path}): {e}")
        return pd.DataFrame(), None

def save_csv(df, sha, path, msg):
    """Dosyayı kaydeder ve yeni gelen SHA değerini döner (Kritik)."""
    content = base64.b64encode(df.to_csv(index=False).encode()).decode()
    data = {"message": msg, "content": content, "sha": sha}
    r = requests.put(f"https://api.github.com/repos/{REPO}/contents/{path}", headers=get_headers(), json=data)
    if r.status_code == 200 or r.status_code == 201:
        return r.json()["content"]["sha"]
    else:
        st.error(f"GitHub Kayıt Hatası: {r.text}")
        return sha

# --------------------------------------------------
# TWILIO SMS
# --------------------------------------------------
def send_sms(msg):
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_no = os.getenv("TWILIO_FROM")
    to_no = os.getenv("TWILIO_TO")
    
    if all([sid, token, from_no, to_no]):
        try:
            client = Client(sid, token)
            client.messages.create(body=msg, from_=from_no, to=to_no)
        except Exception as e:
            st.warning(f"SMS gönderilemedi: {e}")

# --------------------------------------------------
# MAIN LOGIC (DATA LOAD & SYNC)
# --------------------------------------------------
# Verileri yükle
df, sha = load_csv(CSV_PATH)
exp_df, exp_sha = load_csv(EXPIRED_PATH)
today = pd.Timestamp.today().normalize()

if not df.empty:
    updated = False
    
    # 1. UYARI MEKANİZMASI (5 GÜN KALA)
    if "uyari_gonderildi" not in df.columns:
        df["uyari_gonderildi"] = False
    
    alert_mask = ((df["son_kullanma_tarihi"] - today).dt.days <= 5) & (df["uyari_gonderildi"] == False)
    
    if alert_mask.any():
        for idx, row in df[alert_mask].iterrows():
            kalan = (row["son_kullanma_tarihi"] - today).days
            mesaj = f"⚠️ KIT UYARISI\nTest: {row['test']}\nLot: {row['lot_numarasi']}\nKalan: {kalan} gün"
            send_sms(mesaj)
            df.at[idx, "uyari_gonderildi"] = True
        updated = True

    # 2. SKT GEÇENLERİ TAŞIMA
    expired_mask = df["son_kullanma_tarihi"] < today
    if expired_mask.any():
        expired_items = df[expired_mask].copy()
        exp_df = pd.concat([exp_df, expired_items], ignore_index=True)
        df = df[~expired_mask].copy()
        
        # Önce expired dosyasını güncelle
        exp_sha = save_csv(exp_df, exp_sha, EXPIRED_PATH, "SKT dolanlar tasindi")
        updated = True

    # Değişiklik varsa ana dosyayı GitHub'a yaz
    if updated:
        sha = save_csv(df, sha, CSV_PATH, "Otomatik stok guncelleme")

# --------------------------------------------------
# UI - ADD NEW ITEM
# --------------------------------------------------
st.title("📦 Kit Stok Takip")

with st.expander("➕ Yeni Kit Ekle", expanded=False):
    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        lot = c1.text_input("Lot Numarası")
        test = c2.selectbox("Test Adı", TEST_LIST)
        
        c3, c4 = st.columns(2)
        adet = c3.number_input("Adet/Test Sayısı", min_value=1, value=100)
        skt = c4.date_input("Son Kullanma Tarihi", min_value=date.today())

        if st.form_submit_button("Sisteme Kaydet"):
            new_data = pd.DataFrame([{
                "lot_numarasi": lot,
                "test": test,
                "test_sayisi": adet,
                "son_kullanma_tarihi": pd.to_datetime(skt),
                "uyari_gonderildi": False
            }])
            df = pd.concat([df, new_data], ignore_index=True)
            sha = save_csv(df, sha, CSV_PATH, f"Yeni kit eklendi: {test}")
            st.success("Kit başarıyla eklendi!")
            st.rerun()

# --------------------------------------------------
# UI - TABLE VIEW
# --------------------------------------------------
if not df.empty:
    st.subheader("Mevcut Stok Durumu")
    view_df = df.copy()
    view_df["kalan_gun"] = (view_df["son_kullanma_tarihi"] - today).dt.days
    
    # Görselleştirme için renklendirme (isteğe bağlı)
    def color_days(val):
        color = 'red' if val <= 7 else 'orange' if val <= 30 else 'black'
        return f'color: {color}'

    st.dataframe(
        view_df.sort_values("son_kullanma_tarihi"),
        use_container_width=True,
        column_config={
            "son_kullanma_tarihi": st.column_config.DateColumn("SKT"),
            "kalan_gun": st.column_config.NumberColumn("Kalan Gün", format="%d gün")
        }
    )
else:
    st.info("Stokta kayıtlı kit bulunamadı.")

# --------------------------------------------------
# LOGOUT
# --------------------------------------------------
st.divider()
if st.button("Güvenli Çıkış"):
    st.session_state.auth = False
    st.rerun()
