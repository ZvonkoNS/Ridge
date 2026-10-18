import "@fontsource/atkinson-hyperlegible-next/400.css";
import "@fontsource/atkinson-hyperlegible-next/700.css";
import "@fontsource/atkinson-hyperlegible-mono/400.css";
import "@fontsource/atkinson-hyperlegible-mono/700.css";
import "./styles/tokens.css";
import "./styles/app.css";

import { MotionConfig } from "motion/react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { installPreview } from "./dev/preview";

// Development preview in a plain browser (synthetic data); compiled out of production builds.
if (import.meta.env.DEV && !("__TAURI_INTERNALS__" in window)) {
  installPreview();
}

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <MotionConfig reducedMotion="user">
        <App />
      </MotionConfig>
    </StrictMode>,
  );
}
