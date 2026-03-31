import requests
import time
from datetime import datetime

# ================= CONFIG =================
TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]

COOLDOWN = 60
SLEEP = 5

# ================= TELEGRAM =================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# ================= PRICE =================
def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    return float(requests.get(url).json()["price"])

# ================= BOT =================
class Bot:
    def __init__(self):
        self.last_price = {}
        self.last_signal = {}
        self.last_trade_time = {}
        self.trades = {}

        self.trade_history = []
        self.win = 0
        self.loss = 0

    # ===== PERFECT BALANCE ANALYSIS =====
    def analyze(self, symbol, price):
        last = self.last_price.get(symbol)

        if last is None:
            self.last_price[symbol] = price
            return None

        change = (price - last) / last

        # ===== MARKET ACTIVITY FILTER =====
        volatility = abs(change) > 0.0006

        # ===== MOMENTUM =====
        momentum = abs(change) > 0.0009

        # ===== STRUCTURE =====
        structure = (price > last * 1.001) or (price < last * 0.999)

        # ===== LIQUIDITY MOVE =====
        liquidity = abs(price - last) > 0.0012 * price

        score = sum([momentum, structure, liquidity])

        # ===== FINAL SIGNAL =====
        signal = None
        if volatility and score >= 2:
            signal = "BUY" if change > 0 else "SELL"

        self.last_price[symbol] = price

        if signal:
            return {
                "signal": signal,
                "sl": price * (0.996 if signal == "BUY" else 1.004),
                "tp": price * (1.012 if signal == "BUY" else 0.988),
                "entry": price
            }

        return None

    # ===== DAILY REPORT =====
    def send_daily_report(self):
        total = self.win + self.loss
        winrate = round((self.win / total) * 100, 2) if total > 0 else 0

        msg = "📊 DAILY REPORT\n\n"
        msg += f"Total Trades: {total}\n"
        msg += f"Wins: {self.win} ✅\n"
        msg += f"Loss: {self.loss} ❌\n"
        msg += f"Win Rate: {winrate}%\n\n"

        pnl = 0
        msg += "Trades:\n"

        for t in self.trade_history:
            if t["result"] == "TP":
                msg += f"{t['symbol']} {t['dir']} | TP ✅ | R:R {t['rr']}\n"
                pnl += t["rr"]
            elif t["result"] == "SL":
                msg += f"{t['symbol']} {t['dir']} | SL ❌ | R:R {t['rr']}\n"
                pnl -= 1

        msg += f"\nPnL (R): {round(pnl,2)}"

        send_telegram(msg)

    def run(self):
        send_telegram("⚖️ PERFECT BALANCE MODE ACTIVE (DEMO)")

        while True:
            now = datetime.now()

            for symbol in SYMBOLS:
                try:
                    price = get_price(symbol)
                    print(f"{symbol} | {price}")

                    res = self.analyze(symbol, price)

                    last_signal = self.last_signal.get(symbol)
                    last_trade = self.last_trade_time.get(symbol)

                    # ===== ENTRY =====
                    if res:
                        if (
                            symbol not in self.trades and
                            res["signal"] != last_signal and
                            (last_trade is None or (now - last_trade).seconds > COOLDOWN)
                        ):
                            self.trades[symbol] = res
                            self.last_signal[symbol] = res["signal"]
                            self.last_trade_time[symbol] = now

                            rr = round(abs((res["tp"] - res["entry"]) / (res["entry"] - res["sl"])), 2)

                            self.trade_history.append({
                                "symbol": symbol,
                                "dir": res["signal"],
                                "rr": rr,
                                "result": "OPEN"
                            })

                            send_telegram(
                                f"🚀 ENTER {symbol}\n"
                                f"{res['signal']} @ {price}\n"
                                f"SL: {res['sl']}\n"
                                f"TP: {res['tp']}\n"
                                f"R:R: {rr}"
                            )

                    # ===== EXIT =====
                    if symbol in self.trades:
                        trade = self.trades[symbol]

                        if trade["signal"] == "BUY":
                            if price >= trade["tp"]:
                                self.win += 1
                                send_telegram(f"✅ TP HIT {symbol}")
                                del self.trades[symbol]

                                for t in self.trade_history[::-1]:
                                    if t["symbol"] == symbol and t["result"] == "OPEN":
                                        t["result"] = "TP"
                                        break

                            elif price <= trade["sl"]:
                                self.loss += 1
                                send_telegram(f"❌ SL HIT {symbol}")
                                del self.trades[symbol]

                                for t in self.trade_history[::-1]:
                                    if t["symbol"] == symbol and t["result"] == "OPEN":
                                        t["result"] = "SL"
                                        break

                        elif trade["signal"] == "SELL":
                            if price <= trade["tp"]:
                                self.win += 1
                                send_telegram(f"✅ TP HIT {symbol}")
                                del self.trades[symbol]

                                for t in self.trade_history[::-1]:
                                    if t["symbol"] == symbol and t["result"] == "OPEN":
                                        t["result"] = "TP"
                                        break

                            elif price >= trade["sl"]:
                                self.loss += 1
                                send_telegram(f"❌ SL HIT {symbol}")
                                del self.trades[symbol]

                                for t in self.trade_history[::-1]:
                                    if t["symbol"] == symbol and t["result"] == "OPEN":
                                        t["result"] = "SL"
                                        break

                except Exception as e:
                    print("Error:", e)

            # ===== DAILY REPORT =====
            if now.hour == 23 and now.minute == 59:
                self.send_daily_report()
                self.trade_history = []
                self.win = 0
                self.loss = 0

            time.sleep(SLEEP)

# ================= RUN =================
if __name__ == "__main__":
    Bot().run()
