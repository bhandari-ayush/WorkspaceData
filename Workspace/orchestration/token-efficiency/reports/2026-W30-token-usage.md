# Token-usage report — first full week after token-efficiency go-live

Owner: ayush.bhandari · Generated: 2026-07-27 · Window: **2026-07-20 → 2026-07-26** (W30)
Go-live of the token-efficiency system: **2026-07-16**.

> **Measurement caveat (honest):** Cursor's subscription exposes **no per-turn token
> meter**, and the Headroom *proxy* perf log is structurally empty on a subscription
> (Cursor traffic never flows through the proxy — see §5). The one reproducible proxy
> is **visible transcript text ÷ 4 ≈ tokens**, measured live from 135 chat transcripts.
> It undercounts absolute tokens (excludes tool-call/result bodies) but consistently
> captures the dominant cost: **context re-sent on every turn**.
> Reproduce: `python3 orchestration/token-efficiency/scripts/measure-baseline.py`
> and `python3 orchestration/token-efficiency/scripts/efficiency-tiers.py`.

---

## 1. Headline

| Metric | Before (<07-16, 120 chats) | Last week (07-20→26, 8 chats) | Change |
|---|---|---|---|
| Mean visible tokens / chat | ~545,290 | ~47,215 | **~91% lower** |
| Largest single chat | ~23,971,243 | 126,249 | **~99% lower** |
| Longest chat | 2,386 turns | 395 turns | **~83% lower** |

The mega-chats (400–2,386 turns) that drove **93.8% of all historical token cost**
have been eliminated. That is the win.

## 2. Per-request metrics (the new ask)

| Per user request | Before (<07-16) | Last week | Drop |
|---|---|---|---|
| **A. Visible tokens / request** | 27,239 | 3,316 | **~88%** |
| **B. Context re-sent / request** (true $ driver) | 11,453,328 | 497,054 | **~96%** |

Metric B is the truest cost proxy: every turn re-sends the whole prior chat, so cost
grows ~quadratically with chat length. Keeping chats scoped collapsed it ~96%.

## 3. Where the saving happened (by workflow stage)

Splitting visible volume into **context-build / re-send** (pasted files + resent
history) vs **analysis + output** (the assistant's own reasoning/writeups):

```
Stage mix — BEFORE
context-build / re-sent  ##############################  94%   <- all the waste was here
analysis + output        ##                               6%

Stage mix — LAST WEEK
context-build / re-sent  ###                              9%
analysis + output        ###########################     91%   <- now mostly real work
```

| Stage | Before / request | Last week / request | Effect |
|---|---|---|---|
| Context-build & re-send | ~25,471 tok | ~294 tok | **~99% cut** — win is almost entirely here |
| Analysis + output | ~1,769 tok | ~3,022 tok | intact / +71% — thinking kept, even deepened |

The reduction did **not** come from the AI analyzing less; it came from cutting the
context-build/re-send stage.

## 4. Efficiency tiers (1 = worst, 5 = best) and reduction per tier

Each chat scored 1–5 from measurable proxies (primary: cumulative re-send per
request; secondary: chat length). Rubric in `scripts/efficiency-tiers.py`.

| Tier | # chats before | # chats after | % of cost before | % of cost after | med tok/req before | med tok/req after |
|---|---|---|---|---|---|---|
| 5 (best) | 34 | 5 | 0.3% | 4.6% | 2,315 | 3,058 |
| 4 | 34 | 2 | 1.0% | 7.6% | 4,185 | 3,505 |
| 3 | 24 | 4 | 1.3% | 24.6% | 4,295 | 4,660 |
| 2 | 12 | 4 | 3.6% | 63.2% | 4,831 | 3,216 |
| 1 (worst) | 16 | **0** | **93.8%** | **0.0%** | 17,176 | — |

**Reduction per tier — the story:**

- **Tier 1 (mega/inefficient chats): 16 → 0. The single biggest reduction.** These
  were **93.8% of all historical token cost** (~17,176 tok/request each). Fully
  eliminated — no chat last week landed in tier 1 or 2's catastrophic range.
- **Tier 1–2 cost share: 97% → 63%.** Inefficient chats no longer dominate, but a
  chunk of the *remaining* cost still sits in tier-2/3 (250–500-turn chats). This is
  the next target (see §6).
- **Tier 4–5 cost share: 1% → 12%.** Efficient chats now carry more of the (much
  smaller) total — but there is still headroom to push mass into tiers 4–5.

Weighted-mean tier barely moved (3.48 → 3.53) because it counts chats equally; the
real change is in the **cost-weighted** view above — the expensive tier-1 mass is gone.

## 5. CCR compression — status: NOW LIVE (was 0 uses)

- The Headroom **proxy** path (whole-traffic, auto-compress) is unused on a Cursor
  subscription and its perf log is permanently empty — that is why every
  `metrics/raw/*.stats.txt` says *"No performance data found."* Not a bug; wrong pipe.
- The **CCR MCP tools** (`headroom_compress` / `headroom_retrieve`) are the real
  in-Cursor lever. They were failing discovery (stale MCP connection); reconnected on
  2026-07-27 → `serverStatus: ready`. Verified end-to-end:
  - repetitive log blob: **20,662 → 294 tokens (~98.6% saved)**
  - mixed log blob (kept the decisive ERROR line): **552 → 311 tokens (~44% saved)**
- Savings are reported **in each compress call's response** (`original_tokens`,
  `compressed_tokens`, `tokens_saved`, `hash`) — so we self-measure CCR from the tool,
  not from the always-empty proxy perf. (TODO: rewire the daily capture to log this.)

## 6. Further steps to cut per-request tokens (prioritized to current profile)

1. **Cap chat length + checkpoint-handoff** (biggest remaining lever): at ~150 turns,
   compress context to `analysis-reports/<TICKET>/context.md` and start a fresh chat.
   Splitting a 400-turn chat ~4-ways cuts its cumulative re-send ~75%.
2. **Tighten assistant output** (now 91% of visible volume): stop re-printing big
   tables/dumps each turn; quote only decisive lines. Compounds via re-send.
3. **Use CCR routinely** (now live): route any ≥2k-token blob through
   `headroom_compress` before ingest.
4. **Prune auto-attached context**: close unused editors / large open files re-sent
   every turn.
5. **Build repo maps** (`gitingest` fallback, Node<18) to cut discovery reads.
6. **Model routing**: cheaper tiers for `explore:/lookup:/fix:`, reserve 4.8-high for
   `design:/rca:` (see feasibility note — IDE cannot auto-switch the model per manual
   chat; use Cursor "Auto" model mode, or the Cursor SDK for automated sessions).

Diminishing returns: ranged-reads (Iter 1) and precise-MCP (Iter 3) are already
working — context-build is only ~9% of last week's volume.
