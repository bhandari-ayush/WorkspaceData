# Self-Service / Epsilon Debugging Sheet (Token-Efficient)

Use this as the default playbook for NCM Self-Service, Calm, Epsilon, Ergon, and macro-related issues.

## 0) Accuracy-first operating rules
- If any ID/source is uncertain, mark it as unverified and confirm before branching investigation.
- Capture exact command + exact output in notes.
- Never start with full logs; always start with a known identifier and narrow queries.

## 1) Common identifiers and naming

The naming below is used operationally; exact field names vary by API/log version.

- `rr`: root request id (request correlation id used across service logs).
- `cr`: child request id (downstream request id; not always present in every service).
- `pr`: parent request id or prior request reference (depends on service instrumentation).
- `task_id`: generic task identifier (can refer to workflow/action task).
- `ergon_task_id`: canonical task id in Ergon for state tracking.
- `engine_trl_uuid`: Epsilon TaskRunLog root id for the workflow execution tree.
- `trl_uuid`: task run log id for a specific node (often leaf debug target).

If `cr`/`pr` are missing in a component, use `rr + ergon_task_id` as the primary join key.

## 2) Fast triage sequence (always this order)

1. Identify failing entity: app/project/action/workflow.
2. Capture one stable id (`rr` or `ergon_task_id`).
3. Resolve `engine_trl_uuid` from Calm/Nucalm metadata.
4. Traverse child TRLs until first failing leaf.
5. Inspect owning service log for that leaf (`indra`/`durga`/`arjun`/`karan`).
6. Correlate with upstream API log (`styx`/`zaffi`) for request payload context.

## 3) Service map for app launch and checkpoints

```
Client/API call
  -> Nucalm Styx (API entry)
  -> Nucalm Jove/Hercules (plan + scheduling)
  -> Epsilon Zaffi (workflow API ingress)
  -> Epsilon Durga (graph parse + task planning)
  -> Epsilon Jove (dispatch)
  -> Worker service (Indra/Arjun/Karan/etc)
  -> Narad callback + status propagation
  -> Ergon milestone/state update
  -> Nucalm Iris callback and final runlog state
```

Checkpoint expectations:
- API accepted at Styx/Zaffi.
- Ergon task created and moves from queued to running.
- Child TRLs created under root TRL.
- Leaf worker logs show concrete external call/result.
- Callback updates upstream state and final status.

### 3.1 Service responsibilities (what each does)

| Service | What it does in launch flow | What to verify first |
|---|---|---|
| `styx` (nucalm) | API ingress, auth/context, request shaping | request accepted, request id present, payload not truncated |
| `jove` (nucalm) | orchestration scheduling and dispatch control | runlog/action created and queued correctly |
| `hercules` (nucalm) | compiles action/workflow plan for execution | generated plan has expected tasks/stages |
| `zaffi` (epsilon) | epsilon API entrypoint for workflow execution | workflow start accepted, callback metadata present |
| `durga` (epsilon) | graph walker/parser, task graph and transitions | macros/types resolved, child task graph created |
| `jove` (epsilon) | dispatches executable tasks to workers | leaf tasks assigned to correct worker type |
| `indra` (epsilon) | cloud/platform/API-heavy execution tasks | external endpoint/API errors, retry/backoff behavior |
| `arjun` (epsilon) | shell/script execution (linux) | command payload, stdout/stderr, exit code |
| `karan` (epsilon) | powershell/windows task execution | script invocation correctness and host connectivity |
| `narad` (epsilon) | completion/notification propagation | completion callback fired with correct status |
| `iris` (nucalm) | upstream callback/state reconciliation | final runlog status mapped correctly |
| `ergon` | durable task state/milestone lifecycle | expected milestone progression and terminal status |

### 3.2 App launch triage by stage

1. **Ingress stage** (`styx`, `zaffi`): validate request was accepted and correlated id exists.
2. **Plan stage** (`hercules`, `durga`): validate generated graph and parsed runtime inputs.
3. **Dispatch stage** (`epsilon jove`): validate queue and worker assignment.
4. **Execution stage** (`indra`/`arjun`/`karan`): isolate failing leaf task and concrete error.
5. **Callback stage** (`narad`, `iris`): validate state propagation and runlog convergence.
6. **State stage** (`ergon`): validate transitions and reason fields for terminal state.

