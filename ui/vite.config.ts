import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server sends API calls to the FastAPI workbench (nemotron-challenge ui, port 8790).
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    proxy: { "/api": "http://127.0.0.1:8790", "/site": "http://127.0.0.1:8790" },
  },
  build: { outDir: "dist", sourcemap: false },
});
