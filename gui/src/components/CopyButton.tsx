// Copy a full value (a SHA-256, a key id) to the clipboard, for the examiner's case notes. The value
// is already shown on screen; nothing is logged, and a failed copy says so instead of pretending.
// The result is also announced in a status region: the button's label names what it copies, so
// its changing text alone would not reach a screen reader.
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
    <>
      <button type="button" className="copy" aria-label={`Copy ${what}`} onClick={() => void copy()}>
        {state === "copied" ? "Copied" : state === "failed" ? "Copy failed" : "Copy"}
      </button>
      <span className="visually-hidden" role="status">
        {state === "copied" ? `${what} copied` : state === "failed" ? `Copying the ${what} failed` : ""}
      </span>
    </>
  );
}
