# DEMO
This document shows a full example interaction with the **Marketing Performance Chatbot (CLI version)**.
The goal is to demonstrate:

- Dataset computations
- Follow-ups
- Trends
- Meta questions
- Out-of-scope handling
- Conversation termination
- Provenance output
---

## 1 Start the Application

```bash
python -m app.main
```

If authentication is enabled (`ENABLE_AUTH=true`), you will see:

```
╭──────────── Login ────────────╮
│ Authentication required.      │
╰───────────────────────────────╯

Username: demo
Password: ********    demo123 is the only valid password at the moment
```

If authentication is disabled, the CLI starts immediately.
---

## 2 Basic Aggregate Question

User:

```
Total revenue in 2022?
```

System flow:

- Classifier -> route="dataset"
- Planner -> generates QueryPlan JSON
- QueryEngine -> executes aggregation
- ResponseBuilder -> formats output

Example output:

```
Result (total): revenue: 30,357,817.33

Data used: 4321 rows, date range 2022-01-03 -> 2022-12-26.
Sample row_id(s): a9697a7fe717a004, cde1a15f66060a74, 74da1dbfd2a8f17c
```
---

## 3 Top-N Ranking

User:

```
Top 5 campaign names by revenue in Q2 2023
```

Planner builds:

```json
{
  "intent": "top_n",
  "metrics": ["revenue"],
  "groupby": ["campaign_name"],
  "time_range": {"type":"quarter","year":2023,"quarter":2,"n_years":null},
  "filters": [],
  "top_n": 5,
  "sort_by": {"field":"revenue","direction":"desc"}
}
```

Example output:

```
Top results:
1. Campaign 317 — revenue: 3,626,900.63
2. Campaign 314 — revenue: 1,586,605.94
3. Campaign 328 — revenue: 1,175,438.69
4. Campaign 331 — revenue: 533,025.13
5. Campaign 140 — revenue: 447,165.01

Data used: 1157 rows, date range 2023-04-03 -> 2023-06-26.
Sample row_id(s): e6aee7bf664f7b3e, c7e25492b193c402
```
---

## 4 Follow-Up Question

User:

```
Now only for Country = Denmark
```

Planner receives:

- Previous plan JSON
- Conversation history

It modifies the filters:

```json
"filters": [
  {"field":"country","op":"=","value":"Denmark"}
]
```

If no rows match:

```
I couldn't find any rows matching your request.

Try changing the year/quarter or removing some filters.
```
---

## 5 Time-Based Follow-Up

User:

```
Same but last quarter
```

Planner modifies only:

```json
"time_range": {"type":"last_quarter"}
```

Execution happens deterministically via pandas.
---

## 6 Trend Example

User:

```
What is the monthly revenue trend for 2022?
```

Planner generates:

```json
{
  "intent": "trend",
  "metrics": ["revenue"],
  "groupby": ["year","month"],
  "time_range": {"type":"year","year":2022,"quarter":null,"n_years":null},
  "filters": [],
  "top_n": null,
  "sort_by": null
}
```

CLI output:

```
Trend table computed (grouped by year, month). Metrics: revenue.
```

Then a formatted table:

```
year | month | revenue
-----|-------|---------
2022 | 1     | ...
2022 | 2     | ...
...
```
---

## 7 Last N Years Example

User:

```
What has been the revenue trend over the last 3 years?
```

Planner generates:

```json
"time_range": {"type":"last_n_years","year":null,"quarter":null,"n_years":3}
```

Execution filters the last 3 available years and groups by year.
---

## 8 Meta Question

User:

```
What can you do?
```

Classifier -> route="meta"

LLM answers using `meta_system` prompt:

```
I can extract data, compute totals, identify trends,
rank campaigns, and apply filters to the marketing dataset.
I cannot provide graphics or external information.
```
---

## 9 Conversation History Question

User:

```
What did I ask you before?
```

Classifier -> route="meta"

Planner not involved.

LLM uses conversation memory to answer.
---

## 10 Out-of-Scope Question

User:

```
What is the weather in Copenhagen?
```

Classifier -> route="out_of_scope"

Response:

```
I can only answer questions related to the marketing dataset.
Please ask about revenue, campaigns, trends, or filters.
```
---

## 11 Terminating the Conversation

User:

```
exit
```

-> keyword for termination  
No LLM involved here, we return a standard message and close the interaction.

Otherwise, User can say:

```
I want to end this conversation
```

Classifier -> route="terminate"

Response:

```
Session closed. Goodbye.
```

CLI loop exits.
---

## 12 Debugging (Logging)

If logging level is INFO or DEBUG:

You will see:

- classifier_raw
- classifier_route
- planner_raw
- planner_parsed
- validation errors (if any)

This allows to verify easily:

- LLM JSON correctness
- routing decisions
- follow-up handling
---

## 13 Testing

The project includes automated tests to verify that:

- QueryEngine executes aggregations, top-N queries, and trends correctly
- Results are properly sorted and structured
- The real dataset (`marketing_data.csv`) is compatible with the engine

### Install test dependencies

```bash
pip install -r requirements-dev.txt
```

(Ensure `pytest` is installed.)
---

### Run all tests

From the project root:

```bash
python -m pytest -q
```

You should see output similar to:

```
4 passed in 1.12s
```
---

## 14 Determinism

Important architecture rule:

- LLM NEVER computes numbers
- LLM ONLY generates QueryPlan JSON
- Pandas performs ALL calculations
- ResponseBuilder formats results
- Provenance always shown
---

## Summary

This demo shows that the system supports:

- Aggregations
- Top-N rankings
- Trends
- Filters
- Follow-ups
- Meta questions
- Out-of-scope handling
```
