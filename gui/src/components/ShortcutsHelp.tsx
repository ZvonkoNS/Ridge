// The keyboard shortcuts of the open case, as a modal dialog (Escape or Close returns focus to
// where it was). Shortcuts never act while the examiner is typing in a field.
import { motion } from "motion/react";
import { useEffect, useId, useRef } from "react";

import { Button } from "./ui";

const GROUPS: { title: string; keys: [string[], string][] }[] = [
  {
    title: "Anywhere in a case",
    keys: [
      [["?"], "Show this list"],
      [["Alt", "1"], "Evidence"],
      [["Alt", "2"], "Jobs"],
      [["Alt", "3"], "References"],
      [["Alt", "4"], "Records"],
    ],
  },
  {
    title: "In an image viewer (click it or move to it with Tab first)",
    keys: [
      [["+"], "Zoom in"],
      [["-"], "Zoom out"],
      [["0"], "Fit the image"],
      [["1"], "Actual pixels (100 %)"],
      [["Arrow keys"], "Move the image"],
      [["Shift", "Arrow keys"], "Move the image faster"],
    ],
  },
];

/** True when a key press belongs to a text field, a list box or an editable element. */
export function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
  );
}

export function ShortcutsHelp({ onClose }: { onClose: () => void }) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const close = () => panel.current?.querySelector<HTMLButtonElement>("button");
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
        <h2 id={titleId}>Keyboard shortcuts</h2>
        {GROUPS.map((group) => (
          <table key={group.title} className="shortcuts">
            <caption>{group.title}</caption>
            <tbody>
              {group.keys.map(([keys, action]) => (
                <tr key={action}>
                  <th scope="row">
                    {keys.map((k, i) => (
                      <span key={k}>
                        {i > 0 ? " + " : ""}
                        <kbd>{k}</kbd>
                      </span>
                    ))}
                  </th>
                  <td>{action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}
        <Button variant="primary" onClick={onClose}>
          Close
        </Button>
      </motion.div>
    </div>
  );
}
