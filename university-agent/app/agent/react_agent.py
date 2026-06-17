"""ReAct agent factory — creates and invokes the LangChain agent."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import tenacity
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agent.callbacks import AgentCallbackHandler
from app.agent.mcp_loader import load_mcp_tools_list
from app.agent.prompts import SYSTEM_PROMPT
from app.config import settings
from app.metrics import token_usage_total, tool_calls_total
from app.tools.ask_clarification import CLARIFICATION_PREFIX, ask_clarification
from app.tools.md_to_docx import md_to_docx_convert
from app.tools.search_kb import search_knowledge_base
from app.tools.search_literature import search_literature
from app.tools.search_web import search_web
from app.tools.think import think

logger = logging.getLogger(__name__)

# ── Native tools (MCP tools are appended at agent init) ──────────────────────

NATIVE_TOOLS = [
    think,
    search_knowledge_base,
    search_literature,
    ask_clarification,
    search_web,
    md_to_docx_convert,
]

# ── Prompt template ──────────────────────────────────────────────────────────

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("system", "{routing_hint}"),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ]
)


# ── LLM factory ──────────────────────────────────────────────────────────────


def _build_llm():
    """Instantiate the LLM через RouterAI (OpenAI-совместимый API)."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.routerai_model,
        api_key=settings.routerai_api_key,
        base_url=settings.routerai_base_url,
        temperature=settings.routerai_temperature,
        max_tokens=settings.routerai_max_tokens,
        max_retries=3,
        request_timeout=30,
    )


# ── Agent creation ───────────────────────────────────────────────────────────

_executor: AgentExecutor | None = None
_init_lock = asyncio.Lock()


async def get_agent() -> AgentExecutor:
    """Return a shared AgentExecutor instance (lazy-initialized, thread-safe)."""
    global _executor
    if _executor is not None:
        return _executor
    async with _init_lock:
        if _executor is not None:
            return _executor
        llm = _build_llm()
        mcp_tools = await load_mcp_tools_list()
        tools = NATIVE_TOOLS + mcp_tools
        agent = create_tool_calling_agent(llm, tools, PROMPT)
        _executor = AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=settings.max_agent_iterations,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
            verbose=False,
        )
        logger.info(
            "Агент инициализирован: model=%s tools=%d (native=%d mcp=%d) max_iterations=%d",
            settings.routerai_model,
            len(tools),
            len(NATIVE_TOOLS),
            len(mcp_tools),
            settings.max_agent_iterations,
        )
        return _executor


# ── Invoke ───────────────────────────────────────────────────────────────────


class AgentResult:
    """Structured result from agent invocation."""

    def __init__(
        self,
        answer: str,
        sources: list[dict[str, Any]],
        files: list[str],
        clarification: dict[str, Any] | None,
    ):
        self.answer = answer
        self.sources = sources
        self.files = files
        self.clarification = clarification


