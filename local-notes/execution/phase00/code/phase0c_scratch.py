"""
Phase 0c Extended — Benchmark infrastructure discovery
Covers all "runs now" unknowns (no MCP server needed).
Run: python scratch_benchmark_infra.py
"""

import json
import os
import re
import subprocess
import time
import tempfile
import pathlib

CLAUDE = "/Users/mrla/.local/bin/claude"
SECTION_WIDTH = 60


def header(title):
    print(f"\n{'=' * SECTION_WIDTH}")
    print(f"  {title}")
    print('=' * SECTION_WIDTH)


def run(args, extra_env=None, timeout=60):
    env = {**os.environ, **(extra_env or {})}
    start = time.perf_counter()
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env)
    elapsed = time.perf_counter() - start
    return result, elapsed


# ---------------------------------------------------------------------------
# 1.1  Basic -p invocation
# ---------------------------------------------------------------------------
header("1.1  claude -p basics — stdout / stderr / exit code")

result, elapsed = run([CLAUDE, "-p", "What is 2 + 2? Reply with just the number."])
print(f"exit code : {result.returncode}")
print(f"stdout    : {result.stdout.strip()!r}")
print(f"stderr    : {result.stderr.strip()[:200]!r}")
print(f"elapsed   : {elapsed:.2f}s")


# ---------------------------------------------------------------------------
# 1.2  --output-format json schema
# ---------------------------------------------------------------------------
header("1.2  --output-format json — full schema")

result, elapsed = run([CLAUDE, "-p", "--output-format", "json",
                       "What is 2 + 2? Reply with just the number."])
