# **PRD: Robot Trading BrandBisnis (M5 VST Edition)**

Dokumen Spesifikasi Produk (PRD) ini menggabungkan seluruh arsitektur sistem, logika strategi trading, protokol manajemen risiko, referensi kode Python eksekusi, serta otomatisasi CI/CD untuk Robot Trading BrandBisnis edisi Virtual Simulated Token (VST).

---

# **1\. Arsitektur Sistem (Serverless Hibrida)**

Sistem dirancang menggunakan pendekatan *serverless* terdistribusi untuk meminimalkan *overhead* biaya operasional dan menjaga reliabilitas eksekusi interval 5 menit.

| Komponen | Teknologi / Layanan | Fungsi Utama |
| :---- | :---- | :---- |
| **Mesin Eksekusi** | GitHub Actions | Menjalankan *cron job* otomatis setiap 5 menit untuk analisis teknikal dan eksekusi order. |
| **Bursa (Broker)** | BingX (Standard Futures) | Penyedia likuiditas pasar dan tempat eksekusi kontrak berjangka (*futures*). |
| **Mode Uji Coba** | Demo VST (`marginCoin: VST`) | Menggunakan saldo Virtual Simulated Token untuk pengujian strategi tanpa risiko finansial riil. |
| **Notifikasi** | Telegram Bot API | Mengirimkan log sinyal, eksekusi order, status transaksi, dan pesan *error* secara *real-time*. |
| **Database (Fase 2\)** | Supabase (PostgreSQL) | Menyimpan konfigurasi strategi, histori eksekusi, dan status *stateful* toggle Auto/Manual. |
| **Dashboard (Fase 2\)** | Flutter Web (Cloudflare Pages) | Antarmuka pengguna (*clean flat light theme*) untuk pemantauan performa dan manajemen bot. |

---

# **2\. Strategi Trading (Symmetrical M5 Scalping)**

* **Timeframe:** 5 Menit (M5)  
* **Sifat Eksekusi:** Dua arah (*Simetris*: Berpeluang untuk posisi LONG maupun SHORT)  
* **Aturan Sinyal:** Seluruh 5 lapisan filter wajib bernilai `TRUE` secara bersamaan sebelum posisi dibuka.

## **5 Lapisan Filter Sinyal Wajib**

1. **Tren Utama (EMA-200):**  
   * **LONG:** Harga penutupan (*Close Price*) \> EMA-200.  
   * **SHORT:** Harga penutupan (*Close Price*) \< EMA-200.  
2. **Support & Resistance Dinamis (Swing 20 Period):**  
   * Mengalkulasi *Swing High* dan *Swing Low* berdasarkan 20 *candle* terakhir.  
   * **LONG:** Harga berada di area Support dinamis (mendekati/menyentuh *Swing Low*).  
   * **SHORT:** Harga berada di area Resistance dinamis (mendekati/menyentuh *Swing High*).  
3. **Momentum Divergence / Crossover (RSI 14):**  
   * **LONG:** RSI (14) memotong ke atas (*crosses above*) dari zona *Oversold* (\< 30).  
   * **SHORT:** RSI (14) memotong ke bawah (*crosses below*) dari zona *Overbought* (\> 70).  
4. **Validasi Volume:**  
   * Volume *candle* sinyal saat ini harus lebih besar dari rata-rata pergerakan volume 20 periode.  
   * Aturan: `Volume > SMA(Volume, 20)`.  
5. **Filter Anti-Sideways (ADX 14):**  
   * Mengukur kekuatan tren untuk mengeliminasi sinyal palsu pada kondisi pasar *choppy* atau konsolidasi.  
   * Aturan: `ADX(14) > 20`.

---

# **3\. Protokol Manajemen Risiko**

* **Bracket Order (OVO / OCO):** Setiap pembukaan posisi wajib disertai dengan nilai Stop Loss (SL) dan Take Profit (TP) secara langsung dalam satu paket permintaan order ke *exchange*.  
* **Penentuan Jarak Dinamis (ATR 14):**  
  * Menggunakan indikator *Average True Range* (ATR) periode 14 untuk memastikan batasan risiko beradaptasi terhadap volatilitas pasar terkini.  
  * **Jarak Stop Loss (SL):** \$1.5 \\times \\text{ATR}(14)\$  
  * **Jarak Take Profit (TP):** \$3.0 \\times \\text{ATR}(14)\$  
  * **Risk-to-Reward Ratio (RRR):** Minimum \$1 : 2\$

---

# **4\. Script Python (`bot_sinyal_m5.py`)**

Kode di bawah ini merupakan fondasi eksekusi penuh yang membaca data pasar BingX VST, mengkalkulasi kelima filter indikator, mengevaluasi kondisi *entry*, dan mengeksekusi *bracket order* jika kriteria terpenuhi.import os

