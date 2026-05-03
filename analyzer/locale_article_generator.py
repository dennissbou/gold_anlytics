"""
Locale-native article generator — generates a gold market analysis article
directly in the locale's language using Ollama, incorporating locale-specific
data (FX rate, central bank rate, macro indicators).

Usage:
  python analyzer/locale_article_generator.py --locale cl
  python analyzer/locale_article_generator.py --locale cl --date 2026-05-03
  python analyzer/locale_article_generator.py --locale cl --no-gifs
"""

import json
import os
import re
import shutil
import sys
import argparse
import unicodedata
import ollama
import psycopg2
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:latest")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "127.0.0.1"),
    "port":     os.getenv("DB_PORT", "5432"),
    "dbname":   os.getenv("DB_NAME", "gold_analytics"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
}

# ── Locale registry ────────────────────────────────────────────────────────────

LOCALE_CONFIG: dict[str, dict] = {
    "cl": {
        "language":      "Spanish",
        "country":       "Chile",
        "currency_code": "CLP",
        "currency_name": "peso chileno",
        "hreflang":      "es-CL",
        "seo_country":   "Chile",
        "bank_name":     "Banco Central de Chile",
        "local_note": (
            "Chile es el mayor productor de cobre del mundo. El peso chileno (CLP) "
            "está fuertemente correlacionado con el ciclo global de materias primas, "
            "especialmente el cobre, lo que amplifica el impacto de los movimientos "
            "del oro en la economía local."
        ),
    },
}


# ── System prompt builder ──────────────────────────────────────────────────────