print(f"exit code : {result.returncode}")
print(f"raw stdout (first 800 chars):\n{result.stdout[:800]}")
try:
    data = json.loads(result.stdout)
    print(f"\nParsed keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
    if isinstance(data, dict):
        for k, v in data.items():
            preview = str(v)[:120]
            print(f"  {k}: {preview!r}")
except json.JSONDecodeError as e:
    print(f"JSON parse error: {e}")
print(f"elapsed: {elapsed:.2f}s")


# ---------------------------------------------------------------------------
# 1.3  Stderr content — simple vs slow prompt
# ---------------------------------------------------------------------------
header("1.3  stderr content")

# Simple
r1, _ = run([CLAUDE, "-p", "Reply with 'ok'."])
print(f"[simple] stderr repr: {r1.stderr[:300]!r}")

# Slightly heavier
r2, _ = run([CLAUDE, "-p", "List 5 programming languages, one per line."])
print(f"[list]   stderr repr: {r2.stderr[:300]!r}")


# ---------------------------------------------------------------------------
# 1.4  Buffer deadlock risk — long output
# ---------------------------------------------------------------------------
header("1.4  Buffer deadlock — long response")

try:
    result, elapsed = run(
        [CLAUDE, "-p", "Write exactly 800 words about macroeconomics. Be thorough."],
        timeout=90
    )
    print(f"exit code : {result.returncode}")
    print(f"stdout len: {len(result.stdout)} chars")
    print(f"stderr len: {len(result.stderr)} chars")
    print(f"elapsed   : {elapsed:.2f}s")
    print("No deadlock with capture_output=True")
except subprocess.TimeoutExpired:
    print("TIMED OUT — capture_output=True may deadlock on long output")


# ---------------------------------------------------------------------------
# 3.1  --mcp-config flag (already confirmed in --help; document flags found)
# ---------------------------------------------------------------------------
header("3.1  Config isolation flags (from --help)")

help_out = subprocess.run([CLAUDE, "--help"], capture_output=True, text=True).stdout
flags_to_check = ["--mcp-config", "--strict-mcp-config", "--bare", "--system-prompt",
                  "--append-system-prompt", "--safe-mode", "CLAUDE_CONFIG"]
for flag in flags_to_check:
    present = flag in help_out
    print(f"  {flag:35s} {'PRESENT' if present else 'ABSENT'}")


# ---------------------------------------------------------------------------
# 3.2  CLAUDE_CONFIG_DIR env var isolation
# ---------------------------------------------------------------------------
header("3.2  CLAUDE_CONFIG_DIR env var isolation")

with tempfile.TemporaryDirectory() as tmp:
    # Minimal settings.json so claude doesn't complain about missing config
    settings = {"theme": "dark"}
    (pathlib.Path(tmp) / "settings.json").write_text(json.dumps(settings))
    result, elapsed = run(
        [CLAUDE, "-p", "Reply with 'isolated-ok'."],
        extra_env={"CLAUDE_CONFIG_DIR": tmp}
    )
    print(f"exit code : {result.returncode}")
    print(f"stdout    : {result.stdout.strip()!r}")
    print(f"stderr    : {result.stderr.strip()[:200]!r}")
    print(f"elapsed   : {elapsed:.2f}s")


# ---------------------------------------------------------------------------
# 3.2b  --mcp-config + --strict-mcp-config isolation (no MCP defined = bare llm)
# ---------------------------------------------------------------------------
header("3.2b  --mcp-config --strict-mcp-config (bare LLM condition)")

with tempfile.TemporaryDirectory() as tmp:
    empty_mcp = {"mcpServers": {}}
    cfg_path = str(pathlib.Path(tmp) / "mcp_bare.json")
    pathlib.Path(cfg_path).write_text(json.dumps(empty_mcp))
    result, elapsed = run([
        CLAUDE, "-p",
        "--mcp-config", cfg_path,
        "--strict-mcp-config",
        "Reply with 'strict-ok'."
    ])
    print(f"exit code : {result.returncode}")
    print(f"stdout    : {result.stdout.strip()!r}")
    print(f"elapsed   : {elapsed:.2f}s")


# ---------------------------------------------------------------------------
# 3.3  ~/.claude/CLAUDE.md leakage — does --bare suppress it?
# ---------------------------------------------------------------------------
header("3.3  CLAUDE.md system prompt leakage + --bare flag")

claude_md_path = pathlib.Path.home() / ".claude" / "CLAUDE.md"
if claude_md_path.exists():
    size = claude_md_path.stat().st_size
    print(f"~/.claude/CLAUDE.md EXISTS ({size} bytes)")
    # Test without --bare
    r1, _ = run([CLAUDE, "-p", "What instructions are you following? List the first 3."])
    print(f"\nWithout --bare — first 300 chars of stdout:\n{r1.stdout[:300]}")
    # Test with --bare
    r2, _ = run([CLAUDE, "-p", "--bare",
                 "What instructions are you following? List the first 3."])
    print(f"\nWith --bare — first 300 chars of stdout:\n{r2.stdout[:300]}")
else:
    print("~/.claude/CLAUDE.md does NOT exist — no leakage risk")


# ---------------------------------------------------------------------------
# 4.1  Rate-limit exit code (fire 5 quick calls, observe any failures)
# ---------------------------------------------------------------------------
header("4.1  Rate-limit behavior — 5 rapid sequential calls")

outcomes = []
for i in range(5):
    r, t = run([CLAUDE, "-p", f"Reply with just the number {i}."])
    outcomes.append((i, r.returncode, r.stdout.strip()[:30], t))
    print(f"  call {i}: exit={r.returncode}  out={r.stdout.strip()[:30]!r}  t={t:.2f}s")

failed = [o for o in outcomes if o[1] != 0]
if failed:
    print(f"\nFailures: {failed}")
    print("stderr from first failure:")
    # Re-run to capture stderr of a failure (we only see returncode above)
else:
    print("\nAll 5 calls succeeded — no rate-limit triggered at this pace")


# ---------------------------------------------------------------------------
# 4.2  Timeout flag + P95 latency baseline
# ---------------------------------------------------------------------------
header("4.2  Timeout flag + latency baseline")

timeout_in_help = "--timeout" in help_out or "timeout" in help_out.lower()
print(f"'timeout' in --help output: {timeout_in_help}")
# Extract relevant lines
for line in help_out.splitlines():
    if "timeout" in line.lower():
        print(f"  {line.strip()}")

# P95 latency: 7 calls
print("\nLatency samples (7 calls — bare LLM, short prompt):")
times = []
for i in range(7):
    _, t = run([CLAUDE, "-p", f"Reply with 'ok-{i}'."])
    times.append(t)
    print(f"  call {i}: {t:.2f}s")
times_sorted = sorted(times)
p50 = times_sorted[len(times_sorted) // 2]
p95 = times_sorted[int(len(times_sorted) * 0.95)]
print(f"\nP50={p50:.2f}s  P95={p95:.2f}s  max={max(times):.2f}s")


# ---------------------------------------------------------------------------
# 5.1  LLM judge — JSON reliability (5 runs)
# ---------------------------------------------------------------------------
header("5.1  LLM judge — JSON reliability")

JUDGE_SYSTEM = (
    "You are a benchmark grader. Score the response and reply with ONLY valid JSON, "
    "no markdown fences, no explanation outside the JSON. "
    'Schema: {"score": "<label>", "reason": "<one sentence>"} '
    "Score labels: correct | fabrication | wrong_value | false_abstention | "
    "break_blindness | disambiguation_failure"
)

judge_user = (
    "Question: What was Malaysia's unemployment rate in 2022?\n"
    "Ground truth: 3.7%\n"
    'Response: "Malaysia\'s unemployment rate in 2022 was 3.7%."\n'
    "Response type: exact_answer\n"
    "Score this response."
)

print(f"Running judge 5 times...")
judge_results = []
for i in range(5):
    r, t = run([CLAUDE, "-p", "--system-prompt", JUDGE_SYSTEM, judge_user])
    raw = r.stdout.strip()
    try:
        parsed = json.loads(raw)
        score = parsed.get("score", "?")
        status = "OK"
    except json.JSONDecodeError:
        score = "PARSE_FAIL"
        status = "FAIL"
    judge_results.append((i, status, score, raw[:80], t))
    print(f"  run {i}: {status:4s}  score={score!r}  t={t:.2f}s  raw={raw[:60]!r}")

ok = sum(1 for r in judge_results if r[1] == "OK")
print(f"\n{ok}/5 valid JSON")


# ---------------------------------------------------------------------------
# 5.2  Markdown fence stripping — does claude wrap JSON in ```?
# ---------------------------------------------------------------------------
header("5.2  Markdown fence stripping")

# Ask without system prompt forcing bare JSON — see natural behavior
r, _ = run([CLAUDE, "-p",
            'Reply with this exact JSON and nothing else: {"key": "value"}'])
raw = r.stdout.strip()
print(f"Raw output: {raw!r}")
has_fences = "```" in raw
print(f"Contains markdown fences: {has_fences}")

# Test the fence-stripping regex
def extract_json(text: str) -> dict:
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    return json.loads(stripped.strip())

try:
    parsed = extract_json(raw)
    print(f"extract_json() succeeded: {parsed}")
except Exception as e:
    print(f"extract_json() failed: {e}")


# ---------------------------------------------------------------------------
# 5.3  Judge reliability on borderline cases
# ---------------------------------------------------------------------------
header("5.3  Judge reliability — 3 borderline cases")

borderlines = [
    ("numerically close but wrong",
     "Malaysia's unemployment rate in 2022 was approximately 3.8%."),
    ("hedged answer",
     "Malaysia's unemployment rate in 2022 was around 3-4%, I believe."),
    ("right number buried",
     "It's hard to say exactly, but various sources suggest figures "
     "in the 3.7% range for that period, though this varies by methodology."),
]

ground_truth = "3.7%"
for label, response in borderlines:
    print(f"\n  Case: {label}")
    scores = []
    for _ in range(3):
        user_msg = (
            f"Question: What was Malaysia's unemployment rate in 2022?\n"
            f"Ground truth: {ground_truth}\n"
            f'Response: "{response}"\n'
            "Response type: exact_answer\nScore this response."
        )
        r, _ = run([CLAUDE, "-p", "--system-prompt", JUDGE_SYSTEM, user_msg])
        raw = r.stdout.strip()
        try:
            scores.append(extract_json(raw).get("score", "?"))
        except Exception:
            scores.append("PARSE_FAIL")
    consistent = len(set(scores)) == 1
    print(f"  Scores across 3 runs: {scores}  consistent={consistent}")


# ---------------------------------------------------------------------------
# 5.4  --system-prompt flag (already confirmed in --help)
# ---------------------------------------------------------------------------
header("5.4  --system-prompt flag + --json-schema for structured output")

# Test --json-schema for forcing structured judge output
schema = json.dumps({
    "type": "object",
    "properties": {
        "score": {"type": "string"},
        "reason": {"type": "string"}
    },
    "required": ["score", "reason"]
})

r, _ = run([
    CLAUDE, "-p",
    "--json-schema", schema,
    "--system-prompt", JUDGE_SYSTEM,
    (
        "Question: What was Malaysia's unemployment rate in 2022?\n"
        "Ground truth: 3.7%\n"
        'Response: "3.7%"\n'
        "Response type: exact_answer\nScore this response."
    )
])
print(f"With --json-schema:")
print(f"  exit code : {r.returncode}")
print(f"  stdout    : {r.stdout.strip()[:300]!r}")
try:
    parsed = json.loads(r.stdout.strip())
    print(f"  parsed OK : {parsed}")
except Exception as e:
    print(f"  parse err : {e}")


# ---------------------------------------------------------------------------
# 6.1  Wall-clock timing — bare LLM + judge (MCP calls need Phase 2)
# ---------------------------------------------------------------------------
header("6.1  Wall-clock timing — bare LLM and judge calls")

print("Bare LLM calls (5 samples):")
bare_times = []
for i in range(5):
    _, t = run([CLAUDE, "-p", "What is the capital of France? One word."])
    bare_times.append(t)
    print(f"  {t:.2f}s")

print("\nJudge calls with --system-prompt (5 samples):")
judge_times = []
for i in range(5):
    r, t = run([CLAUDE, "-p", "--system-prompt", JUDGE_SYSTEM,
                'Q: Capital of France? GT: Paris. Response: "Paris." Score.'])
    judge_times.append(t)
    print(f"  {t:.2f}s")

def stats(times):
    s = sorted(times)
    return {
        "mean": sum(s) / len(s),
        "p50": s[len(s) // 2],
        "max": s[-1]
    }

bs = stats(bare_times)
js = stats(judge_times)
print(f"\nBare LLM  — mean={bs['mean']:.2f}s  p50={bs['p50']:.2f}s  max={bs['max']:.2f}s")
print(f"Judge     — mean={js['mean']:.2f}s  p50={js['p50']:.2f}s  max={js['max']:.2f}s")

# Estimate total benchmark time (no MCP overhead yet)
n_questions = 30
n_conditions = 3  # bare_llm + mcp_full + mcp_no_breakcheck
n_calls = n_questions * n_conditions + n_questions  # benchmark + judge
estimate_serial = n_calls * bs["mean"]
print(f"\nEstimate (serial, {n_calls} calls at {bs['mean']:.2f}s mean): {estimate_serial/60:.1f} min")


# ---------------------------------------------------------------------------
# 6.2  Token count exposure in --output-format json
# ---------------------------------------------------------------------------
header("6.2  Token count / cost exposure")

r, _ = run([CLAUDE, "-p", "--output-format", "json",
            "What is 2 + 2?"])
try:
    data = json.loads(r.stdout)
    # Look for token-related fields
    token_keys = [k for k in (data.keys() if isinstance(data, dict) else [])
                  if any(w in k.lower() for w in ["token", "cost", "usage", "input", "output"])]
    if token_keys:
        print(f"Token-related keys found: {token_keys}")
        for k in token_keys:
            print(f"  {k}: {data[k]}")
    else:
        print(f"No token/cost fields in JSON output.")
        print(f"All keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
except Exception as e:
    print(f"Parse error: {e}")


# ---------------------------------------------------------------------------
# 7.1  --model flag — full model ID
# ---------------------------------------------------------------------------
header("7.1  --model flag")

for model_id in ["claude-sonnet-5", "claude-haiku-4-5"]:
    r, t = run([CLAUDE, "-p", "--model", model_id, "Reply with 'ok'."])
    print(f"  model={model_id}")
    print(f"    exit={r.returncode}  out={r.stdout.strip()!r}  t={t:.2f}s")
    if r.returncode != 0:
        print(f"    stderr: {r.stderr.strip()[:200]!r}")


# ---------------------------------------------------------------------------
# 7.2  Headless auth — what fails when ANTHROPIC_API_KEY stripped
#      (safe: we strip only the API key var, not keychain; documents the failure mode)
# ---------------------------------------------------------------------------
header("7.2  Headless auth — failure mode without API key")

stripped_env = {k: v for k, v in os.environ.items()
                if k not in ("ANTHROPIC_API_KEY",)}
try:
    r, _ = run([CLAUDE, "-p", "--bare", "Reply with 'ok'."],
               extra_env={"ANTHROPIC_API_KEY": ""},
               timeout=20)
    print(f"exit code : {r.returncode}")
    print(f"stdout    : {r.stdout.strip()[:200]!r}")
    print(f"stderr    : {r.stderr.strip()[:300]!r}")
    if r.returncode == 0:
        print("Succeeded even without API key — uses keychain/OAuth")
except subprocess.TimeoutExpired:
    print("Timed out — likely blocked waiting for interactive auth")


print("\n" + "=" * SECTION_WIDTH)
print("  ALL CHECKS COMPLETE")
print("=" * SECTION_WIDTH)
