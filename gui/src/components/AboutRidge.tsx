// "About Ridge": what it is and is not, where data lives, and how exported files are checked.
import { Dialog } from "./Dialog";

export function AboutRidge({
  versions,
  storePath,
  onClose,
}: {
  versions: string | null;
  storePath: string;
  onClose: () => void;
}) {
  return (
    <Dialog title="About Ridge" onClose={onClose}>
      <p>{versions ?? "Ridge"}</p>
      <p>
        Ridge enhances photos of fingers into prints for a fingerprint examiner. It does not identify anyone
        or decide whether prints match: comparison and conclusions are the examiner&apos;s.
      </p>
      <h3>Your data</h3>
      <p>
        Cases are encrypted in the case store <span className="path">{storePath}</span>. Originals are never
        changed. Plaintext leaves the store only through exports, and every export, job and note is written to
        the case&apos;s signed custody log.
      </p>
      <h3>Checking exported files</h3>
      <p>
        Reports, processing records, custody heads and packages can be verified without the store: on the
        store screen (&quot;Check exported files&quot;) or with <code>ridge-case check FILE</code>. Readable
        HTML copies are not signed; the signed JSON files are the record.
      </p>
      <p className="muted">Internal engineering build: not for casework.</p>
    </Dialog>
  );
}
