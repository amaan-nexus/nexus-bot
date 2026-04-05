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

# Fees & Spread (adjust if needed)
FEE_PERCENT = 0.0004   # 0.04%
SPREAD_BUFFER = 0.0003 # 0.03%

# ================= GLOBAL =================
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

        # ================= CHECK ACTIVE =================
        for trade in active_trades[:]:
            price = get_price(trade["symbol"])
            move = abs(trade["entry"] - trade["sl_initial"])

            # ===== BE LEVEL 1 (SAFE) =====
            if not trade.get("be1", False):
                if trade["type"] == "BUY" and price >= trade["entry"] + move:
                    trade["sl"] = trade["entry"] * (1 + FEE_PERCENT)
                    trade["be1"] = True
                    send_telegram(f"🟡 BE1 Activated {trade['symbol']}")

                elif trade["type"] == "SELL" and price <= trade["entry"] - move:
                    trade["sl"] = trade["entry"] * (1 - FEE_PERCENT)
                    trade["be1"] = True
                    send_telegram(f"🟡 BE1 Activated {trade['symbol']}")

            # ===== BE LEVEL 2 (LOCK PROFIT) =====
            if not trade.get("be2", False):
                if trade["type"] == "BUY" and price >= trade["entry"] + (move * 1.5):
                    trade["sl"] = trade["entry"] + (move * 0.5)
                    trade["be2"] = True
                    send_telegram(f"🟢 PROFIT LOCK {trade['symbol']}")

                elif trade["type"] == "SELL" and price <= trade["entry"] - (move * 1.5):
                    trade["sl"] = trade["entry"] - (move * 0.5)
                    trade["be2"] = True
                    send_telegram(f"🟢 PROFIT LOCK {trade['symbol']}")

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

                if trade.get("be1", False):
                    pnl = 0
                    breakevens += 1
                    send_telegram(f"⚪ BE EXIT {trade['symbol']} | 0 USDT")
                else:
                    pnl = -trade["risk"]
                    losses += 1
                    send_telegram(f"❌ SL HIT {trade['symbol']} | {pnl} USDT")

                total_pnl += pnl
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

                # Micro SL filter
                if sl_dist < price * 0.001:
                    continue

                tp_dist = sl_dist * RR

                # Spread adjustment
                price_adj = price * (1 + SPREAD_BUFFER if signal == "BUY" else 1 - SPREAD_BUFFER)

                if signal == "BUY":
                    sl = price_adj - sl_dist
                    tp = price_adj + tp_dist
                else:
                    sl = price_adj + sl_dist
                    tp = price_adj - tp_dist

                qty = RISK_PER_TRADE / abs(price_adj - sl)

                trade = {
                    "symbol": symbol,
                    "type": signal,
                    "entry": price_adj,
                    "sl": sl,
                    "sl_initial": sl,
                    "tp": tp,
                    "qty": qty,
                    "risk": RISK_PER_TRADE,
                    "be1": False,
                    "be2": False
                }

                active_trades.append(trade)

                send_telegram(
                    f"🚀 ENTER {symbol}\n"
                    f"Type: {signal}\n"
                    f"Entry: {round(price_adj,4)}\n"
                    f"SL: {round(sl,4)}\n"
                    f"TP: {round(tp,4)}\n"
                    f"Qty: {round(qty,4)}\n"
                    f"Risk: {RISK_PER_TRADE} USDT"
                )

                break

        # ================= REPORT =================
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
                f"PnL: {round(total_pnl,2)} USDT"
            )

            last_report_time = time.time()

        time.sleep(10)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(5)
