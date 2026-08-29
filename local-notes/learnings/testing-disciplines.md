# Testing Disciplines

*Last updated: 2026-08-29.*

---

## Testing is almost as hard as building

The instinct is that testing is the easy part — you just run the app and see
if it crashes. But systematic testing requires a completely different mindset:
you have to imagine everything that could go wrong, including things the
developer never intended to happen. That's harder than building the happy path.

This is the core reason dev and QA are separate roles — a developer is too
close to their own code. They test the paths they know exist. A good tester
deliberately ignores how the code works internally and probes from the outside,
which surfaces assumptions the developer didn't know they were making.

---

## The testing landscape

### Functional testing
Does it do what it's supposed to? The happy path. This is where most people
stop — it's not enough.

### Edge case testing
What happens at the boundaries? Empty inputs, maximum values, dates far in
the past or future, IDs that don't exist, ranges that produce no results.
Examples: a user ID of 0, a date range where start > end, a search term
with no matches, a request for data that exists in the schema but not in
the database.

### Negative testing
What happens when you deliberately do the wrong thing? Pass an invalid
parameter, exceed a limit, use a value from the wrong set. The system should
fail explicitly and helpfully — not silently or cryptically.

### Integration testing
Does it hold together when all the parts run at once? A unit test checks a
function in isolation. An integration test checks that function A calls
function B with the right parameters, handles an empty result, and surfaces
the right output — all in one flow, against real dependencies.

### Resilience testing (chaos testing)
What happens when dependencies fail? Kill an external API mid-request.
Throttle the network to simulate a slow response. Return a malformed payload.
This is where you find the "it works on my machine" bugs — things that only
break in production because production has unreliable dependencies.

### Regression testing
Does fixing one thing break something that was working? This is why test suites
exist — to catch regressions automatically. Every time you change code, the
suite runs and tells you if something you didn't touch is now broken. Without
this, you're re-testing everything by hand on every change.

---

## The hardening phase principle

You can only see certain failure modes after the full system exists. A gap
that's invisible when one component is built in isolation becomes obvious once
the rest of the system is running against it. This is why mature teams run a
dedicated **hardening phase** (also called a resilience review) after the
feature-complete milestone but before shipping — specifically to catch these
cross-component failures that individual-phase testing missed.

---

## Who is responsible when something fails in production?

**Old model (waterfall):** dev builds → throws to QA → QA approves → ships.
If it fails, QA missed it.

**Modern model (agile/DevOps):** quality is shared. The developer is expected
to write tests and think about edge cases. QA is a safety net, not the first
line of defence.

**Blameless post-mortems:** at companies like Google, Amazon, and Netflix,
production failures are analysed without assigning blame to individuals. The
goal is to find the systemic gap — where the process failed — not the person
to fire. Reasoning: if you blame people, they hide failures. If you treat
failures as process gaps, people surface them and the system improves.

The honest answer for most production failures: everyone owns a piece of it.
The goal is fixing the gap so it doesn't happen again.

---

## Production testing rules

- Tests must be meaningful — verify correctness against known values, not
  just "does it run without crashing"
- Every error path has a test — not just the happy path
- Live/integration tests against real dependencies are intentional — mocks
  hide real behaviour and give false confidence
- Tests pass before any commit to main
- CI runs lint → type check → tests on every push (see [[cicd-github-actions]])

---

## Related

- [[observability]] — how you see what's happening in production when tests miss something
- [[cicd-github-actions]] — how tests run automatically on every push
- [[software-eng-breadth]] — testing is one of many non-coding skills in the job
