// The open case: the case reference set like a stamped exhibit tag, a rail of sections, and one
// place that decides what a failure means (a locked case returns to the store).
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";

import { Button, Notice } from "../components/ui";
import { IpcError, ipc, isLocked } from "../ipc/commands";
import { revokeAll } from "../ipc/images";
import { useIdle } from "../lib/idle";
import type { CaseInfo, Item, LimitsStatus, SessionInfo } from "../ipc/types";
import { EvidenceSection } from "./EvidenceSection";
import { JobsSection } from "./JobsSection";
import { RecordsSection } from "./RecordsSection";
import { ReferencesSection } from "./ReferencesSection";

type SectionId = "evidence" | "jobs" | "references" | "records";

const SECTIONS: { id: SectionId; label: string; hint: string }[] = [
  { id: "evidence", label: "Evidence", hint: "photos and review" },
  { id: "jobs", label: "Jobs", hint: "signed reports" },
  { id: "references", label: "References", hint: "manual comparison" },
  { id: "records", label: "Records", hint: "verify, hold, log" },
];

interface Props {
  session: SessionInfo;
  storePath: string;
  versions?: string | null;
  onClosed: (message: string | null) => void;
}

export function CaseScreen({ session, storePath, versions = null, onClosed }: Props) {
  const [section, setSection] = useState<SectionId>("evidence");
  const [items, setItems] = useState<Item[]>([]);
  const [info, setInfo] = useState<CaseInfo | null>(null);
  const [limits, setLimits] = useState<LimitsStatus | null>(null);
  const [idleTimeout, setIdleTimeout] = useState(15 * 60);
  const idle = useIdle(idleTimeout);
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  const close = useCallback(
    (text: string | null) => {
      revokeAll(); // no decrypted preview outlives the open case
      onClosed(text);
    },
    [onClosed],
  );

  const onFailure = useCallback(
    (error: unknown) => {
      if (isLocked(error)) {
        close(
          "The case was locked: 15 minutes without activity, or the processing engine restarted. Unlock it again.",
        );
      } else if (error instanceof IpcError && error.kind === "cancelled") {
        setMessage(null);
      } else {
        setMessage({ tone: "error", text: error instanceof Error ? error.message : "Something went wrong." });
      }
    },
    [close],
  );

  const refresh = useCallback(() => {
    ipc.listItems().then(setItems, onFailure);
  }, [onFailure]);

  useEffect(() => {
    refresh();
    ipc.caseInfo().then(setInfo, onFailure);
    ipc.limitsOfUse().then(setLimits, onFailure);
    ipc.sessionStatus().then((status) => {
      setIdleTimeout(status.idle_timeout_s);
    }, onFailure);
  }, [refresh, onFailure]);

  useEffect(() => {
    if (idle.expired) {
      // lock on time, as the engine does, rather than waiting for the next request to fail
      void ipc
        .lockCase()
        .catch(() => undefined)
        .finally(() => {
          close(
            `The case was locked after ${Math.round(idleTimeout / 60)} minutes without activity. Unlock it again.`,
          );
        });
    }
  }, [idle.expired, idleTimeout, close]);

  const notify = (text: string) => {
    setMessage({ tone: "ok", text });
  };

  const lock = async () => {
    try {
      await ipc.lockCase();
    } finally {
      close("Case locked.");
    }
  };

  const hold = info?.legal_hold ?? session.legal_hold;
  return (
    <div className="case">
      <header className="case-head">
        <div className="case-tag" aria-label={`Case ${session.reference}`}>
          <span className="case-tag-eyebrow">Case</span>
          <span className="case-tag-ref">{session.reference}</span>
        </div>
        <dl className="case-facts">
          <dt>Retention until</dt>
          <dd>{info?.retention_until ?? session.retention_until}</dd>
          <dt>Legal hold</dt>
          <dd className={hold ? "on-hold" : undefined}>{hold ? "on hold" : "none"}</dd>
          {info ? (
            <>
              <dt>Legal basis</dt>
              <dd>{info.legal_basis}</dd>
            </>
          ) : null}
          <dt>Store</dt>
          <dd className="path">{storePath}</dd>
        </dl>
        <Button onClick={() => void lock()}>Lock case</Button>
      </header>
      <div className="case-body">
        <nav className="rail" aria-label="Case sections">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`rail-item${section === s.id ? " rail-on" : ""}`}
              aria-current={section === s.id ? "page" : undefined}
              onClick={() => {
                setSection(s.id);
              }}
            >
              <span>{s.label}</span>
              <small>{s.hint}</small>
            </button>
          ))}
          {versions ? <p className="versions">{versions}</p> : null}
          <p className="rail-note">
            Image enhancement only. Ridge does not identify anyone and draws no conclusions.
          </p>
        </nav>
        <main className="case-main" id="main">
          {idle.secondsLeft !== null && !idle.expired ? (
            <div className="notice notice-caution idle-banner" role="alert">
              <div className="notice-body">
                Nothing was done in Ridge for a while: the case locks in{" "}
                <span aria-hidden="true">{idle.secondsLeft} s</span>
                <span className="visually-hidden">about a minute</span>.
              </div>
              <Button
                onClick={() => {
                  ipc.sessionStatus().catch(onFailure);
                }}
              >
                Keep the case open
              </Button>
            </div>
          ) : null}
          <AnimatePresence>
            {message ? (
              <motion.div
                key={message.text}
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                <Notice
                  tone={message.tone}
                  onDismiss={() => {
                    setMessage(null);
                  }}
                >
                  {message.text}
                </Notice>
              </motion.div>
            ) : null}
          </AnimatePresence>
          {section === "evidence" ? (
            <EvidenceSection items={items} onFailure={onFailure} onChanged={refresh} notify={notify} />
          ) : null}
          {section === "jobs" ? (
            <JobsSection items={items} onFailure={onFailure} onChanged={refresh} notify={notify} />
          ) : null}
          {section === "references" ? (
            <ReferencesSection items={items} onFailure={onFailure} onChanged={refresh} notify={notify} />
          ) : null}
          {section === "records" ? (
            <RecordsSection
              info={info}
              items={items}
              limits={limits}
              onInfo={setInfo}
              onFailure={onFailure}
              notify={notify}
            />
          ) : null}
        </main>
      </div>
    </div>
  );
}
