import React from "react";
import { Composition } from "remotion";
import { TechnicalIndicators } from "./TechnicalIndicators";
import data from "../public/data.json";

// 13 seconds: 30 header + 88 rows stagger + 272 hold = 390 frames
const TOTAL_FRAMES = 390;

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="TechnicalIndicators"
      component={TechnicalIndicators}
      durationInFrames={TOTAL_FRAMES}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        date:          data.date,
        current_price: data.current_price,
        trend:         data.trend,
        rsi:           data.rsi,
        macd:          data.macd,
        macd_signal:   data.macd_signal,
        macd_hist:     data.macd_hist,
        hist_series:   data.hist_series,
        sma20:         data.sma20,
        sma50:         data.sma50,
        sma200:        data.sma200,
        bb_upper:      data.bb_upper,
        bb_mid:        data.bb_mid,
        bb_lower:      data.bb_lower,
        bb_pct:        data.bb_pct,
        atr:           data.atr,
        atr_pct:       data.atr_pct,
      }}
    />
  );
};
