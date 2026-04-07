import requests
import pandas as pd
import time
from binance.client import Client

# ================= API =================
API_KEY = "EFZG4pDUD86WX1nyYWoodp0EOOFOmwMGYNYOe1yHdo9QKuqtyRKWrbJJlODZleSx"
API_SECRET = "dvKR4s9nMkfxwL6kFs71jMucwYv2jKZUi2izFSikflQkMx8OizOgkzafGJOISF6q"

client = Client(API_KEY, API_SECRET)

# ================= SETTINGS =================
BOT_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
TIMEFRAME = "5m"

RISK_PER_TRADE = 1
RR = 2
LEVERAGE = 5

MAX_TRADES = 3

# ================= TELEGRAM =================
def send_telegram(msg):
    print(msg)
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                  data={"chat_id": CHAT_ID, "text": msg})

# ================= DATA =================
def get_klines(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={TIMEFRAME}&limit=100"
    df = pd.DataFrame(requests.get(url).json())
    df = df.iloc[:, :6]
    df.columns = ["time", "open", "high", "low", "close", "volume"]
    return df.astype(float)

def get_price(symbol):
    return float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}").json()["price"])

# ================= INDICATORS =================
def calculate_atr(df):
    df["H-L"] = df["high"] - df["low"]
    df["H-C"] = abs(df["high"] - df["close"].shift())
    df["L-C"] = abs(df["low"] - df["close"].shift())
    df["TR"] = df[["H-L", "H-C", "L-C"]].max(axis=1)
    return df["TR"].rolling(14).mean().iloc[-1]

def generate_signal(df):
    df["ema20"] = df["close"].ewm(span=20).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()

    if df["ema20"].iloc[-1] > df["ema50"].iloc[-1]:
        return "BUY"
    elif df["ema20"].iloc[-1] < df["ema50"].iloc[-1]:
        return "SELL"
    return None

# ================= ORDER =================
def place_trade(symbol, side, entry, sl, tp, qty):
    try:
        client.futures_change_leverage(symbol=symbol, leverage=LEVERAGE)

        # ENTRY
        order = client.futures_create_order(
            symbol=symbol,
            side="BUY" if side == "BUY" else "SELL",
            type="MARKET",
            quantity=round(qty, 3)
        )

        # SL
        client.futures_create_order(
            symbol=symbol,
            side="SELL" if side == "BUY" else "BUY",
            type="STOP_MARKET",
            stopPrice=round(sl, 4),
            closePosition=True
        )

        # TP
        client.futures_create_order(
            symbol=symbol,
            side="SELL" if side == "BUY" else "BUY",
            type="TAKE_PROFIT_MARKET",
            stopPrice=round(tp, 4),
            closePosition=True
        )

        send_telegram(f"✅ LIVE TRADE {symbol}\nEntry: {entry}\nSL: {sl}\nTP: {tp}")

    except Exception as e:
        send_telegram(f"❌ Order Error: {e}")

# ================= START =================
send_telegram("🚀 v6.9 SAFE AUTO BOT STARTED")

# ================= LOOP =================
while True:
    try:

        for symbol in PAIRS:

            df = get_klines(symbol)
            signal = generate_signal(df)

            if not signal:
                continue

            atr = calculate_atr(df)
            price = get_price(symbol)

            sl_dist = atr * 2
            tp_dist = sl_dist * RR

            if signal == "BUY":
                sl = price - sl_dist
                tp = price + tp_dist
            else:
                sl = price + sl_dist
                tp = price - tp_dist

            qty = RISK_PER_TRADE / abs(price - sl)

            place_trade(symbol, signal, price, sl, tp, qty)

            time.sleep(5)

        time.sleep(10)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(5)
