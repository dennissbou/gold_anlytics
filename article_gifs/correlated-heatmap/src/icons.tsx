import React from "react";
import { Img, staticFile } from "remotion";

interface IconProps {
  size?: number;
}

export const GoldIcon: React.FC<IconProps> = ({ size = 60 }) => (
  <Img
    src={staticFile("gold_logo.png")}
    width={size}
    height={size}
    style={{ objectFit: "contain" }}
  />
);

export const SilverIcon: React.FC<IconProps> = ({ size = 60 }) => (
  <svg width={size} height={size} viewBox="0 0 60 60" fill="none">
    <circle cx="30" cy="30" r="25" fill="#B0B0BC" />
    <circle cx="30" cy="30" r="19" fill="#D4D4E0" stroke="#9898A8" strokeWidth="1.5" />
    {/* Shine */}
    <ellipse cx="23" cy="23" rx="5" ry="3" fill="white" opacity="0.35" transform="rotate(-30 23 23)" />
    <text x="30" y="35" textAnchor="middle" fontFamily="Arial" fontSize="13"
      fontWeight="bold" fill="#68687A">Ag</text>
  </svg>
);

export const DxyIcon: React.FC<IconProps> = ({ size = 60 }) => (
  <svg width={size} height={size} viewBox="0 0 60 60" fill="none">
    <circle cx="30" cy="30" r="28" fill="#1C3D72" />
    {/* Dollar sign */}
    <text x="30" y="41" textAnchor="middle" fontFamily="Arial" fontSize="32"
      fontWeight="bold" fill="white">$</text>
    {/* vertical line through $ */}
    <line x1="30" y1="9" x2="30" y2="15" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="30" y1="45" x2="30" y2="51" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
  </svg>
);

export const WtiIcon: React.FC<IconProps> = ({ size = 60 }) => (
  <Img
    src={staticFile("wti_logo.jpg")}
    width={size}
    height={size}
    style={{ objectFit: "contain", borderRadius: "50%" }}
  />
);

export const SpxIcon: React.FC<IconProps> = ({ size = 60 }) => (
  <svg width={size} height={size} viewBox="0 0 60 60" fill="none">
    <defs>
      <clipPath id="spx-circle">
        <circle cx="30" cy="30" r="28" />
      </clipPath>
    </defs>
    <circle cx="30" cy="30" r="28" fill="#0d1f0d" />
    <g clipPath="url(#spx-circle)">
      {/* Axes */}
      <line x1="8" y1="52" x2="52" y2="52" stroke="#2a3a2a" strokeWidth="1.5" />
      <line x1="8" y1="8"  x2="8"  y2="52" stroke="#2a3a2a" strokeWidth="1.5" />
      {/* Area fill */}
      <polygon
        points="8,44 18,38 26,40 36,26 46,30 54,14 54,52 8,52"
        fill="#f9db6d" opacity="0.12"
      />
      {/* Line */}
      <polyline
        points="8,44 18,38 26,40 36,26 46,30 54,14"
        fill="none" stroke="#f9db6d" strokeWidth="2.5"
        strokeLinecap="round" strokeLinejoin="round"
      />
    </g>
  </svg>
);

export const BtcIcon: React.FC<IconProps> = ({ size = 60 }) => (
  <svg width={size} height={size} viewBox="0 0 60 60" fill="none">
    <circle cx="30" cy="30" r="28" fill="#F7931A" />
    {/* ₿ symbol */}
    <text x="31" y="42" textAnchor="middle" fontFamily="Arial" fontSize="30"
      fontWeight="bold" fill="white">₿</text>
  </svg>
);

export const VixIcon: React.FC<IconProps> = ({ size = 60 }) => (
  <svg width={size} height={size} viewBox="0 0 60 60" fill="none">
    <defs>
      <clipPath id="vix-circle">
        <circle cx="30" cy="30" r="28" />
      </clipPath>
    </defs>
    <circle cx="30" cy="30" r="28" fill="#1a0a0a" />
    <g clipPath="url(#vix-circle)">
      {/* Axes */}
      <line x1="8" y1="52" x2="52" y2="52" stroke="#3a1a1a" strokeWidth="1.5" />
      <line x1="8" y1="8"  x2="8"  y2="52" stroke="#3a1a1a" strokeWidth="1.5" />
      {/* Volatile zigzag */}
      <polyline
        points="8,36 16,16 24,42 32,20 40,38 48,14 54,28"
        fill="none" stroke="#e65100" strokeWidth="2.5"
        strokeLinecap="round" strokeLinejoin="round"
      />
    </g>
  </svg>
);

// Dispatcher
const ICON_MAP: Record<string, React.FC<IconProps>> = {
  GOLD:  GoldIcon,
  SILVER: SilverIcon,
  DXY:   DxyIcon,
  WTI:   WtiIcon,
  SPX:   SpxIcon,
  BTC:   BtcIcon,
  VIX:   VixIcon,
};

export const AssetIcon: React.FC<{ symbol: string; size?: number }> = ({ symbol, size = 60 }) => {
  const Icon = ICON_MAP[symbol];
  if (!Icon) return null;
  return <Icon size={size} />;
};