import requests

import pandas as pd

import pandas\_ta as ta

import ccxt

\# \==========================================

\# KONFIGURASI LINGKUNGAN & PARAMETER

\# \==========================================

API\_KEY \= os.getenv("BINGX\_API\_KEY")

SECRET\_KEY \= os.getenv("BINGX\_SECRET\_KEY")

TELEGRAM\_BOT\_TOKEN \= os.getenv("TELEGRAM\_BOT\_TOKEN")

TELEGRAM\_CHAT\_ID \= os.getenv("TELEGRAM\_CHAT\_ID")

SYMBOL \= "BTC/USDT:USDT"

TIMEFRAME \= "5m"

LIMIT \= 250

POSITION\_SIZE\_USDT \= 100  \# Size posisi standar dalam nominal VST/USDT

LEVERAGE \= 10

\# \==========================================

\# INISIALISASI BINGX VIA CCXT

\# \==========================================

exchange \= ccxt.bingx({

    "apiKey": API\_KEY,

    "secret": SECRET\_KEY,

    "enableRateLimit": True,

    "options": {

        "defaultType": "swap",  \# Futures Standard / Perpetual

    }

})

def send\_telegram\_message(message: str):

    """Mengirimkan pesan format Markdown ke Telegram."""

    if not TELEGRAM\_BOT\_TOKEN or not TELEGRAM\_CHAT\_ID:

        print("Telegram Credentials tidak ditemukan. Menyeberangi pengiriman pesan.")

        return

    

    url \= f"https\://api.telegram.org/bot{TELEGRAM\_BOT\_TOKEN}/sendMessage"

    payload \= {

        "chat\_id": TELEGRAM\_CHAT\_ID,

        "text": message,

        "parse\_mode": "Markdown"

    }

    try:

        requests.post(url, json=payload, timeout=10)

    except Exception as e:

        print(f"Gagal mengirim pesan Telegram: {e}")

def fetch\_market\_data() \-\> pd.DataFrame:

    """Mengambil data OHLCV dari BingX dan menghitung indikator teknikal."""

    ohlcv \= exchange.fetch\_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=LIMIT)

    df \= pd.DataFrame(ohlcv, columns=\['timestamp', 'open', 'high', 'low', 'close', 'volume'\])

    df\['timestamp'\] \= pd.to\_datetime(df\['timestamp'\], unit='ms')

    \# Indikator 1: EMA-200

    df\['ema200'\] \= ta.ema(df\['close'\], length=200)

    \# Indikator 2: Support & Resistance Dinamis (Swing 20\)

    df\['swing\_high'\] \= df\['high'\].rolling(window=20).max()

    df\['swing\_low'\] \= df\['low'\].rolling(window=20).min()

    \# Indikator 3: RSI (14)

    df\['rsi'\] \= ta.rsi(df\['close'\], length=14)

    \# Indikator 4: Volume SMA (20)

    df\['vol\_sma'\] \= ta.sma(df\['volume'\], length=20)

    \# Indikator 5: ADX (14)

    adx\_df \= ta.adx(df\['high'\], df\['low'\], df\['close'\], length=14)

    df\['adx'\] \= adx\_df\['ADX\_14'\]

    \# Manajemen Risiko: ATR (14)

    df\['atr'\] \= ta.atr(df\['high'\], df\['low'\], df\['close'\], length=14)

    return df

def check\_signal(df: pd.DataFrame) \-\> str:

    """Mengevaluasi 5 lapisan filter sinyal trading."""

    curr \= df.iloc\[-1\]

    prev \= df.iloc\[-2\]

    \# Evaluasi Filter

    c\_ema \= curr\['close'\] \> curr\['ema200'\]

    c\_adx \= curr\['adx'\] \> 20

    c\_vol \= curr\['volume'\] \> curr\['vol\_sma'\]

    \# Filter LONG

    rsi\_long\_cross \= (prev\['rsi'\] \< 30\) and (curr\['rsi'\] \>= 30\)

    near\_support \= curr\['close'\] \<= (curr\['swing\_low'\] \* 1.002)

    is\_long \= c\_ema and c\_adx and c\_vol and rsi\_long\_cross and near\_support

    \# Filter SHORT

    c\_ema\_short \= curr\['close'\] \< curr\['ema200'\]

    rsi\_short\_cross \= (prev\['rsi'\] \> 70\) and (curr\['rsi'\] \<= 70\)

    near\_resistance \= curr\['close'\] \>= (curr\['swing\_high'\] \* 0.998)

    is\_short \= c\_ema\_short and c\_adx and c\_vol and rsi\_short\_cross and near\_resistance

    if is\_long:

        return "LONG"

    elif is\_short:

        return "SHORT"

    return "NEUTRAL"

