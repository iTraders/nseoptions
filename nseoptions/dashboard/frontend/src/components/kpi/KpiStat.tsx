import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface KpiStatProps {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "profit" | "loss" | "call" | "put";
}

const TONES: Record<NonNullable<KpiStatProps["tone"]>, string> = {
  default: "",
  profit: "text-profit",
  loss: "text-loss",
  call: "text-call",
  put: "text-put",
};

/** A compact metric tile used across the dashboard header strip. */
export function KpiStat({ label, value, hint, tone = "default" }: KpiStatProps) {
  return (
    <Card>
      <CardContent className="p-3">
        <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
        <div className={cn("mt-0.5 font-mono text-lg font-semibold leading-tight", TONES[tone])}>
          {value}
        </div>
        {hint ? <div className="text-[11px] text-muted-foreground">{hint}</div> : null}
      </CardContent>
    </Card>
  );
}
