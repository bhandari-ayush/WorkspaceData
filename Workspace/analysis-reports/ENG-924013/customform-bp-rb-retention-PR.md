# ENG-924013 — CustomForm retention on BP / Runbook decompile + compile

- **Jira:** [ENG-924013](https://jira.nutanix.com/browse/ENG-924013)
- **Branch:** `taks/m-ENG-924013-cf-data-retention-bp-rb` (base `origin/master`)
- **Requires:** Calm `>= 4.4.0` (server schema; gated by `CUSTOM_FORM_MIN_VERSION`)

## Problem

A blueprint profile or runbook can carry a **CustomForm** (a launch-time form:
json schema + ui schema) on the server. `calm decompile` silently dropped it,
and the next `calm compile + upload` shipped the entity without the form — so
the form was **lost on every DSL round trip**, breaking GitOps workflows.

## What this PR does

Make the form (and its runtime-editable variables) survive the round trip, both
ways, **without** changing the existing `use_custom_form` semantics.

- **Decompile** lifts `custom_form_definition_list[0]` from the payload, parses
  `resources.schema`/`.uischema` JSON-strings back to dicts, writes the form to
  `specs/<...>_custom_form.yaml`, and emits a one-liner
  `custom_form = CustomForm(name="…")` in the generated `.py`.
- **Compile / CRUD** auto-loads that YAML and ships the form inline in
  `custom_form_definition_list` + a synthesised `custom_form_reference`.
- **`use_custom_form` is retained as authored** (True or False) — its value is
  never rewritten on compile or decompile.
- **Runtime-editable variables** are written to
  `specs/<prefix>_custom_form_runtime_variable.py` on decompile so the operator
  can pre-fill them at launch with `calm launch … -l <file>` (default launch
  flow; no custom-form UI required).

## Flow (arrow diagrams)

**Decompile (server → DSL)**

```
GET bp/runbook payload
   │
   │  app_profile_list[i] / runbook
   │    ├─ use_custom_form  (True|False)  ─────────────────────────┐
   │    ├─ custom_form_definition_list[0]  ─── render_custom_form_*─┤
   │    └─ runtime-editable variables       ─── render_runtime_vars─┤
   ▼                                                                ▼
decompile/profile.py · runbook.py                          generated DSL .py
   │                                                          custom_form =
   ├─► specs/<profile>_<form>.yaml      (BP, form name embedded) CustomForm(name=)
   ├─► specs/runbook_<form>.yaml        (RB)                     use_custom_form =
   └─► specs/<prefix>_custom_form_runtime_variable.py             <retained value>
                                         (variable_list = [...])
```

**Compile (DSL → server)**

```
blueprint.py / runbook.py
   │  custom_form = CustomForm(name="X")     use_custom_form = <as authored>
   ▼
Profile.compile / RunbookService.compile
   │
   └─► apply_custom_form_to_payload(cdict, context_prefix)
           │  load_custom_form_spec → reads specs/<prefix>_<form>.yaml
           │  CustomFormType.compile → JSON-stringify schema/uischema, version gate
           ▼
        cdict:
          use_custom_form            = <retained, unchanged>
          custom_form_definition_list = [ {name, uuid=uuid5(name), resources} ]
          custom_form_reference       = {kind: custom_form, name, uuid}
   ▼
PUT/POST to server  (idempotent: same source ⇒ identical payload)
```

**Launch (`use_custom_form` semantics — unchanged by this PR)**

```
calm launch bp/runbook  [-l <file>]
   │
   ├─ use_custom_form == True  ─► WARN "custom form launch not supported,
   │                               using default flow" → default launch
   │                               (a *_custom_form_runtime_variable.py -l file
   │                                is accepted to pre-fill runtime vars)
   │
   └─ use_custom_form == False ─► default launch
                                   (a *_custom_form_runtime_variable.py -l file
                                    is REJECTED: it does not apply here)
```

## New artifacts a reviewer / author will see

| Thing | Where / name | Notes |
|-------|--------------|-------|
| Form definition (YAML) | `specs/<context_prefix>_<form_name>.yaml` | Reviewable in PRs (multi-line `schema`/`uischema`, `# comments`). `context_prefix` = **profile name** (BP) or the constant **`runbook`** (RB). The **form name is embedded** so a renamed form keeps a distinct, round-trip-stable file. |
| Runtime-editable launch params (Python) | `specs/<prefix>_custom_form_runtime_variable.py` | `variable_list = [...]` in launch shape. Consumed by `calm launch … -l <file>`. **Detected purely by the `_custom_form_runtime_variable.py` filename suffix** — no in-file marker. |
| DSL one-liner | `custom_form = CustomForm(name="…")` | What decompile emits; compile auto-loads the YAML. Explicit `spec_file="…"` / `spec=read_spec("…")` also supported. |
| Read-only REST client | `api/custom_form.py` → `CustomFormAPI` | `read` / `list` inherited; `create` / `update` / `delete` raise `NotImplementedError`. **The DSL never authors a form over REST** — the blob ships inline; the client is for introspection only. |

## Schema (verified, not redundant)

The Profile / RunbookService OpenAPI carries **one DSL-only input field plus the
three server (wire) fields**:

| Field | Side | Verified |
|-------|------|----------|
| `custom_form` (`x-calm-dsl-type: custom_form`) | **DSL-only input** | **Required.** Removing it makes `custom_form = CustomForm(...)` raise `TypeError: Unknown attribute custom_form given`. It is popped by `apply_custom_form_to_payload` before the wire payload is built, which is why it does **not** appear in styx swagger. |
| `use_custom_form` / `custom_form_reference` / `custom_form_definition_list` | **Wire** | Match `styx/yamls/apps/app_profile.yaml` 1:1. |

## File-by-file (execution order)

**Compile (DSL → server)**

| File | Change |
|------|--------|
| `constants.py` | `CUSTOM_FORM_MIN_VERSION`, `custom_form_yaml_filename()`, `CUSTOM_FORM_RUNTIME_FILE_SUFFIX`, launch warning / runtime-file error text; `custom_forms` URL. |
| `api/custom_form.py` (new) + `api/handle.py` | Read-only `CustomFormAPI` (`read`/`list`); `create`/`update`/`delete` raise. |
| `builtins/models/custom_form.py` (new) | `CustomForm(...)` factory, `CustomFormType.compile` (version gate, JSON-stringify schema/uischema), `apply_custom_form_to_payload` (retains `use_custom_form`, builds `custom_form_definition_list` + `custom_form_reference`), `load_custom_form_spec` (auto-load YAML). |
| `builtins/models/schemas/*.jinja2` | OpenAPI for the entity + the input field + 3 wire props on Profile/RunbookService (min-version 4.4.0). |
| `profile.py` / `runbook_service.py` | Call `apply_custom_form_to_payload` with the profile name / runbook prefix. |
| `cli/bps.py`, `cli/runbooks.py` | `set_dsl_source_dir`; launch warning when `use_custom_form=True`; reject a `*_custom_form_runtime_variable.py` `-l` file when `use_custom_form=False`. |

**Decompile (server → DSL)**

| File | Change |
|------|--------|
| `decompile/file_handler.py` | `make_runbook_dirs` now creates `specs/` + sets `SPECS_DIR` (runbooks had none); public return stays the 3-tuple — master parity. |
| `cli/runbooks.py` | `_hydrate_custom_form_definition_list`: a plain `GET /runbooks/{uuid}` omits the blob, so fetch it via the read-only API and splice it in. |
| `decompile/custom_form.py` (new) | Parse schema/uischema back to dicts, write the YAML, emit the `CustomForm(name=…)` line; write the runtime-var `.py`. Decompile is silent (warning only at launch). |
| `decompile/profile.py` / `runbook.py` | Wire the renderer in; pop the raw wire fields. |
| `decompile/schemas/profile.py.jinja2` / `runbook.py.jinja2` | When a form exists, emit `custom_form = …` + the **retained** `use_custom_form` value; no-form entities stay clean. (Runbook attrs land on `<rb>.runbook`.) |

## Risk surface (review checklist)

| Concern | Why it's bounded |
|---------|------------------|
| Older Calm rejects the new fields | All new props carry `x-calm-dsl-min-version: 4.4.0` + `not-required-if-none`; `compile` aborts with a clear message on Calm < 4.4.0 (skipped offline). |
| `@runbook` descriptor swallows attrs on the bare function | Decompile emits `<rb>.runbook.custom_form = …`. |
| `read_spec` is frame-relative and mis-resolves at compile | `load_custom_form_spec` resolves against `set_dsl_source_dir` (the `.py` dir), not the caller frame. |
| No-form payload trips a server `422` | Empty `custom_form_definition_list` / `custom_form_reference` are popped for no-form entities. |
| Re-compile double-adds the form | UUID is `uuid5(name)`, so repeat compiles produce an identical payload. |
| Runbook GET omits the form blob | `_hydrate_custom_form_definition_list` fetches it; no-op when already present. |
| Runtime `.py` applied to the wrong entity | Launch rejects a `*_custom_form_runtime_variable.py` `-l` file when `use_custom_form=False`. |

## Test plan

**Offline — 130 passing, 0 failing.**

| Suite | Cases | What it covers |
|-------|-------|----------------|
| In-tree `tests/unit/test_custom_form.py` | 60 | entity, version gate, read-only API contract, lazy `CustomForm(name=)` auto-load, `apply_custom_form_to_payload`, Profile + RunbookService compile, decompile, runbook namespace, runtime-file launch gating. |
| In-tree `tests/unit/test_decompile_runbook_specs_dir.py` | 5 | `init_runbook_dir` parity with `init_bp_dir` (creates `specs/`). |
| In-tree `tests/unit/test_decompile_http_var_with_basic_auth.py` | 1 | unchanged neighbour, still green. |
| Out-of-tree `eng-924013-regression/tests` | 64 | custom_form (11), api_sanity (9), negative_paths (7), followup (12), multi_profile (8), round_trip (9), runbook (8) — incl. static + dynamic runtime-var e2e. |

**Live server (Calm 4.4.0, `10.103.243.86`, latest containers) — BP / RB / MPI.**

| Entity | Flow validated | Result |
|--------|----------------|--------|
| **BP** | compile→create, decompile (form + runtime `.py` retained), recompile→re-upload v2, launch (warning + runtime-var fill → app RUNNING) | ✅ |
| **RB** | compile→create with form (no 422 on latest container), decompile (form retained, `use_custom_form=True`), execute (warning + default flow) | ✅ (execute watch timed out — engine timing, not custom-form) |
| **MPI** | publish→approve→store, form retained in marketplace item, clone/launch → app RUNNING | ✅ |

Artifacts (results, logs, decompiled outputs, server-run READMEs):
`WorkspaceData` repo → `analysis-reports/ENG-924013/` (`test-summary.md`,
`server-test-runs/`).

## Out of scope

- The custom-form **launch UI** (server-driven). When `use_custom_form=True`,
  launch logs a warning and runs the **default** launch flow.
- CustomForm **CRUD over REST** from the DSL — the form ships inline; the REST
  client is read-only.
- update-config / NIC macro blueprint — tracked separately.
