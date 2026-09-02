# SOLID Principles and Modular Design

*Last updated: 2026-09-03.*

---

## What SOLID is

SOLID is five design principles that make code easier to extend, test, and
maintain. Each letter is one principle. They apply to any language, not just
object-oriented code. In practice, the first two matter most in everyday work.

---

## S — Single Responsibility Principle (SRP)

A module, function, or class should have exactly one reason to change.

If you need "and" to describe what it does, it's doing too many things. A
function that validates input AND fetches data AND formats the response will
need to be edited when the validation rules change, when the data source
changes, and when the output format changes — three unrelated reasons.

**In practice:** when a module grows beyond ~200 lines, ask what each section
is "responsible for." If the answer involves multiple distinct concerns (validation,
I/O, formatting, orchestration), split them. Each concern changes at a different
rate and for different reasons — keeping them together creates coupling with no
benefit.

---

## O — Open/Closed Principle (OCP)

A system should be *open for extension* but *closed for modification*.

Adding a new feature should require writing new code, not editing existing code.

**Bad (violates OCP):**
```python
def process(event_type: str, data: dict) -> None:
    if event_type == "order":
        handle_order(data)
    elif event_type == "refund":
        handle_refund(data)
    # Adding "cancellation" means editing this function
```

**Good (obeys OCP):**
```python
_HANDLERS: dict[str, Callable] = {
    "order": handle_order,
    "refund": handle_refund,
}

def process(event_type: str, data: dict) -> None:
    handler = _HANDLERS.get(event_type)
    if handler is None:
        raise ValueError(f"Unknown event type: {event_type}")
    handler(data)

# Adding "cancellation" = add one line to _HANDLERS dict; process() never changes
```

The existing code is "closed" — it doesn't change. New behavior is "open" —
you add to the registry, not the dispatch logic.

---

## The other three (briefly)

**L — Liskov Substitution:** if you have a subclass, you should be able to use
it anywhere the parent is used without breaking anything. Relevant when you have
inheritance hierarchies; less common in everyday Python.

**I — Interface Segregation:** don't force callers to depend on methods they
don't use. In Python this mostly means: don't put unrelated methods in the same
class or module.

**D — Dependency Inversion:** high-level modules shouldn't depend on low-level
details. Instead, both should depend on abstractions. In Python: pass
dependencies as parameters, don't hardcode them.

---

## Separation of Concerns (SoC)

Closely related to SRP — keep code that changes for different reasons in
different places. The key insight is "different reasons":

- **Validation** changes when business rules change
- **I/O** (API calls, database queries) changes when external systems change
- **Business logic** changes when requirements change
- **Formatting/presentation** changes when the output format changes
- **Observability** (logging, tracing) changes when your monitoring stack changes

If these are all tangled in one file, a change to validation accidentally breaks
I/O. Separating them means each concern can evolve independently, and you can
test each in isolation.

---

## Registry + handler pattern

A concrete application of OCP. Instead of a monolithic dispatcher that knows
about every case, you have:

1. **A registry** — a dict (or any lookup structure) mapping a key to a handler
2. **Self-contained handlers** — each handler owns one case
3. **A thin orchestrator** — reads the registry and calls the right handler

```python
# handlers/order.py
def handle(data: dict) -> Result:
    # everything about orders lives here

# handlers/refund.py
def handle(data: dict) -> Result:
    # everything about refunds lives here

# registry.py
from handlers import order, refund

HANDLERS: dict[str, Callable[[dict], Result]] = {
    "order": order.handle,
    "refund": refund.handle,
}

# dispatcher.py
from registry import HANDLERS

def process(event_type: str, data: dict) -> Result:
    if event_type not in HANDLERS:
        raise ValueError(f"Unknown event type: {event_type}")
    return HANDLERS[event_type](data)
```

Adding a new event type: create `handlers/cancellation.py`, add one line to
`registry.py`. `dispatcher.py` never changes. Neither do any of the other handlers.

**This is how web frameworks handle routes.** Flask's `@app.route("/orders")`
and FastAPI's `@router.get("/orders")` are the same pattern — you define a
handler, register it with a decorator, the framework's dispatcher takes care
of the rest. You never edit the dispatcher when you add a route.

---

## How to spot a SRP violation in code review

Look for functions where:
- The name is vague or compound: `process_and_validate`, `fetch_format_return`
- There are multiple levels of abstraction in the same function: low-level I/O
  (open file, make API call) mixed with high-level business logic
- Any change to one part of the function makes you nervously re-test all the
  other parts
- The function is hard to unit test without mocking 3+ things

If any of these are true, the function is doing more than one thing.

---

## Measuring the impact of applying these principles

Before and after a modular refactor, run:
```bash
radon cc path/to/module.py -s   # cyclomatic complexity per function
radon mi path/to/module.py -s   # maintainability index (0–100, higher = better)
radon raw path/to/module.py     # lines of code
```

Count manually:
- **Files that must change to add a new feature** — target is 1
- **Lines of boilerplate to replicate per new feature** — target is 0

The before/after delta is concrete interview evidence. See [[code-quality-metrics]].

---

## Related

- [[code-quality-metrics]] — how to measure and communicate improvement
- [[observability]] — observability is its own concern; it should not live inside business logic
