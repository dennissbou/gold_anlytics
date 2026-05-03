import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { colors, fonts } from "./theme";

// ─── Types ────────────────────────────────────────────────────────────────────
interface HistPoint {
  date: string;
  macd_hist: number;
}

interface Props {
  date: string;
  current_price: number;
  trend: string;
  rsi: number;
  macd: number;
  macd_signal: number;
  macd_hist: number;
  hist_series: HistPoint[];
  sma20: number;
  sma50: number;
  sma200: number;
  bb_upper: number;
  bb_mid: number;
  bb_lower: number;
  bb_pct: number;   // 0-100, where price sits in the BB range
  atr: number;
  atr_pct: number;  // atr as % of price
}

// ─── Timing ───────────────────────────────────────────────────────────────────
const HEADER_IN   = 0;
const ROWS_START  = 30;
const ROW_STAGGER = 22;

// RSI gauge fills from 0 → rsi over 80 frames
const RSI_ANIM_START = ROWS_START + 8;
const RSI_ANIM_END   = RSI_ANIM_START + 80;

// MACD histogram bars appear after the MACD card row slides in
const MACD_HIST_START = ROWS_START + ROW_STAGGER + 18;
const MACD_HIST_END   = MACD_HIST_START + 70;

// BB marker animates to position after BB row enters
const BB_MARKER_START = ROWS_START + 2 * ROW_STAGGER + 22;
const BB_MARKER_END   = BB_MARKER_START + 80;

