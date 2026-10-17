# Handoff Workflow

Last verified: 2026-10-16
Use whenever substantial work on Ridge is completed, paused, or transferred to another developer or coding agent.

## Purpose

Handoffs preserve continuity, expose unresolved risk and keep traceability across product, engineering, security, forensic, standards, testing and release decisions.

## When a handoff is required

Create the next consecutive handoff when:

- A substantial feature, fix, refactor, dependency upgrade, release or investigation is completed or paused.
- Work touches the pipeline, decoding, output writing, hashing, custody, reports, keys, case store, exports, sidecar, GUI IPC, CI or release signing.
- Output pixels, defaults or golden data change (method change).
- Standards applicability, evidence or exceptions change.
- Gates, tests or scanners could not be run.
- Known risks, blockers or recommended next steps exist.

## File naming

```text
Instruction_documentation/Handoff/Handoff_1.md
Instruction_documentation/Handoff/Handoff_2.md
...
```

- Numbers are consecutive without gaps; `python tools/gate.py docs` checks this.
- Never overwrite or renumber an existing handoff. Copy `Handoff/Handoff_Template.md` for each new one.
- Parallel work: agree who writes the next number before writing it; two handoffs with the same number are a defect to resolve immediately.

## Required handoff content

- Date/time (ISO 8601 with offset), author or agent, branch, base and latest commit.
- Requested change, completed work, out-of-scope items.
- Repository state and git status summary.
- Files changed and purpose.
- Standards considered, evidence produced, exceptions.
- Forensic impact: pixels or defaults changed, golden data changed, revalidation decision, ADR links.
- Data classes touched and how class E data was kept out of the repository and the agent session.
- Case-store, custody or report format changes and migrations (M1+).
- Configuration, environment variables, keys and CI changes.
- Security changes and threat-model notes.
- Tests added, commands run with results, commands not run with reasons.
- Release readiness, blockers, rollback.
- Open risks and recommended next work.
- First thing the next developer or agent should do.

## Content rules

- Specific and factual; exact commands and results.
- Never claim a gate passed unless it ran successfully.
- Never include real images, crops, screenshots of outputs, case identifiers, examiner personal data, secrets or key material.
- Name risks plainly; replace "needs testing" with the specific tests and why.
- Paths are repository-relative.

## Reading handoffs

Before new work:

1. Read the latest handoff.
2. Read older handoffs it references.
3. Read `Project_Standards_Profile.md` exceptions.
4. Check the files and tests mentioned.

Verify the current repository state; an old handoff may be outdated.

## Closing risks

When closing a risk from an earlier handoff: reference the handoff and item, explain the change, list the evidence (tests, gate output), update the profile exception if one existed, and remove stale documentation.