def execute\_order(signal: str, df: pd.DataFrame):

    """Mengeksekusi order pasar VST BingX dilengkapi Stop Loss & Take Profit."""

    curr \= df.iloc\[-1\]

    close\_price \= curr\['close'\]

    atr\_value \= curr\['atr'\]

    \# Mengatur Leverage

    try:

        exchange.set\_leverage(LEVERAGE, SYMBOL, params={"marginCoin": "VST"})

    except Exception as e:

        print(f"Log Info Leverage: {e}")

    \# Kalkulasi Ukuran Posisi dan Jarak SL/TP

    amount \= POSITION\_SIZE\_USDT / close\_price

    sl\_distance \= 1.5 \* atr\_value

    tp\_distance \= 3.0 \* atr\_value

    if signal \== "LONG":

        sl\_price \= close\_price \- sl\_distance

        tp\_price \= close\_price \+ tp\_distance

        side \= "buy"

    elif signal \== "SHORT":

        sl\_price \= close\_price \+ sl\_distance

        tp\_price \= close\_price \- tp\_distance

        side \= "sell"

    else:

        return

    params \= {

        "marginCoin": "VST",

        "stopLoss": {

            "triggerPrice": round(sl\_price, 2),

            "type": "market"

        },

        "takeProfit": {

            "triggerPrice": round(tp\_price, 2),

            "type": "market"

        }

    }

    try:

        order \= exchange.create\_order(

            symbol=SYMBOL,

            type="market",

            side=side,

            amount=amount,

            params=params

        )

        msg \= (

            f"🚀 \*SINYAL TERDETEKSI & DIEKSEKUSI (VST)\*\\n\\n"

            f"\*Simbol:\* \`{SYMBOL}\`\\n"

            f"\*Arah:\* \`{signal}\`\\n"

            f"\*Harga Masuk:\* \`{close\_price:.2f}\`\\n"

            f"\*Stop Loss:\* \`{sl\_price:.2f}\` (1.5x ATR)\\n"

            f"\*Take Profit:\* \`{tp\_price:.2f}\` (3.0x ATR)\\n"

            f"\*Leverage:\* \`{LEVERAGE}x\`"

        )

        send\_telegram\_message(msg)

        print("Order berhasil dieksekusi:", order)

    except Exception as e:

        err\_msg \= f"❌ \*GAGAL EKSEKUSI ORDER\*\\n\\nError: \`{str(e)}\`"

        send\_telegram\_message(err\_msg)

        print("Error eksekusi order:", e)

def main():

    print("Mulai menganalisis pasar...")

    try:

        df \= fetch\_market\_data()

        signal \= check\_signal(df)

        print(f"Status Sinyal Saat Ini: {signal}")

        if signal in \["LONG", "SHORT"\]:

            execute\_order(signal, df)

        else:

            print("Tidak ada sinyal yang memenuhi 5 syarat filter.")

    except Exception as e:

        print(f"Terjadi kesalahan pada loop utama: {e}")

if \_\_name\_\_ \== "\_\_main\_\_":

    main()

---

# **5\. Deployment Github Actions (`cron.yml`)**

File konfigurasi ini diletakkan pada direktori .github/workflows/cron.yml untuk menjalankan bot secara terjadwal setiap 5 menit menggunakan infrastruktur GitHub Actions.l  
name: M5 Scalper Bot Execution

on:  
schedule:  
\# Menjalankan skrip setiap interval 5 menit  
\- cron: '\*/5 \* \* \* \*'  
workflow\_dispatch:

jobs:  
run-trading-bot:  
runs-on: ubuntu-lateststeps:

  \- name: Checkout Repository

    uses: actions/checkout@v3

  \- name: Setup Python Environment

    uses: actions/setup-python@v4

    with:

      python-version: '3.10'

  \- name: Cache Python Dependencies

    uses: actions/cache@v3

    with:

      path: \~/.cache/pip

      key: \${{ runner.os }}-pip-\${{ hashFiles('\*\*/requirements.txt') }}

      restore-keys: \|

        \${{ runner.os }}-pip-

  \- name: Install Dependencies

    run: \|

      python \-m pip install \--upgrade pip

      pip install ccxt pandas pandas-ta requests

  \- name: Execute Trading Engine

    env:

      BINGX\_API\_KEY: \${{ secrets.BINGX\_API\_KEY }}

      BINGX\_SECRET\_KEY: \${{ secrets.BINGX\_SECRET\_KEY }}

      TELEGRAM\_BOT\_TOKEN: \${{ secrets.TELEGRAM\_BOT\_TOKEN }}

      TELEGRAM\_CHAT\_ID: \${{ secrets.TELEGRAM\_CHAT\_ID }}

    run: \|

      python bot\_sinyal\_m5.py  
