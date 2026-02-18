# cli/memory.py
"""
cli/memory.py

In-memory conversation state for the CLI chatbot.

Responsibilities:
- Store the last N user messages and last N assistant messages (short memory)
- Store the last QueryPlan (used by the LLM planner to interpret follow-ups)
- Provide helper methods to format history for LLM prompts
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from src.engine.query_plan import QueryPlan

logger = logging.getLogger(__name__)

@dataclass
class ChatMemory:
    """
    Keeps a bounded chat history and the latest QueryPlan.
    This is a simple in-memory implementation. In a more complex app, you might want to:
    - persist memory to disk or a database
    - implement more complex retrieval (e.g. semantic search over past messages)
    
    Two separate buffers (user vs assistant) for simplicity, 
    since they have different roles in the conversation and may be used differently in prompts.
    """

    max_user: int = 5
    max_bot: int = 5

    user_messages: List[str] = field(default_factory=list)
    bot_messages: List[str] = field(default_factory=list)

    _last_plan: Optional[QueryPlan] = None

    def push_user(self, text: str) -> None:
        """
        Add a user message to memory and enforce the max length.
        """
        self.user_messages.append(text)
        if len(self.user_messages) > self.max_user:
            self.user_messages = self.user_messages[-self.max_user :]

        logger.info("Memory: stored user msg (count=%d)", len(self.user_messages))

    def push_bot(self, text: str) -> None:
        """
        Add an assistant message to memory and enforce the max length.
        """
        self.bot_messages.append(text)
        if len(self.bot_messages) > self.max_bot:
            self.bot_messages = self.bot_messages[-self.max_bot :]

        logger.info("Memory: stored bot msg (count=%d)", len(self.bot_messages))

    def set_last_plan(self, plan: QueryPlan) -> None:
        """
        Store the last valid dataset plan (used for follow-ups).
        """
        self._last_plan = plan
        logger.info("Memory: updated last plan (intent=%s)", getattr(plan, "intent", "unknown"))

    def clear(self) -> None:
        """
        Clears history and last plan (useful for a 'reset' command).
        """
        self.user_messages.clear()
        self.bot_messages.clear()
        self._last_plan = None
        logger.info("Memory: cleared all state")

    def history_string(self, max_turns: int = 5) -> str:
        """
        Builds a compact conversation history string for LLM prompts.

        We format paired turns:
          User: ...
          Assistant: ...

        If buffers are not the same length, we only pair what exists.
        """
        u = self.user_messages[-max_turns:]
        b = self.bot_messages[-max_turns:]

        pairs = []
        for i in range(min(len(u), len(b))):
            pairs.append(f"User: {u[i]}\nAssistant: {b[i]}")

        history = "\n\n".join(pairs)
        logger.info("Memory: built history string (pairs=%d, chars=%d)", len(pairs), len(history))
        return history

    def last_plan_json(self) -> str:
        """
        Returns the previous QueryPlan as JSON for the planner prompt,
        or "null" if no previous plan exists.
        """
        if self._last_plan is None:
            logger.info("Memory: last plan is null")
            return "null"

        txt = self._last_plan.model_dump_json(indent=2)
        logger.info("Memory: exported last plan json (chars=%d)", len(txt))
        return txt