// Copy a full value (a SHA-256, a key id) to the clipboard, for the examiner's case notes. The value
// is already shown on screen; nothing is logged, and a failed copy says so instead of pretending.
import { useEffect, useRef, useState } from "react";

export function CopyButton({ value, what }: { value: string; what: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const timer = useRef<number | null>(null);
  useEffect(
    () => () => {
      if (timer.current !== null) {
        window.clearTimeout(timer.current);
      }
    },
    [],
  );

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setState("copied");
    } catch {
      setState("failed");
    }
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
    }
    timer.current = window.setTimeout(() => {
      setState("idle");
    }, 2000);
  };

  return (
    <button type="button" className="copy" aria-label={`Copy ${what}`} onClick={() => void copy()}>
      {state === "copied" ? "Copied" : state === "failed" ? "Copy failed" : "Copy"}
    </button>
  );
}
