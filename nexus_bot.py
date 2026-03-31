import time
import requests
import random
from datetime import datetime

TELEGRAM_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]

active_trades = {}
cooldown = {}

MAX_ACTIVE_TRADES = 2
COOLDOWN_TIME = 300

def log(msg):
    print(f"[{datetime.now()}] {msg}", flush=True)

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    price = float(requests.get(url).json()['price'])
    log(f"{symbol} Price: {price}")
    return price

def generate_signal():
    return random.choice(["BUY", "SELL", None])

def calculate_sl_tp(price, side, strength):
    sl_percent = 0.002

    rr = 3 if strength == 3 else 2

    if side == "BUY":
        sl = price * (1 - sl_percent)
        tp = price + (price - sl) * rr
    else:
        sl = price * (1 + sl_percent)
        tp = price - (sl - price) * rr

    return sl, tp, rr

def check_trade_exit(symbol, trade, price):
    if trade['side'] == "BUY":
        if price <= trade['sl']:
            log(f"{symbol} SL HIT")
            send_telegram(f"❌ SL HIT {symbol}")
            cooldown[symbol] = time.time()
            return True
        elif price >= trade['tp']:
            log(f"{symbol} TP HIT")
            send_telegram(f"✅ TP HIT {symbol}")
            return True
    else:
        if price >= trade['sl']:
            log(f"{symbol} SL HIT")
            send_telegram(f"❌ SL HIT {symbol}")
            cooldown[symbol] = time.time()
            return True
        elif price <= trade['tp']:
            log(f"{symbol} TP HIT")
            send_telegram(f"✅ TP HIT {symbol}")
            return True
    return False

send_telegram("⚖️ PERFECT BALANCE MODE ACTIVE (DEMO)")
log("BOT STARTED")

while True:
    try:
        for symbol in symbols:

            price = get_price(symbol)

            # Manage existing trade
            if symbol in active_trades:
                if check_trade_exit(symbol, active_trades[symbol], price):
                    del active_trades[symbol]
                continue

            if len(active_trades) >= MAX_ACTIVE_TRADES:
                log("Max trades reached")
                continue

            if symbol in cooldown:
                if time.time() - cooldown[symbol] < COOLDOWN_TIME:
                    log(f"{symbol} in cooldown")
                    continue

            signal = generate_signal()

            if signal is None:
                log(f"{symbol} No signal")
                continue

            strength = random.choice([2, 3])
            sl, tp, rr = calculate_sl_tp(price, signal, strength)

            active_trades[symbol] = {
                "side": signal,
                "entry": price,
                "sl": sl,
                "tp": tp
            }

            log(f"NEW TRADE {symbol} {signal}")

            msg = f"""🚀 ENTER {symbol}
Type: {signal}
Price: {round(price, 2)}
SL: {round(sl, 2)}
TP: {round(tp, 2)}
R:R: {rr}
Strength: {strength}/3"""

            send_telegram(msg)

        time.sleep(15)

    except Exception as e:
        log(f"ERROR: {e}")
        time.sleep(10)
