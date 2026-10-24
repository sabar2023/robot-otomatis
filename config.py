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
TIMEFRAME_SCALP = "15m"
TIMEFRAME_HIGHER = "1h"

EXCHANGE_ID = os.getenv("EXCHANGE_ID", "binance").strip().lower()
SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT").split(",") if s.strip()]
BTC_SYMBOL = "BTC/USDT"

M15_CANDLE_COUNT = 300
H1_CANDLE_COUNT = 100
SCAN_INTERVAL_MINUTES = 5
FRESH_CANDLE_MAX_AGE_MINUTES = 4.5

EMA_TREND_M15 = 200
EMA_TREND_H1 = 50
SWING_LOOKBACK = 20
SUPPORT_TOLERANCE_PCT = 0.5
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_STRONG = 50
VOLUME_SMA_PERIOD = 20
ADX_PERIOD = 14
ADX_MIN = 20
BTC_FAR_BELOW_EMA_PCT = 2.0

ATR_PERIOD = 14
ATR_SL_MULT = 1.5
ATR_TP_MULT = 3.0
ENTRY_SPREAD_PCT = 0.1

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
