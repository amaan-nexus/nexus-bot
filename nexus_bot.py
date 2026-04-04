import requests
import pandas as pd
import time

# ================= SETTINGS =================
BOT_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
TIMEFRAME = "5m"

RISK_PER_TRADE = 3
RR = 2
MAX_TRADES = 2

SPREAD = 0.0005
FEE = 0.0004

# ================= GLOBAL STATS =================
active_trades = []

wins = 0
losses = 0
breakevens = 0
total_pnl = 0

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

# ================= SIGNAL =================
def generate_signal(df):
    df["ema20"] = df["close"].ewm(span=20).mean()
    df["ema50"] = df["close"].ewm(span=50).mean()

    last = df.iloc[-1]

    if last["ema20"] > last["ema50"]:
        return "BUY"
    elif last["ema20"] < last["ema50"]:
        return "SELL"
    return None

# ================= START =================
send_telegram("🚀 v6.6 PRO SNIPER BOT STARTED")

# ================= MAIN LOOP =================
while True:
    try:

        # ================= CHECK ACTIVE TRADES =================
        for trade in active_trades[:]:
            price = get_price(trade["symbol"])

            move = abs(price - trade["entry"])
            risk_val = abs(trade["entry"] - trade["sl_initial"])

            # ===== BREAKEVEN =====
            if not trade["be"] and move >= risk_val:
                trade["sl"] = trade["entry"]
                trade["be"] = True
                breakevens += 1
                send_telegram(f"🔒 BE Activated {trade['symbol']}")

            elif trade["be"] and not trade["locked"] and move >= risk_val * 1.5:
                if trade["type"] == "BUY":
                    trade["sl"] = trade["entry"] + (risk_val * 0.5)
                else:
                    trade["sl"] = trade["entry"] - (risk_val * 0.5)

                trade["locked"] = True
                send_telegram(f"💰 Profit Locked {trade['symbol']}")

            # ===== TP HIT =====
            if (trade["type"] == "BUY" and price >= trade["tp"]) or \
               (trade["type"] == "SELL" and price <= trade["tp"]):

                pnl = trade["risk"] * RR
                wins += 1
                total_pnl += pnl

                send_telegram(f"✅ TP HIT {trade['symbol']} | +{pnl} USDT")
                active_trades.remove(trade)

            # ===== SL HIT =====
            elif (trade["type"] == "BUY" and price <= trade["sl"]) or \
                 (trade["type"] == "SELL" and price >= trade["sl"]):

                pnl = -trade["risk"]
                losses += 1
                total_pnl += pnl

                send_telegram(f"❌ SL HIT {trade['symbol']} | {pnl} USDT")
                active_trades.remove(trade)

        # ================= NEW TRADES =================
        if len(active_trades) < MAX_TRADES:

            for symbol in PAIRS:

                if any(t["symbol"] == symbol for t in active_trades):
                    continue

                df = get_klines(symbol)
                signal = generate_signal(df)

                if not signal:
                    continue

                atr = calculate_atr(df)
                price = get_price(symbol)

                sl_dist = atr * 2

                # ❌ MICRO SL FILTER
                if sl_dist / price < 0.002:
                    continue

                tp_dist = sl_dist * RR

                # ❌ TP QUALITY FILTER
                if tp_dist / price < 0.004:
                    continue

                # ===== SPREAD ADJUSTMENT =====
                if signal == "BUY":
                    entry = price * (1 + SPREAD + FEE)
                    sl = entry - sl_dist
                    tp = entry + tp_dist
                else:
                    entry = price * (1 - SPREAD - FEE)
                    sl = entry + sl_dist
                    tp = entry - tp_dist

                qty = RISK_PER_TRADE / abs(entry - sl)

                trade = {
                    "symbol": symbol,
                    "type": signal,
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "qty": qty,
                    "risk": RISK_PER_TRADE,
                    "sl_initial": sl,
                    "be": False,
                    "locked": False
                }

                active_trades.append(trade)

                send_telegram(
                    f"🚀 ENTER {symbol}\n"
                    f"Type: {signal}\n"
                    f"Entry: {round(entry,4)}\n"
                    f"SL: {round(sl,4)}\n"
                    f"TP: {round(tp,4)}\n"
                    f"Qty: {round(qty,4)}\n"
                    f"Risk: {RISK_PER_TRADE} USDT"
                )

                break

        # ================= PERFORMANCE REPORT =================
        if time.time() - last_report_time >= 3600:
            total_trades = wins + losses
            winrate = (wins / total_trades * 100) if total_trades > 0 else 0

            send_telegram(
                f"📊 PERFORMANCE REPORT\n\n"
                f"Trades: {total_trades}\n"
                f"Wins: {wins}\n"
                f"Losses: {losses}\n"
                f"BE: {breakevens}\n\n"
                f"Win Rate: {round(winrate,2)}%\n"
                f"PnL: {round(total_pnl,2)} USDT"
            )

            last_report_time = time.time()

        time.sleep(10)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(5)
