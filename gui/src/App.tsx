// Top level: the store screen until a case is unlocked, then the case screen. All case state is
// in memory and dropped when the case closes.
import { useCallback, useEffect, useState } from "react";

import { ipc } from "./ipc/commands";
import type { AppInfo, SessionInfo, StoreView } from "./ipc/types";
import { CaseScreen } from "./screens/CaseScreen";
import { StoreScreen } from "./screens/StoreScreen";

/** "Ridge 0.2.0 (GUI 0.2.0)" for the screens' footers, or null until the engine answered. */
export function versionText(info: AppInfo | null): string | null {
  return info ? `Ridge ${info.engine.ridge} (GUI ${info.gui}, ${info.engine.protocol})` : null;
}

export function App() {
  const [store, setStore] = useState<StoreView | null>(null);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [engineProblem, setEngineProblem] = useState<string | null>(null);

  useEffect(() => {
    // The Rust core remembers the last store the examiner chose; without one, the store is chosen
    // in a native dialog. Nothing is unlocked here.
    ipc.refreshStore().then(setStore, () => undefined);
    // Start the processing engine now and check its version, so a problem shows before any work.
    ipc.appInfo().then(setInfo, (error: unknown) => {
      setEngineProblem(error instanceof Error ? error.message : "the processing engine is not available");
    });
  }, []);

  const onClosed = useCallback((message: string | null) => {
    setSession(null);
    setNotice(message);
  }, []);

  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      {session && store ? (
        <CaseScreen
          session={session}
          storePath={store.path}
          versions={versionText(info)}
          onClosed={onClosed}
        />
      ) : (
        <StoreScreen
          store={store}
          notice={notice}
          engineProblem={engineProblem}
          versions={versionText(info)}
          onStore={(next) => {
            setStore(next);
            setNotice(null);
          }}
          onOpened={(opened) => {
            setNotice(null);
            setSession(opened);
          }}
        />
      )}
    </>
  );
}
