# CustomForm + AHV Macro Support — Technical Design (ENG-924013)

Audience: calm-dsl reviewers and users. Scope (per the Custom Form epic): DSL support for
**Custom Form definitions, runtime inputs, JSON variables, and dynamic macro-based AHV
substrate fields** across compile / decompile / launch for blueprints, runbooks, and
marketplace items. Target: Calm **4.4.0+**
(`CUSTOM_FORM_MIN_VERSION` / `MACRO_SUPPORT_AHV_SPEC_MIN_VERSION`).

---

## 1. Behavior at a glance

- **Decompile** retains the custom-form definition and the authored `use_custom_form` value;
  the round trip download → edit → upload is faithful.
- **Compile** keeps `use_custom_form` as authored.
- **Custom-form launch** (the server-driven form UI) is out of scope: launch **warns** and
  runs the standard runtime-editable launch flow.
- **Macros** (`@@{var}@@`) are supported on a defined allowlist of AHV VM fields and survive
  the round trip unchanged.

---

## 2. CustomForm round trip

### 2.1 Decompile (server → DSL)

For a profile / runbook that carries a custom form, decompile writes two artifacts under
`specs/`:

| Artifact | Produced by | Contents |
|---|---|---|
| `specs/<owner>_<formname>.yaml` | `decompile/custom_form.py: render_custom_form_blob` | the form blob (`name`, `description`, `resources.schema/uischema`) parsed back to YAML |
| `specs/<owner>_custom_form_runtime_variable.py` | `decompile/custom_form.py: render_custom_form_runtime_vars` | runtime-editable variables in launch shape (`variable_list = [...]`) |

The generated `blueprint.py` / `runbook.py` emits a lazy `CustomForm(name="...")` line and
`use_custom_form = <authored value>`. Compile auto-loads the YAML by filename convention
(`custom_form_yaml_filename`), so the two sides always agree on where the form lives.

**Design decision — filename embeds the form name** (`<owner>_<formname>.yaml`): the form
survives a round trip even if renamed, and multiple profiles can each own a distinct form.

### 2.2 Compile (DSL → server)

`builtins/models/profile.py` and `runbook_service.py` populate `custom_form_definition_list`
from the loaded YAML and pass `use_custom_form` through unchanged.

### 2.3 Decompile is silent about the launch warning

