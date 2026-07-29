# Token-Efficient Debug Revamp Analysis

## Objective
Build a low-request, high-signal debugging workflow for Self-Service/Epsilon investigations, backed by:
- one-year Jira trend sampling (NCM2.0/NCM2.1/Iris/Janus terms),
- Glean troubleshooting references,
- Sourcegraph code-level confirmation.

## Evidence Inputs

### 1) Jira sampling (last year, ENG project, targeted terms)
Key recurring tickets observed in sampled results:
- `ENG-961844` (NCM2.1 RBAC visibility issue post-upgrade)
- `ENG-960398` (task failed with internal timeout)
- `ENG-946479` (project delete fails due to service resolution)
- `ENG-948127` / `ENG-948295` / `ENG-949136` (post-Janus->NCM2.1 migration breakages)
- `ENG-924418` (IDF crashloop due to missing ZK node post-upgrade)
- `ENG-935577` (coupled upgrade failure)
- `ENG-927344` (missing records after 2.0->2.1 upgrade)

Observed dominant categories:
1. Upgrade/migration regressions (2.0->2.1, Janus migration).
2. Task orchestration/state handling failures (stuck/running/timeout/missing task sync).
3. RBAC and visibility mismatches post-migration.
4. Dependency/service reachability failures across components.
5. Macro/payload parsing or schema mismatch edge cases.

### 2) Glean references (operational guidance)
Frequently surfaced operational docs:
- Calm Troubleshooting
- How to Find relevant End-to-End logs
- Guidelines for debugging epsilon-LEAP issues
- NCM MPI common flows and debugging guide
- Ergon/ecli primers
- Self-Service deployment workflow troubleshooting guide

These references converge on the same triage sequence:
`request id` -> `runlog/task id` -> `engine TRL` -> `child TRLs` -> `leaf error` -> `service log`.

### 3) Sourcegraph confirmation (code-level)
Cross-repo confirmations:
- `calm-epsilon-shared`: response packet includes `ergon_task_id`.
- `epsilon` Durga context middleware extracts `ergon_task_id` from request query.
- `epsilon` zaffi/durga models explicitly represent `in_args` and `out_args`.
- `epsilon` routing milestone store marks Ergon state transitions controlled by Durga for RUNNING/SUCCESS/FAILURE/ABORTED semantics.
- `calm` GoIris set-status paths show behavior when `ergon_task_id` is absent or not found (skips update path with warnings).

## Pattern Matrix (what to check first)

| Symptom | First service/log to check | Fast discriminator |
|---|---|---|
| App launch stuck / action stuck | `nucalm/hercules.log`, `nucalm/jove.log`, `epsilon/durga.log` | Missing progression from parent TRL to child TRLs |
| Task RUNNING forever | `ecli task.get`, `epsilon/jove.log`, `epsilon/narad.log` | No milestone transition updates to Ergon |
| Upgrade/migration broke entities | `nucalm/iris.log`, `epsilon/indra.log`, platform sync logs | missing/invalid mappings, post-migration references |
| RBAC visibility mismatch | API gateway logs + domain/project logs | successful backend fetch but filtered projection |
| Macro-driven payload failures | `epsilon/durga.log`, macro evaluator logs | unresolved macro string passed where object expected |
| Internal errors/timeouts | leaf task logs (`indra`, `arjun`, `karan`) | repeated retries, dependency endpoint failure |

## Recommended Triage Policy
1. Always capture IDs first (`rr`, `task_uuid`, `ergon_task_id`, `engine_trl_uuid`).
2. Never broad-scan logs initially; grep by `rr` or task UUID.
3. Walk parent->children task graph and stop at first failing leaf.
4. Correlate one control-plane log source + one execution-plane source before concluding.
5. Log exact commands and exact outputs into case notes for reproducibility.

## Confidence and Limits
- Confidence: medium-high for the workflow and categories.
- Limits: Jira query scope includes noise from non-Self-Service components because global labels overlap Janus/Iris context; use the sheet's component-first filters during real triage.
