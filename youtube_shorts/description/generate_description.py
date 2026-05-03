#!/usr/bin/env python3
"""
Generate a YouTube upload .md file for today's gold analysis Short.

Reads existing public/data.json files from each block — no DB queries.

Usage:
    python youtube_shorts/description/generate_description.py
    python youtube_shorts/description/generate_description.py --date 2026-03-27
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent  # youtube_shorts/


def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt_price(v: float) -> str:
    return f"${v:,.0f}"


def fmt_pct(v: float) -> str:
    return f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%"


def fmt_date(iso: str) -> str:
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%B %d, %Y")


def trend_emoji(v: float) -> str:
    return "📈" if v >= 0 else "📉"


def rsi_label(rsi: float) -> str:
    if rsi >= 70:
        return "Overbought"
    if rsi <= 30:
        return "Oversold"
    return "Neutral"


def main():
    # ── Load data from each block ──────────────────────────────────────────────
    candle   = load(ROOT / "rolling-candles"      / "public" / "data.json")
    stats    = load(ROOT / "stat_overview"         / "public" / "data.json")
    corr     = load(ROOT / "correlated_assets"     / "public" / "data.json")
    tech     = load(ROOT / "technical_indicators"  / "public" / "data.json")

    date_iso   = candle["date"]
    date_str   = fmt_date(date_iso)
    price      = candle["close_price"]
    change_pct = candle["change_pct"]
    day_high   = candle["high"]
    day_low    = candle["low"]
    week_pct   = stats["week_pct"]
    month_pct  = stats["month_pct"]
    support    = stats["support"]
    resistance = stats["resistance"]

    rsi        = tech["rsi"]
    trend      = tech["trend"].replace("trend", "-trend").title().replace("-Trend", "trend")
    sma20      = tech["sma20"]
    sma50      = tech["sma50"]
    sma200     = tech["sma200"]
    atr        = tech["atr"]
    atr_pct    = tech["atr_pct"]
    bb_upper   = tech["bb_upper"]
    bb_lower   = tech["bb_lower"]
    bb_pct     = tech["bb_pct"]

    assets = {a["symbol"]: a for a in corr["assets"]}

    # ── Title ──────────────────────────────────────────────────────────────────
    emoji = trend_emoji(change_pct)
    sign  = "+" if change_pct >= 0 else ""
    title = (
        f"Gold {fmt_price(price)} | {sign}{change_pct:.2f}% Today {emoji} | "
        f"XAU/USD Analysis {date_str}"
    )

    # ── Description ───────────────────────────────────────────────────────────
    def asset_line(sym: str, label: str) -> str:
        if sym not in assets:
            return ""
        a = assets[sym]
        return f"  {label}: {fmt_price(a['close'])} ({fmt_pct(a['change_pct'])})"

    corr_lines = "\n".join(filter(None, [
        asset_line("SILVER", "Silver (XAG/USD)"),
        asset_line("DXY",    "US Dollar (DXY) "),
        asset_line("WTI",    "Crude Oil (WTI) "),
        asset_line("SPX",    "S&P 500 (SPX)   "),
        asset_line("BTC",    "Bitcoin (BTC)   "),
        asset_line("VIX",    "Volatility (VIX)"),
    ]))

    description = f"""\
Gold price today: {fmt_price(price)} ({sign}{change_pct:.2f}%) {emoji}
Daily range: {fmt_price(day_low)} – {fmt_price(day_high)} | ATR: {fmt_price(atr)} ({atr_pct:.1f}%)

📊 PERFORMANCE
  Week:  {fmt_pct(week_pct)}
  Month: {fmt_pct(month_pct)}

📐 KEY LEVELS
  Support:    {fmt_price(support)}
  Resistance: {fmt_price(resistance)}
  SMA 20:     {fmt_price(sma20)}
  SMA 50:     {fmt_price(sma50)}
  SMA 200:    {fmt_price(sma200)}

🔬 TECHNICAL INDICATORS
  Trend:              {trend.capitalize()}
  RSI (14):           {rsi:.1f} — {rsi_label(rsi)}
  Bollinger Bands:    {fmt_price(bb_lower)} – {fmt_price(bb_upper)} (position: {bb_pct:.1f}%)

🔗 CORRELATED MARKETS
{corr_lines}

🌐 FULL ANALYSIS → goldprice.trade
Daily gold price charts, technical analysis, market context and more.
Free. No sign-up required.

─────────────────────────────────────────
⚠️ NOT FINANCIAL ADVICE
This video is for informational purposes only. Trading precious metals involves significant risk of loss. Always do your own research.
─────────────────────────────────────────

#gold #xauusd #goldprice #goldtrading #preciousmetals #technicalanalysis #forextrading #commodities #goldanalysis #trading #finance #investing #marketanalysis #goldmarket #xau"""

    # ── Tags ──────────────────────────────────────────────────────────────────
    tags = [
        "gold", "xauusd", "gold price", "gold price today", "gold trading",
        "gold analysis", "xau usd", "precious metals", "technical analysis",
        "forex", "commodities", "gold market", "gold chart", "trading",
        "investing", "finance", "market analysis", "gold forecast",
        "gold price prediction", "goldprice.trade",
    ]

    # ── Build markdown ─────────────────────────────────────────────────────────
    output_dir = Path(__file__).parent / "out"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"youtube_{date_iso}.md"

    content = f"""\
# YouTube Upload — {date_str}

## Title
```
{title}
```

## Description
```
{description}
```

## Tags
```
{", ".join(tags)}
```

## Checklist
- [ ] Thumbnail: use frame from `rolling-candles/out/` or `stat_overview/out/`
- [ ] Video file: `youtube_shorts/out/gold_short.mp4`
- [ ] Category: News & Politics  (or Finance)
- [ ] Playlist: Gold Price Analysis
- [ ] Made for kids: No
- [ ] Location: (optional)
- [ ] License: Standard YouTube License
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[DONE] {output_path}")
    safe_title = title.encode("ascii", errors="replace").decode("ascii")
    print(f"  Title: {safe_title}")
    print(f"  Tags:  {len(tags)}")


if __name__ == "__main__":
    main()