def build_locale_system_prompt(cfg: dict) -> str:
    lang      = cfg["language"]
    country   = cfg["country"]
    cur_code  = cfg["currency_code"]
    cur_name  = cfg["currency_name"]
    seo       = cfg["seo_country"]
    bank_name = cfg.get("bank_name", "Banco Central")

    return f"""You are a senior gold market analyst with 20+ years of experience covering XAU/USD
for institutional clients and financial publications in {country}. Your analysis combines:

- Technical Analysis: price action, moving averages, oscillators, chart patterns, support/resistance
- Macro Fundamentals: central bank policy, real interest rates, inflation, currency dynamics, geopolitical risk
- Market Positioning: COT futures positioning, ETF flows, central bank demand
- News Sentiment: recent headlines and their impact on gold
- Local Context: {country} economy, {cur_name} ({cur_code}) dynamics, local investment landscape

Your task is to write a professional, publication-ready gold market analysis article for {country} investors.

**IMPORTANT: Write the entire article in {lang}. All headings, text, and analysis must be in {lang}.**

---

**TITLE REQUIREMENTS (critical for SEO)**

The title must follow this exact format:
  Precio del Oro Hoy en {seo} ({cur_code}) — [Analyst opinion in 4–6 words]

Examples of good titles:
  "Precio del Oro Hoy en {seo} ({cur_code}) — Corrección Técnica con Soporte Clave"
  "Precio del Oro Hoy en {seo} ({cur_code}) — Señales Alcistas Pese al Retroceso"

- Maximum 12 words total
- The phrase "Precio del Oro" must appear in the title
- Title must reflect the current bias, not a generic statement
- Do NOT include a month name or year in the title (e.g., never "Marzo 2026"). Use "Hoy" for recency. The date is in the data header — the title must match that date's market reality, not a different month.

**PRIMARY SEO KEYWORD**

Choose ONE primary keyword (e.g., "precio del oro en {seo}" or "oro en {cur_code} hoy") and repeat it naturally **4–5 times** across the article. It MUST appear in: (a) the title, (b) the Executive Summary, (c) at least one section in §4–§8 as a natural sentence opener, and (d) the final section. Do NOT concentrate all keyword uses in a single section.

---

**Article Structure** (use exactly these 11 sections in this order — number them 1 through 11):

1. **Title** — (see Title Requirements above)
2. **Market Bias** — one line: Alcista / Bajista / Neutral with brief rationale (in {lang})
3. **Executive Summary** — 3-4 sentences. Include the gold price in {cur_code} and USD. Repeat the primary keyword naturally.
4. **{country} y el Triángulo Cobre-Peso-Oro** ← THIS IS SECTION 4, placed early as the key differentiator
   - {country} as the world's largest copper producer means the {cur_name} is commodity-correlated
   - Explain how CLP/USD moves amplify or cushion gold price changes for local investors
   - {bank_name} policy rate vs. Fed: convergence or divergence and what it means for gold
   - Local inflation and GDP context
5. **Análisis Técnico**
   - Current price action and trend (use ONLY the {cur_code} price and the USD price — do not mix)
   - Key moving averages (SMA 20/50/200) and their significance
   - RSI and MACD interpretation
   - Bollinger Bands and ATR (volatility context)
   - Key support and resistance levels (express in both USD and {cur_code}; label clearly as support/resistance)
6. **Factores Macroeconómicos**
   - Fed policy trajectory: current rate, expected path, and what it means for real rates and USD
   - {cur_name} vs USD dynamics
   - Geopolitical/risk-off premium
7. **Posicionamiento y Flujos de Mercado**
   - COT report: speculative positioning — AND explicitly reconcile with ETF flows if they contradict
   - ETF flows: institutional demand trend. IMPORTANT: ETF outflows mean investors are SELLING gold ETF shares — this is bearish/neutral. Do NOT describe ETF outflows as "rotation toward physical gold" — outflows and physical buying are separate phenomena. If ETF outflows are large, say so clearly and explain the bearish implication.
   - Central bank buying context
8. **Activos Correlacionados**
   - DXY, US10Y, Silver, WTI Oil, SPX, VIX — how they support/contradict gold thesis
9. **Catalizadores Próximos**
   - Key economic events in the next 30 days that could move gold
10. **Idea de Trading**
    - Direction (Long/Short)
    - Entry zone (in USD and {cur_code})
    - Stop loss (with rationale)
    - Target(s) (with rationale)
    - Risk/Reward ratio
    - **{seo}-specific instruments**: mention how local investors can implement this via AFP voluntary contributions, Bolsa de Comercio de Santiago (BCS) instruments, or gold-linked funds/ETFs accessible in {country}
11. **Perspectiva de Precio y FAQ**
    - Tomorrow's expected range (in USD and {cur_code})
    - 1-week directional bias with key pivot levels
    - Write exactly 3 FAQ questions relevant to {seo} investors. Each FAQ must follow this format exactly — write the actual question text and the actual answer, never placeholders:
      **¿[actual question text here]?**
      [actual 2-3 sentence answer here]
    - The three questions must cover: (1) whether now is a good time to buy gold in {seo}, (2) how to buy gold in {cur_code}, (3) how the copper price affects gold for {seo} investors.
    - Do NOT output the literal text "[Question]" or "[answer]" — replace them with real content.

---

**Writing Style:**
- Professional yet accessible — suitable for {seo} financial publications and TradingView
- Data-driven: reference specific numbers from the data provided
- Confident but balanced — the bearish case must be acknowledged (e.g., if ETF outflows are large, say so and explain its significance)
- No fluff or generic statements — every sentence must add value
- Use markdown formatting: headers (##), bold for key numbers, bullet points where appropriate
- Naturally include SEO-relevant terms: "{seo}", "{cur_name}", "precio del oro", "análisis oro hoy"
- Complete every sentence fully — never leave dangling text, broken price fragments, or incomplete clauses (e.g., never end a bullet with "/ prima" or a bare slash)
- Spanish grammar: "la plata" is feminine (never "el plata"); "el oro" is masculine. Apply correct gender agreement throughout.

**Currency Units Rule (CRITICAL):**
The data context provides ALL technical price levels (current price, SMAs, support, resistance, Bollinger Bands) in USD. The local {cur_code} price is provided separately in the "Local Data" block.
- When citing a USD price in the article, always write "USD X,XXX" — never "$X,XXX" without the currency label.
- When citing the {cur_code} price, always write "X,XXX,XXX {cur_code}/oz".
- Do NOT apply the {cur_code} label to a USD figure, and vice versa.
- Express support and resistance levels in BOTH USD and {cur_code} (convert using the CLP/USD rate provided).
- COP is the Colombian Peso — never use COP when writing about Chile. When describing the link between the peso and copper, write "CLP/USD influenciado por el precio del cobre", never "CLP/COP".

**Economic Logic Rules (CRITICAL — do not invert these):**
- When CLP weakens vs USD (USD/CLP rate rises), gold becomes MORE expensive in CLP → bullish for local gold holders.
- When CLP strengthens vs USD (USD/CLP rate falls), gold becomes CHEAPER in CLP → bearish for local gold holders.
- A falling copper price → weakens CLP → raises the CLP gold price → net effect for Chilean investors is gold becomes pricier locally.
- A rising copper price → strengthens CLP → lowers the CLP gold price → gold becomes cheaper locally.
Never write that "a weaker CLP makes gold cheaper" or "copper falls → gold falls in CLP" — both are wrong.

**Price Consistency Rule (CRITICAL):**
Use ONE current price throughout the entire article — the "Gold price in {cur_code}" from the Local Data block and its USD equivalent from the "Current price" field. Do not reference any other price level as "the current price." News headlines sometimes mention future targets or historic levels — do NOT treat those as the current price. Label all-time highs explicitly as "máximo histórico" and technical resistance levels as "resistencia" so they are never confused with the current price.

**Contradiction Rule:**
If two data points seem to contradict (e.g., ETF outflows + bullish futures), you MUST explicitly reconcile them: state which signal you weight more heavily and why (timing, institutional vs. retail, leading vs. lagging indicator).

**Do NOT:**
- Mention individual mining stocks or equities unless you have specific price/flow data about them
- Use generic advice like "diversificación de cartera" without a specific {seo} angle
- Present the same analysis as "neutral" everywhere — take a clear stance section by section

**Important:** Base your analysis ONLY on the data provided. Do not invent price levels or events.
Output ONLY the article — no preamble, no meta-commentary, no follow-up questions, no placeholder text.
Do NOT include any markdown tables. Present all data as prose or bullet points only.
Do NOT add a "Key Data Points" section or any summary data block.
The article ends with the third FAQ answer. Stop writing immediately after that. Do not add any text, heading, or sentence after the last FAQ answer — not a disclaimer, not a note, not a closing line."""


