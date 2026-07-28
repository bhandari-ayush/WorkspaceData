#!/usr/bin/env python3
"""Model A/B token-efficiency test harness (headless cursor-agent).

For a fixed set of issues (labelled by type), run each issue on several models in
READ-ONLY mode and record tokens / cost / wall-time, so we can validate the router's
mapping: "for a lookup, is the cheap model really cheaper and still correct?".

Safety: defaults to `--mode ask` (read-only Q&A) so test runs never edit code.

Auth: needs `cursor-agent login` (or CURSOR_API_KEY). Use --dry-run to preview the
commands without auth.

Usage:
  python3 model-ab-test.py --list-models                 # what models are available
  python3 model-ab-test.py --dry-run                     # preview commands, no calls
  python3 model-ab-test.py --models auto,sonnet-4.5,claude-opus-4-8
  python3 model-ab-test.py --models auto,gpt-5 --only lookup,fix
Results: orchestration/token-efficiency/reports/ab/<timestamp>/ (raw json + summary.csv)
"""
import os, sys, json, time, subprocess, datetime, shutil, csv

ROOT = os.path.expanduser("~/Workspace")
OUTDIR = os.path.join(ROOT, "orchestration/token-efficiency/reports/ab")
AGENT = shutil.which("cursor-agent") or os.path.expanduser("~/.local/bin/cursor-agent")

# (type, prompt) — small, read-only-answerable issues spanning the router tiers.
TEST_SET = [
    ("lookup",  "What does the function IsPulseEnabled do and where is it defined?"),
    ("explore", "Explain at a high level how project usage rollup flows in styx."),
    ("fix",     "Describe the minimal change to add a nil check before dereferencing the project pointer in projects_uuid_usage."),
    ("bug",     "Why might projects_uuid_usage return a 500 intermittently? List the top 2 causes to check."),
    ("design",  "Compare 2-3 approaches to cache project usage rollups (in-memory vs IDF vs materialized), with trade-offs."),
    ("rca",     "Root-cause approach for ENG-960206: project usage returns 500 in production. Outline the investigation steps."),
]

DEFAULT_MODELS = ["auto", "gpt-5", "gpt-5-codex", "sonnet-4.5", "claude-opus-4-8[effort=high]"]


def logged_in():
    try:
        out = subprocess.run([AGENT, "status"], capture_output=True, text=True, timeout=30)
        return "not logged in" not in (out.stdout + out.stderr).lower()
    except Exception:
        return False


def list_models():
    subprocess.run([AGENT, "--list-models"])


def extract_usage(raw):
    """Best-effort pull of token/cost fields from cursor-agent json (schema-tolerant)."""
    found = {}
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                lk = k.lower()
                if any(s in lk for s in ("token", "cost", "usage", "input", "output")) and isinstance(v, (int, float)):
                    found[k] = v
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    try:
        walk(json.loads(raw))
    except Exception:
        pass
    return found


def run_one(model, prompt, mode, timeout):
    cmd = [AGENT, "-p", "--output-format", "json", "--model", model, "--mode", mode, prompt]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        dt = time.time() - t0
        return dict(ok=r.returncode == 0, seconds=round(dt, 1), raw=r.stdout, err=r.stderr[-400:])
    except subprocess.TimeoutExpired:
        return dict(ok=False, seconds=timeout, raw="", err="timeout")


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    if "--list-models" in args:
        return list_models()
    models = DEFAULT_MODELS
    only = None
    mode = "ask"
    timeout = 300
    i = 0
    while i < len(args):
        if args[i] == "--models":
            models = args[i + 1].split(","); i += 2
        elif args[i] == "--only":
            only = set(args[i + 1].split(",")); i += 2
        elif args[i] == "--mode":
            mode = args[i + 1]; i += 2
        elif args[i] == "--timeout":
            timeout = int(args[i + 1]); i += 2
        else:
            i += 1
    tests = [t for t in TEST_SET if not only or t[0] in only]

    if dry:
        print(f"[dry-run] would run {len(tests)} issues x {len(models)} models (mode={mode}):")
        for typ, prompt in tests:
            for m in models:
                print(f"  {typ:8} {m:30} {AGENT} -p --output-format json --model {m} --mode {mode} \"{prompt[:50]}...\"")
        return

    if not logged_in():
        print("cursor-agent is NOT logged in. Run:  cursor-agent login   (or set CURSOR_API_KEY)")
        sys.exit(2)

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    d = os.path.join(OUTDIR, stamp)
    os.makedirs(d, exist_ok=True)
    rows = []
    for typ, prompt in tests:
        for m in models:
            print(f"running [{typ}] on {m} ...", flush=True)
            res = run_one(m, prompt, mode, timeout)
            safe_m = m.replace("/", "_").replace("[", "_").replace("]", "")
            with open(os.path.join(d, f"{typ}__{safe_m}.json"), "w") as fh:
                fh.write(res["raw"] or res["err"])
            usage = extract_usage(res["raw"])
            row = dict(type=typ, model=m, ok=res["ok"], seconds=res["seconds"], **usage)
            rows.append(row)
            print(f"   ok={res['ok']} {res['seconds']}s usage={usage}")

    keys = sorted({k for r in rows for k in r})
    csvp = os.path.join(d, "summary.csv")
    with open(csvp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\nresults -> {csvp}")


if __name__ == "__main__":
    main()
