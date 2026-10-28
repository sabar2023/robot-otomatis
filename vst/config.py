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


def _timeframe_minutes(timeframe):
    multiplier = {"m": 1, "h": 60, "d": 1440, "w": 10080}[timeframe[-1]]
    return int(timeframe[:-1]) * multiplier


PRODUCT_NAME = "Robot Trading BrandBisnis (V5.0 H1 Multi-User)"
TIMEFRAME = os.getenv("VST_TIMEFRAME", "1h").strip()
TIMEFRAME_LABEL = TIMEFRAME.upper()
TIMEFRAME_MINUTES = _timeframe_minutes(TIMEFRAME)
SYMBOL = os.getenv("VST_SYMBOL", "BTC/USDT:USDT").strip()
CANDLE_LIMIT = 300
SCAN_INTERVAL_MINUTES = 60
FRESH_CANDLE_MAX_AGE_MINUTES = float(os.getenv("VST_FRESH_MAX_AGE_MINUTES", "90"))

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
ATR_SL_MULT = float(os.getenv("ATR_SL_MULT", "1.5"))
ATR_TP_MULT = float(os.getenv("ATR_TP_MULT", "4.0"))
SL_PCT_MIN = 1.0
SL_PCT_MAX = 5.0
TP_PCT_MIN = 3.0
TP_PCT_MAX = 12.0
SL_PCT_USER_MIN = 0.5
SL_PCT_USER_MAX = 20.0
TP_PCT_USER_MIN = 0.5
TP_PCT_USER_MAX = 50.0

LEVERAGE_MIN = 5
LEVERAGE_MAX = 10
LEVERAGE_DEFAULT = 10
EXEC_MODE = os.getenv("VST_EXEC_MODE", "demo").strip().lower()
MARGIN_PCT = float(os.getenv("VST_MARGIN_PCT", "10"))
MARGIN_COIN = os.getenv("VST_MARGIN_COIN", "USDT" if EXEC_MODE == "real" else "VST")
MIN_ORDER_USDT = float(os.getenv("VST_MIN_ORDER_USDT", "10"))
SIMULATED_NOTIONAL_USDT = float(os.getenv("VST_SIM_NOTIONAL_USDT", "100"))
EXECUTE_LIVE = os.getenv("VST_LIVE", "0").strip().lower() in ("1", "true", "yes", "on")

WATCHLIST_SIZE = int(os.getenv("VST_WATCHLIST_SIZE", "5"))

BINGX_API_KEY = os.getenv("BINGX_API_KEY", "").strip()
BINGX_SECRET_KEY = os.getenv("BINGX_SECRET_KEY", "").strip()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://jklbczruvbxscpwxxfud.supabase.co").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
SETTINGS_ENC_KEY = os.getenv("SETTINGS_ENC_KEY", "").strip()

DATA_EXCHANGES = [
    s.strip().lower()
    for s in os.getenv("VST_DATA_EXCHANGES", "bingx,bybit,kraken,gate,bitget,kucoin").split(",")
    if s.strip()
]
