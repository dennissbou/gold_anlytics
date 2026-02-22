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

| Source | Description |
|--------|-------------|
| Historical gold prices | OHLCV data for XAU/USD |
| Recent price updates | Last week / last day price movements |
| Economic news | Latest news that impacts gold (USD strength, inflation, geopolitics, Fed decisions) |
| Economic calendar | Upcoming scheduled events (CPI, NFP, FOMC, etc.) |
| Correlated instruments | DXY (Dollar Index), US10Y (bonds), oil, silver, S&P 500 |

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
- Price data: Fetch from API (e.g., Alpha Vantage, MetalPriceAPI, yfinance, or broker API)
- News: Scrape or use NewsAPI / financial news APIs (Bloomberg, Reuters, Investing.com)
- Economic calendar: Scrape Forex Factory, Investing.com calendar, or use an API
- Correlated assets: DXY, US10Y yield, WTI Oil, Silver (XAG/USD), S&P 500

### Step 2: Storage
- Database: PostgreSQL or SQLite
- Tables: prices, news, economic_events, correlated_assets

### Step 3: Analysis
- Technical: Moving averages, RSI, MACD, Bollinger Bands, key S/R levels
- Fundamental: Summarize relevant news, upcoming event risk
- Sentiment: Bullish / Bearish / Neutral score from news

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
| News | NewsAPI / web scraping (BeautifulSoup) |
| Economic calendar | Forex Factory scraper / Investing.com API |
| Database | PostgreSQL (or SQLite for MVP) |
| Analysis | pandas, ta-lib, numpy |
| AI generation | Claude API (claude-sonnet-4-6) |
| Scheduling | cron job / APScheduler |
| Output | Markdown / HTML article file |

---

## MVP Scope

1. Fetch XAU/USD daily prices (last 30 days)
2. Pull top 5 recent gold-related news headlines
3. Get next week's economic events (high-impact)
4. Run basic technical analysis (trend + RSI + key levels)
5. Generate a structured article using Claude API
6. Save article as Markdown file ready for publishing

---

## Future Enhancements

- Auto-post to TradingView via API or browser automation
- Add chart image generation (matplotlib / mplfinance)
- Multi-language article output
- Performance tracking (compare predictions vs actual price)
- Web dashboard to review and approve articles before publishing
