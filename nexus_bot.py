import time
import requests
from datetime import datetime

TELEGRAM_TOKEN = "8680925321:AAF3d9OwKKBjXSQzO0_A7rxIzOQDtLIhuKo"
CHAT_ID = "2046394042"

symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]

active_trades = {}
cooldown = {}

MAX_ACTIVE_TRADES = 2
COOLDOWN_TIME = 300  # 5 min


# ---------- UTIL ----------
def log(msg):
    print(f"[{datetime.now()}] {msg}", flush=True)


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})


def get_klines(symbol, interval="1m", limit=50):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    return requests.get(url).json()


def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    price = float(requests.get(url).json()['price'])
    log(f"{symbol} Price: {price}")
    return price


# ---------- INDICATORS ----------
def ema(prices, period):
    k = 2 / (period + 1)
    ema_val = prices[0]
    for price in prices:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val


def rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        if diff >= 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))

    avg_gain = sum(gains[-period:]) / period if gains else 0
    avg_loss = sum(losses[-period:]) / period if losses else 1

    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    return 100 - (100 / (1 + rs))


# ---------- SIGNAL LOGIC ----------
def generate_signal(symbol):
    klines = get_klines(symbol)
    closes = [float(k[4]) for k in klines]

    ema_fast = ema(closes[-20:], 20)
    ema_slow = ema(closes[-50:], 50)
    current_price = closes[-1]

    rsi_val = rsi(closes)

    # TREND
    trend = None
    if ema_fast > ema_slow:
        trend = "BUY"
    elif ema_fast < ema_slow:
        trend = "SELL"

    # MOMENTUM
    momentum = None
    if rsi_val > 55:
        momentum = "BUY"
    elif rsi_val < 45:
        momentum = "SELL"

    # PULLBACK (simple liquidity-style)
    pullback = None
    if trend == "BUY" and current_price < ema_fast:
        pullback = "BUY"
    elif trend == "SELL" and current_price > ema_fast:
        pullback = "SELL"

    confirmations = [trend, momentum, pullback]
    valid = [c for c in confirmations if c is not None]

    if len(valid) < 2:
        log(f"{symbol} No strong signal")
        return None, 0

    # Majority direction
    direction = max(set(valid), key=valid.count)
    strength = valid.count(direction)

    return direction, strength


# ---------- RISK ----------
def calculate_sl_tp(price, side, strength):
    sl_percent = 0.003  # 0.3% (better than before)

    rr = 3 if strength == 3 else 2

    if side == "BUY":
        sl = price * (1 - sl_percent)
        tp = price + (price - sl) * rr
    else:
        sl = price * (1 + sl_percent)
        tp = price - (sl - price) * rr

    return sl, tp, rr


# ---------- TRADE MGMT ----------
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


# ---------- START ----------
send_telegram("🧠 BALANCED SMC MODE ACTIVE (DEMO)")
log("SMC BOT STARTED")

while True:
    try:
        for symbol in symbols:

            price = get_price(symbol)

            # Manage existing trade
            if symbol in active_trades:
                if check_trade_exit(symbol, active_trades[symbol], price):
                    del active_trades[symbol]
                continue

            # Limit trades
            if len(active_trades) >= MAX_ACTIVE_TRADES:
                log("Max trades reached")
                continue

            # Cooldown
            if symbol in cooldown:
                if time.time() - cooldown[symbol] < COOLDOWN_TIME:
                    log(f"{symbol} cooling down")
                    continue

            signal, strength = generate_signal(symbol)

            if signal is None:
                continue

            sl, tp, rr = calculate_sl_tp(price, signal, strength)

            active_trades[symbol] = {
                "side": signal,
                "entry": price,
                "sl": sl,
                "tp": tp
            }

            log(f"NEW TRADE {symbol} {signal} strength {strength}")

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
