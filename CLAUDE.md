# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated pipeline that generates XAU/USD (gold) trading analysis articles and optional YouTube Shorts. Runs daily via n8n scheduler (18:00 UTC Mon–Fri), fetching market data from multiple sources, storing in PostgreSQL, then generating AI-powered markdown articles published to goldprice.trade.

## Services & Ports

| Service | Port | How to Start |
|---------|------|-------------|
| PostgreSQL 16 | 5432 | `docker-compose up -d postgres` |
| Fetcher API (FastAPI) | 8000 | `docker-compose up -d fetcher-api` |
| n8n (orchestrator) | 5678 | `docker-compose up -d n8n` |

```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f fetcher-api
docker-compose logs -f n8n

# Initialize DB schemas (only needed first run or after schema changes)
python database/init_db.py

# Run fetcher API locally (outside Docker), from repo root:
uvicorn fetcher_api.main:app --reload --port 8000
```

## Running Individual Components

```bash
# Run a specific data fetcher manually
python data_sources/gold_prices/fetcher.py        # daily OHLCV
python data_sources/gold_prices/fetcher_1h.py     # hourly OHLCV
python data_sources/correlated_assets/fetcher.py
# etc.

# Trigger fetchers via API (Swagger UI at http://localhost:8000/docs)
curl -X POST http://localhost:8000/fetch/all
curl -X POST http://localhost:8000/fetch/gold-prices-1d

# Inspect the raw context dict that feeds article/shorts generation
python analyzer/data_collector.py

# Generate article with GIFs (reads DB, renders GIFs, calls Ollama, saves to output/)
python analyzer/article_generator.py
# Skip GIF rendering (faster, no Remotion dependency):
python analyzer/article_generator.py --no-gifs

# Translate today's article into Spanish, Portuguese, Russian (default):
python analyzer/article_translator.py
# Translate a specific date's article into specific languages:
python analyzer/article_translator.py --date 2026-04-14 --languages es pt ru
# Translate a specific file:
python analyzer/article_translator.py --file output/gold_analysis_2026-04-14_en.md --languages ru

# Publish generated articles to goldprice.trade website (all 11 locales):
python publish_article.py
python publish_article.py --date 2026-04-14

# YouTube Short — step by step (run from repo root)
python youtube_shorts/rolling-candles/fetch_hourly.py
python youtube_shorts/stat_overview/fetch_stats.py
python youtube_shorts/correlated_assets/fetch_correlated.py
python youtube_shorts/technical_indicators/fetch_technicals.py
# Then render each Remotion block (requires Node/npm):
bash youtube_shorts/rolling-candles/render.sh
# (or: npx remotion render <Comp> out/<name>.mp4 from within the block dir)
# Assemble all rendered MP4s into one final video:
python youtube_shorts/assemble.py
# Generate voiceover (Claude API → edge-tts MP3):
python youtube_shorts/voice/generate_voice.py
# Generate YouTube upload description:
python youtube_shorts/description/generate_description.py
```

## External Publishers (SEO Backlinks)

Generates Medium, PRLog, and Reddit adaptations of a published article for backlink building.
Reads the existing translated article from `output/`, uses local Ollama, writes to `external-publishers/{locale}/{date}/`.

```bash
# Generate all 3 platform files for a locale + date
python publish_external.py --locale ar --date 20260409

# Override the canonical URL (use when auto-derived slug doesn't match)
python publish_external.py --locale cl --date 20260409 --url https://goldprice.trade/cl/analytics/exact-slug-260409/

# All 11 locales: ar cl co cr en kz mx pa pe uy br
python publish_external.py --locale br --date 20260409   # Portuguese
python publish_external.py --locale kz --date 20260409   # Russian
python publish_external.py --locale en --date 20260409   # English (root)
```

Output structure: `external-publishers/{locale}/{date}/medium.md`, `prlog.txt`, `reddit.md`

Canonical URL is auto-derived from the article title using the same `make_slug` logic as `publish_article.py` (YYMMDD date suffix + locale country keyword).

**Locale → language mapping** (determines which translated article file is read from `output/`):

| Locales | Language | Article file suffix |
|---------|----------|---------------------|
| `ar cl co cr mx pa pe uy` | Spanish | `_es.md` |
| `br` | Portuguese | `_pt.md` |
| `kz` | Russian | `_ru.md` |
| `en` | English | `_en.md` |

## Environment Setup

Copy `.env.example` to `.env` and fill in:
- `FRED_API_KEY` — Federal Reserve Economic Data (free at fred.stlouisfed.org)
- `ANTHROPIC_API_KEY` — Claude API (required for youtube_shorts voice/description)
- `OLLAMA_MODEL` — override default LLM (default: `qwen3.5:latest`); not in `.env.example`, add manually. Applies to **all three** Ollama-using scripts: `article_generator.py`, `article_translator.py`, and `publish_external.py`

