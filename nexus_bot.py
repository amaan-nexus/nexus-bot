import time
import requests
from datetime import datetime

# ================= CONFIG =================
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
TIMEFRAME = "1m"
MAX_TRADES = 2

TELEGRAM_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

FEE_PERCENT = 0.04  # 0.04% per side (Binance approx)
MIN_PROFIT_PERCENT = 0.15  # skip low profit trades

active_trades = []
max_log_flag = False

# ================= TELEGRAM =================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# ================= PRICE =================
def get_price(symbol):
    url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
    return float(requests.get(url).json()["price"])

# ================= STRATEGY =================
def generate_signal(symbol, price):
    # SIMPLE DEMO LOGIC (replace later with full SMC)
    import random

    direction = random.choice(["BUY", "SELL"])
    strength = random.choice([2, 3])

    if direction == "BUY":
        sl = price * 0.997
        tp = price * 1.004
    else:
        sl = price * 1.003
        tp = price * 0.996

    return direction, sl, tp, strength

# ================= FEES =================
def calculate_fees(entry, exit):
    fee = (entry + exit) * (FEE_PERCENT / 100)
    return fee

# ================= MAIN LOOP =================
send_telegram("🚀 BOT STARTED (BALANCED SMC v2.2 CLEAN DEMO)")

while True:
    try:
        for symbol in SYMBOLS:

            # ===== MAX TRADE CONTROL =====
            if len(active_trades) >= MAX_TRADES:
                if not max_log_flag:
                    print("[LOG] Max trades reached")
                    max_log_flag = True
                continue
            else:
                max_log_flag = False

            price = get_price(symbol)

            # ===== SIGNAL =====
            direction, sl, tp, strength = generate_signal(symbol, price)

            # ===== PROFIT CHECK =====
            potential_profit = abs(tp - price) / price * 100

            if potential_profit < MIN_PROFIT_PERCENT:
                print(f"[LOG] {symbol} skipped (low profit)")
                continue

            # ===== CREATE TRADE =====
            trade = {
                "symbol": symbol,
                "entry": price,
                "sl": sl,
                "tp": tp,
                "direction": direction
            }

            active_trades.append(trade)

            # ===== TELEGRAM ENTRY =====
            msg = f"""
🚀 ENTER {symbol}
Type: {direction}
Price: {round(price, 2)}
SL: {round(sl, 2)}
TP: {round(tp, 2)}
R:R: 2
Strength: {strength}/3
Fees Included ✅
"""
            send_telegram(msg)

        # ===== MONITOR TRADES =====
        for trade in active_trades[:]:
            current_price = get_price(trade["symbol"])

            hit_tp = False
            hit_sl = False

            if trade["direction"] == "BUY":
                if current_price >= trade["tp"]:
                    hit_tp = True
                elif current_price <= trade["sl"]:
                    hit_sl = True
            else:
                if current_price <= trade["tp"]:
                    hit_tp = True
                elif current_price >= trade["sl"]:
                    hit_sl = True

            if hit_tp or hit_sl:
                fee = calculate_fees(trade["entry"], current_price)

                pnl = abs(current_price - trade["entry"]) - fee
                pnl = round(pnl, 2)

                if hit_tp:
                    send_telegram(f"✅ TP HIT {trade['symbol']} | PnL: {pnl}")
                else:
                    send_telegram(f"❌ SL HIT {trade['symbol']} | PnL: -{pnl}")

                active_trades.remove(trade)

        time.sleep(10)

    except Exception as e:
        print("[ERROR]", e)
        time.sleep(5)