# ── Locale data fetcher ────────────────────────────────────────────────────────

def fetch_locale_data(locale: str, conn) -> dict:
    """Query locale_data tables for FX, central bank rate, and macro indicators."""
    result: dict = {}
    cur = conn.cursor()

    cur.execute("""
        SELECT rate_usd, gold_price_local, change_30d_pct, fx_trend
        FROM locale_data.fx_rates
        WHERE locale = %s
        ORDER BY fetched_date DESC LIMIT 1
    """, (locale,))
    row = cur.fetchone()
    if row:
        result["fx"] = {
            "rate_usd":       row[0],
            "gold_price_local": row[1],
            "change_30d_pct": row[2],
            "fx_trend":       row[3],
        }

    cur.execute("""
        SELECT policy_rate, rate_trend, rate_date, bank_name
        FROM locale_data.central_bank_rates
        WHERE locale = %s
    """, (locale,))
    row = cur.fetchone()
    if row:
        result["cb"] = {
            "policy_rate": row[0],
            "rate_trend":  row[1],
            "rate_date":   str(row[2]) if row[2] else None,
            "bank_name":   row[3],
        }

    cur.execute("""
        SELECT inflation_annual_pct, inflation_year, gdp_growth_pct, gdp_year
        FROM locale_data.macro
        WHERE locale = %s
    """, (locale,))
    row = cur.fetchone()
    if row:
        result["macro"] = {
            "inflation_annual_pct": row[0],
            "inflation_year":       row[1],
            "gdp_growth_pct":       row[2],
            "gdp_year":             row[3],
        }

    cur.close()
    return result


