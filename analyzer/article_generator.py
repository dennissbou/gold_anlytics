"""
Article Generator — reads structured context from data_collector,
calls local Ollama LLM (qwen3.5) to write a professional gold analysis article,
then returns the markdown text.
"""

import json
import os
import subprocess
import sys
import ollama
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent

load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:latest")

SYSTEM_PROMPT = """You are a senior gold market analyst with 20+ years of experience covering XAU/USD
for institutional clients and financial publications. Your analysis combines:

- Technical Analysis: price action, moving averages, oscillators, chart patterns, support/resistance
- Macro Fundamentals: Fed policy, real interest rates, inflation, USD dynamics, geopolitical risk
- Market Positioning: COT futures positioning, ETF flows, central bank demand
- News Sentiment: recent headlines and their impact on gold

Your task is to write a professional, publication-ready gold market analysis article.

**Article Structure** (use exactly these sections in this order):

1. **Title** — catchy, informative, reflects current bias
2. **Market Bias** — one line: Bullish / Bearish / Neutral with brief rationale
3. **Executive Summary** — 3-4 sentences covering the most important takeaways
4. **Technical Analysis**
   - Current price action and trend
   - Key moving averages (SMA 20/50/200) and their significance
   - RSI and MACD interpretation
   - Bollinger Bands and ATR (volatility context)
   - Key support and resistance levels
5. **Macro & Fundamental Drivers**
   - Fed policy and real interest rates impact on gold
   - USD and yield correlations (DXY, 10Y Treasury)
   - Inflation backdrop (CPI, PCE)
   - Geopolitical/risk-off premium
6. **Market Positioning & Flows**
   - COT report: speculative positioning (bullish/bearish signal)
   - ETF flows: institutional demand trend
   - Central bank buying context
7. **Correlated Assets**
   - DXY, US10Y, Silver, WTI Oil, SPX, VIX — how they support/contradict gold thesis
8. **Upcoming Catalysts**
   - Key economic events in the next 30 days that could move gold
9. **Trade Idea**
   - Direction (Long/Short)
   - Entry zone
   - Stop loss (with rationale)
   - Target(s) (with rationale)
   - Risk/Reward ratio
10. **Price Outlook**
    - Tomorrow's expected range
    - 1-week directional bias with key pivot levels

**Writing Style:**
- Professional yet accessible — suitable for TradingView and financial magazines
- Data-driven: reference specific numbers from the data provided
- Confident but balanced — acknowledge key risks to the thesis
- No fluff or generic statements — every sentence must add value
- Use markdown formatting: headers (##), bold for key numbers, bullet points where appropriate

**Important:** Base your analysis ONLY on the data provided. Do not invent price levels or events.
Output ONLY the article — no preamble, no meta-commentary, no "Here is the article:" header.
Do NOT include any markdown tables anywhere in the article. Do not add an appendix, data snapshot table, metrics table, or summary table — anywhere in the article, including at the end. Present all data as prose or bullet points only.
Do NOT add a "Key Data Points" section or any equivalent summary data block — not at the top, bottom, or anywhere in the article."""


