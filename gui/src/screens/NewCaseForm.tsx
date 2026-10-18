// "New case": the case reference, legal basis and retention date a case cannot be created without
// (PRD FR-20). The Rust core validates them again and opens its own passphrase prompt.
import { useState } from "react";

import { Button } from "../components/ui";

export interface NewCase {
  reference: string;
  legalBasis: string;
  retention: string;
}

export function NewCaseForm({ busy, onCreate }: { busy: boolean; onCreate: (form: NewCase) => void }) {
  const [form, setForm] = useState<NewCase>({ reference: "", legalBasis: "", retention: "" });
  return (
    <section className="card" aria-labelledby="new-title">
      <h2 id="new-title">New case</h2>
      <form
        className="newcase"
        onSubmit={(e) => {
          e.preventDefault();
          onCreate(form);
        }}
      >
        <label className="field">
          <span>Case reference</span>
          <input
            required
            maxLength={200}
            value={form.reference}
            placeholder="KT-2026-0001"
            onChange={(e) => {
              setForm({ ...form, reference: e.target.value });
            }}
          />
        </label>
        <label className="field">
          <span>Legal basis</span>
          <input
            required
            maxLength={500}
            value={form.legalBasis}
            placeholder="Order or article"
            onChange={(e) => {
              setForm({ ...form, legalBasis: e.target.value });
            }}
          />
        </label>
        <label className="field">
          <span>Keep until (retention date)</span>
          <input
            required
            type="date"
            value={form.retention}
            onChange={(e) => {
              setForm({ ...form, retention: e.target.value });
            }}
          />
        </label>
        <Button variant="primary" type="submit" busy={busy}>
          Create case...
        </Button>
      </form>
    </section>
  );
}
