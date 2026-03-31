import time
import requests
from datetime import datetime

# ================= CONFIG =================
CONFIG = {
    "SYMBOLS": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"],
    "INTERVAL": "1m",
    "COOLDOWN": 120,   # seconds
}

TELEGRAM_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

# ================= TELEGRAM =================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# ================= MARKET DATA =================
def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    return float(requests.get(url).json()["price"])

def get_klines(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=5"
    data = requests.get(url).json()
    highs = [float(x[2]) for x in data]
    lows = [float(x[3]) for x in data]
    closes = [float(x[4]) for x in data]
    return highs, lows, closes

# ================= STRATEGY =================
def analyze(symbol):
    highs, lows, closes = get_klines(symbol)

    last = closes[-1]
    prev = closes[-2]

    # Simple trend logic
    if last > prev:
        signal = "BUY"
    elif last < prev:
        signal = "SELL"
    else:
        return None

    sl = lows[-1] if signal == "BUY" else highs[-1]

    return {
        "signal": signal,
        "sl": sl
    }

def get_trend(symbol):
    highs, lows, closes = get_klines(symbol)
    return "BUY" if closes[-1] > closes[-3] else "SELL"

def check_momentum(symbol):
    highs, lows, closes = get_klines(symbol)
    return abs(closes[-1] - closes[-2]) > 0.001 * closes[-1]

# ================= ADAPTIVE RR =================
def calculate_rr(strength):
    if strength >= 3:
        return 3.0
    elif strength == 2:
        return 2.0
    else:
        return None

def get_strength(res, trend, momentum):
    score = 0

    if res["signal"] in ["BUY", "SELL"]:
        score += 1
    if trend == res["signal"]:
        score += 1
    if momentum:
        score += 1

    return score

# ================= BOT =================
class Bot:
    def __init__(self):
        self.trades = {}
        self.last_trade_time = {}

    def run(self):
        send_telegram("⚖️ PERFECT BALANCE MODE ACTIVE (DEMO)")

        while True:
            for symbol in CONFIG["SYMBOLS"]:
                try:
                    price = get_price(symbol)
                    res = analyze(symbol)

                    if not res:
                        continue

                    now = datetime.now()

                    # cooldown
                    if symbol in self.last_trade_time:
                        diff = (now - self.last_trade_time[symbol]).seconds
                        if diff < CONFIG["COOLDOWN"]:
                            continue

                    # already active trade
                    if symbol in self.trades:
                        self.check_exit(symbol, price)
                        continue

                    trend = get_trend(symbol)
                    momentum = check_momentum(symbol)

                    strength = get_strength(res, trend, momentum)
                    rr = calculate_rr(strength)

                    if rr is None:
                        continue

                    sl = res["sl"]

                    # TP calculation
                    if res["signal"] == "BUY":
                        tp = price * (1 + 0.01 * rr)
                    else:
                        tp = price * (1 - 0.01 * rr)

                    self.trades[symbol] = {
                        "entry": price,
                        "sl": sl,
                        "tp": tp,
                        "dir": res["signal"],
                        "rr": rr
                    }

                    self.last_trade_time[symbol] = now

                    send_telegram(
                        f"🚀 ENTER {symbol}\n"
                        f"{res['signal']} @ {price}\n"
                        f"SL: {sl}\n"
                        f"TP: {tp}\n"
                        f"R:R: {rr}\n"
                        f"Strength: {strength}/3"
                    )

                except Exception as e:
                    print("Error:", e)

            time.sleep(5)

    def check_exit(self, symbol, price):
        trade = self.trades[symbol]

        highs, lows, closes = get_klines(symbol)
        high = highs[-1]
        low = lows[-1]

        if trade["dir"] == "BUY":
            if low <= trade["sl"]:
                send_telegram(f"❌ SL HIT {symbol}")
                del self.trades[symbol]

            elif high >= trade["tp"]:
                send_telegram(f"✅ TP HIT {symbol}")
                del self.trades[symbol]

        elif trade["dir"] == "SELL":
            if high >= trade["sl"]:
                send_telegram(f"❌ SL HIT {symbol}")
                del self.trades[symbol]

            elif low <= trade["tp"]:
                send_telegram(f"✅ TP HIT {symbol}")
                del self.trades[symbol]

# ================= RUN =================
if __name__ == "__main__":
    bot = Bot()
    bot.run()
