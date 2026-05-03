import React from "react";
import { Composition } from "remotion";
import { CorrelatedHeatmap } from "./CorrelatedHeatmap";
import { CorrelatedHeatmapSquare } from "./CorrelatedHeatmapSquare";
import data from "../public/data.json";

// 4 seconds at 15fps
const TOTAL_FRAMES = 60;

const defaultProps = {
  date:    data.date,
  period:  data.period,
  assets:  data.assets,
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="CorrelatedHeatmap"
        component={CorrelatedHeatmap}
        durationInFrames={TOTAL_FRAMES}
        fps={15}
        width={1200}
        height={400}
        defaultProps={defaultProps}
      />
      <Composition
        id="CorrelatedHeatmapSquare"
        component={CorrelatedHeatmapSquare}
        durationInFrames={TOTAL_FRAMES}
        fps={15}
        width={800}
        height={800}
        defaultProps={defaultProps}
      />
    </>
  );
};
