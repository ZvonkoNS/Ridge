// Vite builds the two WebView pages: the main window and the passphrase prompt (ADR-010).
// No source maps, no module-preload polyfill (an inline script the CSP would refuse), and
// a target the oldest supported WebView runs: WebView2 (Windows 11), WKWebView (macOS 13+),
// WebKitGTK 2.40+.
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const page = (name: string): string => fileURLToPath(new URL(name, import.meta.url));

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { host: "localhost", port: 1420, strictPort: true },
  build: {
    target: ["es2022", "chrome120", "safari16"],
    modulePreload: { polyfill: false },
    sourcemap: false,
    rolldownOptions: {
      input: { main: page("index.html"), passphrase: page("passphrase.html") },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
    css: false,
  },
});
