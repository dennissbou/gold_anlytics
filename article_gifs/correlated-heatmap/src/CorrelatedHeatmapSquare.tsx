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

// ─── Fixed layout constants (800 × 800) ──────────────────────────────────────
const CANVAS_W  = 800;
const CANVAS_H  = 800;
const HEADER_H  = 62;
const X_AXIS_H  = 50;
const LEFT_W    = 326;
const CHART_X   = LEFT_W;
const CHART_W   = CANVAS_W - LEFT_W;    // 474
const HALF_W    = CHART_W / 2;          // 237
const CHART_Y   = HEADER_H;
const CHART_H   = CANVAS_H - HEADER_H - X_AXIS_H;  // 688
const N         = 7;
const ROW_H     = CHART_H / N;          // ≈ 98.3
const BAR_H     = 46;
const BAR_OFF   = (ROW_H - BAR_H) / 2;

const formatPrice = (symbol: string, price: number | null): string => {
  if (price === null) return "—";
  if (symbol === "GOLD")   return "$" + price.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  if (symbol === "SPX")    return price.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  if (symbol === "BTC")    return "$" + price.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  if (symbol === "SILVER") return "$" + price.toFixed(2);
  if (symbol === "WTI")    return "$" + price.toFixed(2);
  return price.toFixed(2);
};

export const CorrelatedHeatmapSquare: React.FC<Props> = ({ period, assets }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const maxAbsPct = Math.max(0.5, ...assets.map(a => Math.abs(a.change_pct ?? 0)));
  const capPct    = Math.ceil(maxAbsPct * 1.25 * 2) / 2;
  const pctToPx   = HALF_W / capPct;
  const tickStep  = capPct / 2;
  const ticks     = [-capPct, -tickStep, 0, tickStep, capPct];

  const barSpring   = spring({ frame: frame - 5, fps, config: { damping: 80, stiffness: 100, mass: 1 } });
  const barProgress = interpolate(barSpring, [0, 1], [0, 1]);

  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg, fontFamily: fonts.main, overflow: "hidden" }}>

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: HEADER_H,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        paddingLeft: 18, paddingRight: 18,
        borderBottom: `1px solid ${colors.surfaceLight}`,
      }}>
        <span style={{ fontSize: 22, fontWeight: 700, color: colors.gold, letterSpacing: 3, textTransform: "uppercase" as const }}>
          Market Heatmap · Weekly
        </span>
        <span style={{ fontSize: 22, fontWeight: 600, color: colors.textSecondary, letterSpacing: 1 }}>
          {period}
        </span>
      </div>

      {/* ── Left column rows ────────────────────────────────────────────────── */}
      {assets.map((asset, i) => {
        const rowY   = CHART_Y + i * ROW_H;
        const isGold = asset.symbol === "GOLD";
        return (
          <div key={asset.symbol} style={{
            position: "absolute", top: rowY, left: 0, width: LEFT_W, height: ROW_H,
            display: "flex", flexDirection: "row", alignItems: "center",
            paddingLeft: 12, paddingRight: 12, gap: 10,
            borderBottom: `1px solid ${colors.surfaceLight}`,
          }}>
            <div style={{ flexShrink: 0 }}>
              <AssetIcon symbol={asset.symbol} size={36} />
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2, overflow: "hidden" }}>
              <span style={{
                fontSize: 19, fontWeight: isGold ? 700 : 500,
                color: isGold ? colors.gold : colors.textSecondary,
                whiteSpace: "nowrap" as const, overflow: "hidden", textOverflow: "ellipsis",
              }}>
                {asset.name}
              </span>
              <span style={{ fontSize: 15, color: colors.textDim }}>
                {asset.label}
              </span>
            </div>
            <span style={{
              fontSize: 18, fontWeight: 600, color: colors.text,
              fontVariantNumeric: "tabular-nums", flexShrink: 0, whiteSpace: "nowrap" as const,
            }}>
              {formatPrice(asset.symbol, asset.close)}
            </span>
            <div style={{
              position: "absolute", right: 0, top: 8, bottom: 8,
              width: 1, backgroundColor: colors.surfaceLight,
            }} />
          </div>
        );
      })}

      {/* ── Bar chart (SVG) ─────────────────────────────────────────────────── */}
      <svg width={CHART_W} height={CHART_H}
        style={{ position: "absolute", top: CHART_Y, left: CHART_X }}>
        <line x1={HALF_W} y1={0} x2={HALF_W} y2={CHART_H}
          stroke={colors.surfaceLight} strokeWidth={1} />
        {assets.map((_, i) => (
          <line key={i} x1={0} y1={(i + 1) * ROW_H} x2={CHART_W} y2={(i + 1) * ROW_H}
            stroke={colors.surfaceLight} strokeWidth={0.5} opacity={0.5} />
        ))}
        {assets.map((asset, i) => {
          const pct      = asset.change_pct ?? 0;
          const isPos    = pct >= 0;
          const barColor = isPos ? colors.green : colors.red;
          const finalW   = Math.min(Math.abs(pct), capPct) * pctToPx;
          const animW    = finalW * barProgress;
          const barX     = isPos ? HALF_W : HALF_W - animW;
          const barY     = i * ROW_H + BAR_OFF;
          const midY     = barY + BAR_H / 2 + 6;
          const labelX   = isPos ? HALF_W + animW + 12 : HALF_W - animW - 12;
          const anchor   = isPos ? "start" : "end";
          return (
            <g key={asset.symbol}>
              <rect x={barX} y={barY} width={animW} height={BAR_H}
                fill={barColor} opacity={0.9} rx={4} />
              {barProgress > 0.1 && asset.change_pct !== null && (
                <text x={labelX} y={midY} textAnchor={anchor}
                  fill={barColor} fontSize={19} fontWeight={700} fontFamily={fonts.main}>
                  {isPos ? "+" : ""}{pct.toFixed(2)}%
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* ── X-axis ──────────────────────────────────────────────────────────── */}
      <svg width={CHART_W} height={X_AXIS_H}
        style={{ position: "absolute", bottom: 0, left: CHART_X }}>
        <line x1={0} y1={0} x2={CHART_W} y2={0}
          stroke={colors.surfaceLight} strokeWidth={1} />
        {ticks.map((tick, idx) => {
          const x      = HALF_W + tick * pctToPx;
          const isZero = tick === 0;
          const isFirst = idx === 0;
          const isLast  = idx === ticks.length - 1;
          const anchor  = isFirst ? "start" : isLast ? "end" : "middle";
          const label   = tick > 0 ? `+${tick}%` : tick === 0 ? "0" : `${tick}%`;
          return (
            <g key={tick}>
              <line x1={x} y1={0} x2={x} y2={isZero ? 10 : 6}
                stroke={isZero ? colors.textDim : "#333"} strokeWidth={1} />
              <text x={x} y={X_AXIS_H - 8} textAnchor={anchor}
                fill={isZero ? colors.textSecondary : colors.textDim}
                fontSize={19} fontFamily={fonts.main}>
                {label}
              </text>
            </g>
          );
        })}
      </svg>

    </AbsoluteFill>
  );
};
