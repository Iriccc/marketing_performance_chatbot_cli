# Marketing Performance Chatbot (CLI Version)

A terminal-based chatbot that answers natural-language questions about a marketing performance dataset (`marketing_data.csv`).

The system converts user questions into a structured **QueryPlan (JSON)** using an LLM (AWS Bedrock), then executes that plan deterministically using **pandas**.


---

# Features

- CLI interface (no Streamlit)
- Optional local authentication (bcrypt + users.yaml)
- LLM-powered QueryPlan generation (AWS Bedrock – Claude 3 / 3.5)
- Deterministic pandas execution
- Row-level provenance tracking
- Short memory (last N user + assistant messages)
- Intelligent follow-up handling via LLM
- Structured logging for debugging

---

# How It Works

1. User enters a natural-language question.
2. Router classifies it:
   - `dataset`
   - `meta`
   - `out_of_scope`
   - `terminate`
3. If dataset:
   - LLM generates strict JSON `QueryPlan`
4. QueryEngine executes plan using pandas.
5. ResponseBuilder formats:
   - Result summary
   - Rows used
   - Date range
   - Sample `row_id`s
6. CLI prints formatted output.
---

# Repository Structure

marketing_performance_chatbot/
│
├── app/
│   ├── main.py          # CLI entrypoint
│   ├── chat_loop.py     # Terminal chat loop
│   ├── auth.py          # Optional login
│
├── src/
│   ├── config.py
│   │
│   ├── data/
│   │   ├── loader.py
│   │   └── schema.py
│   │
│   ├── engine/
│   │   ├── query_plan.py
│   │   ├── query_engine.py
│   │   └── response.py
│   │
│   └── llm/
│       ├── router.py
│       └── prompts.yaml
│
├── marketing_data.csv
├── users.yaml
├── .env.example
├── requirements.txt
├── ARCHITECTURE.md
├── QUICKSTART.md
└── RUNBOOK.md
---

# Dataset

Expected CSV columns:

Year
Quarter
Month
Week
Date
Country
Media Category
Media Name
Communication
Campaign Category
Product
Campaign Name
Revenue
Cost

During loading:

- Columns normalized to snake_case
- `profit = revenue - cost`
- `row_id` generated using deterministic SHA256 hash
- Types coerced and validated
- Invalid rows cause explicit errors
---

# QueryPlan Schema

The LLM generates structured JSON:


{
  "intent": "aggregate | top_n | trend | unknown",
  "metrics": ["revenue", "cost", "profit"],
  "groupby": ["campaign_name", "country", ...],
  "time_range": {
    "type": "all | year | quarter | last_quarter | last_n_years",
    "year": 2023,
    "quarter": 2,
    "n_years": 3
  },
  "filters": [
    {"field": "country", "op": "=", "value": "Italy"}
  ],
  "top_n": 5,
  "sort_by": {"field": "revenue", "direction": "desc"}
}

This ensures:

- No hallucinated SQL
- No unsafe execution
- Fully deterministic results
---

# Follow-Ups

Follow-ups are handled by the LLM using:

- Conversation history
- Previous QueryPlan JSON

Examples:

Total revenue in 2022?
Now only for Country = Italy
Same but last quarter
Ok, and in Q3?
Show trend for the last 3 years

The model rewrites the previous plan accordingly.
---

# Optional Authentication

Disabled by default.

Enable in `.env`:

ENABLE_AUTH=true

Create `users.yaml`:

yaml
users:
  - username: demo
    password_hash: "<bcrypt-hash>"

Passwords are bcrypt hashed.
---

# Logging

The app uses structured logging.

Logs include:

- Classification results
- Raw LLM outputs
- Parsed QueryPlan
- Validation errors
- Execution summaries
---

# Running the Project

See:

QUICKSTART.md or DEMO.md
---

# Example Questions

Total revenue in 2024?
Top 5 campaign names by revenue last quarter
Revenue and cost trend by month in 2023
Which media categories had the highest profit in Q2 2023?
Now only for Product = X
Same but last quarter
---

# Architectural Philosophy


Natural Language
        ↓
LLM → QueryPlan (JSON)
        ↓
Deterministic Pandas Engine
        ↓
Formatted CLI Output
