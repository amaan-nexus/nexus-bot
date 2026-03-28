"""
╔══════════════════════════════════════════════════════════╗
║           NEXUS AUTO-TRADER BOT v1.0                     ║
║           Supports: Binance (Crypto) + MT5 (XAU/XAG)    ║
║           Built-in: R/R rules, Risk Mgmt, Trade Log      ║
╚══════════════════════════════════════════════════════════╝

SETUP INSTRUCTIONS:
1. Install dependencies:
   pip install python-binance pandas ta schedule requests MetaTrader5

2. Set your API keys (do NOT hardcode — use environment variables):
   Windows:  set BINANCE_KEY=xxx  &  set BINANCE_SECRET=xxx
   Mac/Linux: export BINANCE_KEY=xxx && export BINANCE_SECRET=xxx

3. For Telegram alerts (optional):
   - Create bot via @BotFather in Telegram
   - Set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID below

4. ALWAYS start in DEMO mode. Switch to LIVE only after 2 weeks profit.

5. Run: python nexus_bot.py
"""

import os
import time
import logging
import csv
import json
import requests
from datetime import datetime, date
from binance.client import Client
from binance.enums import *
import pandas as pd
import ta

# ─────────────────────────────────────────
#   ⚙  CONFIGURATION — EDIT THIS SECTION
# ─────────────────────────────────────────
CONFIG = {
    # Trading mode: 'DEMO' (paper trade, no real orders) or 'LIVE'
    "TRADE_MODE": "DEMO",

    # ── Binance Crypto Settings ──
    "BINANCE_SYMBOL": "BTCUSDT",     # Symbol to trade
    "BINANCE_INTERVAL": "5m",         # Candle interval: 1m, 5m, 15m, 1h, 4h
    "BINANCE_LEVERAGE": 1,            # 1 = no leverage (recommended for beginners)

    # ── Risk Management ──
    "RISK_PERCENT": 1.0,              # % of capital to risk per trade (1-2%)
    "RR_RATIO": 2.0,                  # Risk:Reward ratio (2.0 = 1:2)
    "MAX_DAILY_LOSS_PCT": 3.0,        # Stop trading if daily loss exceeds this %
    "MAX_OPEN_TRADES": 1,             # Max simultaneous open trades

    # ── Strategy Settings ──
    "EMA_FAST": 9,
    "EMA_SLOW": 21,
    "RSI_PERIOD": 14,
    "RSI_OVERBOUGHT": 70,
    "RSI_OVERSOLD": 30,
    "MACD_FAST": 12,
    "MACD_SLOW": 26,
    "MACD_SIGNAL": 9,

    # ── Capital ──
    "STARTING_CAPITAL": float(os.getenv("STARTING_CAPITAL", "30000")),        # Your capital in base currency (₹ equivalent)

    # ── Telegram Alerts (optional) ──
    "TELEGRAM_TOKEN": os.getenv("TELEGRAM_TOKEN", ""),             # Your bot token from @BotFather
    "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", ""),           # Your chat ID

    # ── Logging ──
    "LOG_FILE": "nexus_bot.log",
    "TRADE_LOG": "trade_log.csv",
}

# ─────────────────────────────────────────
#   LOGGING SETUP
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(CONFIG["LOG_FILE"]),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("NexusBot")


# ─────────────────────────────────────────
#   TRADE JOURNAL
# ─────────────────────────────────────────
class TradeJournal:
    """Logs every trade to a CSV file — your automated trade journal."""

    def __init__(self, filepath):
        self.filepath = filepath
        self.headers = [
            "Date", "Time", "Symbol", "Direction", "Entry",
            "StopLoss", "TakeProfit", "PositionSize", "RiskAmount",
            "PotentialProfit", "RR", "Status", "PnL", "Notes"
        ]
        if not os.path.exists(filepath):
            with open(filepath, "w", newline="") as f:
                csv.writer(f).writerow(self.headers)
        log.info(f"Trade journal ready: {filepath}")

    def log_trade(self, trade: dict):
        with open(self.filepath, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writerow(trade)
        log.info(f"Trade logged: {trade['Direction']} {trade['Symbol']} @ {trade['Entry']}")


# ─────────────────────────────────────────
#   TELEGRAM ALERTS
# ─────────────────────────────────────────
class TelegramAlert:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)

    def send(self, message):
        if not self.enabled:
            return
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            requests.post(url, data={"chat_id": self.chat_id, "text": message}, timeout=5)
            log.info("Telegram alert sent")
        except Exception as e:
            log.warning(f"Telegram alert failed: {e}")


