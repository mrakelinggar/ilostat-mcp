# ILOSTAT MCP — Use Case Specification

---

## What this project is

Claude and other AI assistants are often asked labour market questions — unemployment rates, wage trends, country comparisons. They answer confidently even when they don't actually know. They produce plausible-sounding numbers from their training data, which may be outdated, approximated, or simply made up. There is no easy way to tell the difference.

The ILOSTAT MCP is a server that sits between Claude and ILOSTAT — the ILO's official labour statistics database — so Claude can look up real, verified numbers for 335 countries instead of guessing.

Two things make it more than a basic data lookup:

**1. A hallucination benchmark** — a formal test measuring exactly how often Claude fabricates labour statistics versus how often it gets them right when equipped with this server. Scored across 30 questions and three conditions: no tools, full tools, tools without break detection. Not a demo — actual numbers.

**2. Methodology break detection** — ILOSTAT's data sometimes switches survey source mid-series without any label (a country moves from a household survey to a labour force survey). Computing a trend across that switch produces a number that looks precise but is methodologically meaningless. This server detects those switches automatically and warns before any calculation. A bare AI assistant has no access to this information and will compute the trend anyway.

---

## What you can ask

"Reliable" means: the same query always hits the same data source, applies the same filters, runs the same calculation, and returns the same number.

