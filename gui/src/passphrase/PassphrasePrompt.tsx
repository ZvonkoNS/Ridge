// The passphrase prompt. The passphrase goes from this window to the Rust core only, which uses
// it with the sidecar and drops it (zeroised). It is kept in a field's state only while typed,
// is never logged or stored, and is cleared after every submission.
import { useEffect, useRef, useState } from "react";

import { IpcError, promptIpc } from "../ipc/commands";
import type { PromptContext } from "../ipc/types";

const ACTION: Record<PromptContext["purpose"], string> = {
  create_identity: "Create identity",
  create_case: "Create and open case",
  unlock: "Unlock",
  verify_store: "Verify all cases",
  store_overview: "Show case details",
};

export function PassphrasePrompt() {
  const [context, setContext] = useState<PromptContext | null>(null);
  const [passphrase, setPassphrase] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const first = useRef<HTMLInputElement>(null);

  useEffect(() => {
    promptIpc.context().then(
      (c) => {
        setContext(c);
      },
      (error: unknown) => {
        setProblem(error instanceof Error ? error.message : "This prompt is not in use.");
      },
    );
  }, []);

  useEffect(() => {
    first.current?.focus();
  }, [context]);

  const tooShort =
    context !== null && passphrase.length > 0 && Array.from(passphrase).length < context.min_chars;
  const mismatch = context?.confirm === true && confirmation.length > 0 && confirmation !== passphrase;

  const submit = async () => {
    if (!context || busy) {
      return;
    }
    setBusy(true);
    setProblem(null);
    try {
      await promptIpc.submit(passphrase, context.confirm ? confirmation : null);
    } catch (error) {
      setProblem(error instanceof IpcError ? error.message : "The passphrase could not be used.");
      setContext(await promptIpc.context().catch(() => context));
    } finally {
      setPassphrase("");
      setConfirmation("");
      setBusy(false);
      first.current?.focus();
    }
  };

  return (
    <main className="prompt">
      <h1>{context?.title ?? "Passphrase"}</h1>
      {context ? <p className="prompt-detail">{context.detail}</p> : null}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <label className="prompt-field">
          <span>{context?.confirm ? "New passphrase" : "Passphrase"}</span>
          <input
            ref={first}
            type="password"
            autoComplete={context?.confirm ? "new-password" : "current-password"}
            spellCheck={false}
            value={passphrase}
            aria-invalid={tooShort || undefined}
            aria-describedby={tooShort ? "prompt-length" : undefined}
            onChange={(e) => {
              setPassphrase(e.target.value);
            }}
          />
        </label>
        {tooShort ? (
          <p id="prompt-length" className="prompt-hint">
            Use at least {context.min_chars} characters. A few unrelated words work well.
          </p>
        ) : null}
        {context?.confirm ? (
          <label className="prompt-field">
            <span>Type it again</span>
            <input
              type="password"
              autoComplete="new-password"
              spellCheck={false}
              value={confirmation}
              aria-invalid={mismatch || undefined}
              onChange={(e) => {
                setConfirmation(e.target.value);
              }}
            />
          </label>
        ) : null}
        {mismatch ? <p className="prompt-hint">The two passphrases are not the same yet.</p> : null}
        {problem ? (
          <p className="prompt-error" role="alert">
            {problem}
            {context && context.attempts_left < 5 ? ` (${context.attempts_left} attempts left)` : ""}
          </p>
        ) : null}
        <div className="prompt-actions">
          <button
            type="button"
            className="btn btn-quiet"
            onClick={() => void promptIpc.cancel()}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!context || busy || passphrase.length === 0 || tooShort || mismatch}
          >
            {busy ? "Checking..." : ACTION[context?.purpose ?? "unlock"]}
          </button>
        </div>
      </form>
      <p className="prompt-note">
        Ridge never stores or shows your passphrase. It cannot be recovered if lost.
      </p>
    </main>
  );
}