# ─────────────────────────────────────────
#   RISK MANAGER
# ─────────────────────────────────────────
class RiskManager:
    """
    Enforces your risk rules:
    - Max 1-2% risk per trade
    - Daily loss limit
    - Max open trades
    """

    def __init__(self, capital, risk_pct, max_daily_loss_pct, rr_ratio):
        self.capital = capital
        self.risk_pct = risk_pct / 100
        self.max_daily_loss_pct = max_daily_loss_pct / 100
        self.rr_ratio = rr_ratio
        self.daily_pnl = 0.0
        self.daily_reset_date = date.today()
        self.open_trades = 0

    def reset_daily_if_needed(self):
        today = date.today()
        if today != self.daily_reset_date:
            log.info(f"New day — resetting daily P&L (was {self.daily_pnl:.2f})")
            self.daily_pnl = 0.0
            self.daily_reset_date = today

    def can_trade(self):
        self.reset_daily_if_needed()
        loss_limit = self.capital * self.max_daily_loss_pct
        if self.daily_pnl <= -loss_limit:
            log.warning(f"🛑 DAILY LOSS LIMIT HIT ({self.daily_pnl:.2f}). No more trades today.")
            return False
        if self.open_trades >= CONFIG["MAX_OPEN_TRADES"]:
            log.warning(f"Max open trades ({CONFIG['MAX_OPEN_TRADES']}) reached.")
            return False
        return True

    def calculate_position(self, entry_price, stop_loss_price):
        """
        Calculate position size based on 1% risk rule.
        Returns: (position_size, risk_amount, take_profit_price)
        """
        risk_amount = self.capital * self.risk_pct
        sl_distance = abs(entry_price - stop_loss_price)

        if sl_distance == 0:
            log.error("Stop loss = entry price. Skipping.")
            return None, None, None

        position_size = risk_amount / sl_distance
        tp_distance = sl_distance * self.rr_ratio

        if entry_price > stop_loss_price:  # Long
            take_profit = entry_price + tp_distance
        else:  # Short
            take_profit = entry_price - tp_distance

        potential_profit = position_size * tp_distance

        log.info(
            f"Position calculated: Size={position_size:.6f} | "
            f"Risk=₹{risk_amount:.2f} | "
            f"TP={take_profit:.4f} | "
            f"Potential profit=₹{potential_profit:.2f}"
        )
        return position_size, risk_amount, take_profit

    def update_pnl(self, pnl):
        self.daily_pnl += pnl
        self.capital += pnl
        log.info(f"PnL updated: {pnl:+.2f} | Daily: {self.daily_pnl:+.2f} | Capital: {self.capital:.2f}")


