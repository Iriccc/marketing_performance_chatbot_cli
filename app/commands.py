# cli/commands.py
"""
cli/commands.py

Small command helpers for the CLI chat loop.

These commands are handled locally (no LLM call) to:
- keep interactions fast
- avoid spending tokens on obvious control actions

This module focuses on:
- exit commands (end the program)
- reset/clear commands (optional, to clear local memory or state. Not yet implemented in the main loop)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Exact shortcuts (match-only, not substring) to avoid accidental exits.
_EXIT_COMMANDS = {"exit", "quit", "stop", "terminate"}

# Optional local commands you may support later (not wired by default).
_RESET_COMMANDS = {"reset", "clear"}
_HELP_COMMANDS = {"help", "?"}


def is_exit_command(text: str) -> bool:
    """
    Returns True only if the user input is exactly one of the allowed exit commands.
    """
    t = text.strip().lower()
    ok = t in _EXIT_COMMANDS
    if ok:
        logger.info("CLI command detected: exit (%s)", t)
    return ok


def is_reset_command(text: str) -> bool:
    """
    Optional: returns True if the user wants to clear the local chat state.
    """
    t = text.strip().lower()
    ok = t in _RESET_COMMANDS
    if ok:
        logger.info("CLI command detected: reset (%s)", t)
    return ok


def is_help_command(text: str) -> bool:
    """
    Optional: returns True if the user asks for local help.
    """
    t = text.strip().lower()
    ok = t in _HELP_COMMANDS
    if ok:
        logger.info("CLI command detected: help (%s)", t)
    return ok