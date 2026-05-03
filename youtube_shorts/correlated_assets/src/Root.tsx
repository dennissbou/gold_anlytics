import React from "react";
import { Composition } from "remotion";
import { CorrelatedAssets } from "./CorrelatedAssets";
import data from "../public/data.json";

// 10 seconds: 20 header + 175 cards stagger + 105 hold = 300 frames
const TOTAL_FRAMES = 300;

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="CorrelatedAssets"
      component={CorrelatedAssets}
      durationInFrames={TOTAL_FRAMES}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        date:   data.date,
        assets: data.assets,
      }}
    />
  );
};
