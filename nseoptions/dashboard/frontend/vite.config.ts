import path from "path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The dev server proxies `/api` + `/ws` to the FastAPI backend so the app
// uses identical, origin-relative paths in development and production.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        // Split only the heavy chart stack into its own cacheable chunk.
        // React MUST stay with its consumers (radix, etc.) in one chunk,
        // otherwise a cross-chunk load-order race breaks React.forwardRef.
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (/recharts|\/d3-|d3-[a-z]|react-smooth|victory-vroom|internmap/.test(id)) {
            return "charts";
          }
          return "vendor";
        },
      },
    },
  },
});
