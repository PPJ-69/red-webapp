import { svelte } from "@sveltejs/vite-plugin-svelte";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, ".", "POC_");
  const apiOrigin = environment.POC_API_ORIGIN ?? "http://127.0.0.1:8001";
  return {
    plugins: [svelte()],
    server: {
      proxy: {
        "/api": apiOrigin,
        "/__poc": apiOrigin,
      },
    },
    build: {
      rollupOptions: {
        input: "index.html",
      },
    },
    test: {
      environment: "node",
      include: ["tests/unit/**/*.test.ts"],
    },
  };
});
