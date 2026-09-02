# Learnings Index

Personal knowledge capture from building this project. Each file explains a concept
in plain English — what it means, why it matters, and how it connects to real decisions
made here. Feed this into your Obsidian vault after each session or when the project ends.

---

- [mcp-fundamentals.md](mcp-fundamentals.md) — MCP's three primitives: tools, resources, prompts. What each is, who controls it, how it works in Claude Desktop vs Claude Code.
- [mcp-fastmcp.md](mcp-fastmcp.md) — FastMCP v2 vs the official MCP Python SDK. Why we use the standalone package and what it gives us.
- [testing-disciplines.md](testing-disciplines.md) — The full testing landscape beyond "does it run": functional, edge case, resilience, regression. Why dev and QA are separate roles. Blameless post-mortems.
- [observability.md](observability.md) — The three pillars: logs, traces, metrics. What a trace actually is, how OTel + Honeycomb works, why structured JSON logs beat plain text.
- [software-eng-breadth.md](software-eng-breadth.md) — Software engineering is more than programming. The full map of what the job actually involves.
- [cicd-github-actions.md](cicd-github-actions.md) — What CI/CD is, why CI must be set up early, how GitHub Actions works (workflow YAML, triggers, jobs, steps), PyPI Trusted Publishing for CD, Azure Pipelines vs GitHub Actions.
- [WRITING_MATERIALS.md](WRITING_MATERIALS.md) — Article ideas worth writing: practitioner-level, grounded in real decisions from real implementations. Updated each session. Not intro/tutorial material.
- [TDS_GUIDELINES.md](TDS_GUIDELINES.md) — Towards Data Science submission guidelines (sourced August 2026). What passes, what gets rejected, the three filters to apply to every article idea before writing.
- [python-static-analysis.md](python-static-analysis.md) — Ruff vs mypy: what each does, what each catches that the other misses, what they found on a real first run, and how to handle third-party libraries with no stubs.
- [python-type-system.md](python-type-system.md) — Python's opt-in type system vs TypeScript's mandatory one. Why discipline on annotations matters, how `Any` is contagious, and why bare `dict` is a type coverage gap.
- [solid-principles.md](solid-principles.md) — SOLID principles in plain English: SRP, OCP, and the registry + handler pattern. How to apply Open/Closed in practice and spot SRP violations in code review.
- [code-quality-metrics.md](code-quality-metrics.md) — radon: cyclomatic complexity, maintainability index, raw counts. How to run a before/after analysis that turns a refactor into concrete interview evidence.
- [git-advanced.md](git-advanced.md) — Multi-remote refspec patterns (local:remote mapping), the common mistake of omitting `:main`, rewriting history with git filter-repo, and GitHub's contributor cache behaviour.
