import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import psycopg2
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request

app = FastAPI(title="Gold Analytics Fetcher API", version="1.0.0")

PROJECT_ROOT = Path("/app")

FETCHERS: dict[str, Path] = {
    "gold-prices-1d":    PROJECT_ROOT / "data_sources/gold_prices/fetcher.py",
    "gold-prices-1h":    PROJECT_ROOT / "data_sources/gold_prices/fetcher_1h.py",
    "correlated-assets": PROJECT_ROOT / "data_sources/correlated_assets/fetcher.py",
    "central-bank":      PROJECT_ROOT / "data_sources/central_bank/fetcher.py",
    "cot-report":        PROJECT_ROOT / "data_sources/cot_report/fetcher.py",
    "fed-rates":         PROJECT_ROOT / "data_sources/fed_rates/fetcher.py",
    "etf-flows":         PROJECT_ROOT / "data_sources/etf_flows/fetcher.py",
    "economic-calendar": PROJECT_ROOT / "data_sources/economic_calendar/fetcher.py",
    "news":              PROJECT_ROOT / "data_sources/news/fetcher.py",
    # Locale-specific market data
    "locale/fx-rates":            PROJECT_ROOT / "data_sources/locale_data/fetcher_fx_rates.py",
    "locale/macro":               PROJECT_ROOT / "data_sources/locale_data/fetcher_macro.py",
    "locale/central-bank-rates":  PROJECT_ROOT / "data_sources/locale_data/fetcher_central_bank_rates.py",
}

# Per-fetcher timeouts in seconds
TIMEOUTS: dict[str, int] = {
    "gold-prices-1d":    120,
    "gold-prices-1h":    180,
    "correlated-assets": 180,
    "central-bank":      120,
    "cot-report":        300,   # downloads ZIP files per year
    "fed-rates":         120,
    "etf-flows":         60,
    "economic-calendar": 120,
    "news":              60,
    "locale/fx-rates":           60,
    "locale/macro":              120,   # 10 World Bank calls, one per country
    "locale/central-bank-rates": 60,
}


def _run(name: str) -> dict:
    script = FETCHERS[name]
    timeout = TIMEOUTS[name]

    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env={**os.environ},
        cwd=str(PROJECT_ROOT),
        timeout=timeout,
    )
    elapsed = round(time.time() - t0, 2)

    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())

    return {
        "status": "ok",
        "fetcher": name,
        "elapsed_s": elapsed,
        "output": proc.stdout.strip(),
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/fetchers")
def list_fetchers():
    return {"fetchers": list(FETCHERS.keys())}


def _make_endpoint(name: str):
    async def endpoint():
        try:
            return _run(name)
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail=f"{name} timed out after {TIMEOUTS[name]}s")
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

    endpoint.__name__ = f"fetch_{name.replace('-', '_').replace('/', '_')}"
    return endpoint


for _name in FETCHERS:
    app.post(f"/fetch/{_name}", tags=["fetchers"])(_make_endpoint(_name))


@app.post("/fetch/all", tags=["fetchers"])
def fetch_all():
    results = {}
    for name in FETCHERS:
        try:
            results[name] = _run(name)
        except Exception as e:
            results[name] = {"status": "error", "fetcher": name, "error": str(e)}
    return results

# Which fetch scripts each render block needs (run before rendering)
RENDER_FETCHERS: dict[str, list[Path]] = {
    "rolling-candles": [
        PROJECT_ROOT / "youtube_shorts/rolling-candles/fetch_hourly.py",
        PROJECT_ROOT / "youtube_shorts/stat_overview/fetch_stats.py",
    ],
    "correlated-assets": [
        PROJECT_ROOT / "youtube_shorts/correlated_assets/fetch_correlated.py",
    ],
    "technical-indicators": [
        PROJECT_ROOT / "youtube_shorts/technical_indicators/fetch_technicals.py",
    ],
    "cta": [],
}

SHORTS_RENDERS: dict[str, dict] = {
    "rolling-candles":      {"cwd": PROJECT_ROOT / "youtube_shorts/rolling-candles",      "comp": "RollingCandles",       "out": "out/rolling_candles.mp4"},
    "correlated-assets":    {"cwd": PROJECT_ROOT / "youtube_shorts/correlated_assets",    "comp": "CorrelatedAssets",     "out": "out/correlated_assets.mp4"},
    "technical-indicators": {"cwd": PROJECT_ROOT / "youtube_shorts/technical_indicators", "comp": "TechnicalIndicators",  "out": "out/technical_indicators.mp4"},
    "cta":                  {"cwd": PROJECT_ROOT / "youtube_shorts/cta",                  "comp": "CTA",                  "out": "out/cta.mp4"},
}


