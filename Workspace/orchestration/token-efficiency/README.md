# Token-efficiency system

Cut Cursor token spend without losing rigor, and measure it honestly. Go-live:
**2026-07-16**. This folder holds the plan, the measurement scripts, the per-issue
**model router**, the **A/B test harness**, and the weekly reports.

> **Why tokens are spent:** Cursor re-sends the *entire* chat history + attachments on
> **every** turn, so cost grows ~quadratically with chat length. Measured on 138 real
> chats: **93.8% of all historical cost lived in 15–17 mega-chats (400–2,386 turns)**,
> and **~93% of volume is re-sent context, not the AI's answers.** So the levers target
> context re-send, not model verbosity.

---

## 1. Measurement (no per-turn meter exists in Cursor)

Cursor's subscription exposes no token meter, so we use a reproducible proxy:
**visible transcript text ÷ 4 ≈ tokens** (undercounts absolute tokens but tracks the
dominant cost). Scripts (read-only, print to stdout):

| Script | What it reports |
|---|---|
| `scripts/measure-baseline.py` | per-chat est-tokens, before/after go-live, where tokens go (context vs output), largest chats |
| `scripts/efficiency-tiers.py` | classifies every chat into an efficiency tier **1–5** and shows cost-share + tokens/request per tier, before vs after |

```bash
python3 orchestration/token-efficiency/scripts/measure-baseline.py
python3 orchestration/token-efficiency/scripts/efficiency-tiers.py
```

**Efficiency tiers (5 = best):** scored from cumulative re-send per request + chat
length. The win to date: **Tier-1 mega-chats (93.8% of historical cost) → eliminated**;
remaining cost sits in Tier-2/3 (300–500-turn chats), which the checkpoint rule targets.

---

## 2. Per-issue model router (pick the token-efficient model)

`scripts/model-router.py` classifies an issue → **tier** → **model**, per
`.cursor/rules/task-tag-routing.mdc`. Cheapest tier that plausibly fits; complexity
signals (P0/P1, prod failure, intermittent/race, multi-ticket regression) bump it up,
never past the `high` ceiling.

| Task (tag) | Tier | Model (default — verify with `--list-models`) | Use for |
|---|---|---|---|
| `explore` `lookup` `quick` | **fast** | `auto` | reads, explanations, one-shot facts |
| `fix` | **code** | `gpt-5-codex` | focused code generation / small mechanical edits |
| `bug` `review` `pr` | **balanced** | `sonnet-4.5` | debugging, code review, PR writeups (reasoning + tools) |
| `design` `rca` | **high** | `claude-opus-4-8[effort=high]` | architecture / root-cause (the 4.8-high ceiling) |

```bash
python3 orchestration/token-efficiency/scripts/model-router.py "why does styx 500 in prod"
python3 orchestration/token-efficiency/scripts/model-router.py --tag fix "add a nil check"
python3 orchestration/token-efficiency/scripts/model-router.py --selftest
```

**Important limitation:** the interactive Cursor IDE chat cannot switch models via
script/rule/hook — that's the human picker or Cursor "Auto". Programmatic per-issue
routing only works via the **headless CLI/SDK** (below).

---

## 3. A/B test harness (validate the mapping with real tokens)

`scripts/model-ab-test.py` runs a fixed issue set across several models in **read-only
mode** (`--mode ask`, so test runs never edit code), records tokens/cost/time per model
per issue-type, and writes `reports/ab/<timestamp>/summary.csv`.

```bash
# 1) one-time: install + login (login is interactive — only the user can do it)
curl https://cursor.com/install -fsS | bash        # installs cursor-agent
cursor-agent login                                  # or: export CURSOR_API_KEY=...

# 2) confirm the real model ids, then run
cursor-agent --list-models
python3 orchestration/token-efficiency/scripts/model-ab-test.py --dry-run     # preview
python3 orchestration/token-efficiency/scripts/model-ab-test.py --only lookup,fix
python3 orchestration/token-efficiency/scripts/model-ab-test.py               # full set
```

The harness answers empirically: *"for a lookup, is the cheap model actually cheaper
and still correct?"* — and lets us tune `MODEL_MAP` from measured numbers.

---

## 4. CCR compression (shrink big blobs before ingest)

The Headroom **proxy** path is unused on a Cursor subscription (its perf log is always
empty). The real in-Cursor lever is the **CCR MCP tools** `headroom_compress` /
`headroom_retrieve` (see `.cursor/rules/context-compression.mdc`). Route any ≥2k-token
blob (logs, big JSON, dumps, wide search results) through compress before reading;
originals are retrievable by `hash`. Verified: a log blob compressed **20,662 → 294
tokens (~98.6%)**. Note: the MCP server may need a reconnect at session start.

---

## 5. Chat-size checkpoint (cap the re-send blowup)

`.cursor/rules/chat-size-checkpoint.mdc`: at ~150 turns, CCR-compress the accumulated
context, write a `context.md` handoff (retaining all data via hashes), and move to a new
chat that reads only that file. A rule cannot auto-close/open a Cursor chat — it prepares
the handoff and recommends the cut; the user performs the new-chat action.

---

## 6. How it's tested

- `measure-baseline.py` / `efficiency-tiers.py` — run against the live transcript set;
  numbers in the weekly reports are reproduced by re-running them.
- `model-router.py --selftest` — **11/11** labelled issues route to the expected tier.
- `model-ab-test.py --dry-run` — verified command generation; real runs pending
  `cursor-agent login` (auth is interactive).
- CCR — verified end-to-end through the MCP tool (compress returns `tokens_saved` + hash).

Reports: `reports/` (weekly) and `metrics/` (daily raw + CSV). Latest: see
`reports/2026-W30-token-usage.md`.
