import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { colors, fonts } from "./theme";

// ─── Types ────────────────────────────────────────────────
interface WeekPoint {
  label: string;  // "Mar 12"
  price: number;
  pct: number;
}

interface MonthPoint {
  label: string;  // "Feb 18"
  price: number;
  pct: number;
}

interface Props {
  date: string;
  current_price: number;
  week_pct: number;
  week_series: WeekPoint[];
  month_pct: number;
  month_series: MonthPoint[];
  support: number;
  resistance: number;
}

// ─── Timing ───────────────────────────────────────────────
const HEADER_IN   = 0;   // header fades in
const ROWS_START  = 30;  // rows stagger start
const ROW_STAGGER = 15;  // frames between each row

// ─── Component ────────────────────────────────────────────
export const StatOverview: React.FC<Props> = ({
  date,
  current_price,
  week_pct,
  week_series,
  month_pct,
  month_series,
  support,
  resistance,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Header opacity
  const headerOpacity = interpolate(frame, [HEADER_IN, HEADER_IN + 25], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Row animation factory
  const rowSpring = (rowIndex: number) =>
    spring({
      frame: frame - (ROWS_START + rowIndex * ROW_STAGGER),
      fps,
      config: { damping: 80, stiffness: 160, mass: 0.8 },
    });

  // Shared counter start — both counters begin at the same frame
  const COUNTER_START = ROWS_START + 20; // frame 50

  // Month counter: 30 steps × 7 frames = 210 frames total (sets the pace)
  const FRAMES_PER_MONTH_STEP = 7;
  const nm = month_series.length; // ~30
  const mPcts   = month_series.map((s) => s.pct);
  const mPrices = month_series.map((s) => s.price);
  const mLabels = month_series.map((s) => s.label);

  const MONTH_TOTAL_FRAMES = (nm - 1) * FRAMES_PER_MONTH_STEP; // 210 frames

  const monthProgress = Math.max(0, frame - COUNTER_START);
  const rawMonthStep = monthProgress / FRAMES_PER_MONTH_STEP;
  const monthStepClamped = Math.min(rawMonthStep, nm - 1);
  const monthStepIndex = Math.floor(monthStepClamped);
  const monthStepFrac  = monthStepClamped - monthStepIndex;

  const animatedMonthPct =
    monthStepIndex >= nm - 1
      ? mPcts[nm - 1]
      : mPcts[monthStepIndex] + (mPcts[monthStepIndex + 1] - mPcts[monthStepIndex]) * monthStepFrac;

  const animatedMonthPrice =
    monthStepIndex >= nm - 1
      ? mPrices[nm - 1]
      : mPrices[monthStepIndex] + (mPrices[monthStepIndex + 1] - mPrices[monthStepIndex]) * monthStepFrac;

  const animatedMonthLabel =
    monthStepIndex >= nm - 1 ? mLabels[nm - 1] : mLabels[monthStepIndex];

  // Week counter: synced to same total duration as month (210 frames / 7 steps = 30 frames/step)
  const n = week_series.length; // 7
  const FRAMES_PER_WEEK_STEP = MONTH_TOTAL_FRAMES / (n - 1); // 30 frames/step
  const pcts   = week_series.map((s) => s.pct);
  const prices = week_series.map((s) => s.price);
  const labels = week_series.map((s) => s.label);

  const weekProgress = Math.max(0, frame - COUNTER_START);
  const rawStep = weekProgress / FRAMES_PER_WEEK_STEP;
  const stepClamped = Math.min(rawStep, n - 1);
  const stepIndex = Math.floor(stepClamped);
  const stepFrac  = stepClamped - stepIndex;

  const animatedPct =
    stepIndex >= n - 1
      ? pcts[n - 1]
      : pcts[stepIndex] + (pcts[stepIndex + 1] - pcts[stepIndex]) * stepFrac;

  const animatedPrice =
    stepIndex >= n - 1
      ? prices[n - 1]
      : prices[stepIndex] + (prices[stepIndex + 1] - prices[stepIndex]) * stepFrac;

  const animatedLabel =
    stepIndex >= n - 1 ? labels[n - 1] : labels[stepIndex];

  const rowStyle = (rowIndex: number): React.CSSProperties => {
    const s = rowSpring(rowIndex);
    return {
      opacity: interpolate(s, [0, 1], [0, 1]),
      transform: `translateY(${interpolate(s, [0, 1], [40, 0])}px)`,
    };
  };

  // Formatted date
  const formattedDate = new Date(date + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  // Change badge
  const ChangeBadge = ({ value, suffix = "%" }: { value: number; suffix?: string }) => {
    const up = value >= 0;
    const sign = up ? "+" : "";
    return (
      <span style={{
        fontSize: 38,
        fontWeight: 800,
        fontFamily: fonts.main,
        color: up ? colors.green : colors.red,
        backgroundColor: up ? "rgba(249,219,109,0.15)" : "rgba(239,83,80,0.15)",
        border: `2px solid ${up ? "rgba(249,219,109,0.35)" : "rgba(239,83,80,0.35)"}`,
        borderRadius: 10,
        padding: "6px 22px",
      }}>
        {sign}{value.toFixed(2)}{suffix}
      </span>
    );
  };

  // Row template
  const StatRow = ({
    label,
    children,
    rowIndex,
  }: {
    label: string;
    children: React.ReactNode;
    rowIndex: number;
  }) => (
    <div
      style={{
        ...rowStyle(rowIndex),
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        backgroundColor: colors.surface,
        borderRadius: 18,
        padding: "32px 48px",
        borderLeft: `4px solid ${colors.gold}`,
      }}
    >
      <span style={{
        fontSize: 40,
        fontWeight: 500,
        fontFamily: fonts.main,
        color: colors.textSecondary,
        letterSpacing: 1,
      }}>
        {label}
      </span>
      {children}
    </div>
  );

  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg }}>

      {/* ─── Stats Card Area ──────────────────── */}
      <div style={{
        position: "absolute",
        top: 120,
        left: 60,
        right: 60,
        display: "flex",
        flexDirection: "column",
        gap: 24,
      }}>

        {/* Row 1: Month — animated counter through 30 daily checkpoints (1d increment) */}
        <StatRow label="Month" rowIndex={0}>
          {(() => {
            const up = animatedMonthPct >= 0;
            const sign = up ? "+" : "";
            const col = up ? colors.green : colors.red;
            const bg  = up ? "rgba(249,219,109,0.15)" : "rgba(239,83,80,0.15)";
            const bdr = up ? "rgba(249,219,109,0.35)" : "rgba(239,83,80,0.35)";
            return (
              <div style={{
                display: "flex",
                flexDirection: "row",
                alignItems: "center",
                backgroundColor: bg,
                border: `2px solid ${bdr}`,
                borderRadius: 12,
                padding: "12px 28px",
                gap: 18,
              }}>
                <span style={{ fontSize: 34, fontWeight: 800, fontFamily: fonts.main, color: col, lineHeight: 1 }}>
                  ${animatedMonthPrice.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                </span>
                <span style={{ fontSize: 26, fontWeight: 400, fontFamily: fonts.main, color: colors.textDim, lineHeight: 1 }}>|</span>
                <span style={{ fontSize: 32, fontWeight: 700, fontFamily: fonts.main, color: col, lineHeight: 1 }}>
                  {sign}{animatedMonthPct.toFixed(2)}%
                </span>
                <span style={{ fontSize: 26, fontWeight: 400, fontFamily: fonts.main, color: colors.textDim, lineHeight: 1 }}>|</span>
                <span style={{ fontSize: 24, fontWeight: 400, fontFamily: fonts.main, color: colors.textDim, lineHeight: 1 }}>
                  {animatedMonthLabel}
                </span>
              </div>
            );
          })()}
        </StatRow>

        {/* Row 2: Week — animated counter through 7 daily checkpoints */}
        <StatRow label="Week" rowIndex={1}>
          {(() => {
            const up = animatedPct >= 0;
            const sign = up ? "+" : "";
            const col = up ? colors.green : colors.red;
            const bg  = up ? "rgba(249,219,109,0.15)" : "rgba(239,83,80,0.15)";
            const bdr = up ? "rgba(249,219,109,0.35)" : "rgba(239,83,80,0.35)";
            return (
              <div style={{
                display: "flex",
                flexDirection: "row",
                alignItems: "center",
                backgroundColor: bg,
                border: `2px solid ${bdr}`,
                borderRadius: 12,
                padding: "12px 28px",
                gap: 18,
              }}>
                <span style={{ fontSize: 34, fontWeight: 800, fontFamily: fonts.main, color: col, lineHeight: 1 }}>
                  ${animatedPrice.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                </span>
                <span style={{ fontSize: 26, fontWeight: 400, fontFamily: fonts.main, color: colors.textDim, lineHeight: 1 }}>|</span>
                <span style={{ fontSize: 32, fontWeight: 700, fontFamily: fonts.main, color: col, lineHeight: 1 }}>
                  {sign}{animatedPct.toFixed(2)}%
                </span>
                <span style={{ fontSize: 26, fontWeight: 400, fontFamily: fonts.main, color: colors.textDim, lineHeight: 1 }}>|</span>
                <span style={{ fontSize: 24, fontWeight: 400, fontFamily: fonts.main, color: colors.textDim, lineHeight: 1 }}>
                  {animatedLabel}
                </span>
              </div>
            );
          })()}
        </StatRow>

        {/* Row 3: Support / Resistance range bar — marker tracks week_series prices */}
        {(() => {
          const barSpring = rowSpring(2);
          // Marker follows animatedPrice (week counter), clamped within bar bounds
          const markerPct = Math.max(0.02, Math.min(0.98,
            (animatedPrice - support) / (resistance - support)
          ));
          const fillWidth = markerPct * 100;
          const fmt = (v: number) =>
            "$" + v.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

          return (
            <div style={{
              ...rowStyle(3),
              backgroundColor: colors.surface,
              borderRadius: 18,
              padding: "32px 48px",
              borderLeft: `4px solid ${colors.gold}`,
              display: "flex",
              flexDirection: "column",
              gap: 20,
            }}>
              {/* Label row */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
                  <span style={{ fontSize: 22, fontWeight: 500, fontFamily: fonts.main, color: colors.textDim, letterSpacing: 2 }}>
                    SUPPORT
                  </span>
                  <span style={{ fontSize: 36, fontWeight: 700, fontFamily: fonts.main, color: colors.green }}>
                    {fmt(support)}
                  </span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                  <span style={{ fontSize: 22, fontWeight: 500, fontFamily: fonts.main, color: colors.textDim, letterSpacing: 2 }}>
                    RESISTANCE
                  </span>
                  <span style={{ fontSize: 36, fontWeight: 700, fontFamily: fonts.main, color: colors.red }}>
                    {fmt(resistance)}
                  </span>
                </div>
              </div>

              {/* Track */}
              <div style={{ position: "relative", height: 20, borderRadius: 10, backgroundColor: colors.surfaceLight }}>
                {/* Filled portion: support → current price */}
                <div style={{
                  position: "absolute",
                  left: 0,
                  top: 0,
                  height: "100%",
                  width: `${fillWidth}%`,
                  borderRadius: 10,
                  background: `linear-gradient(90deg, ${colors.green}55, ${colors.gold})`,
                }} />
                {/* Current price marker */}
                <div style={{
                  position: "absolute",
                  top: "50%",
                  left: `${markerPct * 100}%`,
                  transform: "translate(-50%, -50%)",
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  backgroundColor: colors.gold,
                  boxShadow: `0 0 12px ${colors.goldGlow}`,
                  opacity: interpolate(barSpring, [0.6, 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
                }} />
              </div>

              {/* Current price label under marker */}
              <div style={{ position: "relative", height: 36 }}>
                <div style={{
                  position: "absolute",
                  left: `${markerPct * 100}%`,
                  transform: "translateX(-50%)",
                  opacity: interpolate(barSpring, [0.6, 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
                  textAlign: "center",
                }}>
                  <span style={{ fontSize: 30, fontWeight: 700, fontFamily: fonts.main, color: colors.gold }}>
                    {fmt(animatedPrice)}
                  </span>
                </div>
              </div>
            </div>
          );
        })()}
      </div>

      {/* ─── Branding ────────────────────────── */}
      <div style={{
        position: "absolute",
        bottom: 60,
        left: 0,
        right: 0,
        textAlign: "center",
      }}>
        <span style={{
          fontSize: 28,
          fontWeight: 300,
          fontFamily: fonts.main,
          color: colors.gold,
          opacity: 0.5,
        }}>
          goldprice.trade
        </span>
      </div>

    </AbsoluteFill>
  );
};
