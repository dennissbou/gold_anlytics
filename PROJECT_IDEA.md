# Automated Gold Trading Article Generator

## Project Overview

A fully automated pipeline that generates professional trading articles about XAU/USD (Gold).
Articles cover price prediction, technical analysis, and trade ideas for the nearest future.

**Target publication platforms:** TradingView, trading blogs

---

## Final Product

A generated article containing:
- Gold price prediction for the upcoming week
- Technical analysis of XAU/USD
- Trade ideas (entry, direction, reasoning)
- Context from economic news and correlated instruments

---

## Data Sources

| Source | Description | Priority |
|--------|-------------|----------|
| Historical gold prices | OHLCV data for XAU/USD (90–180 days daily) | Critical |
| Recent price updates | Last week / last day price movements | Critical |
| Correlated instruments | DXY, US10Y yield, WTI Oil, Silver (XAG/USD), S&P 500, VIX | Critical |
| Economic news | Last 7 days of gold-relevant headlines (USD strength, inflation, geopolitics, Fed) | Critical |
| Economic calendar | Upcoming high-impact events: CPI, NFP, FOMC, GDP, PPI, Treasury auctions | Critical |
| Fed / rates context | Current Fed funds rate, last FOMC statement, rate expectations (CME FedWatch) | High |
| Central bank activity | Gold reserve buying/selling by major central banks (China, India, etc.) | High |
| COT report | CFTC Commitments of Traders — speculative net longs/shorts in gold futures (weekly) | Medium |
| Gold ETF flows | Weekly inflows/outflows for GLD and IAU ETFs | Medium |
| News sentiment score | Bullish/Bearish/Neutral score derived from recent gold-related news | Medium |

---

## Pipeline

```
1. Fetch Data
   ├── Historical XAU/USD prices (OHLCV)
   ├── Latest price updates (last week, last day)
   ├── Recent impactful news (gold-related)
   └── Upcoming economic events (calendar)

2. Store Data
   └── Save everything to database (structured for analysis)

3. Analyze
   ├── Technical analysis (trends, support/resistance, indicators)
   ├── Fundamental analysis (news sentiment, economic context)
   └── Correlation analysis (DXY, bonds, oil, silver)

4. Generate Article
   └── AI-written article with prediction + trade idea
```

---

## Pipeline Steps — Detail

### Step 1: Data Collection
- **Price data:** XAU/USD daily OHLCV (90–180d) via yfinance / MetalPriceAPI / Alpha Vantage
- **Correlated assets:** DXY, US10Y yield, WTI Oil, Silver (XAG/USD), S&P 500, VIX — via yfinance
- **Economic news:** Last 7 days of gold-relevant headlines via NewsAPI / web scraping (Reuters, Bloomberg, Investing.com)
- **Economic calendar:** Next 7–10 days, high-impact events — Forex Factory scraper / Investing.com API
- **Fed/rates context:** Current Fed funds rate + FOMC statement summary; CME FedWatch for rate probabilities
- **Central bank gold activity:** World Gold Council reports or manual/scraped data (monthly cadence)
- **COT report:** CFTC weekly data (Gold Futures, non-commercial net positioning) — CFTC website or Quandl
- **ETF flows:** GLD / IAU weekly flow data — ETF provider websites or financial data APIs

### Step 2: Storage
- Database: PostgreSQL
- Tables: `prices`, `correlated_prices`, `news`, `economic_events`, `cot_data`, `etf_flows`, `fed_context`, `generated_articles`

### Step 3: Analysis
- **Technical:** SMA 20/50/200, RSI 14, MACD, Bollinger Bands, ATR, key S/R levels (swing highs/lows)
- **Fundamental:** Summarize relevant news, assess upcoming event risk (CPI/NFP/FOMC weight)
- **Sentiment:** Bullish / Bearish / Neutral score from news headlines (keyword-based or LLM-scored)
- **Macro/positioning:** COT net speculative positioning trend, ETF flow direction, Fed rate trajectory
- **Correlation check:** DXY vs gold divergence/convergence, US10Y vs gold relationship current state

### Step 4: Content Generation
- Use Claude API (or OpenAI) to generate the article
- Prompt includes: technical summary, news context, economic events, correlated data
- Output: structured article (intro, analysis, prediction, trade idea, conclusion)

---

## Tech Stack (Proposed)

| Component | Tool / Library |
|-----------|----------------|
| Language | Python |
| Price data | yfinance / MetalPriceAPI / Alpha Vantage |
| Correlated assets | yfinance (DXY, US10Y, Oil, Silver, SPX, VIX) |
| News | NewsAPI / web scraping (BeautifulSoup, Reuters, Investing.com) |
| Economic calendar | Forex Factory scraper / Investing.com API |
| COT data | CFTC website scraper / Quandl / nasdaq-data-link |
| ETF flows | GLD/IAU provider pages scraper or financial API |
| Fed/rates data | CME FedWatch scraper / FRED API (Federal Reserve Economic Data) |
| Database | PostgreSQL |
| Analysis | pandas, ta-lib, numpy |
| AI generation | Claude API (claude-sonnet-4-6) |
| Scheduling | cron job / APScheduler |
| Output | Markdown / HTML article file |

---

## MVP Scope

1. Fetch XAU/USD daily prices (last 90 days)
2. Fetch correlated assets: DXY, US10Y, Silver, Oil, S&P 500 (last 90 days)
3. Pull top 5–10 recent gold-related news headlines + basic sentiment score
4. Get next week's economic events (high-impact: CPI, NFP, FOMC)
5. Fetch current Fed funds rate and last FOMC decision summary
6. Run technical analysis (SMA 20/50/200, RSI, MACD, key S/R levels)
7. Generate a structured article using Claude API
8. Save article as Markdown file ready for publishing

> COT data and ETF flows are post-MVP — useful but harder to source reliably.

---

## Future Enhancements

- Auto-post to TradingView via API or browser automation
- Add chart image generation (matplotlib / mplfinance)
- Multi-language article output
- Performance tracking (compare predictions vs actual price)
- Web dashboard to review and approve articles before publishing

DB_HOST=127.0.0.1                                                            DB_PORT=5432                                                            
DB_NAME=gold_analytics                                                       DB_USER=postgres                                                        
DB_PASSWORD=gold_price    
