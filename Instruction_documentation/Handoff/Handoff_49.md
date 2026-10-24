# Handoff_49.md

Date/time (ISO 8601 with offset): 2026-10-24T19:20+02:00
Author/agent: Claude Code (claude-fable-5-1), on the product owner's instruction to push the stack and open its pull requests
Project: Ridge
Branch: `afis-docs-31` (stack top)
Base commit: `b9c6254` (Handoff_48)
Latest commit: see `git log afis-docs-31`

## 1. Scope

Requested change: push the thirteen `afis-*` branches and open the stacked pull requests bottom-up, each against the branch below it.

Completed work:

- All thirteen branches pushed to `origin` (https://github.com/ZvonkoNS/Ridge) at the commits of Handoff_48's table; pushes trigger no workflow (CI runs on pull requests only).
- Pull requests #33 to #45 opened bottom-up with the repository's body convention (stacked-on line and handoff, What, Merge order, Forensic impact, Checks).
- **Fold at the bottom of the stack.** #33 (`afis-gray-export-19`, the grayscale export) failed the dependency audit job: it is based on `main`, whose `requirements-dev.lock` still pins filelock 4.2.0 and setuptools 84.0.0, the advisories that Handoff_36's lock fix closes one commit higher. #34 (`afis-deps-20`) was therefore retargeted to `main`, so it carries both commits (`d799929` and `fb5261d`) and is green, and #33 was closed in its favour with the reason in a comment. The branch `afis-gray-export-19` stays as it was; the merge-order lines of #35 to #45 now start at #34. Twelve pull requests are open.

Out of scope: merging; retargeting as the stack merges; review threads.

## 2. Current repository state

Git status summary: clean on `afis-docs-31`; every `afis-*` branch pushed.

Pull requests (open, bottom-up): #34 `afis-deps-20` → `main`; #35 `afis-scale-reference-21`; #36 `afis-export-formats-22`; #37 `afis-submission-23`; #38 `afis-sweep-24`; #39 `afis-provenance-25`; #40 `afis-rank-metrics-26`; #41 `afis-method-channel-27`; #42 `afis-method-upright-28`; #43 `afis-method-frequency-29`; #44 `afis-method-rectify-30`; #45 `afis-docs-31`, each against the one before. #33 closed (folded into #34).

## 3. Standards applicability and evidence

Project standards profile updated: no.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Stacked-PR workflow (local gate first; merge bottom-up only on green CI) | Yes | Local gates passed on the stack top before the push (Handoff_48); CI per PR running | #33 could not go green on its own and was folded into #34 |
| Minimal GitHub Actions use | Yes | One `pull_request` run per PR (ci.yml) and one arm64 run where pipeline or export paths changed; no re-runs requested | Twelve PRs opened at once means twelve concurrent runs |

Standards checks or tools run: section 9.

## 4. Forensic impact

None (no code change in this handoff).

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `Instruction_documentation/Handoff/Handoff_49.md` (new) | This handoff |

## 6. Data store, records and formats

None.

## 7. Configuration, keys and CI

CI state at 19:20 (from `gh pr checks`): #34 dependency audit and gates pass; #35 to #44 dependency audit pass, Linux gates pending, arm64 pixel tests pass on #35, #36, #38, #41, #42, #43 and #44 (the branches that change pipeline or export code); #45 has no checks (documents only; ci.yml ignores docs paths).

## 8. Security

No change.

## 9. Tests

Commands run:

```bash
git push -u origin <each afis-* branch>        # thirteen branches
gh pr create --base <branch below> --head <branch> ...   # #33 to #45
gh pr edit 34 --base main; gh pr close 33 --comment ...  # the fold at the bottom
gh pr checks <n>                                        # section 7
```

Tests not run and why: none of the code changed; CI is running on GitHub.

## 10. Release readiness

As Handoff_48; merging is the owner's decision, bottom-up on green CI, retargeting each PR to `main` after the one below merges.

## 11. Open risks and known issues

- The Linux gate jobs were still pending on #35 to #44 when this handoff was written; results arrive on GitHub.
- Retargeting a PR after the one below merges is a manual step per PR (twelve times).

## 12. Recommended next work

Watch the gate jobs; merge #34 first; then retarget and merge upwards. Handoff_48 section 12 lists the decisions outside engineering.

## 13. First thing the next agent/developer should read or do

`gh pr list` for the stack's state, then Handoff_48's section 1 table.