# ── Context message builder ────────────────────────────────────────────────────

def build_locale_context_message(core_ctx: dict, locale_data: dict, cfg: dict) -> str:
    """Build full context message: global market data + locale-specific data block."""
    from analyzer.article_generator import build_context_message
    base = build_context_message(core_ctx)

    # Append locale-specific block
    cur_code = cfg["currency_code"]
    cur_name = cfg["currency_name"]
    country  = cfg["country"]
    local_note = cfg.get("local_note", "")

    lines = [
        "",
        f"## Local Data ({country})",
    ]

    fx = locale_data.get("fx", {})
    if fx:
        rate    = fx.get("rate_usd")
        gl      = fx.get("gold_price_local")
        chg     = fx.get("change_30d_pct")
        trend   = fx.get("fx_trend", "")
        if rate:
            lines.append(f"- {cur_code}/USD rate: {rate:.4f} ({trend}; 30d change: {chg:+.2f}%)" if chg is not None else f"- {cur_code}/USD rate: {rate:.4f} ({trend})")
        if gl:
            lines.append(f"- Gold price in {cur_code}: {gl:,.0f} {cur_code}/oz")

    cb = locale_data.get("cb", {})
    if cb and cb.get("policy_rate") is not None:
        bank    = cb.get("bank_name", "Central Bank")
        rate    = cb["policy_rate"]
        trend   = cb.get("rate_trend", "")
        dt      = cb.get("rate_date", "")
        lines.append(f"- {bank} policy rate: {rate:.2f}% ({trend}, as of {dt})")

    macro = locale_data.get("macro", {})
    if macro:
        inf = macro.get("inflation_annual_pct")
        inf_yr = macro.get("inflation_year", "")
        gdp = macro.get("gdp_growth_pct")
        gdp_yr = macro.get("gdp_year", "")
        if inf is not None:
            lines.append(f"- Annual inflation ({inf_yr}): {inf:.1f}%")
        if gdp is not None:
            lines.append(f"- GDP growth ({gdp_yr}): {gdp:.1f}%")

    if local_note:
        lines.append(f"- Context: {local_note}")

    lines.append("")
    lines.append(
        "---\n"
        f"Write the full professional gold market analysis article for {country} investors "
        f"in {cfg['language']}. Follow the 11-section structure from your instructions exactly."
    )

    # Prepend a currency disambiguation note before any price data
    currency_note = (
        f"**UNITS NOTE**: All price levels in the data below (current price, SMAs, support, "
        f"resistance, Bollinger Bands) are in USD. The {cur_code} price is provided in the "
        f"'Local Data ({country})' block below. Never apply the {cur_code} label to a USD figure.\n\n"
    )

    # Replace the generic closing line from build_context_message
    base_without_closing = base.rsplit("---\n", 1)[0]
    return currency_note + base_without_closing + "\n".join(lines)


# ── GIF injection ──────────────────────────────────────────────────────────────

def build_gif_alt_texts(cfg: dict, article_title: str, date_str: str) -> dict:
    """Return unique, SEO-friendly alt texts for each GIF block, specific to this article."""
    country  = cfg["country"]
    cur_code = cfg["currency_code"]
    # Extract the dynamic part after the dash (e.g. "Corrección Técnica con Soporte Clave")
    dynamic = re.sub(r"^[^—–-]+[—–-]\s*", "", article_title).strip() or article_title
    return {
        "price-chart": (
            f"Precio del oro en {country} {date_str} — {dynamic} — "
            f"gráfico de velas diarias y medias móviles ({cur_code})"
        ),
        "technical-dashboard": (
            f"Análisis técnico del oro en {country} {date_str} — {dynamic} — "
            f"RSI, MACD, Bandas de Bollinger"
        ),
        "correlated-heatmap": (
            f"Activos correlacionados con el oro en {country} {date_str} — {dynamic} — "
            f"DXY, plata, petróleo, VIX"
        ),
    }


