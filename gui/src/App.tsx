// Top level: the store screen until a case is unlocked, then the case screen. All case state is
// in memory and dropped when the case closes.
import { useCallback, useEffect, useState } from "react";

import { ipc } from "./ipc/commands";
import type { SessionInfo, StoreView } from "./ipc/types";
import { CaseScreen } from "./screens/CaseScreen";
import { StoreScreen } from "./screens/StoreScreen";

export function App() {
  const [store, setStore] = useState<StoreView | null>(null);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    // The Rust core remembers the last store the examiner chose; without one, the store is chosen
    // in a native dialog. Nothing is unlocked here.
    ipc.refreshStore().then(setStore, () => undefined);
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
        <CaseScreen session={session} storePath={store.path} onClosed={onClosed} />
      ) : (
        <StoreScreen
          store={store}
          notice={notice}
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
