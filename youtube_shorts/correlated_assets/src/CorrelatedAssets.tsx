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
  prev_close: number | null;
  change_pct: number | null;
  date:       string | null;
}

interface Props {
  date:   string;
  assets: AssetData[];
}

// ─── Timing ───────────────────────────────────────────────────────────────────
const ROWS_START  = 20;
const ROW_STAGGER = 25;   // frames between card entrances

// ─── Helpers ──────────────────────────────────────────────────────────────────

// Intensity 0-1 based on |change_pct|, capped at CAP_PCT
const CAP_PCT = 5;
const heatIntensity = (pct: number | null): number => {
  if (pct === null) return 0;
  return Math.min(Math.abs(pct) / CAP_PCT, 1);
};

// RGBA color string for the heat overlay
const heatColor = (pct: number | null, intensity: number): string => {
  if (pct === null || pct === 0) return "transparent";
  if (pct > 0) return `rgba(249, 219, 109, ${(intensity * 0.30).toFixed(3)})`;
  return `rgba(239, 83, 80, ${(intensity * 0.38).toFixed(3)})`;
};

// Price formatting per symbol
const formatPrice = (symbol: string, price: number | null): string => {
  if (price === null) return "N/A";
  if (symbol === "GOLD") {
    return "$" + price.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  }
  if (symbol === "SPX") {
    return price.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  }
  if (symbol === "BTC") return "$" + price.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  if (symbol === "SILVER") return "$" + price.toFixed(2);
  if (symbol === "WTI")    return "$" + price.toFixed(2);
  return price.toFixed(2);
};

