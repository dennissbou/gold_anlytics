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
export interface HourlyCandle {
  hour: string; // "00:00", "01:00", etc.
  open: number;
  high: number;
  low: number;
  close: number;
}

interface WeekPoint  { label: string; price: number; pct: number; }
interface MonthPoint { label: string; price: number; pct: number; }

interface Props {
  candles: HourlyCandle[];
  prev_candles?: HourlyCandle[];
  title?: string;
  date?: string;
  change_pct?: number;
  // Stat overview data
  week_pct?: number;
  week_series?: WeekPoint[];
  month_pct?: number;
  month_series?: MonthPoint[];
  support?: number;
  resistance?: number;
}

// ─── Timing ───────────────────────────────────────────────
const INTRO_FRAMES = 8;       // 0.27s intro before first candle
const FRAMES_PER_CANDLE = 7;  // 0.23s per candle at 30fps
const HOLD_FRAMES = 90;       // 3s hold at end — gives stats time to animate + be read

// ─── Layout ───────────────────────────────────────────────
const PADDING_X = 160;
const PADDING_X_RIGHT = 220;
const CHART_TOP = 450;
const CHART_BOTTOM = 1040;
const CHART_HEIGHT = CHART_BOTTOM - CHART_TOP; // 590
const CHART_WIDTH = 1080 - PADDING_X - PADDING_X_RIGHT;

