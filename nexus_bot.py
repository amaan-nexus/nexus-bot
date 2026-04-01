import requests
import time

# ================= CONFIG =================
SYMBOLS = ["BTCUSDT", "ETHUSDT"]

CAPITAL = 30000
RISK_PERCENT = 1
RISK_AMOUNT = CAPITAL * RISK_PERCENT / 100  # ₹300 risk

MAX_TRADES = 2

TELEGRAM_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

active_trades = []

# ================= TELEGRAM =================
def send_telegram(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg}
    )

# ================= DATA =================
def get_klines(symbol):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=1m&limit=50"
    data = requests.get(url).json()
    closes = [float(x[4]) for x in data]
    return closes

def get_price(symbol):
    url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
    return float(requests.get(url).json()["price"])

# ================= INDICATORS =================
def ema(data, period):
    k = 2 / (period + 1)
    ema_val = data[0]
    for price in data:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val

def rsi(data, period=14):
    gains, losses = [], []

    for i in range(1, len(data)):
        diff = data[i] - data[i-1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))

    avg_gain = sum(gains[-period:]) / period if gains else 0
    avg_loss = sum(losses[-period:]) / period if losses else 1

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ================= SIGNAL =================
def generate_signal(symbol):
    closes = get_klines(symbol)
    price = closes[-1]

    ema_fast = ema(closes[-20:], 20)
    ema_slow = ema(closes[-50:], 50)
    rsi_val = rsi(closes)

    # TREND + MOMENTUM
    if ema_fast > ema_slow and rsi_val > 55:
        direction = "BUY"
    elif ema_fast < ema_slow and rsi_val < 45:
        direction = "SELL"
    else:
        return None

    # STRUCTURE SL
    recent_high = max(closes[-10:])
    recent_low = min(closes[-10:])

    if direction == "BUY":
        sl = recent_low
        tp = price + (price - sl) * 2
    else:
        sl = recent_high
        tp = price - (sl - price) * 2

    return direction, price, sl, tp

# ================= POSITION SIZE =================
def calculate_quantity(entry, sl):
    sl_distance = abs(entry - sl)
    if sl_distance == 0:
        return None
    qty = RISK_AMOUNT / sl_distance
    return qty

# ================= START =================
send_telegram("🚀 v3 BOT STARTED (REAL + BE TRAILING)")

while True:
    try:
        # ===== ENTRY =====
        for symbol in SYMBOLS:

            if len(active_trades) >= MAX_TRADES:
                continue

            signal = generate_signal(symbol)

            if signal is None:
                continue

            direction, entry, sl, tp = signal

            qty = calculate_quantity(entry, sl)
            if qty is None:
                continue

            trade = {
                "symbol": symbol,
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "qty": qty,
                "dir": direction,
                "be_done": False
            }

            active_trades.append(trade)

            send_telegram(f"""
🚀 ENTER {symbol}
Type: {direction}
Entry: {round(entry,2)}
SL: {round(sl,2)}
TP: {round(tp,2)}
Qty: {round(qty,4)}
Risk: ₹{RISK_AMOUNT}
""")

        # ===== TRACK =====
        for trade in active_trades[:]:
            price = get_price(trade["symbol"])

            entry = trade["entry"]
            sl = trade["sl"]
            tp = trade["tp"]
            qty = trade["qty"]

            # ===== 1:1 LEVEL =====
            if trade["dir"] == "BUY":
                one_to_one = entry + (entry - sl)
            else:
                one_to_one = entry - (sl - entry)

            # ===== BREAK EVEN =====
            if not trade["be_done"]:
                if (trade["dir"] == "BUY" and price >= one_to_one) or \
                   (trade["dir"] == "SELL" and price <= one_to_one):

                    trade["sl"] = entry
                    trade["be_done"] = True

                    send_telegram(f"🔒 BE ACTIVATED {trade['symbol']}")

            # ===== EXIT =====
            if trade["dir"] == "BUY":

                if price <= trade["sl"]:
                    pnl = (price - entry) * qty
                    send_telegram(f"⚖️ EXIT {trade['symbol']} | ₹{round(pnl,2)}")
                    active_trades.remove(trade)

                elif price >= tp:
                    pnl = (price - entry) * qty
                    send_telegram(f"✅ TP HIT {trade['symbol']} | ₹{round(pnl,2)}")
                    active_trades.remove(trade)

            else:

                if price >= trade["sl"]:
                    pnl = (entry - price) * qty
                    send_telegram(f"⚖️ EXIT {trade['symbol']} | ₹{round(pnl,2)}")
                    active_trades.remove(trade)

                elif price <= tp:
                    pnl = (entry - price) * qty
                    send_telegram(f"✅ TP HIT {trade['symbol']} | ₹{round(pnl,2)}")
                    active_trades.remove(trade)

        time.sleep(10)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(5)
