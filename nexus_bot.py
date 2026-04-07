import requests
import pandas as pd
import time

# ================= SETTINGS =================
BOT_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
TIMEFRAME = "5m"

BASE_RISK = 3
RR = 2
MAX_TRADES = 2

FEE = 0.0004
SPREAD = 0.0003

MIN_ATR = 0.002
TREND_THRESHOLD = 0.001

# ================= GLOBAL =================
active_trades = []

wins = 0
losses = 0
breakevens = 0
total_pnl = 0

risk_per_trade = BASE_RISK
last_compound_level = 0

last_report_time = time.time()

# ================= TELEGRAM =================
def send_telegram(msg):
    print(msg)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# ================= DATA =================
def get_klines(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={TIMEFRAME}&limit=100"
    data = requests.get(url).json()
    df = pd.DataFrame(data)
    df = df.iloc[:, :6]
    df.columns = ["time", "open", "high", "low", "close", "volume"]
    df = df.astype(float)
    return df

def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    return float(requests.get(url).json()["price"])

# ================= INDICATORS =================
def calculate_atr(df):
    df["H-L"] = df["high"] - df["low"]
    df["H-C"] = abs(df["high"] - df["close"].shift())
    df["L-C"] = abs(df["low"] - df["close"].shift())
    df["TR"] = df[["H-L", "H-C", "L-C"]].max(axis=1)
    df["ATR"] = df["TR"].rolling(14).mean()
    return df["ATR"].iloc[-1]

def generate_signal(df):
    df["ema20"] = df["close"].ewm(span=20).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()

    last = df.iloc[-1]
    ema_gap = abs(last["ema20"] - last["ema50"]) / last["close"]

    if ema_gap < TREND_THRESHOLD:
        return None

    if last["ema20"] > last["ema50"]:
        return "BUY"
    elif last["ema20"] < last["ema50"]:
        return "SELL"
    return None

# ================= START =================
send_telegram("🚀 v6.8 PRO SNIPER BOT STARTED")

# ================= MAIN LOOP =================
while True:
    try:

        # ===== MANAGE TRADES =====
        for trade in active_trades[:]:
            price = get_price(trade["symbol"])
            move = abs(price - trade["entry"])
            profit = move * trade["qty"]

            # ===== BE =====
            if not trade["be_done"] and profit >= trade["risk"]:
                trade["sl"] = trade["entry"]
                trade["be_done"] = True
                send_telegram(f"🔒 BE ACTIVATED {trade['symbol']}")

            # ===== PARTIAL PROFIT (1.5R) =====
            if not trade["partial_done"] and profit >= trade["risk"] * 1.5:
                partial_pnl = trade["risk"] * 0.75  # 50% of 1.5R
                total_pnl += partial_pnl
                trade["qty"] *= 0.5
                trade["partial_done"] = True

                send_telegram(f"💰 PARTIAL BOOKED {trade['symbol']} | +{round(partial_pnl,2)} USDT")

            # ===== TP =====
            if (trade["type"] == "BUY" and price >= trade["tp"]) or \
               (trade["type"] == "SELL" and price <= trade["tp"]):

                pnl = trade["risk"] * RR * 0.5  # remaining 50%
                wins += 1
                total_pnl += pnl

                send_telegram(f"✅ TP HIT {trade['symbol']} | +{round(pnl,2)} USDT")
                active_trades.remove(trade)

            # ===== SL =====
            elif (trade["type"] == "BUY" and price <= trade["sl"]) or \
                 (trade["type"] == "SELL" and price >= trade["sl"]):

                if trade["be_done"]:
                    pnl = 0
                    breakevens += 1
                    send_telegram(f"⚪ BE EXIT {trade['symbol']}")
                else:
                    pnl = -trade["risk"]
                    losses += 1
                    send_telegram(f"❌ SL HIT {trade['symbol']} | {pnl} USDT")

                total_pnl += pnl
                active_trades.remove(trade)

        # ===== COMPOUNDING =====
        global risk_per_trade, last_compound_level

        if total_pnl >= (last_compound_level + 1) * 20:
            risk_per_trade += 1
            last_compound_level += 1
            send_telegram(f"📈 RISK INCREASED → {risk_per_trade} USDT")

        if total_pnl <= (last_compound_level - 1) * 20:
            risk_per_trade = max(BASE_RISK, risk_per_trade - 1)
            last_compound_level -= 1
            send_telegram(f"📉 RISK REDUCED → {risk_per_trade} USDT")

        # ===== NEW TRADES =====
        if len(active_trades) < MAX_TRADES:

            for symbol in PAIRS:

                if any(t["symbol"] == symbol for t in active_trades):
                    continue

                df = get_klines(symbol)
                atr = calculate_atr(df)

                if atr / df["close"].iloc[-1] < MIN_ATR:
                    continue

                signal = generate_signal(df)
                if not signal:
                    continue

                price = get_price(symbol)

                sl_dist = atr * 2
                tp_dist = sl_dist * RR

                spread_cost = price * SPREAD
                fee_cost = price * FEE

                if signal == "BUY":
                    entry = price + spread_cost
                    sl = entry - sl_dist - fee_cost
                    tp = entry + tp_dist
                else:
                    entry = price - spread_cost
                    sl = entry + sl_dist + fee_cost
                    tp = entry - tp_dist

                qty = risk_per_trade / abs(entry - sl)

                trade = {
                    "symbol": symbol,
                    "type": signal,
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "qty": qty,
                    "risk": risk_per_trade,
                    "be_done": False,
                    "partial_done": False
                }

                active_trades.append(trade)

                send_telegram(
                    f"🚀 ENTER {symbol}\n"
                    f"Type: {signal}\n"
                    f"Entry: {round(entry,4)}\n"
                    f"SL: {round(sl,4)}\n"
                    f"TP: {round(tp,4)}\n"
                    f"Qty: {round(qty,4)}\n"
                    f"Risk: {risk_per_trade} USDT"
                )

                break

        # ===== REPORT =====
        if time.time() - last_report_time >= 3600:
            total_trades = wins + losses + breakevens
            winrate = (wins / total_trades * 100) if total_trades > 0 else 0

            send_telegram(
                f"📊 PERFORMANCE REPORT\n\n"
                f"Trades: {total_trades}\n"
                f"Wins: {wins}\n"
                f"Losses: {losses}\n"
                f"BE: {breakevens}\n\n"
                f"Win Rate: {round(winrate,2)}%\n"
                f"PnL: {round(total_pnl,2)} USDT\n"
                f"Current Risk: {risk_per_trade} USDT"
            )

            last_report_time = time.time()

        time.sleep(10)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(5)
