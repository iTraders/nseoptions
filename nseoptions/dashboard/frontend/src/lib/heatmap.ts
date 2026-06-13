/**
 * Heat-map colour interpolation.
 *
 * Reproduces the NSE Option Chain Excel template's 3-colour scale exactly:
 *   low (#F8696B, red) -> mid (#FFEB84, yellow) -> high (#63BE7B, green).
 * This is the unit covered by the visual snapshot test.
 */

export const HEAT = {
  low: "#F8696B",
  mid: "#FFEB84",
  high: "#63BE7B",
} as const;

interface RGB {
  r: number;
  g: number;
  b: number;
}

function clamp01(t: number): number {
  return Math.min(1, Math.max(0, t));
}

function hexToRgb(hex: string): RGB {
  const h = hex.replace("#", "");
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  };
}

function channel(value: number): string {
  return Math.round(clamp01(value / 255) * 255)
    .toString(16)
    .padStart(2, "0");
}

function mix(a: RGB, b: RGB, t: number): RGB {
  return {
    r: a.r + (b.r - a.r) * t,
    g: a.g + (b.g - a.g) * t,
    b: a.b + (b.b - a.b) * t,
  };
}

const LOW = hexToRgb(HEAT.low);
const MID = hexToRgb(HEAT.mid);
const HIGH = hexToRgb(HEAT.high);

/** Interpolate `t` in [0,1] across low -> mid -> high; returns "#rrggbb". */
export function heatColor(t: number): string {
  const x = clamp01(t);
  const rgb = x <= 0.5 ? mix(LOW, MID, x / 0.5) : mix(MID, HIGH, (x - 0.5) / 0.5);
  return `#${channel(rgb.r)}${channel(rgb.g)}${channel(rgb.b)}`;
}

/** Normalize a value into [0,1] over [min,max] for sequential scales. */
export function normalize(value: number, min: number, max: number): number {
  if (max <= min) return 0.5;
  return clamp01((value - min) / (max - min));
}

/**
 * Map a signed value into [0,1] symmetric around zero for diverging scales:
 * -bound -> 0 (red), 0 -> 0.5 (yellow), +bound -> 1 (green).
 */
export function diverging(value: number, bound: number): number {
  if (bound <= 0) return 0.5;
  return clamp01(0.5 + value / (2 * bound));
}

/** Choose a legible text colour (near-black / near-white) for a background. */
export function textColorFor(hex: string): string {
  const { r, g, b } = hexToRgb(hex);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.55 ? "#0b0b0c" : "#f8fafc";
}
