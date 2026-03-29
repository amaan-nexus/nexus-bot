import os, time, logging, requests
from datetime import datetime
import pandas as pd
import ta

# ================= CONFIG =================
CONFIG = {
    "TRADE_MODE": "DEMO",
    "MULTI_SYMBOLS": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"],
    "BINANCE_INTERVAL": "1m",
}

# ================= TELEGRAM =================
TELEGRAM_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
TELEGRAM_CHAT_ID = "2046394042"

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except:
        pass

# ================= LOG =================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("BOT")

# ================= STRATEGY =================
class StrategyEngine:

    def analyze(self, df):
        if len(df) < 50:
            return {"signal": "WAIT", "entry": 0}

        df["ema_fast"] = ta.trend.ema_indicator(df["close"], 9)
        df["ema_slow"] = ta.trend.ema_indicator(df["close"], 21)
        df["atr"] = ta.volatility.average_true_range(df["high"], df["low"], df["close"])

        last = df.iloc[-1]
        price = last["close"]
        atr = last["atr"]

        high = df["high"].rolling(10).max().iloc[-2]
        low = df["low"].rolling(10).min().iloc[-2]

        # 🔥 EARLIER BREAKOUT (more trades)
        if price > high * 0.999 and last["ema_fast"] > last["ema_slow"]:
            return {"signal": "BUY", "entry": price, "sl": price - atr}

        if price < low * 1.001 and last["ema_fast"] < last["ema_slow"]:
            return {"signal": "SELL", "entry": price, "sl": price + atr}

        # 🔥 TREND FOLLOW (backup)
        if last["ema_fast"] > last["ema_slow"]:
            return {"signal": "BUY", "entry": price, "sl": price - atr}

        elif last["ema_fast"] < last["ema_slow"]:
            return {"signal": "SELL", "entry": price, "sl": price + atr}

        return {"signal": "WAIT", "entry": price}


# ================= BINANCE =================
class BinanceTrader:

    def get_candles(self, symbol):
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=100"
        data = requests.get(url).json()

        df = pd.DataFrame(data, columns=["t","o","h","l","c","v","ct","q","n","tb","tq","i"])
        df = df.astype(float)
        df.columns = ["time","open","high","low","close","volume","ct","q","n","tb","tq","i"]
        return df

    def get_price(self, symbol):
        return float(requests.get(
            f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        ).json()["price"])


# ================= BOT =================
class Bot:

    def __init__(self):
        self.trader = BinanceTrader()
        self.strategy = StrategyEngine()
        self.trades = {}
        self.last_trade_time = {}

        send_telegram("✅ CONNECTED: Bot is live")

    def run(self):

        for symbol in CONFIG["MULTI_SYMBOLS"]:

            df = self.trader.get_candles(symbol)
            res = self.strategy.analyze(df)

            log.info(f"{symbol} → {res['signal']}")

            # ENTRY
            
now = datetime.now()

if res["signal"] in ["BUY", "SELL"] and symbol not in self.trades:

    last_time = self.last_trade_time.get(symbol)

    if last_time and (now - last_time).seconds < 300:
        continue
                self.trades[symbol] = {
                    "entry": res["entry"],
                    "sl": res["sl"],
                    "tp": res["entry"] * 1.02,
                    "dir": res["signal"],
                    "time": datetime.now()
                }
        self.last_trade_time[symbol] = datetime.now()

                msg = f"🚀 ENTER {symbol}\nPrice: {res['entry']}\nSL: {res['sl']}"
                log.info(msg)
                send_telegram(msg)

            # EXIT
            elif symbol in self.trades:

                t = self.trades[symbol]
                price = self.trader.get_price(symbol)

                # TP
                if (t["dir"] == "BUY" and price >= t["tp"]) or \
                   (t["dir"] == "SELL" and price <= t["tp"]):
                    send_telegram(f"✅ TP HIT {symbol}")
self.last_trade_time[symbol] = datetime.now()
del self.trades[symbol]

                # SL
                elif (t["dir"] == "BUY" and price <= t["sl"]) or \
                     (t["dir"] == "SELL" and price >= t["sl"]):
                    send_telegram(f"❌ SL HIT {symbol}")
self.last_trade_time[symbol] = datetime.now()
del self.trades[symbol]

                # TIME EXIT
                elif (datetime.now() - t["time"]).seconds > 900:
                    send_telegram(f"⏱ TIME EXIT {symbol}")
self.last_trade_time[symbol] = datetime.now()
del self.trades[symbol]


# ================= RUN =================
bot = Bot()

while True:
    bot.run()
    time.sleep(5)