// ─── Component ────────────────────────────────────────────
export const RollingCandles: React.FC<Props> = ({
  candles,
  prev_candles = [],
  title = "XAUUSD · 24H",
  date,
  change_pct,
  week_pct,
  week_series = [],
  month_pct,
  month_series = [],
  support,
  resistance,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const numCandles = candles.length;
  const totalSlots = prev_candles.length + numCandles;
  const slotWidth = CHART_WIDTH / totalSlots;
  const candleBodyWidth = Math.min(slotWidth * 0.6, 22);

  // Price range for Y axis — include both days
  const allHighs = [...candles, ...prev_candles].map((c) => c.high);
  const allLows = [...candles, ...prev_candles].map((c) => c.low);
  const priceMin = Math.min(...allLows);
  const priceMax = Math.max(...allHighs);
  const pricePadding = (priceMax - priceMin) * 0.08;
  const yMin = priceMin - pricePadding;
  const yMax = priceMax + pricePadding;

  // Map price to Y coordinate (top = high price, bottom = low price)
  const priceToY = (price: number) => {
    return CHART_TOP + (1 - (price - yMin) / (yMax - yMin)) * CHART_HEIGHT;
  };

  // Current price (most recently revealed candle)
  const revealedCount = Math.min(
    numCandles,
    Math.floor((frame - INTRO_FRAMES) / FRAMES_PER_CANDLE) + 1
  );
  const currentCandle = candles[Math.max(0, Math.min(revealedCount - 1, numCandles - 1))];
  const isUp = currentCandle.close >= currentCandle.open;

  // Animated current price display
  const prevCandle = revealedCount >= 2 ? candles[revealedCount - 2] : candles[0];
  const priceProgress = spring({
    frame: Math.max(0, frame - INTRO_FRAMES - (revealedCount - 1) * FRAMES_PER_CANDLE),
    fps,
    config: { damping: 100, stiffness: 80, mass: 1 },
    durationInFrames: FRAMES_PER_CANDLE,
  });
  const displayPrice = interpolate(
    priceProgress,
    [0, 1],
    [prevCandle.close, currentCandle.close]
  );

  // Header fade in
  const headerOpacity = interpolate(frame, [0, 30], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Watermark appears after all candles
  const allRevealed = frame > INTRO_FRAMES + (numCandles - 1) * FRAMES_PER_CANDLE + 30;
  const watermarkOpacity = allRevealed
    ? interpolate(
        frame - (INTRO_FRAMES + (numCandles - 1) * FRAMES_PER_CANDLE + 30),
        [0, 30],
        [0, 0.5],
        { extrapolateRight: "clamp" }
      )
    : 0;

  // Generate Y-axis price labels (5 levels)
  const priceLabels = Array.from({ length: 5 }, (_, i) => {
    const price = yMin + ((yMax - yMin) * i) / 4;
    return { price, y: priceToY(price) };
  });

  // ─── Stat overview animations (start at frame 90 = 3s) ─────────────────────
  const STAT_START = 60;
  const statRowSpring = (i: number) =>
    spring({
      frame: frame - (STAT_START + i * 15),
      fps,
      config: { damping: 80, stiffness: 160, mass: 0.8 },
    });

  // Month counter (synced to stat appearance)
  const nm = month_series.length;
  const FRAMES_PER_MONTH_STEP = 7;
  const monthProgress = Math.max(0, frame - STAT_START);
  const rawMonthStep = monthProgress / FRAMES_PER_MONTH_STEP;
  const monthStepIdx = Math.min(Math.floor(rawMonthStep), nm - 1);
  const monthStepFrac = rawMonthStep - monthStepIdx;
  const animMonthPct = nm === 0 ? 0
    : monthStepIdx >= nm - 1 ? month_series[nm - 1].pct
    : month_series[monthStepIdx].pct + (month_series[monthStepIdx + 1].pct - month_series[monthStepIdx].pct) * monthStepFrac;
  const animMonthPrice = nm === 0 ? 0
    : monthStepIdx >= nm - 1 ? month_series[nm - 1].price
    : month_series[monthStepIdx].price + (month_series[monthStepIdx + 1].price - month_series[monthStepIdx].price) * monthStepFrac;

  // Week counter
  const nw = week_series.length;
  const MONTH_TOTAL = (nm - 1) * FRAMES_PER_MONTH_STEP;
  const FRAMES_PER_WEEK_STEP = nw > 1 ? MONTH_TOTAL / (nw - 1) : 30;
  const weekProgress = Math.max(0, frame - STAT_START);
  const rawWeekStep = weekProgress / FRAMES_PER_WEEK_STEP;
  const weekStepIdx = Math.min(Math.floor(rawWeekStep), nw - 1);
  const weekStepFrac = rawWeekStep - weekStepIdx;
  const animWeekPct = nw === 0 ? 0
    : weekStepIdx >= nw - 1 ? week_series[nw - 1].pct
    : week_series[weekStepIdx].pct + (week_series[weekStepIdx + 1].pct - week_series[weekStepIdx].pct) * weekStepFrac;
  const animWeekPrice = nw === 0 ? 0
    : weekStepIdx >= nw - 1 ? week_series[nw - 1].price
    : week_series[weekStepIdx].price + (week_series[weekStepIdx + 1].price - week_series[weekStepIdx].price) * weekStepFrac;

  const fmtPrice = (v: number) =>
    "$" + v.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

  // "00:00" → "0H", "04:00" → "4H", "16:00" → "16H"
  const fmtHour = (h: string) => `${parseInt(h, 10)}H`;

  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg }}>
      {/* ─── Disclaimer ──────────────────────── */}
      {/* ─── Header ──────────────────────────── */}
      <div
        style={{
          position: "absolute",
          top: 170,
          left: 0,
          right: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          opacity: headerOpacity,
        }}
      >
        <span
          style={{
            fontSize: 36,
            fontWeight: 500,
            color: colors.textSecondary,
            fontFamily: fonts.main,
            letterSpacing: 4,
          }}
        >
          {title}
        </span>
        <span
          style={{
            fontSize: 112,
            fontWeight: 800,
            fontFamily: fonts.main,
            color: colors.gold,
            textShadow: `0 0 40px ${colors.goldGlow}`,
            marginTop: 8,
            lineHeight: 1,
          }}
        >
          ${displayPrice.toLocaleString("en-US", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
          })}
        </span>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 20,
            marginTop: 16,
          }}
        >
          {date && (
            <span
              style={{
                fontSize: 30,
                fontWeight: 400,
                fontFamily: fonts.main,
                color: colors.textSecondary,
                letterSpacing: 1,
              }}
            >
              {new Date(date + "T12:00:00").toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </span>
          )}
          {(() => {
            const liveDelta = currentCandle.close - candles[0].open;
            const liveChange = (liveDelta / candles[0].open) * 100;
            const up = liveDelta >= 0;
            const sign = up ? "+" : "";
            const borderColor = up ? "rgba(249,219,109,0.3)" : "rgba(239,83,80,0.3)";
            const bgColor = up ? "rgba(249,219,109,0.15)" : "rgba(239,83,80,0.15)";
            return (
              <div
                style={{
                  display: "flex",
                  flexDirection: "row",
                  alignItems: "center",
                  gap: 16,
                  backgroundColor: bgColor,
                  border: `2px solid ${borderColor}`,
                  borderRadius: 10,
                  padding: "10px 24px",
                }}
              >
                <span
                  style={{
                    fontSize: 48,
                    fontWeight: 800,
                    fontFamily: fonts.main,
                    color: up ? colors.green : colors.red,
                    lineHeight: 1,
                  }}
                >
                  {sign}{liveChange.toFixed(2)}%
                </span>
                <span
                  style={{
                    fontSize: 48,
                    fontWeight: 600,
                    fontFamily: fonts.main,
                    color: up ? colors.green : colors.red,
                    opacity: 0.7,
                    lineHeight: 1,
                  }}
                >
                  ·
                </span>
                <span
                  style={{
                    fontSize: 48,
                    fontWeight: 600,
                    fontFamily: fonts.main,
                    color: up ? colors.green : colors.red,
                    opacity: 0.85,
                    lineHeight: 1,
                  }}
                >
                  {sign}${Math.abs(liveDelta).toFixed(1)}
                </span>
              </div>
            );
          })()}
        </div>
      </div>

      {/* ─── Chart Area ──────────────────────── */}
      <svg
        width={1080}
        height={1920}
        viewBox="0 0 1080 1920"
        style={{ position: "absolute", top: 0, left: 0 }}
      >
        {/* Grid lines */}
        {priceLabels.map(({ price, y }) => (
          <g key={price}>
            <line
              x1={PADDING_X}
              y1={y}
              x2={1080 - PADDING_X_RIGHT}
              y2={y}
              stroke={colors.surfaceLight}
              strokeWidth={1}
              opacity={0.4}
            />
            <text
              x={1080 - PADDING_X_RIGHT + 12}
              y={y + 6}
              fill={colors.textSecondary}
              fontSize={32}
              fontFamily={fonts.main}
            >
              {price.toFixed(0)}
            </text>
          </g>
        ))}

        {/* Previous day candles — slots 0..N-1, static, dimmed */}
        {prev_candles.map((candle, i) => {
          const cx = PADDING_X + slotWidth * i + slotWidth / 2;
          const up = candle.close >= candle.open;
          const color = up ? colors.green : colors.red;

          const bodyTop = priceToY(Math.max(candle.open, candle.close));
          const bodyBottom = priceToY(Math.min(candle.open, candle.close));
          const bodyHeight = Math.max(bodyBottom - bodyTop, 2);
          const wickTop = priceToY(candle.high);
          const wickBottom = priceToY(candle.low);

          return (
            <g key={`prev-${i}`} opacity={0.3}>
              <line x1={cx} y1={wickTop} x2={cx} y2={wickBottom} stroke={color} strokeWidth={1.5} />
              <rect x={cx - candleBodyWidth / 2} y={bodyTop} width={candleBodyWidth} height={bodyHeight} fill={color} rx={2} />
              {i % 4 === 0 && (
                <text x={cx} y={CHART_BOTTOM + 52} textAnchor="middle" fill={colors.textDim} fontSize={28} fontFamily={fonts.main}>
                  {fmtHour(candle.hour)}
                </text>
              )}
            </g>
          );
        })}

        {/* Day separator + date labels */}
        {prev_candles.length > 0 && date && (() => {
          const sepX = PADDING_X + slotWidth * prev_candles.length;
          const todayDate = new Date(date + "T12:00:00");
          const prevDate = new Date(todayDate);
          prevDate.setDate(prevDate.getDate() - 1);
          const fmt = (d: Date) => d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
          const labelY = CHART_BOTTOM + 96;
          const prevMidX = PADDING_X + slotWidth * prev_candles.length / 2;
          const todayMidX = sepX + slotWidth * numCandles / 2;
          return (
            <g>
              <line x1={sepX} y1={CHART_TOP} x2={sepX} y2={CHART_BOTTOM + 60} stroke={colors.gold} strokeWidth={1} strokeDasharray="6 4" opacity={0.4} />
              <text x={prevMidX} y={labelY} textAnchor="middle" fill={colors.textDim} fontSize={30} fontFamily={fonts.main}>{fmt(prevDate)}</text>
              <text x={todayMidX} y={labelY} textAnchor="middle" fill={colors.textSecondary} fontSize={30} fontFamily={fonts.main}>{fmt(todayDate)}</text>
            </g>
          );
        })()}

        {/* Current day candles — slots N..2N-1, rolling animation */}
        {candles.map((candle, i) => {
          const candleFrame = INTRO_FRAMES + i * FRAMES_PER_CANDLE;
          const isRevealed = frame >= candleFrame;
          if (!isRevealed) return null;

          const cx = PADDING_X + slotWidth * (prev_candles.length + i) + slotWidth / 2;
          const up = candle.close >= candle.open;
          const color = up ? colors.green : colors.red;

          const bodyTop = priceToY(Math.max(candle.open, candle.close));
          const bodyBottom = priceToY(Math.min(candle.open, candle.close));
          const bodyHeight = Math.max(bodyBottom - bodyTop, 2);
          const wickTop = priceToY(candle.high);
          const wickBottom = priceToY(candle.low);

          // Spring animation: candle grows from center
          const candleSpring = spring({
            frame: frame - candleFrame,
            fps,
            config: { damping: 70, stiffness: 180, mass: 0.6 },
          });

          // Glow on the latest candle
          const isLatest = i === revealedCount - 1;
          const glowOpacity = isLatest ? 0.6 : 0;

          return (
            <g key={i} opacity={candleSpring}>
              {/* Glow behind latest candle */}
              {isLatest && (
                <rect
                  x={cx - candleBodyWidth / 2 - 6}
                  y={wickTop - 6}
                  width={candleBodyWidth + 12}
                  height={wickBottom - wickTop + 12}
                  rx={6}
                  fill={color}
                  opacity={glowOpacity * 0.15}
                  filter="url(#candleGlow)"
                />
              )}

              {/* Wick */}
              <line
                x1={cx}
                y1={interpolate(candleSpring, [0, 1], [(wickTop + wickBottom) / 2, wickTop])}
                x2={cx}
                y2={interpolate(candleSpring, [0, 1], [(wickTop + wickBottom) / 2, wickBottom])}
                stroke={color}
                strokeWidth={2}
              />

              {/* Body */}
              <rect
                x={cx - candleBodyWidth / 2}
                y={interpolate(candleSpring, [0, 1], [(bodyTop + bodyBottom) / 2, bodyTop])}
                width={candleBodyWidth}
                height={interpolate(candleSpring, [0, 1], [0, bodyHeight])}
                fill={color}
                rx={2}
              />

              {/* Hour label every 4h */}
              {i % 4 === 0 && (
                <text
                  x={cx}
                  y={CHART_BOTTOM + 52}
                  textAnchor="middle"
                  fill={colors.textSecondary}
                  fontSize={28}
                  fontFamily={fonts.main}
                  opacity={candleSpring}
                >
                  {fmtHour(candle.hour)}
                </text>
              )}
            </g>
          );
        })}

        {/* Current price line (dashed) — spans only today's revealed candles */}
        {revealedCount > 0 && (
          <line
            x1={PADDING_X + slotWidth * prev_candles.length}
            y1={priceToY(currentCandle.close)}
            x2={PADDING_X + slotWidth * (prev_candles.length + revealedCount)}
            y2={priceToY(currentCandle.close)}
            stroke={isUp ? colors.green : colors.red}
            strokeWidth={1}
            strokeDasharray="8 6"
            opacity={0.6}
          />
        )}

        {/* Glow filter definition */}
        <defs>
          <filter id="candleGlow">
            <feGaussianBlur stdDeviation="8" />
          </filter>
        </defs>
      </svg>

      {/* ─── Stat Overview rows ──────────────── */}
      {week_series.length > 0 && (
        <div style={{
          position: "absolute",
          top: CHART_BOTTOM + 120,
          left: 44,
          right: 140,
          display: "flex",
          flexDirection: "column",
          gap: 18,
        }}>
          {/* Month row */}
          {(() => {
            const s = statRowSpring(0);
            const up = animMonthPct >= 0;
            const col = up ? colors.green : colors.red;
            const bg  = up ? "rgba(249,219,109,0.12)" : "rgba(239,83,80,0.12)";
            const bdr = up ? "rgba(249,219,109,0.30)" : "rgba(239,83,80,0.30)";
            const sign = up ? "+" : "";
            return (
              <div style={{
                opacity: interpolate(s, [0, 1], [0, 1]),
                transform: `translateY(${interpolate(s, [0, 1], [30, 0])}px)`,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                backgroundColor: colors.surface,
                borderRadius: 16,
                padding: "22px 36px",
                borderLeft: `4px solid ${colors.gold}`,
              }}>
                <span style={{ fontSize: 42, fontWeight: 500, fontFamily: fonts.main, color: colors.textSecondary, letterSpacing: 1 }}>Month</span>
                <div style={{ display: "flex", alignItems: "center", gap: 14, backgroundColor: bg, border: `2px solid ${bdr}`, borderRadius: 10, padding: "8px 20px" }}>
                  <span style={{ fontSize: 38, fontWeight: 800, fontFamily: fonts.main, color: col }}>{fmtPrice(animMonthPrice)}</span>
                  <span style={{ fontSize: 28, color: colors.textDim }}>|</span>
                  <span style={{ fontSize: 38, fontWeight: 700, fontFamily: fonts.main, color: col }}>{sign}{animMonthPct.toFixed(2)}%</span>
                </div>
              </div>
            );
          })()}

          {/* Week row */}
          {(() => {
            const s = statRowSpring(1);
            const up = animWeekPct >= 0;
            const col = up ? colors.green : colors.red;
            const bg  = up ? "rgba(249,219,109,0.12)" : "rgba(239,83,80,0.12)";
            const bdr = up ? "rgba(249,219,109,0.30)" : "rgba(239,83,80,0.30)";
            const sign = up ? "+" : "";
            return (
              <div style={{
                opacity: interpolate(s, [0, 1], [0, 1]),
                transform: `translateY(${interpolate(s, [0, 1], [30, 0])}px)`,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                backgroundColor: colors.surface,
                borderRadius: 16,
                padding: "22px 36px",
                borderLeft: `4px solid ${colors.gold}`,
              }}>
                <span style={{ fontSize: 42, fontWeight: 500, fontFamily: fonts.main, color: colors.textSecondary, letterSpacing: 1 }}>Week</span>
                <div style={{ display: "flex", alignItems: "center", gap: 14, backgroundColor: bg, border: `2px solid ${bdr}`, borderRadius: 10, padding: "8px 20px" }}>
                  <span style={{ fontSize: 38, fontWeight: 800, fontFamily: fonts.main, color: col }}>{fmtPrice(animWeekPrice)}</span>
                  <span style={{ fontSize: 28, color: colors.textDim }}>|</span>
                  <span style={{ fontSize: 38, fontWeight: 700, fontFamily: fonts.main, color: col }}>{sign}{animWeekPct.toFixed(2)}%</span>
                </div>
              </div>
            );
          })()}

          {/* Support / Resistance row */}
          {support !== undefined && resistance !== undefined && (() => {
            const s = statRowSpring(2);
            const markerPct = Math.max(0.02, Math.min(0.98, (animWeekPrice - support) / (resistance - support)));
            return (
              <div style={{
                opacity: interpolate(s, [0, 1], [0, 1]),
                transform: `translateY(${interpolate(s, [0, 1], [30, 0])}px)`,
                backgroundColor: colors.surface,
                borderRadius: 16,
                padding: "22px 36px",
                borderLeft: `4px solid ${colors.gold}`,
                display: "flex",
                flexDirection: "column",
                gap: 16,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    <span style={{ fontSize: 24, fontWeight: 500, fontFamily: fonts.main, color: colors.textDim, letterSpacing: 2 }}>SUPPORT</span>
                    <span style={{ fontSize: 40, fontWeight: 700, fontFamily: fonts.main, color: colors.green }}>{fmtPrice(support)}</span>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
                    <span style={{ fontSize: 24, fontWeight: 500, fontFamily: fonts.main, color: colors.textDim, letterSpacing: 2 }}>RESISTANCE</span>
                    <span style={{ fontSize: 40, fontWeight: 700, fontFamily: fonts.main, color: colors.red }}>{fmtPrice(resistance)}</span>
                  </div>
                </div>
                <div style={{ position: "relative", height: 16, borderRadius: 8, backgroundColor: colors.surfaceLight }}>
                  <div style={{ position: "absolute", left: 0, top: 0, height: "100%", width: `${markerPct * 100}%`, borderRadius: 8, background: `linear-gradient(90deg, ${colors.green}55, ${colors.gold})` }} />
                  <div style={{ position: "absolute", top: "50%", left: `${markerPct * 100}%`, transform: "translate(-50%, -50%)", width: 22, height: 22, borderRadius: "50%", backgroundColor: colors.gold, boxShadow: `0 0 10px ${colors.goldGlow}` }} />
                  <div style={{ position: "absolute", bottom: "calc(100% + 10px)", left: `${markerPct * 100}%`, transform: "translateX(-50%)", fontSize: 28, fontWeight: 700, fontFamily: fonts.main, color: colors.gold, whiteSpace: "nowrap", textShadow: `0 0 8px ${colors.goldGlow}` }}>
                    {fmtPrice(animWeekPrice)}
                  </div>
                </div>
              </div>
            );
          })()}
          {/* Disclaimer */}
          <div style={{ textAlign: "center", paddingTop: 8 }}>
            <span style={{ fontSize: 40, fontWeight: 300, fontFamily: fonts.main, color: "#666666", letterSpacing: 1 }}>
              Not financial advice. Trading involves risk of loss.{" "}
            </span>
            <span style={{ fontSize: 40, fontWeight: 400, fontFamily: fonts.main, color: colors.gold, letterSpacing: 1 }}>
              goldprice.trade
            </span>
          </div>
        </div>
      )}

    </AbsoluteFill>
  );
};