def build_context_message(ctx: dict) -> str:
    """Format the collected context dict into a clear prompt for the LLM."""
    today = ctx.get("generated_at", str(date.today()))

    gold      = ctx.get("gold", {})
    price     = gold.get("price", {})
    ma        = gold.get("moving_averages", {})
    indicators = gold.get("indicators", {})
    bb        = gold.get("bollinger_bands", {})
    levels    = gold.get("levels", {})
    trend     = gold.get("trend", "unknown")

    correlated = ctx.get("correlated", {})
    cot        = ctx.get("cot", {})
    etf        = ctx.get("etf_flows", {})
    fed        = ctx.get("fed_rates", {})
    calendar   = ctx.get("calendar", {})
    news       = ctx.get("news", [])
    cb         = ctx.get("central_bank", {})

    lines = [
        f"# Gold Market Data — {today}",
        "",
        "## Gold Price",
        f"- Current price: ${price.get('current', 'N/A')}",
        f"- 1-week change: {price.get('week_change_pct', 'N/A')}%",
        f"- 1-month change: {price.get('month_change_pct', 'N/A')}%",
        f"- 1-year change: {price.get('year_change_pct', 'N/A')}%",
        f"- 52-week high: ${price.get('high_52w', 'N/A')}",
        f"- 52-week low: ${price.get('low_52w', 'N/A')}",
        f"- Trend: {trend}",
        "",
        "## Moving Averages",
        f"- SMA 20: ${ma.get('sma20', 'N/A')}",
        f"- SMA 50: ${ma.get('sma50', 'N/A')}",
        f"- SMA 200: ${ma.get('sma200', 'N/A')}",
        "",
        "## Technical Indicators",
        f"- RSI (14): {indicators.get('rsi', 'N/A')}",
        f"- MACD: {indicators.get('macd', 'N/A')}",
        f"- MACD Signal: {indicators.get('macd_signal', 'N/A')}",
        f"- MACD Histogram: {indicators.get('macd_hist', 'N/A')}",
        f"- ATR (14): {indicators.get('atr', 'N/A')}",
        "",
        "## Bollinger Bands (20-period, 2 std)",
        f"- Upper: ${bb.get('upper', 'N/A')}",
        f"- Middle: ${bb.get('mid', 'N/A')}",
        f"- Lower: ${bb.get('lower', 'N/A')}",
        "",
        "## Key Support & Resistance",
        f"- Resistance (60-day high): ${levels.get('resistance', 'N/A')}",
        f"- Support (60-day low): ${levels.get('support', 'N/A')}",
        "",
    ]

    if correlated:
        lines += ["## Correlated Assets"]
        for symbol, data in correlated.items():
            lines.append(
                f"- {symbol}: {data.get('current', 'N/A')} "
                f"(W: {data.get('week_change_pct', 'N/A')}%, "
                f"M: {data.get('month_change_pct', 'N/A')}%)"
            )
        lines.append("")

    if cot:
        def _fmt_int(v):
            return f"{v:,}" if isinstance(v, (int, float)) else str(v)
        lines += [
            "## COT Futures Positioning (CFTC)",
            f"- Report date: {cot.get('report_date', 'N/A')}",
            f"- Non-commercial net: {_fmt_int(cot.get('noncomm_net', 'N/A'))} contracts",
            f"- Change (5 weeks): {_fmt_int(cot.get('noncomm_change', 'N/A'))} contracts",
            f"- Commercial net: {_fmt_int(cot.get('comm_net', 'N/A'))} contracts",
            f"- Open interest: {_fmt_int(cot.get('open_interest', 'N/A'))}",
            f"- Speculative bias: {str(cot.get('bias', 'N/A')).upper()}",
            "",
        ]

    if etf:
        lines += [
            "## Gold ETF Holdings & Flows",
            f"- Month: {etf.get('month', 'N/A')}",
            f"- Total holdings: {etf.get('total_tonnes', 'N/A')} tonnes",
            f"- Monthly change: {etf.get('month_change_t', 'N/A')} tonnes",
            f"- Monthly flow (USD): ${etf.get('monthly_flow_usd', 'N/A'):,}" if etf.get('monthly_flow_usd') else "- Monthly flow (USD): N/A",
            f"- Flow bias: {str(etf.get('flow_bias', 'N/A')).upper()}",
            "",
        ]

    if fed:
        lines += ["## Fed & Macro Rates (FRED)"]
        label_map = {
            "fed_funds_rate":     "Fed Funds Rate",
            "cpi":                "US CPI YoY",
            "yield_10y":          "US 10Y Treasury Yield",
            "yield_2y":           "US 2Y Treasury Yield",
            "yield_spread_10y2y": "10Y-2Y Spread",
            "real_rate_10y":      "10Y Real Rate (TIPS)",
        }
        for key, label in label_map.items():
            d = fed.get(key, {})
            if not d:
                continue
            if key == "cpi":
                # CPIAUCSL is an index level — use pre-computed YoY% or derive it
                yoy = d.get("yoy_pct")
                if yoy is None and d.get("year_ago"):
                    yoy = round((d["current"] - d["year_ago"]) / d["year_ago"] * 100, 2)
                if yoy is not None:
                    lines.append(f"- {label}: {yoy}%")
                else:
                    lines.append(f"- {label}: N/A")
            else:
                chg = f" (chg: {d.get('change', 'N/A')})" if d.get('change') is not None else ""
                ya  = f" | year ago: {d.get('year_ago', 'N/A')}" if d.get('year_ago') is not None else ""
                lines.append(f"- {label}: {d.get('current', 'N/A')}%{chg}{ya}")
        lines.append("")

    if calendar:
        upcoming = calendar.get("upcoming", [])
        recent   = calendar.get("recent_releases", [])
        if upcoming:
            lines += ["## Upcoming Economic Events (next 30 days)"]
            for ev in upcoming[:8]:
                forecast = f" | forecast: {ev.get('forecast')}" if ev.get('forecast') else ""
                lines.append(f"- {ev.get('date')}: {ev.get('event')}{forecast}")
            lines.append("")
        if recent:
            lines += ["## Recent Economic Releases"]
            for ev in recent[:6]:
                lines.append(
                    f"- {ev.get('date')}: {ev.get('event')} "
                    f"actual={ev.get('actual')} vs prev={ev.get('previous')}"
                )
            lines.append("")

    if cb:
        lines += [
            "## Central Bank Gold Reserves",
            f"- As of: {cb.get('as_of', 'N/A')}",
            f"- Top-10 total: {cb.get('total_top10t', 'N/A')} tonnes",
        ]
        for country, tonnes in list(cb.get("holdings", {}).items())[:5]:
            lines.append(f"  - {country}: {tonnes} tonnes")
        lines.append("")

    if news:
        lines += ["## Recent Gold Market News (latest 15 articles)"]
        for article in news[:15]:
            summary = f" -- {article['summary'][:120]}" if article.get("summary") else ""
            lines.append(
                f"- [{article['date']}] **{article['title']}** "
                f"({article.get('source', '')}){summary}"
            )
        lines.append("")

    lines.append(
        "---\n"
        "Write the full professional analysis article based on the data above. "
        "Follow the 10-section structure from your instructions exactly."
    )

    return "\n".join(lines)