Additional env vars used by `publish_article.py` and the fetcher-api `/publish/website` endpoint (not in `.env.example`):
- `MD_DIR` — path to output markdown articles (default: `F:/Programming/analytic_gold/output` locally, `/app/output` in Docker)
- `GIF_DIR` — path to `article_gifs/` directory (default: `F:/Programming/analytic_gold/article_gifs` locally, `/app/article_gifs` in Docker)
- `WEBSITE_ROOT` — path to goldprice.trade website root (default: `F:/Programming/goldprice.trade/website` locally, `/website` in Docker — see volume mount in `docker-compose.yml`)

**Gotcha**: `.env.example` has `WEBSITE_HOST_PATH` but `publish_article.py` reads `WEBSITE_ROOT`. The `.env.example` variable name is unused — set `WEBSITE_ROOT` directly in `.env`.

All Python dependencies are in `fetcher_api/requirements.txt` — this single file covers the entire project (fetchers, analyzer, shorts pipeline).

**Ollama prerequisite**: article generation requires Ollama running locally at `http://localhost:11434`. The fetcher-api container reaches it via `http://host.docker.internal:11434`.

`config.json` also stores DB credentials, n8n API key, and the **Banxico SIE API token** (`["banxico"]["token"]`). **Do not commit `.env` or `config.json`** — config.json currently contains plaintext credentials, an n8n JWT, and the Banxico token.

## DB Name Gotcha

There are **two different DB names** in use — keep them in sync:

| Context | DB name |
|---------|---------|
| PostgreSQL container default (`POSTGRES_DB`) | `analytic_gold` |
| Python scripts / fetcher-api default (`DB_NAME`) | `gold_analytics` |

The postgres container creates the `analytic_gold` database, but all Python code (fetchers, `data_collector.py`, `init_db.py`) defaults to connecting to `gold_analytics`. The fetcher-api container also hardcodes `DB_NAME=gold_analytics`. Set `DB_NAME` in `.env` to whichever DB you actually created, and set `POSTGRES_DB` in `.env` to match.

Additionally, `docker-compose.yml` hardcodes `DB_USER=postgres / DB_PASSWORD=gold_price` for the fetcher-api container environment, while the postgres container defaults to `POSTGRES_USER=analytic_gold` and `.env.example` uses `analytic_gold / your-secure-password`. Keep these in sync or override via `.env`.

## Architecture: Data Flow

```
n8n (cron 18:00 UTC Mon–Fri)
  → HTTP POST to Fetcher API (fetcher_api/main.py, port 8000)
    → 12 data fetchers (9 core in data_sources/ + 3 locale in data_sources/locale_data/)
      → PostgreSQL (9 core schemas + 3 locale schemas)

article_generator.py
  → data_collector.py (reads all schemas, computes TA indicators)
  → article_gifs/render_all.py (optional) → article_gifs/out/manifest_<date>.json
  → Ollama (qwen3.5:latest, local) or Claude API
  → output/gold_analysis_YYYY-MM-DD_en.md (GIFs injected inline) + articles DB table

article_translator.py  (optional, run after article_generator.py)
  → Ollama → output/gold_analysis_YYYY-MM-DD_<lang>.md  (es, pt, ru)

publish_article.py  (run after article_generator.py + article_translator.py)
  → reads output/gold_analysis_YYYY-MM-DD_{en,es,pt,ru}.md
  → converts markdown → full HTML pages (with SEO, hreflang, schema.org, broker section)
  → writes to WEBSITE_ROOT/{cc}/analytics/{slug}/index.html for 11 locales
  → updates analytics/index.html listings, landing page block4, app-{cc}.v2.js React lists, sitemap.xml
  → copies GIFs from article_gifs/out/ to website/assets/gifs/{date}/

YouTube Shorts (Remotion block architecture — see section below)
  → Python fetch_*.py scripts → public/data.json per block
  → npx remotion render → per-block MP4
  → assemble.py (moviepy) → youtube_shorts/out/gold_short.mp4
  → generate_voice.py (Claude API + edge-tts) → voice.mp3
```

## Key Architecture Notes

