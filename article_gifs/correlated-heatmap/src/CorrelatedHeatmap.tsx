import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { colors, fonts } from "./theme";
import { AssetIcon } from "./icons";

// ─── Types ────────────────────────────────────────────────────────────────────
interface AssetData {
  symbol:     string;
  name:       string;
  label:      string;
  close:      number | null;
  change_pct: number | null;
  date:       string | null;
}

interface Props {
  date:    string;
  period:  string;
  assets:  AssetData[];
}

// ─── Fixed layout constants (canvas 1200 × 400) ───────────────────────────────
const CANVAS_W  = 1200;
const CANVAS_H  = 400;
const HEADER_H  = 44;
const X_AXIS_H  = 36;
const LEFT_W    = 300;   // one-line info column
const CHART_X   = LEFT_W;
const CHART_W   = CANVAS_W - LEFT_W;   // 900
const HALF_W    = CHART_W / 2;         // 450

const CHART_Y   = HEADER_H;
const CHART_H   = CANVAS_H - HEADER_H - X_AXIS_H;  // 320
const N         = 7;
const ROW_H     = CHART_H / N;         // ≈45.7
const BAR_H     = 22;
const BAR_OFF   = (ROW_H - BAR_H) / 2;

// ─── Price formatter ─────────────────────────────────────────────────────────
const formatPrice = (symbol: string, price: number | null): string => {
  if (price === null) return "—";
  if (symbol === "GOLD")   return "$" + price.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  if (symbol === "SPX")    return price.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  if (symbol === "BTC")    return "$" + price.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  if (symbol === "SILVER") return "$" + price.toFixed(2);
  if (symbol === "WTI")    return "$" + price.toFixed(2);
  return price.toFixed(2);
};