The custom-form "not supported" message is a **launch-time** concern only; decompile does not
emit it (`decompile/custom_form.py`: *"use_custom_form is preserved as-is; True only triggers
a launch-time warning"*). This keeps decompile output clean.

---

## 3. Runtime-editables file

### 3.1 File format

`specs/<owner>_custom_form_runtime_variable.py` is a plain Python launch-params module so it
can be passed to `calm launch bp ... -l <file>` (`-i <file>` for runbooks):

```python
variable_list = [
    {"value": {"value": "dev"}, "context": "Default", "name": "region"},
    ...
]
```

It contains **only** `variable_list` — the same shape every launch-params `.py` uses — so the
existing `-l/-i` parser consumes it with no new logic.

### 3.2 How launch recognises it (internal, by filename)

A custom-form runtime file is identified **internally by its
`_custom_form_runtime_variable.py` filename suffix** (`constants.CUSTOM_FORM_RUNTIME_FILE_SUFFIX`,
checked by `cli/bps.py: launch_params_is_custom_form_runtime`). Nothing is written inside the
file to mark it — the detection logic lives in the DSL, not in the artifact. This is what lets
launch enforce that the file is only used against a custom-form entity (§4).

---

## 4. Launch behavior matrix

Enforced in `cli/bps.py: launch_blueprint_simple` and `cli/runbooks.py: run_runbook_command`.
The decision reads `use_custom_form` from the **server** profile/runbook payload and whether
the `-l`/`-i` file is a custom-form runtime file (by filename).

| Entity state | `-l`/`-i` is a custom-form runtime file? | Behavior |
|---|---|---|
| **No custom form** | n/a | Standard runtime-editable flow. Substrate `create_spec` editables file written (§5), interactive prompts / defaults. |
| **`use_custom_form = True`** | yes **or** no | **Warn** (`CUSTOM_FORM_LAUNCH_NOT_SUPPORTED_WARNING`) and continue the default launch. All runtime fields are shown/prompted; values from the `.py` file are applied, the rest take defaults. |
| **`use_custom_form = False`** (author set it) | **yes** | **Error + exit** (`CUSTOM_FORM_RUNTIME_REQUIRES_CUSTOM_FORM_ERROR`). The custom-form runtime file does not apply to a non-custom-form entity. |
| **`use_custom_form = False`** | no | Standard runtime-editable launch. |

Net guarantee: (a) non-custom-form blueprints use the standard runtime-editable flow;
(b) a custom-form blueprint can still be launched (with a clear warning); (c) custom-form
runtime data cannot silently be applied to an entity where the author has disabled the custom
form.

### 4.1 Live validation (`.86`, Calm 4.4.0)

See `server-test-runs/<run-id>/README.md` for full CLI logs and outputs.

| Case | Command | Result |
|---|---|---|
| A — CF=True + CF file | `calm launch bp e2e924013_bp_v2 -l <…_custom_form_runtime_variable.py>` | WARNING, then `Successfully launched` |
| B — CF=False + CF file | `calm launch bp normal_flow -l <…_custom_form_runtime_variable.py>` | ERROR + non-zero exit, no app |
| C — CF=False + plain file | `calm launch bp normal_flow -l <plain_launch_params.py>` | plain launch, no gating error |
| D — CF=False, no `-l` | `calm launch bp normal_flow` | interactive prompts, then launch |

---

## 5. When `*_create_spec_editables.yaml` is generated

`decompile/substrate.py` writes `specs/<VM>_create_spec_editables.yaml` **iff** the server
returns non-empty `substrate.editables.create_spec` for that substrate:

```python
create_spec_editables = provider_spec_editables.get("create_spec", {})
if create_spec_editables:
    ... write <VM>_create_spec_editables.yaml ...
```

This depends purely on **where editability is declared**, and is independent of custom forms:

- **Substrate-level editability** (VM spec fields like `num_sockets`, `num_vcpus_per_socket`,
  `memory_size_mib` marked runtime-editable on the VM) → server returns `create_spec`
  editables → the YAML is written (the `normal_flow` case).
- **Profile-variable / macro editability** (VM resources driven by profile variables via
  macros, e.g. `vCPUs = @@{cpu}@@`) → the substrate carries **no** `create_spec` editables →
  the YAML is **not** written; the editable values live in the profile variable list.

A custom-form blueprint can have either (e.g. `macro_bp` decompiles with both a custom form
and a `VM1_create_spec_editables.yaml`). The file's presence is not a custom-form signal — it
reflects substrate-level editables in that particular blueprint.

---

## 6. AHV macro support on VM specs

`@@{var}@@` macros are resolved server-side at runtime; the DSL treats a full-string macro as
opaque and does not parse it structurally.

### 6.1 Allowlist (`constants.AHV_MACRO_FIELDS`, enforced by `macro_helper.validate_ahv_macro_fields`)

| Entity | Field | Type |
|---|---|---|
| `AhvVm` | `name`, `cluster_reference`, `categories` | string / json |
| `AhvVmResources` | `num_sockets`, `num_vcpus_per_socket`, `memory_size_mib`, `power_state`, `guest_customization`, `disk_list`, `nic_list` | int / string / json / json-per-item |
| `AhvDisk` | `data_source_reference`, `disk_size_mib` | json / int |
| `AhvNic` | `subnet_reference` | json |

A macro on any **other** AHV field is rejected at compile **and** decompile with a clear,
actionable error (`AHV <entity> compile: macro on unsupported field 'X'. Allowed (Calm 4.4.0): ...`).
Example: a macro on `vpc_reference` is intentionally rejected in 4.4.0.

### 6.2 Decompile handling (`builtins/models/entity.py`)

- Full-string macros (`MACRO_PATTERN = ^@@\{[^}]+\}@@$`) are kept **as-is**.
- Non-macro strings (e.g. bare UUIDs the server returns in reference lists) skip structural
  decompile and keep their raw value.
- Type-mismatched fields are excluded from the generated class instead of aborting.
- The attribute map is iterated over a snapshot (`list(user_attrs.items())`) so the
  type-mismatch branch can safely drop a key without mutating-during-iteration.

---

## 7. Logging policy

Rule: **compile / decompile / launch diagnostics are `debug`; only genuinely user-facing flow
stays at `info`; failures are `error` / `warning`.** Demoted `info → debug`:

- `decompile/decompile_render.py` — all six `Formatting <X> file using black`.
- `builtins/models/entity.py` — all `[decompile] Field '...'` diagnostics.
- `cli/bps.py` — `Searching for existing applications` / `No existing application found`.

---

## 8. What a user can do

- **Download / edit / upload** a blueprint, runbook, or MPI with a custom form and keep the
  form intact.
- **Author** `use_custom_form = True/False` and have it preserved.
- **Launch** a custom-form blueprint: it runs the standard launch flow with a warning; pass
  the generated `*_custom_form_runtime_variable.py` via `-l` to fill runtime fields
  non-interactively, or omit it to be prompted.
- **Use macros** on the AHV fields in §6.1 to template VM name, cluster, categories, CPU /
  memory, disks, NIC subnet, etc.
- **Publish / clone** custom-form blueprints as marketplace items — the form is retained.

## 9. Limitations / out of scope

- **Server-driven custom-form launch UI** is not implemented; launch falls back to the default
  flow with a warning.
- A custom-form runtime file is **rejected** against an entity whose `use_custom_form` is
  `False` (§4).
- Macros are restricted to the §6.1 allowlist; other AHV fields error out.
- The DSL never authors custom forms via the API (`api/custom_form.py` create/update/delete
  raise `NotImplementedError`); forms originate from the server payload.
- **Tracked separately:** update-config macro blueprint issues (clone-recompile crash on macro
  NIC + UpdateConfig; AHV v4 update-config 400 on omitted memory). See
  `e2e-launch-blocker/update-config-macro-findings.md`.

## 10. Key files

| File | Role |
|---|---|
| `decompile/custom_form.py` | write form YAML + runtime `.py` (`variable_list` only) |
| `decompile/profile.py`, `decompile/runbook.py` | emit `CustomForm(...)` + retain `use_custom_form` |
| `decompile/substrate.py` | write `*_create_spec_editables.yaml` when substrate has create_spec editables |
| `builtins/models/profile.py`, `runbook_service.py` | compile: keep `use_custom_form`, populate `custom_form_definition_list` |
| `builtins/models/entity.py` | macro-safe decompile + iteration-snapshot |
| `builtins/models/macro_helper.py`, `constants.AHV_MACRO_FIELDS` | macro detection + AHV allowlist |
| `cli/bps.py`, `cli/runbooks.py` | launch matrix + custom-form-file gating |
| `constants.py` | `CUSTOM_FORM_*`, `CUSTOM_FORM_RUNTIME_FILE_SUFFIX`, error/warning text |

## 11. Validation summary

- Unit: `tests/unit/test_custom_form.py` — **60 passed** (incl. the gating tests in
  `TestCustomFormRuntimeLaunchGating`).
- Out-of-tree regression (`eng-924013-regression`): **64 pytest passed**; the compile-variant
  step intentionally rejects the `vpc_reference` macro variant (allowlist enforcement).
- Live `.86` (Calm 4.4.0): launch matrix A/B/C/D confirmed (§4.1, with full CLI logs under
  `server-test-runs/`); BP/RB/MPI compile → decompile → recompile → launch → publish → clone
  covered in `test-summary.md`.
