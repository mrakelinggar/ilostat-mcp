# Observability

*Learned while building ilostat-mcp. Last updated: 2026-08-29.*

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
INFO: Fetching time series for DEU
INFO: Got 15 rows
```

**Structured JSON logs (production):**
```json
{"event": "get_time_series.complete", "flow_id": "DF_UNE_DEAP_SEX_AGE_RT",
 "country": "DEU", "rows": 15, "duration_ms": 1240, "status": "success"}
```

JSON logs are machine-readable — you can query, filter, and aggregate them.
Plain text logs are grep-only. Use `structlog` in Python for structured logging.

### Traces — how a request flowed

A trace is the complete causal picture of one request through the system.
Each unit of work is a **span** — it has a name, start time, end time,
attributes (inputs/outputs), and status. Spans nest to show hierarchy.

A trace for `labor_market_snapshot("DEU", "FRA")`:
```
labor_market_snapshot               [1.8s total]
├── search_indicators               [320ms]
│   └── ilostat.api.dataflow()      [305ms]
├── get_time_series (DEU)           [1.1s]
│   ├── ilostat.api.data()          [1.08s]
│   └── detect_breaks               [12ms]
├── get_time_series (FRA)           [980ms]
│   └── ilostat.api.data()          [965ms]
└── get_trend                       [9ms]
```

Logs tell you *what* happened. Traces tell you *where time went* and *what
caused what*. When something is slow, the trace immediately shows you which
span is the bottleneck.

The standard for traces is **OpenTelemetry (OTel)** — an open, vendor-neutral
specification. You instrument your code with OTel, and the traces export to
whatever backend you choose.

### Metrics — aggregated numbers over time

Counters and histograms: how many tool calls per minute? What's the p95
latency? What's the error rate? Metrics are for volume — they're only useful
when you have enough traffic to aggregate meaningfully.

**Deferred for this project** — metrics make sense when the MCP is serving
many users. For a local-install tool in v1, logs and traces are sufficient.

---

## What we use in this project

| Pillar | Tool | Why |
|---|---|---|
| Structured logs | `structlog` | Cleaner API than stdlib `logging`, JSON output by default |
| Traces | OpenTelemetry SDK → Honeycomb | OTel is the industry standard; Honeycomb has the best trace UI |
| Metrics | Deferred to future version | No traffic volume to aggregate yet |

**Honeycomb** — free tier, cloud-hosted, no Docker required. The trace
waterfall UI is what you screenshot for the article and README. Recognisable
to engineers at top companies.

OTel exporter is configured to fail silently when offline — the MCP never
breaks because Honeycomb is unreachable.

---

## Where instrumentation lives

- `server.py` — one OTel span per tool call (name, inputs as attributes, duration, outcome)
- `sdmx_client.py` — one OTel span per ILOSTAT API call (flow ID, country, HTTP status, duration)
- Nowhere else — don't scatter OTel code across the codebase

---

## Comparison to LangChain/LangGraph equivalents

| LangChain world | This project |
|---|---|
| LangSmith / LangFuse | Honeycomb |
| LangChain callback system | OpenTelemetry spans |
| LangFuse traces | OTel traces (same concept, different wire format) |

LangFuse actually speaks OTLP (the OpenTelemetry wire protocol), so MCP traces
can also be sent there if you prefer the LangFuse UI. Honeycomb is the choice
here because it's more general-purpose and better known outside the LLM world.

---

## Why this impresses recruiters

Most junior-to-mid engineers can show working code. Showing a Honeycomb trace
waterfall of a real request — with every tool call timed, every ILOSTAT API
call visible, and break detection nested inside `get_time_series` — signals
that you understand production systems, not just code. It's the difference
between "I built a thing" and "I built a thing you could actually run in
production."

---

## Related

- [[testing-disciplines]] — observability is how you debug what testing misses
- [[mcp-fundamentals]] — the system being observed
