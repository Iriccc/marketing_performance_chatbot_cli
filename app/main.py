# app/main.py
"""
app/main.py

CLI entrypoint for exploring marketing_data.csv.

This file bootstraps dependencies and starts the
interactive chat loop implemented in app/chat_loop.py.

Main responsibilities:
- Load environment variables (.env)
- Load Settings from src/config.py
- Optional login gate (enabled only if ENABLE_AUTH=true)
- Load and normalize the marketing dataset
- Initialize LLM router + query engine + memory
- Render a small session header (dataset stats + model info)
- Start ChatLoop.run()

Run:
  python -m app.main
"""

from __future__ import annotations

import logging

from dotenv import load_dotenv

from src.config import get_settings
from src.data.loader import MarketingDataLoader
from src.engine.query_engine import QueryEngine
from src.llm.router import LLMRouter

from app.auth import maybe_login
from app.chat_loop import ChatLoop, ChatLoopDeps
from app.memory import ChatMemory
from app.render import render_header, render_info_panel

# Initializing here the logger for the main module, other modules will initialize their own loggers with their respective __name__. 
logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """
    Configure basic logging for the CLI app.

    Logs go to stderr (standard behavior). In AWS environments like ECS/EKS/Lambda,
    stdout/stderr can be shipped to CloudWatch by the platform logging pipeline.
    """
    # For simplicity, we use a basic configuration here.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    _configure_logging()
    load_dotenv()

    # Define environment variables as attributes of a Settings dataclass (see src/config.py)
    cfg = get_settings()

    # Optional login gate (only if ENABLE_AUTH=true)
    if not maybe_login(cfg):
        return

    # Load and normalize dataset
    loader = MarketingDataLoader()
    load_result = loader.load(cfg.dataset_path)
    df = load_result.df

    # Core components
    router = LLMRouter()
    engine = QueryEngine(df)
    memory = ChatMemory(max_user=cfg.max_history_user, max_bot=cfg.max_history_bot)

    # CLI session header
    render_header(cfg.app_title)
    render_info_panel(
        rows=load_result.row_count,
        min_date=str(load_result.min_date.date()),
        max_date=str(load_result.max_date.date()),
        provider=cfg.llm_provider,
        model_id=cfg.bedrock_model_id,
        region=cfg.aws_region,
    )

    # Start chat loop
    deps = ChatLoopDeps(
        settings=cfg,
        router=router,
        engine=engine,
        memory=memory,
    )
    ChatLoop(deps).run()


if __name__ == "__main__":
    main()