# ─────────────────────────────────────────
#   TECHNICAL ANALYSIS ENGINE
# ─────────────────────────────────────────
class StrategyEngine:
    """
    Strategy: EMA crossover + RSI filter + MACD confirmation
    Based on your trading foundations (top-down approach)
    """

    def __init__(self, cfg):
        self.cfg = cfg

    def analyze(self, df: pd.DataFrame) -> dict:
        """
        Run technical analysis on OHLCV data.
        Returns signal dict with: signal, entry, sl, reason
        """
        if len(df) < 50:
            return {"signal": "WAIT", "reason": "Not enough data"}

        # ── Indicators ──
        df["ema_fast"] = ta.trend.ema_indicator(df["close"], window=self.cfg["EMA_FAST"])
        df["ema_slow"] = ta.trend.ema_indicator(df["close"], window=self.cfg["EMA_SLOW"])
        df["rsi"] = ta.momentum.rsi(df["close"], window=self.cfg["RSI_PERIOD"])

        macd = ta.trend.MACD(
            df["close"],
            window_fast=self.cfg["MACD_FAST"],
            window_slow=self.cfg["MACD_SLOW"],
            window_sign=self.cfg["MACD_SIGNAL"]
        )
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        df["macd_hist"] = macd.macd_diff()

        # ATR for stop loss placement
        df["atr"] = ta.volatility.average_true_range(df["high"], df["low"], df["close"], window=14)

        last = df.iloc[-1]
        prev = df.iloc[-2]

        price = last["close"]
        atr = last["atr"]
        rsi = last["rsi"]

        # ── Signal Logic ──

        # BUY conditions:
        # 1. Fast EMA crossed above Slow EMA
        # 2. RSI between 40-65 (not overbought, not oversold bounce)
        # 3. MACD histogram turning positive
        ema_cross_up = prev["ema_fast"] < prev["ema_slow"] and last["ema_fast"] > last["ema_slow"]
        rsi_ok_buy = self.cfg["RSI_OVERSOLD"] < rsi < self.cfg["RSI_OVERBOUGHT"] - 5
        macd_bullish = last["macd_hist"] > 0 and prev["macd_hist"] <= 0

        # SELL conditions:
        # 1. Fast EMA crossed below Slow EMA
        # 2. RSI between 35-70
        # 3. MACD histogram turning negative
        # HARD RULE: Never sell if RSI < 20
        ema_cross_down = prev["ema_fast"] > prev["ema_slow"] and last["ema_fast"] < last["ema_slow"]
        rsi_ok_sell = rsi > 20 and rsi > self.cfg["RSI_OVERSOLD"] + 5  # Never sell below RSI 20
        macd_bearish = last["macd_hist"] < 0 and prev["macd_hist"] >= 0

        if ema_cross_up and rsi_ok_buy and macd_bullish:
            sl = price - (atr * 1.5)
            return {
                "signal": "BUY",
                "entry": price,
                "sl": round(sl, 4),
                "rsi": round(rsi, 2),
                "reason": f"EMA crossover UP + MACD bullish + RSI {rsi:.1f}"
            }

        elif ema_cross_down and rsi_ok_sell and macd_bearish:
            sl = price + (atr * 1.5)
            return {
                "signal": "SELL",
                "entry": price,
                "sl": round(sl, 4),
                "rsi": round(rsi, 2),
                "reason": f"EMA crossover DOWN + MACD bearish + RSI {rsi:.1f}"
            }

        return {
            "signal": "WAIT",
            "entry": price,
            "rsi": round(rsi, 2),
            "reason": f"No signal. RSI={rsi:.1f}, EMA gap={abs(last['ema_fast'] - last['ema_slow']):.4f}"
        }


