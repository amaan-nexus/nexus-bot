import requests
import time
import logging
from datetime import datetime

# ================= CONFIG =================
CONFIG = {
    "TELEGRAM_TOKEN": "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo",
    "CHAT_ID": "2046394042",
    "MULTI_SYMBOLS": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"],
}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

# ================= TELEGRAM =================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{CONFIG['TELEGRAM_TOKEN']}/sendMessage"
        requests.post(url, json={
            "chat_id": CONFIG["CHAT_ID"],
            "text": msg
        })
    except Exception as e:
        log.error(f"Telegram Error: {e}")

# ================= BINANCE =================
class BinanceTrader:
    def get_price(self, symbol):
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        return float(requests.get(url).json()["price"])

# ================= STRATEGY =================
class StrategyEngine:
    def analyze(self, price):
        # SIMPLE DEMO STRATEGY (can upgrade later)
        if price % 2 > 1:
            return {"signal": "BUY", "entry": price, "sl": price * 0.995}
        else:
            return {"signal": "SELL", "entry": price, "sl": price * 1.005}

# ================= BOT =================
class Bot:
    def __init__(self):
        self.trader = BinanceTrader()
        self.strategy = StrategyEngine()

        self.trades = {}        # active trades
        self.last_signal = {}   # prevent duplicate entries

        send_telegram("✅ Bot Connected & Running")

    def run(self):
        while True:
            for symbol in CONFIG["MULTI_SYMBOLS"]:
                try:
                    price = self.trader.get_price(symbol)
                    res = self.strategy.analyze(price)

                    # ================= ENTRY =================
                    if (
                        res["signal"] in ["BUY", "SELL"]
                        and symbol not in self.trades
                        and res["signal"] != self.last_signal.get(symbol)
                    ):

                        tp = price * (1.02 if res["signal"] == "BUY" else 0.98)

                        self.trades[symbol] = {
                            "entry": price,
                            "sl": res["sl"],
                            "tp": tp,
                            "dir": res["signal"]
                        }

                        self.last_signal[symbol] = res["signal"]

                        send_telegram(
                            f"🚀 ENTER {symbol}\n"
                            f"Type: {res['signal']}\n"
                            f"Price: {price}\n"
                            f"SL: {res['sl']}\n"
                            f"TP: {tp}"
                        )

                    # ================= EXIT =================
                    if symbol in self.trades:
                        trade = self.trades[symbol]

                        if trade["dir"] == "BUY":
                            if price >= trade["tp"]:
                                send_telegram(f"✅ TP HIT {symbol}")
                                del self.trades[symbol]
                                self.last_signal[symbol] = None

                            elif price <= trade["sl"]:
                                send_telegram(f"❌ SL HIT {symbol}")
                                del self.trades[symbol]
                                self.last_signal[symbol] = None

                        elif trade["dir"] == "SELL":
                            if price <= trade["tp"]:
                                send_telegram(f"✅ TP HIT {symbol}")
                                del self.trades[symbol]
                                self.last_signal[symbol] = None

                            elif price >= trade["sl"]:
                                send_telegram(f"❌ SL HIT {symbol}")
                                del self.trades[symbol]
                                self.last_signal[symbol] = None

                except Exception as e:
                    log.error(f"{symbol} error: {e}")

            # 🔥 IMPORTANT DELAY (prevents spam)
            time.sleep(10)

# ================= RUN =================
if __name__ == "__main__":
    bot = Bot()
    bot.run()
