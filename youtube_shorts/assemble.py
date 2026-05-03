#!/usr/bin/env python3
"""
Assembles all Remotion block MP4s into a single YouTube Shorts video.

Block order:
  1. rolling-candles        (29s)
  2. correlated_assets      (10s)
  3. technical_indicators   (13s)

Usage:
    python youtube_shorts/assemble.py
"""

import json
import os
from pathlib import Path
from moviepy.editor import VideoFileClip, concatenate_videoclips

BASE = Path(__file__).parent

OUTPUT_DIR = BASE / "out"

# (folder, file_stem, dated) — dated=False means always use plain filename (static blocks)
BLOCK_NAMES = [
    ("rolling-candles",      "rolling_candles",      True),
    ("correlated_assets",    "correlated_assets",    True),
    ("technical_indicators", "technical_indicators", True),
    ("cta",                  "cta",                  False),
]

def _stat_date() -> str:
    stat_path = BASE / "rolling-candles" / "public" / "stat_data.json"
    try:
        return json.loads(stat_path.read_text())["date"]
    except Exception:
        return ""

def _dated_blocks(date: str) -> list[Path]:
    return [
        BASE / folder / "out" / (f"{name}_{date}.mp4" if (dated and date) else f"{name}.mp4")
        for folder, name, dated in BLOCK_NAMES
    ]

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    date = _stat_date()
    blocks = _dated_blocks(date)
    output_file = OUTPUT_DIR / (f"gold_short_{date}.mp4" if date else "gold_short.mp4")

    # Verify all blocks exist
    for path in blocks:
        if not path.exists():
            raise FileNotFoundError(f"Missing block: {path}")
        print(f"  ok  {path.parent.parent.name}  ({path.stat().st_size // 1024} KB)")

    print(f"\nLoading clips...")
    clips = [VideoFileClip(str(p)) for p in blocks]

    total_s = sum(c.duration for c in clips)
    print(f"Total duration: {total_s:.1f}s  ({len(clips)} blocks)\n")

    print("Concatenating...")
    final = concatenate_videoclips(clips, method="compose")

    print(f"Writing -> {output_file}")
    final.write_videofile(
        str(output_file),
        codec="libx264",
        audio=False,
        fps=30,
        preset="fast",
        ffmpeg_params=["-crf", "18"],
        logger="bar",
    )

    for c in clips:
        c.close()
    final.close()

    size_kb = output_file.stat().st_size // 1024
    print(f"\nDone.  {output_file.name}  ({size_kb} KB)  {total_s:.1f}s")


if __name__ == "__main__":
    main()
