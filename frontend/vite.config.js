import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

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
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
