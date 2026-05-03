import React from "react";
import { Composition } from "remotion";
import { TechnicalDashboard } from "./TechnicalDashboard";
import { TechnicalDashboardSquare } from "./TechnicalDashboardSquare";
import data from "../public/data.json";

// 4 seconds at 15fps
const TOTAL_FRAMES = 60;

const defaultProps = {
  date:          data.date,
  period:        data.period,
  current_price: data.current_price,
  rsi:           data.rsi,
  macd:          data.macd,
  macd_signal:   data.macd_signal,
  macd_hist:     data.macd_hist,
  hist_series:   data.hist_series,
  bb_upper:      data.bb_upper,
  bb_mid:        data.bb_mid,
  bb_lower:      data.bb_lower,
  bb_pct:        data.bb_pct,
  atr:           data.atr,
  atr_pct:       data.atr_pct,
  sma20:         data.sma20,
  sma50:         data.sma50,
  sma200:        data.sma200,
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="TechnicalDashboard"
        component={TechnicalDashboard}
        durationInFrames={TOTAL_FRAMES}
        fps={15}
        width={1200}
        height={400}
        defaultProps={defaultProps}
      />
      <Composition
        id="TechnicalDashboardSquare"
        component={TechnicalDashboardSquare}
        durationInFrames={TOTAL_FRAMES}
        fps={15}
        width={800}
        height={800}
        defaultProps={defaultProps}
      />
    </>
  );
};
