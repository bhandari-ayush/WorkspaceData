# TOKEN-EFFICIENT-DEBUG-REVAMP-2026-07-29
Setup: Local workspace revamp for low-request, high-accuracy Self-Service/Epsilon debugging.
Scope: Workspace rule + selected-repo safe pull + debugging sheet + Jira/Glean/Sourcegraph pattern synthesis.

VERDICT: A practical low-token workflow is feasible now: enforce truth/accuracy behavior globally, standardize first-hop logs/IDs, and use a fixed triage matrix before deep dives. Confidence: medium-high.

EVIDENCE:
- Workspace rule added: `.cursor/rules/truth-accuracy-and-budget-guard.mdc`.
- Repo pull run summary from terminal capture: clean default branches updated; dirty/non-default repos skipped safely.
- Glean references surfaced for command/log workflow (Calm Troubleshooting, End-to-End log guide, ecli/Ergon primer, Self-Service deployment troubleshooting guide).
- Sourcegraph cross-check confirmed `ergon_task_id`, inargs/outargs structures, and durga state-transition points in `calm`, `epsilon`, and `calm-epsilon-shared`.
- Jira one-year mining (ENG project with NCM2.0/NCM2.1/Iris/Janus terms) shows repeated patterns in upgrade/migration, RBAC visibility, task-state drift, and dependency/service availability.

ARTIFACTS:
- `analysis.md`
- `debugging-sheet.md`
- `repo-update-report.md`

STATE:
- done=rule creation, safe repo update execution, first-pass pattern collection.
- pending=none (ready for 1-2 day trial monitoring loop from debugging sheet).
- open-q=none blocking; deeper product-specific tuning can be added after first trial data.
