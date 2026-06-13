import { Button } from "@/components/ui/button";
import { useSymbols } from "@/hooks/useSymbols";
import { useDashboardStore } from "@/store/dashboard";

/**
 * Multi-select toggle row of downloadable symbols.
 *
 * Highlights the symbols currently selected for the next "Fetch Data".
 * An empty selection means "all symbols" (the backend default).
 */
export function SymbolSelector() {
  const { data } = useSymbols();
  const { selectedSymbols, toggleSymbol } = useDashboardStore();

  const symbols = data?.symbols ?? [];
  if (symbols.length === 0) return null;

  return (
    <div className="flex items-center gap-1">
      {symbols.map(({ symbol }) => {
        const active = selectedSymbols.includes(symbol);
        return (
          <Button
            key={symbol}
            size="sm"
            variant={active ? "default" : "outline"}
            className="h-8 px-2 font-mono text-xs"
            aria-pressed={active}
            onClick={() => toggleSymbol(symbol)}
          >
            {symbol}
          </Button>
        );
      })}
    </div>
  );
}
