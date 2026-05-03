#!/bin/bash
set -e

# Always run from the script's own directory
cd "$(dirname "$0")"

echo "📦 Installing dependencies..."
npm install

DATE=$(node -p "require('./public/stat_data.json').date" 2>/dev/null || echo "")
if [ -n "$DATE" ]; then
  OUT="out/rolling_candles_${DATE}.mp4"
else
  OUT="out/rolling_candles.mp4"
fi

echo "🎬 Rendering rolling candles Short → $OUT"
npx remotion render RollingCandles "$OUT" \
  --codec=h264 \
  --crf=18

echo ""
echo "✅ Done! → $OUT"
