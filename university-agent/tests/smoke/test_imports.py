"""Smoke tests: verify all imports work without infrastructure."""

from __future__ import annotations


class TestImports:
    """Ensure every module can be imported without runtime errors
    (assuming dependencies are installed)."""

    def test_import_config(self):
        import app.config

        assert app.config.settings is not None

    def test_import_schemas(self):
        import app.models.schemas

        assert app.models.schemas.ChatRequest is not None

    def test_import_database(self):
        import app.models.database

        assert app.models.database.Base is not None
        assert app.models.database.KnowledgeDocument is not None

    def test_import_middleware_auth(self):
        import app.middleware.auth

        assert app.middleware.auth.APIKeyMiddleware is not None

    def test_import_middleware_request_id(self):
        import app.middleware.request_id

        assert app.middleware.request_id.RequestIDMiddleware is not None

    def test_import_guardrails(self):
        import app.agent.guardrails

        assert app.agent.guardrails.check_injection is not None

    def test_import_prompts(self):
        import app.agent.prompts

        assert len(app.agent.prompts.SYSTEM_PROMPT) > 100

    def test_import_logging_config(self):
        import app.logging_config

        assert app.logging_config.setup_logging is not None

    def test_import_metrics(self):
        import app.metrics

        assert app.metrics.chat_requests_total is not None

    def test_import_tools_ask_clarification(self):
        import app.tools.ask_clarification

        assert app.tools.ask_clarification.CLARIFICATION_PREFIX is not None

    def test_import_tools_search_kb(self):
        import app.tools.search_kb

        assert app.tools.search_kb.search_knowledge_base is not None

    def test_import_tools_search_literature(self):
        import app.tools.search_literature

        assert app.tools.search_literature.search_literature is not None

    def test_import_tools_think(self):
        import app.tools.think

        assert app.tools.think.think is not None

    def test_import_tools_search_web(self):
        import app.tools.search_web

        assert app.tools.search_web.search_web is not None

    def test_import_tools_md_to_docx(self):
        import app.tools.md_to_docx

        assert app.tools.md_to_docx.md_to_docx_convert is not None
