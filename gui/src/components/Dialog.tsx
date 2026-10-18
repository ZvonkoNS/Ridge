// A modal dialog with one Close button: focus moves to Close, Tab stays inside, Escape or Close
// returns focus to where it was. Used for the shortcut list and "About Ridge".
import { motion } from "motion/react";
import { type ReactNode, useEffect, useId, useRef } from "react";

import { Button } from "./ui";

export function Dialog({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const close = () => panel.current?.querySelector<HTMLButtonElement>("[data-dialog-close]");
    close()?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      } else if (event.key === "Tab") {
        event.preventDefault(); // the Close button is the dialog's only control: keep focus inside
        close()?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      opener?.focus();
    };
  }, [onClose]);

  return (
    <div className="modal-backdrop">
      <motion.div
        ref={panel}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h2 id={titleId}>{title}</h2>
        {children}
        <Button variant="primary" data-dialog-close onClick={onClose}>
          Close
        </Button>
      </motion.div>
    </div>
  );
}