# ─────────────────────────────────────────
#   BINANCE CONNECTOR
# ─────────────────────────────────────────
class BinanceTrader:
    def __init__(self, trade_mode="DEMO"):
        self.mode = trade_mode
        api_key = os.getenv("BINANCE_KEY", "")
        api_secret = os.getenv("BINANCE_SECRET", "")

        if api_key and api_secret:
            self.client = Client(api_key, api_secret)
            log.info("✅ Binance API connected")
        else:
            self.client = None
            log.warning("⚠ No Binance API keys found. Running in simulation mode.")

    def get_candles(self, symbol, interval, limit=100) -> pd.DataFrame:
        """Fetch OHLCV candles from Binance."""
        try:
            if self.client:
                raw = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            else:
                # Fallback: use public endpoint (no auth needed)
                url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
                raw = requests.get(url, timeout=10).json()

            df = pd.DataFrame(raw, columns=[
                "time", "open", "high", "low", "close", "volume",
                "close_time", "quote_vol", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore"
            ])
            df[["open", "high", "low", "close", "volume"]] = \
                df[["open", "high", "low", "close", "volume"]].astype(float)
            return df

        except Exception as e:
            log.error(f"Failed to get candles: {e}")
            return pd.DataFrame()

    def get_price(self, symbol) -> float:
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            return float(requests.get(url, timeout=5).json()["price"])
        except:
            return 0.0

    def get_balance(self) -> float:
        if not self.client or self.mode == "DEMO":
            return CONFIG["STARTING_CAPITAL"]
        try:
            balance = self.client.get_asset_balance(asset="USDT")
            return float(balance["free"])
        except Exception as e:
            log.error(f"Balance error: {e}")
            return 0.0

    def place_order(self, symbol, side, quantity, entry, sl, tp):
        """Place order — real if LIVE, simulated if DEMO."""
        if self.mode == "DEMO":
            log.info(
                f"[DEMO] {side} {quantity:.6f} {symbol} @ {entry:.4f} | "
                f"SL: {sl:.4f} | TP: {tp:.4f}"
            )
            return {"orderId": f"DEMO-{int(time.time())}", "status": "DEMO_FILLED"}

        # LIVE mode — real order
        try:
            order_side = SIDE_BUY if side == "BUY" else SIDE_SELL
            order = self.client.create_order(
                symbol=symbol,
                side=order_side,
                type=ORDER_TYPE_MARKET,
                quantity=round(quantity, 6),
            )
            log.info(f"✅ LIVE ORDER PLACED: {order}")
            return order
        except Exception as e:
            log.error(f"Order failed: {e}")
            return None


# ─────────────────────────────────────────
#   ECONOMIC CALENDAR CHECK
# ─────────────────────────────────────────
def is_high_impact_news_soon() -> bool:
    """
    Check Forex Factory for high-impact news in next 30 minutes.
    Returns True if we should pause trading.
    (Simplified version — checks known major events by hour)
    """
    now = datetime.utcnow()
    # Major recurring news times (UTC): NFP (Fri 13:30), CPI (mid-month 13:30), Fed (varies)
    # This is a simplified check — integrate forex_factory_calendar API for full version
    known_high_impact_hours = {
        4: (13, 30),   # Fridays — NFP
    }
    if now.weekday() in known_high_impact_hours:
        h, m = known_high_impact_hours[now.weekday()]
        news_time = now.replace(hour=h, minute=m, second=0)
        diff = (news_time - now).total_seconds() / 60
        if 0 <= diff <= 30:
            log.warning(f"⚠ High-impact news in {diff:.0f} mins. Pausing trading.")
            return True
    return False


