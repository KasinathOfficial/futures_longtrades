# swing_trade_bot.py
import streamlit as st
import pandas as pd
import numpy as np
import ta
import requests
import time
from datetime import datetime

# Telegram Configuration
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

# Function to send Telegram alert
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, data=payload)
        return response.status_code == 200
    except Exception as e:
        print("Telegram error:", e)
        return False

# Get futures symbols from CoinDCX API
def get_futures_symbols():
    try:
        url = "https://api.coindcx.com/exchange/v1/markets_details"
        res = requests.get(url)
        markets = res.json()
        futures = [m['symbol'] for m in markets if m['market_type'] == 'futures']
        return futures
    except:
        return []

# Fetch 1H OHLCV data for a symbol
def fetch_candle_data(symbol):
    try:
        url = f"https://public.coindcx.com/market_data/candles?pair={symbol}&interval=1h&limit=100"
        res = requests.get(url)
        data = res.json()
        df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
        df.set_index("timestamp", inplace=True)
        df = df.astype(float)
        return df
    except:
        return pd.DataFrame()

# Analyze a single symbol for trade setup
def analyze_symbol(symbol):
    df = fetch_candle_data(symbol)
    if df.empty or len(df) < 50:
        return None

    df['EMA21'] = ta.trend.ema_indicator(df['close'], window=21)
    df['EMA50'] = ta.trend.ema_indicator(df['close'], window=50)
    df['RSI'] = ta.momentum.rsi(df['close'], window=14)
    df['MACD'] = ta.trend.macd_diff(df['close'])
    df['Volume Spike'] = df['volume'] > df['volume'].rolling(window=20).mean() * 1.5

    latest = df.iloc[-1]
    bullish = latest['EMA21'] > latest['EMA50'] and latest['RSI'] < 40 and latest['MACD'] > 0 and latest['Volume Spike']
    bearish = latest['EMA21'] < latest['EMA50'] and latest['RSI'] > 60 and latest['MACD'] < 0 and latest['Volume Spike']

    entry = round(latest['close'], 4)

    if bullish:
        sl = round(df['low'].iloc[-5:-1].min(), 4)
        targets = [round(entry + (entry - sl) * i, 4) for i in range(1, 6)]
        msg = f"\n*LONG Signal on {symbol}*\nEntry: {entry}\nSL: {sl}\nTargets: {targets}"
        return msg

    elif bearish:
        sl = round(df['high'].iloc[-5:-1].max(), 4)
        targets = [round(entry - (sl - entry) * i, 4) for i in range(1, 6)]
        msg = f"\n*SHORT Signal on {symbol}*\nEntry: {entry}\nSL: {sl}\nTargets: {targets}"
        return msg

    return None

# Streamlit Web UI
st.set_page_config(page_title="CoinDCX Futures Bot", layout="centered")
st.title("🤖 24/7 CoinDCX Futures Analyzer + Telegram Bot")

if st.button("🔍 Scan All Futures and Alert on Telegram"):
    with st.spinner("Scanning all CoinDCX futures..."):
        futures = get_futures_symbols()
        signals_sent = 0

        for symbol in futures:
            signal = analyze_symbol(symbol)
            if signal:
                sent = send_telegram_alert(signal)
                if sent:
                    signals_sent += 1
                    st.success(f"✅ Signal sent for {symbol}")

        if signals_sent == 0:
            st.warning("No valid setups found.")
        else:
            st.info(f"✅ {signals_sent} signals sent to Telegram.")
