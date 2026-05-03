#!/usr/bin/env python3
"""
Generates a voiceover script + MP3 for the gold YouTube Short.

Reads data from each block's public/data.json, calls Claude API to write
a concise spoken narration highlighting key moments, then converts to speech.

Outputs:
  youtube_shorts/voice/voice_script.txt  -- the full generated script
  youtube_shorts/voice/voice.mp3         -- TTS audio of the script

Usage:
    python youtube_shorts/voice/generate_voice.py

━━━ VOICE OPTIONS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Change VOICE below to any edge-tts voice name.

Popular choices:
  en-US-GuyNeural         US male, clear & professional  ← default
  en-US-ChristopherNeural US male, deep & authoritative
  en-US-EricNeural        US male, warm
  en-US-JennyNeural       US female, friendly newscast
  en-US-AriaNeural        US female, expressive
  en-GB-RyanNeural        British male, calm
  en-GB-SoniaNeural       British female, confident
  en-AU-WilliamNeural     Australian male

RATE adjusts speed: "+0%" normal, "+10%" faster, "-10%" slower
PITCH adjusts pitch: "+0Hz" normal, "+5Hz" higher, "-5Hz" lower

List all available voices:
    python -m edge_tts --list-voices
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import json
import os
from pathlib import Path
from datetime import datetime

import anthropic
import edge_tts
from dotenv import load_dotenv

# ─── Voice config ─────────────────────────────────────────────────────────────
VOICE = "en-US-GuyNeural"   # change this to switch voice
RATE  = "+0%"               # speech speed
PITCH = "+0Hz"              # voice pitch

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent          # youtube_shorts/
OUT  = Path(__file__).parent                  # youtube_shorts/voice/

def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)

# ─── Load all block data ──────────────────────────────────────────────────────
def collect_data() -> dict:
    candle_data = load_json(ROOT / "rolling-candles" / "public" / "data.json")
    stat_data   = load_json(ROOT / "rolling-candles" / "public" / "stat_data.json")
    corr_data   = load_json(ROOT / "correlated_assets" / "public" / "data.json")
    tech_data   = load_json(ROOT / "technical_indicators" / "public" / "data.json")

    # Intraday candles summary
    candles = candle_data.get("candles", [])
    intraday_high  = max(c["high"]  for c in candles) if candles else None
    intraday_low   = min(c["low"]   for c in candles) if candles else None
    intraday_range = round(intraday_high - intraday_low, 1) if candles else None

    # Notable intraday move (biggest single-candle swing)
    biggest_move = max(candles, key=lambda c: abs(c["close"] - c["open"])) if candles else None

    # Correlated assets
    assets = {a["symbol"]: a for a in corr_data.get("assets", [])}

    return {
        "date":           candle_data.get("date"),
        "open":           candle_data.get("open_price"),
        "close":          candle_data.get("close_price"),
        "high":           candle_data.get("high"),
        "low":            candle_data.get("low"),
        "change_pct":     candle_data.get("change_pct"),
        "intraday_range": intraday_range,
        "biggest_candle_hour":  biggest_move["hour"] if biggest_move else None,
        "biggest_candle_move":  round(biggest_move["close"] - biggest_move["open"], 1) if biggest_move else None,
        "week_pct":       stat_data.get("week_pct"),
        "month_pct":      stat_data.get("month_pct"),
        "support":        stat_data.get("support"),
        "resistance":     stat_data.get("resistance"),
        "current_price":  stat_data.get("current_price"),
        # Technicals
        "rsi":            tech_data.get("rsi"),
        "macd_hist":      tech_data.get("macd_hist"),
        "trend":          tech_data.get("trend"),
        "sma20":          tech_data.get("sma20"),
        "sma200":         tech_data.get("sma200"),
        "bb_pct":         tech_data.get("bb_pct"),
        "atr":            tech_data.get("atr"),
        # Correlated
        "dxy_pct":        assets.get("DXY", {}).get("change_pct"),
        "spx_pct":        assets.get("SPX", {}).get("change_pct"),
        "wti_pct":        assets.get("WTI", {}).get("change_pct"),
        "silver_pct":     assets.get("SILVER", {}).get("change_pct"),
        "btc_pct":        assets.get("BTC",  {}).get("change_pct"),
        "vix_close":      assets.get("VIX",  {}).get("close"),
    }

# ─── Generate script via Claude ───────────────────────────────────────────────
SYSTEM_PROMPT = """\
You write short, punchy voiceover scripts for a 40-second gold trading YouTube Short.
Rules:
- Plain spoken English, no markdown, no bullet points, no headers
- Total length: 120-150 words (fits ~40s at normal speech pace)
- Cover exactly 4 moments in order: (1) daily price action, (2) intraday highlight,
  (3) weekly/monthly context, (4) technical read + what to watch
- Each moment is 1-2 sentences
- Use natural transitions ("meanwhile", "zooming out", "on the technicals")
- Round all prices to whole numbers, use % with one decimal
- End with a single call-to-action sentence about following for daily updates
"""

def generate_script(data: dict) -> str:
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env")

    client = anthropic.Anthropic(api_key=api_key)

    user_msg = f"""
Date: {data['date']}
Gold price: ${data['close']:,.0f} (open ${data['open']:,.0f}, change {data['change_pct']:+.1f}%)
Intraday high: ${data['high']:,.0f}, low: ${data['low']:,.0f}, range: ${data['intraday_range']}
Biggest intraday candle: {data['biggest_candle_hour']} hour, move {data['biggest_candle_move']:+.1f}
Week: {data['week_pct']:+.1f}%  |  Month: {data['month_pct']:+.1f}%
Support: ${data['support']:,.0f}  |  Resistance: ${data['resistance']:,.0f}
RSI: {data['rsi']}  |  MACD histogram: {data['macd_hist']:.1f}  |  Trend: {data['trend']}
SMA20: ${data['sma20']:,.0f}  |  SMA200: ${data['sma200']:,.0f}
Bollinger %B: {data['bb_pct']}%  |  ATR: ${data['atr']}
DXY: {data['dxy_pct']:+.1f}%  |  SPX: {data['spx_pct']:+.1f}%  |  WTI: {data['wti_pct']:+.1f}%
Silver: {data['silver_pct']:+.1f}%  |  BTC: {data['btc_pct']:+.1f}%  |  VIX: {data['vix_close']:.1f}
"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg.strip()}],
    )
    return message.content[0].text.strip()


# ─── Text-to-speech ───────────────────────────────────────────────────────────
async def _synthesize_async(text: str, out_path: Path):
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH)
    await communicate.save(str(out_path))

def synthesize(text: str, out_path: Path):
    asyncio.run(_synthesize_async(text, out_path))


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("Loading block data...")
    data = collect_data()

    date_str = data["date"] or datetime.today().strftime("%Y-%m-%d")
    print(f"Date: {date_str}  |  Price: ${data['close']:,.0f}  ({data['change_pct']:+.1f}%)")

    print("\nGenerating script via Claude...")
    script = generate_script(data)

    script_path = OUT / "voice_script.txt"
    audio_path  = OUT / "voice.mp3"

    script_path.write_text(script, encoding="utf-8")
    print("\n" + "-"*60)
    print(script)
    print("-"*60)
    print(f"\nSaved text  -> {script_path}")

    print("Synthesizing audio...")
    synthesize(script, audio_path)
    size_kb = audio_path.stat().st_size // 1024
    print(f"Saved audio -> {audio_path}  ({size_kb} KB)")


if __name__ == "__main__":
    main()
