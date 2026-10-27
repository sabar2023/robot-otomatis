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


_here = os.path.dirname(os.path.abspath(__file__))
_load_env_file(os.path.join(_here, ".env"))
_load_env_file(os.path.join(os.path.dirname(_here), ".env"))

PRODUCT_NAME = "Robot Trading BrandBisnis (M5 VST Edition)"
TIMEFRAME = "5m"
TIMEFRAME_LABEL = "M5"
TIMEFRAME_MINUTES = 5
SYMBOL = os.getenv("VST_SYMBOL", "BTC/USDT:USDT").strip()
CANDLE_LIMIT = 250
SCAN_INTERVAL_MINUTES = 5
FRESH_CANDLE_MAX_AGE_MINUTES = 9.5

EMA_TREND_PERIOD = 200
SWING_LOOKBACK = 20
SUPPORT_TOLERANCE_PCT = 0.2
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
VOLUME_SMA_PERIOD = 20
ADX_PERIOD = 14
ADX_MIN = 20

ATR_PERIOD = 14
SL_PCT = float(os.getenv("SL_PCT", "2.5"))
TP_PCT = float(os.getenv("TP_PCT", "7.5"))

POSITION_SIZE_USDT = float(os.getenv("VST_POSITION_SIZE_USDT", "100"))
LEVERAGE = int(os.getenv("VST_LEVERAGE", "10"))
MARGIN_COIN = os.getenv("VST_MARGIN_COIN", "VST")
EXECUTE_LIVE = os.getenv("VST_LIVE", "0").strip().lower() in ("1", "true", "yes", "on")

BINGX_API_KEY = os.getenv("BINGX_API_KEY", "").strip()
BINGX_SECRET_KEY = os.getenv("BINGX_SECRET_KEY", "").strip()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://jklbczruvbxscpwxxfud.supabase.co").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

DATA_EXCHANGES = [
    s.strip().lower()
    for s in os.getenv("VST_DATA_EXCHANGES", "bingx,bybit,kraken,gate,bitget,kucoin").split(",")
    if s.strip()
]
