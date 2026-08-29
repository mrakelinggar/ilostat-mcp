# CI/CD and GitHub Actions

*Learned while building ilostat-mcp. Last updated: 2026-08-29.*

---

## What CI/CD is

**CI — Continuous Integration:** automatically run checks against code on
every push. Catch problems immediately, before bad code merges. The "continuous"
part means every push, not just before a release.

**CD — Continuous Delivery/Deployment:** automatically move code through
environments after CI passes.

The standard flow in most teams:
```
push to feature branch
    → CI runs (lint, type check, tests)
    → merge to main (gated — CI must pass)
    → auto-deploy to dev/test
    → approval gate
    → deploy to prod
```

For a library (like this MCP), CD means publishing to a package registry
(PyPI) instead of deploying to a server. The trigger is pushing a version tag.

---

## Why CI must be set up early

CI set up retroactively is a checkbox. CI set up before features are built is
a gate. If you add it after months of commits, you're playing catch-up instead
of preventing problems. The rule: set up CI before writing the second meaningful
chunk of code.

---

## What CI checks (in order — fast first, slow last)

```
push → lint + format check    (seconds — fail fast on obvious issues)
     → type check             (seconds — catches a whole class of bugs)
     → unit tests             (seconds to minutes — no network)
     → integration tests      (minutes — hits real dependencies)
     → smoke tests            (end-to-end sanity check, optional)
```

The ordering matters: if lint fails, there's no point running 5-minute API
tests. Fail cheap before failing expensive.

For this project:
- **Job 1 (`quality`):** `ruff check` + `ruff format --check` + `mypy`
- **Job 2 (`tests`):** `pytest` against live ILOSTAT API
- Job 2 only runs if Job 1 passes

---

## How GitHub Actions works

Workflow files live in `.github/workflows/*.yml` in the repo. Each file is
one workflow. GitHub reads them automatically — no setup needed beyond
committing the files.

**Basic structure:**
```yaml
name: CI

on:                          # trigger — what event fires this workflow
  push:
  pull_request:
    branches: [main]

jobs:
  quality:                   # job name (arbitrary)
    runs-on: ubuntu-latest   # GitHub-hosted VM
    steps:
      - uses: actions/checkout@v4          # check out the repo
      - uses: astral-sh/setup-uv@v3        # install uv
      - run: uv sync                       # install deps
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy src/

  tests:
    runs-on: ubuntu-latest
    needs: quality             # only run if quality passes
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: pytest tests/ -v
```

**Triggers:**
- `push` — fires on every push to any branch
- `pull_request` — fires when a PR is opened or updated
- `push: tags: ['v*']` — fires when a version tag is pushed (used for CD)

**GitHub-hosted runners:** free Ubuntu VMs. Unlimited minutes for public
repos; 2000 free minutes/month for private repos.

---

## CD for a Python library — PyPI publish

No server to deploy to — CD means publishing a new version to PyPI when a
release tag is pushed.

```
git tag v1.0.0
git push public v1.0.0
    → publish.yml fires
    → build the package
    → publish to PyPI
```

**PyPI Trusted Publishing (OIDC):** the modern standard — no API token stored
as a secret anywhere. GitHub's identity is used directly via OpenID Connect.
Configure once in PyPI project settings; the workflow just calls the publish
action. More secure than storing long-lived credentials.

---

## Branch protection

On GitHub: repo Settings → Branches → Add rule for `main`.
- Require status checks to pass (the `quality` job at minimum)
- This blocks merging to main unless CI is green
- For solo projects: no required reviewers, but the CI gate is the important part

---

## Azure Pipelines vs GitHub Actions

Same concept, different tools. Azure Pipelines is Microsoft's version — common
in enterprise. GitHub Actions is GitHub's native version — more common in open
source and startups. Both define pipelines in YAML, both run on triggers.

Key difference: Azure Pipelines integrates with Azure DevOps boards and
Microsoft ecosystem. GitHub Actions integrates with GitHub natively (PRs,
issues, releases). For a GitHub-hosted project, GitHub Actions is the
obvious choice.

---

## Related

- [[testing-disciplines]] — what CI runs (the checks it executes)
- [[observability]] — what you need after CI passes and code is in production
- [[software-eng-breadth]] — CI/CD is one of the infrastructure skills
