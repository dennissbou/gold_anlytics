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
interface Candle {
  date:   string;
  open:   number;
  high:   number;
  low:    number;
  close:  number;
  sma20:  number | null;
  sma50:  number | null;
  sma200: number | null;
}

interface Props {
  date:          string;
  date_from:     string;
  current_price: number;
  candles:       Candle[];
  sma20:         number | null;
  sma50:         number | null;
  sma200:        number | null;
}

// ─── Fixed layout (1200 × 400) ────────────────────────────────────────────────
const CANVAS_W   = 1200;
const CANVAS_H   = 400;
const HEADER_H   = 44;
const XAXIS_H    = 28;
const YAXIS_W    = 78;
const RIGHT_W    = 110;   // current price label + SMA legend right margin

const CHART_TOP_PAD = 8;   // gap between header border and first candle

const CHART_X    = YAXIS_W;
const CHART_Y    = HEADER_H;
const CHART_W    = CANVAS_W - YAXIS_W - RIGHT_W;                       // 1012
const CHART_H    = CANVAS_H - HEADER_H - XAXIS_H - CHART_TOP_PAD;     // 320

// ─── Animation frame ranges ───────────────────────────────────────────────────
const CANDLE_IN_START  = 0;
const CANDLE_IN_END    = 20;
const SMA200_START     = 20;
const SMA200_END       = 45;
const SMA50_START      = 32;
const SMA50_END        = 57;
const SMA20_START      = 44;
const SMA20_END        = 69;
const LEGEND_START     = 70;
const LEGEND_END       = 82;

// ─── Helpers ──────────────────────────────────────────────────────────────────
const buildPolyline = (
  candles: Candle[],
  key: "sma20" | "sma50" | "sma200",
  slotW: number,
  priceToY: (p: number) => number
): string => {
  const pts: string[] = [];
  candles.forEach((c, i) => {
    const v = c[key];
    if (v === null) return;
    const x = CHART_X + (i + 0.5) * slotW;
    const y = priceToY(v);
    pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  });
  return pts.join(" ");
};

// ─── Component ────────────────────────────────────────────────────────────────
const fmtDateRange = (from: string, to: string) => {
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const [, fm, fd] = from.split("-").map(Number);
  const [, tm, td] = to.split("-").map(Number);
  return `${fd} ${months[fm-1]} – ${td} ${months[tm-1]}`;
};

