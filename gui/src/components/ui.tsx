// Small shared controls: buttons with a press micro-interaction, status notices, and the staggered
// fade-and-rise used for lists. Motion respects prefers-reduced-motion through <MotionConfig
// reducedMotion="user"> in main.tsx; nothing here ever animates evidence pixels.
import { motion, type HTMLMotionProps } from "motion/react";
import type { ReactNode } from "react";

type Variant = "primary" | "quiet" | "danger";

interface ButtonProps extends Omit<HTMLMotionProps<"button">, "children"> {
  variant?: Variant;
  busy?: boolean;
  children: ReactNode;
}

export function Button({
  variant = "quiet",
  busy = false,
  disabled,
  children,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <motion.button
      {...rest}
      type={type}
      className={`btn btn-${variant}`}
      disabled={disabled === true || busy}
      aria-busy={busy || undefined}
      whileHover={{ y: -1 }}
      whileTap={{ scale: 0.97 }}
      transition={{ type: "spring", stiffness: 600, damping: 32 }}
    >
      {children}
      {busy ? <span className="btn-busy" aria-hidden="true" /> : null}
    </motion.button>
  );
}

export type Tone = "info" | "ok" | "error" | "caution";

interface NoticeProps {
  tone: Tone;
  children: ReactNode;
  onDismiss?: () => void;
}

/** Errors are announced assertively, everything else politely. */
export function Notice({ tone, children, onDismiss }: NoticeProps) {
  return (
    <div className={`notice notice-${tone}`} role={tone === "error" ? "alert" : "status"}>
      <div className="notice-body">{children}</div>
      {onDismiss ? (
        <button type="button" className="notice-close" onClick={onDismiss} aria-label="Dismiss">
          ×
        </button>
      ) : null}
    </div>
  );
}

const list = { hidden: {}, shown: { transition: { staggerChildren: 0.035 } } };
const row = { hidden: { opacity: 0, y: 6 }, shown: { opacity: 1, y: 0, transition: { duration: 0.18 } } };

export function StaggerList({
  children,
  className,
  label,
}: {
  children: ReactNode;
  className?: string;
  label: string;
}) {
  return (
    <motion.ul className={className} aria-label={label} variants={list} initial="hidden" animate="shown">
      {children}
    </motion.ul>
  );
}

export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.li className={className} variants={row}>
      {children}
    </motion.li>
  );
}

/** A short SHA-256 prefix with the full value available to assistive technology and on hover. */
export function Hash({ value, length = 12 }: { value: string; length?: number }) {
  return (
    <span className="hash" title={value}>
      {value.slice(0, length)}
      <span className="visually-hidden">{value.slice(length)}</span>
    </span>
  );
}

/** ISO 8601 UTC timestamps shown as "2026-10-17 12:05 UTC" (records stay in UTC, never local time). */
export function utc(value: string | null): string {
  if (!value) {
    return "-";
  }
  return `${value.slice(0, 10)} ${value.slice(11, 16)} UTC`;
}
