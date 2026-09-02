# Code Quality Metrics

*Last updated: 2026-09-03.*

---

## Why measure code quality?

"The code is cleaner now" is an opinion. "Cyclomatic complexity dropped from 18
to 4 per function, maintainability index rose from 42 to 71, and adding a new
feature now touches 1 file instead of 3" is evidence. Metrics turn a subjective
claim into a concrete, verifiable improvement — the kind of thing you can say
in an interview, a PR description, or an engineering post-mortem.

---

## The tool: `radon`

`radon` is a Python static analysis library that computes code quality metrics
without running your code.

```bash
pip install radon
radon cc path/to/file.py -s    # cyclomatic complexity, with scores
radon mi path/to/file.py -s    # maintainability index
radon raw path/to/file.py      # raw counts (lines, logical lines, comments)
```

---

## Cyclomatic complexity (CC)

Counts the number of independent paths through a function. Each `if`, `elif`,
`for`, `while`, `except`, `and`, `or` adds one path.

**Interpretation:**
| CC score | Meaning |
|---|---|
| 1–5 | Simple, low risk, easy to test |
| 6–10 | Moderate complexity |
| 11–15 | High complexity — consider refactoring |
| 16+ | Very high — almost certainly doing too many things |

**Why it matters:** a function with CC=15 needs 15 distinct tests to cover every
path. A function with CC=3 needs 3. Lower complexity = less test burden, fewer
bugs hiding in untested paths.

`radon` assigns a letter grade: A (1–5), B (6–10), C (11–15), D (16–20), E/F (21+).

---

## Maintainability Index (MI)

A composite score (0–100) combining lines of code, cyclomatic complexity, and
comment density. Higher is better.

| MI score | Meaning |
|---|---|
| 100–20 | Highly maintainable |
| 20–10 | Moderate |
| 10–0 | Hard to maintain — a warning sign |

Rarely used alone, but useful as a summary number when explaining a refactor's
overall impact.

---

## Raw counts

```bash
radon raw path/to/file.py
```

Reports:
- **LOC** — total lines of code (including blank lines and comments)
- **LLOC** — logical lines of code (statements only)
- **SLOC** — source lines of code (non-blank, non-comment)
- **Comments** — comment lines
- **Multi** — lines inside multi-line strings

A file with SLOC > 400 is a signal it's doing too much. Not a hard rule, but
a useful prompt to ask "is this one module or three?"

---

## The before/after analysis technique

**Before a refactor:**
1. Run radon on the files you plan to change. Record all numbers.
2. Count manually: how many files must change to add a new feature?
3. Count manually: how many lines of boilerplate must be replicated per new feature?

**After the refactor:**
1. Run radon again. Record the new numbers.
2. Repeat the manual counts.

**The delta is your evidence.** Examples of compelling before/after statements:

> "The main server module went from 670 lines and average CC of 12 per tool
> function to under 80 lines with CC of 2–3 per handler. Adding a new tool
> dropped from touching 2 files + replicating 40 lines of boilerplate to
> creating 1 file with 0 boilerplate."

> "Maintainability index improved from 38 to 74 across the module — verified
> with radon before and after the refactor."

This is a concrete engineering story. It demonstrates you understand *why*
the refactor matters, not just that you split a big file into small ones.

---

## Other useful metrics (manual)

**Fan-out** — how many modules does module X import from? High fan-out means X
depends on many things and breaks when any of them change.

**Fan-in** — how many modules import module X? High fan-in means X is a stable
core — changes to it ripple everywhere, so stability matters more than flexibility.

**Cost to add a feature** — the most interview-friendly metric. Count the files
that must change (not new files created) when adding a new feature. Zero means
the system is fully open/closed. One or two is acceptable. More than three is
a smell.

---

## When to run metrics

- **Before a planned refactor** — establish the baseline. Without this, you
  can't make a before/after claim.
- **As part of code review** — for files flagged as "getting complex."
- **Not as a gate** — metrics are signals, not rules. A CC of 12 in a well-tested,
  clearly named function is fine. A CC of 4 in a tangled, side-effecting mess
  is still a problem. Use metrics to prompt investigation, not replace judgment.

---

## Related

- [[solid-principles]] — the principles that metrics measure compliance with
- [[python-static-analysis]] — ruff and mypy: what they catch that radon doesn't
