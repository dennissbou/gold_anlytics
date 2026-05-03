"""
Data Collector — reads all DB sources, computes TA indicators,
and returns a structured context dict ready for the article generator.
"""

import psycopg2
import pandas as pd
import os
from datetime import date, timedelta
from dotenv import load_dotenv

import ta

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "gold_analytics"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


# ─── helpers ────────────────────────────────────────────────────────────────

def pct_change(current, previous) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / previous * 100, 2)


def trend_label(current, sma20, sma50, sma200) -> str:
    if current > sma200 and sma20 > sma50:
        return "strong uptrend"
    elif current > sma200:
        return "uptrend"
    elif current < sma200 and sma20 < sma50:
        return "strong downtrend"
    elif current < sma200:
        return "downtrend"
    return "sideways"


# ─── gold prices + technical analysis ───────────────────────────────────────

def collect_gold_technicals(conn) -> dict:
    df = pd.read_sql(
        "SELECT timestamp, open, high, low, close, volume "
        "FROM gold_prices.gold_prices_1d ORDER BY timestamp ASC",
        conn
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")

    # Moving averages
    df["sma20"]  = ta.trend.sma_indicator(df["close"], window=20)
    df["sma50"]  = ta.trend.sma_indicator(df["close"], window=50)
    df["sma200"] = ta.trend.sma_indicator(df["close"], window=200)

    # RSI
    df["rsi"] = ta.momentum.rsi(df["close"], window=14)

    # MACD
    macd = ta.trend.MACD(df["close"])
    df["macd"]        = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"]   = macd.macd_diff()

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_mid"]   = bb.bollinger_mavg()

    # ATR
    df["atr"] = ta.volatility.average_true_range(df["high"], df["low"], df["close"], window=14)

    latest = df.iloc[-1]
    prev_week  = df.iloc[-6] if len(df) >= 6 else df.iloc[0]
    prev_month = df.iloc[-22] if len(df) >= 22 else df.iloc[0]
    prev_year  = df.iloc[-252] if len(df) >= 252 else df.iloc[0]

    # Key S/R levels — recent 20-day swing highs and lows
    recent = df.iloc[-60:]
    resistance = round(float(recent["high"].max()), 1)
    support    = round(float(recent["low"].min()), 1)
    # Intermediate levels
    r2 = round(float(df.iloc[-20]["high"].max() if hasattr(df.iloc[-20]["high"], "max") else recent["high"].nlargest(5).iloc[-1]), 1)
    s2 = round(float(recent["low"].nsmallest(5).iloc[-1]), 1)

    price = round(float(latest["close"]), 1)

    return {
        "price": {
            "current":       price,
            "week_change_pct":  pct_change(price, float(prev_week["close"])),
            "month_change_pct": pct_change(price, float(prev_month["close"])),
            "year_change_pct":  pct_change(price, float(prev_year["close"])),
            "high_52w":      round(float(df.iloc[-252:]["high"].max()), 1),
            "low_52w":       round(float(df.iloc[-252:]["low"].min()), 1),
        },
        "trend": trend_label(
            price,
            float(latest["sma20"]),
            float(latest["sma50"]),
            float(latest["sma200"]),
        ),
        "moving_averages": {
            "sma20":  round(float(latest["sma20"]), 1),
            "sma50":  round(float(latest["sma50"]), 1),
            "sma200": round(float(latest["sma200"]), 1),
        },
        "indicators": {
            "rsi":         round(float(latest["rsi"]), 1),
            "macd":        round(float(latest["macd"]), 2),
            "macd_signal": round(float(latest["macd_signal"]), 2),
            "macd_hist":   round(float(latest["macd_hist"]), 2),
            "atr":         round(float(latest["atr"]), 1),
        },
        "bollinger_bands": {
            "upper": round(float(latest["bb_upper"]), 1),
            "mid":   round(float(latest["bb_mid"]), 1),
            "lower": round(float(latest["bb_lower"]), 1),
        },
        "levels": {
            "resistance":  resistance,
            "support":     support,
        },
    }


# ─── correlated assets ───────────────────────────────────────────────────────

def collect_correlated(conn) -> dict:
    df = pd.read_sql(
        "SELECT timestamp, symbol, close FROM correlated_assets.prices_1d "
        "ORDER BY timestamp ASC",
        conn
    )
    result = {}
    for symbol in df["symbol"].unique():
        s = df[df["symbol"] == symbol].set_index("timestamp")["close"]
        if len(s) < 2:
            continue
        current  = round(float(s.iloc[-1]), 4)
        prev_week = round(float(s.iloc[-6]), 4) if len(s) >= 6 else None
        prev_month = round(float(s.iloc[-22]), 4) if len(s) >= 22 else None
        result[symbol] = {
            "current":          current,
            "week_change_pct":  pct_change(current, prev_week),
            "month_change_pct": pct_change(current, prev_month),
        }
    return result


# ─── COT positioning ─────────────────────────────────────────────────────────

def collect_cot(conn) -> dict:
    df = pd.read_sql(
        "SELECT report_date, noncomm_net, comm_net, open_interest "
        "FROM cot_report.gold_futures ORDER BY report_date ASC",
        conn
    )
    if df.empty:
        return {}
    latest = df.iloc[-1]
    prev   = df.iloc[-5] if len(df) >= 5 else df.iloc[0]
    return {
        "report_date":      str(latest["report_date"]),
        "noncomm_net":      int(latest["noncomm_net"]),
        "noncomm_net_prev": int(prev["noncomm_net"]),
        "noncomm_change":   int(latest["noncomm_net"]) - int(prev["noncomm_net"]),
        "comm_net":         int(latest["comm_net"]),
        "open_interest":    int(latest["open_interest"]),
        "bias": "bullish" if latest["noncomm_net"] > 0 else "bearish",
    }


# ─── ETF flows ───────────────────────────────────────────────────────────────

def collect_etf_flows(conn) -> dict:
    h = pd.read_sql(
        "SELECT month, total, gold_price_usd FROM etf_flows.holdings_monthly "
        "ORDER BY month ASC",
        conn
    )
    f = pd.read_sql(
        "SELECT month, total FROM etf_flows.flows_monthly ORDER BY month ASC",
        conn
    )
    if h.empty:
        return {}
    latest_h = h.iloc[-1]
    prev_h   = h.iloc[-2] if len(h) >= 2 else h.iloc[0]
    latest_f = f.iloc[-1] if not f.empty else None

    return {
        "month":              str(latest_h["month"]),
        "total_tonnes":       round(float(latest_h["total"]), 1),
        "month_change_t":     round(float(latest_h["total"]) - float(prev_h["total"]), 1),
        "monthly_flow_usd":   round(float(latest_f["total"]), 0) if latest_f is not None else None,
        "flow_bias":          "inflow" if (float(latest_h["total"]) - float(prev_h["total"])) > 0 else "outflow",
    }


# ─── Fed / macro rates ────────────────────────────────────────────────────────

def collect_fed_rates(conn) -> dict:
    series_ids = {
        "FEDFUNDS": "fed_funds_rate",
        "CPIAUCSL": "cpi",
        "GS10":     "yield_10y",
        "GS2":      "yield_2y",
        "T10Y2Y":   "yield_spread_10y2y",
        "DFII10":   "real_rate_10y",
    }
    result = {}
    for sid, label in series_ids.items():
        df = pd.read_sql(
            "SELECT date, value FROM fed_rates.observations "
            "WHERE series_id = %s ORDER BY date ASC",
            conn, params=(sid,)
        )
        if df.empty:
            continue
        latest    = float(df.iloc[-1]["value"])
        prev      = float(df.iloc[-2]["value"]) if len(df) >= 2 else None
        prev_year = float(df.iloc[-13]["value"]) if len(df) >= 13 else None
        entry = {
            "current":          round(latest, 3),
            "prev":             round(prev, 3) if prev else None,
            "change":           round(latest - prev, 3) if prev else None,
            "year_ago":         round(prev_year, 3) if prev_year else None,
        }
        # CPIAUCSL is an index level (~330), not a rate — pre-compute YoY %
        if label == "cpi" and prev_year is not None:
            entry["yoy_pct"] = round((latest - prev_year) / prev_year * 100, 2)
        result[label] = entry
    return result


# ─── economic calendar ────────────────────────────────────────────────────────

def collect_calendar(conn) -> dict:
    today = date.today()
    next_month = today + timedelta(days=30)
    last_month = today - timedelta(days=30)

    upcoming = pd.read_sql(
        "SELECT event_date, event_name, forecast, actual FROM economic_calendar.events "
        "WHERE event_date >= %s AND event_date <= %s "
        "ORDER BY event_date ASC",
        conn, params=(today, next_month)
    )

    recent = pd.read_sql(
        "SELECT event_date, event_name, actual, previous FROM economic_calendar.events "
        "WHERE event_date >= %s AND event_date < %s AND actual IS NOT NULL "
        "ORDER BY event_date DESC LIMIT 6",
        conn, params=(last_month, today)
    )

    return {
        "upcoming": [
            {
                "date":      str(row["event_date"]),
                "event":     row["event_name"],
                "forecast":  row["forecast"],
            }
            for _, row in upcoming.iterrows()
        ],
        "recent_releases": [
            {
                "date":     str(row["event_date"]),
                "event":    row["event_name"],
                "actual":   row["actual"],
                "previous": row["previous"],
            }
            for _, row in recent.iterrows()
        ],
    }


# ─── news ────────────────────────────────────────────────────────────────────

def collect_news(conn) -> list[dict]:
    df = pd.read_sql(
        "SELECT published_at, title, summary, source FROM news.articles "
        "ORDER BY published_at DESC LIMIT 20",
        conn
    )
    return [
        {
            "date":    str(row["published_at"])[:10],
            "title":   row["title"],
            "summary": row["summary"],
            "source":  row["source"],
        }
        for _, row in df.iterrows()
    ]


# ─── central bank ─────────────────────────────────────────────────────────────

def collect_central_bank(conn) -> dict:
    df = pd.read_sql(
        "SELECT month, country, tonnes FROM central_bank.gold_reserves "
        "ORDER BY month ASC",
        conn
    )
    if df.empty:
        return {}
    latest_month = df["month"].max()
    latest = df[df["month"] == latest_month].set_index("country")["tonnes"].to_dict()
    total  = round(sum(latest.values()), 1)
    return {
        "as_of":        str(latest_month),
        "total_top10t": total,
        "holdings":     {k: round(float(v), 1) for k, v in sorted(latest.items(), key=lambda x: -x[1])},
    }


# ─── main ─────────────────────────────────────────────────────────────────────

def collect_all() -> dict:
    conn = get_conn()
    try:
        print("Collecting data...")
        context = {
            "generated_at":   str(date.today()),
            "gold":           collect_gold_technicals(conn),
            "correlated":     collect_correlated(conn),
            "cot":            collect_cot(conn),
            "etf_flows":      collect_etf_flows(conn),
            "fed_rates":      collect_fed_rates(conn),
            "calendar":       collect_calendar(conn),
            "news":           collect_news(conn),
            "central_bank":   collect_central_bank(conn),
        }
        print("  Done.")
        return context
    finally:
        conn.close()


if __name__ == "__main__":
    import json
    context = collect_all()
    print(json.dumps(context, indent=2, default=str))
