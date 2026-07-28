#!/usr/bin/env python3
"""Classify every Cursor chat into an efficiency tier (1..5) and report the
token-usage reduction per tier, before vs after the token-efficiency go-live.

Efficiency is scored from measurable transcript proxies (no per-turn meter exists
in Cursor). The dominant cost is context RE-SENT every turn, so the primary signal
is `resend_per_req` = (sum over turns of cumulative-context-so-far) / user-requests.
Secondary signals: chat length (turns) and visible tokens per request.

Tiers (5 = most efficient, 1 = least):
  5  resend/req <   75k  and turns <  60
  4  resend/req <  300k  and turns < 120
  3  resend/req < 1_000k and turns < 250
  2  resend/req < 4_000k and turns < 500
  1  otherwise (mega-chat / huge re-send)

Read-only. Prints a text report to stdout.
Usage: python3 efficiency-tiers.py [TRANSCRIPTS_DIR]
"""
import os, sys, glob, json, datetime, statistics

DEFAULT_TDIR = os.path.expanduser(
    "~/.cursor/projects/Users-ayush-bhandari-Workspace/agent-transcripts")
GOLIVE = datetime.datetime(2026, 7, 16)


def score(resend_per_req, turns):
    if resend_per_req < 75_000 and turns < 60:
        return 5
    if resend_per_req < 300_000 and turns < 120:
        return 4
    if resend_per_req < 1_000_000 and turns < 250:
        return 3
    if resend_per_req < 4_000_000 and turns < 500:
        return 2
    return 1


def load(tdir):
    rows = []
    for d in glob.glob(os.path.join(tdir, "*")):
        if not os.path.isdir(d):
            continue
        files = glob.glob(os.path.join(d, "*.jsonl"))
        if not files:
            continue
        f = files[0]
        uch = ach = turns = uturns = 0
        per_turn = []
        with open(f) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                turns += 1
                content = o.get("message", {}).get("content", [])
                text = ""
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict):
                            text += b.get("text", "") or ""
                elif isinstance(content, str):
                    text = content
                tok = len(text) // 4
                per_turn.append(tok)
                if o.get("role") == "user":
                    uch += tok
                    uturns += 1
                else:
                    ach += tok
        cum = resend = 0
        for t in per_turn:
            cum += t
            resend += cum
        uturns = uturns or 1
        rows.append(dict(
            date=datetime.datetime.fromtimestamp(os.path.getmtime(f)),
            turns=turns, uturns=uturns, est=uch + ach,
            tok_per_req=(uch + ach) / uturns,
            resend_per_req=resend / uturns,
            tier=score(resend / uturns, turns),
        ))
    return rows


def report(rows):
    before = [r for r in rows if r["date"] < GOLIVE]
    after = [r for r in rows if r["date"] >= GOLIVE]
    print(f"chats: {len(rows)}  before(<{GOLIVE.date()})={len(before)}  after={len(after)}\n")

    hdr = ("tier", "n_before", "n_after", "share%_before", "share%_after",
           "med_tok/req_before", "med_tok/req_after")
    print("Per-tier chat counts and token-cost share (share = % of that group's total est-tokens)")
    print(f"{hdr[0]:>4} {hdr[1]:>9} {hdr[2]:>8} {hdr[3]:>14} {hdr[4]:>13} "
          f"{hdr[5]:>19} {hdr[6]:>18}")
    tb = sum(r["est"] for r in before) or 1
    ta = sum(r["est"] for r in after) or 1
    for tier in [5, 4, 3, 2, 1]:
        b = [r for r in before if r["tier"] == tier]
        a = [r for r in after if r["tier"] == tier]
        sb = sum(r["est"] for r in b)
        sa = sum(r["est"] for r in a)
        mb = statistics.median([r["tok_per_req"] for r in b]) if b else 0
        ma = statistics.median([r["tok_per_req"] for r in a]) if a else 0
        print(f"{tier:>4} {len(b):>9} {len(a):>8} {100*sb/tb:>13.1f}% "
              f"{100*sa/ta:>12.1f}% {mb:>19,.0f} {ma:>18,.0f}")

    print("\nWeighted mean efficiency tier (higher = better; weighted by chats):")
    for nm, rs in [("before", before), ("after", after)]:
        if rs:
            print(f"  {nm}: {statistics.mean([r['tier'] for r in rs]):.2f}  "
                  f"(median tier {statistics.median([r['tier'] for r in rs]):.0f})")

    print("\nToken-cost concentration by tier (where the spend lives):")
    for nm, rs, tot in [("before", before, tb), ("after", after, ta)]:
        low = sum(r["est"] for r in rs if r["tier"] <= 2)
        high = sum(r["est"] for r in rs if r["tier"] >= 4)
        print(f"  {nm}: tier1-2(inefficient)={100*low/tot:>4.0f}% of cost | "
              f"tier4-5(efficient)={100*high/tot:>4.0f}% of cost")

    print("\nHeadline reduction (median visible tokens per request, all chats):")
    mb = statistics.median([r["tok_per_req"] for r in before]) if before else 0
    ma = statistics.median([r["tok_per_req"] for r in after]) if after else 0
    print(f"  before={mb:,.0f} tok/req  ->  after={ma:,.0f} tok/req  "
          f"({100*(1-ma/mb):.0f}% lower)" if mb else "")


if __name__ == "__main__":
    tdir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TDIR
    report(load(tdir))
