# Token-efficiency — current stats (as of 2026-07-28)

> Auto-generated daily by `scripts/token-trend.py` (transcript proxy: chars/4 tokens;
> no LLM, no API cost). History: `metrics/daily-token-stats.csv`.

## Per-request (the money metric)

| | Before (<07-16) | After (all) | Last 7d |
|---|---|---|---|
| Chats | 120 | 18 | 10 |
| Tokens / request | 27,205 | 3,609 | 3,498 |
| Re-send / request | 11,439,041 | 608,846 | 699,130 |
| Max chat turns | 2,386 | 506 | 506 |
| Tier-1 (mega) chats | 16 | 1 | 1 |

**Headline:** ~87% lower tokens/request vs pre-go-live. Tier-1 mega-chats
before=16 -> after=1.

## Compression (CCR) status
- CCR MCP tools (`headroom_compress`/`headroom_retrieve`) are the in-Cursor lever;
  verified working (e.g. a log blob 20,662 -> 294 tokens, ~98.6%).
- The Headroom **proxy** perf log is empty by design on a Cursor subscription, and CCR
  MCP savings are **session-only** (not yet persisted cumulatively) — so there is no
  cumulative "tokens saved by compression" number to report. Per-call savings are
  visible in each `headroom_compress` response (`tokens_saved`).

## Next lever
Max chat turns after go-live = 506 (target: keep < ~150 via
`chat-size-checkpoint`). REGRESSION: a chat re-entered Tier-1.
