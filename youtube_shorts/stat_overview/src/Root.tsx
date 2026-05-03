import React from "react";
import { Composition } from "remotion";
import { StatOverview } from "./StatOverview";
import data from "../public/data.json";

// 10 seconds: 30 header + 75 rows stagger + 195 hold = 300 frames
const TOTAL_FRAMES = 300;

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="StatOverview"
      component={StatOverview}
      durationInFrames={TOTAL_FRAMES}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        date: data.date,
        current_price: data.current_price,
        week_pct: data.week_pct,
        week_series: data.week_series,
        month_pct: data.month_pct,
        month_series: data.month_series,
        support: data.support,
        resistance: data.resistance,
      }}
    />
  );
};