def generate_article(verbose: bool = True) -> str:
    """Collect data, call Ollama LLM with streaming, return markdown article."""
    from analyzer.data_collector import collect_all

    if verbose:
        print("Collecting market data...")
    ctx = collect_all()

    if verbose:
        print("Building context message...")
    user_message = build_context_message(ctx)

    if verbose:
        print(f"Generating article with {OLLAMA_MODEL} (streaming)...\n")
        print("-" * 60)

    full_text = ""
    stream = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        stream=True,
        think=False,        # disable chain-of-thought for Qwen3.5
        options={"temperature": 0.7, "num_predict": 8192},
    )

    for chunk in stream:
        text = chunk["message"].get("content", "")
        if text:
            full_text += text
            if verbose:
                print(text, end="", flush=True)

    if verbose:
        print("\n" + "-" * 60)

    return full_text


def save_article(article: str, date_str: str, output_dir: str = "output") -> str:
    """Save the article to output/{output_dir}/en/. Returns the file path."""
    en_dir = os.path.join(output_dir, "en")
    os.makedirs(en_dir, exist_ok=True)
    filename = f"gold_analysis_{date_str}_en.md"
    path = os.path.join(en_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(article)
    return path


def save_to_db(article: str, conn=None) -> None:
    """Save the article to the articles table (public schema)."""
    close_conn = False
    if conn is None:
        from analyzer.data_collector import get_conn
        conn = get_conn()
        close_conn = True

    cur = conn.cursor()
    title = next(
        (line.lstrip("#").strip() for line in article.splitlines() if line.strip()),
        f"Gold Analysis {date.today()}"
    )
    today = date.today().isoformat()
    cur.execute("DELETE FROM articles WHERE created_at::date = %s", (today,))
    cur.execute(
        "INSERT INTO articles (title, content) VALUES (%s, %s)",
        (title, article),
    )
    conn.commit()
    cur.close()
    if close_conn:
        conn.close()


def _header_title(line: str) -> str:
    """Strip leading # characters and ** bold markers, return lowercased section title."""
    return line.strip().lstrip("#").strip().strip("*").strip().lower()


def _resolve_gif(gif_paths: dict, name: str, prefer: str = "desktop") -> str:
    """
    Resolve a GIF path from the manifest entry for `name`.
    Handles both the new nested format {"desktop": path, "mobile": path}
    and the legacy flat format where the value is a plain string.
    Falls back to the other variant if the preferred one is absent.
    """
    entry = gif_paths.get(name, "")
    if not entry:
        return ""
    if isinstance(entry, str):          # legacy flat manifest
        return entry
    fallback = "mobile" if prefer == "desktop" else "desktop"
    return entry.get(prefer) or entry.get(fallback) or ""


def inject_gifs_into_article(article: str, gif_paths: dict, prefer: str = "desktop") -> str:
    """Insert GIF embed tags at fixed positions in the article.

    Positions:
      price-chart         — before ## Executive Summary
      technical-dashboard — after  ## Technical Analysis
      correlated-heatmap  — after  ## Correlated Assets
    """
    lines = article.splitlines(keepends=True)

    result = []
    for line in lines:
        title = _header_title(line)

        # Inject price-chart GIF *before* Executive Summary
        if title == "executive summary":
            pc = _resolve_gif(gif_paths, "price-chart", prefer)
            if pc:
                result.append(f"\n![Gold Price Chart — Daily Candles & Moving Averages]({pc})\n\n")

        result.append(line)

        # Inject technical-dashboard *after* Technical Analysis heading
        if title == "technical analysis":
            td = _resolve_gif(gif_paths, "technical-dashboard", prefer)
            if td:
                result.append(f"\n![Technical Dashboard — RSI / MACD / Bollinger Bands]({td})\n\n")

        # Inject correlated-heatmap *after* Correlated Assets heading
        if title.startswith("correlated assets"):
            ch = _resolve_gif(gif_paths, "correlated-heatmap", prefer)
            if ch:
                result.append(f"\n![Correlated Assets Heatmap]({ch})\n\n")

    return "".join(result)


def generate_article_with_gifs(verbose: bool = True, render_gifs: bool = True) -> tuple[str, str]:
    """Returns (article_text, date_str)."""
    date_str = str(date.today())
    article = generate_article(verbose=verbose)
    if not render_gifs:
        return article, date_str

    manifest_path = PROJECT_ROOT / "article_gifs" / "out" / f"manifest_{date_str}.json"

    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "article_gifs" / "render_all.py"), "--date", date_str],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        cwd=str(PROJECT_ROOT),
        timeout=600,
    )

    if proc.returncode == 0 and manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
        article = inject_gifs_into_article(article, manifest.get("gifs", {}))
        if verbose:
            print(f"GIFs injected: {list(manifest.get('gifs', {}).keys())}")
    elif verbose:
        print(f"GIF render skipped/failed (rc={proc.returncode}): {proc.stderr[:300]}")

    return article, date_str


if __name__ == "__main__":
    render_gifs = "--no-gifs" not in sys.argv
    article, date_str = generate_article_with_gifs(verbose=True, render_gifs=render_gifs)

    path = save_article(article, date_str)
    print(f"\nArticle saved to: {path}")

    try:
        save_to_db(article)
        print("Article saved to database.")
    except Exception as e:
        print(f"DB save skipped: {e}")
