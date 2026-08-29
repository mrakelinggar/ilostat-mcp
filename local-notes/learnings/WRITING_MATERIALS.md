# Writing Materials

Article ideas worth writing — each grounded in a real technical decision or
finding from an actual implementation, not synthesised opinion. Target audience
is practitioners: senior engineers and data scientists who will recognise the
problem immediately and care about the decision behind the solution.

Updated as ideas surface each session. Ideas marked ✅ are drafted/published.

---

## From ilostat-mcp (2026-08-29)

### 1. "Why your AI agent lies — and how methodology-break detection fixes it"

**The hook:** most people writing about LLMs and data tools don't know that
the data itself has breaks — survey sources change mid-series and numbers stop
being comparable. A bare LLM hallucinates a clean trend across a methodology
break. A tool-equipped agent with break detection flags it explicitly.

**What makes it substantive:**
- Concrete, reproducible demonstration: Nigeria employment data, 2019 SOURCE
  change, bare Claude vs MCP-equipped Claude
- Benchmark numbers (fabrication rate, break-blindness rate) as evidence, not
  anecdote
- The specific mechanism: SOURCE attribute diff in SDMX, not a vague "data
  quality" concern

**Where it fits:** after the benchmark is run and results are in (Phase 5).
This is the flagship article — write it last, get the numbers right.

---

### 2. "The hallucination benchmark nobody runs"

**The hook:** most AI benchmark articles test model capability in isolation.
This tests tool-equipped agent correctness on real-world data questions —
with verified ground truth, six failure categories, and three conditions that
isolate the contribution of different features.

**What makes it substantive:**
- The benchmark design itself: why six categories, what `mcp_no_breakcheck`
  isolates that `mcp_full` doesn't, why ground truth must be pulled by hand
- The methodology is publishable independently of the results
- Rare: almost no rigorous evaluation of MCP server correctness exists

**Where it fits:** can be written before results are in — the methodology
article doesn't need final numbers, though results make it stronger.

---

### 3. "MCP error handling is an afterthought — here's how to do it properly"

**The hook:** every MCP tutorial shows the happy path. None of them design
an error contract. When your tool returns `[]` for both "no data" and "API
is down", the agent can't tell the difference and will give the user a wrong
answer.

**What makes it substantive:**
- The taxonomy: infrastructure failures vs user input errors vs legitimate
  empty results — three different things that most implementations conflate
- The principle: error messages are written for Claude to relay, not for a
  Python developer reading logs
- Concrete patterns: when to raise vs when to return a structured error field,
  why silent swallowing is a correctness bug not a style issue
- The timeout problem: a hung request is worse than a failed one

**Where it fits:** can be written after Phase 2b (error handling is implemented
and verified). Fastest to write — the design decisions are already documented.

---

### 4. "What CI/CD actually looks like for an AI tool library"

**The hook:** not another intro to GitHub Actions. The specific decisions that
practitioners face and tutorials skip: why split quality and test jobs, why
live API tests beat mocks, PyPI Trusted Publishing vs stored tokens, the
Cloudflare-on-shared-runners problem.

**What makes it substantive:**
- Every decision has a reason, not just "this is how you do it"
- The live-vs-mock testing debate applied to a real case: mocks hide Cloudflare
  behaviour, rate limiting, and API shape changes
- PyPI Trusted Publishing (OIDC) — most tutorials still use stored API tokens;
  this is the modern standard
- The Cloudflare/shared-IP problem is a real gotcha that nobody writes about

**Where it fits:** after Phase 1.5 (CI/CD set up and verified).

---

### 5. "Observability for MCP servers — logs, traces, and what LangSmith gets wrong"

**The hook:** almost nothing is written about observability specifically for
MCP servers. The LLM tooling world defaults to LangSmith/LangFuse, but OTel +
Honeycomb is the more general, more powerful, more transferable choice.

**What makes it substantive:**
- The trace waterfall: a prompt triggering nested tool and API spans, showing
  exactly where time goes and where failures occur
- The three pillars applied to MCP specifically: what to log at tool level vs
  API level vs benchmark level
- The LangSmith comparison: what it does well (LLM-native), what it misses
  (general distributed tracing), and why OTel is the right foundation
- `structlog` vs stdlib `logging` — a concrete, practical comparison

**Where it fits:** after Phase 4.5 (observability implemented and screenshots
taken from Honeycomb).

---

## Rules for adding new ideas

- Must be grounded in a real decision or finding — not "here's a concept I read about"
- Must have a clear practitioner hook: what problem does this solve that
  someone will recognise from their own work?
- Note which phase it can be written after — ideas are only as good as the
  implementation behind them
- One idea per section, enough detail to reconstruct the angle cold
