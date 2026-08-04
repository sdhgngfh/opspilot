from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from streamlit.testing.v1 import AppTest

APP_TEST_TIMEOUT_SECONDS = 30


class _DemoAPIHandler(BaseHTTPRequestHandler):
    def _json(self, payload: dict[str, object], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/v1/system/info":
            self._json(
                {
                    "version": "test",
                    "rag_mode": "local",
                    "index_backend": "local",
                    "persistence_backend": "local",
                    "retrieval_strategy": "hybrid_rerank",
                    "reranker_provider": "local",
                    "tracing_enabled": False,
                    "auth_enabled": False,
                }
            )
            return
        self._json({"detail": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/v1/graph/ask":
            self._json(
                {
                    "answer": "根据授权证据，应检查部门数据权限。",
                    "citations": [
                        {
                            "rank": 1,
                            "title": "权限手册",
                            "source": "permissions.md",
                            "chunk_id": "chunk-1",
                            "score": 0.9,
                            "excerpt": "按部门限制数据权限。",
                        }
                    ],
                    "rewrite_count": 1,
                    "evidence_score": 0.9,
                    "attempts": [{"query": "部门权限"}],
                    "execution_path": ["prepare_query", "retrieve", "generate_answer"],
                    "evidence_reason": "证据充分",
                }
            )
            return
        self._json({"detail": "not found"}, 404)

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture
def demo_api() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _DemoAPIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_streamlit_offline_state_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPSPILOT_API_URL", "http://127.0.0.1:1")

    app = AppTest.from_file(
        "frontend/streamlit_app.py",
        default_timeout=APP_TEST_TIMEOUT_SECONDS,
    ).run()

    assert not app.exception
    assert app.title[0].value == "OpsPilot 智能运维助手"
    assert [tab.label for tab in app.tabs] == []
    assert any(error.value == "API 未连接" for error in app.error)
    assert len(app.session_state["thread_id"]) > len("demo-")


def test_streamlit_chat_happy_path(
    demo_api: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPSPILOT_API_URL", demo_api)
    app = AppTest.from_file(
        "frontend/streamlit_app.py",
        default_timeout=APP_TEST_TIMEOUT_SECONDS,
    ).run()

    app.chat_input[0].set_value("怎么限制跨部门订单？").run()

    assert not app.exception
    assert any(success.value == "API 已连接" for success in app.success)
    assert len(app.chat_message) == 2
    assert app.session_state["messages"][0]["role"] == "user"
    assert app.session_state["messages"][1]["role"] == "assistant"
    assert "部门数据权限" in app.session_state["messages"][1]["content"]
    assert any(code.value == "prepare_query → retrieve → generate_answer" for code in app.code)
