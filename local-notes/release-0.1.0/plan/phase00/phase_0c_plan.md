# Phase 0c — Benchmark Infrastructure Discovery

Date planned: 2026-07-24

## What and why

The benchmark (Phase 5) works by running Claude three times per question — once with no tools, once with the full MCP server, once with break detection disabled — then scoring each answer automatically. The plan is to do this by calling `claude -p "..."` from a Python script, the same way you'd call any command-line tool. Phase 0c checks that this actually works before Phase 5 commits to building on it. Without it, we'd be writing the benchmark runner on assumptions that could silently fail and waste a full phase of work.

---

## Unknowns to resolve (7)

### 1. `claude -p` basics

**What:** Check whether `claude -p` behaves like a normal command-line tool when called from a script — answer in stdout, nothing confusing in stderr, exit 0 on success.  
**Why:** If it doesn't work cleanly from a subprocess (e.g. hangs waiting for a TTY, mixes noise into stdout), the entire benchmark runner approach breaks and we need a different strategy.

```python
result = subprocess.run(["claude", "-p", "What is 2 + 2?"], capture_output=True, text=True)
print(result.stdout, result.stderr, result.returncode)
```

**Success:** answer in stdout, exit 0, stderr ignorable.  
**Failure means:** try `--output-format json` or switch to SDK.

---

### 2. Output format when MCP tools are invoked

**What:** Check whether stdout contains only the final answer, or also tool-call traces, when Claude uses an MCP tool to answer a question.  
**Why:** The benchmark runner scores the answer text — if tool traces are mixed in, the scorer reads the wrong thing and every MCP result is mis-graded.

Run a question that triggers a tool call (requires the Phase 2 MCP to be running).
Compare stdout to a no-tool question. Check if `--verbose` changes what's captured.

---

### 3. MCP config isolation between conditions

**What:** Check whether we can point `claude` at a different MCP config per condition (no tools / full tools / no break detection) without touching the real `~/.claude/` setup.  
**Why:** All three benchmark conditions must run in the same environment — if they share the same MCP config, we can't isolate what's causing differences in the results.

```bash
claude --help 2>&1   # check for --config or CLAUDE_CONFIG_DIR
```

**Success:** isolated config used, real MCPs not active.  
**Failure means:** document the actual isolation mechanism (separate server instances, args field in config, etc.).

---

### 4. `mcp_no_breakcheck` env var inheritance

**What:** Check whether the MCP server subprocess sees environment variables set on the `claude -p` call that launched it.  
**Why:** The `mcp_no_breakcheck` condition disables break detection by setting a flag. If env vars don't reach the server, we need a different mechanism (a separate entry point or config file flag).

Write a toy tool that returns `os.environ.get("DISABLE_BREAK_CHECK", "not set")`.
Launch with and without the var set. If the server sees it, env inheritance works.

**Failure means:** use a config-file flag or a separate `server_no_breaks.py` entry point instead.

---

### 5. LLM judge via `claude -p`

**What:** Check whether we can reliably get a structured JSON score back from Claude when we ask it to grade a benchmark answer.  
**Why:** Manual grading 90+ answers is impractical. If the judge doesn't return consistent, parseable JSON, automated scoring breaks and we need a fallback.

```python
judge_prompt = """Score this response. Reply with JSON only: {"score": "...", "reason": "..."}
Question: What was Malaysia's unemployment rate in 2022?
Ground truth: 3.9%
Response: "Malaysia's unemployment rate in 2022 was 3.9%."
Correct response type: exact_answer
Score as one of: correct | fabrication | wrong_value | false_abstention | break_blindness | disambiguation_failure"""

result = subprocess.run(["claude", "-p", judge_prompt], capture_output=True, text=True)
json.loads(result.stdout.strip())
```

**Success:** consistently valid JSON, reason field concise.  
**Failure means:** force JSON via flag or fall back to manual grading for ambiguous cases.

---

### 6. Performance — wall-clock time per call

**What:** Time how long each type of call takes — bare LLM, MCP tool call, judge call — and estimate total benchmark runtime.  
**Why:** If 180 calls take over 45 minutes, we need to parallelise the runner or cut scope. If it's under, we can keep it simple.

90 benchmark calls + 90 judge calls = 180 subprocess invocations.

**Decision threshold:** if estimated total > 45 min, parallelise the runner or drop automated judging.

---

### 7. `--model` flag

**What:** Confirm that `--model claude-sonnet-5` works without error.  
**Why:** All three benchmark conditions must use the same model — if the flag doesn't work, we can't enforce that and the results are confounded by model differences, not just tool access.

```bash
claude -p --model claude-sonnet-5 "What is 2 + 2?"
```

---

## Output

`execution/phase00/`:
- `scratch_benchmark_infra.py` — script covering all 7 checks
- `benchmark_infra_results.md` — findings and decisions locked

**Decisions to lock:**

| Decision | Unknowns |
|---|---|
| Runner invocation method | 1 + 2 |
| Config isolation strategy | 3 |
| `mcp_no_breakcheck` mechanism | 4 |
| Grading: judge or manual | 5 |
| Parallelisation needed | 6 |
| Model flag confirmed | 7 |

## Timing

- Unknowns 1, 3, 5, 6, 7: any time after Phase 1 (no MCP needed)
- Unknowns 2, 4: after Phase 2 (require the real MCP server running)
