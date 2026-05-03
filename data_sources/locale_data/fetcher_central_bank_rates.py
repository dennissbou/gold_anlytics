"""
Fetches central bank policy rates using each country's official API.

Sources:
  US     → FRED (FEDFUNDS)                — requires FRED_API_KEY in .env
  BR     → BCB SGS series 432 (SELIC)     — no auth
  MX     → Banxico SIE SF61745            — token in config.json ["banxico"]["token"]
  PE     → BCRP series PD04736PD          — no auth
  AR/CL/CO → BIS WS_CBPOL monthly series — no auth (AR lags ~11 months)
  CR/KZ/UY → no reliable free API; stored as null
  PA     → dollarized; mirrors US rate

Token behaviour:
  If the Banxico token is expired or invalid the fetcher logs a warning and
  stores null for MX — it does NOT abort. Update the token in config.json and
  re-run to get a fresh value.
"""

import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"

def _load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "127.0.0.1"),
    "port":     os.getenv("DB_PORT", "5432"),
    "dbname":   os.getenv("DB_NAME", "gold_analytics"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
}

FRED_API_KEY      = os.getenv("FRED_API_KEY")
REQUEST_TIMEOUT   = 15
REFRESH_INTERVAL  = 3   # days — skip run if all rows are fresher than this

# Static locale metadata (countries with no working API keep series=None)
LOCALES = {
    "en": {"iso2": "US",  "bank": "Federal Reserve"},
    "ar": {"iso2": "AR",  "bank": "Banco Central de la República Argentina"},
    "br": {"iso2": "BR",  "bank": "Banco Central do Brasil"},
    "cl": {"iso2": "CL",  "bank": "Banco Central de Chile"},
    "co": {"iso2": "CO",  "bank": "Banco de la República de Colombia"},
    "cr": {"iso2": "CR",  "bank": "Banco Central de Costa Rica"},
    "kz": {"iso2": "KZ",  "bank": "Национальный Банк Казахстана"},
    "mx": {"iso2": "MX",  "bank": "Banco de México"},
    "pa": {"iso2": "PA",  "bank": "Federal Reserve (dollarized)"},
    "pe": {"iso2": "PE",  "bank": "Banco Central de Reserva del Perú"},
    "uy": {"iso2": "UY",  "bank": "Banco Central del Uruguay"},
}


# ── Source fetchers ───────────────────────────────────────────────────────────

def fetch_fred(series_id: str) -> tuple[float | None, float | None, str | None]:
    """Fetch latest two observations from FRED."""
    if not FRED_API_KEY:
        print("  [WARN] FRED_API_KEY not set — skipping US rate")
        return None, None, None
    try:
        r = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id":  series_id,
                "sort_order": "desc",
                "limit":      5,
                "api_key":    FRED_API_KEY,
                "file_type":  "json",
            },
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        valid = [
            o for o in r.json().get("observations", [])
            if o.get("value") not in (".", "", None)
        ]
        if not valid:
            return None, None, None
        current  = float(valid[0]["value"])
        previous = float(valid[1]["value"]) if len(valid) > 1 else None
        return current, previous, valid[0]["date"]
    except Exception as e:
        print(f"  [WARN] FRED {series_id}: {e}")
        return None, None, None