// ─── Component ────────────────────────────────────────────────────────────────
export const CorrelatedHeatmap: React.FC<Props> = ({ period, assets }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // ── Dynamic axis scale fitted to actual data ──────────────────────────────
  const maxAbsPct = Math.max(0.5, ...assets.map(a => Math.abs(a.change_pct ?? 0)));
  // Round cap up to next 0.5 with 25% headroom
  const capPct    = Math.ceil(maxAbsPct * 1.25 * 2) / 2;
  const pctToPx   = HALF_W / capPct;
  const tickStep  = capPct / 2;
  const ticks     = [-capPct, -tickStep, 0, tickStep, capPct];

  // ── Bar spring — all bars animate simultaneously ──────────────────────────
  const barSpring  = spring({ frame: frame - 5, fps, config: { damping: 80, stiffness: 100, mass: 1 } });
  const barProgress = interpolate(barSpring, [0, 1], [0, 1]);

  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg, fontFamily: fonts.main, overflow: "hidden" }}>

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: HEADER_H,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        paddingLeft: 16, paddingRight: 16,
        borderBottom: `1px solid ${colors.surfaceLight}`,
      }}>
        <span style={{ fontSize: 20, fontWeight: 700, color: colors.gold, letterSpacing: 3, textTransform: "uppercase" as const }}>
          Market Heatmap · Weekly
        </span>
        <span style={{ fontSize: 20, fontWeight: 600, color: colors.textSecondary, letterSpacing: 1 }}>
          {period}
        </span>
      </div>

      {/* ── Left column rows (HTML — needed for Remotion Img in icons) ────── */}
      {assets.map((asset, i) => {
        const rowY   = CHART_Y + i * ROW_H;
        const isGold = asset.symbol === "GOLD";

        return (
          <div
            key={asset.symbol}
            style={{
              position: "absolute", top: rowY, left: 0, width: LEFT_W, height: ROW_H,
              display: "flex", flexDirection: "row", alignItems: "center",
              paddingLeft: 10, paddingRight: 10, gap: 8,
              borderBottom: `1px solid ${colors.surfaceLight}`,
            }}
          >
            {/* Icon */}
            <div style={{ flexShrink: 0 }}>
              <AssetIcon symbol={asset.symbol} size={24} />
            </div>

            {/* Name — flex-grows, truncates with ellipsis if too long */}
            <span style={{
              fontSize: 17, fontWeight: isGold ? 700 : 500,
              color: isGold ? colors.gold : colors.textSecondary,
              flex: 1, overflow: "hidden", whiteSpace: "nowrap" as const,
              textOverflow: "ellipsis",
            }}>
              {asset.name}
            </span>

            {/* Ticker symbol */}
            <span style={{
              fontSize: 17, fontWeight: 400, color: colors.textDim,
              flexShrink: 0, whiteSpace: "nowrap" as const,
            }}>
              {asset.label}
            </span>

            {/* Price */}
            <span style={{
              fontSize: 17, fontWeight: 600, color: colors.text,
              fontVariantNumeric: "tabular-nums",
              flexShrink: 0, whiteSpace: "nowrap" as const,
            }}>
              {formatPrice(asset.symbol, asset.close)}
            </span>

            {/* Right border */}
            <div style={{
              position: "absolute", right: 0, top: 6, bottom: 6,
              width: 1, backgroundColor: colors.surfaceLight,
            }} />
          </div>
        );
      })}

      {/* ── Bar chart + % labels (SVG) ──────────────────────────────────────── */}
      <svg
        width={CHART_W}
        height={CHART_H}
        style={{ position: "absolute", top: CHART_Y, left: CHART_X }}
      >
        {/* Zero line */}
        <line x1={HALF_W} y1={0} x2={HALF_W} y2={CHART_H} stroke={colors.surfaceLight} strokeWidth={1} />

        {/* Row separators */}
        {assets.map((_, i) => (
          <line
            key={i}
            x1={0} y1={(i + 1) * ROW_H}
            x2={CHART_W} y2={(i + 1) * ROW_H}
            stroke={colors.surfaceLight} strokeWidth={0.5} opacity={0.5}
          />
        ))}

        {assets.map((asset, i) => {
          const pct      = asset.change_pct ?? 0;
          const isPos    = pct >= 0;
          const barColor = isPos ? colors.green : colors.red;

          const finalW   = Math.min(Math.abs(pct), capPct) * pctToPx;
          const animW    = finalW * barProgress;

          const barX     = isPos ? HALF_W : HALF_W - animW;
          const barY     = i * ROW_H + BAR_OFF;
          const midY     = barY + BAR_H / 2 + 6; // text baseline

          const labelX   = isPos ? HALF_W + animW + 10 : HALF_W - animW - 10;
          const anchor   = isPos ? "start" : "end";

          return (
            <g key={asset.symbol}>
              <rect x={barX} y={barY} width={animW} height={BAR_H} fill={barColor} opacity={0.9} rx={3} />

              {/* % change at bar tip */}
              {barProgress > 0.1 && asset.change_pct !== null && (
                <text
                  x={labelX} y={midY}
                  textAnchor={anchor}
                  fill={barColor}
                  fontSize={17} fontWeight={700} fontFamily={fonts.main}
                >
                  {isPos ? "+" : ""}{pct.toFixed(2)}%
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* ── X-axis (SVG, fitted to dynamic scale) ───────────────────────────── */}
      <svg
        width={CHART_W}
        height={X_AXIS_H}
        style={{ position: "absolute", bottom: 0, left: CHART_X }}
      >
        <line x1={0} y1={0} x2={CHART_W} y2={0} stroke={colors.surfaceLight} strokeWidth={1} />

        {ticks.map((tick, idx) => {
          const x       = HALF_W + tick * pctToPx;
          const isZero  = tick === 0;
          const isFirst = idx === 0;
          const isLast  = idx === ticks.length - 1;
          const anchor  = isFirst ? "start" : isLast ? "end" : "middle";
          const label   = tick > 0 ? `+${tick}%` : tick === 0 ? "0" : `${tick}%`;

          return (
            <g key={tick}>
              <line
                x1={x} y1={0} x2={x} y2={isZero ? 8 : 5}
                stroke={isZero ? colors.textDim : "#333"} strokeWidth={1}
              />
              <text
                x={x} y={X_AXIS_H - 8}
                textAnchor={anchor}
                fill={isZero ? colors.textSecondary : colors.textDim}
                fontSize={17} fontFamily={fonts.main}
              >
                {label}
              </text>
            </g>
          );
        })}
      </svg>

    </AbsoluteFill>
  );
};