// ─── Component ────────────────────────────────────────────────────────────────
export const TechnicalIndicators: React.FC<Props> = ({
  date,
  current_price,
  trend,
  rsi,
  macd,
  macd_signal,
  macd_hist,
  hist_series,
  sma20,
  sma50,
  sma200,
  bb_upper,
  bb_mid,
  bb_lower,
  bb_pct,
  atr,
  atr_pct,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Header fade-in
  const headerOpacity = interpolate(frame, [HEADER_IN, HEADER_IN + 25], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Row spring factory (slide-up + fade)
  const rowSpring = (rowIndex: number) =>
    spring({
      frame: frame - (ROWS_START + rowIndex * ROW_STAGGER),
      fps,
      config: { damping: 80, stiffness: 160, mass: 0.8 },
    });

  const rowStyle = (rowIndex: number): React.CSSProperties => {
    const s = rowSpring(rowIndex);
    return {
      opacity: interpolate(s, [0, 1], [0, 1]),
      transform: `translateY(${interpolate(s, [0, 1], [40, 0])}px)`,
    };
  };

  // RSI gauge: animate fill width from 0 to rsi/100
  const animatedRsi = interpolate(frame, [RSI_ANIM_START, RSI_ANIM_END], [0, rsi], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // MACD histogram: animate the displayed value from 0 → actual
  const animatedMacdHist = interpolate(
    frame,
    [MACD_HIST_START, MACD_HIST_END],
    [0, macd_hist],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // BB marker: animate from center (50) → actual bb_pct
  const animatedBbPct = interpolate(
    frame,
    [BB_MARKER_START, BB_MARKER_END],
    [50, bb_pct],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const markerLeft = Math.max(2, Math.min(98, animatedBbPct));
  const bbMarkerOpacity = interpolate(
    frame,
    [BB_MARKER_START, BB_MARKER_START + 20],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Derived values
  const rsiColor = rsi > 70 ? colors.red : rsi < 30 ? colors.green : colors.gold;
  const rsiLabel = rsi > 70 ? "OVERBOUGHT" : rsi < 30 ? "OVERSOLD" : "NEUTRAL";

  const macdHistColor = macd_hist >= 0 ? colors.green : colors.red;
  const animHistColor = animatedMacdHist >= 0 ? colors.green : colors.red;

  const trendColor =
    trend.includes("uptrend")   ? colors.green :
    trend.includes("downtrend") ? colors.red   : colors.textSecondary;
  const trendBg =
    trend.includes("uptrend")   ? "rgba(249,219,109,0.15)" :
    trend.includes("downtrend") ? "rgba(239,83,80,0.15)"   :
    "rgba(184,184,184,0.10)";
  const trendBorder =
    trend.includes("uptrend")   ? "rgba(249,219,109,0.35)" :
    trend.includes("downtrend") ? "rgba(239,83,80,0.35)"   :
    "rgba(184,184,184,0.25)";

  const atrLabel = atr_pct > 1.5 ? "HIGH" : atr_pct < 0.7 ? "LOW" : "MODERATE";
  const atrColor = atr_pct > 1.5 ? colors.red : atr_pct < 0.7 ? colors.green : colors.gold;

  const fmt = (v: number) =>
    "$" + v.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

  const formattedDate = new Date(date + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric", year: "numeric",
  });

  // Shared card style
  const cardStyle: React.CSSProperties = {
    backgroundColor: colors.surface,
    borderRadius: 18,
    padding: "30px 44px",
    borderLeft: `4px solid ${colors.gold}`,
  };

  // Section label style
  const sectionLabel: React.CSSProperties = {
    fontSize: 34,
    fontWeight: 500,
    fontFamily: fonts.main,
    color: colors.textSecondary,
    letterSpacing: 2,
    marginBottom: 18,
  };

  // MACD histogram bar chart (SVG) — last 20 days
  const maxAbsHist = Math.max(...hist_series.map((p) => Math.abs(p.macd_hist)), 0.001);
  const chartH = 72;
  const midY   = chartH / 2;
  const barMaxH = midY - 4;

  const macdBars = hist_series.map((point, i) => {
    const barH = (Math.abs(point.macd_hist) / maxAbsHist) * barMaxH;
    const isPos = point.macd_hist >= 0;
    const barProgress = interpolate(
      frame,
      [MACD_HIST_START + i * 2, MACD_HIST_START + i * 2 + 25],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    const animH = barH * barProgress;
    const barColor = isPos ? colors.green : colors.red;
    const isLatest = i === hist_series.length - 1;
    return { isPos, animH, barColor, isLatest };
  });

  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg }}>

      <div style={{
        position: "absolute",
        top: 60,
        left: 60,
        right: 140,
        display: "flex",
        flexDirection: "column",
        gap: 22,
      }}>

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div style={{ opacity: headerOpacity }}>
          <div style={{
            fontSize: 26,
            fontWeight: 400,
            fontFamily: fonts.main,
            color: colors.textSecondary,
            letterSpacing: 4,
            marginBottom: 8,
          }}>
            XAUUSD  ·  TECHNICAL INDICATORS
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 24, marginBottom: 10 }}>
            <span style={{
              fontSize: 80,
              fontWeight: 800,
              fontFamily: fonts.main,
              color: colors.gold,
              lineHeight: 1,
              textShadow: `0 0 40px ${colors.goldGlow}`,
            }}>
              ${current_price.toLocaleString("en-US", {
                minimumFractionDigits: 1,
                maximumFractionDigits: 1,
              })}
            </span>
            <span style={{
              fontSize: 30,
              fontWeight: 700,
              fontFamily: fonts.main,
              color: trendColor,
              backgroundColor: trendBg,
              border: `2px solid ${trendBorder}`,
              borderRadius: 10,
              padding: "6px 20px",
              letterSpacing: 2,
              textTransform: "uppercase",
            }}>
              {trend}
            </span>
          </div>

          {/* SMA20 basis line */}
          {(() => {
            const sma20Diff = ((current_price - sma20) / sma20 * 100);
            const sma20Above = current_price >= sma20;
            return (
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: 16,
                marginBottom: 8,
              }}>
                <span style={{ fontSize: 22, fontFamily: fonts.main, color: colors.textDim, letterSpacing: 1 }}>
                  vs SMA 20
                </span>
                <span style={{ fontSize: 26, fontWeight: 600, fontFamily: fonts.main, color: colors.textSecondary }}>
                  {fmt(sma20)}
                </span>
                <span style={{
                  fontSize: 24,
                  fontWeight: 700,
                  fontFamily: fonts.main,
                  color: sma20Above ? colors.green : colors.red,
                }}>
                  {sma20Above ? "▲" : "▼"} {sma20Above ? "+" : ""}{sma20Diff.toFixed(2)}%
                </span>
              </div>
            );
          })()}

          <div style={{
            fontSize: 26,
            fontWeight: 300,
            fontFamily: fonts.main,
            color: colors.textDim,
          }}>
            {formattedDate}
          </div>
        </div>

        {/* ── Row 1: RSI ─────────────────────────────────────────────────── */}
        <div style={{ ...rowStyle(0), ...cardStyle }}>
          <div style={sectionLabel}>RSI  (14)</div>

          {/* Gauge track */}
          <div style={{ position: "relative", height: 24, borderRadius: 12, backgroundColor: colors.surfaceLight, marginBottom: 16 }}>
            {/* Zone markers */}
            {[30, 70].map((zone) => (
              <div key={zone} style={{
                position: "absolute",
                top: 0,
                bottom: 0,
                left: `${zone}%`,
                width: 2,
                backgroundColor: colors.textDim,
                opacity: 0.6,
              }} />
            ))}
            {/* Fill */}
            <div style={{
              position: "absolute",
              left: 0, top: 0, bottom: 0,
              width: `${animatedRsi}%`,
              borderRadius: 12,
              backgroundColor: rsiColor,
              opacity: 0.75,
              transition: "none",
            }} />
            {/* Current position dot */}
            <div style={{
              position: "absolute",
              top: "50%",
              left: `${animatedRsi}%`,
              transform: "translate(-50%, -50%)",
              width: 20, height: 20,
              borderRadius: "50%",
              backgroundColor: rsiColor,
              boxShadow: `0 0 10px ${rsiColor}`,
              opacity: animatedRsi > 1 ? 1 : 0,
            }} />
          </div>

          {/* Zone labels */}
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 14 }}>
            <span style={{ fontSize: 26, color: colors.green, fontFamily: fonts.main }}>Oversold  ≤30</span>
            <span style={{ fontSize: 26, color: colors.textDim, fontFamily: fonts.main }}>Neutral</span>
            <span style={{ fontSize: 26, color: colors.red,   fontFamily: fonts.main }}>≥70  Overbought</span>
          </div>

          {/* RSI value + label */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{
              fontSize: 64,
              fontWeight: 800,
              fontFamily: fonts.main,
              color: rsiColor,
              lineHeight: 1,
            }}>
              {rsi.toFixed(1)}
            </span>
            <span style={{
              fontSize: 32,
              fontWeight: 700,
              fontFamily: fonts.main,
              color: rsiColor,
              backgroundColor: rsi > 70 ? "rgba(239,83,80,0.15)" : rsi < 30 ? "rgba(249,219,109,0.15)" : "rgba(249,219,109,0.12)",
              border: `2px solid ${rsi > 70 ? "rgba(239,83,80,0.4)" : "rgba(249,219,109,0.35)"}`,
              borderRadius: 10,
              padding: "8px 28px",
              letterSpacing: 2,
            }}>
              {rsiLabel}
            </span>
          </div>
        </div>

        {/* ── Row 2: MACD ────────────────────────────────────────────────── */}
        <div style={{ ...rowStyle(1), ...cardStyle }}>
          <div style={sectionLabel}>MACD  (12, 26, 9)</div>

          {/* Histogram bar chart */}
          <svg
            width="100%"
            height={chartH}
            style={{ display: "block", marginBottom: 20 }}
          >
            {/* Baseline */}
            <line
              x1="0" y1={midY} x2="100%" y2={midY}
              stroke={colors.surfaceLight} strokeWidth={1}
            />
            {macdBars.map((bar, i) => {
              const xPct = (i / hist_series.length) * 100;
              const wPct = (1 / hist_series.length) * 100 - 0.8;
              return (
                <rect
                  key={i}
                  x={`${xPct}%`}
                  y={bar.isPos ? midY - bar.animH : midY}
                  width={`${wPct}%`}
                  height={bar.animH}
                  fill={bar.barColor}
                  opacity={bar.isLatest ? 1 : 0.6}
                />
              );
            })}
          </svg>

          {/* Three metric cards */}
          <div style={{ display: "flex", gap: 16 }}>
            {[
              { label: "MACD Line", value: macd,            color: macd >= 0 ? colors.green : colors.red },
              { label: "Signal",    value: macd_signal,     color: macd_signal >= 0 ? colors.green : colors.red },
              { label: "Histogram", value: animatedMacdHist, color: animHistColor },
            ].map(({ label, value, color }) => (
              <div key={label} style={{
                flex: 1,
                backgroundColor: colors.surfaceLight,
                borderRadius: 12,
                padding: "18px 20px",
                borderTop: `3px solid ${color}`,
              }}>
                <div style={{
                  fontSize: 26,
                  fontFamily: fonts.main,
                  color: colors.textSecondary,
                  marginBottom: 8,
                }}>
                  {label}
                </div>
                <div style={{
                  fontSize: 36,
                  fontWeight: 800,
                  fontFamily: fonts.main,
                  color,
                }}>
                  {value >= 0 ? "+" : ""}{value.toFixed(3)}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Row 3: Bollinger Bands ─────────────────────────────────────── */}
        <div style={{ ...rowStyle(2), ...cardStyle }}>
          <div style={sectionLabel}>BOLLINGER BANDS  (20, 2σ)</div>

          {/* Upper / Mid / Lower values */}
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 20, alignItems: "flex-end" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: 26, color: colors.textDim, fontFamily: fonts.main, letterSpacing: 2 }}>LOWER</span>
              <span style={{ fontSize: 40, fontWeight: 700, fontFamily: fonts.main, color: colors.green }}>{fmt(bb_lower)}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <span style={{ fontSize: 26, color: colors.textDim, fontFamily: fonts.main, letterSpacing: 2 }}>MID (SMA20)</span>
              <span style={{ fontSize: 36, fontWeight: 500, fontFamily: fonts.main, color: colors.gold }}>{fmt(bb_mid)}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
              <span style={{ fontSize: 26, color: colors.textDim, fontFamily: fonts.main, letterSpacing: 2 }}>UPPER</span>
              <span style={{ fontSize: 40, fontWeight: 700, fontFamily: fonts.main, color: colors.red }}>{fmt(bb_upper)}</span>
            </div>
          </div>

          {/* Range bar */}
          <div style={{ position: "relative", height: 20, borderRadius: 10, backgroundColor: colors.surfaceLight }}>
            <div style={{
              position: "absolute",
              left: 0, top: 0, height: "100%",
              width: `${markerLeft}%`,
              borderRadius: 10,
              background: `linear-gradient(90deg, ${colors.green}55, ${colors.gold})`,
            }} />
            <div style={{
              position: "absolute",
              top: "50%",
              left: `${markerLeft}%`,
              transform: "translate(-50%, -50%)",
              width: 28, height: 28,
              borderRadius: "50%",
              backgroundColor: colors.gold,
              boxShadow: `0 0 14px ${colors.goldGlow}`,
              opacity: bbMarkerOpacity,
            }} />
          </div>

          {/* Current price label under marker */}
          <div style={{ position: "relative", height: 44, marginTop: 6 }}>
            <div style={{
              position: "absolute",
              left: `${markerLeft}%`,
              transform: "translateX(-50%)",
              opacity: bbMarkerOpacity,
              textAlign: "center",
            }}>
              <div style={{ fontSize: 28, fontWeight: 700, fontFamily: fonts.main, color: colors.gold }}>
                ${current_price.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
              </div>
              <div style={{ fontSize: 18, fontFamily: fonts.main, color: colors.textDim }}>
                {bb_pct.toFixed(1)}% of range
              </div>
            </div>
          </div>
        </div>

        {/* ── Row 4: ATR + Moving Averages ──────────────────────────────── */}
        <div style={{ ...rowStyle(3), ...cardStyle }}>
          <div style={sectionLabel}>VOLATILITY  &  MOVING AVERAGES</div>

          <div style={{ display: "flex", gap: 24 }}>
            {/* ATR */}
            <div style={{
              width: "38%",
              backgroundColor: colors.surfaceLight,
              borderRadius: 14,
              padding: "24px 28px",
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}>
              <span style={{ fontSize: 22, fontFamily: fonts.main, color: colors.textSecondary, letterSpacing: 1 }}>
                ATR  (14)
              </span>
              <span style={{
                fontSize: 52,
                fontWeight: 800,
                fontFamily: fonts.main,
                color: colors.text,
                lineHeight: 1,
              }}>
                ${atr.toFixed(1)}
              </span>
              <span style={{ fontSize: 22, fontFamily: fonts.main, color: colors.textDim }}>
                {atr_pct.toFixed(2)}% daily
              </span>
              <span style={{
                fontSize: 24,
                fontWeight: 700,
                fontFamily: fonts.main,
                color: atrColor,
                backgroundColor: atr_pct > 1.5 ? "rgba(239,83,80,0.15)" : atr_pct < 0.7 ? "rgba(249,219,109,0.15)" : "rgba(249,219,109,0.12)",
                border: `2px solid ${atrColor}44`,
                borderRadius: 8,
                padding: "4px 14px",
                alignSelf: "flex-start",
                letterSpacing: 1,
              }}>
                {atrLabel}
              </span>
            </div>

            {/* SMAs */}
            <div style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              gap: 14,
            }}>
              {[
                { label: "SMA 20",  value: sma20  },
                { label: "SMA 50",  value: sma50  },
                { label: "SMA 200", value: sma200 },
              ].map(({ label, value }) => {
                const above   = current_price >= value;
                const diffPct = ((current_price - value) / value * 100).toFixed(2);
                const arrow   = above ? "▲" : "▼";
                const col     = above ? colors.green : colors.red;
                return (
                  <div key={label} style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    backgroundColor: colors.surfaceLight,
                    borderRadius: 12,
                    padding: "16px 24px",
                    borderLeft: `3px solid ${col}`,
                  }}>
                    <span style={{ fontSize: 30, fontFamily: fonts.main, color: colors.textSecondary }}>
                      {label}
                    </span>
                    <span style={{ fontSize: 30, fontFamily: fonts.main, color: colors.textDim }}>
                      {fmt(value)}
                    </span>
                    <span style={{ fontSize: 32, fontWeight: 800, fontFamily: fonts.main, color: col }}>
                      {arrow} {above ? "+" : ""}{diffPct}%
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* ── Disclaimer ─────────────────────────────────────────────────── */}
        <div style={{ textAlign: "center", paddingTop: 8, paddingBottom: 16 }}>
          <span style={{ fontSize: 40, fontWeight: 300, fontFamily: fonts.main, color: "#666666", letterSpacing: 1 }}>
            Not financial advice. Trading involves risk of loss.{" "}
          </span>
          <span style={{ fontSize: 40, fontWeight: 400, fontFamily: fonts.main, color: colors.gold, letterSpacing: 1 }}>
            goldprice.trade
          </span>
        </div>

      </div>

    </AbsoluteFill>
  );
};
