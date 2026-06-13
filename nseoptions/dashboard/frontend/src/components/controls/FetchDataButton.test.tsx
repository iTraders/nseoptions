import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import type { FetchStatus } from "@/types/contract";

import { FetchDataButton } from "./FetchDataButton";

vi.mock("@/lib/api", () => ({
  api: {
    fetchStatus: vi.fn(),
    fetchStart: vi.fn(),
    fetchStop: vi.fn(),
  },
}));

import { api } from "@/lib/api";

function renderWithClient(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("FetchDataButton", () => {
  it("shows the Fetch Data action when the downloader is idle", async () => {
    vi.mocked(api.fetchStatus).mockResolvedValue({
      running: false,
      symbols: [],
      started_at: null,
      workers: [],
    } satisfies FetchStatus);

    renderWithClient(<FetchDataButton />);

    expect(await screen.findByRole("button", { name: /fetch data/i })).toBeInTheDocument();
  });

  it("shows Stop and a live worker badge when the downloader is running", async () => {
    vi.mocked(api.fetchStatus).mockResolvedValue({
      running: true,
      symbols: ["NIFTY"],
      started_at: "2026-06-13T09:15:00",
      workers: [
        {
          symbol: "NIFTY",
          expiry: "26-Jun-2025",
          state: "ok",
          snapshots: 1,
          last_timestamp: "13-Jun-2026 09:15:00",
          detail: null,
        },
      ],
    } satisfies FetchStatus);

    renderWithClient(<FetchDataButton />);

    expect(await screen.findByRole("button", { name: /stop/i })).toBeInTheDocument();
    expect(screen.getByText(/1\/1 live/)).toBeInTheDocument();
  });
});
