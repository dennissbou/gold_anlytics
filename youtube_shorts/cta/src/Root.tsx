import React from "react";
import { Composition } from "remotion";
import { CTA } from "./CTA";

// 5 seconds = 150 frames
export const RemotionRoot: React.FC = () => (
  <Composition
    id="CTA"
    component={CTA}
    durationInFrames={180}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={{}}
  />
);
