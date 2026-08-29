# Observability

*Last updated: 2026-08-29.*

---

## What observability means

Observability is the ability to understand what your system is doing from the
outside — without having to guess or add new code every time something goes
wrong. If something breaks in production at 2am, observability is what lets
you find the cause without re-deploying or reproducing the bug locally.

The analogy: a pilot has instruments (altitude, speed, fuel) that tell them the
state of the plane without opening the engine. Observability gives you the same
visibility into running software.

---

## The three pillars

### Logs — what happened

A sequential record of events. Every significant thing the system does writes
a log line. Good for: "what happened, in what order?"

**Plain text logs (junior):**
```
INFO: Fetching order for user 42
INFO: Got 3 items
```

**Structured JSON logs (production):**
```json
{"event": "fetch_order.complete", "user_id": 42, "item_count": 3,
 "duration_ms": 84, "status": "success"}
```

JSON logs are machine-readable — you can query, filter, and aggregate them.
Plain text logs are grep-only. Use `structlog` in Python for structured logging.

### Traces — how a request flowed

A trace is the complete causal picture of one request through the system.
Each unit of work is a **span** — it has a name, start time, end time,
attributes (inputs/outputs), and status. Spans nest to show hierarchy.

Example trace for a `place_order(user_id, items)` request:
```
place_order                         [310ms total]
├── validate_user                   [12ms]
│   └── db.users.lookup             [10ms]
├── check_inventory                 [180ms]
│   └── inventory.api.check         [175ms]
├── charge_payment                  [95ms]
│   └── payment.api.charge          [92ms]
└── send_confirmation_email         [23ms]
```

Logs tell you *what* happened. Traces tell you *where time went* and *what
caused what*. When something is slow, the trace immediately shows you which
span is the bottleneck. When something fails, the trace shows exactly where
in the chain it broke.

The standard for traces is **OpenTelemetry (OTel)** — an open, vendor-neutral
specification. You instrument your code with OTel, and the traces export to
whatever backend you choose.

### Metrics — aggregated numbers over time

Counters and histograms: how many requests per minute? What's the p95 latency?
What's the error rate? Metrics are for volume — they're only useful when you
have enough traffic to aggregate meaningfully. Start with logs and traces; add
metrics when you have real traffic to measure.

---

## Recommended stack

| Pillar | Tool | Why |
|---|---|---|
| Structured logs | `structlog` | Cleaner API than stdlib `logging`, JSON output by default |
| Traces | OpenTelemetry SDK → Honeycomb | OTel is the vendor-neutral industry standard; Honeycomb has the best trace UI |
| Metrics | Add when you have traffic | Prometheus + Grafana for self-hosted; Datadog/Honeycomb for managed |

**Honeycomb** — free tier, cloud-hosted, no Docker required. The trace
waterfall UI is what you screenshot for portfolios, articles, and post-mortems.
Recognisable to engineers at top companies.

Configure the OTel exporter to fail silently when offline — the app should
never break because a telemetry backend is unreachable.

---

## Where instrumentation belongs

- **Entry points** (API handlers, tool functions, queue consumers) — one span per request
- **External calls** (database queries, third-party API calls) — one span per call, nested inside the entry span
- **Nowhere else** — don't scatter OTel code across business logic

This keeps traces readable. If you instrument too granularly, the waterfall
becomes noise.

---

## Comparison to LangChain/LangGraph equivalents

| LangChain world | General equivalent |
|---|---|
| LangSmith / LangFuse | Honeycomb, Jaeger, or any OTel backend |
| LangChain callback system | OpenTelemetry spans |
| LangFuse traces | OTel traces (same concept, different wire format) |

LangFuse speaks OTLP (the OpenTelemetry wire protocol) natively, so any OTel-
instrumented app can send traces there. Honeycomb is the better general-purpose
choice — it's not LLM-specific and is well-known across the industry.

---

## Why observability separates junior from senior

Most junior-to-mid engineers can show working code. A senior engineer also
shows you they can *see* what the code is doing in production — a Honeycomb
trace waterfall, a structured log query that pinpoints a slow dependency, a
dashboard that caught an issue before users noticed. That's the difference
between "I built a thing" and "I built a thing you could actually run and
maintain in production."

---

## Related

- [[testing-disciplines]] — observability is how you debug what testing misses
- [[cicd-github-actions]] — CI runs before code ships; observability watches after
