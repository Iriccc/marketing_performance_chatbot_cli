"""
tests/test_query_engine.py

Runs end-to-end query execution tests on the real dataset (marketing_data.csv):
- loads the CSV through MarketingDataLoader
- executes representative QueryPlans through QueryEngine
- checks basic invariants (non-empty results, expected columns, ordering)

This is not an exhaustive test suite, but it covers some key scenarios and serves as a sanity check for the core query execution logic.
"""

from __future__ import annotations

import os
import pytest

from src.data.loader import MarketingDataLoader
from src.engine.query_engine import QueryEngine
from src.engine.query_plan import QueryPlan, TimeRange, SortBy


@pytest.fixture(scope="session")
def dataset_path() -> str:
    # assumes tests are run from the project root
    path = os.path.join(os.getcwd(), "marketing_data.csv")
    if not os.path.exists(path):
        raise RuntimeError("marketing_data.csv not found in project root.")
    return path


@pytest.fixture(scope="session")
def df(dataset_path):
    # Load the dataset once for all tests to speed up execution. The loader will validate and normalize it.
    loader = MarketingDataLoader()
    return loader.load(dataset_path).df


def test_total_revenue_in_2022(df):
    # Simple aggregate test: total revenue in 2022 should be non-negative and return a single row with the "revenue" column.
    engine = QueryEngine(df)
    plan = QueryPlan(
        intent="aggregate",
        metrics=["revenue"],
        groupby=[],
        time_range=TimeRange(type="year", year=2022),
    )
    out = engine.execute(plan)

    assert "revenue" in out.columns
    assert len(out) == 1
    assert float(out.iloc[0]["revenue"]) >= 0.0


def test_top_5_campaigns_by_revenue_last_quarter(df):
    # Test top_n intent: top 5 campaigns by revenue in the last quarter. 
    # Checks that we get at most 5 rows, with the expected columns, and that revenue is sorted descending.
    engine = QueryEngine(df)
    plan = QueryPlan(
        intent="top_n",
        metrics=["revenue"],
        groupby=["campaign_name"],
        time_range=TimeRange(type="last_quarter"),
        top_n=5,
        sort_by=SortBy(field="revenue", direction="desc"),
    )
    out = engine.execute(plan)

    assert len(out) <= 5
    assert "campaign_name" in out.columns
    assert "revenue" in out.columns

    # revenue should be sorted descending
    revenues = out["revenue"].tolist()
    assert revenues == sorted(revenues, reverse=True)


def test_revenue_and_cost_trend_by_month(df):
    # Test trend intent: revenue and cost trend by month for all time.
    # Checks that we get the expected columns, that the result is non-empty, and that the ordering by year/month is correct (non-decreasing).
    engine = QueryEngine(df)
    plan = QueryPlan(
        intent="trend",
        metrics=["revenue", "cost"],
        groupby=["year", "month"],
        time_range=TimeRange(type="all"),
    )
    out = engine.execute(plan)

    assert "year" in out.columns and "month" in out.columns
    assert "revenue" in out.columns and "cost" in out.columns
    assert len(out) > 0

    # verify ordering by year/month (non-decreasing)
    years_months = list(zip(out["year"].tolist(), out["month"].tolist()))
    assert years_months == sorted(years_months)


def test_media_category_highest_profit_q2_2023(df):
    # Test top_n intent: media category with highest profit in Q2 2023.
    # Checks that we get at most 5 rows, with the expected columns, and that profit is sorted descending.
    engine = QueryEngine(df)
    plan = QueryPlan(
        intent="top_n",
        metrics=["profit"],
        groupby=["media_category"],
        time_range=TimeRange(type="quarter", year=2023, quarter=2),
        top_n=5,
        sort_by=SortBy(field="profit", direction="desc"),
    )
    out = engine.execute(plan)

    assert "media_category" in out.columns
    assert "profit" in out.columns
    assert len(out) <= 5

    profits = out["profit"].tolist()
    assert profits == sorted(profits, reverse=True)