- **Each data fetcher is independent**: lives in `data_sources/<name>/fetcher.py` with its own `schema.sql`. Fetchers do incremental upserts — they check the latest timestamp in DB before fetching.
- **Fetcher API** (`fetcher_api/main.py`) wraps all fetchers as HTTP endpoints, spawning each as a subprocess. n8n calls these endpoints; `/fetch/all` runs them sequentially (not parallel). Per-fetcher timeouts range 60–300s. The API also exposes `/shorts/render/{block}/{date}`, `/shorts/assemble`, `/shorts/voice`, `/shorts/description`, `/generate/article`, `/generate/translations`, `/gifs/render/{block}/{date}`, `/gifs/render/all/{date}`, and `/publish/website` — all callable from n8n or directly via Swagger UI at `http://localhost:8000/docs`. **Note**: there are no separate `/shorts/fetch/*` endpoints — data fetching for shorts blocks happens internally within `/shorts/render/{block}/{date}` before rendering.
- **data_collector.py** is the analysis hub: reads all core DB schemas, computes TA indicators (SMA 20/50/200, RSI, MACD, Bollinger Bands, ATR), and returns a structured `context` dict used by `article_generator.py`. Run it standalone to debug data issues.
- **Article generation** uses Ollama by default (`qwen3.5:latest`). The `think=False` flag disables Qwen3's chain-of-thought. To use Claude API instead, change the `ollama.chat` call in `article_generator.py` to use the Anthropic SDK. The system prompt explicitly forbids markdown tables, but Qwen3.5 occasionally generates them anyway — treat table output as a soft model quirk, not a code bug.
- **Translation GIF preservation**: `article_translator.py` extracts all `![...](...)` image lines from the English article before sending sections to Ollama, then reinserts them after translation at the same relative positions. This prevents Ollama from corrupting or omitting GIF embeds. If translated articles are missing GIFs, check that the EN source article had them inline before translation ran.
- **YouTube Shorts** uses a **Remotion block architecture** — see section below.
- **n8n workflows** are stored in `n8n/workflows/` — import `master_analytic.json` (main daily pipeline) and `video_generation.json` (shorts pipeline) into n8n on first setup.

## Publication Pipeline

`publish_article.py` converts the generated markdown articles into full HTML pages and deploys them to the goldprice.trade website. It requires `WEBSITE_ROOT` to point to the website repository.

