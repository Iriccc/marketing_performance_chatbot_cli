# ARCHITECTURE

This project answers natural-language questions about `marketing_data.csv`.

It converts user questions into a structured **QueryPlan (JSON)** using an LLM (AWS Bedrock Claude), then executes that plan deterministically using pandas.

**Important:** the LLM never computes numbers. It only generates a plan. All metrics are computed locally.

---

## 1. Dataset model

### Raw CSV columns

The CSV is expected to contain:

"Year","Quarter","Month","Week","Date","Country","Media Category","Media Name","Communication",
"Campaign Category","Product","Campaign Name","Revenue","Cost"

### Normalized columns (snake_case)

During loading, columns are normalized to:

- year
- quarter
- month
- week
- date
- country
- media_category
- media_name
- communication
- campaign_category
- product
- campaign_name
- revenue
- cost

This avoids column-name inconsistencies and makes query execution predictable.

### Derived fields

The loader also computes:

- profit = revenue - cost
- row_id = deterministic SHA256-based id (truncated)

`row_id` is generated from stable row fields and is used as provenance (“where did this come from?”).

---

## 2. Core execution flow (CLI)

1) User types a question in the CLI  
2) Router classifies the message into one of:
   - dataset
   - meta
   - out_of_scope
   - terminate  
3) If dataset -> planner generates strict QueryPlan JSON  
4) QueryEngine executes the plan on the pandas DataFrame  
5) ResponseBuilder formats:
   - short human-readable summary
   - provenance (rows used, date range, sample row_ids)  
6) CLI prints:
   - assistant message
   - result table
   - sample subset rows (optional)

---

## 3. QueryPlan schema

Defined in `src/engine/query_plan.py`.

A QueryPlan contains:

### intent

- aggregate -> totals or grouped sums
- top_n -> grouped sums + sorting + head(top_n)
- trend -> time series grouped by time dimensions
- unknown -> not a dataset computation request

### metrics

Allowed metrics:

- revenue
- cost
- profit

### groupby

Allowed group-by dimensions:

- year, quarter, month, week
- country
- media_category, media_name
- communication, campaign_category
- product
- campaign_name

### time_range

{
  "type": "all | year | quarter | last_quarter | last_n_years",
  "year": 2022,
  "quarter": 2,
  "n_years": 3
}


Rules:
- type="all" -> ignore year/quarter/n_years
- type="year" -> year required
- type="quarter" -> year and quarter required
- type="last_quarter" -> engine computes last available quarter
- type="last_n_years" -> n_years required

### filters

Equality only:


[
  { "field": "country", "op": "=", "value": "Denmark" },
  { "field": "product", "op": "=", "value": "X" }
]


### top_n and sort_by

Used for intent="top_n":


{
  "top_n": 5,
  "sort_by": { "field": "revenue", "direction": "desc" }
}


---

## 4. Example QueryPlans

### Example A — Total revenue in 2024


{
  "intent": "aggregate",
  "metrics": ["revenue"],
  "groupby": [],
  "time_range": { "type": "year", "year": 2024, "quarter": null, "n_years": null },
  "filters": [],
  "top_n": null,
  "sort_by": null
}


### Example B — Top 5 campaigns by revenue last quarter


{
  "intent": "top_n",
  "metrics": ["revenue"],
  "groupby": ["campaign_name"],
  "time_range": { "type": "last_quarter", "year": null, "quarter": null, "n_years": null },
  "filters": [],
  "top_n": 5,
  "sort_by": { "field": "revenue", "direction": "desc" }
}


### Example C — Revenue and cost trend by month in 2022


{
  "intent": "trend",
  "metrics": ["revenue", "cost"],
  "groupby": ["year", "month"],
  "time_range": { "type": "year", "year": 2022, "quarter": null, "n_years": null },
  "filters": [],
  "top_n": null,
  "sort_by": null
}


---

## 5. Follow-ups (LLM-based)

Follow-ups are resolved by the planner because we pass:

- conversation history (last turns)
- previous QueryPlan JSON (or null)

The LLM decides whether to:

- modify the previous plan
- or create a new plan

Examples:

- "same but last quarter"
- "only for Country = Italy"
- "now in Q3 2023"
- "same but for the following year"
- "last 3 years"

---

## 6. Provenance (anti-hallucination layer)

The system prints provenance from the exact subset used:

- rows_used
- date_range (min -> max)
- sample_row_ids

This ensures transparency and reduces hallucination risk.

---

## 7. Memory

Stored in `app/memory.py`:

- last 5 user messages
- last 5 assistant messages
- last QueryPlan

Used for:

- follow-ups
- meta questions ("what did I ask before?")

Memory is intentionally small to keep context stable and predictable.

---

## 8. High-level architecture diagram


User (CLI)
  |
  v
Router (LLM classifier)
  |----------------------------------------\
  |                                         \
  v                                          v
Planner (LLM -> QueryPlan JSON)            Meta responder (LLM -> text)
  |                                       |                      |
  v                                       v                      v
QueryEngine (pandas)            Answers user questions    Terminates conversation
  |
  v
ResponseBuilder (summary + provenance)
  |
  v
Terminal output (Rich tables)


---

## 9. Design insights

- LLM = reasoning + planning only
- pandas = deterministic execution
- strict JSON schema for QueryPlan
- provenance always included
- separation of concerns:
  - data
  - engine
  - llm
  - app
- predictable, testable execution path