def inject_gifs_locale(article: str, gif_paths: dict, alt_texts: dict, prefer: str = "mobile") -> str:
    """Inject GIFs at fixed positions using per-article alt text.

    Positions:
      price-chart         — before Executive Summary / Resumen Ejecutivo
      technical-dashboard — after  Análisis Técnico heading
      correlated-heatmap  — after  Activos Correlacionados heading
    Section headers may be numbered (e.g. "5. Análisis Técnico") — use `in` matching.
    """
    from analyzer.article_generator import _header_title, _resolve_gif

    lines = article.splitlines(keepends=True)
    result = []

    for line in lines:
        title = _header_title(line)

        if "resumen ejecutivo" in title or "executive summary" in title:
            pc = _resolve_gif(gif_paths, "price-chart", prefer)
            if pc:
                result.append(f"\n![{alt_texts['price-chart']}]({pc})\n\n")

        result.append(line)

        if "análisis técnico" in title or "technical analysis" in title:
            td = _resolve_gif(gif_paths, "technical-dashboard", prefer)
            if td:
                result.append(f"\n![{alt_texts['technical-dashboard']}]({td})\n\n")

        if "activos correlacionados" in title or "correlated assets" in title:
            ch = _resolve_gif(gif_paths, "correlated-heatmap", prefer)
            if ch:
                result.append(f"\n![{alt_texts['correlated-heatmap']}]({ch})\n\n")

    return "".join(result)


# ── GIF renaming ──────────────────────────────────────────────────────────────

def _title_slug(title: str, max_words: int = 6) -> str:
    """Convert an article title to a URL-safe slug (first N words)."""
    normalized = unicodedata.normalize("NFD", title)
    ascii_only = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    words_only = re.sub(r"[^a-zA-Z0-9\s]", " ", ascii_only)
    words = words_only.lower().split()[:max_words]
    return "-".join(words)


def prepare_locale_gifs(
    manifest_gifs: dict, locale: str, title: str, date_str: str, prefer: str = "mobile"
) -> dict:
    """
    Copy the preferred GIF variant for each block into output/{locale}/, renamed to:
      {locale}-{date}-{dynamic-title-slug}-{block}.gif

    Returns a flat {block: filename} dict where each value is just the bare filename
    (no directory prefix) — the article and GIFs live in the same folder, so relative
    paths work without any path prefix.
    """
    out_dir = PROJECT_ROOT / "output" / locale
    out_dir.mkdir(parents=True, exist_ok=True)

    dynamic = re.sub(r"^[^—–-]+[—–-]\s*", "", title).strip() or title
    slug = _title_slug(dynamic)
    fallback = "desktop" if prefer == "mobile" else "mobile"
    renamed: dict = {}

    for block, variants in manifest_gifs.items():
        src_path = variants.get(prefer) or variants.get(fallback)
        if not src_path:
            continue
        src = Path(src_path)
        new_name = f"{locale}-{date_str}-{slug}-{block}.gif"
        dst = out_dir / new_name
        if src.exists():
            shutil.copy2(src, dst)
        renamed[block] = new_name  # bare filename — same dir as the article

    return renamed


# ── Save helpers ───────────────────────────────────────────────────────────────

def save_article(article: str, locale: str, date_str: str) -> str:
    out_dir = PROJECT_ROOT / "output" / locale
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"gold_analysis_{date_str}_{locale}.md"
    path.write_text(article, encoding="utf-8")
    return str(path)


