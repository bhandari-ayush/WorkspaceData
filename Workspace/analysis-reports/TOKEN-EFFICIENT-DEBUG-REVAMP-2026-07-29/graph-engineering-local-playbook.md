# Graph Engineering Local Playbook

## What it is
Graph engineering is designing a multi-node execution graph (planner, worker, reviewer, synthesizer, gates) instead of one long free-form prompt. It is useful when tasks require role specialization, explicit routing, and auditable checkpoints.

## When to use vs skip

Use graph flow when:
- work spans multiple specialties (code + tests + security + docs),
- you need parallel reviews and merge of results,
- you need deterministic pass/fail gates before side effects.

Skip graph flow when:
- one constrained loop can finish safely,
- no independent verification is needed,
- task is simple lookup/single edit.

## Local graph template (practical)

```
Task -> Planner -> Worker -> Reviewers (parallel) -> Synthesize -> Pass Gate
  -> (fail) feedback loop to Worker (bounded retries)
  -> (pass) actionable output -> Plan Reviewer -> User
```

## Node specs (minimal)

- Planner
  - input: goal, scope, constraints
  - output: ordered plan, acceptance criteria, risk list
- Worker
  - input: one scoped plan item
  - output: artifact diff + evidence
- Reviewer(s)
  - input: artifact + acceptance criteria
  - output: structured verdict (`PASS|PARTIAL|FAIL|BLOCKED`) + exact findings
- Synthesize
  - input: reviewer verdicts
  - output: merged verdict + ranked fixes
- Plan Reviewer
  - input: final package
  - output: ready-to-send summary

## Required prerequisites (efficient operation)

1. **Typed shared state**
   - must include `goal`, `scope`, `constraints`, `acceptance_criteria`, `artifacts`, `verdict`.
2. **Structured router outputs**
   - avoid free-text routing; route on fixed enum values.
3. **Revision caps**
   - set `max_revisions` and global recursion limit.
4. **Separation of concerns**
   - side-effect nodes (commit/push/deploy) must be gated and explicit.
5. **Observability**
   - record node duration, request count, failure rate, retry count.
6. **Human gate for risky actions**
   - require explicit approval before irreversible mutations.

## How it is initiated (input contract)

Use this template:

```text
Task: <one line>
Mode: planning | execution | bug
Scope: <repos/files/services>
Acceptance criteria: <3-7 bullets>
Constraints: <token/request/time/risk>
Resources: <files/links/logs/ids>
Allowed side effects: <none|commit|push|deploy>
```

## Bug-mode rule

For token efficiency, run graph bug flow only when explicitly requested with:
- `bug:`
- `[bug]`
- `rca:`

Otherwise use normal direct flow.

## What user should feed for better results

- one objective line,
- exact artifact paths,
- 3-5 decisive evidence lines (ids/errors),
- clear done criteria,
- explicit side-effect permission.

## Reference links
- [Graph Engineering Guide (2026)](https://www.aibuilderclub.com/blog/graph-engineering-guide-2026)
- [Graph Engineering Explained](https://www.louisbouchard.ai/graph-engineering-explained/)
- [Graph-Centric Orchestration](https://handbook.reopt.ai/en/books/vercel-enterprise-ai-platform/graph-centric-orchestration)
- [LangGraph Multi-Agent Tutorial](https://dev.to/sidkul2000/production-ready-multi-agent-systems-with-langgraph-a-complete-tutorial-20k8)
- [Agent Orchestration (Dataiku)](https://www.dataiku.com/blog/agent-orchestration-explained)
