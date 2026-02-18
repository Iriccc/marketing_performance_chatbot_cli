# app/chat_loop.py
"""
app/chat_loop.py

High-level chat loop orchestration for the CLI chatbot.

This module concentrates the "conversation engine" of the CLI:
- reads user input
- routes messages (terminate | meta | dataset)
- builds QueryPlan (LLM planner)
- executes it deterministically with pandas
- renders assistant output and tables
- keeps short memory (last N turns) + last QueryPlan for follow-ups

The goal is to keep app/main.py as a small bootstrapper:
- load env + config
- optional auth
- load dataset
- build dependencies
- start ChatLoop.run()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.engine.query_engine import QueryEngine
from src.engine.response import ResponseBuilder
from src.llm.router import LLMRouter
from src.config import Settings

from app.commands import is_exit_command
from app.memory import ChatMemory
from app.render import (
    prompt_user_input,
    render_assistant_message,
    render_dataframe_table,
    render_sample_rows_table,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatLoopDeps:
    """
    Keeps dependencies together to simplify the ChatLoop constructor and keep initialization in one place (main.py).
    """
    settings: Settings
    router: LLMRouter
    engine: QueryEngine
    memory: ChatMemory


class ChatLoop:
    """
    Runs the interactive CLI conversation.

    This class owns:
    - the loop lifecycle
    - interaction with ChatMemory
    """

    def __init__(self, deps: ChatLoopDeps) -> None:
        self.cfg = deps.settings
        self.router = deps.router
        self.engine = deps.engine
        self.memory = deps.memory

    def run(self) -> None:
        """
        Starts the blocking interactive loop.

        The loop ends when:
        - the user types a local exit command (exit/quit/stop/terminate)
        - the classifier routes to "terminate"
        - the input stream is closed (EOF / Ctrl+D) or Ctrl+C
        """
        logger.info("ChatLoop started (provider=%s, model=%s)", self.cfg.llm_provider, self.cfg.bedrock_model_id)

        while True:
            user_text = prompt_user_input("Ask a question about marketing performance")
            if user_text is None:
                # EOF / Ctrl+C
                render_assistant_message("Goodbye 👋")
                logger.info("ChatLoop ended (input interrupted)")
                return

            user_text = user_text.strip()
            if not user_text:
                continue

            # Local (non-LLM) exit commands: exact match only.
            if is_exit_command(user_text):
                self.memory.push_user(user_text)
                render_assistant_message("Ok! Session closed. Come back anytime. 👋")
                logger.info("ChatLoop ended (local exit command)")
                return

            # Save user turn in memory
            self.memory.push_user(user_text)

            # Prepare the memory to be passed to the router/planner LLM prompts. 
            # We typically include the last N turns of conversation history (both user and bot) in the prompt, so the LLM can use that for context and follow-up questions.
            history_str = self.memory.history_string(max_turns=5)
            
            # We also pass the last plan as a JSON string to the router/planner
            # so it can use that for follow-up questions like "and what about last month?".
            last_plan_json = self.memory.last_plan_json()

            # 1) Classify route
            route = self._safe_route(user_text)
            logger.info("Route=%s user_text=%r", route, user_text)

            if route == "terminate":
                self._handle_terminate(user_text, history_str)
                logger.info("ChatLoop ended (LLM terminate)")
                return

            if route in {"meta", "out_of_scope"}:
                self._handle_meta(user_text, history_str)
                continue

            # 2) Dataset plan generation + follow-ups (LLM-only)
            plan = self.router.build_plan(
                provider=self.cfg.llm_provider,
                question=user_text,
                history=history_str,
                last_plan_json=last_plan_json,
                bedrock_model_id=self.cfg.bedrock_model_id,
                aws_region=self.cfg.aws_region,
            )

            logger.info("Planner intent=%s metrics=%s groupby=%s", plan.intent, plan.metrics, plan.groupby)

            if plan.intent == "unknown":
                # If the planner can't map this to a dataset query, we let the meta responder explain.
                self._handle_meta(user_text, history_str)
                continue

            # Persist plan for follow-ups
            self.memory.set_last_plan(plan)

            # 3) Execute deterministically
            self._handle_dataset(plan)

    def _safe_route(self, user_text: str) -> str:
        """
        Wraps the LLM classifier call so the chat loop keeps running even if routing fails.
        In case of any exception (e.g. LLM error, network blip, unexpected output), 
        we log the error and default to "meta" route, which is a safe fallback that can handle any user input with a generic response.
        """
        try:
            return self.router.route_question(
                provider=self.cfg.llm_provider,
                question=user_text,
                bedrock_model_id=self.cfg.bedrock_model_id,
                aws_region=self.cfg.aws_region,
            )
        except Exception:
            logger.exception("Routing failed; defaulting to meta")
            return "meta"

    def _handle_terminate(self, user_text: str, history_str: str) -> None:
        """
        Produces a short goodbye via the meta LLM prompt (no 'anything else' line).
        """
        try:
            goodbye = self.router.answer_meta(
                provider=self.cfg.llm_provider,
                question=user_text,
                history=history_str,
                bedrock_model_id=self.cfg.bedrock_model_id,
                aws_region=self.cfg.aws_region,
            ).strip()
        except Exception:
            logger.exception("Terminate meta-answer failed; using fallback goodbye")
            goodbye = "Goodbye 👋"

        self.memory.push_bot(goodbye)
        render_assistant_message(goodbye)

    def _handle_meta(self, user_text: str, history_str: str) -> None:
        """
        Handles meta/out-of-scope/help/conversation-history questions via LLM.
        """
        try:
            answer = self.router.answer_meta(
                provider=self.cfg.llm_provider,
                question=user_text,
                history=history_str,
                bedrock_model_id=self.cfg.bedrock_model_id,
                aws_region=self.cfg.aws_region,
            ).strip()
        except Exception as e:
            logger.exception("Meta answer failed")
            answer = f"I couldn't answer that right now: {e}"

        self.memory.push_bot(answer)
        render_assistant_message(answer)

    def _handle_dataset(self, plan) -> None:
        """
        Executes a dataset plan and renders:
        - assistant response message
        - result table
        - sample subset rows (provenance)
        """
        try:
            exec_res = self.engine.execute_with_subset(plan)
            result_df = exec_res.result_df
            subset_df = exec_res.subset_df

            prov = ResponseBuilder.compute_provenance(subset_df)
            bot_text = ResponseBuilder.build_message(plan, prov, result_df)

            self.memory.push_bot(bot_text)
            render_assistant_message(bot_text)

            if result_df is not None:
                render_dataframe_table(result_df, title="Result table", max_rows=self.cfg.max_render_rows)

            if subset_df is not None and len(subset_df) > 0:
                render_sample_rows_table(subset_df, title="Sample rows used (subset)")

            logger.info(
                "Dataset executed ok (intent=%s, rows_used=%d)",
                plan.intent,
                prov.rows_used,
            )

        except Exception as e:
            logger.exception("Dataset execution failed")
            bot_text = f"I couldn't compute that: {e}"
            self.memory.push_bot(bot_text)
            render_assistant_message(bot_text)