@tenacity.retry(
    retry=tenacity.retry_if_exception_type((ConnectionError, TimeoutError, RuntimeError)),
    wait=tenacity.wait_exponential(multiplier=1, min=2, max=30),
    stop=tenacity.stop_after_attempt(3),
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _invoke_with_retry(executor, user_input, chat_history, routing_hint, callbacks):
    return await executor.ainvoke(
        {
            "input": user_input,
            "chat_history": chat_history,
            "routing_hint": routing_hint,
        },
        config={"callbacks": callbacks},
    )


async def invoke(
    user_input: str,
    chat_history: list[BaseMessage],
    user_id: str = "unknown",
) -> AgentResult:
    """Run the agent and parse its output into a structured result."""
    executor = await get_agent()

    # Классифицируем запрос и даём агенту направляющую подсказку.
    from app.agent import classifier

    query_type = await classifier.classify(user_input)
    routing_hint = classifier.build_routing_hint(query_type)

    logger.info(
        "Запрос агента: user=%s type=%s msg_len=%d history_msgs=%d",
        user_id,
        query_type,
        len(user_input),
        len(chat_history),
    )

    # Callback handler для логирования каждого шага
    callbacks = [AgentCallbackHandler(user_id=user_id)]

    # Подсчёт токенов — необязательная обвязка поверх одного прогона агента.
    # Стоимость не считаем: тарифы get_openai_callback не применимы к RouterAI.
    try:
        from langchain_community.callbacks import get_openai_callback
    except Exception:
        get_openai_callback = None

    token_info = {}
    try:
        if get_openai_callback is None:
            result = await _invoke_with_retry(executor, user_input, chat_history, routing_hint, callbacks)
        else:
            async with get_openai_callback() as cb:
                result = await _invoke_with_retry(executor, user_input, chat_history, routing_hint, callbacks)
            token_info = {
                "prompt_tokens": cb.prompt_tokens,
                "completion_tokens": cb.completion_tokens,
            }
    except tenacity.RetryError as e:
        logger.error("Agent invocation failed after retries: %s", e)
        raise RuntimeError("LLM API недоступен после нескольких попыток") from e

    if token_info:
        logger.info(
            "Токены использованы: user=%s prompt=%d completion=%d",
            user_id,
            token_info["prompt_tokens"],
            token_info["completion_tokens"],
        )
        token_usage_total.labels(type="prompt").inc(token_info["prompt_tokens"])
        token_usage_total.labels(type="completion").inc(token_info["completion_tokens"])

    raw_output: str = result.get("output", "")
    intermediate_steps: list = result.get("intermediate_steps", [])

    # Проверка: не упёрся ли агент в лимит итераций
    if len(intermediate_steps) >= settings.max_agent_iterations:
        logger.warning(
            "Агент достиг лимита итераций: user=%s max=%d steps=%d",
            user_id,
            settings.max_agent_iterations,
            len(intermediate_steps),
        )

    # Проверка на ошибку парсинга в ответе LLM
    if not raw_output and not intermediate_steps:
        logger.error(
            "Агент вернул пустой ответ: user=%s steps=%d",
            user_id,
            len(intermediate_steps),
        )
    elif not raw_output or raw_output.startswith("Agent stopped due to"):
        logger.warning(
            "Агент остановлен с ошибкой: user=%s output=%s",
            user_id,
            raw_output[:200],
        )

    # Record tool usage metrics
    for action, _ in intermediate_steps:
        tool_calls_total.labels(tool_name=action.tool).inc()

    sources = extract_sources(intermediate_steps)
    files = extract_files(intermediate_steps)
    clarification = extract_clarification(raw_output, intermediate_steps)

    # If this is a clarification, the answer is the question text
    if clarification:
        answer = clarification["question"]
    else:
        answer = raw_output

    return AgentResult(
        answer=answer,
        sources=sources,
        files=files,
        clarification=clarification,
    )


# ── Parsing helpers ──────────────────────────────────────────────────────────


def parse_observation(observation: Any) -> dict[str, Any] | None:
    """Decode a single tool observation into a dict, or None if it isn't JSON."""
    try:
        data = json.loads(observation) if isinstance(observation, str) else observation
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def sources_from_observation(observation: Any) -> list[dict[str, Any]]:
    """Extract source references from a single tool observation."""
    data = parse_observation(observation)
    if not data:
        return []

    sources: list[dict[str, Any]] = []
    for chunk in data.get("chunks", []):
        src = chunk.get("source", "")
        if src:
            sources.append({"title": src, "snippet": chunk.get("text", "")[:200]})
    for r in data.get("results", []):
        url = r.get("url", "")
        if url:
            sources.append({"title": r.get("title", ""), "url": url, "snippet": r.get("snippet", "")})
    return sources


def files_from_observation(observation: Any) -> list[str]:
    """Extract download URLs from a single tool observation."""
    data = parse_observation(observation)
    if not data:
        return []

    files: list[str] = []
    if url := data.get("download_url"):
        files.append(url)
    for book in data.get("books", []) or []:
        if isinstance(book, dict) and (dl := book.get("download_url")):
            files.append(dl)
    return files


def extract_sources(steps: list) -> list[dict[str, Any]]:
    """Aggregate deduplicated source references across all tool outputs."""
    sources = []
    seen = set()
    for _action, observation in steps:
        for src in sources_from_observation(observation):
            key = src.get("url") or src.get("title")
            if key and key not in seen:
                seen.add(key)
                sources.append(src)
    return sources


def extract_files(steps: list) -> list[str]:
    """Aggregate download URLs across all tool outputs (md_to_docx, literature)."""
    files = []
    for _action, observation in steps:
        files.extend(files_from_observation(observation))
    return files


def extract_clarification(raw_output: str, steps: list) -> dict[str, Any] | None:
    """Detect if the agent output or any tool result contains a clarification."""
    # Check intermediate steps for clarification tool output
    for _action, observation in steps:
        if isinstance(observation, str) and observation.startswith(CLARIFICATION_PREFIX):
            payload = observation[len(CLARIFICATION_PREFIX) :]
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                pass

    # Also check raw output in case the agent echoed the clarification
    if CLARIFICATION_PREFIX in raw_output:
        idx = raw_output.index(CLARIFICATION_PREFIX) + len(CLARIFICATION_PREFIX)
        try:
            return json.loads(raw_output[idx:])
        except json.JSONDecodeError:
            pass

    return None