## 4) Log locations (primary)

Host-level:
- `/home/nutanix/data/logs/genesis.out`
- `/home/nutanix/data/logs/nucalm.out`
- `/home/nutanix/data/logs/epsilon.out`

Nucalm:
- `/home/docker/nucalm/log/styx.log`
- `/home/docker/nucalm/log/jove.log`
- `/home/docker/nucalm/log/hercules.log`
- `/home/docker/nucalm/log/iris.log`

Epsilon:
- `/home/docker/epsilon/log/zaffi.log`
- `/home/docker/epsilon/log/jove.log`
- `/home/docker/epsilon/log/durga.log`
- `/home/docker/epsilon/log/indra.log` (or `indra_0.log`, `indra_1.log`)
- `/home/docker/epsilon/log/arjun.log`
- `/home/docker/epsilon/log/karan.log`
- `/home/docker/epsilon/log/narad.log`
- `/home/docker/epsilon/log/vajra.log`

## 5) Command cookbook

### 5.1 Correlate with request id
```bash
RR="<root-request-id>"
grep -Rsn "$RR" /home/docker/nucalm/log /home/docker/epsilon/log
```

### 5.2 Ergon task quick checks
```bash
ecli task.list include_completed=false limit=1000
ecli task.list component_list=Calm-Engine-Hercules,Calm-Engine-Indra,Calm-Engine-Durga,Calm-Engine-Narad
ecli task.get <ergon_task_uuid>
```

### 5.3 Trace child tasks (from root TRL)
Python/eshell flow (environment specific):
```python
trl = s.query(m.TaskRunLog).filter_by(uuid="<engine_trl_uuid>").all()
print(trl[0].children)  # recurse until failing leaf trl_uuid
```

### 5.4 Extract leaf execution output (if Vajra API available)
```bash
curl --location 'http://<pcvm_or_local>:4120/api/workflowrun/get_trl_output' \
  --header 'Content-Type: application/json' \
  --header 'Authorization: Basic <redacted>' \
  --data '{"trl_uuid":"<leaf-trl-uuid>"}'
```

### 5.5 Macro and payload checks
```bash
grep -Rsn "macro\\|parse\\|template\\|in_args\\|out_args" /home/docker/epsilon/log/durga*.log
grep -Rsn "<rr_or_task_id>" /home/docker/epsilon/log/durga*.log
```

## 6) Macro issues in Calm/Durga

Common failure pattern:
- macro placeholders survive into downstream payloads as raw strings,
- task expects structured object/value and fails parse/validation.

What to verify:
1. launch payload variable section (pre-Epsilon),
2. Durga parser logs for resolution and type conversion,
3. leaf worker task input fields matching expected schema.

## 7) Ergon usage notes

What gets updated:
- task status (`queued/running/success/failure/aborted`)
- milestone/progress updates from workflow engine components

How to inspect current state:
```bash
ecli task.get <ergon_task_uuid>
```
Look for:
- current status,
- milestone transitions,
- error message/reason fields,
- update timestamps (stalled windows).

## 8) Task model: inargs/outargs and execution lifecycle

Code-level confirmed behavior (calm/epsilon shared patterns):
- `in_args`/`out_args` are explicit task call workflow fields.
- call workflow path builds `inArgs` from available properties.
- state transitions are mapped into Ergon milestones by Durga/Jove contracts.

Execution timing model:
1. task spec parsed and normalized,
2. `in_args` resolved into runtime inputs,
3. workflow/leaf task executes,
4. `out_args` are captured and pushed upstream for later steps.

If state progression is broken:
- verify whether `ergon_task_id` exists on runlog/task context,
- verify milestone updates are being emitted.

## 9) PostgreSQL query starter pack

Use only in approved/debug environments with least privilege.

```sql
-- recent task-like rows (adapt table names to deployment schema)
SELECT id, status, created_at, updated_at
FROM task_run_log
ORDER BY created_at DESC
LIMIT 100;

-- fetch a specific runlog/task
SELECT *
FROM task_run_log
WHERE uuid = '<trl_uuid>';

-- status distribution in a time window
SELECT status, COUNT(*)
FROM task_run_log
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY status
ORDER BY COUNT(*) DESC;
```