// ─── Component ────────────────────────────────────────────────────────────────
export const CorrelatedAssets: React.FC<Props> = ({ date, assets }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // GOLD always first; rest sorted by abs(change_pct) desc, nulls last
  const gold = assets.filter((a) => a.symbol === "GOLD");
  const rest = assets
    .filter((a) => a.symbol !== "GOLD")
    .sort((a, b) => {
      if (a.change_pct === null && b.change_pct === null) return 0;
      if (a.change_pct === null) return 1;
      if (b.change_pct === null) return -1;
      return Math.abs(b.change_pct) - Math.abs(a.change_pct);
    });
  const sortedAssets = [...gold, ...rest];

  const headerOpacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });

  const formattedDate = new Date(date + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric", year: "numeric",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg, fontFamily: fonts.main }}>

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div style={{
        position: "absolute",
        top: 60,
        left: 60,
        right: 140,
        opacity: headerOpacity,
      }}>
        <div style={{
          fontSize: 30,
          fontWeight: 400,
          color: colors.textSecondary,
          letterSpacing: 4,
          marginBottom: 6,
        }}>
          XAUUSD  ·  MARKET HEATMAP
        </div>
        <div style={{
          fontSize: 42,
          fontWeight: 800,
          color: colors.gold,
          letterSpacing: 1,
          marginBottom: 14,
          textShadow: `0 0 30px ${colors.goldGlow}`,
        }}>
          Daily Change
        </div>
        {/* Gold divider */}
        <div style={{ height: 2, backgroundColor: colors.gold, opacity: 0.35 }} />
        <div style={{
          fontSize: 28,
          fontWeight: 300,
          color: colors.textDim,
          marginTop: 10,
        }}>
          {formattedDate}
        </div>
      </div>

      {/* ── Asset Cards ─────────────────────────────────────────────────────── */}
      <div style={{
        position: "absolute",
        top: 228,
        left: 44,
        right: 140,
        display: "flex",
        flexDirection: "column",
        gap: 14,
      }}>
        {sortedAssets.map((asset, i) => {
          const cardStart = ROWS_START + i * ROW_STAGGER;
          const s = spring({
            frame: frame - cardStart,
            fps,
            config: { damping: 90, stiffness: 180, mass: 0.8 },
          });
          const slideX = interpolate(s, [0, 1], [120, 0]);
          const opacity = interpolate(s, [0, 1], [0, 1]);

          // Animate color intensity after card enters
          const colorStart = cardStart + 10;
          const animIntensity = interpolate(
            frame,
            [colorStart, colorStart + 30],
            [0, heatIntensity(asset.change_pct)],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );

          const isPos     = (asset.change_pct ?? 0) >= 0;
          const changeCol = asset.change_pct === null ? colors.textDim
            : isPos ? colors.gold : colors.red;
          const isGold    = asset.symbol === "GOLD";
          const isStale   = asset.date !== null && asset.date !== date;

          // Bar fill: shows magnitude (0–100% of card width = 0–CAP_PCT%)
          const barFillPct = Math.min(Math.abs(asset.change_pct ?? 0) / CAP_PCT, 1) * 100;
          const barFillAnim = interpolate(
            frame,
            [colorStart + 10, colorStart + 40],
            [0, barFillPct],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );

          // Calendar flip: prev_close → close
          const FLIP_START = colorStart + 8;
          const FLIP_MID   = FLIP_START + 10;
          const FLIP_END   = FLIP_MID   + 12;
          const oldRotX = interpolate(frame, [FLIP_START, FLIP_MID], [0, -90], {
            extrapolateLeft: "clamp", extrapolateRight: "clamp",
          });
          const newRotX = interpolate(frame, [FLIP_MID, FLIP_END], [90, 0], {
            extrapolateLeft: "clamp", extrapolateRight: "clamp",
          });
          const showNew = frame >= FLIP_MID;

          return (
            <div
              key={asset.symbol}
              style={{
                opacity,
                transform: `translateX(${slideX}px)`,
                position: "relative",
                height: 196,
                borderRadius: 18,
                overflow: "hidden",
                backgroundColor: colors.surface,
                borderLeft: isGold
                  ? `5px solid ${colors.gold}`
                  : `3px solid ${colors.surfaceLight}`,
              }}
            >
              {/* Heat overlay */}
              <div style={{
                position: "absolute",
                inset: 0,
                backgroundColor: heatColor(asset.change_pct, animIntensity),
                borderRadius: 18,
                pointerEvents: "none",
              }} />

              {/* Content — single row: Name · Icon · Price · % */}
              <div style={{
                position: "relative",
                display: "flex",
                flexDirection: "row",
                alignItems: "stretch",
                height: "calc(100% - 6px)",
                padding: "0 24px",
                gap: 16,
              }}>
                {/* Symbol + full name stacked */}
                <div style={{
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "center",
                  alignItems: "flex-start",
                  gap: 4,
                  width: 180,
                  flexShrink: 0,
                }}>
                  <span style={{
                    fontSize: isGold ? 40 : 36,
                    fontWeight: 700,
                    color: isGold ? colors.gold : colors.textSecondary,
                    letterSpacing: 1,
                    whiteSpace: "nowrap",
                    lineHeight: 1,
                  }}>
                    {asset.label}
                  </span>
                  <span style={{
                    fontSize: 32,
                    fontWeight: 400,
                    color: isGold ? colors.gold : colors.textSecondary,
                    whiteSpace: "nowrap",
                    lineHeight: 1,
                  }}>
                    {asset.name}
                  </span>
                </div>

                {/* Icon */}
                <div style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
                  <AssetIcon symbol={asset.symbol} size={88} />
                </div>

                {/* Price — calendar flip prev_close → close */}
                <div style={{
                  flex: 1,
                  position: "relative",
                  perspective: "500px",
                  overflow: "hidden",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}>
                  {/* Spacer keeps container height */}
                  <span style={{
                    visibility: "hidden",
                    fontSize: isGold ? 40 : 36,
                    fontWeight: 800,
                    fontVariantNumeric: "tabular-nums",
                    display: "block",
                    textAlign: "center",
                  }}>
                    {formatPrice(asset.symbol, asset.close)}
                  </span>

                  {/* Old price (prev_close) — folds upward */}
                  {!showNew && asset.prev_close !== null && (
                    <span style={{
                      position: "absolute",
                      inset: 0,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: isGold ? 40 : 36,
                      fontWeight: 800,
                      color: colors.textDim,
                      fontVariantNumeric: "tabular-nums",
                      transform: `rotateX(${oldRotX}deg)`,
                      transformOrigin: "50% 100%",
                    }}>
                      {formatPrice(asset.symbol, asset.prev_close)}
                    </span>
                  )}

                  {/* New price (close) — unfolds downward */}
                  {showNew && (
                    <span style={{
                      position: "absolute",
                      inset: 0,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: isGold ? 40 : 36,
                      fontWeight: 800,
                      color: colors.textSecondary,
                      fontVariantNumeric: "tabular-nums",
                      transform: `rotateX(${newRotX}deg)`,
                      transformOrigin: "50% 0%",
                    }}>
                      {asset.change_pct !== null ? formatPrice(asset.symbol, asset.close) : "N/A"}
                    </span>
                  )}
                </div>

                {/* Percentage — calendar flip 0.00% → actual */}
                {asset.change_pct !== null && (
                  <div style={{
                    position: "relative",
                    perspective: "500px",
                    overflow: "hidden",
                    whiteSpace: "nowrap",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "flex-end",
                  }}>
                    {/* Spacer */}
                    <span style={{
                      visibility: "hidden",
                      fontSize: isGold ? 46 : 40,
                      fontWeight: 900,
                      fontVariantNumeric: "tabular-nums",
                      display: "block",
                    }}>
                      {isPos ? "▲" : "▼"}{Math.abs(asset.change_pct).toFixed(2)}
                      %
                    </span>

                    {/* Old % (0.00) — folds upward */}
                    {!showNew && (
                      <span style={{
                        position: "absolute",
                        inset: 0,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "flex-end",
                        fontSize: isGold ? 46 : 40,
                        fontWeight: 900,
                        color: colors.textDim,
                        fontVariantNumeric: "tabular-nums",
                        transform: `rotateX(${oldRotX}deg)`,
                        transformOrigin: "50% 100%",
                      }}>
                        {isPos ? "▲" : "▼"}0.00
                        %
                      </span>
                    )}

                    {/* New % — unfolds downward */}
                    {showNew && (
                      <span style={{
                        position: "absolute",
                        inset: 0,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "flex-end",
                        fontSize: isGold ? 46 : 40,
                        fontWeight: 900,
                        color: changeCol,
                        fontVariantNumeric: "tabular-nums",
                        transform: `rotateX(${newRotX}deg)`,
                        transformOrigin: "50% 0%",
                      }}>
                        {isPos ? "▲" : "▼"}{Math.abs(asset.change_pct).toFixed(2)}
                        %
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Bottom magnitude bar */}
              <div style={{
                position: "absolute",
                bottom: 0,
                left: 0,
                height: 6,
                width: `${barFillAnim}%`,
                backgroundColor: changeCol,
                opacity: 0.7,
                borderRadius: "0 0 0 18px",
              }} />
            </div>
          );
        })}

        {/* ── Disclaimer ───────────────────────────────────────────────────── */}
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
