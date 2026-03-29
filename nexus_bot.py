import os, time, logging, requests
from datetime import datetime
import pandas as pd
import ta

# ================= CONFIG =================
CONFIG = {
    "TRADE_MODE": "DEMO",

    # ✅ FIXED MULTI SYMBOLS
    "MULTI_SYMBOLS": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"],

    "BINANCE_INTERVAL": "1m",

    "RISK_PERCENT": 0.5,
    "RR_RATIO": 2.0,
    "MAX_OPEN_TRADES": 3,

    "STARTING_CAPITAL": 30000,
}

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

        # 🔥 BREAKOUT LOGIC
        high = df["high"].rolling(10).max().iloc[-2]
        low = df["low"].rolling(10).min().iloc[-2]

        vol_avg = df["volume"].rolling(10).mean().iloc[-2]

        if price > high and last["volume"] > vol_avg * 1.5:
            return {"signal": "BUY", "entry": price, "sl": price - atr}

        if price < low and last["volume"] > vol_avg * 1.5:
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

    def run(self):

        for symbol in CONFIG["MULTI_SYMBOLS"]:

            df = self.trader.get_candles(symbol)
            res = self.strategy.analyze(df)

            log.info(f"{symbol} → {res['signal']}")

            # ENTRY
            if res["signal"] in ["BUY", "SELL"] and symbol not in self.trades:

                self.trades[symbol] = {
                    "entry": res["entry"],
                    "sl": res["sl"],
                    "tp": res["entry"] * 1.01,
                    "dir": res["signal"],
                    "time": datetime.now()
                }

                log.info(f"🚀 ENTER {symbol}")

            # EXIT
            elif symbol in self.trades:

                t = self.trades[symbol]
                price = self.trader.get_price(symbol)

                # TP
                if (t["dir"] == "BUY" and price >= t["tp"]) or \
                   (t["dir"] == "SELL" and price <= t["tp"]):
                    log.info(f"✅ TP {symbol}")
                    del self.trades[symbol]

                # SL
                elif (t["dir"] == "BUY" and price <= t["sl"]) or \
                     (t["dir"] == "SELL" and price >= t["sl"]):
                    log.info(f"❌ SL {symbol}")
                    del self.trades[symbol]

                # TIME EXIT
                elif (datetime.now() - t["time"]).seconds > 900:
                    log.info(f"⏱ TIME EXIT {symbol}")
                    del self.trades[symbol]


# ================= RUN =================
bot = Bot()

while True:
    bot.run()
    time.sleep(5)
