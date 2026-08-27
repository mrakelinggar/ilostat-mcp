# ILOSTAT MCP Benchmark — Schema & Methodology

## Purpose
Measure whether the MCP-equipped agent reduces hallucination vs. a bare LLM,
and whether it correctly handles methodology breaks in ILOSTAT series —
a failure mode no other public data MCP explicitly tests for.

## Categories (assign one per question)

| Category | Definition |
|---|---|
| `answerable_clean` | Real data exists, no break in the requested range |
| `answerable_break` | Real data exists, but a methodology break (SOURCE change or OBS_PRE_BREAK_VALUE) falls inside the requested range |
| `unanswerable_no_data` | No data exists for this country/indicator/period combination |
| `unanswerable_wrong_entity` | Category error — asks for something ILOSTAT doesn't track, or confuses the entity type |
| `ambiguous` | Entity name collides with something else (e.g. "Georgia" country vs. US state) |
| `comparative` | Requires correctly pulling and comparing 2+ entities |

## Question object schema

```json
{
  "id": "string, unique, e.g. 'q001'",
  "category": "one of the categories above",
  "question": "the exact natural-language prompt to give the agent, verbatim, no hints",
  "entities": {
    "countries": ["ISO3 codes, e.g. 'MYS', 'SGP'"],
    "indicator_theme": "employment | wages",
    "dataflow_id": "ILOSTAT dataflow ID if known, else null",
    "start_year": "int or null",
    "end_year": "int or null"
  },
  "ground_truth": {
    "has_data": "bool — does real ILOSTAT data exist for this query at all",
    "values": "array of {year, value, unit} — filled in by hand from ILOSTAT before testing, or null if has_data is false",
    "as_of_date": "date you pulled the ground truth, so you can re-verify later if ILOSTAT revises",
    "has_break": "bool — is there a detected/known methodology break inside the requested range",
    "break_years": "array of years where a break occurs, or null",
    "correct_response_type": "one of: exact_answer | abstain_no_data | disambiguate | warn_and_answer (answer but disclose the break)"
  },
  "notes": "anything a human grader needs to know — e.g. why this is a trick question"
}
```

## Response scoring (apply this per question, per condition tested)

| Score label | Meaning |
|---|---|
| `correct` | Matches `correct_response_type` and, where applicable, the right values |
| `fabrication` | Gave a specific number when `has_data` is false |
| `break_blindness` | Computed/stated a trend or change across a `has_break=true` range without disclosing it |
| `false_abstention` | Said "no data" when `has_data` is true |
| `disambiguation_failure` | Answered using the wrong entity for an `ambiguous` question without asking/clarifying |
| `wrong_value` | Answered with data that exists, but the number itself is wrong |

## Conditions to run each question through

1. **bare_llm** — no tools, plain chat
2. **mcp_full** — your MCP with break-detection active
3. **mcp_no_breakcheck** (optional but recommended) — same MCP, break-detection disabled, isolates how much of the improvement is from that specific feature vs. tool access alone

## Reporting

For each condition, compute across all questions:
- Fabrication rate = fabrication / total
- Break-blindness rate = break_blindness / total `answerable_break` questions
- Abstention accuracy = correct abstentions / total `unanswerable_*` questions
- False-abstention rate = false_abstention / total `answerable_*` questions

Report as one small table in the README. This table *is* your evidence — don't
editorialize beyond it.
