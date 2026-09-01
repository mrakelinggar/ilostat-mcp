---
name: python-type-system
description: Python's optional type system — how it compares to TypeScript, what opt-in means in practice, and why discipline matters
metadata:
  type: feedback
---

# Python's type system

## The TypeScript comparison

Python's type annotations give you the same core benefit as TypeScript: annotate
types, run a static checker, catch a class of bugs before the code runs rather
than in production.

The key difference: TypeScript's type system is **mandatory and built into the
language**. Python's is **opt-in** — annotations are hints only. The runtime
ignores them entirely. A function annotated `def f(x: int) -> str` can be called
with a list and return None and Python won't complain at runtime.

Mypy is the external tool that enforces the annotations statically. Running mypy
is the equivalent of running the TypeScript compiler.

## What "opt-in" means in practice

Because annotations are optional, a Python codebase can have:
- A fully annotated file next to a completely unannotated file
- Mypy only checks what's been annotated
- Unannotated functions are typed as `(...) -> Any` — mypy lets `Any` through
  everywhere, so a gap in one function propagates silently

This is why a discipline rule like "full type annotations on all public functions"
matters. Without it, mypy's coverage is spotty and you lose most of the benefit.
A single unannotated function can inject `Any` into a chain of otherwise well-typed
code and mypy won't catch it.

## The practical implication

If you annotate your own code but depend on a third-party library with no stubs,
that library's return values are typed as `Any`. `Any` is contagious — it flows
through assignments, function calls, and returns without triggering mypy errors.
You need to use `cast()` at the boundary to restore correct typing:

```python
# sdmx.to_pandas() has no stubs → returns Any
# Without cast: df is Any, downstream code loses type coverage
df = cast(pd.DataFrame, sdmx.to_pandas(resp, attributes="o"))
```

After the `cast`, `df` is `pd.DataFrame` and all subsequent operations are
fully checked.

## `dict` without type arguments

In Python's type system, `dict` alone is like `object` — mypy can't check
anything about the keys or values. Always specify: `dict[str, str]` for
string-only dicts, `dict[str, object]` for mixed-value dicts (str, bool, etc.).

A function returning bare `dict` means every caller's access to that dict is
unchecked. This is a common gap in codebases that add type annotations
incrementally without running mypy.

**Why:** [[python-static-analysis]]
