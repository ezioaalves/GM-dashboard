import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": process.env.KAIHOU_DASHBOARD_API || "https://gm.ezioalves.cloud",
    },
  },
});