def _run_fetch(script: Path, date: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(script), "--date", date],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        cwd=str(PROJECT_ROOT),
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout.strip()


def _last_trading_day() -> str:
    """
    Return the last completed trading day using calendar rules only:
      - Tue/Wed/Thu/Fri → yesterday
      - Sat/Sun/Mon     → last Friday
    """
    d = date.today() - timedelta(days=1)
    while d.weekday() >= 5:  # skip Saturday (5) and Sunday (6)
        d -= timedelta(days=1)
    return d.isoformat()


def _last_closed_day() -> str:
    """Return the last fully closed trading day: MAX(date) - 1 day from DB, skipping weekends."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "analytic_gold"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
    )
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(DATE(timestamp)) FROM gold_prices.gold_prices_1h")
        max_date = cur.fetchone()[0]
    finally:
        conn.close()
    d = max_date - timedelta(days=1)
    while d.weekday() >= 5:  # skip Saturday / Sunday
        d -= timedelta(days=1)
    return d.isoformat()


def _make_shorts_render_endpoint(name: str):
    async def endpoint(date: str):
        t0 = time.time()
        fetch_logs = []

        # 1. Fetch data from DB for this date
        for script in RENDER_FETCHERS.get(name, []):
            try:
                fetch_logs.append(_run_fetch(script, date))
            except RuntimeError as e:
                raise HTTPException(status_code=500, detail=f"fetch failed ({script.name}): {e}")

        # 2. Render
        cfg = SHORTS_RENDERS[name]
        # CTA is static — no date suffix.
        # For dated blocks, use the actual data date from public/data.json (the fetch scripts
        # may fall back to the latest DB date when the requested date has no data, e.g. weekends).
        actual_date = date
        if name != "cta":
            data_json = cfg["cwd"] / "public" / "data.json"
            try:
                with open(data_json) as _f:
                    actual_date = json.load(_f).get("date", date) or date
            except Exception:
                pass
        base_out = cfg["out"] if name == "cta" else cfg["out"].replace(".mp4", f"_{actual_date}.mp4")
        cmd = (
            "rm -rf node_modules package-lock.json "
            "&& npm install "
            f"&& npx remotion render {cfg['comp']} {base_out} --codec=h264 --crf=18"
        )
        try:
            proc = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True, text=True,
                env={**os.environ},
                cwd=str(cfg["cwd"]),
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail=f"shorts/render/{name} timed out")

        elapsed = round(time.time() - t0, 2)
        out_file = cfg["cwd"] / base_out
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=proc.stderr.strip() or proc.stdout.strip())
        if not out_file.exists():
            raise HTTPException(status_code=500, detail=f"Render completed but output file not found: {base_out}")
        return {"status": "ok", "step": f"render/{name}", "date": actual_date, "requested_date": date, "elapsed_s": elapsed}
    endpoint.__name__ = f"shorts_render_{name.replace('-', '_')}"
    return endpoint


for _name in SHORTS_RENDERS:
    app.post(f"/shorts/render/{_name}/{{date}}", tags=["shorts"])(_make_shorts_render_endpoint(_name))


def _run_shorts_script(script: Path, timeout: int) -> dict:
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        cwd=str(PROJECT_ROOT),
        timeout=timeout,
    )
    elapsed = round(time.time() - t0, 2)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return {"status": "ok", "elapsed_s": elapsed, "output": proc.stdout.strip()}


@app.post("/shorts/assemble", tags=["shorts"])
def shorts_assemble():
    try:
        return _run_shorts_script(PROJECT_ROOT / "youtube_shorts/assemble.py", timeout=120)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="shorts/assemble timed out")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/shorts/voice", tags=["shorts"])
def shorts_voice():
    try:
        return _run_shorts_script(PROJECT_ROOT / "youtube_shorts/voice/generate_voice.py", timeout=120)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="shorts/voice timed out")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/shorts/description", tags=["shorts"])
def shorts_description():
    try:
        return _run_shorts_script(PROJECT_ROOT / "youtube_shorts/description/generate_description.py", timeout=60)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="shorts/description timed out")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Article GIFs ─────────────────────────────────────────────────────────────

GIF_RENDER_CONFIGS: dict[str, dict] = {
    "price-chart":         {"fetch": PROJECT_ROOT / "article_gifs/price-chart/fetch_price_chart.py",                 "cwd": PROJECT_ROOT / "article_gifs/price-chart",         "comp": "PriceChart",         "out_tpl": "out/price_chart_{date}.gif"},
    "technical-dashboard": {"fetch": PROJECT_ROOT / "article_gifs/technical-dashboard/fetch_technical_dashboard.py", "cwd": PROJECT_ROOT / "article_gifs/technical-dashboard", "comp": "TechnicalDashboard", "out_tpl": "out/technical_dashboard_{date}.gif"},
    "correlated-heatmap":  {"fetch": PROJECT_ROOT / "article_gifs/correlated-heatmap/fetch_correlated_heatmap.py",   "cwd": PROJECT_ROOT / "article_gifs/correlated-heatmap",  "comp": "CorrelatedHeatmap",  "out_tpl": "out/correlated_heatmap_{date}.gif"},
}


GIF_MANIFEST_DIR = PROJECT_ROOT / "article_gifs" / "out"


def _update_gif_manifest(date: str, chart_name: str, rel_path: str) -> None:
    """Add or update a single chart entry in the manifest for the given date."""
    GIF_MANIFEST_DIR.mkdir(exist_ok=True)
    manifest_path = GIF_MANIFEST_DIR / f"manifest_{date}.json"
    # Remove stale manifests from previous days
    for old in GIF_MANIFEST_DIR.glob("manifest_*.json"):
        if old != manifest_path:
            old.unlink()
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
    else:
        manifest = {"date": date, "gifs": {}}
    manifest["gifs"][chart_name] = rel_path
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)


def _make_gif_render_endpoint(name: str):
    async def endpoint(date: str):
        t0 = time.time()
        cfg = GIF_RENDER_CONFIGS[name]

        # 1. Fetch data
        try:
            _run_fetch(cfg["fetch"], date)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=f"fetch failed: {e}")

        # 2. npm install — always run so binaries match the current OS/platform
        cwd = cfg["cwd"]
        subprocess.run(["npm", "install"], cwd=str(cwd), capture_output=True, timeout=120)

        # 3. Render GIF
        out_name = cfg["out_tpl"].format(date=date)
        (cwd / "out").mkdir(exist_ok=True)
        try:
            proc = subprocess.run(
                ["npx", "remotion", "render", cfg["comp"], out_name,
                 "--codec=gif", "--fps=15", "--number-of-gif-loops=1"],
                capture_output=True, text=True,
                cwd=str(cwd), timeout=300,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail=f"gifs/render/{name} timed out")

        elapsed = round(time.time() - t0, 2)
        out_path = cwd / out_name
        if proc.returncode != 0 and not out_path.exists():
            raise HTTPException(status_code=500, detail=proc.stderr.strip() or proc.stdout.strip())

        # 4. Update manifest so article_generator can pick this chart up
        rel_path = out_path.relative_to(PROJECT_ROOT).as_posix()
        _update_gif_manifest(date, name, rel_path)

        return {"status": "ok", "chart": name, "date": date, "elapsed_s": elapsed}
    endpoint.__name__ = f"gif_render_{name.replace('-', '_')}"
    return endpoint


for _gname in GIF_RENDER_CONFIGS:
    app.post(f"/gifs/render/{_gname}/{{date}}", tags=["gifs"])(_make_gif_render_endpoint(_gname))


@app.post("/gifs/render/all/{date}", tags=["gifs"])
def gif_render_all(
    date: str,
    format: Optional[str] = Query(default="mobile", description="desktop | mobile | all"),
):
    """Render all article GIFs. format=all renders both desktop (1200×400) and mobile/square (800×800) variants."""
    if format not in ("desktop", "mobile", "all"):
        raise HTTPException(status_code=400, detail="format must be 'desktop', 'mobile', or 'all'")
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "article_gifs/render_all.py"),
         "--date", date, "--format", format],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        cwd=str(PROJECT_ROOT),
        timeout=1200,
    )
    elapsed = round(time.time() - t0, 2)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=proc.stderr.strip() or proc.stdout.strip())
    return {"status": "ok", "date": date, "format": format, "elapsed_s": elapsed, "output": proc.stdout.strip()}


@app.post("/gifs/render/all", tags=["gifs"])
def gif_render_all_auto(
    format: Optional[str] = Query(default="mobile", description="desktop | mobile | all"),
):
    """Render all GIFs for the last trading day (auto-computed — no date needed)."""
    return gif_render_all(date=_last_trading_day(), format=format)


# ─── Article generator ────────────────────────────────────────────────────────

@app.post("/generate/article", tags=["generator"])
def generate_article():
    script = PROJECT_ROOT / "analyzer/article_generator.py"
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
            cwd=str(PROJECT_ROOT),
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="timed out after 600s")
    elapsed = round(time.time() - t0, 2)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=proc.stderr.strip() or proc.stdout.strip())
    return {"status": "ok", "elapsed_s": elapsed, "output": proc.stdout.strip()}


@app.post("/generate/article/locale", tags=["generator"])
def generate_locale_article(
    locale: str = Query(..., description="Locale code, e.g. cl, mx, ar"),
    date: Optional[str] = Query(default=None, description="Date YYYY-MM-DD (default: today)"),
    no_gifs: bool = Query(default=False, description="Skip GIF injection"),
):
    """Generate a locale-native article in the locale's language using local market data."""
    script = PROJECT_ROOT / "analyzer/locale_article_generator.py"
    cmd = [sys.executable, str(script), "--locale", locale]
    if date:
        cmd += ["--date", date]
    if no_gifs:
        cmd.append("--no-gifs")
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
            cwd=str(PROJECT_ROOT),
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="timed out after 600s")
    elapsed = round(time.time() - t0, 2)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=proc.stderr.strip() or proc.stdout.strip())
    return {"status": "ok", "locale": locale, "elapsed_s": elapsed, "output": proc.stdout.strip()}