def fetch_bcb() -> tuple[float | None, float | None, str | None]:
    """Brazil — BCB SGS series 432 (SELIC target rate). No auth required."""
    try:
        r = requests.get(
            "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/2",
            params={"formato": "json"},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            return None, None, None
        # BCB returns list ordered oldest→newest
        current  = float(data[-1]["valor"])
        previous = float(data[-2]["valor"]) if len(data) > 1 else None
        # date format: DD/MM/YYYY → convert to YYYY-MM-DD
        raw_date = data[-1]["data"]
        d, m, y  = raw_date.split("/")
        rate_date = f"{y}-{m}-{d}"
        return current, previous, rate_date
    except Exception as e:
        print(f"  [WARN] BCB (BR): {e}")
        return None, None, None


def fetch_banxico(token: str) -> tuple[float | None, float | None, str | None]:
    """Mexico — Banxico SIE SF61745 (overnight interbank rate / objetivo).
    Returns (None, None, None) if the token is expired or invalid — does NOT raise.
    """
    if not token:
        print("  [WARN] Banxico token not configured in config.json — skipping MX rate")
        return None, None, None
    try:
        r = requests.get(
            "https://www.banxico.org.mx/SieAPIRest/service/v1/series/SF61745/datos/oportuno",
            headers={"Bmx-Token": token},
            timeout=REQUEST_TIMEOUT,
        )
        body = r.json()

        # Detect expired / invalid token
        error = body.get("bmx", {}).get("error")
        if error:
            code = error.get("error_code", "?")
            msg  = error.get("error_msg", "unknown error")
            print(f"  [WARN] Banxico token error ({code}): {msg}")
            print("         Update config.json [\"banxico\"][\"token\"] and re-run.")
            return None, None, None

        series = body.get("bmx", {}).get("series", [])
        if not series:
            return None, None, None
        datos = series[0].get("datos", [])
        if not datos:
            return None, None, None

        current   = float(datos[-1]["dato"])
        previous  = float(datos[-2]["dato"]) if len(datos) > 1 else None
        # date format: DD/MM/YYYY
        raw_date  = datos[-1]["fecha"]
        d, m, y   = raw_date.split("/")
        rate_date = f"{y}-{m}-{d}"
        return current, previous, rate_date
    except Exception as e:
        print(f"  [WARN] Banxico (MX): {e}")
        return None, None, None


_BCRP_MONTHS = {
    "Ene": "01", "Feb": "02", "Mar": "03", "Abr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Ago": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dic": "12",
}

def _parse_bcrp_date(raw: str) -> str | None:
    """Convert BCRP date labels like 'Abr.25' or 'Dic.2021' to YYYY-MM-DD."""
    try:
        parts = raw.split(".")
        month_str = parts[0].strip()
        year_str  = parts[1].strip()
        month = _BCRP_MONTHS.get(month_str)
        if not month:
            return None
        year = int(year_str) if len(year_str) == 4 else 2000 + int(year_str)
        return f"{year}-{month}-01"
    except Exception:
        return None


def fetch_bcrp() -> tuple[float | None, float | None, str | None]:
    """Peru — BCRP reference rate (Tasa de referencia). No auth required.
    Series PD04736PD = daily overnight reference rate.
    Falls back gracefully if the series is unavailable or returns bad data.
    Rate sanity check: must be between 0 and 50% to be a valid policy rate.
    """
    try:
        r = requests.get(
            "https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD04736PD/json",
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        periods = data.get("periods", [])
        valid = [
            p for p in periods
            if p.get("values") and p["values"][0] not in ("n.d.", "", None)
        ]
        if not valid:
            return None, None, None
        current  = float(valid[-1]["values"][0])
        previous = float(valid[-2]["values"][0]) if len(valid) > 1 else None

        # Sanity check — reject if value looks like an index / inflation series
        if current > 50:
            print(f"  [WARN] BCRP returned suspicious rate {current}% — skipping PE")
            return None, None, None

        rate_date = _parse_bcrp_date(valid[-1].get("name", ""))
        return current, previous, rate_date
    except Exception as e:
        print(f"  [WARN] BCRP (PE): {e}")
        return None, None, None


_BIS_COUNTRIES = ["AR", "CL", "CO"]
_BIS_ISO2_TO_LOCALE = {"AR": "ar", "CL": "cl", "CO": "co"}

def fetch_bis() -> dict[str, tuple[float | None, float | None, str | None]]:
    """Fetch policy rates from BIS WS_CBPOL for AR, CL, CO. No auth required.
    Returns dict keyed by ISO2 → (current_rate, previous_rate, date_str).
    AR typically lags ~11 months; CL and CO are usually current to within 5 weeks.
    """
    result: dict[str, tuple[float | None, float | None, str | None]] = {
        c: (None, None, None) for c in _BIS_COUNTRIES
    }
    start = (date.today().replace(day=1) - timedelta(days=395)).strftime("%Y-%m-%d")
    key = "+".join(_BIS_COUNTRIES)
    try:
        r = requests.get(
            f"https://stats.bis.org/api/v1/data/WS_CBPOL/M.{key}",
            params={"startPeriod": start, "detail": "dataonly"},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        root = ET.fromstring(r.text)
        for elem in root.iter():
            if elem.tag.split("}")[-1] != "Series":
                continue
            iso2 = elem.get("REF_AREA")
            if iso2 not in _BIS_COUNTRIES:
                continue
            obs = [c for c in elem if c.tag.split("}")[-1] == "Obs"]
            if not obs:
                continue
            current  = float(obs[-1].get("OBS_VALUE"))
            previous = float(obs[-2].get("OBS_VALUE")) if len(obs) > 1 else None
            # BIS period format: YYYY-MM → use first day of month
            rate_date = obs[-1].get("TIME_PERIOD", "") + "-01"
            result[iso2] = (current, previous, rate_date)
            print(f"  BIS {iso2}: {current}% ({rate_date})")
    except Exception as e:
        print(f"  [WARN] BIS WS_CBPOL: {e}")
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def compute_trend(current: float | None, previous: float | None) -> str | None:
    if current is None or previous is None:
        return None
    diff = round(current - previous, 4)
    if diff > 0.01:
        return "hiking"
    if diff < -0.01:
        return "cutting"
    return "holding"


_SOURCED_LOCALES = {"en", "br", "mx", "pe", "ar", "cl", "co", "pa"}

def is_fresh(conn) -> bool:
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*), MIN(updated_at),
               COUNT(*) FILTER (WHERE policy_rate IS NULL AND locale = ANY(%s))
        FROM locale_data.central_bank_rates
    """, (list(_SOURCED_LOCALES),))
    count, oldest, missing = cur.fetchone()
    cur.close()
    if count < len(LOCALES) or missing > 0:
        return False
    if oldest is None:
        return False
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)
    return oldest >= datetime.now(timezone.utc) - timedelta(days=REFRESH_INTERVAL)


def save_to_db(conn, records: list[dict]) -> int:
    cur = conn.cursor()
    upserted = 0
    for r in records:
        cur.execute(
            """
            INSERT INTO locale_data.central_bank_rates
                (locale, iso2, bank_name, source, policy_rate, previous_rate,
                 rate_change, rate_trend, rate_date, updated_at)
            VALUES
                (%(locale)s, %(iso2)s, %(bank_name)s, %(source)s,
                 %(policy_rate)s, %(previous_rate)s, %(rate_change)s,
                 %(rate_trend)s, %(rate_date)s, CURRENT_TIMESTAMP)
            ON CONFLICT (locale) DO UPDATE SET
                policy_rate   = EXCLUDED.policy_rate,
                previous_rate = EXCLUDED.previous_rate,
                rate_change   = EXCLUDED.rate_change,
                rate_trend    = EXCLUDED.rate_trend,
                rate_date     = EXCLUDED.rate_date,
                source        = EXCLUDED.source,
                updated_at    = CURRENT_TIMESTAMP
            """,
            r,
        )
        upserted += cur.rowcount
    conn.commit()
    cur.close()
    return upserted


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    config = _load_config()
    banxico_token = config.get("banxico", {}).get("token", "")

    conn = psycopg2.connect(**DB_CONFIG)

    if is_fresh(conn):
        print(f"Central bank rates are fresh (within {REFRESH_INTERVAL}d) — skipping")
        conn.close()
        raise SystemExit(0)

    print("Fetching central bank policy rates...")

    # Fetch all sources
    us_rate,  us_prev,  us_date  = fetch_fred("FEDFUNDS")
    br_rate,  br_prev,  br_date  = fetch_bcb()
    mx_rate,  mx_prev,  mx_date  = fetch_banxico(banxico_token)
    pe_rate,  pe_prev,  pe_date  = fetch_bcrp()
    bis = fetch_bis()  # AR, CL, CO

    source_data = {
        "en": (us_rate,  us_prev,  us_date,  "fred"),
        "br": (br_rate,  br_prev,  br_date,  "bcb"),
        "mx": (mx_rate,  mx_prev,  mx_date,  "banxico"),
        "pe": (pe_rate,  pe_prev,  pe_date,  "bcrp"),
        "ar": (*bis["AR"], "bis"),
        "cl": (*bis["CL"], "bis"),
        "co": (*bis["CO"], "bis"),
        # No reliable free API for the remaining locales
        "cr": (None, None, None, None),
        "kz": (None, None, None, None),
        # Panama is dollarized — mirrors US rate
        "pa": (us_rate, us_prev, us_date, "fred"),
        "uy": (None, None, None, None),
    }

    records = []
    for locale, meta in LOCALES.items():
        rate, prev, date_str, source = source_data[locale]
        trend       = compute_trend(rate, prev)
        rate_change = round(rate - prev, 4) if rate is not None and prev is not None else None

        rate_str  = f"{rate:.2f}%" if rate is not None else "n/a"
        trend_str = f"  [{trend}]" if trend else ""
        print(f"  {locale.upper()} ({meta['iso2']}): {rate_str}{trend_str}  ({date_str or 'no date'})")

        records.append({
            "locale":       locale,
            "iso2":         meta["iso2"],
            "bank_name":    meta["bank"],
            "source":       source,
            "policy_rate":  rate,
            "previous_rate": prev,
            "rate_change":  rate_change,
            "rate_trend":   trend,
            "rate_date":    date_str,
        })

    upserted = save_to_db(conn, records)
    conn.close()
    print(f"\nUpserted {upserted}/{len(records)} rows into locale_data.central_bank_rates")
