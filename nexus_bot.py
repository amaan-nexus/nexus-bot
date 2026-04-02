import requests
import time
from datetime import datetime

# ================= SETTINGS =================
SYMBOLS = ["BTCUSDT", "ETHUSDT"]
TIMEFRAME = "1m"

CAPITAL = 300
RISK_PER_TRADE = 0.01  # 1% = 3 USDT
FEE = 0.0004  # 0.04%

TELEGRAM_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

REPORT_INTERVAL = 3600  # 1 hour

# ================= GLOBAL TRACKER =================
trade_data = {
    "total": 0,
    "tp": 0,
    "sl": 0,
    "be": 0,
    "pnl": 0.0
}

open_trades = {}
last_report_time = time.time()

# ================= TELEGRAM =================
def send(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except:
        print("Telegram error")

# ================= MARKET DATA =================
def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    return float(requests.get(url).json()["price"])

# ================= POSITION SIZE =================
def calculate_qty(entry, sl):
    risk_amount = CAPITAL * RISK_PER_TRADE
    sl_distance = abs(entry - sl)

    qty = risk_amount / sl_distance
    return round(qty, 4), risk_amount

# ================= TRADE TRACKING =================
def update_trade(result, pnl):
    trade_data["total"] += 1
    trade_data["pnl"] += pnl

    if result == "TP":
        trade_data["tp"] += 1
    elif result == "SL":
        trade_data["sl"] += 1
    elif result == "BE":
        trade_data["be"] += 1

    print(f"[TRADE CLOSED] {result} | PnL: {pnl:.2f} | Total: {trade_data['total']}")

# ================= HOURLY REPORT =================
def send_report():
    global last_report_time

    if time.time() - last_report_time >= REPORT_INTERVAL:
        total = trade_data["total"]
        tp = trade_data["tp"]
        sl = trade_data["sl"]
        be = trade_data["be"]
        pnl = round(trade_data["pnl"], 2)

        winrate = (tp / total * 100) if total > 0 else 0

        msg = f"""📊 PERFORMANCE REPORT

Trades: {total}
TP: {tp}
SL: {sl}
BE: {be}

Win Rate: {winrate:.2f}%
PnL: {pnl} USDT
"""

        print("[REPORT SENT]")
        print(msg)

        send(msg)
        last_report_time = time.time()

# ================= STRATEGY =================
def generate_signal(symbol):
    price = get_price(symbol)

    # Simple momentum logic (replace later with SMC)
    if int(price) % 2 == 0:
        return "BUY"
    else:
        return "SELL"

# ================= EXECUTE TRADE =================
def open_trade(symbol):
    if symbol in open_trades:
        return

    signal = generate_signal(symbol)
    entry = get_price(symbol)

    if signal == "BUY":
        sl = entry * 0.998
        tp = entry * 1.004
    else:
        sl = entry * 1.002
        tp = entry * 0.996

    qty, risk = calculate_qty(entry, sl)

    open_trades[symbol] = {
        "type": signal,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "qty": qty,
        "be": False
    }

    msg = f"""🚀 ENTER {symbol}
Type: {signal}
Entry: {entry}
SL: {sl}
TP: {tp}
Qty: {qty}
Risk: {round(risk,2)} USDT"""

    print(msg)
    send(msg)

# ================= MANAGE TRADE =================
def manage_trades():
    for symbol in list(open_trades.keys()):
        trade = open_trades[symbol]
        price = get_price(symbol)

        entry = trade["entry"]
        sl = trade["sl"]
        tp = trade["tp"]
        qty = trade["qty"]

        # BE logic (1:1)
        if not trade["be"]:
            if trade["type"] == "BUY" and price >= entry + (entry - sl):
                trade["sl"] = entry
                trade["be"] = True
                send(f"🔒 BE ACTIVATED {symbol}")
                print(f"{symbol} BE activated")

            elif trade["type"] == "SELL" and price <= entry - (sl - entry):
                trade["sl"] = entry
                trade["be"] = True
                send(f"🔒 BE ACTIVATED {symbol}")
                print(f"{symbol} BE activated")

        # TP HIT
        if (trade["type"] == "BUY" and price >= tp) or (trade["type"] == "SELL" and price <= tp):
            profit = abs(tp - entry) * qty
            profit -= (entry * qty * FEE * 2)

            send(f"✅ TP HIT {symbol} | {round(profit,2)} USDT")
            update_trade("TP", profit)

            del open_trades[symbol]

        # SL HIT
        elif (trade["type"] == "BUY" and price <= trade["sl"]) or (trade["type"] == "SELL" and price >= trade["sl"]):
            loss = abs(entry - trade["sl"]) * qty
            loss += (entry * qty * FEE * 2)

            result = "BE" if trade["be"] else "SL"
            pnl = 0 if trade["be"] else -loss

            send(f"❌ {result} {symbol} | {round(pnl,2)} USDT")
            update_trade(result, pnl)

            del open_trades[symbol]

# ================= MAIN LOOP =================
print("🚀 BOT STARTED (v3.3 FINAL USDT MODE)")

while True:
    try:
        for symbol in SYMBOLS:
            open_trade(symbol)

        manage_trades()
        send_report()

        time.sleep(20)

    except Exception as e:
        print(f"[ERROR] {e}")
        time.sleep(5)
