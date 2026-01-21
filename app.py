import streamlit as st
import pandas as pd
from datetime import datetime
from twilio.rest import Client

# -------------------------------
# TWILIO CONFIG
# -------------------------------
TWILIO_ACCOUNT_SID = st.secrets.get("TWILIO_SID")
TWILIO_AUTH_TOKEN = st.secrets.get("TWILIO_TOKEN")
TWILIO_FROM = st.secrets.get("TWILIO_FROM")   # whatsapp:+14155238886
TWILIO_TO = st.secrets.get("TWILIO_TO")       # whatsapp:+905...

def send_whatsapp(msg: str):
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM, TWILIO_TO]):
        return

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client.messages.create(
        body=msg,
        from_=TWILIO_FROM,
        to=TWILIO_TO
    )

# -------------------------------
# LOAD DATA
# -------------------------------
st.title("📦 Kit Son Kullanma Tarihi Takibi")

uploaded_file = st.file_uploader("Excel dosyasını yükle", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df["son_kullanma_tarihi"] = pd.to_datetime(df["son_kullanma_tarihi"])

    today = datetime.today().date()

    for _, row in df.iterrows():
        kalan = (row["son_kullanma_tarihi"].date() - today).days

        if 0 < kalan <= 5:
            mesaj = (
                "⚠️ KİT SKT UYARISI\n\n"
                f"Kit adı: {row['kit_adi']}\n"
                f"Lot: {row['lot_numarasi']}\n"
                f"Kalan gün: {kalan}\n"
                f"SKT: {row['son_kullanma_tarihi'].date()}"
            )
            send_whatsapp(mesaj)

    st.success("Kontrol tamamlandı. Uygun kayıtlar için WhatsApp bildirimi gönderildi.")
