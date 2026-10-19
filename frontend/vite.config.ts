import { svelte } from "@sveltejs/vite-plugin-svelte";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

function browserSecurityHeaders(
  connectSources: string,
  allowDevelopmentEval = false,
): Record<string, string> {
  const scriptSource = allowDevelopmentEval
    ? "script-src 'self' 'unsafe-eval'"
    : "script-src 'self'";
  return {
    "Content-Security-Policy": [
      "default-src 'self'",
      "base-uri 'self'",
      "object-src 'none'",
      "frame-ancestors 'none'",
      "form-action 'self'",
      scriptSource,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' https: data:",
      "media-src 'self' https:",
      `connect-src 'self' ${connectSources}`.trim(),
    ].join("; "),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Permissions-Policy":
      "accelerometer=(), camera=(), display-capture=(), fullscreen=(self), geolocation=(), microphone=()",
  };
}

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, ".", "POC_");
  const corsEnvironment = loadEnv(mode, ".", "CORS_");
  const apiOrigin = environment.POC_API_ORIGIN ?? "http://127.0.0.1:8001";
  const allowedOrigins = (corsEnvironment.CORS_ALLOWED_ORIGINS ?? "")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean)
    .map((origin) => {
      const parsed = new URL(origin);
      if (
        !["http:", "https:"].includes(parsed.protocol) ||
        parsed.username ||
        parsed.password ||
        parsed.pathname !== "/" ||
        parsed.search ||
        parsed.hash ||
        origin.includes("*")
      ) {
        throw new Error("CORS_ALLOWED_ORIGINS must contain explicit HTTP(S) origins.");
      }
      return parsed.origin;
    });
  const devConnectSources = [
    ...allowedOrigins,
    ...(mode === "development"
      ? ["ws://127.0.0.1:*", "ws://localhost:*"]
      : []),
  ].join(" ");
  return {
    plugins: [svelte()],
    server: {
      headers: browserSecurityHeaders(
        devConnectSources,
        mode === "development",
      ),
      proxy: {
        "/api": apiOrigin,
        "/__poc": apiOrigin,
      },
    },
    preview: {
      headers: browserSecurityHeaders(""),
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
