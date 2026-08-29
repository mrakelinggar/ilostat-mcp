# Testing Disciplines

*Learned while building ilostat-mcp. Last updated: 2026-08-29.*

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
the past or future, countries with no data, years out of range. Examples from
this project: North Korea (no data), year 1960 (before ILOSTAT coverage),
`start_year > end_year` (inverted range).

### Negative testing
What happens when you deliberately do the wrong thing? Pass an invalid country
code, an unrecognised `age_group` value, more than 3 countries to a prompt
that caps at 3. The system should fail explicitly and helpfully, not silently
or cryptically.

### Integration testing
Does it hold together when all the parts run at once? A unit test checks
`yoy()` in isolation. An integration test checks that `get_yoy_change` calls
`get_time_series`, passes the right parameters, handles an empty result, and
surfaces the break warning correctly — all in one flow.

### Resilience testing (chaos testing)
What happens when dependencies fail? Kill the API mid-request. Throttle the
network to simulate a slow response. Return a malformed response. This is
where you find the "it works on my machine" bugs — things that only break in
production because production has unreliable dependencies.

### Regression testing
Does fixing one thing break something that was working? This is why test suites
exist — to catch regressions automatically. Every time you change code, the
suite runs and tells you if something you didn't touch is now broken. Without
this, you're re-testing everything by hand on every change.

---

## The Phase 4.5 principle

You can only see certain failure modes after the full system exists. A break
that's invisible in Phase 2 becomes obvious once Phase 3's detection logic is
running against it. This is why a dedicated resilience audit phase (Phase 4.5
in this project) runs after the feature-complete milestone but before shipping.

In software engineering this is called a **hardening phase** or **resilience
review**. Common in mature engineering teams.

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

## Practical rules (from this project's CLAUDE.md)

- Tests must be meaningful — verify correctness against known values, not
  just "does it run without crashing"
- Every error path has a test — not just the happy path
- Live API tests are intentional — mocks hide real behaviour
- Tests pass before any commit to main
- CI runs lint → type check → tests on every push

---

## Related

- [[observability]] — how you see what's happening in production when things go wrong
- [[software-eng-breadth]] — testing is one of many non-coding skills in the job
