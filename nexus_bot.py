import requests
import pandas as pd
import time
import sys

# ================= CONFIG =================
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
RISK_PER_TRADE = 3
MAX_TRADES = 2
TIMEFRAME = "5m"

TELEGRAM_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

# ================= LOGGER =================
def log(msg):
    print(msg)
    sys.stdout.flush()

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# ================= GLOBAL STATE =================
last_trade_time = {}
active_symbols = set()

# ================= DATA =================
def get_data(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={TIMEFRAME}&limit=100"
    data = requests.get(url).json()
    df = pd.DataFrame(data)
    df = df[[0,1,2,3,4,5]]
    df.columns = ["time","open","high","low","close","volume"]
    df = df.astype(float)
    return df

def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={symbol}"
    data = requests.get(url).json()
    return float(data["bidPrice"]), float(data["askPrice"])

# ================= STRATEGY =================
def generate_signal(df):
    df["ema"] = df["close"].ewm(span=20).mean()

    last = df.iloc[-1]
    prev = df.iloc[-2]

    if last["close"] > last["ema"] and prev["close"] < prev["ema"]:
        return "BUY"
    elif last["close"] < last["ema"] and prev["close"] > prev["ema"]:
        return "SELL"
    return None

# ================= TRADE BUILDER =================
def build_trade(symbol):
    global last_trade_time

    # ⛔ Cooldown (5 min)
    if symbol in last_trade_time:
        if time.time() - last_trade_time[symbol] < 300:
            return None

    df = get_data(symbol)
    signal = generate_signal(df)

    if not signal:
        return None

    bid, ask = get_price(symbol)
    entry = ask if signal == "BUY" else bid

    # ================= ATR SL =================
    df["tr"] = df["high"] - df["low"]
    atr = df["tr"].rolling(14).mean().iloc[-1]

    if atr == 0 or pd.isna(atr):
        return None

    if signal == "BUY":
        sl = entry - (atr * 1.5)
        tp = entry + (atr * 3)
    else:
        sl = entry + (atr * 1.5)
        tp = entry - (atr * 3)

    risk = abs(entry - sl)

    # ❌ STRONG MIN SL FILTER
    if risk < entry * 0.003:
        return None

    # ❌ SPREAD FILTER
    spread = abs(ask - bid)
    if spread > entry * 0.0005:
        return None

    qty = RISK_PER_TRADE / risk

    # SCORE (ranking)
    score = abs(tp - entry) / risk

    # Save cooldown time
    last_trade_time[symbol] = time.time()

    return {
        "symbol": symbol,
        "type": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "qty": qty,
        "score": score
    }

# ================= MAIN LOOP =================
log("🚀 v6.2 PRO SNIPER BOT STARTED")

while True:
    try:
        trades = []
        active_symbols.clear()

        for symbol in SYMBOLS:
            trade = build_trade(symbol)
            if trade:
                trades.append(trade)

        # 🔥 Rank best trades
        trades = sorted(trades, key=lambda x: x["score"], reverse=True)
        trades = trades[:MAX_TRADES]

        for t in trades:
            # ❌ Prevent duplicate
            if t["symbol"] in active_symbols:
                continue

            active_symbols.add(t["symbol"])

            msg = f"""
🚀 ENTER {t['symbol']}
Type: {t['type']}
Entry: {round(t['entry'],2)}
SL: {round(t['sl'],2)}
TP: {round(t['tp'],2)}
Qty: {round(t['qty'],4)}
Risk: {RISK_PER_TRADE} USDT
"""

            log(msg)
            send_telegram(msg)

        time.sleep(60)

    except Exception as e:
        log(f"ERROR: {e}")
        time.sleep(10)