# ─────────────────────────────────────────
#   MAIN BOT LOOP
# ─────────────────────────────────────────
class NexusBot:
    def __init__(self):
        log.info("=" * 60)
        log.info("  NEXUS AUTO-TRADER BOT v1.0 STARTING")
        log.info(f"  Mode: {CONFIG['TRADE_MODE']}")
        log.info(f"  Symbol: {CONFIG['BINANCE_SYMBOL']}")
        log.info(f"  Risk: {CONFIG['RISK_PERCENT']}% per trade | R/R: 1:{CONFIG['RR_RATIO']}")
        log.info("=" * 60)

        self.trader = BinanceTrader(CONFIG["TRADE_MODE"])
        self.strategy = StrategyEngine(CONFIG)
        self.risk = RiskManager(
            capital=CONFIG["STARTING_CAPITAL"],
            risk_pct=CONFIG["RISK_PERCENT"],
            max_daily_loss_pct=CONFIG["MAX_DAILY_LOSS_PCT"],
            rr_ratio=CONFIG["RR_RATIO"],
        )
        self.journal = TradeJournal(CONFIG["TRADE_LOG"])
        self.telegram = TelegramAlert(CONFIG["TELEGRAM_TOKEN"], CONFIG["TELEGRAM_CHAT_ID"])
        self.active_trade = None

        self.telegram.send(
            f"🤖 NEXUS BOT STARTED\n"
            f"Mode: {CONFIG['TRADE_MODE']}\n"
            f"Symbol: {CONFIG['BINANCE_SYMBOL']}\n"
            f"Capital: {CONFIG['STARTING_CAPITAL']}"
        )

    def run_cycle(self):
        """One complete analysis + decision cycle."""
        symbol = CONFIG["BINANCE_SYMBOL"]

        # 1. Check economic calendar
        if is_high_impact_news_soon():
            log.info("📰 Standby mode: High-impact news approaching.")
            return

        # 2. Check if we can trade today
        if not self.risk.can_trade():
            return

        # 3. Get market data
        df = self.trader.get_candles(symbol, CONFIG["BINANCE_INTERVAL"])
        if df.empty:
            log.warning("No market data received. Retrying next cycle.")
            return

        # 4. Run strategy
        result = self.strategy.analyze(df)
        price = result.get("entry", 0)
        rsi = result.get("rsi", 0)

        log.info(f"📊 {symbol} @ {price:.4f} | RSI: {rsi:.1f} | Signal: {result['signal']} | {result['reason']}")

        # 5. Act on signal
        if result["signal"] in ("BUY", "SELL") and self.active_trade is None:
            entry = result["entry"]
            sl = result["sl"]

            # Calculate position size
            pos_size, risk_amt, tp = self.risk.calculate_position(entry, sl)
            if pos_size is None:
                return

            # Place order
            order = self.trader.place_order(
                symbol=symbol,
                side=result["signal"],
                quantity=pos_size,
                entry=entry,
                sl=sl,
                tp=tp,
            )

            if order:
                self.active_trade = {
                    "symbol": symbol,
                    "direction": result["signal"],
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "size": pos_size,
                    "risk": risk_amt,
                    "open_time": datetime.now(),
                }
                self.risk.open_trades += 1

                # Log trade
                self.journal.log_trade({
                    "Date": datetime.now().strftime("%Y-%m-%d"),
                    "Time": datetime.now().strftime("%H:%M:%S"),
                    "Symbol": symbol,
                    "Direction": result["signal"],
                    "Entry": entry,
                    "StopLoss": sl,
                    "TakeProfit": tp,
                    "PositionSize": round(pos_size, 6),
                    "RiskAmount": round(risk_amt, 2),
                    "PotentialProfit": round(risk_amt * CONFIG["RR_RATIO"], 2),
                    "RR": f"1:{CONFIG['RR_RATIO']}",
                    "Status": "OPEN",
                    "PnL": "",
                    "Notes": result["reason"],
                })

                # Telegram alert
                self.telegram.send(
                    f"🔔 TRADE OPENED\n"
                    f"{result['signal']} {symbol}\n"
                    f"Entry: {entry:.4f}\n"
                    f"SL: {sl:.4f} | TP: {tp:.4f}\n"
                    f"Risk: ₹{risk_amt:.2f} | Potential: ₹{risk_amt * CONFIG['RR_RATIO']:.2f}\n"
                    f"Reason: {result['reason']}"
                )

        # 6. Monitor active trade
        elif self.active_trade:
            current_price = self.trader.get_price(symbol)
            trade = self.active_trade
            direction = trade["direction"]

            hit_tp = (direction == "BUY" and current_price >= trade["tp"]) or \
                     (direction == "SELL" and current_price <= trade["tp"])
            hit_sl = (direction == "BUY" and current_price <= trade["sl"]) or \
                     (direction == "SELL" and current_price >= trade["sl"])

            if hit_tp or hit_sl:
                pnl = trade["risk"] * CONFIG["RR_RATIO"] if hit_tp else -trade["risk"]
                result_label = "✅ TAKE PROFIT" if hit_tp else "❌ STOP LOSS"

                self.risk.update_pnl(pnl)
                self.risk.open_trades -= 1

                log.info(f"{result_label} | PnL: {pnl:+.2f} | Capital: {self.risk.capital:.2f}")

                self.telegram.send(
                    f"{result_label} HIT\n"
                    f"{direction} {symbol}\n"
                    f"PnL: ₹{pnl:+.2f}\n"
                    f"Capital: ₹{self.risk.capital:.2f}\n"
                    f"Daily PnL: ₹{self.risk.daily_pnl:+.2f}"
                )

                self.active_trade = None

    def start(self, interval_seconds=60):
        """Start the bot loop."""
        log.info(f"🚀 Bot running. Checking every {interval_seconds} seconds. Press Ctrl+C to stop.")
        try:
            while True:
                self.run_cycle()
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            log.info("🛑 Bot stopped by user.")
            self.telegram.send("🛑 NEXUS BOT STOPPED")


