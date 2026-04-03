import requests
import pandas as pd
import time
import numpy as np

# ================= SETTINGS =================
BOT_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
TIMEFRAME = "5m"

RISK_PER_TRADE = 3
MAX_TRADES = 2

# ============================================

active_trades = []
trade_history = []
last_report_time = time.time()

# ================= TELEGRAM =================
def send_telegram(msg):
    print(msg)  # IMPORTANT for logs
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# ================= DATA =================
def get_klines(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={TIMEFRAME}&limit=100"
    data = requests.get(url).json()
    df = pd.DataFrame(data)
    df = df.iloc[:, :6]
    df.columns = ["time","open","high","low","close","volume"]
    df = df.astype(float)
    return df

def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    return float(requests.get(url).json()['price'])

# ================= INDICATORS =================
def calculate_atr(df):
    df["H-L"] = df["high"] - df["low"]
    df["H-C"] = abs(df["high"] - df["close"].shift())
    df["L-C"] = abs(df["low"] - df["close"].shift())
    df["TR"] = df[["H-L","H-C","L-C"]].max(axis=1)
    df["ATR"] = df["TR"].rolling(14).mean()
    return df["ATR"].iloc[-1]

# ================= SIGNAL =================
def generate_signal(df):
    df["ema20"] = df["close"].ewm(span=20).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()

    last = df.iloc[-1]

    if last["ema20"] > last["ema50"]:
        return "BUY"
    elif last["ema20"] < last["ema50"]:
        return "SELL"
    return None

# ================= SCORING =================
def score_trade(df):
    momentum = abs(df["close"].iloc[-1] - df["close"].iloc[-5])
    volume = df["volume"].iloc[-1]
    return momentum + volume

# ================= START MESSAGE =================
send_telegram("🚀 v6.3 PRO SNIPER BOT STARTED")

# ================= MAIN =================
while True:
    try:
        candidates = []

        for symbol in PAIRS:
            df = get_klines(symbol)
            signal = generate_signal(df)

            if not signal:
                continue

            atr = calculate_atr(df)
            price = get_price(symbol)

            sl_distance = atr * 1.5
            tp_distance = atr * 3

            # ❌ Skip bad trades (too small SL)
            if (sl_distance / price) < 0.003:
                continue

            score = score_trade(df)

            candidates.append({
                "symbol": symbol,
                "signal": signal,
                "price": price,
                "sl_dist": sl_distance,
                "tp_dist": tp_distance,
                "score": score
            })

        # 🎯 Select best trades only
        candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)[:MAX_TRADES]

        for trade in candidates:
            symbol = trade["symbol"]
            signal = trade["signal"]
            entry = trade["price"]

            if signal == "BUY":
                sl = entry - trade["sl_dist"]
                tp = entry + trade["tp_dist"]
            else:
                sl = entry + trade["sl_dist"]
                tp = entry - trade["tp_dist"]

            qty = RISK_PER_TRADE / abs(entry - sl)

            send_telegram(
                f"🚀 v6.3 ENTER {symbol}\n"
                f"Type: {signal}\n"
                f"Entry: {entry:.2f}\n"
                f"SL: {sl:.2f}\n"
                f"TP: {tp:.2f}\n"
                f"Qty: {qty:.4f}\n"
                f"Risk: {RISK_PER_TRADE} USDT"
            )

        time.sleep(60)

    except Exception as e:
        print("Error:", e)
        time.sleep(10)
