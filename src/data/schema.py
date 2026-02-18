"""
src/data/schema.py

Defines the expected raw CSV schema and a normalized column mapping.
Normalizing column names is efficient for future use of:
- filters
- query planning
- pandas operations
- follow-up modifications

It is also added an id column to identify a specific row. It will be used by the LLM to justify its answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


RAW_COLUMNS: List[str] = [
    "Year", "Quarter", "Month", "Week", "Date", "Country",
    "Media Category", "Media Name", "Communication",
    "Campaign Category", "Product", "Campaign Name", "Revenue", "Cost"
]

RENAME_MAP: Dict[str, str] = {
    "Year": "year",
    "Quarter": "quarter",
    "Month": "month",
    "Week": "week",
    "Date": "date",
    "Country": "country",
    "Media Category": "media_category",
    "Media Name": "media_name",
    "Communication": "communication",
    "Campaign Category": "campaign_category",
    "Product": "product",
    "Campaign Name": "campaign_name",
    "Revenue": "revenue",
    "Cost": "cost",
}

NUMERIC_COLUMNS = ["year", "quarter", "month", "week", "revenue", "cost"]
DATE_COLUMN = "date"

DIMENSIONS = [
    "year", "quarter", "month", "week",
    "country", "media_category", "media_name",
    "communication", "campaign_category",
    "product", "campaign_name",
]

# Columns used to build a deterministic row identifier.
# This should include enough fields to uniquely identify a row "semantically".
# In this project we assume the combination of all fields except profit is unique enough.
ROW_ID_HASH_COLUMNS = [
    "year", "quarter", "month", "week", "date",
    "country", "media_category", "media_name",
    "communication", "campaign_category", "product", "campaign_name",
    "revenue", "cost",
]


@dataclass(frozen=True)
class DatasetSchema:
    """
    Class that contains the structure of the dataset. Easily accessible.
    Used mainly when loading the dataset, renaming the columns and checking for potential type errors.
    """
    raw_columns: List[str]
    rename_map: Dict[str, str]
    numeric_columns: List[str]
    date_column: str
    dimensions: List[str]
    row_id_hash_columns: List[str]

    @classmethod
    def marketing_default(cls) -> "DatasetSchema":
        return cls(
            raw_columns=RAW_COLUMNS,
            rename_map=RENAME_MAP,
            numeric_columns=NUMERIC_COLUMNS,
            date_column=DATE_COLUMN,
            dimensions=DIMENSIONS,
            row_id_hash_columns=ROW_ID_HASH_COLUMNS,
        )
        