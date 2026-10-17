@AGENTS.md

## Ridge reminders for Claude Code

- Finger photos and extracted prints are forensic evidence and special-category biometric data. Never ask for, open, attach or generate code from real images; use synthetic data only.
- Never commit images or other biometric data; do not weaken `.gitignore`.
- Ridge is an enhancement aid: never write code, text or messages that claim identification, matching, validation or certification.
- Originals are read-only, outputs are never overwritten silently, decoding is bounded and allow-listed, every input and output is hashed (`Instruction_documentation/forensic_evidence_and_biometric_data_standards.md`).
- Same input, version, parameters, OS and CPU architecture must give identical output; results differ between x86-64 and arm64 by design (per-architecture goldens). Never update `tests/golden/` to make tests pass.
- Before proposing a merge, run `python tools/gate.py all` and report the exact result; list anything not run and why.
- End substantial work with the next consecutive handoff in `Instruction_documentation/Handoff/` (no gaps, never overwrite).
- Do not commit, push or release unless the user asks.
