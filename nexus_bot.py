import requests
import pandas as pd
import time
import threading

# ================= CONFIG =================
TELEGRAM_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
INTERVAL = "1m"

RISK_PER_TRADE = 3  # USDT
RR = 2

# ================= STATS =================
total_trades = 0
tp_count = 0
sl_count = 0
be_count = 0
pnl = 0

open_trades = {}

# ================= TELEGRAM =================
def send(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# ================= DATA =================
def get_data(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={INTERVAL}&limit=100"
    data = requests.get(url).json()
    df = pd.DataFrame(data)
    df = df.astype(float)
    df.columns = ["time","open","high","low","close","volume",
                  "ct","qv","n","tb","tq","ignore"]
    return df

# ================= STRATEGY =================
def check_trade(symbol):
    df = get_data(symbol)

    df["ema20"] = df["close"].ewm(span=20).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()

    last = df.iloc[-1]

    # TREND FILTER
    if last["ema20"] > last["ema50"]:
        trend = "BUY"
    elif last["ema20"] < last["ema50"]:
        trend = "SELL"
    else:
        return None

    # BASIC ENTRY LOGIC
    price = last["close"]

    sl = price * (0.998 if trend == "BUY" else 1.002)
    tp = price + (price - sl) * RR if trend == "BUY" else price - (sl - price) * RR

    risk = abs(price - sl)
    qty = RISK_PER_TRADE / risk

    return {
        "symbol": symbol,
        "type": trend,
        "entry": price,
        "sl": sl,
        "tp": tp,
        "qty": qty,
        "risk": RISK_PER_TRADE,
        "be": False
    }

# ================= TRADE MANAGEMENT =================
def manage_trades():
    global pnl, tp_count, sl_count, be_count, total_trades

    while True:
        for symbol, trade in list(open_trades.items()):
            df = get_data(symbol)
            price = df.iloc[-1]["close"]

            entry = trade["entry"]
            sl = trade["sl"]
            tp = trade["tp"]

            # BE activation (1:1)
            if not trade["be"]:
                if trade["type"] == "BUY" and price >= entry + (entry - sl):
                    trade["sl"] = entry
                    trade["be"] = True
                    send(f"🔒 BE ACTIVATED {symbol}")

                elif trade["type"] == "SELL" and price <= entry - (sl - entry):
                    trade["sl"] = entry
                    trade["be"] = True
                    send(f"🔒 BE ACTIVATED {symbol}")

            # TP HIT
            if (trade["type"] == "BUY" and price >= tp) or \
               (trade["type"] == "SELL" and price <= tp):

                profit = RISK_PER_TRADE * RR
                pnl += profit
                tp_count += 1
                total_trades += 1

                send(f"✅ TP HIT {symbol} | {profit} USDT")
                del open_trades[symbol]

            # SL HIT
            elif (trade["type"] == "BUY" and price <= trade["sl"]) or \
                 (trade["type"] == "SELL" and price >= trade["sl"]):

                if trade["be"]:
                    be_count += 1
                    send(f"❌ BE {symbol} | 0 USDT")
                else:
                    loss = -RISK_PER_TRADE
                    pnl += loss
                    sl_count += 1
                    send(f"❌ SL {symbol} | {loss} USDT")

                total_trades += 1
                del open_trades[symbol]

        time.sleep(5)

# ================= ENTRY LOOP =================
def run_bot():
    send("🚀 BOT STARTED (v4 SMART MODE)")

    while True:
        for symbol in SYMBOLS:
            if symbol not in open_trades:
                trade = check_trade(symbol)
                if trade:
                    open_trades[symbol] = trade

                    send(
                        f"🚀 ENTER {symbol}\n"
                        f"Type: {trade['type']}\n"
                        f"Entry: {round(trade['entry'],2)}\n"
                        f"SL: {round(trade['sl'],2)}\n"
                        f"TP: {round(trade['tp'],2)}\n"
                        f"Qty: {round(trade['qty'],4)}\n"
                        f"Risk: {trade['risk']} USDT"
                    )

        time.sleep(30)

# ================= REPORT =================
def report():
    while True:
        time.sleep(3600)

        if total_trades == 0:
            continue

        win_rate = (tp_count / total_trades) * 100

        send(
            f"📊 PERFORMANCE REPORT\n\n"
            f"Trades: {total_trades}\n"
            f"TP: {tp_count}\n"
            f"SL: {sl_count}\n"
            f"BE: {be_count}\n\n"
            f"Win Rate: {round(win_rate,2)}%\n"
            f"PnL: {round(pnl,2)} USDT"
        )

# ================= START =================
threading.Thread(target=manage_trades).start()
threading.Thread(target=report).start()

run_bot()
