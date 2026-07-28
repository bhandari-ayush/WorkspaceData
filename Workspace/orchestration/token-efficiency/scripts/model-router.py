#!/usr/bin/env python3
"""Per-issue model router + classifier (token-efficiency).

Given an issue/prompt (and optional explicit tag), decide the cheapest model TIER
that plausibly fits, per .cursor/rules/task-tag-routing.mdc. This is the "identify
which model to use" step. Actually *using* that model requires the headless Cursor
CLI/SDK (see route_cmd / --run); the interactive IDE cannot switch models via script.

Tiers (cheapest first): fast < balanced < high(4.8-high ceiling).

Usage:
  python3 model-router.py "why does the styx build fail intermittently in CI"
  python3 model-router.py --tag rca "ENG-960206 project usage 500s in prod"
  python3 model-router.py --selftest         # run the built-in test set
  python3 model-router.py --run "..."        # print the cursor-agent command to run

Model names are placeholders in MODEL_MAP — set them to the exact model ids available
on your Cursor account before using --run.
"""
import sys, re, json

# tier -> concrete model id. VERIFY/ADJUST against `cursor-agent --list-models`
# (ids below match Cursor's naming convention; --list-models is the source of truth).
MODEL_MAP = {
    "fast":     "auto",                          # cheap/low-latency: reads, explains, short Q&A
    "code":     "gpt-5-codex",                   # focused code generation / small mechanical edits
    "balanced": "sonnet-4.5",                    # day-to-day bug/debug/review/PR (reasoning + tools)
    "high":     "claude-opus-4-8[effort=high]",  # 4.8-high ceiling: design / RCA only
}
BUDGET = {"fast": "<=2 reads", "code": "<=6 reads + 1 test",
          "balanced": "<=8-12 reads", "high": "large"}

# task tag -> tier
TAG_TIER = {
    "explore": "fast", "lookup": "fast", "quick": "fast",
    "fix": "code",
    "bug": "balanced", "review": "balanced", "pr": "balanced",
    "design": "high", "rca": "high",
}
# escalation order (cheap -> expensive); complexity signals bump UP this ladder.
ORDER = ["fast", "code", "balanced", "high"]


def _bump(tier, to):
    return to if ORDER.index(to) > ORDER.index(tier) else tier


def classify(text, tag=None):
    t = (text or "").lower().strip()
    reasons = []

    # 1) explicit tag wins the base tier
    if not tag:
        m = re.match(r"\s*(\w+)\s*:", t)
        if m and m.group(1) in TAG_TIER:
            tag = m.group(1)
    if tag and tag.lower() in TAG_TIER:
        tier = TAG_TIER[tag.lower()]
        reasons.append(f"explicit tag '{tag}' -> {tier}")
    else:
        # 2) infer from keywords
        tier = "balanced"
        if re.search(r"\b(design|architect|architecture|trade-?off|approach|refactor|migrat|scalab)", t):
            tier = "high"; reasons.append("design/architecture keyword -> high")
        elif re.search(r"\b(rca|root[ -]?cause|postmortem|post-mortem)\b", t):
            tier = "high"; reasons.append("rca keyword -> high")
        elif re.search(r"\b(why|fail|failing|error|crash|broken|not working|debug|stack ?trace|traceback|panic)\b", t):
            tier = "balanced"; reasons.append("bug/why keyword -> balanced")
        elif re.search(r"\b(fix|add|update|rename|bump|tweak|small change|typo|comment|implement)\b", t):
            tier = "code"; reasons.append("small-change/codegen keyword -> code (codex)")
        elif re.search(r"\b(what|where|which|explain|understand|show|find|list|how do i|meaning of)\b", t) or len(t) < 60:
            tier = "fast"; reasons.append("lookup/explore keyword or short -> fast")
        else:
            reasons.append("no strong signal -> default balanced")

    # 3) complexity signals bump the tier UP (never past 'high')
    if re.search(r"\b(p0|p1|critical|sev1|sev-1)\b", t):
        tier = _bump(tier, "high"); reasons.append("P0/P1/critical -> bump high")
    if re.search(r"\b(prod|production|customer|field)\b", t) and re.search(r"\b(fail|down|500|error|incident|why)\b", t):
        tier = _bump(tier, "high"); reasons.append("prod/customer failure -> bump high")
    if re.search(r"\b(intermittent|race|flaky|non-deterministic|heisenbug)\b", t):
        tier = _bump(tier, "high"); reasons.append("intermittent/race -> bump high")
    multi_ticket = len(re.findall(r"\b[A-Z]{2,}-\d+\b", text or "")) >= 2
    if multi_ticket and re.search(r"\b(regress|regression|broke|broken|after the|bump|cross-repo)\b", t):
        tier = _bump(tier, "high"); reasons.append("multi-ticket regression -> bump high")
    elif multi_ticket:
        tier = _bump(tier, "balanced"); reasons.append(">=2 tickets -> at least balanced")
    if len(t) > 1500:
        tier = _bump(tier, "balanced"); reasons.append("long prompt -> at least balanced")

    return tier, reasons


def decide(text, tag=None):
    tier, reasons = classify(text, tag)
    return {"tier": tier, "model": MODEL_MAP[tier], "budget": BUDGET[tier], "reasons": reasons}


SELFTEST = [
    ("what does getCwd do in this file", None, "fast"),
    ("lookup: current branch name", None, "fast"),
    ("fix the null check in projects_uuid_usage.py", None, "code"),
    ("why does the styx build fail in CI", None, "balanced"),
    ("why does the styx build fail intermittently in CI on prod", None, "high"),
    ("design a caching layer for project usage rollups", None, "high"),
    ("rca: ENG-960206 project usage returns 500 in production for customer", None, "high"),
    ("add a comment to calculateTotal", None, "code"),
    ("ENG-100 and ENG-200 both regressed after the gamma-libs bump, why", None, "high"),
    ("explain the environment_helper flow", None, "fast"),
    ("P1: apps stuck in provisioning", None, "high"),
]


def selftest():
    ok = 0
    for text, tag, exp in SELFTEST:
        got = decide(text, tag)["tier"]
        mark = "OK " if got == exp else "XX "
        ok += got == exp
        print(f"  {mark} exp={exp:<8} got={got:<8} | {text[:60]}")
    print(f"\n  {ok}/{len(SELFTEST)} correct")
    return ok == len(SELFTEST)


def main():
    args = sys.argv[1:]
    if not args or args[0] == "--selftest":
        print("model-router self-test:"); sys.exit(0 if selftest() else 1)
    tag = None; run = False
    while args and args[0].startswith("--"):
        if args[0] == "--tag":
            tag = args[1]; args = args[2:]
        elif args[0] == "--run":
            run = True; args = args[1:]
        else:
            args = args[1:]
    text = " ".join(args)
    d = decide(text, tag)
    print(json.dumps(d, indent=2))
    if run:
        # the headless invocation (requires `cursor-agent` installed + logged in)
        prompt = text.replace('"', '\\"')
        print("\n# to actually run this issue on the chosen model:")
        print(f'cursor-agent -m {d["model"]} -p "{prompt}" --output-format json')


if __name__ == "__main__":
    main()