If schema/table names differ, first introspect:
```sql
\dt
\d+ task_run_log
```

## 10) One-year pattern highlights (NCM2.0/NCM2.1/Iris/Janus)

Top recurring clusters:
- upgrade/migration state mismatches,
- RBAC visibility and projection issues,
- task stuck/running with incomplete transitions,
- dependency resolution and service reachability failures,
- schema/macro payload incompatibilities.

First-check matrix:
- upgrade issue -> verify mapping/znode/state sync + runlog continuity.
- stuck task -> `ecli task.get` + child TRL traversal.
- RBAC mismatch -> compare backend success vs filtered response projection.
- macro failure -> verify resolved payload types before leaf execution.

## 11) Cursor usage and routing guidance (for lower request cost)

Recommended:
- Use Cursor IDE agent for iterative code+log work where local context matters.
- Use CLI/one-shot mode for bounded analyses (single question, fixed artifact).
- Route by complexity:
  - quick lookup: fast model, <=2 reads
  - bug triage: balanced model, strict id-first flow
  - RCA/design fork: high-reasoning model only for decision points
- De-escalate model after hard reasoning step to save budget.

## 12) How to feed analysis to the agent (best format)

Best (lowest token cost):
1. Write findings in a file under `analysis-reports/<ticket-or-topic>/`.
2. Provide:
   - exact path,
   - objective,
   - 3-5 decisive log lines/IDs,
   - open questions.

Template:
```text
Goal: <one line>
Evidence file: <absolute/relative path>
Known IDs: rr=..., ergon_task_id=..., trl_uuid=...
Observed error: <exact line>
Ask: <specific next action>
```

Avoid pasting huge raw logs directly in chat unless needed for an exact quote.

## 13) 1-2 day monitoring checklist

- Track per-investigation:
  - request count,
  - time to first failing leaf task,
  - time to root-cause hypothesis,
  - number of false paths.
- If request count crosses 40, checkpoint and summarize before continuing.
- At 50 requests, stop and decide whether to continue with narrowed scope.

## 14) Graph engineering loop (from your image)

Use this loop only when user explicitly asks for a planned multi-step execution (or explicitly starts with `bug:` for bug workflows).

```
Task
 -> Planner
 -> Worker
 -> Reviewer 1..N (parallel where possible)
 -> Synthesize
 -> Pass?
    -> no: feedback -> Worker (iterate with revision cap)
    -> yes: Turn into actionable output
 -> Plan Reviewer
 -> Send to user
```

### 14.1 Node contract for local usage

- `Planner`: converts task into scoped plan + acceptance criteria + constraints.
- `Worker`: executes one scoped unit at a time; emits artifacts and evidence.
- `Reviewer(s)`: independent verification (quality, correctness, security, testability).
- `Synthesize`: merges reviewer outputs into one verdict + actionable deltas.
- `Pass gate`: deterministic threshold check (not free-text judgement).
- `Plan Reviewer`: final coherence check before user-facing output.

### 14.2 Hard guards

- Use typed state shared across nodes (objective, constraints, artifacts, verdicts).
- Cap revision loops (`max_revisions`, `recursion_limit`) to avoid cost runaway.
- Keep reviewer read-only and independent from worker output claims.
- Require structured outputs for routing (`PASS|PARTIAL|FAIL|BLOCKED`).
- Separate reasoning nodes from side-effect nodes (commit/push/deploy).

### 14.3 Inputs user should provide to start graph loop

```text
Task: <one line goal>
Mode: planning | execution | bug
Scope: <repos/files/services>
Acceptance criteria: <bullet list>
Constraints: <time/budget/risk/compliance>
Evidence/resources: <logs, links, files, IDs>
Side-effects allowed: yes/no (commit, push, deploy)
```

### 14.4 Bug-mode opt-in rule

Graph bug flow should run only when user explicitly marks start with one of:
- `bug:`
- `[bug]`
- `rca:`

Else default to normal single-agent flow to conserve requests/tokens.
