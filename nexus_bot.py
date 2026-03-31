import time
import requests

# ================= SETTINGS =================
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
INTERVAL = "1m"
MAX_TRADES = 2

FEE_PERCENT = 0.001
SLIPPAGE = 0.001
TOTAL_COST = (FEE_PERCENT * 2) + SLIPPAGE

TELEGRAM_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

active_trades = {}

# ================= TELEGRAM =================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# ================= LOGGING =================
def log(msg):
    print(f"[LOG] {msg}")
    send_telegram(f"📊 {msg}")

# ================= DATA =================
def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    return float(requests.get(url).json()["price"])

def get_klines(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={INTERVAL}&limit=20"
    data = requests.get(url).json()
    return [float(x[4]) for x in data]

# ================= SIGNAL =================
def get_signal(closes):
    price = closes[-1]

    volatility = max(closes[-5:]) - min(closes[-5:])
    if volatility < price * 0.001:
        return None, 0

    ema_fast = sum(closes[-5:]) / 5
    ema_slow = sum(closes[-10:]) / 10

    strength = 0

    if ema_fast > ema_slow:
        strength += 1
    if price > ema_fast:
        strength += 1
    if closes[-1] > closes[-3]:
        strength += 1

    if strength >= 2:
        return "BUY", strength

    strength = 0

    if ema_fast < ema_slow:
        strength += 1
    if price < ema_fast:
        strength += 1
    if closes[-1] < closes[-3]:
        strength += 1

    if strength >= 2:
        return "SELL", strength

    return None, 0

# ================= PNL =================
def calculate_real_pnl(entry, exit, side):
    gross = (exit - entry) if side == "BUY" else (entry - exit)
    cost = entry * TOTAL_COST
    return gross - cost

# ================= START =================
send_telegram("🚀 BOT STARTED (BALANCED SMC v2.1 FINAL TEST)")

while True:
    try:
        for symbol in SYMBOLS:

            if len(active_trades) >= MAX_TRADES:
                log("Max trades reached")
                continue

            closes = get_klines(symbol)
            signal, strength = get_signal(closes)

            if signal is None:
                log(f"{symbol} → No signal")
                continue

            price = closes[-1]

            # ENTRY DELAY
            time.sleep(5)
            new_price = get_price(symbol)

            if signal == "BUY" and new_price < price:
                log(f"{symbol} → Entry cancelled (weak BUY)")
                continue
            if signal == "SELL" and new_price > price:
                log(f"{symbol} → Entry cancelled (weak SELL)")
                continue

            range_size = max(closes[-10:]) - min(closes[-10:])

            # ===== SL/TP FIX =====
            if signal == "BUY":
                sl = price - range_size
                tp = price + (range_size * 2)

                if tp <= price:
                    tp = price + (range_size * 2)

                tp -= price * TOTAL_COST

            if signal == "SELL":
                sl = price + range_size
                tp = price - (range_size * 2)

                if tp >= price:
                    tp = price - (range_size * 2)

                tp += price * TOTAL_COST

            # ===== MIN PROFIT FILTER =====
            min_profit = price * 0.004
            if abs(tp - price) < min_profit:
                log(f"{symbol} → Skipped (low profit)")
                continue

            # ===== RR CHECK =====
            risk = abs(price - sl)
            reward = abs(tp - price)

            if reward < (risk * 1.5):
                log(f"{symbol} → Skipped (bad RR)")
                continue

            active_trades[symbol] = {
                "side": signal,
                "entry": price,
                "sl": sl,
                "tp": tp
            }

            log(f"{symbol} → TRADE OPENED ({signal})")

            send_telegram(f"""
🚀 ENTER {symbol}
Type: {signal}
Price: {price:.2f}
SL: {sl:.2f}
TP: {tp:.2f}
R:R: {round(reward/risk,2)}
Strength: {strength}/3
Fees Included ✅
""")

        # ===== EXIT TRACK =====
        for symbol in list(active_trades.keys()):
            trade = active_trades[symbol]
            price = get_price(symbol)

            if trade["side"] == "BUY":
                if price <= trade["sl"]:
                    pnl = calculate_real_pnl(trade["entry"], price, "BUY")
                    log(f"{symbol} → SL HIT | PnL: {pnl:.2f}")
                    del active_trades[symbol]

                elif price >= trade["tp"]:
                    pnl = calculate_real_pnl(trade["entry"], price, "BUY")
                    log(f"{symbol} → TP HIT | PnL: {pnl:.2f}")
                    del active_trades[symbol]

            if trade["side"] == "SELL":
                if price >= trade["sl"]:
                    pnl = calculate_real_pnl(trade["entry"], price, "SELL")
                    log(f"{symbol} → SL HIT | PnL: {pnl:.2f}")
                    del active_trades[symbol]

                elif price <= trade["tp"]:
                    pnl = calculate_real_pnl(trade["entry"], price, "SELL")
                    log(f"{symbol} → TP HIT | PnL: {pnl:.2f}")
                    del active_trades[symbol]

        time.sleep(5)

    except Exception as e:
        log(f"ERROR: {e}")
        time.sleep(10)
