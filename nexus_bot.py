import requests
import time
import logging
from datetime import datetime

# ================= CONFIG =================
CONFIG = {
    "TELEGRAM_TOKEN": "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo",
    "CHAT_ID": "2046394042",
    "MULTI_SYMBOLS": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"],
    "INTERVAL": "5m",
    "COOLDOWN": 300,  # seconds (5 min)
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
        # SIMPLE LOGIC (you can upgrade later)
        if price % 2 > 1:
            return {"signal": "BUY", "entry": price, "sl": price * 0.995}
        else:
            return {"signal": "SELL", "entry": price, "sl": price * 1.005}

# ================= BOT =================
class Bot:
    def __init__(self):
        self.trader = BinanceTrader()
        self.strategy = StrategyEngine()

        self.trades = {}
        self.last_trade_time = {}
        self.last_signal = {}
        self.last_entry_price = {}

        send_telegram("✅ Bot Connected & Running")

    def run(self):
        while True:
            for symbol in CONFIG["MULTI_SYMBOLS"]:
                try:
                    price = self.trader.get_price(symbol)
                    res = self.strategy.analyze(price)

                    now = datetime.now()

                    last_signal = self.last_signal.get(symbol)
                    last_price = self.last_entry_price.get(symbol)

                    # DEBUG (always sends → confirm working)
                    send_telegram(f"DEBUG {symbol}: {res['signal']} @ {price}")

                    # ENTRY CONDITIONS
                    if (
                        res["signal"] in ["BUY", "SELL"]
                        and symbol not in self.trades
                        and (
                            last_signal != res["signal"]
                            or (now - self.last_trade_time.get(symbol, now)).seconds > CONFIG["COOLDOWN"]
                        )
                        and (last_price is None or abs(price - last_price) > 0.002 * price)
                    ):

                        self.trades[symbol] = {
                            "entry": price,
                            "sl": res["sl"],
                            "tp": price * (1.02 if res["signal"] == "BUY" else 0.98),
                            "dir": res["signal"]
                        }

                        self.last_trade_time[symbol] = now
                        self.last_signal[symbol] = res["signal"]
                        self.last_entry_price[symbol] = price

                        send_telegram(
                            f"🚀 ENTER {symbol}\n"
                            f"Type: {res['signal']}\n"
                            f"Price: {price}\n"
                            f"SL: {res['sl']}"
                        )

                    # EXIT CONDITIONS
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

                except Exception as e:
                    log.error(f"{symbol} error: {e}")

            time.sleep(10)

# ================= RUN =================
if __name__ == "__main__":
    bot = Bot()
    bot.run()
