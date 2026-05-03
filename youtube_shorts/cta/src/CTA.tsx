import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const colors = {
  bg:            "#0A0A0A",
  surface:       "#1A1A1A",
  surfaceLight:  "#2A2A2A",
  gold:          "#f9db6d",
  goldGlow:      "rgba(249,219,109,0.4)",
  textSecondary: "#B8B8B8",
  textDim:       "#555555",
  red:           "#EF5350",
} as const;

const fonts = { main: "'Inter','Helvetica Neue',Arial,sans-serif" } as const;

// Button states
const STATES = [
  { label: "TRADE NOW", color: "#0A0A0A", bg: colors.gold,          border: colors.gold,          glow: "rgba(249,219,109,0.5)" },
  { label: "SELL",      color: colors.red,  bg: "rgba(239,83,80,0.12)",  border: colors.red,       glow: "rgba(239,83,80,0.3)"   },
  { label: "BUY",       color: colors.gold, bg: "rgba(249,219,109,0.12)", border: colors.gold,     glow: "rgba(249,219,109,0.3)" },
  { label: "HOLD",      color: colors.textSecondary, bg: "rgba(184,184,184,0.10)", border: colors.textSecondary, glow: "rgba(184,184,184,0.2)" },
] as const;

// Sequence: start and end on TRADE NOW
const SEQUENCE  = [0, 1, 2, 3, 0] as const; // indices into STATES
const CYCLE     = 22;  // frames per state (fast)
const FLIP_DUR  = 6;   // frames for flip
const BTN_START = 20;  // frame when button animation starts

// 6s = 180 frames — exactly one full loop through all 4 states
export const CTA: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // ── Logo + site name ─────────────────────────────────────────────
  const logoSpring = spring({ frame: frame - 10, fps, config: { damping: 80, stiffness: 120, mass: 1 } });
  const logoY  = interpolate(logoSpring, [0, 1], [80, 0]);
  const logoOp = interpolate(logoSpring, [0, 1], [0, 1]);

  const subOp = interpolate(frame, [35, 60], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const lineW = interpolate(frame, [25, 55], [0, 760],  { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  // ── Calendar flip logic (non-looping, ends on TRADE NOW) ────────
  const relFrame    = Math.max(0, frame - BTN_START);
  const rawStep     = relFrame / CYCLE;
  const seqIdx      = Math.min(Math.floor(rawStep), SEQUENCE.length - 1);
  const stateProgress = seqIdx < SEQUENCE.length - 1 ? relFrame % CYCLE : CYCLE; // hold last

  const isFlipping  = stateProgress < FLIP_DUR && seqIdx > 0;
  const flipMid     = FLIP_DUR / 2;
  const prevSeqIdx  = Math.max(0, seqIdx - 1);

  const oldRotX = isFlipping
    ? interpolate(stateProgress, [0, flipMid], [0, -90], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : -90;
  const newRotX = isFlipping
    ? interpolate(stateProgress, [flipMid, FLIP_DUR], [90, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : 0;

  const current = STATES[SEQUENCE[seqIdx]];
  const prev    = STATES[SEQUENCE[prevSeqIdx]];

  // Glow pulse only on final TRADE NOW
  const pulse = Math.sin((frame / 30) * Math.PI) * 0.25 + 0.75;

  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg, fontFamily: fonts.main, alignItems: "center", justifyContent: "center" }}>

      {/* ─── Disclaimer ──────────────────────── */}
      <div style={{ position: "absolute", bottom: 22, left: 0, right: 0, textAlign: "center", zIndex: 10 }}>
        <span style={{ fontSize: 26, fontWeight: 300, fontFamily: fonts.main, color: "#444444", letterSpacing: 1 }}>
          Not financial advice. Trading involves risk of loss.{" "}
        </span>
        <span style={{ fontSize: 26, fontWeight: 300, fontFamily: fonts.main, color: colors.gold, letterSpacing: 1 }}>
          goldprice.trade
        </span>
      </div>

      {/* Radial background glow */}
      <div style={{
        position: "absolute",
        inset: 0,
        background: "radial-gradient(ellipse 700px 700px at 50% 42%, rgba(249,219,109,0.07) 0%, transparent 70%)",
      }} />

      <div style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        opacity: logoOp,
        transform: `translateY(${logoY}px)`,
      }}>

        {/* Logo — bigger */}
        <Img
          src={staticFile("logo.png")}
          width={420}
          height={420}
          style={{ objectFit: "contain", marginBottom: 28 }}
        />

        {/* Domain name — uniform gold color */}
        <div style={{
          fontSize: 72,
          fontWeight: 800,
          color: colors.gold,
          letterSpacing: 2,
          lineHeight: 1,
          textShadow: `0 0 40px ${colors.goldGlow}`,
          textAlign: "center",
        }}>
          GoldPrice.trade
        </div>

        {/* Divider */}
        <div style={{ width: lineW, height: 2, backgroundColor: colors.gold, opacity: 0.35, marginTop: 28, marginBottom: 28 }} />

        {/* Subtitle */}
        <div style={{
          fontSize: 36,
          fontWeight: 300,
          color: colors.textSecondary,
          letterSpacing: 6,
          textTransform: "uppercase",
          opacity: subOp,
          marginBottom: 56,
        }}>
          Choose Your Broker
        </div>

        {/* ── Calendar flip button ────────────────────────────────── */}
        <div style={{
          position: "relative",
          width: 560,
          height: 130,
          perspective: "600px",
          overflow: "hidden",
        }}>
          {/* Spacer */}
          <div style={{ visibility: "hidden", fontSize: 52, fontWeight: 900, padding: "36px 0", textAlign: "center" }}>
            TRADE NOW
          </div>

          {/* Previous state — folds away upward */}
          {isFlipping && (
            <div style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: prev.bg,
              border: `3px solid ${prev.border}`,
              borderRadius: 20,
              boxShadow: `0 0 30px ${prev.glow}`,
              transform: `rotateX(${oldRotX}deg)`,
              transformOrigin: "50% 100%",
            }}>
              <span style={{ fontSize: 52, fontWeight: 900, color: prev.color, letterSpacing: 3 }}>
                {prev.label}
              </span>
            </div>
          )}

          {/* Current state — unfolds downward */}
          <div style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: current.bg,
            border: `3px solid ${current.border}`,
            borderRadius: 20,
            boxShadow: `0 0 ${30 * pulse}px ${current.glow}`,
            transform: `rotateX(${newRotX}deg)`,
            transformOrigin: "50% 0%",
          }}>
            <span style={{ fontSize: 52, fontWeight: 900, color: current.color, letterSpacing: 3 }}>
              {current.label}
            </span>
          </div>
        </div>

      </div>
    </AbsoluteFill>
  );
};
