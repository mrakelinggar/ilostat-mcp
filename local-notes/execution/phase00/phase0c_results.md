# Phase 0c Extended — Benchmark Infrastructure Results

Date: 2026-07-24  
Script: `scratch_benchmark_infra.py`  
All "runs now" checks complete (17/22 unknowns). 5 unknowns deferred to Phase 2.

---

## Summary of findings

### 1. Basic invocation

**`claude -p` works cleanly in a subprocess.**  
Exit 0, answer in stdout, stderr completely empty (no spinners, no progress noise).  
`capture_output=True` is safe — no deadlock even for long outputs (tested to ~5800 chars / 26s).

Latency baseline: **P50 = 7.2s, P95 = 7.9s, max = 9.1s** per bare-LLM call.

---

### 2. Output format

**Use `--output-format json` and read `data["result"]`.**  

The JSON schema has ~20 fields. The ones we care about:

| Field | Value |
|---|---|
| `result` | The model's text answer |
| `is_error` | `false` on success |
| `total_cost_usd` | Cost of this call |
| `usage` | Input/output/cache token counts |
| `modelUsage` | Per-model breakdown including `costUSD` |
| `stop_reason` | `"end_turn"` on normal completion |

Cost tracking is built in — no need to estimate from token counts separately.

---

### 3. Config isolation

**`CLAUDE_CONFIG_DIR` env var does NOT work** — auth is in the macOS keychain, not in a config dir. Setting it to a temp dir causes "Not logged in · Please run /login" (exit 1).

**`--mcp-config <path> --strict-mcp-config` is the correct isolation mechanism.**  
Tested and confirmed: passing an empty `{"mcpServers": {}}` config with `--strict-mcp-config` runs successfully (exit 0) and ignores any real MCP servers. Each benchmark condition gets its own JSON config file, not a config directory swap.

**No `~/.claude/CLAUDE.md`** — no system prompt leakage risk. `--bare` is available as a backup if that changes.

---

### 4. Rate limiting and robustness

5 rapid sequential calls all succeeded. No rate-limit triggered at normal API pace.  

**No `--timeout` flag exists in the CLI.** Use `subprocess.run(timeout=120)` as the safety net — enough headroom above P95 (7.9s) to catch genuine hangs without false positives.

---

### 5. LLM judge

**Reliable.** 5/5 runs returned valid JSON with no markdown fences.  

**`--json-schema` is the best approach** — enforces the output schema at the API level, not just via prompt instruction. Combine with `--system-prompt` for the grading rubric:

```python
subprocess.run([
    CLAUDE, "-p",
    "--system-prompt", JUDGE_SYSTEM,
    "--json-schema", json.dumps(JUDGE_SCHEMA),
    "--output-format", "json",
    user_message
], ...)
# answer is in data["result"], parsed as JSON
```

**Borderline case behavior:** The judge is strict. All three hard cases scored "wrong_value" consistently (3/3 runs each):
- "approximately 3.8%" → `wrong_value` (correct)
- "around 3-4%" → `wrong_value` (correct)
- "in the 3.7% range" → `wrong_value` (**flag**: this is the right number buried in hedging; the judge treats it as wrong)

The third case is a real concern: a hedged-but-correct answer gets penalized. Benchmark categories `answerable_clean` responses that hedge should be manually reviewed after automated scoring. Add a `needs_review` flag to the benchmark schema for judge scores on hedged answers.

---

### 6. Performance and cost

**Serial is fine.** 120 calls (30 questions × 3 conditions + 30 judge calls) at 7.66s mean = **~15.3 minutes**. Well under the 45-min threshold. Parallelization not needed for v1.

**Cost is trackable.** `total_cost_usd` in the JSON output gives exact cost per call. A full 120-call benchmark run will cost roughly $2–6 depending on prompt length and model (claude-sonnet-5 default). Log cumulative cost in `run_benchmark.py`.

---

### 7. Model and auth

`--model claude-sonnet-5` and `--model claude-haiku-4-5` both work. Full model IDs accepted.

Auth uses the macOS keychain. Without it (or without `ANTHROPIC_API_KEY`): exit 1, "Not logged in · Please run /login". Clean failure mode — easy to detect. CI would need `ANTHROPIC_API_KEY` set explicitly.

---

## Decisions locked

| Decision | Verdict |
|---|---|
| Runner invocation | `claude -p` subprocess. No SDK needed. |
| Output parsing | `--output-format json` → `data["result"]`. Clean, no stripping needed. |
| Buffer handling | `capture_output=True` is safe. No deadlock observed. |
| Config isolation | `--mcp-config <path> --strict-mcp-config`. NOT `CLAUDE_CONFIG_DIR`. |
| System prompt leakage | No risk (no `~/.claude/CLAUDE.md`). `--bare` available as backup. |
| Timeout | No `--timeout` flag. Use `subprocess.run(timeout=120)`. |
| Judge format | `--system-prompt` + `--json-schema` + `--output-format json`. |
| Judge edge cases | Strict scorer. Add manual `needs_review` pass for hedged-correct answers. |
| Parallelization | Not needed. 15.3 min serial is acceptable. |
| Cost tracking | `total_cost_usd` in JSON output. Log per-call and accumulate total. |
| Model flag | `--model claude-sonnet-5` confirmed. Same model all 3 conditions. |
| Auth | Keychain-based. CI needs `ANTHROPIC_API_KEY`. Documents cleanly on failure. |

---

## Remaining for Phase 2

These 5 unknowns require the MCP server to be running:

| Unknown | What to test |
|---|---|
| 2.1 MCP server lifecycle | Does each `claude -p` call start a fresh server? Add startup log, count fires. |
| 2.2 Tool-call output format | Does `data["result"]` still contain only the final answer (not tool traces)? |
| 3.4 Parallel config contention | Can N parallel `claude -p` processes share one MCP config safely? |
| 4.3 env var inheritance | Does `DISABLE_BREAK_CHECK` env var reach the MCP server subprocess? |
| 6.1 MCP call timing | What is P50/P95 for a call that triggers a real tool? Revise time estimate. |

---

## Impact on `run_benchmark.py` design

```python
# Invocation pattern locked (for all 3 conditions):
result = subprocess.run(
    [
        CLAUDE, "-p",
        "--model", "claude-sonnet-5",
        "--mcp-config", condition_config_path,   # per-condition JSON
        "--strict-mcp-config",                    # ignore ~/.claude MCP servers
        "--output-format", "json",
        "--no-session-persistence",               # clean slate per call
        prompt
    ],
    capture_output=True, text=True, timeout=120
)
data = json.loads(result.stdout)
answer = data["result"]
cost = data["total_cost_usd"]

# Judge invocation:
judge_result = subprocess.run(
    [
        CLAUDE, "-p",
        "--model", "claude-sonnet-5",
        "--system-prompt", JUDGE_SYSTEM,
        "--json-schema", json.dumps(JUDGE_SCHEMA),
        "--output-format", "json",
        "--bare",   # no CLAUDE.md, no hooks, faster
        "--no-session-persistence",
        judge_prompt
    ],
    capture_output=True, text=True, timeout=120
)
judge_data = json.loads(judge_result.stdout)
score = json.loads(judge_data["result"])  # --json-schema forces valid JSON
```
