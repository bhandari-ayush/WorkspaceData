# ENG-924013 — Server test run (use_custom_form runtime-file gating)

- **Setup:** `10.103.243.86`, Calm **4.4.0**, PC `ganges-7.6-stable-pc`.
- **calm-dsl branch:** local working branch (CustomForm retention + macro work).
- **Detection model under test:** a custom-form runtime editables file is recognised
  **internally by its `_custom_form_runtime_variable.py` filename** — nothing is written
  inside the file (no in-file marker).
- **Date:** 2026-06-18.

## Pre-check — runtime file has no in-file marker

Decompiled `e2e924013_bp_v2`; the generated
`specs/Default_custom_form_runtime_variable.py` starts directly with `variable_list = [...]`
and contains **no** `is_custom_form_runtime` marker. (`00_decompile.log`,
`00_runtime_file_check.log`.)

## Launch matrix

| # | Test case | What it tests | Command | Expected | Actual | Log |
|---|---|---|---|---|---|---|
| A | CF=True + custom-form file | A custom-form blueprint accepts its runtime file; launch warns and runs the default flow | `calm launch bp e2e924013_bp_v2 -l <Default_custom_form_runtime_variable.py>` | WARNING "Custom form launch is not supported…" then `Successfully launched` | PASS — warning fired, app `5b04a88e-d242-411f-b32d-ab92fc0aaf77` | `caseA_true_with_cf_file.log` |
| B | CF=False + custom-form file | A non-custom-form profile **rejects** a custom-form runtime file | `calm launch bp normal_flow -l <Default_custom_form_runtime_variable.py>` | ERROR "Custom-form runtime editables file '…' can only be used when … use_custom_form=True", non-zero exit, **no app** | PASS — exit 255, error fired, no app created | `caseB_false_with_cf_file.log` |
| C | CF=False + plain file | A marker-less `-l` file is **not** gated; plain launch proceeds | `calm launch bp normal_flow -l /tmp/cfm/plain_launch_params.py` | No gating error; `Successfully launched` | PASS — app `067d1541-59d4-4b02-9bfa-4a973d9e487d` | `caseC_false_with_plain_file.log` |
| D | CF=False, **no** `-l` | Default 4.3.0 interactive runtime-editable flow is unchanged | `calm launch bp normal_flow` (defaults accepted) | Prompts vCPUs/Cores/Memory, then `Successfully launched` | PASS — prompts shown, app `716d57f1-baba-49a1-8d1f-e2e58475fee7` | `caseD_false_no_launch_params_interactive.log` |

Cases A, C, B use the file **with** launch params (`-l`); case D is the **without** launch
params (interactive) path.

## Cleanup note

Apps `5b04a88e…`, `067d1541…`, `716d57f1…` (cases A/C/D) returned **422** on soft/normal
delete (`Unable to run delete action on Application`) — a known `.86` state/policy quirk,
unrelated to the DSL change. Delete from the PC UI when convenient. Case B created no app.

## Exact commands (history)

```bash
# pre-check
calm decompile bp e2e924013_bp_v2 -d /tmp/cfm/v2n
head -4 /tmp/cfm/v2n/specs/Default_custom_form_runtime_variable.py   # -> variable_list = [...]
grep -c is_custom_form_runtime /tmp/cfm/v2n/specs/Default_custom_form_runtime_variable.py  # -> 0

CF=/tmp/cfm/v2n/specs/Default_custom_form_runtime_variable.py
cp "$CF" /tmp/cfm/plain_launch_params.py            # same content, non-CF filename

# A: CF=True + custom-form file  -> warn + launch
calm launch bp e2e924013_bp_v2 -l "$CF"
# B: CF=False + custom-form file -> ERROR, no app
calm launch bp normal_flow -l "$CF"
# C: CF=False + plain file       -> plain launch
calm launch bp normal_flow -l /tmp/cfm/plain_launch_params.py
# D: CF=False, no -l             -> interactive prompts, launch
printf '\n\n\n' | calm launch bp normal_flow
```
