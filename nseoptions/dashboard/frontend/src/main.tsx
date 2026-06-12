import React from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ReactDOM from "react-dom/client";

import App from "@/App";
import { TooltipProvider } from "@/components/ui/tooltip";

import "@/index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, staleTime: 15_000, retry: 1 },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={150}>
        <App />
      </TooltipProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
