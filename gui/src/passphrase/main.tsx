// The passphrase window (ADR-010): its own page, its own capability with three commands, no case
// data. Nothing from the main window is rendered here.
import "@fontsource/atkinson-hyperlegible-next/400.css";
import "@fontsource/atkinson-hyperlegible-next/700.css";
import "../styles/tokens.css";
import "../styles/prompt.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { PassphrasePrompt } from "./PassphrasePrompt";

const root = document.getElementById("prompt");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <PassphrasePrompt />
    </StrictMode>,
  );
}
