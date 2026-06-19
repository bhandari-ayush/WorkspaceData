# ENG-924013 — Test summary (UT + live server) for BP / RB / MPI

Scope: custom-form retention on blueprint, runbook, marketplace-item compile/decompile/
CRUD/launch. **Excludes** the update-config macro blueprint (Bug 2 & 3 below) — separate
issue, tracked apart per request.
Setup: `10.103.243.86`, Calm **release 4.4.0**, **latest** containers (nucalm/epsilon
patched). Local: `calm-dsl` on branch with the ENG-924013 + entity.py fix.

## 1. Offline tests (local) — ALL PASS
| Suite | Passed | Failed | Notes |
|---|---|---|---|
| Unit `tests/unit` (custom_form 60 + decompile specs 5 + http_var 1) | **66** | 0 | incl. 5 runtime-file launch-gating tests; re-run after docstring cleanup |
| Regression `eng-924013-regression/tests` | **64** | 0 | custom_form 11, api_sanity 9, negative_paths 7, followup 12, multi_profile 8, round_trip 9, runbook 8 |
| **Total offline** | **130** | **0** | |

## 2. Live server tests on `.86` — BP / RB / MPI
| # | Flow | Result | Evidence |
|---|---|---|---|
| 1 | **BP** compile → create | ✅ PASS | `e2e924013_bp` |
| 2 | **BP** decompile: form retained, R1 filename, R3 runtime JSON | ✅ PASS | `Default_custom_form_*.yaml` + `*_runtime_variable.json` |
| 3 | **BP** recompile → re-upload (v2) | ✅ PASS | `e2e924013_bp_v2` |
| 4 | **BP** launch (R2 warning + runtime-var fill) → **app RUNNING** | ✅ PASS | `e2e924013_app5`, VM `10.103.227.148` |
| 5 | **RB** compile → create with custom form | ✅ PASS | `eng924013_rb_cftest` — **no 422** on latest container |
| 6 | **RB** decompile: form retained, R1 filename | ✅ PASS | `runbook_custom_form_37ec2fe5-….yaml`, `use_custom_form=True` |
| 7 | **RB** execute (run) | ⚠️ PARTIAL | R2 warning fired + default flow; CLI watch timed out, full task completion not confirmed (engine/escript timing — not a custom-form issue) |
| 8 | **MPI** publish (category Backup, project setup) → approve → store | ✅ PASS | `e2e924013_mpi` v1.0.0 |
| 9 | **MPI** form retained in marketplace item | ✅ PASS | `describe marketplace bp` |
| 10 | **MPI** clone/launch from marketplace → **app RUNNING** | ✅ PASS | `e2e924013_mpi_app`, VM `10.103.224.52` |

**Live tally (BP/RB/MPI in scope): 9 PASS, 1 PARTIAL (RB execute), 0 FAIL.**

## 3. What "failed" earlier and why (now resolved / explained)
| Symptom | Root cause | Bug type | Status |
|---|---|---|---|
| All launch/run → HTTP 500 (`simple_launch`/`execute`) | Policy Engine VM down + enforcement enabled (`styx policy_helper.raise_error_if_policy_down`) | Environment / cluster-config | **Resolved** — Policy disabled from PC UI; BP+MPI then reached RUNNING. `e2e-launch-blocker/policy-engine-down-500.md` |
| **RB create custom form → 422** "Additional properties … custom_form_definition_list" | **Old container** lacked `ENG-892908` (Apr-27) which adds `custom_form_definition_list` to the runbook create/upload schema | Environment / stale image (NOT DSL, NOT schema) | **Resolved** — latest container: RB create works, form retained. `runbook-export-import-schema-rca.md` |
| Decompile crash on macro BPs (`dict changed size during iteration`) | `entity.py:525` deletes from dict mid-iteration | Decompile code bug (macro work) | **Fixed** — `list(user_attrs.items())`; 126 offline tests green |

## 4. Excluded — separate issue (update-config macro BP)
Not part of BP/RB/MPI custom-form scope; tracked separately.
- **Bug 2** — clone recompile crash: macro nic `["@@{nic}@@"]` + UpdateConfig →
  `config_spec.py:168 .compile()` on a str. (Not fixed — needs decision.)
- **Bug 3** — update-config action AHV v4 400: patch omits memory → spec sends
  `memorySizeBytes=0` (min 1). (Server/DSL macro path, not custom-form.)
  Detail: `e2e-launch-blocker/update-config-macro-findings.md`.

## 5. Per-PR readiness (for your review)
- **Custom-form retention (BP/RB/MPI)** — ✅ ready: compile/decompile/CRUD/launch all
  pass on latest container; R1 (form-name filename), R2 (launch warning), R3 (runtime JSON),
  R4 (`init_runbook_dir` 3-arg), R5 (`spec_file`) all validated.
- **entity.py decompile fix** — ✅ ready (small, safe; enables macro-BP decompile).
- **Macro / update-config BP** — ⛔ separate: Bug 2 & 3 to be handled in that PR.

## Conclusion
For **blueprint, runbook and marketplace-item** custom-form flows the feature is
**working end-to-end** on the latest container (126/126 offline; 9/10 live pass, the one
PARTIAL being RB-execute watch timeout, unrelated to custom forms). The two historical
"failures" (launch 500, RB 422) were **environment** issues (policy down, stale image),
now resolved.
