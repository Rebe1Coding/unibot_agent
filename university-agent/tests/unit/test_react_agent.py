"""Unit tests: agent result parsing and LLM factory."""

from __future__ import annotations

import json

import pytest


class TestExtractSources:
    """Parsing of source references from intermediate steps."""

    def test_empty_steps(self):
        from app.agent.react_agent import extract_sources

        assert extract_sources([]) == []

    def test_kb_chunks(self):
        from app.agent.react_agent import extract_sources

        observation = json.dumps(
            {
                "found": True,
                "chunks": [
                    {"text": "Текст про поступление", "source": "rules.pdf", "section": "Правила"},
                    {"text": "Проходные баллы 2025", "source": "scores.pdf"},
                ],
            }
        )
        steps = [(_FakeAction("search_knowledge_base"), observation)]
        sources = extract_sources(steps)
        assert len(sources) == 2
        assert sources[0]["title"] == "rules.pdf"
        assert sources[0]["snippet"] == "Текст про поступление"
        assert sources[1]["title"] == "scores.pdf"

    def test_web_search_results(self):
        from app.agent.react_agent import extract_sources

        observation = json.dumps(
            {
                "found": True,
                "results": [
                    {"title": "Wikipedia", "url": "https://wiki.example.com", "snippet": "Some text"},
                ],
            }
        )
        steps = [(_FakeAction("search_web"), observation)]
        sources = extract_sources(steps)
        assert len(sources) == 1
        assert sources[0]["title"] == "Wikipedia"
        assert sources[0]["url"] == "https://wiki.example.com"

    def test_deduplication_by_title(self):
        from app.agent.react_agent import extract_sources

        obs1 = json.dumps({"found": True, "chunks": [{"text": "A", "source": "doc1.pdf"}]})
        obs2 = json.dumps({"found": True, "chunks": [{"text": "B", "source": "doc1.pdf"}]})
        steps = [
            (_FakeAction("search_knowledge_base"), obs1),
            (_FakeAction("search_knowledge_base"), obs2),
        ]
        sources = extract_sources(steps)
        assert len(sources) == 1  # deduplicated

    def test_invalid_json_skipped(self):
        from app.agent.react_agent import extract_sources

        steps = [(_FakeAction("search_knowledge_base"), "not valid json {")]
        sources = extract_sources(steps)
        assert sources == []

    def test_non_string_observation(self):
        from app.agent.react_agent import extract_sources

        steps = [(_FakeAction("search_knowledge_base"), {"found": True, "chunks": []})]
        sources = extract_sources(steps)
        assert sources == []


class TestExtractFiles:
    """Parsing of file download URLs from intermediate steps."""

    def test_empty_steps(self):
        from app.agent.react_agent import extract_files

        assert extract_files([]) == []

    def test_md_to_docx_url(self):
        from app.agent.react_agent import extract_files

        observation = json.dumps({"success": True, "download_url": "http://minio/doc.docx"})
        steps = [(_FakeAction("md_to_docx_convert"), observation)]
        files = extract_files(steps)
        assert files == ["http://minio/doc.docx"]

    def test_literature_books(self):
        from app.agent.react_agent import extract_files

        observation = json.dumps(
            {
                "found": True,
                "books": [
                    {"title": "Учебник", "download_url": "http://minio/book1.pdf"},
                    {"title": "Без ссылки"},
                ],
            }
        )
        steps = [(_FakeAction("search_literature"), observation)]
        files = extract_files(steps)
        assert files == ["http://minio/book1.pdf"]  # only those with download_url


class TestExtractClarification:
    """Detection of clarification tool output."""

    def test_no_clarification(self):
        from app.agent.react_agent import extract_clarification

        assert extract_clarification("Normal answer.", []) is None

    def test_from_intermediate_step(self):
        from app.agent.react_agent import CLARIFICATION_PREFIX, extract_clarification

        payload = json.dumps({"question": "Какой курс?", "options": [{"label": "1", "value": "1"}]})
        observation = f"{CLARIFICATION_PREFIX}{payload}"
        steps = [(_FakeAction("ask_clarification"), observation)]
        result = extract_clarification("Some output", steps)
        assert result is not None
        assert result["question"] == "Какой курс?"
        assert len(result["options"]) == 1

    def test_from_raw_output(self):
        from app.agent.react_agent import CLARIFICATION_PREFIX, extract_clarification

        payload = json.dumps({"question": "Уточните группу", "options": []})
        raw_output = f"Вот ответ... {CLARIFICATION_PREFIX}{payload}"
        result = extract_clarification(raw_output, [])
        assert result is not None
        assert result["question"] == "Уточните группу"

    def test_garbled_prefix_returns_none(self):
        from app.agent.react_agent import extract_clarification

        result = extract_clarification("__CLARIFICATION__not valid json", [])
        assert result is None

    def test_multiple_steps_first_wins(self):
        from app.agent.react_agent import CLARIFICATION_PREFIX, extract_clarification

        obs1 = f'{CLARIFICATION_PREFIX}{{"question": "Первая", "options": []}}'
        obs2 = f'{CLARIFICATION_PREFIX}{{"question": "Вторая", "options": []}}'
        steps = [(_FakeAction("ask_clarification"), obs1), (_FakeAction("ask_clarification"), obs2)]
        result = extract_clarification("", steps)
        assert result["question"] == "Первая"


class TestLLMFactory:
    """LLM provider instantiation."""

    def test_routerai_provider(self, monkeypatch):
        monkeypatch.setenv("ROUTERAI_API_KEY", "sk-test")
        monkeypatch.setenv("ROUTERAI_MODEL", "openai/gpt-4o")

        from app.agent.react_agent import _build_llm

        llm = _build_llm()
        assert llm is not None


class TestAgentResult:
    """AgentResult data class."""

    def test_full_result(self):
        from app.agent.react_agent import AgentResult

        r = AgentResult(
            answer="Ответ",
            sources=[{"title": "src"}],
            files=["file.docx"],
            clarification=None,
        )
        assert r.answer == "Ответ"
        assert len(r.sources) == 1
        assert len(r.files) == 1
        assert r.clarification is None

    def test_clarification_result(self):
        from app.agent.react_agent import AgentResult

        r = AgentResult(
            answer="Уточните курс",
            sources=[],
            files=[],
            clarification={"question": "Какой курс?", "options": []},
        )
        assert r.clarification["question"] == "Какой курс?"


class TestInvokeRetry:
    """Retry logic for agent invocation."""

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        """Agent invoke retries on transient errors."""
        from app.agent.react_agent import _invoke_with_retry

        executor = _FakeExecutor(failures=2)
        result = await _invoke_with_retry(executor, "test", [], "", callbacks=[])
        assert result["output"] == "success after retry"


# ── Helpers ──────────────────────────────────────────────────────────────────


class _FakeAction:
    """Minimal fake for AgentAction used in tests."""

    def __init__(self, tool: str):
        self.tool = tool


class _FakeExecutor:
    """Fake AgentExecutor that fails N times then succeeds."""

    def __init__(self, failures: int = 0):
        self.call_count = 0
        self.failures = failures

    async def ainvoke(self, input_data: dict, config: dict | None = None) -> dict:
        self.call_count += 1
        if self.call_count <= self.failures:
            raise ConnectionError("Simulated connection failure")
        return {"output": "success after retry"}
