import { Download, Loader2, Square } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useFetchControl } from "@/hooks/useFetchControl";
import { useDashboardStore } from "@/store/dashboard";

/**
 * Start/stop the asynchronous downloader for the selected symbols.
 *
 * Idle: a "Fetch Data" button that starts the downloader (an empty
 * selection asks the backend for its default universe). Running: a "Stop"
 * button plus a live badge of how many workers are healthy.
 */
export function FetchDataButton() {
  const { selectedSymbols } = useDashboardStore();
  const { status, start, stop } = useFetchControl();

  const running = status.data?.running ?? false;
  const workers = status.data?.workers ?? [];
  const live = workers.filter((worker) => worker.state === "ok").length;
  const errors = workers.filter((worker) => worker.state === "error").length;
  const busy = start.isPending || stop.isPending;

  return (
    <div className="flex items-center gap-2">
      {running ? (
        <Badge variant="secondary" className="font-mono text-xs">
          {live}/{workers.length} live{errors > 0 ? ` · ${errors} err` : ""}
        </Badge>
      ) : null}

      {running ? (
        <Button
          size="sm"
          variant="destructive"
          className="h-8"
          disabled={busy}
          onClick={() => stop.mutate()}
        >
          {busy ? (
            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
          ) : (
            <Square className="mr-1 h-3.5 w-3.5" />
          )}
          Stop
        </Button>
      ) : (
        <Button
          size="sm"
          className="h-8"
          disabled={busy}
          onClick={() => start.mutate(selectedSymbols)}
        >
          {busy ? (
            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
          ) : (
            <Download className="mr-1 h-3.5 w-3.5" />
          )}
          Fetch Data
        </Button>
      )}
    </div>
  );
}