**What it does per run:**
1. Reads `output/gold_analysis_{date}_{lang}.md` for EN, ES, PT, RU
2. Copies GIFs from `article_gifs/out/` to `website/assets/gifs/{date}/`
3. For each of 11 locales (EN root + 8 ES country variants + PT-BR + RU-KZ):
   - Generates a URL slug from the article title
   - Converts markdown to HTML, injects GIFs and internal links
   - Builds a full HTML page (header/footer extracted from the locale's `index.html`)
   - Writes `website/{cc}/analytics/{slug}/index.html`
   - Prepends entry to `analytics/index.html`, landing page block4, and `app-{cc}.v2.js` React list (max 3 shown)
4. Appends all new URLs to `sitemap.xml`
5. Syncs all locale JS files from their HTML counterparts (safety net for drift)

**Via API:** `POST /publish/website?date=YYYY-MM-DD` (omit date to default to today)

**Gotcha**: `publish_article.py` has an `OLD_SLUG_TO_REMOVE` variable at the top — clear it to `''` between runs or it will delete previously published articles.

**GIF injection in publish_article.py**: If GIFs are already embedded inline in the markdown (from `article_generator.py`), `publish_article.py` skips re-injecting them to avoid duplicates. It resolves GIF paths from `manifest_{date}.json`, preferring the mobile variant for web pages.

## YouTube Shorts Block Architecture

Each block is a self-contained **Remotion** (React/TypeScript) project under `youtube_shorts/<block-name>/`. The pipeline is:

1. **Python data fetchers** — each block has a `fetch_*.py` that queries PostgreSQL and writes `public/data.json` inside the block directory. Remotion reads this file at render time.
2. **Remotion render** — `npx remotion render <Comp> out/<name>.mp4` (or `render.sh`) renders the block to 1080×1920 MP4. The render endpoint runs `npm install` fresh each time (removes `node_modules` first), so first renders are slow.
3. **Assembly** — `youtube_shorts/assemble.py` (moviepy) concatenates all block MP4s into `youtube_shorts/out/gold_short.mp4`.
4. **Voiceover** — `youtube_shorts/voice/generate_voice.py` reads all blocks' `public/data.json`, calls Claude API for a script, then uses `edge-tts` to produce `voice.mp3`.
5. **Description** — `youtube_shorts/description/generate_description.py` reads block data and outputs an upload-ready markdown file.

**Current blocks** (in assembly order):

| Block dir | Duration | Remotion comp | Data fetcher |
|-----------|----------|---------------|--------------|
| `rolling-candles` | ~29s | `RollingCandles` | `fetch_hourly.py` (hourly OHLCV + stat_data) |
| `correlated-assets` | ~10s | `CorrelatedAssets` | `fetch_correlated.py` |
| `technical-indicators` | ~13s | `TechnicalIndicators` | `fetch_technicals.py` |
| `cta` | — | `CTA` | static |

`stat_overview/` has no Remotion render — `fetch_stats.py` is data-only and writes to `rolling-candles/public/stat_data.json` so both the video block and the article pipeline share identical numbers. The shorts fetch scripts accept a `--date YYYY-MM-DD` argument; when called via the API, the date is auto-computed as the last fully closed trading day from DB.

**Adding a new block:** create `youtube_shorts/<name>/` as a Remotion project with its own `package.json`, a `fetch_<name>.py` that populates `public/data.json`, and add the rendered MP4 path to the `BLOCKS` list in `assemble.py`.

## Article GIFs

Alongside the YouTube Shorts pipeline there is a second Remotion-based system that generates animated GIFs embedded in the markdown articles. It lives in `article_gifs/<block-name>/` and follows the same pattern as Shorts blocks.

**Current GIF blocks** — each block has two Remotion compositions (desktop + mobile):

| Block | Desktop comp (1200×400) | Mobile comp (800×800) | Data fetcher |
|-------|-------------------------|-----------------------|--------------|
| `price-chart` | `PriceChart` | `PriceChartSquare` | `fetch_price_chart.py` |
| `technical-dashboard` | `TechnicalDashboard` | `TechnicalDashboardSquare` | `fetch_technical_dashboard.py` |
| `correlated-heatmap` | `CorrelatedHeatmap` | `CorrelatedHeatmapSquare` | `fetch_correlated_heatmap.py` |

GIFs are rendered at 15 fps, codec=gif, 3 loops. `render_all.py` writes a manifest to `article_gifs/out/manifest_<date>.json`; `article_generator.py` reads this manifest to inject GIF embeds into the article. The manifest format is nested: `{"gifs": {"price-chart": {"desktop": "path", "mobile": "path"}}}`.

GIF injection positions in the article:
- `price-chart` → inserted **before** `## Executive Summary`
- `technical-dashboard` → inserted **after** `## Technical Analysis`
- `correlated-heatmap` → inserted **after** `## Correlated Assets`

The fetcher API exposes:
- `POST /gifs/render/{block}/{date}` — fetch data + render a single block using the **desktop** composition (1200×400); updates `manifest_{date}.json`
- `POST /gifs/render/all/{date}?format=mobile|desktop|all` — run `render_all.py` sequentially (timeout 1200s); defaults to `mobile`

Unlike Shorts renders, GIF blocks **skip `npm install` if `node_modules` already exists**, so subsequent renders are faster.

```bash
# Render all GIFs for a date — defaults to mobile variant
python article_gifs/render_all.py --date 2026-04-14
# Render both desktop and mobile variants
python article_gifs/render_all.py --date 2026-04-14 --format all
# Render a single chart
python article_gifs/render_all.py --date 2026-04-14 --charts price-chart
```

## Data Sources

**Core schemas (9):**

| Schema | Source | Data |
|--------|--------|------|
| `gold_prices` | yfinance | XAU/USD daily + hourly OHLCV |
| `correlated_assets` | yfinance | DXY, US10Y, WTI, Silver, SPX, VIX |
| `news` | yfinance (GLD/IAU/GC=F) | Deduplicated news articles |
| `economic_calendar` | Manual/scraped | Upcoming economic releases |
| `fed_rates` | FRED API | Fed Funds Rate, CPI, yields, spreads |
| `cot_report` | CFTC | Weekly gold futures positioning (downloads ZIP per year) |
| `etf_flows` | yfinance | GLD/IAU holdings |
| `central_bank` | WGC data | Gold reserves by country |
| `articles` (public) | Generated | Article archive |

**Locale-specific schemas (3 — `data_sources/locale_data/`):**

| API endpoint | Fetcher | Data |
|---|---|---|
| `locale/fx-rates` | `fetcher_fx_rates.py` | FX rates for each of the 11 locale currencies |
| `locale/macro` | `fetcher_macro.py` | World Bank macro indicators per country |
| `locale/central-bank-rates` | `fetcher_central_bank_rates.py` | Central bank policy rates via native APIs |

**Central bank rate sources** (per locale):

| Locale | Source | Auth |
|--------|--------|------|
| US (en) | FRED `FEDFUNDS` | `FRED_API_KEY` in `.env` |
| BR | BCB SGS series 432 (SELIC) | none |
| MX | Banxico SIE `SF61745` | token in `config.json ["banxico"]["token"]` |
| PE | BCRP series `PD04736PD` | none |
| AR | BIS `WS_CBPOL` monthly | none (lags ~11 months) |
| CL | BIS `WS_CBPOL` monthly | none |
| CO | BIS `WS_CBPOL` monthly | none |
| PA | mirrors US (dollarized) | — |
| CR/KZ/UY | no reliable free API | stored as null |

If the Banxico token expires, the fetcher logs a warning and stores null for MX without aborting. Update `config.json ["banxico"]["token"]` and re-run.

`fetcher_news.py` exists in `locale_data/` but is not wired into the API. Run locale fetchers directly with `python data_sources/locale_data/fetcher_fx_rates.py`, etc., or via `/fetch/locale/fx-rates` API endpoint.
