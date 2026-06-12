import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface PCRGaugeProps {
  pcr: number;
}

const MIN = 0;
const MAX = 2;

function point(cx: number, cy: number, r: number, deg: number) {
  const rad = (deg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

// Arc on the upper semicircle (SVG y-down): 180deg = left, 270 = top, 360 = right.
function arc(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const start = point(cx, cy, r, endDeg);
  const end = point(cx, cy, r, startDeg);
  return `M ${start.x} ${start.y} A ${r} ${r} 0 0 0 ${end.x} ${end.y}`;
}

/** Semicircular Put-Call-Ratio gauge with bearish / neutral / bullish bands. */
export function PCRGauge({ pcr }: PCRGaugeProps) {
  const cx = 100;
  const cy = 100;
  const r = 78;

  const t = Math.max(0, Math.min(1, (pcr - MIN) / (MAX - MIN)));
  const needle = point(cx, cy, r - 8, 180 + t * 180);

  const bias = pcr >= 1.3 ? "Bullish" : pcr <= 0.7 ? "Bearish" : "Neutral";
  const biasColor = pcr >= 1.3 ? "text-profit" : pcr <= 0.7 ? "text-loss" : "text-atm";

  return (
    <Card>
      <CardHeader className="pb-0">
        <CardTitle>Put / Call Ratio</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col items-center pt-2">
        <svg viewBox="0 0 200 116" className="w-full max-w-[240px]">
          {/* bearish 0 - 0.7 */}
          <path d={arc(cx, cy, r, 180, 180 + 0.35 * 180)} stroke="hsl(var(--loss))" strokeWidth={14} fill="none" strokeLinecap="round" opacity={0.85} />
          {/* neutral 0.7 - 1.3 */}
          <path d={arc(cx, cy, r, 180 + 0.35 * 180, 180 + 0.65 * 180)} stroke="hsl(var(--atm))" strokeWidth={14} fill="none" opacity={0.85} />
          {/* bullish 1.3 - 2 */}
          <path d={arc(cx, cy, r, 180 + 0.65 * 180, 360)} stroke="hsl(var(--profit))" strokeWidth={14} fill="none" strokeLinecap="round" opacity={0.85} />
          {/* needle */}
          <line x1={cx} y1={cy} x2={needle.x} y2={needle.y} stroke="hsl(var(--foreground))" strokeWidth={2.5} strokeLinecap="round" />
          <circle cx={cx} cy={cy} r={4} fill="hsl(var(--foreground))" />
        </svg>
        <div className="-mt-4 text-center">
          <div className="font-mono text-2xl font-semibold">{pcr.toFixed(2)}</div>
          <div className={`text-xs font-medium ${biasColor}`}>{bias}</div>
        </div>
      </CardContent>
    </Card>
  );
}
