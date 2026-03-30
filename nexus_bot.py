import requests
import time
from datetime import datetime

TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]

# ================= TELEGRAM =================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# ================= DATA =================
def get_klines(symbol):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=5m&limit=120"
    return requests.get(url).json()

# ================= EMA =================
def ema(data, period):
    k = 2 / (period + 1)
    ema_val = float(data[0][4])
    for candle in data:
        price = float(candle[4])
        ema_val = price * k + ema_val * (1 - k)
    return ema_val

# ================= BOT =================
class Bot:
    def __init__(self):
        self.trades = {}
        self.cooldown = {}

    def run(self):
        send_telegram("🏦 HEDGE FUND BOT RUNNING (DEMO MODE)")

        while True:
            try:
                for symbol in SYMBOLS:
                    data = get_klines(symbol)

                    highs = [float(x[2]) for x in data]
                    lows = [float(x[3]) for x in data]
                    closes = [float(x[4]) for x in data]

                    price = closes[-1]
                    prev_high = highs[-2]
                    prev_low = lows[-2]

                    ema50 = ema(data, 50)

                    now = datetime.now()

                    # ================= TREND =================
                    uptrend = price > ema50
                    downtrend = price < ema50

                    # ================= LIQUIDITY =================
                    sweep_high = price > prev_high
                    sweep_low = price < prev_low

                    # ================= STRUCTURE BREAK =================
                    prev_close = closes[-2]
                    bullish_shift = price > prev_close
                    bearish_shift = price < prev_close

                    # ================= ENTRY =================
                    if symbol not in self.trades and (now - self.cooldown.get(symbol, now)).seconds > 180:

                        # 🔺 BUY (liquidity sweep below + trend + shift)
                        if sweep_low and bullish_shift and uptrend:
                            sl = price * 0.995
                            tp = price * 1.02

                            self.trades[symbol] = {"dir": "BUY", "tp": tp, "sl": sl}
                            self.cooldown[symbol] = now

                            send_telegram(
                                f"🏦 BUY {symbol}\n"
                                f"SMC Setup: Liquidity Sweep LOW\n"
                                f"Trend: UP\n"
                                f"Price: {round(price,2)}\n"
                                f"SL: {round(sl,2)}\n"
                                f"TP: {round(tp,2)}"
                            )

                        # 🔻 SELL (liquidity sweep above + trend + shift)
                        elif sweep_high and bearish_shift and downtrend:
                            sl = price * 1.005
                            tp = price * 0.98

                            self.trades[symbol] = {"dir": "SELL", "tp": tp, "sl": sl}
                            self.cooldown[symbol] = now

                            send_telegram(
                                f"🏦 SELL {symbol}\n"
                                f"SMC Setup: Liquidity Sweep HIGH\n"
                                f"Trend: DOWN\n"
                                f"Price: {round(price,2)}\n"
                                f"SL: {round(sl,2)}\n"
                                f"TP: {round(tp,2)}"
                            )

                    # ================= EXIT =================
                    if symbol in self.trades:
                        trade = self.trades[symbol]

                        if trade["dir"] == "BUY":
                            if price >= trade["tp"]:
                                send_telegram(f"✅ TP HIT {symbol}")
                                del self.trades[symbol]

                            elif price <= trade["sl"]:
                                send_telegram(f"❌ SL HIT {symbol}")
                                del self.trades[symbol]

                        elif trade["dir"] == "SELL":
                            if price <= trade["tp"]:
                                send_telegram(f"✅ TP HIT {symbol}")
                                del self.trades[symbol]

                            elif price >= trade["sl"]:
                                send_telegram(f"❌ SL HIT {symbol}")
                                del self.trades[symbol]

                time.sleep(12)

            except Exception as e:
                print("ERROR:", e)
                time.sleep(5)

# ================= RUN =================
if __name__ == "__main__":
    Bot().run()
