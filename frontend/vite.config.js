import { fileURLToPath, URL } from "node:url";

import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

function parseAllowedHosts(rawValue) {
  return String(rawValue || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const allowedHosts = parseAllowedHosts(
    env.VITE_ALLOWED_HOSTS || "localhost,127.0.0.1,44266ed6.r17.cpolar.top,.cpolar.top",
  );
  const proxyTarget = (env.VITE_PROXY_TARGET || "http://127.0.0.1:8520").trim();

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            vue: ["vue", "vue-router"],
            element: ["element-plus", "@element-plus/icons-vue"],
          },
        },
      },
    },
    server: {
      host: "0.0.0.0",
      port: 5173,
      strictPort: true,
      allowedHosts,
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
        },
      },
    },
    preview: {
      host: "0.0.0.0",
      port: 5173,
      strictPort: true,
      allowedHosts,
    },
  };
});
