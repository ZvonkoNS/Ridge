// The case locks after a period without requests to the processing engine (the sidecar's idle
// timeout, 15 minutes by default). The GUI mirrors that clock from its own IPC calls, warns a minute
// before, and locks itself on time, so an unattended workstation never shows a decrypted case
// longer than the engine keeps it open. Only IPC calls count: looking at an image does not keep the
// case open, exactly as in the engine.
import { useEffect, useState } from "react";

type Listener = () => void;

let lastCall = Date.now();
const listeners = new Set<Listener>();

/** Record engine activity (called by the IPC layer after every command). */
export function noteActivity(now: number = Date.now()): void {
  lastCall = now;
  for (const listener of listeners) {
    listener();
  }
}

export function lastActivity(): number {
  return lastCall;
}

export interface IdleState {
  /** Seconds until the case locks; null while far away. */
  secondsLeft: number | null;
  expired: boolean;
}

/** Seconds left before the idle lock, given the timeout and the warning lead time. */
export function idleState(now: number, last: number, timeoutS: number, warnS: number): IdleState {
  const left = Math.ceil(timeoutS - (now - last) / 1000);
  if (left <= 0) {
    return { secondsLeft: 0, expired: true };
  }
  return { secondsLeft: left <= warnS ? left : null, expired: false };
}

/** Tick once a second while a case is open; re-render when activity is recorded. */
export function useIdle(timeoutS: number, warnS = 60): IdleState {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const tick = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);
    const listener = () => {
      setNow(Date.now());
    };
    listeners.add(listener);
    return () => {
      window.clearInterval(tick);
      listeners.delete(listener);
    };
  }, []);
  return idleState(now, lastCall, timeoutS, warnS);
}