@app.post("/publish/website", tags=["publisher"])
def publish_website(
    date: Optional[str] = Query(default=None, description="Article date YYYY-MM-DD (default: today)"),
):
    """Run publish_article.py to deploy the generated article to the goldprice.trade website."""
    website_root = Path(os.getenv("WEBSITE_ROOT", "/website"))
    app_dir = Path(os.getenv("MD_DIR", "/app/output")).parent
    script = app_dir / "publish_article.py"
    if not script.exists():
        raise HTTPException(status_code=500, detail=f"publish_article.py not found at {script}")

    cmd = [sys.executable, str(script)]
    if date:
        cmd += ["--date", date]

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, text=True,
            env={**os.environ},
            cwd=str(app_dir),
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="publish/website timed out after 300s")
    elapsed = round(time.time() - t0, 2)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=proc.stderr.strip() or proc.stdout.strip())
    return {"status": "ok", "elapsed_s": elapsed, "output": proc.stdout.strip()}


@app.post("/generate/translations", tags=["generator"])
def generate_translations(
    date: Optional[str] = Query(default=None, description="Article date YYYY-MM-DD (default: auto-detect latest _en article)"),
    languages: Optional[str] = Query(default="es,pt,ru", description="Comma-separated language codes, e.g. es,pt,ru,de"),
):
    """Translate the latest (or a given date's) EN article into the requested languages using local Ollama."""
    script = PROJECT_ROOT / "analyzer/article_translator.py"
    cmd = [sys.executable, str(script), "--quiet"]
    if date:
        cmd += ["--date", date]
    else:
        # Auto-detect the most recently written _en article so date-boundary issues can't cause a miss
        output_dir = PROJECT_ROOT / "output"
        en_articles = sorted(
            list(output_dir.glob("gold_analysis_*_en.md")) +
            list((output_dir / "en").glob("gold_analysis_*_en.md")),
            key=lambda p: p.stat().st_mtime, reverse=True
        )
        if en_articles:
            cmd += ["--file", str(en_articles[0])]
    if languages:
        cmd += ["--languages"] + languages.split(",")

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
            cwd=str(PROJECT_ROOT),
            timeout=1800,   # 3 languages × ~10 min each worst case
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="translation timed out after 1800s")
    elapsed = round(time.time() - t0, 2)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=proc.stderr.strip() or proc.stdout.strip())
    return {"status": "ok", "elapsed_s": elapsed, "output": proc.stdout.strip()}