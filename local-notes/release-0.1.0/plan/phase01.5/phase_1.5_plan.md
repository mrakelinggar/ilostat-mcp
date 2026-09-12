# Phase 1.5 — CI/CD with GitHub Actions

## What and why

CI/CD should be set up before any more features are built, not after. Adding
it retroactively in Phase 4 or 5 means months of commits were never gated —
the pipeline becomes a checkbox rather than a quality gate. Setting it up now
means every commit from Phase 2b onward is automatically linted, type-checked,
and tested before it can merge. By the time Phase 4.5 (Resilience Audit) runs,
the codebase is clean and consistently verified — not scrambling to pass CI for
the first time.

---

## How GitHub Actions works

GitHub Actions reads workflow files from `.github/workflows/*.yml` in the repo.
Each file is one workflow — a set of jobs that run automatically when a trigger
fires. Triggers are Git events: a push, a pull request, a new tag.

Each job runs on a fresh GitHub-hosted virtual machine (`ubuntu-latest`). Steps
within a job run sequentially; jobs can run in parallel. GitHub provides free
minutes: unlimited for public repos, 2000/month for private. This project's
private repo (`origin`) will use ~3–5 minutes per CI run — well within limits.

```
.github/
└── workflows/
    ├── ci.yml        # runs on every push and PR
    └── publish.yml   # runs when a version tag is pushed (stub now, Phase 6)
```

---

## CI workflow — `ci.yml`

**Trigger:** every push to any branch, and every pull request targeting `main`.

**Two jobs — fast checks before slow ones:**

**Job 1: `quality` (seconds, no network)**
1. Checkout code
2. Set up Python with `uv`
3. Install dependencies
4. `ruff check .` — lint
5. `ruff format --check .` — formatting
6. `mypy src/` — type checking

**Job 2: `tests` (minutes, hits live ILOSTAT API)**
- Runs only if `quality` passes
1. Checkout code
2. Set up Python with `uv`
3. Install dependencies
4. `pytest tests/ -v`

Splitting into two jobs means a lint failure doesn't waste time running the
live API tests. Fast feedback on cheap checks first.

---

## CD workflow — `publish.yml` (stub)

**Trigger:** pushing a version tag to the public repo (e.g. `git tag v1.0.0`).

**Job: `publish`**
1. Checkout code
2. Set up Python with `uv`
3. Build (`uv build`)
4. Publish to PyPI via Trusted Publishing (OIDC — no API token stored as a secret)

PyPI Trusted Publishing is the modern standard — GitHub's identity is used
directly, no long-lived credentials stored anywhere. Must be configured once
in PyPI project settings (done in Phase 6).

The stub is created now so the file exists and the pattern is visible. The
PyPI project registration and trusted publishing configuration happen in Phase 6.

---

## Branch protection

Configure on GitHub (`ilostat-mcp-private` → Settings → Branches → main):
- Require `quality` job to pass before merging
- Optionally require `tests` job (slower; can be skipped for hotfixes)
- No required reviewers — solo project, but the CI gate is the important part

---

## Pre-task discovery — will live API tests work in GitHub Actions?

**What and why:** GitHub Actions runs on shared IP ranges that are publicly
known. Cloudflare (which ILOSTAT sits behind) might block or challenge requests
from these IPs. We use `cloudscraper` to handle Cloudflare challenges, but it's
not guaranteed to work from GH Actions IPs. If live API tests can't run in CI,
the test suite becomes meaningless in the pipeline.

**How to check:** push a minimal workflow that just runs `pytest tests/` and
watch the CI run. If it passes, no problem. If it fails with a Cloudflare
403/503, we have a decision to make.

**Fallback options if it fails:**
- Mark live API tests as `@pytest.mark.live` and skip them in CI with
  `-m "not live"` — CI runs only unit tests, live tests run manually
- Run live tests only on merge to main (not on every push/PR)
- Accept the risk and monitor — ILOSTAT is a public UN database, probably not
  aggressively blocking cloud IPs

Record the finding before declaring Phase 1.5 complete.

---

## Failure modes considered

| Failure mode | Handled? | Notes |
|---|---|---|
| Cloudflare blocks GH Actions IPs | ⚠️ Pre-task discovery | Fallback: mark live tests, skip in CI |
| mypy fails on existing Phase 1 code | ✅ Fix as part of this phase | Phase 1 may have incomplete type annotations |
| ruff format fails on existing code | ✅ Fix as part of this phase | Auto-fixable: `ruff format .` |
| CI takes too long (>10 min) | ✅ Split jobs design | quality job is seconds; tests job is separate |
| Private repo exceeds free CI minutes | ❌ Unlikely | ~3-5 min/run × reasonable commit frequency << 2000 min/month |
| publish.yml fires before PyPI project exists | ✅ Stub only | Trigger requires explicit tag push; won't fire accidentally |

---

## What this phase does NOT cover

- PyPI registration and trusted publishing config — Phase 6
- Smithery registration — Phase 6
- Codecoverage reporting — not planned for v1
- Matrix testing across Python versions — Python 3.11+ only for v1
