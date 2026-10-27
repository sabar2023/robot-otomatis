import os


def _load_env_file(path):
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)
    except FileNotFoundError:
        pass


_load_env_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

PRODUCT_NAME = "Robot Trading BrandBisnis"
TIMEFRAME_SCALP = "5m"
TIMEFRAME_HIGHER = "15m"
TIMEFRAME_LABEL = "M5"
TIMEFRAME_HIGHER_LABEL = "M15"
TIMEFRAME_SCALP_MINUTES = 5

EXCHANGE_ID = os.getenv("EXCHANGE_ID", "binance").strip().lower()
SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT").split(",") if s.strip()]
BTC_SYMBOL = "BTC/USDT"

BASE_CANDLE_COUNT = 300
HIGHER_CANDLE_COUNT = 100
SCAN_INTERVAL_MINUTES = 5
FRESH_CANDLE_MAX_AGE_MINUTES = 9.5

EMA_TREND_BASE = 200
EMA_TREND_HIGHER = 50
SWING_LOOKBACK = 20
SUPPORT_TOLERANCE_PCT = 0.5
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_STRONG = 50
RSI_OVERBOUGHT = 70
RSI_WEAK = 50
VOLUME_SMA_PERIOD = 20
ADX_PERIOD = 14
ADX_MIN = 20
BTC_FAR_BELOW_EMA_PCT = 2.0

ATR_PERIOD = 14
SL_PCT = float(os.getenv("SL_PCT", "2.5"))
TP_PCT = float(os.getenv("TP_PCT", "7.5"))
ENTRY_SPREAD_PCT = 0.1
RISK_PER_TRADE_PCT = 2.0
MAX_LEVERAGE = 10
MIN_LEVERAGE = 2

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
