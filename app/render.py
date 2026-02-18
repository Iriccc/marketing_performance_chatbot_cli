# cli/render.py
"""
cli/render.py

Terminal rendering utilities using rich.

This module keeps all CLI presentation concerns in one place.

We render:
- header / session info panels
- assistant messages
- pandas result tables
- sample subset rows used (provenance)

All printing is done via Rich's Console.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt

logger = logging.getLogger(__name__)
console = Console()


def render_header(title: str) -> None:
    """
    Prints a simple header panel at startup.
    """
    panel = Panel.fit(Text(title, style="bold"), title="Chatbot", border_style="cyan")
    console.print(panel)
    logger.info("Rendered header: %s", title)


def render_info_panel(*, rows: int, min_date: str, max_date: str, provider: str, model_id: str, region: str) -> None:
    """
    Prints dataset + runtime information (useful for debugging and transparency).
    """
    info = (
        f"[bold]Dataset[/bold]\n"
        f"- Rows: {rows}\n"
        f"- Date range: {min_date} → {max_date}\n\n"
        f"[bold]LLM[/bold]\n"
        f"- Provider: {provider}\n"
        f"- Model: {model_id}\n"
        f"- Region: {region}"
    )
    console.print(Panel(info, title="Session", border_style="green"))
    logger.info("Rendered info panel (rows=%d, range=%s..%s)", rows, min_date, max_date)


def prompt_user_input(prompt: str) -> Optional[str]:
    """
    Reads a user message from the terminal.

    Returns:
    - a string if the user typed something
    - None if input stream is closed (EOF / Ctrl+D)
    """
    try:
        return Prompt.ask(f"[bold blue]{prompt}[/bold blue]")
    except (EOFError, KeyboardInterrupt):
        logger.info("User input interrupted (EOF/KeyboardInterrupt)")
        return None


def render_assistant_message(text: str) -> None:
    """
    Prints assistant output as a magenta panel.
    """
    console.print(Panel(text, title="Assistant", border_style="magenta"))
    logger.info("Rendered assistant message (chars=%d)", len(text))


def _df_to_rich_table(df: pd.DataFrame, *, title: str, max_rows: int = 20) -> Table:
    """
    Convert a pandas DataFrame into a Rich Table.

    - Limits rows to avoid flooding the terminal.
    - Converts values to string for stable display.
    """
    table = Table(title=title, show_lines=False)
    for col in df.columns:
        table.add_column(str(col))

    safe_df = df.head(max_rows)
    for _, row in safe_df.iterrows():
        # * to unpack the row values as separate arguments to add_row
        table.add_row(*[str(v) for v in row.values])

    if len(df) > max_rows:
        table.caption = f"Showing first {max_rows} of {len(df)} rows"
    return table


def render_dataframe_table(df: pd.DataFrame, *, title: str = "Result table", max_rows: int = 20) -> None:
    """
    Renders a result table (aggregates/top-n/trends) to the terminal.
    Falls back to a message if the dataframe is empty.
    """
    if df is None or len(df) == 0:
        console.print(Panel("No rows to display.", title=title, border_style="yellow"))
        logger.info("Rendered empty dataframe table: %s", title)
        return

    console.print(_df_to_rich_table(df, title=title, max_rows=max_rows))
    logger.info("Rendered dataframe table: %s (rows=%d, cols=%d)", title, len(df), len(df.columns))


def render_sample_rows_table(df: pd.DataFrame, *, title: str = "Sample rows used (subset)", max_rows: int = 5) -> None:
    """
    Renders a small sample of subset rows used for provenance.

    It is possible to show only a few key columns. In this example we show, if they exist, all the columns.
    """
    if df is None or len(df) == 0:
        console.print(Panel("No subset rows to display.", title=title, border_style="yellow"))
        logger.info("Rendered empty subset table")
        return

    preferred_cols = [
        "row_id", "date", "year", "quarter", "month",
        "country", "product", "media_category", "campaign_name",
        "revenue", "cost", "profit",
    ]
    cols = [c for c in preferred_cols if c in df.columns]
    view = df[cols].head(max_rows) if cols else df.head(max_rows)

    console.print(_df_to_rich_table(view, title=title, max_rows=max_rows))
    logger.info("Rendered subset sample table (rows=%d, cols=%d)", len(view), len(view.columns))