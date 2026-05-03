import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { colors, fonts } from "./theme";

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

// ─── Fixed layout (800 × 800) ────────────────────────────────────────────────
const CANVAS_W   = 800;
const CANVAS_H   = 800;
const HEADER_H   = 62;
const XAXIS_H    = 40;
const YAXIS_W    = 96;
const RIGHT_W    = 130;
const CHART_TOP_PAD = 12;

const CHART_X    = YAXIS_W;
const CHART_W    = CANVAS_W - YAXIS_W - RIGHT_W;          // 602
const CHART_H    = CANVAS_H - HEADER_H - XAXIS_H - CHART_TOP_PAD; // 708

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

const fmtDateRange = (from: string, to: string) => {
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const [, fm, fd] = from.split("-").map(Number);
  const [, tm, td] = to.split("-").map(Number);
  return `${fd} ${months[fm-1]} – ${td} ${months[tm-1]}`;
};

export const PriceChartSquare: React.FC<Props> = ({
  date, date_from, current_price, candles, sma20, sma50, sma200,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const allLows  = candles.map(c => c.low);
  const allHighs = candles.map(c => c.high);
  const priceMin = Math.min(...allLows);
  const priceMax = Math.max(...allHighs);
  const pricePad = (priceMax - priceMin) * 0.05;
  const yMin = priceMin - pricePad;
  const yMax = priceMax + pricePad;

  const priceToY = (p: number) =>
    HEADER_H + CHART_TOP_PAD + CHART_H - ((p - yMin) / (yMax - yMin)) * CHART_H;

  const N     = candles.length;
  const slotW = CHART_W / N;

  const candleOpacity = interpolate(frame, [CANDLE_IN_START, CANDLE_IN_END], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const sma200Progress = interpolate(frame, [SMA200_START, SMA200_END], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const sma50Progress  = interpolate(frame, [SMA50_START,  SMA50_END],  [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const sma20Progress  = interpolate(frame, [SMA20_START,  SMA20_END],  [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const sma200ClipX = CHART_X + CHART_W * sma200Progress;
  const sma50ClipX  = CHART_X + CHART_W * sma50Progress;
  const sma20ClipX  = CHART_X + CHART_W * sma20Progress;

  const legendOpacity = interpolate(frame, [LEGEND_START, LEGEND_END], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const tickCount  = 6;
  const tickStep   = (yMax - yMin) / tickCount;
  const yAxisTicks = Array.from({ length: tickCount + 1 }, (_, i) =>
    Math.round((yMin + i * tickStep) / 50) * 50
  ).filter(t => t > yMin && t < yMax);

  const poly200 = buildPolyline(candles, "sma200", slotW, priceToY);
  const poly50  = buildPolyline(candles, "sma50",  slotW, priceToY);
  const poly20  = buildPolyline(candles, "sma20",  slotW, priceToY);

  // Every 12 bars = every 2 days (less crowded on narrower chart)
  const dateLabels = candles
    .map((c, i) => ({ i, date: c.date }))
    .filter(({ i }) => i % 12 === 0);

  const fmt0 = (v: number) =>
    "$" + v.toLocaleString("en-US", { maximumFractionDigits: 0 });

  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg, fontFamily: fonts.main, overflow: "hidden" }}>

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: HEADER_H,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        paddingLeft: 18, paddingRight: 18,
        borderBottom: `1px solid ${colors.surfaceLight}`,
      }}>
        <span style={{ fontSize: 22, fontWeight: 700, color: colors.gold, letterSpacing: 3, textTransform: "uppercase" as const }}>
          Gold / XAU/USD · 4H Chart
        </span>
        <span style={{ fontSize: 22, fontWeight: 600, color: colors.textSecondary, letterSpacing: 1 }}>
          {fmtDateRange(date_from, date)}
        </span>
      </div>

      {/* ── Main SVG ──────────────────────────────────────────────────────── */}
      <svg
        width={CANVAS_W}
        height={CANVAS_H - HEADER_H}
        style={{ position: "absolute", top: HEADER_H, left: 0 }}
      >
        <line x1={YAXIS_W} y1={CHART_TOP_PAD} x2={YAXIS_W} y2={CHART_TOP_PAD + CHART_H}
          stroke={colors.surfaceLight} strokeWidth={1} />

        {yAxisTicks.map(tick => {
          const y = priceToY(tick) - HEADER_H;
          return (
            <g key={tick}>
              <line x1={YAXIS_W} y1={y} x2={CANVAS_W - RIGHT_W} y2={y}
                stroke={colors.surfaceLight} strokeWidth={0.5} opacity={0.4} />
              <text x={YAXIS_W - 6} y={y + 4}
                textAnchor="end" fill={colors.textDim}
                fontSize={15} fontFamily={fonts.main} fontVariantNumeric="tabular-nums">
                {fmt0(tick)}
              </text>
            </g>
          );
        })}

        {dateLabels.map(({ i, date: d }) => {
          const x = CHART_X + (i + 0.5) * slotW;
          const label = d.slice(5, 10);
          return (
            <text key={i}
              x={x} y={CHART_TOP_PAD + CHART_H + 24}
              textAnchor="middle" fill={colors.textDim}
              fontSize={14} fontFamily={fonts.main}>
              {label}
            </text>
          );
        })}

        <g opacity={candleOpacity}>
          {candles.map((c, i) => {
            const isPos  = c.close >= c.open;
            const col    = isPos ? colors.green : colors.red;
            const x      = CHART_X + (i + 0.5) * slotW;
            const bodyY1 = priceToY(Math.max(c.open, c.close)) - HEADER_H;
            const bodyY2 = priceToY(Math.min(c.open, c.close)) - HEADER_H;
            const bodyH  = Math.max(1, bodyY2 - bodyY1);
            const wickY1 = priceToY(c.high) - HEADER_H;
            const wickY2 = priceToY(c.low)  - HEADER_H;
            return (
              <g key={i}>
                <line x1={x} y1={wickY1} x2={x} y2={wickY2}
                  stroke={col} strokeWidth={1.5} opacity={0.8} />
                <rect x={x - slotW / 2} y={bodyY1} width={slotW} height={bodyH}
                  fill={col} opacity={0.9} />
              </g>
            );
          })}
        </g>

        {poly200 && sma200Progress > 0 && (
          <>
            <defs><clipPath id="sq-clip200">
              <rect x={CHART_X} y={CHART_TOP_PAD} width={sma200ClipX - CHART_X} height={CHART_H} />
            </clipPath></defs>
            <polyline points={poly200} fill="none" stroke={colors.sma200}
              strokeWidth={3} opacity={0.85} clipPath="url(#sq-clip200)" />
          </>
        )}
        {poly50 && sma50Progress > 0 && (
          <>
            <defs><clipPath id="sq-clip50">
              <rect x={CHART_X} y={CHART_TOP_PAD} width={sma50ClipX - CHART_X} height={CHART_H} />
            </clipPath></defs>
            <polyline points={poly50} fill="none" stroke={colors.sma50}
              strokeWidth={3} opacity={0.85} clipPath="url(#sq-clip50)" />
          </>
        )}
        {poly20 && sma20Progress > 0 && (
          <>
            <defs><clipPath id="sq-clip20">
              <rect x={CHART_X} y={CHART_TOP_PAD} width={sma20ClipX - CHART_X} height={CHART_H} />
            </clipPath></defs>
            <polyline points={poly20} fill="none" stroke={colors.sma20}
              strokeWidth={3} opacity={0.85} clipPath="url(#sq-clip20)" />
          </>
        )}

        {legendOpacity > 0 && (
          <line
            x1={YAXIS_W} y1={priceToY(current_price) - HEADER_H}
            x2={CANVAS_W - RIGHT_W + 4} y2={priceToY(current_price) - HEADER_H}
            stroke={colors.gold} strokeWidth={1} strokeDasharray="6 3"
            opacity={legendOpacity * 0.7}
          />
        )}
        {legendOpacity > 0 && (
          <g opacity={legendOpacity}>
            <rect x={CANVAS_W - RIGHT_W + 6} y={priceToY(current_price) - HEADER_H - 14}
              width={RIGHT_W - 10} height={26} rx={4} fill={colors.gold} />
            <text x={CANVAS_W - RIGHT_W + 10} y={priceToY(current_price) - HEADER_H + 5}
              fill={colors.bg} fontSize={14} fontWeight={700} fontFamily={fonts.main}
              fontVariantNumeric="tabular-nums">
              {fmt0(current_price)}
            </text>
          </g>
        )}
      </svg>

      {/* ── SMA Legend ────────────────────────────────────────────────────── */}
      <div style={{
        position: "absolute",
        bottom: XAXIS_H + 10, left: YAXIS_W + 10,
        display: "flex", gap: 16,
        opacity: legendOpacity,
      }}>
        {[
          { label: "SMA 200", color: colors.sma200, value: sma200 },
          { label: "SMA 50",  color: colors.sma50,  value: sma50  },
          { label: "SMA 20",  color: colors.sma20,  value: sma20  },
        ].filter(({ value }) => value !== null).map(({ label, color, value }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 24, height: 3, backgroundColor: color, borderRadius: 1 }} />
            <span style={{ fontSize: 16, color: colors.textDim }}>{label}</span>
            {value !== null && (
              <span style={{ fontSize: 16, fontWeight: 600, color, fontVariantNumeric: "tabular-nums" }}>
                {fmt0(value)}
              </span>
            )}
          </div>
        ))}
      </div>

    </AbsoluteFill>
  );
};
