#!/usr/bin/env python3
"""Daily token-efficiency trend from Cursor transcripts (free, no LLM, no API cost).

Appends one dated row to metrics/daily-token-stats.csv and rewrites metrics/CURRENT-STATS.md
with the current before/after picture (per-request tokens, re-send/request, tier mix,
max chat length, CCR status). Meant to run daily from token-metrics.sh / launchd.

Usage: python3 token-trend.py            # snapshot today
Read-only against transcripts; only writes under metrics/.
"""
import os, glob, json, datetime, statistics, csv

TDIR = os.path.expanduser("~/.cursor/projects/Users-ayush-bhandari-Workspace/agent-transcripts")
MET = os.path.expanduser("~/Workspace/orchestration/token-efficiency/metrics")
CSV = os.path.join(MET, "daily-token-stats.csv")
MD = os.path.join(MET, "CURRENT-STATS.md")
GOLIVE = datetime.datetime(2026, 7, 16)


def load():
    rows = []
    for d in glob.glob(os.path.join(TDIR, "*")):
        if not os.path.isdir(d):
            continue
        fs = glob.glob(os.path.join(d, "*.jsonl"))
        if not fs:
            continue
        uch = ach = turns = ut = 0
        per = []
        with open(fs[0]) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                turns += 1
                c = o.get("message", {}).get("content", [])
                t = ""
                if isinstance(c, list):
                    for b in c:
                        if isinstance(b, dict):
                            t += b.get("text", "") or ""
                elif isinstance(c, str):
                    t = c
                tok = len(t) // 4
                per.append(tok)
                if o.get("role") == "user":
                    uch += tok; ut += 1
                else:
                    ach += tok
        cum = rs = 0
        for t in per:
            cum += t; rs += cum
        rows.append(dict(date=datetime.datetime.fromtimestamp(os.path.getmtime(fs[0])),
                         turns=turns, ut=max(ut, 1), uch=uch, ach=ach,
                         est=uch + ach, resend=rs))
    return rows


def tier(resend_per_req, turns):
    if resend_per_req < 75_000 and turns < 60:
        return 5
    if resend_per_req < 300_000 and turns < 120:
        return 4
    if resend_per_req < 1_000_000 and turns < 250:
        return 3
    if resend_per_req < 4_000_000 and turns < 500:
        return 2
    return 1


def metrics(rows, sel):
    if not sel:
        return dict(chats=0, tok_per_req=0, resend_per_req=0, max_turns=0, tier1=0)
    ut = sum(r["ut"] for r in sel)
    return dict(
        chats=len(sel),
        tok_per_req=round(sum(r["est"] for r in sel) / ut),
        resend_per_req=round(sum(r["resend"] for r in sel) / ut),
        max_turns=max(r["turns"] for r in sel),
        tier1=sum(1 for r in sel if tier(r["resend"] / r["ut"], r["turns"]) == 1),
    )


def main():
    os.makedirs(MET, exist_ok=True)
    rows = load()
    today = datetime.datetime.now()
    before = [r for r in rows if r["date"] < GOLIVE]
    after = [r for r in rows if r["date"] >= GOLIVE]
    last7 = [r for r in rows if r["date"] >= today - datetime.timedelta(days=7)]
    b, a, l = metrics(rows, before), metrics(rows, after), metrics(rows, last7)
    d = today.strftime("%Y-%m-%d")

    hdr = ["date", "total_chats", "after_chats", "after_tok_per_req",
           "after_resend_per_req", "after_max_turns", "after_tier1",
           "last7_chats", "last7_tok_per_req", "last7_resend_per_req", "last7_max_turns"]
    new = [d, len(rows), a["chats"], a["tok_per_req"], a["resend_per_req"],
           a["max_turns"], a["tier1"], l["chats"], l["tok_per_req"],
           l["resend_per_req"], l["max_turns"]]
    existing = []
    if os.path.exists(CSV):
        with open(CSV) as fh:
            existing = [row for row in csv.reader(fh) if row and row[0] not in ("date", d)]
    with open(CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(hdr)
        for row in existing:
            w.writerow(row)
        w.writerow(new)

    red = (100 * (1 - a["tok_per_req"] / b["tok_per_req"])) if b["tok_per_req"] else 0
    with open(MD, "w") as fh:
        fh.write(f"""# Token-efficiency — current stats (as of {d})

> Auto-generated daily by `scripts/token-trend.py` (transcript proxy: chars/4 tokens;
> no LLM, no API cost). History: `metrics/daily-token-stats.csv`.

## Per-request (the money metric)

| | Before (<07-16) | After (all) | Last 7d |
|---|---|---|---|
| Chats | {metrics(rows, before)['chats']} | {a['chats']} | {l['chats']} |
| Tokens / request | {b['tok_per_req']:,} | {a['tok_per_req']:,} | {l['tok_per_req']:,} |
| Re-send / request | {b['resend_per_req']:,} | {a['resend_per_req']:,} | {l['resend_per_req']:,} |
| Max chat turns | {b['max_turns']:,} | {a['max_turns']:,} | {l['max_turns']:,} |
| Tier-1 (mega) chats | {b['tier1']} | {a['tier1']} | {l['tier1']} |

**Headline:** ~{red:.0f}% lower tokens/request vs pre-go-live. Tier-1 mega-chats
before={b['tier1']} -> after={a['tier1']}.

## Compression (CCR) status
- CCR MCP tools (`headroom_compress`/`headroom_retrieve`) are the in-Cursor lever;
  verified working (e.g. a log blob 20,662 -> 294 tokens, ~98.6%).
- The Headroom **proxy** perf log is empty by design on a Cursor subscription, and CCR
  MCP savings are **session-only** (not yet persisted cumulatively) — so there is no
  cumulative "tokens saved by compression" number to report. Per-call savings are
  visible in each `headroom_compress` response (`tokens_saved`).

## Next lever
Max chat turns after go-live = {a['max_turns']} (target: keep < ~150 via
`chat-size-checkpoint`). {"REGRESSION: a chat re-entered Tier-1." if a['tier1'] else "No Tier-1 chats — good."}
""")
    print(f"[token-trend] {d}: after tok/req={a['tok_per_req']:,} resend/req={a['resend_per_req']:,} "
          f"max_turns={a['max_turns']} tier1={a['tier1']}  -> {CSV}")


if __name__ == "__main__":
    main()
