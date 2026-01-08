import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiTarget = process.env.VITE_API_PROXY ?? "http://localhost:8002";

export default defineConfig({
  plugins: [react()],
  server: { port: 5175, proxy: { "/api": apiTarget } },
});
