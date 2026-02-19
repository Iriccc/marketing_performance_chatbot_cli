"""
src/engine/query_plan.py

Defines the structured "QueryPlan" used to represent a user request.
A QueryPlan is produced by:
- the LLM planner (Bedrock) for new questions or follow-ups that modify the previous plan

Then QueryPlan is executed on the pandas DataFrame by query_engine.py.

"""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

# Allowed intents for the QueryPlan -- this is the main signal for the app to decide how to execute the plan and how to answer.
Intent = Literal["aggregate", "top_n", "trend", "unknown"]

# Allowed metrics to compute (normalized names)
Metric = Literal["revenue", "cost", "profit"]

# Allowed columns for filtering (normalized names)
FilterField = Literal[
    "year", "quarter", "month", "week",
    "country", "media_category", "media_name",
    "communication", "campaign_category",
    "product", "campaign_name",
]

# Allowed group-by dimensions (normalized names) 
# note that not all dimensions are valid for grouping (e.g. week), but we can keep it simple for now and let the execution engine decide how to handle invalid group-by fields.
GroupByField = Literal[
    "year", "quarter", "month", "week",
    "country", "media_category", "media_name",
    "product", "campaign_name",
]


class TimeRange(BaseModel):
    """
    A time slice used to restrict the dataset.

    Supported modes:
    - all: no time filter
    - year: a single year (e.g., 2024)
    - quarter: a specific year-quarter (e.g., 2023 Q2)
    - last_quarter: relative to the maximum year/quarter present in the dataset
    - last_n_years: relative to the maximum year present in the dataset, requires n_years parameter (e.g., last 3 years)
    """
    type: Literal["all", "year", "quarter", "last_quarter", "last_n_years"] = "all"
    year: Optional[int] = None
    quarter: Optional[int] = None  # 1..4
    n_years: Optional[int] = None  # used only for last_n_years


class Filter(BaseModel):
    """
    Represents a single filter condition, e.g. product = "X".
    For this project we only use "=".
    """
    field: FilterField
    op: Literal["="] = "="
    value: Any


class SortBy(BaseModel):
    """
    Sorting instructions for a result table.
    Example: sort_by field="revenue", direction="desc"
    """
    field: Metric
    direction: Literal["asc", "desc"] = "desc"


class QueryPlan(BaseModel):
    """
    Main structured request.

    - intent:
        aggregate: totals or grouped sums
        top_n: grouped sums + sorting + head(top_n)
        trend: time series grouped by a time dimension (default year,month)
        unknown: used when parsing failed or request is unsupported

    - metrics: which measures to compute (revenue/cost/profit)
    - groupby: which dimensions to group by
    - time_range: time restriction
    - filters: additional constraints (product/country/etc.)

    - top_n + sort_by: used only by top_n intent
    """
    intent: Intent = "unknown"

    metrics: list[Metric] = Field(default_factory=list)
    groupby: list[GroupByField] = Field(default_factory=list)

    time_range: TimeRange = Field(default_factory=TimeRange)
    filters: list[Filter] = Field(default_factory=list)

    top_n: Optional[int] = None
    sort_by: Optional[SortBy] = None
