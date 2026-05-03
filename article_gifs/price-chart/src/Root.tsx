import React from "react";
import { Composition } from "remotion";
import { PriceChart } from "./PriceChart";
import { PriceChartSquare } from "./PriceChartSquare";
import data from "../public/data.json";

// 6 seconds at 15fps
const TOTAL_FRAMES = 90;

const defaultProps = {
  date:          data.date,
  date_from:     data.date_from,
  current_price: data.current_price,
  candles:       data.candles,
  sma20:         data.sma20,
  sma50:         data.sma50,
  sma200:        data.sma200,
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="PriceChart"
        component={PriceChart}
        durationInFrames={TOTAL_FRAMES}
        fps={15}
        width={1200}
        height={400}
        defaultProps={defaultProps}
      />
      <Composition
        id="PriceChartSquare"
        component={PriceChartSquare}
        durationInFrames={TOTAL_FRAMES}
        fps={15}
        width={800}
        height={800}
        defaultProps={defaultProps}
      />
    </>
  );
};
