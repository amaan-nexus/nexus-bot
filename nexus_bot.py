import requests
import pandas as pd
import time
from telegram import Bot

# ================= CONFIG =================
TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
INTERVAL = "5m"

CAPITAL = 300
RISK_PER_TRADE = 0.01  # 1% = 3 USDT

bot = Bot(token=TOKEN)

# ===== TRACKING =====
total_trades = 0
tp_count = 0
sl_count = 0
be_count = 0
total_pnl = 0

open_trades = {}

# ==========================================

def send(msg):
    print(msg)
    bot.send_message(chat_id=CHAT_ID, text=msg)

# ==========================================

def get_data(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={INTERVAL}&limit=100"
    data = requests.get(url).json()

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","vol",
        "_","_","_","_","_","_"
    ])

    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)

    return df

# ==========================================

def add_indicators(df):
    df["ema"] = df["close"].ewm(span=50).mean()

    df["tr"] = df["high"] - df["low"]
    df["atr"] = df["tr"].rolling(14).mean()

    return df

# ==========================================

def check_entry(symbol):
    df = get_data(symbol)
    df = add_indicators(df)

    price = df["close"].iloc[-1]
    ema = df["ema"].iloc[-1]
    atr = df["atr"].iloc[-1]

    # === VOLATILITY FILTER ===
    if atr < price * 0.001:
        return None

    # === TREND FILTER ===
    if price > ema:
        return "BUY"
    elif price < ema:
        return "SELL"

    return None

# ==========================================

def calculate_trade(symbol, side):
    df = get_data(symbol)
    price = df["close"].iloc[-1]

    if side == "BUY":
        sl = price * 0.997
        tp = price * 1.006
    else:
        sl = price * 1.003
        tp = price * 0.994

    risk_amount = CAPITAL * RISK_PER_TRADE
    qty = risk_amount / abs(price - sl)

    return round(price,2), round(sl,2), round(tp,2), round(qty,4), round(risk_amount,2)

# ==========================================

def open_trade(symbol, side):
    global total_trades

    entry, sl, tp, qty, risk = calculate_trade(symbol, side)

    open_trades[symbol] = {
        "side": side,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "qty": qty,
        "be": False
    }

    total_trades += 1

    send(f"""🚀 ENTER {symbol}
Type: {side}
Entry: {entry}
SL: {sl}
TP: {tp}
Qty: {qty}
Risk: {risk} USDT""")

# ==========================================

def manage_trades():
    global tp_count, sl_count, be_count, total_pnl

    for symbol in list(open_trades.keys()):
        trade = open_trades[symbol]
        df = get_data(symbol)
        price = df["close"].iloc[-1]

        entry = trade["entry"]
        sl = trade["sl"]
        tp = trade["tp"]
        side = trade["side"]

        # === BE LOGIC ===
        if not trade["be"]:
            if (side == "BUY" and price >= entry + (tp-entry)/2) or \
               (side == "SELL" and price <= entry - (entry-tp)/2):

                trade["sl"] = entry
                trade["be"] = True
                send(f"🔒 BE ACTIVATED {symbol}")

        # === EXIT CONDITIONS ===
        if side == "BUY":
            if price <= trade["sl"]:
                pnl = 0 if trade["be"] else -3
                be_count += 1 if trade["be"] else 0
                sl_count += 0 if trade["be"] else 1
                total_pnl += pnl
                send(f"❌ EXIT {symbol} | {pnl} USDT")
                del open_trades[symbol]

            elif price >= tp:
                pnl = 6
                tp_count += 1
                total_pnl += pnl
                send(f"✅ TP HIT {symbol} | {pnl} USDT")
                del open_trades[symbol]

        else:
            if price >= trade["sl"]:
                pnl = 0 if trade["be"] else -3
                be_count += 1 if trade["be"] else 0
                sl_count += 0 if trade["be"] else 1
                total_pnl += pnl
                send(f"❌ EXIT {symbol} | {pnl} USDT")
                del open_trades[symbol]

            elif price <= tp:
                pnl = 6
                tp_count += 1
                total_pnl += pnl
                send(f"✅ TP HIT {symbol} | {pnl} USDT")
                del open_trades[symbol]

# ==========================================

def report():
    win_rate = (tp_count / total_trades * 100) if total_trades > 0 else 0

    send(f"""📊 PERFORMANCE REPORT

Trades: {total_trades}
TP: {tp_count}
SL: {sl_count}
BE: {be_count}

Win Rate: {round(win_rate,2)}%
PnL: {round(total_pnl,2)} USDT
""")

# ==========================================

send("🚀 v4 BOT STARTED (SMART FILTER)")

last_report = time.time()

while True:
    try:
        for sym in SYMBOLS:
            if sym not in open_trades:
                signal = check_entry(sym)
                if signal:
                    open_trade(sym, signal)

        manage_trades()

        if time.time() - last_report > 3600:
            report()
            last_report = time.time()

        time.sleep(10)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
