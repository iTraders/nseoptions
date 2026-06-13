import { SuggestionCard } from "@/components/suggestions/SuggestionCard";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSuggestions } from "@/hooks/useSuggestions";

type ContextValue = string | number | null;

function ContextBar({ context }: { context: Record<string, ContextValue> }) {
  const items: [string, ContextValue][] = [
    ["Bias", context.bias ?? null],
    ["PCR", context.pcr ?? null],
    ["IV regime", context.iv_regime ?? null],
    ["DTE", context.dte ?? null],
    ["Max pain", context.max_pain ?? null],
  ];

  return (
    <div className="flex flex-wrap gap-2">
      {items.map(([label, value]) =>
        value !== null && value !== undefined ? (
          <Badge key={label} variant="secondary" className="gap-1 font-normal">
            <span className="text-muted-foreground">{label}</span>
            <span className="font-mono">{String(value)}</span>
          </Badge>
        ) : null,
      )}
    </div>
  );
}

/** Feature IV: rules-based strategy suggestions for the current scenario. */
export function SuggestionsPanel({ expiry }: { expiry?: string }) {
  const { data, isLoading } = useSuggestions(expiry);

  if (isLoading || !data) {
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <Skeleton key={index} className="h-56" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <ContextBar context={data.context} />
      {data.suggestions.length === 0 ? (
        <Card>
          <CardContent className="flex h-40 items-center justify-center text-sm text-muted-foreground">
            No suggestions for the current scenario.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.suggestions.map((suggestion, index) => (
            <SuggestionCard key={`${suggestion.name}-${index}`} suggestion={suggestion} />
          ))}
        </div>
      )}
    </div>
  );
}
