# src/config.py

"""
src/config.py

Centralized configuration via environment variables.
Used to keep config in one place so the app is easy to run in different environments.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Optional


LLMProvider = Literal["bedrock"]


@dataclass(frozen=True)
class Settings:
    """
    Settings container (dataclass) loaded from environment variables.
    The from_env class method is responsible for parsing environment variables and constructing the Settings object.
    """
    app_title: str
    dataset_path: str

    llm_provider: LLMProvider

    # Bedrock
    bedrock_model_id: str
    aws_region: str
    aws_profile: Optional[str]
    
    # Memory limits (last N user and N bot messages)
    max_history_user: int
    max_history_bot: int
    enable_auth: bool = True  # Optional login gate for the CLI (enabled by default)
    users_file: Optional[str] = None  # Path to users.yaml (only needed if enable_auth=True)
    max_render_rows: int = 20  # Max number of rows to render in the CLI tables

    @staticmethod
    def _get_int(name: str, default: int) -> int:
        """
        Small helper to safely parse integer env vars.
        """
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    @staticmethod
    def _get_bool(name: str, default: bool) -> bool:
        """
        Small helper to safely parse boolean env vars.
        """
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in ("true", "1", "yes", "y", "on")
    
    @classmethod
    def from_env(cls) -> Settings:
        """
        Method used to construct Settings from environment variables.
        """
        provider = os.getenv("LLM_PROVIDER", "bedrock").strip().lower()

        return cls(
            app_title=os.getenv("APP_TITLE", "Marketing Data Chatbot"),
            dataset_path=os.getenv("DATASET_PATH", "marketing_data.csv"),
            llm_provider=provider,  # type: ignore[arg-type]

            bedrock_model_id=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0"),
            aws_region=os.getenv("AWS_REGION", "eu-central-1"),
            aws_profile=os.getenv("AWS_PROFILE"),

            max_history_user=cls._get_int("MAX_HISTORY_USER", 5),
            max_history_bot=cls._get_int("MAX_HISTORY_BOT", 5),
            enable_auth=cls._get_bool("ENABLE_AUTH", True),
            users_file=os.getenv("USERS_FILE", "users.yaml"),
            max_render_rows=cls._get_int("MAX_RENDER_ROWS", 20),
        )


def get_settings() -> Settings:
    """
    Single entry point used by the app.
    """
    return Settings.from_env()
