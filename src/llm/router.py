"""
src/llm/router.py

LLM routing + planning for the marketing chatbot.

- route_question(): LLM classifier -> "dataset" | "meta" | "out_of_scope"
- answer_meta(): LLM-generated help/capabilities/chat-history answer
- build_plan(): LLM planner -> QueryPlan JSON (LLM-only follow-ups via history + last_plan_json)

This file uses:
- AWS Bedrock (Claude 3 / 3.5) via boto3 bedrock-runtime

All LLM calls are expected to return plain text; JSON outputs are parsed with a robust parser.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional, Dict

import boto3
import yaml
import logging 

from src.engine.query_plan import QueryPlan

logger = logging.getLogger(__name__)

class LLMRouter:
    """"
    LLMRouter is the main class responsible for routing user questions to the appropriate LLM prompts and parsing their responses.
    It loads the prompts from a YAML file, and provides methods to:
        - route_question(): classify the user question into "dataset", "meta", "out_of_scope", or "terminate"
        - answer_meta(): generate an answer for meta questions (capabilities, help, chat history)
        - build_plan(): generate a QueryPlan JSON from the user question, conversation history, and last plan (for follow-ups)

    Each method uses the _generate_text() method to call the appropriate LLM backend with the right prompt and parameters.
    The LLM responses are expected to be in plain text, and any JSON output is parsed with the _safe_parse_json() method, 
    which can handle cases where the LLM wraps JSON in extra text or markdown code fences.
    The class also stores debug_info for each step, which can be useful for inspecting LLM outputs and troubleshooting.

    If prompts are missing or if LLM outputs cannot be parsed/validated, the methods return safe defaults to keep the app functional.
    """

    def __init__(self, prompts_path: Optional[str] = None) -> None:
        """
        Initializes the LLMRouter by loading prompts from a YAML file. 
        If no path is provided, it defaults to "prompts.yaml" in the same directory as this script.
        """
        base_dir = Path(__file__).resolve().parent
        self._prompts_path = Path(prompts_path) if prompts_path else (base_dir / "prompts.yaml")
        self.prompts = self._load_prompts(self._prompts_path)
        self.temperature = 0.0  # default temperature for LLM calls, can be overridden in each call
        self.max_tokens = 800  # default max tokens for LLM calls, can be overridden in each call

        # Useful to inspect what the LLM returned at each step, without needing to add print statements or use a debugger.
        self.debug_info: Dict[str, Any] = {}

    @staticmethod
    def _load_prompts(path: Path) -> dict:
        """
        Reads the prompts from a YAML file and returns them as a dictionary.
        The YAML file is expected to contain a mapping at the top level, 
        with keys like "classifier_system", "classifier_user_template", "meta_system", "meta_user_template", "planner_system", and "planner_user_template".
        If the file is missing or cannot be parsed, it raises an error. 
        If the content is not a dictionary, it also raises an error.         
        """
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("prompts.yaml must contain a mapping at the top level.")
        return data

    def route_question(
        self,
        *,
        provider: str,
        question: str,
        bedrock_model_id: str,
        aws_region: str,
    ) -> str:
        """
        LLM classifier that returns one of: dataset | meta | out_of_scope
            - dataset: the question is about the dataset and can be answered by querying it
            - meta: the question is about the chatbot capabilities, or is a follow-up that requires context, or is out-of-scope but we want to answer gracefully via LLM
            - out_of_scope: the question is not answerable (e.g. "What is the weather today?") and we want to say "Sorry, I can only answer questions about the marketing dataset" instead of trying to query the dataset or generating a plan.
        """
        system = self.prompts.get("classifier_system")
        user_tmpl = self.prompts.get("classifier_user_template")
        if not system or not user_tmpl:
            # If prompts are missing, safest default is out_of_scope (app still works)
            return "out_of_scope"

        user = user_tmpl.format(question=question)

        txt = self._generate_text(
            provider=provider,
            system=system,
            user=user,
            bedrock_model_id=bedrock_model_id,
            aws_region=aws_region,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        self.debug_info["classifier_raw"] = txt

        data = self._safe_parse_json(txt)
        route = str(data.get("route", "out_of_scope")).strip().lower()
        if route not in {"dataset", "meta", "out_of_scope", "terminate"}:
            route = "out_of_scope"  # safest default if LLM doesn't follow instructions

        self.debug_info["classifier_route"] = route

        logger.info(f"LLM route_question debug: {self.debug_info}")
        return route

    def answer_meta(
        self,
        *,
        provider: str,
        question: str,
        history: str,
        bedrock_model_id: str,
        aws_region: str,
    ) -> str:
        """
        LLM answer for capabilities/help/chat-history/out-of-scope redirection.
        For example, if the question is "What can you do?", the LLM should answer with the chatbot capabilities. 
        If the question is "What was my last question?", the LLM should use the history to answer. 
        If the question is out-of-scope, the LLM should gracefully say it can only answer questions about the marketing dataset.
        """
        system = self.prompts.get("meta_system")
        user_tmpl = self.prompts.get("meta_user_template")
        if not system or not user_tmpl:
            return "I can help you explore the marketing dataset. Ask something like: 'Total revenue in 2023?'"

        user = user_tmpl.format(history=history, question=question)

        txt = self._generate_text(
            provider=provider,
            system=system,
            user=user,
            bedrock_model_id=bedrock_model_id,
            aws_region=aws_region,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        self.debug_info["meta_raw"] = txt
        logger.info(f"LLM route_question debug: {self.debug_info}")
        return txt.strip()

    def build_plan(
        self,
        *,
        provider: str,
        question: str,
        history: str,
        last_plan_json: str,
        bedrock_model_id: str,
        aws_region: str,
    ) -> QueryPlan:
        """
        Method that builds the QueryPlan JSON by calling the
        LLM planner -> QueryPlan (JSON). 
        Follow-ups are resolved by the LLM because we pass:
        - history (last turns)
        - last_plan_json (previous plan or "null")

        The system and user prompts are designed to use this context to generate a new plan that is consistent
        with the conversation history and the user's intent, even if it's a follow-up question.
        """
        system = self.prompts.get("planner_system")
        user_tmpl = self.prompts.get("planner_user_template")
        if not system or not user_tmpl:
            return QueryPlan(intent="unknown", metrics=[], groupby=[], time_range={"type": "all", "year": None, "quarter": None}, filters=[], top_n=None, sort_by=None)

        user = user_tmpl.format(question=question, history=history, last_plan_json=last_plan_json)

        txt = self._generate_text(
            provider=provider,
            system=system,
            user=user,
            bedrock_model_id=bedrock_model_id,
            aws_region=aws_region,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        self.debug_info["planner_prompt"] = user
        self.debug_info["planner_raw"] = txt

        data = self._safe_parse_json(txt)
        self.debug_info["planner_parsed"] = data

        try:
            logger.info(f"LLM route_question debug: {self.debug_info}")
            return QueryPlan.model_validate(data)
        except Exception as e:
            # If LLM output doesn't validate, return unknown so the app can ask a clarification via LLM meta
            self.debug_info["planner_validate_error"] = str(e)
            logger.info(f"LLM route_question debug: {self.debug_info}")
            return QueryPlan(intent="unknown", metrics=[], groupby=[], time_range={"type": "all", "year": None, "quarter": None}, filters=[], top_n=None, sort_by=None)


    def _generate_text(
        self,
        *,
        provider: str,
        system: str,
        user: str,
        bedrock_model_id: str,
        aws_region: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """
        Provider routing:
        - bedrock
        Could be extended in the future to support other providers by adding more branches here and implementing the corresponding calls.
        """

        return self._bedrock_claude_messages(
            model_id=bedrock_model_id,
            region=aws_region,
            system=system,
            user=user,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    @staticmethod
    def _bedrock_claude_messages(
        *,
        model_id: str,
        region: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """
        Claude 3 / 3.5 on Bedrock via Messages API style payload.
        Works for model IDs like:
        - anthropic.claude-3-5-sonnet-20240620-v1:0
        - anthropic.claude-3-sonnet-20240229-v1:0
        - anthropic.claude-3-haiku-20240307-v1:0
        """
        client = boto3.client("bedrock-runtime", region_name=region)

        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
            "system": system,
            "messages": [
                {"role": "user", "content": user}
            ],
        }
        try:
            resp = client.invoke_model(
                modelId=model_id,
                body=json.dumps(payload).encode("utf-8"),
            )
        except Exception as e:
            return f"LLM call error: {str(e)}"
        
        body = resp["body"].read()
        data = json.loads(body)

        # Claude response: {"content":[{"type":"text","text":"..."}], ...}
        content = data.get("content", [])
        # We want to extract the "text" field from the first item in the "content" list, if it exists and is in the expected format. 
        # If not, we fallback to returning the whole response as a string for debugging purposes.
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and "text" in first:
                return str(first["text"])
        # fallback
        return json.dumps(data)

    
    # ----------------------------
    # JSON parsing helpers
    # ----------------------------

    @staticmethod
    def _safe_parse_json(text: str) -> dict:
        """
        Extracts the first JSON object from an LLM response and parses it.
        Handles cases where the model wraps JSON with extra text or markdown
        code fences like ```json ... ```.
        Returns an empty dict if parsing fails.
        """
        if not text:
            return {}

        # Remove leading/trailing whitespace
        text = text.strip()

        # Remove markdown code fences like ```json ... ``` or ``` ... ``` - Typical of Claude 4 responses, but can appear in other models too.
        text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        # Best case: pure JSON
        try:
            return json.loads(text)
        except Exception:
            pass

        # Try to extract the first {...} block
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not m:
            return {}

        candidate = m.group(0)

        try:
            return json.loads(candidate)
        except Exception:
            return {}
