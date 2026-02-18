"""
src/data/loader.py

Loads the CSV, validates required columns, normalizes schema, and computes derived metrics.
Moreover, it:
- fail if schema is incorrect
- parse types deterministically
- compute "profit" from revenue and cost (source of truth is always the dataset)

It is also added an id column to identify a specific row. It will be used by the LLM to justify its answer.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import pandas as pd

from .schema import DatasetSchema

import logging
logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class LoadResult:
    """
    Class that is used to load the dataframe and the min and max dates found in the dataset
    """
    df: pd.DataFrame
    min_date: pd.Timestamp
    max_date: pd.Timestamp

    @property
    def row_count(self) -> int:
        return int(len(self.df))


class MarketingDataLoader:
    """
    Class defined to load the marketing dataset from CSV, validate and normalize it, and compute derived metrics.
    We initialize the class with the expected schema attribute, taken from DatasetSchema. 
    This allows us to keep the schema definition separate and reusable, and also to easily switch to a different schema if needed (e.g. for a different dataset).
    """
    def __init__(self, schema: DatasetSchema | None = None) -> None:
        self.schema = schema or DatasetSchema.marketing_default()

    def load(self, csv_path: str) -> LoadResult:
        """
        Method that returns the LoadResult class with the optimized dataset plus the most and least recent dates in the df.
        """
        df = pd.read_csv(csv_path)

        self._validate_columns(df)
        df = self._normalize(df)
        df = self._coerce_types(df)
        df = self._add_derived_metrics(df)
        df = self._add_row_id(df)

        min_date = df[self.schema.date_column].min()
        max_date = df[self.schema.date_column].max()

        return LoadResult(df=df, min_date=min_date, max_date=max_date)

    def _validate_columns(self, df: pd.DataFrame) -> None:
        """
        Method that checks wether all the expected columns are present in the dataset according to the schema attribute.
        """
        missing = [c for c in self.schema.raw_columns if c not in df.columns]
        if missing:
            raise ValueError(f"CSV missing expected columns: {missing}")
        
    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Method that renames the columns of the dataframe according to the snake_case logic
        """
        return df.rename(columns=self.schema.rename_map)

    def _coerce_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Parse and validate column types deterministically.

        - Date must be a valid datetime (we use pandas to parse, which can handle various formats, but we enforce errors="coerce" to catch invalid dates)
        - Quarter and Month can be numeric or strings like "Q3", "2020 Q3", "M08", but they will be normalized to numeric values in the final DataFrame (with fallback to date parsing if missing)
        - If missing, quarter/month are derived from date
        - Revenue and cost must be numeric
        """

        date_col = self.schema.date_column

        # ---------------------------
        # Parse date
        # ---------------------------
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        if df[date_col].isna().any():
            bad = df[df[date_col].isna()].head(10)
            raise ValueError(
                "Some rows have invalid Date values after parsing.\n"
                f"{bad.to_string(index=False)}"
            )

        # ---------------------------
        # Quarter parsing
        # Accept:
        # - 1,2,3,4
        # - "Q1", "2020 Q3"
        # Returns numeric quarter or NaN if parsing fails
        # ---------------------------
        q_str = df["quarter"].astype(str).str.extract(r"Q\s*([1-4])", expand=False)
        df["quarter"] = (
            pd.to_numeric(df["quarter"], errors="coerce")
            .fillna(pd.to_numeric(q_str, errors="coerce"))
        )

        # ---------------------------
        # Month parsing
        # Accept:
        # - 1..12
        # - "M08", "2020M08"
        # Returns numeric month or NaN if parsing fails
        # ---------------------------
        m_str = df["month"].astype(str).str.extract(r"M\s*(\d{1,2})", expand=False)
        df["month"] = (
            pd.to_numeric(df["month"], errors="coerce")
            .fillna(pd.to_numeric(m_str, errors="coerce"))
        )

        # ---------------------------
        # Fallback from date
        # ---------------------------
        # If quarter or month are missing, we can derive them from the date column (if present).
        df["quarter"] = df["quarter"].fillna(df[date_col].dt.quarter)
        df["month"] = df["month"].fillna(df[date_col].dt.month)

        # ---------------------------
        # Validate ranges
        # ---------------------------
        bad_q = df["quarter"].isna() | ~df["quarter"].between(1, 4)
        bad_m = df["month"].isna() | ~df["month"].between(1, 12)

        if bad_q.any() or bad_m.any():
            sample = df.loc[bad_q | bad_m, ["year", "quarter", "month", date_col]].head(15)
            raise ValueError(
                "Some rows have invalid Quarter/Month values after parsing.\n"
                f"{sample.to_string(index=False)}"
            )

        # ---------------------------
        # Coerce numeric columns
        # ---------------------------
        for col in self.schema.numeric_columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Revenue & cost must be valid
        if df[["revenue", "cost"]].isna().any().any():
            bad = df[df[["revenue", "cost"]].isna().any(axis=1)].head(10)
            raise ValueError(
                "Some rows have invalid Revenue/Cost values after parsing.\n"
                f"{bad.to_string(index=False)}"
            )

        return df

    # Static method used to compute derived metrics, easily scalable if needed.
    @staticmethod
    def _add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
        df["profit"] = df["revenue"] - df["cost"]
        return df


    def _add_row_id(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Creates a deterministic row_id based on a stable string representation of selected fields.
        The row_id is a hex digest (sha256) truncated for readability.
        The id_key does not change if the order of the data is changed, it is based on the row content itself.
        """
        # We donn't hash all the columns, but only a subset of them that can uniquely identify a row "semantically". 
        # This is to avoid issues with potential floating point differences in revenue/cost, or timezone differences in date, that could lead to different hashes for the same "logical" row.
        cols = self.schema.row_id_hash_columns

        def build_row_key(row) -> str:
            """
            Docstring per build_row_key
            Example output of the key (before hashing):
            year=2023|quarter=2|month=5|week=20
            """
            parts = []
            for c in cols:
                v = row[c]
                # Normalize datetimes to YYYY-MM-DD to avoid timezone / formatting differences
                if c == "date":
                    v = str(v.date())
                parts.append(f"{c}={v}")
            return "|".join(parts)

        def hash_key(key: str) -> str:
            """
            Hash the key using sha256 and return a short digest.
            We use hashing to create a fixed-length identifier that can be easily used by the LLM and displayed to the user, without exposing potentially sensitive information from the dataset.
            The hash is deterministic, so the same row will always have the same id, even if the order of the data changes or if we reload the dataset multiple times. 
            """
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
            return digest[:16]  # short stable id for display

        df = df.copy()
        df["row_id"] = df.apply(lambda r: hash_key(build_row_key(r)), axis=1)
        return df
