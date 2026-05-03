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
  date:          string;
  period:        string;
  current_price: number;
  rsi:           number;
  macd:          number;
  macd_signal:   number;
  macd_hist:     number;
  hist_series:   HistPoint[];
  bb_upper:      number;
  bb_mid:        number;
  bb_lower:      number;
  bb_pct:        number;
  atr:           number;
  atr_pct:       number;
  sma20:         number;
  sma50:         number;
  sma200:        number;
}

// ─── Fixed layout constants (1200 × 400) ──────────────────────────────────────
const CANVAS_W  = 1200;
const CANVAS_H  = 400;
const HEADER_H  = 44;
const PANEL_W   = CANVAS_W / 3;       // 400
const CONTENT_Y = HEADER_H;
const CONTENT_H = CANVAS_H - HEADER_H; // 356
const PAD_X     = 18;
const PAD_Y     = 14;

// MACD histogram: usable width inside panel (minus padding each side)
const HIST_W    = PANEL_W - PAD_X * 2; // 364
const HIST_H    = 196;  // SVG height
const HIST_MID  = HIST_H / 2;          // baseline at center

// ─── Component ────────────────────────────────────────────────────────────────
export const TechnicalDashboard: React.FC<Props> = ({
  date, period, current_price, rsi, macd, macd_signal, macd_hist,
  hist_series, bb_upper, bb_mid, bb_lower, bb_pct, atr, atr_pct,
  sma20, sma50, sma200,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Single spring drives all fill animations simultaneously
  const s = spring({ frame: frame - 3, fps, config: { damping: 80, stiffness: 100, mass: 1 } });
  const progress = interpolate(s, [0, 1], [0, 1]);

  // ── Derived ──────────────────────────────────────────────────────────────
  const rsiColor   = rsi > 70 ? colors.red : rsi < 30 ? colors.green : colors.gold;
  const rsiLabel   = rsi > 70 ? "OVERBOUGHT" : rsi < 30 ? "OVERSOLD" : "NEUTRAL";
  const animRsi    = rsi * progress;

  const atrColor   = atr_pct > 1.5 ? colors.red : atr_pct < 0.7 ? colors.green : colors.gold;
  const atrLabel   = atr_pct > 1.5 ? "HIGH VOL" : atr_pct < 0.7 ? "LOW VOL"  : "MOD VOL";

  const maxAbsHist = Math.max(...hist_series.map(p => Math.abs(p.macd_hist)), 0.001);
  const barMaxH    = HIST_MID - 6;

  // BB marker animates from 50 → actual bb_pct
  const animBbPct  = 50 + (bb_pct - 50) * progress;
  const markerLeft = Math.max(3, Math.min(97, animBbPct));
  // Label x stays within panel interior
  const labelPct   = Math.max(5, Math.min(88, markerLeft - 5));

  const fmt0 = (v: number) =>
    "$" + v.toLocaleString("en-US", { maximumFractionDigits: 0 });

  // Shared panel title style
  const titleStyle: React.CSSProperties = {
    fontSize: 18, fontWeight: 600, color: colors.textDim,
    letterSpacing: 2, textTransform: "uppercase" as const,
    marginBottom: 10,
  };

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
          Technical Indicators · 7D
        </span>
        <span style={{ fontSize: 20, fontWeight: 600, color: colors.textSecondary, letterSpacing: 1 }}>
          {period}
        </span>
      </div>

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* Panel 1 — RSI                                                         */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      <div style={{
        position: "absolute",
        top: CONTENT_Y, left: 0,
        width: PANEL_W, height: CONTENT_H,
        padding: `${PAD_Y}px ${PAD_X}px`,
        borderRight: `1px solid ${colors.surfaceLight}`,
        display: "flex", flexDirection: "column", gap: 0,
      }}>
        <div style={titleStyle}>RSI (14)</div>

        {/* Big RSI value + status */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
          <span style={{ fontSize: 42, fontWeight: 800, color: rsiColor, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>
            {animRsi.toFixed(1)}
          </span>
          <span style={{
            fontSize: 18, fontWeight: 700, color: rsiColor,
            backgroundColor: `${rsiColor}22`, border: `1px solid ${rsiColor}55`,
            borderRadius: 5, padding: "4px 9px", letterSpacing: 1,
          }}>
            {rsiLabel}
          </span>
        </div>

        {/* Gauge track */}
        <div style={{ position: "relative", height: 14, borderRadius: 7, backgroundColor: colors.surfaceLight, marginBottom: 8 }}>
          {[30, 70].map(z => (
            <div key={z} style={{
              position: "absolute", top: 0, bottom: 0, left: `${z}%`,
              width: 1, backgroundColor: colors.textDim, opacity: 0.5,
            }} />
          ))}
          <div style={{
            position: "absolute", left: 0, top: 0, bottom: 0,
            width: `${animRsi}%`, borderRadius: 7,
            backgroundColor: rsiColor, opacity: 0.75,
          }} />
          {progress > 0.05 && (
            <div style={{
              position: "absolute", top: "50%", left: `${animRsi}%`,
              transform: "translate(-50%, -50%)",
              width: 16, height: 16, borderRadius: "50%",
              backgroundColor: rsiColor, boxShadow: `0 0 8px ${rsiColor}`,
            }} />
          )}
        </div>

        {/* Zone labels */}
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 17, marginBottom: 20 }}>
          <span style={{ color: colors.green }}>0</span>
          <span style={{ color: colors.textDim }}>30</span>
          <span style={{ color: colors.textDim }}>50</span>
          <span style={{ color: colors.textDim }}>70</span>
          <span style={{ color: colors.red }}>100</span>
        </div>

        {/* Separator */}
        <div style={{ flex: 1 }} />

        {/* ATR row at bottom */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          borderTop: `1px solid ${colors.surfaceLight}`, paddingTop: 10,
        }}>
          <span style={{ fontSize: 18, color: colors.textDim }}>ATR (14)</span>
          <span style={{ fontSize: 22, fontWeight: 600, color: colors.text, fontVariantNumeric: "tabular-nums" }}>
            ${atr.toFixed(1)}
          </span>
          <span style={{
            fontSize: 18, fontWeight: 700, color: atrColor,
            backgroundColor: `${atrColor}22`, border: `1px solid ${atrColor}44`,
            borderRadius: 4, padding: "3px 8px",
          }}>
            {atrLabel}
          </span>
          <span style={{ fontSize: 18, color: atrColor, fontVariantNumeric: "tabular-nums" }}>
            {atr_pct.toFixed(2)}%
          </span>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* Panel 2 — MACD histogram                                              */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      <div style={{
        position: "absolute",
        top: CONTENT_Y, left: PANEL_W,
        width: PANEL_W, height: CONTENT_H,
        padding: `${PAD_Y}px ${PAD_X}px`,
        borderRight: `1px solid ${colors.surfaceLight}`,
        display: "flex", flexDirection: "column",
      }}>
        <div style={titleStyle}>MACD (12, 26, 9)</div>

        {/* Histogram SVG */}
        <svg width={HIST_W} height={HIST_H} style={{ display: "block", flexShrink: 0 }}>
          {/* Baseline */}
          <line x1={0} y1={HIST_MID} x2={HIST_W} y2={HIST_MID}
            stroke={colors.surfaceLight} strokeWidth={1} />

          {hist_series.map((point, i) => {
            const isPos      = point.macd_hist >= 0;
            const barH       = (Math.abs(point.macd_hist) / maxAbsHist) * barMaxH * progress;
            const barColor   = isPos ? colors.green : colors.red;
            const isLatest   = i === hist_series.length - 1;
            const slotW      = HIST_W / hist_series.length;
            const x          = i * slotW;
            const w          = slotW - 1.5;
            const y          = isPos ? HIST_MID - barH : HIST_MID;
            return (
              <rect
                key={i}
                x={x} y={y} width={w} height={barH}
                fill={barColor}
                opacity={isLatest ? 1 : 0.55}
              />
            );
          })}
        </svg>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Mini metric cards */}
        <div style={{ display: "flex", gap: 8 }}>
          {[
            { label: "MACD",   value: macd,        color: macd >= 0 ? colors.green : colors.red },
            { label: "Signal", value: macd_signal,  color: macd_signal >= 0 ? colors.green : colors.red },
            { label: "Hist",   value: macd_hist,    color: macd_hist >= 0 ? colors.green : colors.red },
          ].map(({ label, value, color }) => (
            <div key={label} style={{
              flex: 1, backgroundColor: colors.surface,
              borderRadius: 6, padding: "8px 10px",
              borderTop: `2px solid ${color}`,
            }}>
              <div style={{ fontSize: 17, color: colors.textDim, marginBottom: 4 }}>{label}</div>
              <div style={{ fontSize: 20, fontWeight: 700, color, fontVariantNumeric: "tabular-nums" }}>
                {value >= 0 ? "+" : ""}{value.toFixed(2)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* Panel 3 — Bollinger Bands                                             */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      <div style={{
        position: "absolute",
        top: CONTENT_Y, left: PANEL_W * 2,
        width: PANEL_W, height: CONTENT_H,
        padding: `${PAD_Y}px ${PAD_X}px`,
        display: "flex", flexDirection: "column",
      }}>
        <div style={titleStyle}>Bollinger Bands (20, 2σ)</div>

        {/* All three band numbers in one row */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 17, color: colors.textDim, letterSpacing: 1, marginBottom: 2 }}>LOWER</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: colors.green, fontVariantNumeric: "tabular-nums" }}>
              {fmt0(bb_lower)}
            </div>
          </div>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 17, color: colors.textDim, letterSpacing: 1, marginBottom: 2 }}>MID · SMA 20</div>
            <div style={{ fontSize: 22, fontWeight: 600, color: colors.gold, fontVariantNumeric: "tabular-nums" }}>
              {fmt0(bb_mid)}
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 17, color: colors.textDim, letterSpacing: 1, marginBottom: 2 }}>UPPER</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: colors.red, fontVariantNumeric: "tabular-nums" }}>
              {fmt0(bb_upper)}
            </div>
          </div>
        </div>

        {/* Range bar + animated marker */}
        <div>
          <div style={{ position: "relative", height: 12, borderRadius: 6, backgroundColor: colors.surfaceLight }}>
            <div style={{
              position: "absolute", left: 0, top: 0, height: "100%",
              width: `${markerLeft}%`, borderRadius: 6,
              background: `linear-gradient(90deg, ${colors.green}55, ${colors.gold})`,
            }} />
            <div style={{
              position: "absolute", top: "50%", left: `${markerLeft}%`,
              transform: "translate(-50%, -50%)",
              width: 16, height: 16, borderRadius: "50%",
              backgroundColor: colors.gold, boxShadow: `0 0 10px ${colors.goldGlow}`,
              opacity: progress > 0.05 ? 1 : 0,
            }} />
          </div>

          {/* Current price label tracks marker */}
          <div style={{ position: "relative", height: 42, marginTop: 4 }}>
            <div style={{ position: "absolute", top: 0, left: `${labelPct}%` }}>
              <div style={{ fontSize: 22, fontWeight: 700, color: colors.gold, fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" as const }}>
                {fmt0(current_price)}
              </div>
              <div style={{ fontSize: 17, color: colors.textDim }}>
                {bb_pct.toFixed(1)}% of band
              </div>
            </div>
          </div>
        </div>

        {/* ── SMA rows ──────────────────────────────────────────────────── */}
        <div style={{ flex: 1 }} />
        <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
          {([
            { label: "SMA 20",  value: sma20  },
            { label: "SMA 50",  value: sma50  },
            { label: "SMA 200", value: sma200 },
          ] as { label: string; value: number }[]).map(({ label, value }) => {
            const pct   = (current_price - value) / value * 100;
            const isPos = pct >= 0;
            const col   = isPos ? colors.green : colors.red;
            return (
              <div key={label} style={{
                display: "flex", alignItems: "center", gap: 10,
                backgroundColor: colors.surface, borderRadius: 6,
                borderLeft: `3px solid ${col}`,
                padding: "8px 12px",
              }}>
                <span style={{ fontSize: 17, color: colors.textDim, flex: 1 }}>{label}</span>
                <span style={{ fontSize: 17, fontWeight: 600, color: colors.text, fontVariantNumeric: "tabular-nums" }}>
                  {fmt0(value)}
                </span>
                <span style={{ fontSize: 17, fontWeight: 700, color: col, fontVariantNumeric: "tabular-nums", minWidth: 90, textAlign: "right" as const }}>
                  {isPos ? "▲" : "▼"} {isPos ? "+" : ""}{pct.toFixed(2)}%
                </span>
              </div>
            );
          })}
        </div>

      </div>

    </AbsoluteFill>
  );
};
