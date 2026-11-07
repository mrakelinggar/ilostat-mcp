# Caching Fundamentals

*Last updated: 2026-11-07.*

---

## What a cache is

A cache keeps the answer to an expensive request so the next identical request
can skip the work. It trades memory (and the risk of an out-of-date answer)
for speed. It only pays off when the same thing is asked for more than once.

---

## Measure first

Before caching, time each step. In a typical "fetch a list, then filter it"
call, the download can take seconds while the filtering takes a millisecond.
Caching the download is then worth almost everything; optimising the filter
is worth nothing. Measuring also stops you "optimising" things that are
already done — compression and connection reuse are often on by default.

---

## Key on the thing, not the question

The cache key decides how often you get a hit.

- **Bad:** key on the exact request, e.g. `(country, start_year, end_year)`.
  "2015–2020" and "2016–2020" become separate entries and almost nothing is
  reused.
- **Good:** fetch the whole underlying object once — e.g. a country's full
  history — key on `(dataset, country)`, and cut out the requested years
  locally. Every question about that series now hits the same entry.

If inputs are validated against a fixed allowlist, the number of possible keys
is capped (datasets × countries × options), however specific users get.

---

## Keeping it fresh

A cached answer can go stale when the source changes. Two tools:

- **Time limit (TTL):** an entry expires after, say, 24 hours. Simple; the worst
  case is "one TTL out of date". Pick the TTL from how often the source really
  changes, not from a guess.
- **Version in the key:** if the source publishes a "last updated" timestamp,
  put it in the key. When the timestamp changes, old entries are simply never
  looked up again. This gives freshness without frequent re-downloads.

Combining them is common: version keys for correctness, a TTL as a backstop.

---

## Bounding memory

An unbounded cache in a long-running server grows until something breaks.
An **LRU** (least-recently-used) cache has a maximum size and evicts the entry
that has gone longest without use. Memory becomes a hard number (entries ×
size per entry) regardless of traffic.

---

## Where the cache lives

- **In-process memory** (a dict in the server): simplest, fastest, lost on
  restart, and not shared between processes or machines.
- **Shared store** (e.g. Redis): shared across machines, survives restarts,
  but adds a service to run. Worth it only when hit rate across machines matters.

More users on one process do not grow a bounded cache — they increase the hit
rate. A cache also protects the upstream service: a thousand users asking for
the same thing becomes one upstream request instead of a thousand, which keeps
you clear of rate limits.

---

## Pitfalls

- **Caching failures.** If a fetch fails, store nothing, so the next call
  retries. Caching an error or an empty result can break a feature until restart.
- **Negative results.** "No data" is worth caching, but with a shorter TTL, so a
  wrong "nothing here" cannot stick around.
- **Thread safety.** If requests run in parallel threads, an LRU cache changes
  its internal order on every *read*. Guard it with a lock.
- **Simultaneous misses.** Several requests for the same missing key at once
  all fetch it. Usually harmless; a per-key lock fixes it if it matters.
- **Test isolation.** Module-level caches leak between tests. Add a fixture that
  clears them.
- **Benchmarks.** Warm-cache runs are faster. Say whether timings started cold.
