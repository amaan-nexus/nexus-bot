import requests
import time
import random

# =========================
# 🔐 TELEGRAM CONFIG
# =========================
BOT_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

def send_telegram(msg, force=False):
    if not force:
        return  # 🚫 block all spam logs
    
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        print("[ERROR] Telegram failed")


# =========================
# ⚙️ SETTINGS
# =========================
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]

MAX_TRADES = 2

# Fees (Binance approx)
FEE_RATE = 0.0006   # 0.06% per side
SPREAD_BUFFER = 0.0005


# =========================
# 📊 GET PRICE
# =========================
def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    return float(requests.get(url).json()["price"])


# =========================
# 🧠 SIGNAL LOGIC (Balanced)
# =========================
def get_signal(price):
    strength = random.choice([2, 3])
    
    if strength == 3:
        rr = 2.5
    else:
        rr = 2.0
    
    direction = random.choice(["BUY", "SELL"])
    
    return direction, rr, strength


# =========================
# 💰 TRADE CALCULATION
# =========================
def calculate_trade(price, direction, rr):

    sl_percent = 0.002  # 0.2%
    tp_percent = sl_percent * rr

    fee_cost = price * (FEE_RATE * 2 + SPREAD_BUFFER)

    if direction == "BUY":
        sl = price * (1 - sl_percent)
        tp = price * (1 + tp_percent)
    else:
        sl = price * (1 + sl_percent)
        tp = price * (1 - tp_percent)

    # Skip low-profit trades
    if abs(tp - price) <= fee_cost:
        return None

    return round(sl, 2), round(tp, 2)


# =========================
# 🚀 MAIN BOT
# =========================
active_trades = {}

send_telegram("🚀 BOT STARTED (BALANCED SMC v2 FINAL DEMO)", force=True)

while True:
    try:
        # 🔍 SCAN MARKET
        for symbol in SYMBOLS:

            if len(active_trades) >= MAX_TRADES:
                print("[LOG] Max trades reached")
                break

            price = get_price(symbol)

            direction, rr, strength = get_signal(price)

            trade = calculate_trade(price, direction, rr)

            if trade is None:
                print(f"[LOG] {symbol} → Skipped (low profit)")
                continue

            sl, tp = trade

            msg = f"""🚀 ENTER {symbol}
Type: {direction}
Price: {price}
SL: {sl}
TP: {tp}
R:R: {rr}
Strength: {strength}/3
Fees Included ✅"""

            send_telegram(msg, force=True)

            active_trades[symbol] = {
                "entry": price,
                "sl": sl,
                "tp": tp,
                "type": direction
            }

        # 📈 TRACK TRADES
        for symbol in list(active_trades.keys()):
            price = get_price(symbol)
            trade = active_trades[symbol]

            entry = trade["entry"]
            sl = trade["sl"]
            tp = trade["tp"]
            direction = trade["type"]

            pnl = (price - entry) if direction == "BUY" else (entry - price)
            pnl -= entry * (FEE_RATE * 2)

            # TP HIT
            if (direction == "BUY" and price >= tp) or (direction == "SELL" and price <= tp):
                send_telegram(f"✅ TP HIT {symbol} | PnL: {round(pnl,2)}", force=True)
                del active_trades[symbol]

            # SL HIT
            elif (direction == "BUY" and price <= sl) or (direction == "SELL" and price >= sl):
                send_telegram(f"❌ SL HIT {symbol} | PnL: {round(pnl,2)}", force=True)
                del active_trades[symbol]

        time.sleep(10)

    except Exception as e:
        print("[ERROR]", e)
        time.sleep(5)
