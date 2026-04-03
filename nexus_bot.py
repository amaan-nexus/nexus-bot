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

# ================= STATE =================
active_trades = []
last_report_time = time.time()

wins = 0
losses = 0
breakevens = 0
total_pnl = 0

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
    df.columns = ["time","open","high","low","close","volume"]
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
    df["TR"] = df[["H-L","H-C","L-C"]].max(axis=1)
    df["ATR"] = df["TR"].rolling(14).mean()
    return df["ATR"].iloc[-1]

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

def score_trade(df):
    momentum = abs(df["close"].iloc[-1] - df["close"].iloc[-5])
    volume = df["volume"].iloc[-1]
    return momentum * volume

# ================= START =================
send_telegram("🚀 v6.4 PRO SNIPER BOT STARTED")

# ================= MAIN LOOP =================
while True:
    try:

        # ===== MANAGE ACTIVE TRADES =====
        for trade in active_trades[:]:
            symbol = trade["symbol"]
            price = get_price(symbol)


            # TP HIT
            if (trade["type"] == "BUY" and price >= trade["tp"]) or \
               (trade["type"] == "SELL" and price <= trade["tp"]):

                pnl = trade["risk"] * RR
                total_pnl += pnl
                wins += 1

                send_telegram(f"✅ TP HIT {symbol} | +{pnl} USDT")
                active_trades.remove(trade)

            # SL HIT
            elif (trade["type"] == "BUY" and price <= trade["sl"]) or \
                 (trade["type"] == "SELL" and price >= trade["sl"]):

                if trade.get("be", False):
                    breakevens += 1
                    send_telegram(f"🔒 BE {symbol} | 0 USDT")
                else:
                    pnl = -trade["risk"]
                    total_pnl += pnl
                    losses += 1
                    send_telegram(f"❌ SL HIT {symbol} | {pnl} USDT")

                active_trades.remove(trade)

            # BE ACTIVATION
            elif not trade.get("be", False):
                risk_move = abs(trade["entry"] - trade["sl"])

                if (trade["type"] == "BUY" and price >= trade["entry"] + risk_move) or \
                   (trade["type"] == "SELL" and price <= trade["entry"] - risk_move):

                    trade["sl"] = trade["entry"]
                    trade["be"] = True
                    send_telegram(f"🔒 BE ACTIVATED {symbol}")

        # ===== FIND NEW TRADES =====
        candidates = []

        for symbol in PAIRS:

            if any(t["symbol"] == symbol for t in active_trades):
                continue

            df = get_klines(symbol)
            signal = generate_signal(df)

            if not signal:
                continue

            atr = calculate_atr(df)
            price = get_price(symbol)

            sl_distance = atr * 2.2
            tp_distance = atr * 3

            # ❌ Skip bad trades
            if (sl_distance / price) < 0.003:
                continue

            score = score_trade(df)

            candidates.append({
                "symbol": symbol,
                "signal": signal,
                "price": price,
                "sl_dist": sl_distance,
                "tp_dist": tp_distance,
                "score": score
            })

        # ===== SELECT BEST =====
        candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)

        for trade in candidates[:MAX_TRADES]:
            symbol = trade["symbol"]
            signal = trade["signal"]
            entry = trade["price"]

            if signal == "BUY":
                sl = entry - trade["sl_dist"]
                tp = entry + trade["tp_dist"]
            else:
                sl = entry + trade["sl_dist"]
                tp = entry - trade["tp_dist"]

            # ❌ XRP FIX (zero SL bug)
            if abs(entry - sl) < 0.001:
                continue

            qty = RISK_PER_TRADE / abs(entry - sl)

            new_trade = {
                "symbol": symbol,
                "type": signal,
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "qty": qty,
                "risk": RISK_PER_TRADE,
                "be": False
            }

            active_trades.append(new_trade)

            send_telegram(
                f"🚀 ENTER {symbol}\n"
                f"Type: {signal}\n"
                f"Entry: {round(entry,2)}\n"
                f"SL: {round(sl,2)}\n"
                f"TP: {round(tp,2)}\n"
                f"Qty: {round(qty,4)}\n"
                f"Risk: {RISK_PER_TRADE} USDT"
            )

        # ===== PERFORMANCE REPORT (1 HR) =====
        if time.time() - last_report_time > 3600:
            total_trades = wins + losses + breakevens
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

            send_telegram(
                f"📊 PERFORMANCE REPORT\n\n"
                f"Trades: {total_trades}\n"
                f"Wins: {wins}\n"
                f"Losses: {losses}\n"
                f"BE: {breakevens}\n\n"
                f"Win Rate: {round(win_rate,2)}%\n"
                f"PnL: {round(total_pnl,2)} USDT"
            )

            last_report_time = time.time()

        time.sleep(30)

    except Exception as e:
        print("Error:", e)
        time.sleep(10)
