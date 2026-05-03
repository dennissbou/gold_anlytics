import React from "react";
import { Composition } from "remotion";
import { RollingCandles } from "./RollingCandles";
import data from "../public/data.json";
import statData from "../public/stat_data.json";

// Timing: 8 intro + 24 candles × 7 frames + 90 hold = 266 frames ≈ 8.9s
const TOTAL_FRAMES = 266;

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="RollingCandles"
      component={RollingCandles}
      durationInFrames={TOTAL_FRAMES}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        candles: data.candles,
        prev_candles: data.prev_candles ?? [],
        title: "XAUUSD · 24H",
        date: data.date,
        change_pct: data.change_pct,
        week_pct: statData.week_pct,
        week_series: statData.week_series,
        month_pct: statData.month_pct,
        month_series: statData.month_series,
        support: statData.support,
        resistance: statData.resistance,
      }}
    />
  );
};
