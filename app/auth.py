# app/auth.py
"""
app/auth.py

Optional login gate for the CLI chatbot.

Goal:
- Keep authentication OFF by default.
- Enable it only when ENABLE_AUTH=true.

How it works:
- Reads users from users.yaml (same structure as the Streamlit version)
- Prompts for username + password in the terminal
- Verifies password against a bcrypt hash

Expected users.yaml structure:
{
  "users": [
    {"username": "demo", "password_hash": "<bcrypt-hash>"},
    ...
  ]
}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import bcrypt
import yaml
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel

logger = logging.getLogger(__name__)
console = Console()


@dataclass(frozen=True)
class AuthConfig:
    """
    Configuration for CLI auth.
    """
    enabled: bool
    users_file: Path
    max_attempts: int = 3


class LocalAuth:
    """
    Local username/password authentication using bcrypt password hashes.
    """

    def __init__(self, cfg: AuthConfig) -> None:
        self.cfg = cfg

    def login(self) -> bool:
        """
        Returns True if auth is disabled OR if user successfully authenticates.
        Returns False if authentication fails or user cancels input.
        """
        if not self.cfg.enabled:
            logger.info("CLI auth disabled (ENABLE_AUTH != true)")
            return True

        users = self._load_users(self.cfg.users_file)
        if not users:
            console.print(Panel("Auth is enabled but no users were found in users.yaml.", title="Login", border_style="red"))
            logger.error("Auth enabled but users list is empty or missing")
            return False

        console.print(Panel("Authentication required.", title="Login", border_style="cyan"))

        for attempt in range(1, self.cfg.max_attempts + 1):
            try:
                username = Prompt.ask("Username").strip()
                password = Prompt.ask("Password", password=True)
            except (EOFError, KeyboardInterrupt):
                logger.info("Login interrupted by user")
                return False

            if self._check_credentials(users, username, password):
                console.print(Panel(f"Welcome, {username}!", title="Login", border_style="green"))
                logger.info("User authenticated: %s", username)
                return True

            remaining = self.cfg.max_attempts - attempt
            console.print(Panel(f"Invalid credentials. Attempts left: {remaining}", title="Login", border_style="yellow"))
            logger.warning("Invalid login attempt for username=%s (attempt=%d)", username, attempt)

        console.print(Panel("Too many failed attempts. Exiting.", title="Login", border_style="red"))
        logger.error("Auth failed: too many attempts")
        return False

    @staticmethod
    def _load_users(path: Path) -> list[dict[str, Any]]:
        """
        Loads users.yaml and returns the list under the 'users' key.
        Example users.yaml structure:
        users:
        - username: demo
            password_hash: $2b$12$KIXQ1Z5Z6ab1u9Zz8jH7OqvYpQeW8vl5eX9f1E6tZyWjHqjK
        - username: alice
            password_hash: $2b$12$7Q9s8v1X23n4o5p6r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2g3h
        Output example:
        [
            {"username": "demo", "password_hash": "$2b$12$KIXQ1Z5Z6ab1u9Zz8jH7OqvYpQeW8vl5eX9f1E6tZyWjHqjK"},
            {"username": "alice", "password_hash": "$2b$12$7Q9s8v1X23n4o5p6r8s9t0u1v2w3x4y5z6a7b8c90e1f2g3h"}
        ]
        """
        if not path.exists():
            logger.error("users.yaml not found at: %s", str(path))
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.exception("Failed to read users.yaml")
            return []

        if not isinstance(data, dict):
            logger.error("users.yaml root must be a mapping/dict")
            return []

        users = data.get("users", [])
        if not isinstance(users, list):
            logger.error("users.yaml 'users' must be a list")
            return []

        # Normalize expected keys
        normalized: list[dict[str, Any]] = []
        for u in users:
            if not isinstance(u, dict):
                continue
            username = str(u.get("username", "")).strip()
            password_hash = str(u.get("password_hash", "")).strip()
            if username and password_hash:
                normalized.append({"username": username, "password_hash": password_hash})

        logger.info("Loaded %d user(s) from users.yaml", len(normalized))
        return normalized

    @staticmethod
    def _check_credentials(users: list[dict[str, Any]], username: str, password: str) -> bool:
        """
        Checks the provided username/password against the stored bcrypt hash.
        """
        for u in users:
            if u["username"] != username:
                continue

            stored = u["password_hash"]
            try:
                ok = bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
            except Exception:
                logger.exception("bcrypt check failed for username=%s", username)
                return False

            return bool(ok)
        
        logger.exception("Username not found: %s\n Check if the insert username is correct", username)
        return False


def maybe_login(settings: Any) -> bool:
    """
    Entry point used by app/main.py.

    Reads auth settings from the main config object. We expect:
    - settings.enable_auth (bool)
    - settings.users_file (str) OR defaults to "users.yaml" in repo root

    Safe fall back is:
    - enable_auth defaults to False
    - users_file defaults to "./users.yaml"
    """
    enable_auth = bool(getattr(settings, "enable_auth", False))

    users_file_raw = getattr(settings, "users_file", None)
    if users_file_raw:
        users_path = Path(str(users_file_raw))
    else:
        users_path = Path("users.yaml")

    cfg = AuthConfig(enabled=enable_auth, users_file=users_path)
    return LocalAuth(cfg).login()