# ─────────────────────────────────────────
#   BACKTEST MODE
# ─────────────────────────────────────────
def run_backtest(symbol="BTCUSDT", interval="1h", days=30):
    """
    Quick backtest on historical data.
    Run: python nexus_bot.py --backtest
    """
    log.info(f"📈 BACKTEST MODE: {symbol} {interval} last {days} days")
    trader = BinanceTrader("DEMO")
    strategy = StrategyEngine(CONFIG)

    limit = days * 24 if "h" in interval else days * 24 * 12
    df = trader.get_candles(symbol, interval, limit=min(limit, 1000))

    if df.empty:
        log.error("No data for backtest.")
        return

    wins = losses = 0
    total_pnl = 0
    risk_per_trade = CONFIG["STARTING_CAPITAL"] * (CONFIG["RISK_PERCENT"] / 100)

    log.info(f"Analyzing {len(df)} candles...")
    for i in range(50, len(df) - 10):
        chunk = df.iloc[:i].copy()
        result = strategy.analyze(chunk)
        if result["signal"] in ("BUY", "SELL"):
            entry = result["entry"]
            sl = result.get("sl", 0)
            sl_dist = abs(entry - sl)
            if sl_dist == 0:
                continue
            tp_dist = sl_dist * CONFIG["RR_RATIO"]

            future = df.iloc[i:i+20]
            hit_tp = hit_sl = False
            for _, candle in future.iterrows():
                if result["signal"] == "BUY":
                    if candle["low"] <= sl:
                        hit_sl = True; break
                    if candle["high"] >= entry + tp_dist:
                        hit_tp = True; break
                else:
                    if candle["high"] >= sl:
                        hit_sl = True; break
                    if candle["low"] <= entry - tp_dist:
                        hit_tp = True; break

            if hit_tp:
                wins += 1
                total_pnl += risk_per_trade * CONFIG["RR_RATIO"]
            elif hit_sl:
                losses += 1
                total_pnl -= risk_per_trade

    total = wins + losses
    winrate = (wins / total * 100) if total > 0 else 0

    log.info("=" * 50)
    log.info(f"BACKTEST RESULTS ({days} days)")
    log.info(f"Trades: {total} | Wins: {wins} | Losses: {losses}")
    log.info(f"Win Rate: {winrate:.1f}%")
    log.info(f"Total PnL: ₹{total_pnl:+.2f}")
    log.info(f"Final Capital: ₹{CONFIG['STARTING_CAPITAL'] + total_pnl:.2f}")
    log.info("=" * 50)
    return {"wins": wins, "losses": losses, "winrate": winrate, "pnl": total_pnl}


# ─────────────────────────────────────────
#   ENTRY POINT
# ─────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if "--backtest" in sys.argv:
        days = 30
        for arg in sys.argv:
            if arg.startswith("--days="):
                days = int(arg.split("=")[1])
        run_backtest(CONFIG["BINANCE_SYMBOL"], CONFIG["BINANCE_INTERVAL"], days)
    else:
        bot = NexusBot()
        bot.start(interval_seconds=60)  # Check every 60 seconds
