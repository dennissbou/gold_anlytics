import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { colors, fonts } from "./theme";

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

// ─── Layout (800 × 800) — 2-row grid ─────────────────────────────────────────
const CANVAS_W  = 800;
const CANVAS_H  = 800;
const HEADER_H  = 62;
const CONTENT_H = CANVAS_H - HEADER_H;   // 738
const TOP_H     = 350;                    // RSI | MACD row
const BOT_H     = CONTENT_H - TOP_H;     // 388 — BB + SMA row
const HALF_W    = CANVAS_W / 2;          // 400
const PAD_X     = 20;
const PAD_Y     = 16;

// MACD histogram (right-top panel)
const HIST_W    = HALF_W - PAD_X * 2;    // 360
const HIST_H    = 180;
const HIST_MID  = HIST_H / 2;

// ─── Component ────────────────────────────────────────────────────────────────
export const TechnicalDashboardSquare: React.FC<Props> = ({
  period, current_price, rsi, macd, macd_signal, macd_hist,
  hist_series, bb_upper, bb_mid, bb_lower, bb_pct, atr, atr_pct,
  sma20, sma50, sma200,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const s        = spring({ frame: frame - 3, fps, config: { damping: 80, stiffness: 100, mass: 1 } });
  const progress = interpolate(s, [0, 1], [0, 1]);

  // RSI
  const rsiColor  = rsi > 70 ? colors.red : rsi < 30 ? colors.green : colors.gold;
  const rsiLabel  = rsi > 70 ? "OVERBOUGHT" : rsi < 30 ? "OVERSOLD" : "NEUTRAL";
  const animRsi   = rsi * progress;

  // ATR
  const atrColor  = atr_pct > 1.5 ? colors.red : atr_pct < 0.7 ? colors.green : colors.gold;
  const atrLabel  = atr_pct > 1.5 ? "HIGH VOL" : atr_pct < 0.7 ? "LOW VOL"  : "MOD VOL";

  // MACD histogram
  const maxAbsHist = Math.max(...hist_series.map(p => Math.abs(p.macd_hist)), 0.001);
  const barMaxH    = HIST_MID - 6;

  // BB marker
  const animBbPct  = 50 + (bb_pct - 50) * progress;
  const markerLeft = Math.max(3, Math.min(97, animBbPct));
  const labelPct   = Math.max(5, Math.min(85, markerLeft - 5));

  const fmt0 = (v: number) =>
    "$" + v.toLocaleString("en-US", { maximumFractionDigits: 0 });

  const titleStyle: React.CSSProperties = {
    fontSize: 20, fontWeight: 600, color: colors.textDim,
    letterSpacing: 2, textTransform: "uppercase" as const,
    marginBottom: 14,
  };

  const divider = `1px solid ${colors.surfaceLight}`;

  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg, fontFamily: fonts.main, overflow: "hidden" }}>

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: HEADER_H,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        paddingLeft: 18, paddingRight: 18,
        borderBottom: divider,
      }}>
        <span style={{ fontSize: 22, fontWeight: 700, color: colors.gold, letterSpacing: 3, textTransform: "uppercase" as const }}>
          Technical Indicators · 7D
        </span>
        <span style={{ fontSize: 22, fontWeight: 600, color: colors.textSecondary, letterSpacing: 1 }}>
          {period}
        </span>
      </div>

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* TOP-LEFT — RSI                                                        */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      <div style={{
        position: "absolute",
        top: HEADER_H, left: 0,
        width: HALF_W, height: TOP_H,
        padding: `${PAD_Y}px ${PAD_X}px`,
        borderRight: divider, borderBottom: divider,
        display: "flex", flexDirection: "column",
      }}>
        <div style={titleStyle}>RSI (14)</div>

        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 18 }}>
          <span style={{ fontSize: 58, fontWeight: 800, color: rsiColor, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>
            {animRsi.toFixed(1)}
          </span>
          <span style={{
            fontSize: 19, fontWeight: 700, color: rsiColor,
            backgroundColor: `${rsiColor}22`, border: `1px solid ${rsiColor}55`,
            borderRadius: 5, padding: "6px 12px", letterSpacing: 1,
          }}>
            {rsiLabel}
          </span>
        </div>

        {/* Gauge */}
        <div style={{ position: "relative", height: 18, borderRadius: 9, backgroundColor: colors.surfaceLight, marginBottom: 10 }}>
          {[30, 70].map(z => (
            <div key={z} style={{
              position: "absolute", top: 0, bottom: 0, left: `${z}%`,
              width: 1, backgroundColor: colors.textDim, opacity: 0.5,
            }} />
          ))}
          <div style={{
            position: "absolute", left: 0, top: 0, bottom: 0,
            width: `${animRsi}%`, borderRadius: 9,
            backgroundColor: rsiColor, opacity: 0.75,
          }} />
          {progress > 0.05 && (
            <div style={{
              position: "absolute", top: "50%", left: `${animRsi}%`,
              transform: "translate(-50%, -50%)",
              width: 22, height: 22, borderRadius: "50%",
              backgroundColor: rsiColor, boxShadow: `0 0 10px ${rsiColor}`,
            }} />
          )}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 17, marginBottom: 0 }}>
          <span style={{ color: colors.green }}>0</span>
          <span style={{ color: colors.textDim }}>30</span>
          <span style={{ color: colors.textDim }}>50</span>
          <span style={{ color: colors.textDim }}>70</span>
          <span style={{ color: colors.red }}>100</span>
        </div>

        <div style={{ flex: 1 }} />

        {/* ATR */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          borderTop: divider, paddingTop: 12,
        }}>
          <span style={{ fontSize: 18, color: colors.textDim }}>ATR (14)</span>
          <span style={{ fontSize: 22, fontWeight: 600, color: colors.text, fontVariantNumeric: "tabular-nums" }}>
            ${atr.toFixed(1)}
          </span>
          <span style={{
            fontSize: 18, fontWeight: 700, color: atrColor,
            backgroundColor: `${atrColor}22`, border: `1px solid ${atrColor}44`,
            borderRadius: 4, padding: "4px 10px",
          }}>
            {atrLabel}
          </span>
          <span style={{ fontSize: 17, color: atrColor, fontVariantNumeric: "tabular-nums" }}>
            {atr_pct.toFixed(2)}%
          </span>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* TOP-RIGHT — MACD                                                      */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      <div style={{
        position: "absolute",
        top: HEADER_H, left: HALF_W,
        width: HALF_W, height: TOP_H,
        padding: `${PAD_Y}px ${PAD_X}px`,
        borderBottom: divider,
        display: "flex", flexDirection: "column",
      }}>
        <div style={titleStyle}>MACD (12, 26, 9)</div>

        <svg width={HIST_W} height={HIST_H} style={{ display: "block", flexShrink: 0 }}>
          <line x1={0} y1={HIST_MID} x2={HIST_W} y2={HIST_MID}
            stroke={colors.surfaceLight} strokeWidth={1} />
          {hist_series.map((point, i) => {
            const isPos    = point.macd_hist >= 0;
            const barH     = (Math.abs(point.macd_hist) / maxAbsHist) * barMaxH * progress;
            const barColor = isPos ? colors.green : colors.red;
            const isLatest = i === hist_series.length - 1;
            const slotW    = HIST_W / hist_series.length;
            const x        = i * slotW;
            const w        = slotW - 2;
            const y        = isPos ? HIST_MID - barH : HIST_MID;
            return (
              <rect key={i} x={x} y={y} width={w} height={barH}
                fill={barColor} opacity={isLatest ? 1 : 0.55} />
            );
          })}
        </svg>

        <div style={{ flex: 1 }} />

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
              <div style={{ fontSize: 16, color: colors.textDim, marginBottom: 4 }}>{label}</div>
              <div style={{ fontSize: 19, fontWeight: 700, color, fontVariantNumeric: "tabular-nums" }}>
                {value >= 0 ? "+" : ""}{value.toFixed(2)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* BOTTOM — Bollinger Bands (left) + SMA (right)                         */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      <div style={{
        position: "absolute",
        top: HEADER_H + TOP_H, left: 0,
        width: CANVAS_W, height: BOT_H,
        display: "flex", flexDirection: "row",
      }}>

        {/* ── BB left half ─────────────────────────────────────────────── */}
        <div style={{
          width: HALF_W, height: BOT_H,
          padding: `${PAD_Y}px ${PAD_X}px`,
          borderRight: divider,
          display: "flex", flexDirection: "column",
        }}>
          <div style={titleStyle}>Bollinger Bands (20, 2σ)</div>

          {/* LOWER | MID | UPPER */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 16 }}>
            <div>
              <div style={{ fontSize: 16, color: colors.textDim, letterSpacing: 1, marginBottom: 2 }}>LOWER</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: colors.green, fontVariantNumeric: "tabular-nums" }}>
                {fmt0(bb_lower)}
              </div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 16, color: colors.textDim, letterSpacing: 1, marginBottom: 2 }}>MID · SMA 20</div>
              <div style={{ fontSize: 21, fontWeight: 600, color: colors.gold, fontVariantNumeric: "tabular-nums" }}>
                {fmt0(bb_mid)}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 16, color: colors.textDim, letterSpacing: 1, marginBottom: 2 }}>UPPER</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: colors.red, fontVariantNumeric: "tabular-nums" }}>
                {fmt0(bb_upper)}
              </div>
            </div>
          </div>

          {/* Range bar */}
          <div>
            <div style={{ position: "relative", height: 16, borderRadius: 8, backgroundColor: colors.surfaceLight }}>
              <div style={{
                position: "absolute", left: 0, top: 0, height: "100%",
                width: `${markerLeft}%`, borderRadius: 8,
                background: `linear-gradient(90deg, ${colors.green}55, ${colors.gold})`,
              }} />
              <div style={{
                position: "absolute", top: "50%", left: `${markerLeft}%`,
                transform: "translate(-50%, -50%)",
                width: 22, height: 22, borderRadius: "50%",
                backgroundColor: colors.gold, boxShadow: `0 0 12px ${colors.goldGlow}`,
                opacity: progress > 0.05 ? 1 : 0,
              }} />
            </div>
            <div style={{ position: "relative", height: 44, marginTop: 8 }}>
              <div style={{ position: "absolute", top: 0, left: `${labelPct}%` }}>
                <div style={{ fontSize: 22, fontWeight: 700, color: colors.gold, fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" as const }}>
                  {fmt0(current_price)}
                </div>
                <div style={{ fontSize: 16, color: colors.textDim }}>
                  {bb_pct.toFixed(1)}% of band
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── SMA right half ───────────────────────────────────────────── */}
        <div style={{
          width: HALF_W, height: BOT_H,
          padding: `${PAD_Y}px ${PAD_X}px`,
          display: "flex", flexDirection: "column",
          justifyContent: "center", gap: 12,
        }}>
          <div style={{ ...titleStyle, marginBottom: 16 }}>Moving Averages</div>
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
                padding: "12px 14px",
              }}>
                <span style={{ fontSize: 18, color: colors.textDim, flex: 1 }}>{label}</span>
                <span style={{ fontSize: 18, fontWeight: 600, color: colors.text, fontVariantNumeric: "tabular-nums" }}>
                  {fmt0(value)}
                </span>
                <span style={{ fontSize: 18, fontWeight: 700, color: col, fontVariantNumeric: "tabular-nums", minWidth: 110, textAlign: "right" as const }}>
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