export const PriceChart: React.FC<Props> = ({
  date, date_from, current_price, candles, sma20, sma50, sma200,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // ── Price scale ──────────────────────────────────────────────────────────
  const allLows  = candles.map(c => c.low);
  const allHighs = candles.map(c => c.high);
  const priceMin = Math.min(...allLows);
  const priceMax = Math.max(...allHighs);
  const pricePad = (priceMax - priceMin) * 0.06;
  const yMin = priceMin - pricePad;
  const yMax = priceMax + pricePad;

  const priceToY = (p: number) =>
    CHART_Y + CHART_TOP_PAD + CHART_H - ((p - yMin) / (yMax - yMin)) * CHART_H;

  // ── Layout ────────────────────────────────────────────────────────────────
  const N     = candles.length;
  const slotW = CHART_W / N;
  const bodyW = slotW;

  // ── Candle opacity (batch fade-in) ───────────────────────────────────────
  const candleOpacity = interpolate(
    frame, [CANDLE_IN_START, CANDLE_IN_END], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // ── SMA clip widths (draw left → right) ──────────────────────────────────
  const sma200Progress = interpolate(
    frame, [SMA200_START, SMA200_END], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const sma50Progress = interpolate(
    frame, [SMA50_START, SMA50_END], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const sma20Progress = interpolate(
    frame, [SMA20_START, SMA20_END], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Clip x boundary for each SMA line
  const sma200ClipX = CHART_X + CHART_W * sma200Progress;
  const sma50ClipX  = CHART_X + CHART_W * sma50Progress;
  const sma20ClipX  = CHART_X + CHART_W * sma20Progress;

  // ── Legend + price label fade ─────────────────────────────────────────────
  const legendOpacity = interpolate(
    frame, [LEGEND_START, LEGEND_END], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // ── Y-axis ticks ─────────────────────────────────────────────────────────
  const tickCount   = 5;
  const tickStep    = (yMax - yMin) / tickCount;
  const yAxisTicks  = Array.from({ length: tickCount + 1 }, (_, i) =>
    Math.round((yMin + i * tickStep) / 50) * 50
  ).filter(t => t > yMin && t < yMax);

  // ── SMA polylines ─────────────────────────────────────────────────────────
  const poly200 = buildPolyline(candles, "sma200", slotW, priceToY);
  const poly50  = buildPolyline(candles, "sma50",  slotW, priceToY);
  const poly20  = buildPolyline(candles, "sma20",  slotW, priceToY);

  // ── X-axis date labels (show every 10th candle) ───────────────────────────
  // Every 6 bars = 1 day; show the date portion (MM-DD) only
  const dateLabels = candles
    .map((c, i) => ({ i, date: c.date }))
    .filter(({ i }) => i % 6 === 0);

  const fmt0 = (v: number) =>
    "$" + v.toLocaleString("en-US", { maximumFractionDigits: 0 });

  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg, fontFamily: fonts.main, overflow: "hidden" }}>

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: HEADER_H,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        paddingLeft: 16, paddingRight: 16,
        borderBottom: `1px solid ${colors.surfaceLight}`,
      }}>
        <span style={{ fontSize: 20, fontWeight: 700, color: colors.gold, letterSpacing: 3, textTransform: "uppercase" as const }}>
          Gold / XAU/USD · 4H Chart
        </span>
        <span style={{ fontSize: 20, fontWeight: 600, color: colors.textSecondary, letterSpacing: 1 }}>
          {fmtDateRange(date_from, date)}
        </span>
      </div>

      {/* ── Main SVG ────────────────────────────────────────────────────────── */}
      <svg
        width={CANVAS_W}
        height={CANVAS_H - HEADER_H}
        style={{ position: "absolute", top: HEADER_H, left: 0 }}
      >
        {/* Y-axis separator */}
        <line x1={YAXIS_W} y1={CHART_TOP_PAD} x2={YAXIS_W} y2={CHART_TOP_PAD + CHART_H}
          stroke={colors.surfaceLight} strokeWidth={1} />

        {/* Horizontal grid lines + Y-axis labels */}
        {yAxisTicks.map(tick => {
          const y = priceToY(tick) - CHART_Y;
          return (
            <g key={tick}>
              <line x1={YAXIS_W} y1={y} x2={CANVAS_W - RIGHT_W} y2={y}
                stroke={colors.surfaceLight} strokeWidth={0.5} opacity={0.4} />
              <text x={YAXIS_W - 6} y={y + 4}
                textAnchor="end" fill={colors.textDim}
                fontSize={12} fontFamily={fonts.main} fontVariantNumeric="tabular-nums">
                {fmt0(tick)}
              </text>
            </g>
          );
        })}

        {/* X-axis date labels */}
        {dateLabels.map(({ i, date: d }) => {
          const x = CHART_X + (i + 0.5) * slotW;
          const label = d.slice(5, 10); // MM-DD
          return (
            <text key={i}
              x={x} y={CHART_TOP_PAD + CHART_H + 18}
              textAnchor="middle" fill={colors.textDim}
              fontSize={11} fontFamily={fonts.main}>
              {label}
            </text>
          );
        })}

        {/* ── Candles ───────────────────────────────────────────────────── */}
        <g opacity={candleOpacity}>
          {candles.map((c, i) => {
            const isPos  = c.close >= c.open;
            const col    = isPos ? colors.green : colors.red;
            const x      = CHART_X + (i + 0.5) * slotW;
            const bodyY1 = priceToY(Math.max(c.open, c.close)) - CHART_Y;
            const bodyY2 = priceToY(Math.min(c.open, c.close)) - CHART_Y;
            const bodyH  = Math.max(1, bodyY2 - bodyY1);
            const wickY1 = priceToY(c.high)  - CHART_Y;
            const wickY2 = priceToY(c.low)   - CHART_Y;
            return (
              <g key={i}>
                {/* Wick */}
                <line x1={x} y1={wickY1} x2={x} y2={wickY2}
                  stroke={col} strokeWidth={1} opacity={0.8} />
                {/* Body */}
                <rect
                  x={x - bodyW / 2} y={bodyY1}
                  width={bodyW} height={bodyH}
                  fill={isPos ? col : col} opacity={0.9}
                />
              </g>
            );
          })}
        </g>

        {/* ── SMA 200 (purple) — clip draws left→right ─────────────────── */}
        {poly200 && sma200Progress > 0 && (
          <>
            <defs>
              <clipPath id="clip200">
                <rect x={CHART_X} y={CHART_TOP_PAD} width={sma200ClipX - CHART_X} height={CHART_H} />
              </clipPath>
            </defs>
            <polyline
              points={poly200}
              fill="none"
              stroke={colors.sma200}
              strokeWidth={1.5}
              opacity={0.85}
              clipPath="url(#clip200)"
            />
          </>
        )}

        {/* ── SMA 50 (amber) ───────────────────────────────────────────── */}
        {poly50 && sma50Progress > 0 && (
          <>
            <defs>
              <clipPath id="clip50">
                <rect x={CHART_X} y={CHART_TOP_PAD} width={sma50ClipX - CHART_X} height={CHART_H} />
              </clipPath>
            </defs>
            <polyline
              points={poly50}
              fill="none"
              stroke={colors.sma50}
              strokeWidth={1.5}
              opacity={0.85}
              clipPath="url(#clip50)"
            />
          </>
        )}

        {/* ── SMA 20 (blue) ────────────────────────────────────────────── */}
        {poly20 && sma20Progress > 0 && (
          <>
            <defs>
              <clipPath id="clip20">
                <rect x={CHART_X} y={CHART_TOP_PAD} width={sma20ClipX - CHART_X} height={CHART_H} />
              </clipPath>
            </defs>
            <polyline
              points={poly20}
              fill="none"
              stroke={colors.sma20}
              strokeWidth={1.5}
              opacity={0.85}
              clipPath="url(#clip20)"
            />
          </>
        )}

        {/* ── Current price dashed line ────────────────────────────────── */}
        {legendOpacity > 0 && (
          <line
            x1={YAXIS_W} y1={priceToY(current_price) - CHART_Y}
            x2={CANVAS_W - RIGHT_W + 4} y2={priceToY(current_price) - CHART_Y}
            stroke={colors.gold} strokeWidth={1} strokeDasharray="6 3"
            opacity={legendOpacity * 0.7}
          />
        )}

        {/* ── Current price label (right edge) ─────────────────────────── */}
        {legendOpacity > 0 && (
          <g opacity={legendOpacity}>
            <rect
              x={CANVAS_W - RIGHT_W + 6}
              y={priceToY(current_price) - CHART_Y - 11}
              width={RIGHT_W - 10} height={20}
              rx={4} fill={colors.gold}
            />
            <text
              x={CANVAS_W - RIGHT_W + 10}
              y={priceToY(current_price) - CHART_Y + 3}
              fill={colors.bg}
              fontSize={11} fontWeight={700} fontFamily={fonts.main}
              fontVariantNumeric="tabular-nums"
            >
              {fmt0(current_price)}
            </text>
          </g>
        )}
      </svg>

      {/* ── SMA Legend (bottom-left of chart area) ────────────────────────── */}
      <div style={{
        position: "absolute",
        bottom: XAXIS_H + 8, left: YAXIS_W + 8,
        display: "flex", gap: 14,
        opacity: legendOpacity,
      }}>
        {[
          { label: "SMA 200", color: colors.sma200, value: sma200 },
          { label: "SMA 50",  color: colors.sma50,  value: sma50  },
          { label: "SMA 20",  color: colors.sma20,  value: sma20  },
        ].filter(({ value }) => value !== null).map(({ label, color, value }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <div style={{ width: 18, height: 2, backgroundColor: color, borderRadius: 1 }} />
            <span style={{ fontSize: 13, color: colors.textDim }}>{label}</span>
            {value !== null && (
              <span style={{ fontSize: 13, fontWeight: 600, color, fontVariantNumeric: "tabular-nums" }}>
                {fmt0(value)}
              </span>
            )}
          </div>
        ))}
      </div>

    </AbsoluteFill>
  );
};
