import requests
import pandas as pd
import time

# ===== CONFIG =====
TELEGRAM_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
TIMEFRAME = "5m"

RISK_PER_TRADE = 3
RR = 2
MAX_ACTIVE_TRADES = 2

# ===== STATS =====
total_trades = 0
tp_count = 0
sl_count = 0
be_count = 0
total_pnl = 0

open_trades = []

# ===== TELEGRAM =====
def send(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# ===== DATA =====
def get_data(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={TIMEFRAME}&limit=100"
    data = requests.get(url).json()
    df = pd.DataFrame(data)
    df = df.iloc[:, :6]
    df.columns = ["time","open","high","low","close","volume"]
    df = df.astype(float)
    return df

# ===== INDICATORS =====
def add_indicators(df):
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()
    df["atr"] = (df["high"] - df["low"]).rolling(14).mean()
    return df

# ===== SCORING FUNCTION =====
def calculate_score(df):
    last = df.iloc[-1]

    trend_strength = abs(last["ema50"] - last["ema200"])
    volatility = last["atr"]
    candle_strength = abs(last["close"] - last["open"])

    score = (trend_strength * 0.4) + (volatility * 0.3) + (candle_strength * 0.3)
    return score

# ===== SIGNAL =====
def get_signal(df):
    last = df.iloc[-1]

    if last["ema50"] > last["ema200"]:
        trend = "BUY"
    elif last["ema50"] < last["ema200"]:
        trend = "SELL"
    else:
        return None

    if last["atr"] < df["atr"].mean():
        return None

    if abs(last["close"] - last["open"]) < (last["atr"] * 0.5):
        return None

    return trend

# ===== EXECUTE =====
def execute_trade(symbol, side, df):
    global total_trades

    entry = df.iloc[-1]["close"]
    atr = df.iloc[-1]["atr"]

    if side == "BUY":
        sl = entry - atr
        tp = entry + atr * RR
    else:
        sl = entry + atr
        tp = entry - atr * RR

    qty = RISK_PER_TRADE / abs(entry - sl)

    trade = {
        "symbol": symbol,
        "side": side,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "qty": qty,
        "be": False
    }

    open_trades.append(trade)
    total_trades += 1

    send(f"""🚀 ENTER {symbol}
Type: {side}
Entry: {entry:.2f}
SL: {sl:.2f}
TP: {tp:.2f}
Qty: {qty:.4f}
Risk: {RISK_PER_TRADE} USDT""")

# ===== MONITOR =====
def monitor_trades():
    global tp_count, sl_count, be_count, total_pnl

    for trade in open_trades[:]:
        price = float(requests.get(
            f"https://api.binance.com/api/v3/ticker/price?symbol={trade['symbol']}"
        ).json()["price"])

        entry = trade["entry"]
        sl = trade["sl"]
        risk = abs(entry - sl)

        # BE
        if not trade["be"]:
            if trade["side"] == "BUY" and price >= entry + risk:
                trade["sl"] = entry
                trade["be"] = True
                send(f"🔒 BE {trade['symbol']}")

            elif trade["side"] == "SELL" and price <= entry - risk:
                trade["sl"] = entry
                trade["be"] = True
                send(f"🔒 BE {trade['symbol']}")

        # 1.5R lock
        if trade["be"]:
            if trade["side"] == "BUY" and price >= entry + (risk * 1.5):
                trade["sl"] = entry + (risk * 0.5)

            elif trade["side"] == "SELL" and price <= entry - (risk * 1.5):
                trade["sl"] = entry - (risk * 0.5)

        # TP
        if (trade["side"] == "BUY" and price >= trade["tp"]) or \
           (trade["side"] == "SELL" and price <= trade["tp"]):
            tp_count += 1
            total_pnl += RISK_PER_TRADE * RR
            send(f"✅ TP {trade['symbol']} +{RISK_PER_TRADE * RR} USDT")
            open_trades.remove(trade)

        # SL
        elif (trade["side"] == "BUY" and price <= trade["sl"]) or \
             (trade["side"] == "SELL" and price >= trade["sl"]):

            if trade["be"]:
                be_count += 1
                send(f"⚖️ BE {trade['symbol']} 0 USDT")
            else:
                sl_count += 1
                total_pnl -= RISK_PER_TRADE
                send(f"❌ SL {trade['symbol']} -{RISK_PER_TRADE} USDT")

            open_trades.remove(trade)

# ===== REPORT =====
def report():
    if total_trades == 0:
        return

    win_rate = (tp_count / total_trades) * 100

    send(f"""📊 REPORT

Trades: {total_trades}
TP: {tp_count}
SL: {sl_count}
BE: {be_count}

Win Rate: {win_rate:.2f}%
PnL: {total_pnl:.2f} USDT""")

# ===== MAIN =====
send("🚀 v6 SNIPER BOT STARTED")

last_report = time.time()

while True:
    try:
        candidates = []

        # ===== SCAN ALL PAIRS =====
        for symbol in SYMBOLS:
            if any(t["symbol"] == symbol for t in open_trades):
                continue

            df = get_data(symbol)
            df = add_indicators(df)

            signal = get_signal(df)

            if signal:
                score = calculate_score(df)
                candidates.append((symbol, signal, df, score))

        # ===== SORT BY BEST SCORE =====
        candidates.sort(key=lambda x: x[3], reverse=True)

        # ===== TAKE BEST 2 =====
        for symbol, signal, df, score in candidates[:MAX_ACTIVE_TRADES - len(open_trades)]:
            execute_trade(symbol, signal, df)

        monitor_trades()

        # REPORT
        if time.time() - last_report > 3600:
            report()
            last_report = time.time()

        time.sleep(15)

    except Exception as e:
        send(f"⚠️ ERROR: {e}")
        time.sleep(5)
