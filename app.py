import datetime as dt
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
import streamlit as st

st.set_page_config(page_title="Crypto Macro Heat", layout="wide")
plt.rcParams["figure.figsize"] = (14, 8)

START_DATE = "2017-01-01"
WEEKLY_VOL_WINDOW = 26
WEEKLY_TREND_WINDOW = 52
FG_OVERHEAT = 80
MIN_FG_WEEKS = 3
STRETCH_THRESHOLD = 0.5

def make_tz_naive(idx):
    try:
        return idx.tz_localize(None)
    except Exception:
        return idx

def get_price_volume(symbol):
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=START_DATE)
    df.index = make_tz_naive(df.index)
    return df

def fetch_fng():
    url = "https://api.alternative.me/fng/"
    r = requests.get(url)
    df = pd.DataFrame(r.json()["data"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="s")
    df["date"] = make_tz_naive(df["date"])
    df["value"] = pd.to_numeric(df["value"])
    df = df.set_index("date")
    return df

st.title("🔥 Crypto Macro Heat Dashboard")
st.write("A simple long-term overheating indicator for BTC + ETH.")

if st.button("Refresh Data"):
    st.cache_data.clear()

@st.cache_data
def load_data():

    # Price data
    btc = get_price_volume("BTC-USD")
    eth = get_price_volume("ETH-USD")

    daily = pd.DataFrame()
    daily["btc"] = btc["Close"]
    daily["eth"] = eth["Close"]
    daily["volume"] = btc["Volume"] + eth["Volume"]
    daily.index = make_tz_naive(daily.index)

    # BTC+ETH index (market cap proxy)
    daily["index"] = 0.65 * daily["btc"] + 0.35 * daily["eth"]

    # Weekly
    weekly = pd.DataFrame()
    weekly["index"] = daily["index"].resample("W-FRI").last()
    weekly["volume"] = daily["volume"].resample("W-FRI").sum()
    weekly = weekly.dropna()

    # Volatility
    weekly["returns"] = weekly["index"].pct_change()
    weekly["volatility"] = weekly["returns"].rolling(WEEKLY_VOL_WINDOW).std() * np.sqrt(52)

    # Fear & Greed
    try:
        fng = fetch_fng()
        weekly["fng"] = fng["value"].resample("W-FRI").mean().ffill()
    except:
        weekly["fng"] = 50  # neutral fallback

    # Trend & stretch
    weekly["trend"] = weekly["index"].rolling(WEEKLY_TREND_WINDOW).mean()
    weekly["stretch"] = (weekly["index"] - weekly["trend"]) / weekly["trend"]

    # Overheating condition
    weekly["overheat"] = (
        (weekly["fng"].rolling(MIN_FG_WEEKS).mean() >= FG_OVERHEAT) &
        (weekly["stretch"] >= STRETCH_THRESHOLD) &
        (weekly["volatility"] > weekly["volatility"].expanding().median())
    )

    return weekly

weekly = load_data()

# Current status
latest = weekly.iloc[-1]
stretch_pct = latest["stretch"] * 100
fgi = latest["fng"]
vol = latest["volatility"]

if latest["overheat"]:
    status = "🔥 OVERHEATED"
elif stretch_pct > 20 and fgi > 60:
    status = "⚠️ WARM"
else:
    status = "🟢 COOL"

st.metric("Market Status", status)
col1, col2, col3 = st.columns(3)
col1.metric("Stretch %", f"{stretch_pct:.1f}%")
col2.metric("Fear & Greed", f"{fgi:.0f}")
col3.metric("Volatility", f"{vol:.2f}")

# Chart
fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)

axes[0].plot(weekly.index, weekly["index"], label="Index")
axes[0].plot(weekly.index, weekly["trend"], "--", label="Trend")
axes[0].fill_between(
    weekly.index,
    weekly["index"].min(),
    weekly["index"].max(),
    where=weekly["overheat"],
    alpha=0.2,
    color="red",
)
axes[0].legend()
axes[0].set_ylabel("Price")

axes[1].plot(weekly.index, weekly["stretch"])
axes[1].axhline(STRETCH_THRESHOLD, ls="--")
axes[1].set_ylabel("Stretch")

axes[2].plot(weekly.index, weekly["volatility"])
axes[2].set_ylabel("Volatility")

axes[3].plot(weekly.index, weekly["fng"])
axes[3].axhline(FG_OVERHEAT, ls="--", color="red")
axes[3].set_ylabel("Fear & Greed")
axes[3].set_xlabel("Date")

plt.tight_layout()
st.pyplot(fig)

st.subheader("Recent Overheating Weeks")
st.dataframe(weekly[weekly["overheat"]].tail(10))
