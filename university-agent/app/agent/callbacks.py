"""Callback handler: логирование инструментов, LLM и шагов агента."""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger("agent.callbacks")


class AgentCallbackHandler(AsyncCallbackHandler):
    """Логирует все ключевые события агента: LLM-запросы, вызовы инструментов, шаги."""

    def __init__(self, user_id: str) -> None:
        super().__init__()
        self.user_id = user_id
        self._step = 0
        self._llm_call_count = 0
        self._tool_call_count = 0
        self._timers: dict[UUID, float] = {}

    # ── LLM ────────────────────────────────────────────────────────────────

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        self._llm_call_count += 1
        self._timers[kwargs["run_id"]] = time.monotonic()

        prompt_len = sum(len(p) for p in prompts)
        logger.info(
            "LLM запрос #%d: user=%s prompt_len=%d",
            self._llm_call_count,
            self.user_id,
            prompt_len,
        )

    async def on_llm_end(
        self,
        response: LLMResult,
        **kwargs: Any,
    ) -> None:
        elapsed = time.monotonic() - self._timers.pop(kwargs["run_id"], 0)

        token_usage = {}
        if response.llm_output and "token_usage" in response.llm_output:
            token_usage = response.llm_output["token_usage"]

        content_preview = ""
        if response.generations:
            gen = response.generations[0][0]
            if hasattr(gen, "message") and gen.message:
                content_preview = gen.message.content[:100] if gen.message.content else ""
                tool_calls_info = getattr(gen.message, "tool_calls", None)
                if tool_calls_info:
                    tools_called = [tc.get("name", "?") for tc in tool_calls_info]
                    logger.info(
                        "LLM ответ #%d: user=%s elapsed=%.2fs prompt_tokens=%s completion_tokens=%s tools=%s",
                        self._llm_call_count,
                        self.user_id,
                        elapsed,
                        token_usage.get("prompt_tokens", "?"),
                        token_usage.get("completion_tokens", "?"),
                        tools_called,
                    )
                    return

        logger.info(
            "LLM ответ #%d: user=%s elapsed=%.2fs prompt_tokens=%s completion_tokens=%s answer_preview=%s",
            self._llm_call_count,
            self.user_id,
            elapsed,
            token_usage.get("prompt_tokens", "?"),
            token_usage.get("completion_tokens", "?"),
            content_preview,
        )

    async def on_llm_error(
        self,
        error: BaseException,
        **kwargs: Any,
    ) -> None:
        self._timers.pop(kwargs["run_id"], None)
        logger.error(
            "LLM ошибка #%d: user=%s error=%s",
            self._llm_call_count,
            self.user_id,
            error,
        )

    # ── Tools ───────────────────────────────────────────────────────────────

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        self._tool_call_count += 1
        self._timers[kwargs["run_id"]] = time.monotonic()

        tool_name = serialized.get("name", "?")
        # Обрезаем аргументы чтобы не забивать лог
        args_preview = input_str[:200] if len(input_str) > 200 else input_str

        logger.info(
            "Инструмент вызов #%d (шаг %d): user=%s tool=%s args=%s",
            self._tool_call_count,
            self._step,
            self.user_id,
            tool_name,
            args_preview,
        )

    async def on_tool_end(
        self,
        output: str,
        **kwargs: Any,
    ) -> None:
        elapsed = time.monotonic() - self._timers.pop(kwargs["run_id"], 0)
        output_len = len(output)

        try:
            import json

            data = json.loads(output)
            found = data.get("found", True)
            error_msg = data.get("error", "")
        except Exception:
            found = True
            error_msg = ""

        if error_msg:
            logger.warning(
                "Инструмент результат #%d: user=%s elapsed=%.2fs error=%s",
                self._tool_call_count,
                self.user_id,
                elapsed,
                error_msg[:150],
            )
        elif not found:
            logger.info(
                "Инструмент результат #%d: user=%s elapsed=%.2fs found=False len=%d",
                self._tool_call_count,
                self.user_id,
                elapsed,
                output_len,
            )
        else:
            logger.info(
                "Инструмент результат #%d: user=%s elapsed=%.2fs len=%d",
                self._tool_call_count,
                self.user_id,
                elapsed,
                output_len,
            )

    async def on_tool_error(
        self,
        error: BaseException,
        **kwargs: Any,
    ) -> None:
        self._timers.pop(kwargs["run_id"], None)
        logger.error(
            "Инструмент ошибка #%d: user=%s error=%s",
            self._tool_call_count,
            self.user_id,
            error,
        )

    # ── Agent actions ───────────────────────────────────────────────────────

    async def on_agent_action(
        self,
        action: Any,
        **kwargs: Any,
    ) -> None:
        self._step += 1
        logger.info(
            "Агент шаг %d: user=%s tool=%s",
            self._step,
            self.user_id,
            action.tool,
        )

    async def on_agent_finish(
        self,
        finish: Any,
        **kwargs: Any,
    ) -> None:
        answer_preview = ""
        if hasattr(finish, "return_values"):
            output = finish.return_values.get("output", "")
            answer_preview = output[:150] if output else ""

        logger.info(
            "Агент завершил: user=%s шагов=%d вызовов_llm=%d вызовов_инструментов=%d answer=%s",
            self.user_id,
            self._step,
            self._llm_call_count,
            self._tool_call_count,
            answer_preview,
        )

    # ── Parsing errors ──────────────────────────────────────────────────────

    async def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        chain_name = serialized.get("name", serialized.get("id", ["?"])[-1])
        if chain_name == "AgentExecutor":
            return
        logger.debug(
            "Цепочка старт: user=%s chain=%s",
            self.user_id,
            chain_name,
        )

    async def on_chain_end(
        self,
        outputs: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        pass  # AgentExecutor цепочка логируется через on_agent_finish

    async def on_chain_error(
        self,
        error: BaseException,
        **kwargs: Any,
    ) -> None:
        logger.error(
            "Цепочка ошибка: user=%s error=%s",
            self.user_id,
            error,
        )
