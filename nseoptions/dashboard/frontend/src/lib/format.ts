/** Number / currency formatting helpers (Indian locale conventions). */

const INR = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
});

const NUM2 = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

/** Format a rupee value, e.g. 23456.75 -> "₹23,456.75". */
export function inr(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  return INR.format(value);
}

/** Plain number with up to two decimals and Indian grouping. */
export function num(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  return value.toLocaleString("en-IN", { maximumFractionDigits: digits });
}

/** Compact open-interest / volume, e.g. 6742334 -> "67.42L", 1.2e7 -> "1.20Cr". */
export function compact(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  const abs = Math.abs(value);
  if (abs >= 1.0e7) return `${(value / 1.0e7).toFixed(2)}Cr`;
  if (abs >= 1.0e5) return `${(value / 1.0e5).toFixed(2)}L`;
  if (abs >= 1.0e3) return `${(value / 1.0e3).toFixed(1)}K`;
  return NUM2.format(value);
}

/** Signed percentage, e.g. 1.5 -> "+1.50%". */
export function pct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

/** Signed plain number, e.g. -12.3 -> "-12.30". */
export function signed(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}`;
}

/** Format an ISO timestamp as a local HH:MM:SS clock. */
export function clock(iso: string | null | undefined): string {
  if (!iso) return "–";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleTimeString("en-IN", { hour12: false });
}