def save_to_db(article: str, locale: str, conn) -> None:
    title = next(
        (line.lstrip("#").strip() for line in article.splitlines() if line.strip()),
        f"Gold Analysis {date.today()} ({locale.upper()})"
    )
    today = date.today().isoformat()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM articles WHERE created_at::date = %s AND title LIKE %s",
        (today, f"%({locale.upper()})%")
    )
    cur.execute(
        "INSERT INTO articles (title, content) VALUES (%s, %s)",
        (f"{title} ({locale.upper()})", article),
    )
    conn.commit()
    cur.close()


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate locale-native gold analysis article")
    parser.add_argument("--locale",  required=True, choices=list(LOCALE_CONFIG), help="Locale code (e.g. cl)")
    parser.add_argument("--date",    default=None,  help="Date override YYYY-MM-DD")
    parser.add_argument("--no-gifs", action="store_true", help="Skip GIF injection")
    args = parser.parse_args()

    locale   = args.locale
    date_str = args.date or str(date.today())
    cfg      = LOCALE_CONFIG[locale]

    print(f"Generating locale-native article: {locale.upper()} ({cfg['country']}, {cfg['language']})")

    # Load core market data
    print("Collecting market data...")
    from analyzer.data_collector import collect_all
    core_ctx = collect_all()

    # Load locale-specific data
    print(f"Fetching locale data for {locale}...")
    conn = psycopg2.connect(**DB_CONFIG)
    locale_data = fetch_locale_data(locale, conn)

    fx = locale_data.get("fx", {})
    cb = locale_data.get("cb", {})
    macro = locale_data.get("macro", {})
    if fx:
        print(f"  FX: 1 USD = {fx.get('rate_usd')} {cfg['currency_code']}  |  Gold = {fx.get('gold_price_local'):,.0f} {cfg['currency_code']}/oz")
    if cb and cb.get("policy_rate"):
        print(f"  CB rate: {cb['policy_rate']}% ({cb.get('rate_trend')})")
    if macro and macro.get("inflation_annual_pct"):
        print(f"  Inflation: {macro['inflation_annual_pct']}%  |  GDP: {macro.get('gdp_growth_pct')}%")

    # Build prompts
    system_prompt  = build_locale_system_prompt(cfg)
    context_message = build_locale_context_message(core_ctx, locale_data, cfg)

    # Generate with Ollama
    print(f"\nGenerating article with {OLLAMA_MODEL} (streaming)...\n" + "-" * 60)
    full_text = ""
    stream = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": context_message},
        ],
        stream=True,
        think=False,
        options={"temperature": 0.7, "num_predict": 8192},
    )
    for chunk in stream:
        text = chunk["message"].get("content", "")
        if text:
            full_text += text
            print(text, end="", flush=True)
    print("\n" + "-" * 60)

    # Extract article title (first non-empty line, strip leading #)
    article_title = next(
        (line.lstrip("#").strip() for line in full_text.splitlines() if line.strip()),
        f"gold-analysis-{date_str}-{locale}"
    )

    # Inject GIFs (renamed to article-title-based filenames)
    if not args.no_gifs:
        gif_out = PROJECT_ROOT / "article_gifs" / "out"
        manifest_path = gif_out / f"manifest_{date_str}.json"
        if not manifest_path.exists():
            # Fall back to the most recent available manifest
            candidates = sorted(gif_out.glob("manifest_*.json"), reverse=True)
            manifest_path = candidates[0] if candidates else None
            if manifest_path:
                print(f"No GIF manifest for {date_str} — using {manifest_path.name} as fallback.")
        if manifest_path and manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)
            gif_paths = prepare_locale_gifs(manifest.get("gifs", {}), locale, article_title, date_str)
            alt_texts = build_gif_alt_texts(cfg, article_title, date_str)
            full_text = inject_gifs_locale(full_text, gif_paths, alt_texts)
            print(f"GIFs injected with unique alt text (slug: {_title_slug(article_title)}).")
        else:
            print("No GIF manifest found anywhere — skipping GIF injection.")

    # Save
    path = save_article(full_text, locale, date_str)
    print(f"\nArticle saved to: {path}")

    try:
        save_to_db(full_text, locale, conn)
        print("Article saved to database.")
    except Exception as e:
        print(f"DB save skipped: {e}")

    conn.close()
