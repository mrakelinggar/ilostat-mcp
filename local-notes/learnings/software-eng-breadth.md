# Software Engineering — It's More Than Coding

*Learned while building ilostat-mcp. Last updated: 2026-08-29.*

---

## The honest map of the job

Programming is the entry ticket. Everything else is the actual job.

### Technical domains

**Data structures & algorithms** — the foundation under the code. Knowing
when a dict lookup is O(1) and a list scan is O(n) changes how you design
things.

**System design** — how to architect something that scales, doesn't fall over,
and can be maintained by 10 people two years from now. This is what senior
interviews are really testing.

**Networking** — HTTP, TCP/IP, DNS, latency, load balancers, CDNs. You can't
build distributed systems without this. Most bugs in production are network bugs.

**Databases** — not just SQL. Indexing, query optimisation, transactions,
consistency, replication, when to use NoSQL vs relational.

**Security** — authentication, authorisation, encryption, injection attacks,
dependency vulnerabilities. Every engineer is responsible for not shipping
exploitable code. Security is not a separate team's job.

**Operating systems** — processes, threads, memory, file systems, how the
code you write actually runs on hardware.

**Cloud & infrastructure** — AWS/GCP/Azure, containers (Docker), orchestration
(Kubernetes), serverless, CI/CD pipelines. You need to know how your code
gets from your machine to production.

**Observability** — logging, monitoring, alerting, tracing. If you can't see
what your system is doing in production, you're flying blind.
See [[observability]].

**Testing** — functional, edge case, resilience, regression. See
[[testing-disciplines]].

### Non-technical skills

**Communication** — writing clear specs, docs, PR descriptions, incident reports.
Bad writing costs teams hours of confusion. A 10-minute write-up can prevent
a 2-hour meeting.

**Estimation** — how long will this take? Consistently the hardest skill. Most
engineers are bad at it for years. The fix is decomposing tasks smaller until
each piece is estimable.

**Debugging mindset** — systematic reasoning under pressure. The ability to
stay calm and methodical when production is on fire at 2am. Panic narrows
thinking; methodical beats fast.

**Reading other people's code** — you spend more time reading code than writing
it. Most of it is code you didn't write. The ability to build a mental model
of unfamiliar code quickly is underrated.

**Saying no** — knowing when a request adds complexity without value, and
being able to articulate why without being dismissive. Scope creep kills
projects. The best engineers protect the codebase's simplicity actively.

**Understanding the business** — why does this feature matter? Who uses it?
What does failure cost? Engineers who can answer this build better things than
those who just execute tickets.

### Process & culture

**Version control discipline** — not just knowing Git commands, but meaningful
commits, clean PRs, good branch hygiene. The commit history is documentation.

**Code review** — giving and receiving feedback that improves quality without
damaging relationships. The goal is better code, not being right.

**Incident response** — what to do when things break, how to communicate during
an outage, how to write a blameless post-mortem after.

**Technical debt management** — every shortcut you take today is work someone
does later. Knowing when debt is acceptable and when it compounds dangerously.

---

## The seniority gap

Senior engineers aren't just better at programming than junior engineers. The
gap is in **judgment** — knowing which tool to use, when to add complexity,
when to push back, and when to ship something imperfect because waiting is
more expensive than fixing it later.

Judgment comes from accumulated failures. You get it by shipping things,
watching them break, and doing post-mortems honestly. There's no shortcut —
but building production-grade projects (like this one) deliberately, instead
of just making things work, accelerates it.

---

## Related

- [[testing-disciplines]] — one of the big non-obvious parts of the job
- [[observability]] — another non-obvious part, and one that separates junior from senior in practice
