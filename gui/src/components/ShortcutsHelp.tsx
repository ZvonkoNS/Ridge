// The keyboard shortcuts of the open case, as a modal dialog (Escape or Close returns focus to
// where it was). Shortcuts never act while the examiner is typing in a field.
import { Dialog } from "./Dialog";

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
  return (
    <Dialog title="Keyboard shortcuts" onClose={onClose}>
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
    </Dialog>
  );
}
