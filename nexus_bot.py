import requests
import pandas as pd
import time

# ================= SETTINGS =================
BOT_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
TIMEFRAME = "5m"

RISK_PER_TRADE = 3
RR = 2
MAX_TRADES = 2

# ============================================

active_trades = []
trade_history = []
last_report_time = time.time()

# ================= TELEGRAM =================
def send_telegram(msg):
    print(msg)  # 👈 ADD THIS LINE (IMPORTANT)

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

# ================= STRATEGY =================
def generate_signal(df):
    df["ema20"] = df["close"].ewm(span=20).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()

    last = df.iloc[-1]

    if last["ema20"] > last["ema50"]:
        return "BUY"
    elif last["ema20"] < last["ema50"]:
        return "SELL"
    return None

def calculate_levels(df, signal):
    high = df["high"].iloc[-5:].max()
    low = df["low"].iloc[-5:].min()
    entry = df["close"].iloc[-1]

    if signal == "BUY":
        sl = low
        risk = entry - sl
        if risk <= 0: return None
        tp = entry + (risk * RR)

    elif signal == "SELL":
        sl = high
        risk = sl - entry
        if risk <= 0: return None
        tp = entry - (risk * RR)

    return entry, sl, tp

def calculate_qty(entry, sl):
    risk = abs(entry - sl)
    if risk == 0:
        return 0
    qty = RISK_PER_TRADE / risk
    return round(qty, 4)

# ================= RANKING =================
def rank_trade(df):
    move = abs(df["close"].iloc[-1] - df["close"].iloc[-5])
    return move

# ================= ENTRY =================
def scan_market():
    global active_trades

    setups = []

    for symbol in PAIRS:
        df = get_klines(symbol)
        signal = generate_signal(df)

        if not signal:
            continue

        levels = calculate_levels(df, signal)
        if not levels:
            continue

        entry, sl, tp = levels
        score = rank_trade(df)

        setups.append((score, symbol, signal, entry, sl, tp))

    setups = sorted(setups, reverse=True)[:MAX_TRADES]

    for setup in setups:
        _, symbol, signal, entry, sl, tp = setup

        if any(t["symbol"] == symbol and t["status"] == "OPEN" for t in active_trades):
            continue

        qty = calculate_qty(entry, sl)

        trade = {
            "symbol": symbol,
            "type": signal,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "qty": qty,
            "status": "OPEN",
            "be_done": False
        }

        active_trades.append(trade)

        send_telegram(f"""🚀 ENTER {symbol}
Type: {signal}
Entry: {entry}
SL: {sl}
TP: {tp}
Qty: {qty}
Risk: {RISK_PER_TRADE} USDT""")

# ================= MANAGEMENT =================
def manage_trades():
    global active_trades, trade_history

    for trade in active_trades:
        if trade["status"] != "OPEN":
            continue

        price = get_price(trade["symbol"])

        entry = trade["entry"]
        sl = trade["sl"]
        tp = trade["tp"]
        direction = trade["type"]

        risk = abs(entry - sl)
        r = abs(price - entry) / risk if risk > 0 else 0

        # TP HIT
        if (direction == "BUY" and price >= tp) or (direction == "SELL" and price <= tp):
            trade["status"] = "TP"
            trade_history.append(trade)
            send_telegram(f"✅ TP HIT {trade['symbol']} | +6 USDT")
            continue

        # SL HIT
        if (direction == "BUY" and price <= sl) or (direction == "SELL" and price >= sl):
            trade["status"] = "SL"
            trade_history.append(trade)
            send_telegram(f"❌ SL HIT {trade['symbol']} | -3 USDT")
            continue

        # BE at 1R
        if not trade["be_done"] and r >= 1:
            trade["sl"] = entry
            trade["be_done"] = True
            send_telegram(f"🔒 BE ACTIVATED {trade['symbol']}")

# ================= PERFORMANCE =================
def send_performance():
    trades = len(trade_history)
    tp = sum(1 for t in trade_history if t["status"] == "TP")
    sl = sum(1 for t in trade_history if t["status"] == "SL")

    pnl = (tp * 6) - (sl * 3)

    winrate = (tp / trades * 100) if trades > 0 else 0

    msg = f"""📊 PERFORMANCE REPORT

Trades: {trades}
TP: {tp}
SL: {sl}

Win Rate: {round(winrate,2)}%
PnL: {pnl} USDT
"""

    send_telegram(msg)

# ================= MAIN LOOP =================
send_telegram("🚀 v6.2 PRO SNIPER BOT STARTED")

while True:
    try:
        scan_market()
        manage_trades()

        if time.time() - last_report_time > 3600:
            send_performance()

        time.sleep(10)

    except Exception as e:
        send_telegram(f"⚠️ ERROR: {str(e)}")
        time.sleep(5)
