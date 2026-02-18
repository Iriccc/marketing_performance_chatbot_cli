"""
src/engine/query_engine.py

Executes a QueryPlan on the marketing DataFrame.

The DataFrame is expected to be normalized by the loader:
- column names in snake_case
- date column parsed to datetime
- profit column present

The output is a pandas DataFrame.

It is also added an execution method that returns:
- the result table
- the filtered subset used for provenance sampling
"""

from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

from .query_plan import QueryPlan


@dataclass(frozen=True)
class ExecutionResult:
    """
    result_df: the aggregated output shown to the user
    subset_df: the row-level subset after applying time_range + filters
    """
    result_df: pd.DataFrame
    subset_df: pd.DataFrame


class QueryEngine:
    """
    Executes a QueryPlan on the marketing DataFrame.
    The DataFrame is expected to be normalized by the loader:
    - column names in snake_case
    - date column parsed to datetime
    - profit column present
    The output is a pandas DataFrame.
    """
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df

    def execute_with_subset(self, plan: QueryPlan) -> ExecutionResult:
        """
        Executes the QueryPlan and returns both the result DataFrame and the filtered subset used for provenance sampling.
        Useful for ensuring that provenance reflects the exact data used to produce the result.
        """
        subset = self._apply_time_range(self.df, plan)
        subset = self._apply_filters(subset, plan)

        if plan.intent == "aggregate":
            res = self._run_aggregate(subset, plan)
        elif plan.intent == "top_n":
            res = self._run_top_n(subset, plan)
        elif plan.intent == "trend":
            res = self._run_trend(subset, plan)
        else:
            raise ValueError(f"Unsupported intent: {plan.intent}")

        return ExecutionResult(result_df=res, subset_df=subset)

    def execute(self, plan: QueryPlan) -> pd.DataFrame:
        return self.execute_with_subset(plan).result_df

    @staticmethod
    def _apply_time_range(df: pd.DataFrame, plan: QueryPlan) -> pd.DataFrame:
        tr = plan.time_range
        if tr.type == "all":
            return df
        if tr.type == "year":
            if tr.year is None:
                raise ValueError("time_range.year is required for type=year")
            return df[df["year"] == tr.year]
        if tr.type == "quarter":
            if tr.year is None or tr.quarter is None:
                raise ValueError("time_range.year and time_range.quarter are required for type=quarter")
            return df[(df["year"] == tr.year) & (df["quarter"] == tr.quarter)]
        if tr.type == "last_quarter":
            return QueryEngine._slice_last_quarter(df)
        if tr.type == "last_n_years":
            if tr.year is None:
                raise ValueError("time_range.year is required for type=last_n_years")
            n = int(tr.n_years or 3) # default to last 3 years if n_years is not specified
            max_year = int(df["year"].max())
            start_year = max_year - n + 1
            df = df[df["year"] >= start_year] & (df["year"] <= max_year)
            return df
        return df

    @staticmethod
    def _slice_last_quarter(df: pd.DataFrame) -> pd.DataFrame:
        max_year = int(df["year"].max())
        max_q = int(df[df["year"] == max_year]["quarter"].max())
        if max_q == 1:
            y, q = max_year - 1, 4
        else:
            y, q = max_year, max_q - 1
        return df[(df["year"] == y) & (df["quarter"] == q)]

    @staticmethod
    def _apply_filters(df: pd.DataFrame, plan: QueryPlan) -> pd.DataFrame:
        out = df
        for f in plan.filters:
            if f.op == "=":
                out = out[out[f.field] == f.value]
        return out

    @staticmethod
    def _run_aggregate(df: pd.DataFrame, plan: QueryPlan) -> pd.DataFrame:
        """
        User request example: "What is the total revenue and profit for Q1 2023?"
            - intent: aggregate
            - metrics: ["revenue", "profit"]
            - time_range: {type: "quarter", year: 2023, quarter: 1}

        User request example: "What is the total revenue and profit by campaign for Q1 2023?"
            - intent: aggregate with groupby
            - metrics: ["revenue", "profit"]
            - groupby: ["campaign_name"]
            - time_range: {type: "quarter", year: 2023, quarter: 1}
        """
        if not plan.metrics:
            raise ValueError("aggregate requires at least one metric")
        agg_map = {m: "sum" for m in plan.metrics} #useful to use df.agg with multiple metrics
        if not plan.groupby:
            return df.agg(agg_map).to_frame().T # transpose to have a row and to_frame returns a DataFrame instead of a Series
        return df.groupby(plan.groupby, dropna=False).agg(agg_map).reset_index()

    @staticmethod
    def _run_top_n(df: pd.DataFrame, plan: QueryPlan) -> pd.DataFrame:
        """
        User request example: "What are the top 5 campaigns by revenue in Q2 2023?"
         - intent: top_n
         - metrics: ["revenue"]
         - groupby: ["campaign_name"]
         - time_range: {type: "quarter", year: 2023, quarter: 2}
         - top_n: 5
         - sort_by: {field: "revenue", direction: "desc"} default is descending by the first metric if not specified
        Note: top_n requires groupby, otherwise it doesn't make sense. 
        If sort_by is not specified, we can default to sorting by the first metric in descending order. 
        We can also allow ascending order if specified in sort_by.
        """
        if not plan.groupby:
            raise ValueError("top_n requires groupby (e.g., campaign_name)")
        if plan.top_n is None or plan.sort_by is None:
            raise ValueError("top_n requires top_n and sort_by")

        metrics = plan.metrics or ["revenue"]
        agg_map = {m: "sum" for m in metrics}

        res = df.groupby(plan.groupby, dropna=False).agg(agg_map).reset_index()
        res = res.sort_values(
            by=plan.sort_by.field,
            ascending=(plan.sort_by.direction == "asc"),
        )
        return res.head(plan.top_n)

    @staticmethod
    def _run_trend(df: pd.DataFrame, plan: QueryPlan) -> pd.DataFrame:
        """
        User request example: "What is the monthly revenue trend for 2023?"
         - intent: trend
         - metrics: ["revenue"]
         - groupby: ["year", "month"] (default for trend if not specified)
         - time_range: {type: "year", year: 2023}
            
        Note: trend is essentially an aggregate with a default groupby of time dimensions (year, month). 
        If the user doesn't specify groupby, we can default to ["year", "month"] for trend intent.
        """
        group = plan.groupby or ["year", "month"]
        metrics = plan.metrics or ["revenue", "cost"]
        agg_map = {m: "sum" for m in metrics}
        res = df.groupby(group, dropna=False).agg(agg_map).reset_index()
        if "year" in group and "month" in group:
            return res.sort_values(["year", "month"])
        return res.sort_values(group)