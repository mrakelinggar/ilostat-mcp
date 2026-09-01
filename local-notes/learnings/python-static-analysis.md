---
name: python-static-analysis
description: Ruff and mypy — what each does, why you need both, and what they caught in practice
metadata:
  type: feedback
---

# Python static analysis: ruff + mypy

Two tools, two different jobs. They don't overlap much.

## Ruff

A linter and formatter. It reads code and flags style issues and bad patterns
without caring about types:

- Unused imports (`import os` that nothing uses)
- Unsorted imports (third-party before standard library)
- Redundant code (`dict(x=1)` instead of `{"x": 1}`, `sorted(x)[-1]` instead of `max(x)`)
- Bad patterns (`except Exception` when you should catch a specific type)
- Formatting (line length, spacing, trailing commas)

Ruff replaces flake8 + isort + black — it does all three, faster.

## Mypy

A type checker. It reads your type annotations and verifies consistency:

- A function declared to return `str` doesn't actually return `int | None` somewhere
- A function receiving `pd.DataFrame` isn't being passed `Any` from an untyped library
- Every `dict` return has type arguments so callers are verifiable (not just bare `dict`)
- Optional values are checked for `None` before use

Mypy knows nothing about style or bad patterns.

## What each catches that the other misses

**Ruff catches, mypy misses:**
An import that's unused. The code runs fine — mypy has no complaint. Ruff flags it.

**Mypy catches, ruff misses:**
A function returning `Any` because an untyped third-party library's result flowed
through without being cast. The code looks fine — ruff has no complaint. Mypy
flags it as `Returning Any from function declared to return "DataFrame"`.

## What they caught in a real codebase

On a first run against a codebase that had been hand-reviewed but never run
through either tool, they found:

**Ruff:**
- `Optional[str]` instead of modern `str | None` (2 places)
- `SEX_TOTAL` imported but never used (2 files)
- Unsorted imports (1 file)
- `dict(age=x)` instead of `{"age": x}` (2 places)
- Iterating a dict with `.items()` when only values were needed (`.values()` is clearer)
- `except Exception` where specific exception types should be caught

**Mypy:**
- `dict` return type without type arguments on every public function — 13 errors
  across 3 files. This means mypy can't verify anything about what's inside those
  dicts, so type errors in callers would go uncaught silently.
- `sdmx.to_pandas()` (from a third-party library with no stubs) returns `Any`,
  which then flowed through the entire data pipeline. The function was declared to
  return `pd.DataFrame` but was actually returning `Any`. Fixed with a `cast()`.

## Why you need both

A codebase can be perfectly formatted and lint-clean but have type bugs only mypy
finds. And vice versa. Both are fast to run, and the cost of the occasional false
positive is far lower than the cost of a runtime type error in production.

**Practical setup:**
- `ruff check src/ tests/` — lint
- `ruff format --check src/ tests/` — formatting
- `mypy src/` — type check (tests are usually not type-checked; they use `assert` which mypy doesn't model well)
- All three in CI as the `quality` job, running in seconds before the slower test job

## Handling third-party libraries with no stubs

Some libraries (like `sdmx1`, `cloudscraper`) have no type stubs and no `py.typed`
marker. Mypy will complain about importing them. Fix: add to `[[tool.mypy.overrides]]`
with `ignore_missing_imports = true`. Their attributes will be typed as `Any` — use
`cast()` at the boundary to restore correct typing for the rest of your code.

**Why:** `[[tool.mypy.overrides]]` — note the double brackets. In TOML, `[[x]]` is
an array of tables. Each `[[tool.mypy.overrides]]` block is one entry in the list.
Single `[tool.mypy.overrides]` would silently overwrite previous entries.

## `python_version` must match the runtime

If mypy's `python_version` setting is lower than the actual Python version in your
venv, mypy may fail to parse stub files that use newer syntax. For example, numpy
and pandas stubs use Python 3.12's `type` statement — setting `python_version = "3.11"`
causes a parse error in those stubs even though your code is fine.

Fix: set `python_version` to match whatever Python version your venv actually uses.
The `requires-python` field in `pyproject.toml` is for distribution compatibility;
mypy's `python_version` is for static analysis accuracy.

**Why it matters:** [[cicd-github-actions]]
