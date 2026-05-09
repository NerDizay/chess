import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

/** В Docker (`deploy/docker-compose.dev.yml`) задайте VITE_DEV_PROXY_API=http://api:8000 */
const apiProxyTarget =
  process.env.VITE_DEV_PROXY_API ?? "http://127.0.0.1:8000";

// Сборка в корневой static/ — FastAPI раздаёт /assets и index.html
export default defineConfig({
  plugins: [vue()],
  root: ".",
  build: {
    outDir: "../static",
    emptyOutDir: true,
    assetsDir: "assets",
  },
  base: "/",
  server: {
    host: true,
    port: 5173,
    /** В Docker с bind-mount без polling изменения на хосте часто не доходят до chokidar. */
    watch:
      process.env.VITE_DOCKER === "1"
        ? { usePolling: true, interval: 200 }
        : undefined,
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