| Indicator | Query type | Example question | What you get back |
|---|---|---|---|
| Unemployment | Single point | "What was Malaysia's unemployment rate in 2022?" | One number (%) for Malaysia 2022, with the survey source named |
| Unemployment | Single point | "What is France's current unemployment rate?" | Most recent available year's rate, with year stated explicitly |
| Unemployment | Single point | "Did Brazil's unemployment go up or down in 2018?" | The 2018 rate vs. 2017, with direction stated |
| Unemployment | Time series | "Show me Spain's unemployment rate from 2010 to 2023" | Year-by-year table. Break warning included if methodology changed mid-range. |
| Unemployment | Time series | "How has Thailand's unemployment changed over the last decade?" | Year-by-year series for the last 10 available years. Clean series stated as such. |
| Unemployment | Time series | "What was Nigeria's unemployment each year between 2015 and 2022?" | Year-by-year series with explicit break warning at 2019 (survey source changed) |
| Unemployment | Year-on-year change | "What was the year-on-year change in Germany's unemployment from 2021 to 2022?" | Percentage point change between 2021 and 2022, with both values shown |
| Unemployment | Compound growth | "What's the CAGR of Pakistan's unemployment from 2010 to 2020?" | CAGR figure with explicit warning that 5 methodology breaks exist in this range |
| Unemployment | Trend | "Is Italy's unemployment trending up or down since 2015?" | Trend direction (up/down/flat), slope, and fit quality over the available data |
| Unemployment | Comparison | "Which has higher unemployment: Spain or Italy in 2022?" | Both values side by side, clear statement of which is higher |
| Unemployment | Comparison | "Compare unemployment trends in France and Germany from 2015 to 2023" | Both series side by side, trend direction for each, break warnings if applicable |
| Unemployment | Comparison | "Which improved more: Brazil or Argentina?" | Change for both countries over the period, with a clear comparative statement |
| Unemployment | Data existence | "Does ILOSTAT have unemployment data for Yemen?" | "No national survey data available for Yemen. ILO modelled estimates exist but are imputed, not observed." |
| Unemployment | Data existence | "What's the most recent unemployment data for Singapore?" | Latest available year and value |
| Wages | Single point | "What was the average monthly wage in Singapore in 2021?" | One number in local currency (SGD), year confirmed, survey source named |
| Wages | Single point | "What did workers earn on average in Germany in 2022?" | Average monthly wage in EUR for Germany 2022, survey source named |
| Wages | Single point | "What is France's average monthly wage?" | Most recent available year in EUR, year stated explicitly |
| Wages | Time series | "Show me Thailand's wage data from 2014 to 2022" | Year-by-year wages in THB, with break warnings at 2013 and 2014 |
| Wages | Time series | "How have wages changed in Pakistan over the last decade?" | Year-by-year wage series with warnings for the multiple methodology breaks |
| Wages | Time series | "What's been happening to wages in Vietnam since 2018?" | Year-by-year series from 2018 to latest available, clean or with break warning |
| Wages | Year-on-year change | "How much did wages grow in France from 2019 to 2023?" | Percentage change 2019–2023, with both endpoint values shown |
| Wages | Compound growth | "What's the CAGR of wages in Germany from 2015 to 2022?" | CAGR figure, with break warning if a methodology change falls in that range |
| Wages | Trend | "Are wages in Singapore growing or declining?" | Trend direction, slope, fit quality over all available data |
| Wages | Comparison | "Who pays more: France or Germany?" | Both most-recent-year average monthly wages in local currency |
| Wages | Comparison | "Which had higher wage growth 2018–2022: Thailand or Vietnam?" | Change for both countries over the period, any break warnings, comparative statement |
| Wages | Comparison | "Compare wages in Singapore and Malaysia" | Both most-recent-year values in local currency, years stated |
| Wages | Data existence | "Does ILOSTAT have wage data for Georgia?" | "Yes — average monthly earnings data is available for Georgia (the country). If you meant the US state, ILOSTAT only covers countries." |
| Youth unemployment | Single point | "What was South Africa's youth unemployment in 2021?" | Youth unemployment rate for South Africa 2021, with note that "youth" here means ages 15–29 (the closest available ILOSTAT band; ILO's formal definition is 15–24) |
| Youth unemployment | Time series | "How has youth unemployment changed in South Africa over the past 5 years?" | Year-by-year youth unemployment series (ages 15–29), age band stated once |

---

## Packaged workflow

| Workflow | How to trigger | What it does | What you get |
|---|---|---|---|
| Labour market snapshot | "Give me a labour market snapshot for Malaysia" | Chains: unemployment rate (latest year + year-on-year) → wage trend (last 5 years) → any break warnings for either series | Current unemployment rate and direction, wage trend and direction, any methodology caveats. All sourced from ILOSTAT survey data. |

---

## What you can't ask — and what the tool says

| Question | Why it can't be answered | What the tool says |
|---|---|---|
| "What's unemployment for 25–34 year olds in France?" | ILOSTAT has no 25–34 age band. Available slices are 15–24 (youth) and 25+ (older adults). | "ILOSTAT doesn't publish unemployment data for the 25–34 age band. The closest available breakdowns are ages 15–24 or 25 and above. Would either of those help?" |
| "What's the male vs female wage gap in Germany?" | The tool retrieves male wages and female wages separately, but computing a gap is not a supported calculation. | "I can retrieve average monthly wages for German men and German women separately, but I don't compute a wage gap directly. Would you like both numbers so you can compare?" |
| "What are hourly wages in France?" | Hourly wages come from a different ILOSTAT dataset not covered in v1. | "This tool covers average monthly wages. ILOSTAT does publish hourly earnings separately, but that's not supported here in v1." |
| "What's unemployment by education level in Brazil?" | Education-disaggregated unemployment is a different dataset not covered in v1. | "ILOSTAT has unemployment broken down by education level, but that dataset isn't supported by this tool. I can give you Brazil's total unemployment rate." |
| "What's the labour force participation rate in Brazil?" | Labour force participation is a different indicator — not unemployment, not wages. | "Labour force participation isn't covered by this tool, which focuses on unemployment rates and average wages. ILOSTAT does publish that data — you'd need to query it directly." |
| "What's the rural unemployment rate in India?" | Urban/rural disaggregation is a different dataset with a different structure. | "Rural vs. urban unemployment breakdowns come from a different ILOSTAT dataset. I can give you India's national total unemployment rate." |
| "What industries have the highest wages in Germany?" | Wages by sector is a different dataset (earnings by economic activity). | "Wages broken down by industry aren't supported here. This tool covers average wages across all employees. ILOSTAT does publish sector-level earnings separately." |
| "What's France's GDP?" | GDP is a macroeconomic indicator from a different database (World Bank, IMF). | "GDP isn't in ILOSTAT — that's a World Bank or IMF indicator. This tool only covers employment and wage data." |
| "What will Malaysia's unemployment be in 2030?" | No observed data exists for 2030. | "There's no observed unemployment data for 2030 — it hasn't happened yet. I won't return ILO projections as if they were real survey data." |
| "What's the GCC unemployment rate?" | GCC is a regional bloc, not a country. ILOSTAT has no GCC aggregate code. | "ILOSTAT doesn't have a GCC aggregate — it's organised by country, not regional blocs. I can look up individual GCC members: Saudi Arabia, UAE, Qatar, Kuwait, Bahrain, or Oman." |
| "What's the World Bank's unemployment rate?" | The World Bank is an organisation, not a country or economy. | "The World Bank is an organisation — it doesn't have an unemployment rate. Did you mean a specific country?" |
| "What is the ILO's GDP?" | The ILO is an organisation; GDP is not a labour market indicator. | "The ILO is an international organisation — it doesn't have a GDP. And GDP is outside the scope of this tool regardless." |
| "What's the literacy rate in Malaysia?" | Literacy is a UNESCO/education indicator, not labour market data. | "Literacy rate is outside the scope of this tool. UNESCO and World Bank publish literacy statistics." |
| "What's the inflation rate in Germany?" | Inflation is a macroeconomic indicator, not a labour market indicator. | "Inflation data isn't in ILOSTAT. That's tracked by the IMF, World Bank, or Eurostat. This tool covers employment and wage data only." |

---

## Combo queries — how the MCP handles mixed and multi-part questions

Users rarely ask one clean question. The behaviour rule that applies to all combo queries:

> Answer every in-scope part using tools. Explicitly decline every out-of-scope part and say why. Never answer an out-of-scope part from training knowledge — not even as a helpful supplement. Never silently skip part of a question; if you only partially answered it, say so.

The dangerous failure mode is not a wrong number — it is Claude answering the unsupported part from training memory and presenting it alongside tool results without flagging the source difference. That looks like a complete answer but mixes verified data with a hallucination.

| Combo type | Example | How it is handled | What the user sees |
|---|---|---|---|
| In-scope + out-of-scope | "UK unemployment last 5 years and a 2-year forecast" | Tool call for the historical part returns clean data. Future years have no survey data — the tool returns `has_data: false` and does not use ILO projections as a substitute. | Historical series answered in full. Explicit statement that no survey-based forecast exists. Redirect to IMF World Economic Outlook for forecasts. No projection returned as if it were real data. |
| Two in-scope indicators | "What are unemployment AND wages in Germany in 2022?" | Two sequential tool calls — one for each indicator. Both return clean data. | Both numbers presented side by side, each with its source named and its unit stated. |
| In-scope + out-of-scope indicator | "Unemployment AND inflation for France" | One tool call for unemployment. No tool call for inflation — it is the wrong database. | Unemployment answered from ILOSTAT. Explicit statement that inflation is not in ILOSTAT and naming where to find it. Inflation figure NOT drawn from training knowledge. |
| In-scope with unavailable disaggregation | "Youth unemployment for ages 25–34 in Brazil" | Tool call returns youth unemployment for ages 15–29 — the closest available band. No 25–34 band exists. | Result returned with explicit statement of the actual age band used (15–29, not 25–34). User is told why the exact band they asked for is not available. |
| Ambiguous entity + valid query | "Unemployment in Georgia for the last 5 years" | No tool call made until ambiguity is resolved. | Claude asks: "Did you mean Georgia the country (in the Caucasus) or the US state of Georgia? ILOSTAT covers countries — if you mean the state, I don't have data for it." Tool call happens only after the user confirms. |
| Ambiguous entity — one option has data, one doesn't | "What is unemployment in Congo?" | No tool call until ambiguity is resolved. Republic of Congo (COG) returns 404; Democratic Republic of Congo (COD) has data. Claude cannot know this in advance — it must ask first. | Claude asks which Congo. After confirmation, tool call is made. If user says "Republic of Congo," tool returns `has_data: false` and Claude says so explicitly. |
| Multiple countries, one valid | "Compare unemployment in France and the GCC" | Tool call for France succeeds. GCC has no country code in ILOSTAT — not attempted. | France's unemployment returned. Explicit statement that GCC is not a country in ILOSTAT, with offer to look up individual member states instead. |
| In-scope calculation + unsupported calculation | "Male and female unemployment in Spain, plus the gender gap" | Two tool calls (male and female filters on the same flow). The gender gap is arithmetic Claude computes from those two numbers — not a tool call. | Male rate, female rate, and the computed gap all presented. Gap clearly labelled as derived from the two retrieved figures. |
| Fully out of scope | "GDP and inflation for Germany" | No tool calls. Nothing in this question is covered by the MCP. | Full decline: neither indicator is in ILOSTAT. Redirect to appropriate sources (World Bank for GDP, IMF/Eurostat for inflation). No figures drawn from training knowledge. |
