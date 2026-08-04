from __future__ import annotations

import os
from uuid import uuid4

import streamlit as st

from frontend.client import OpsPilotAPIError, OpsPilotClient

st.set_page_config(
    page_title="OpsPilot",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: #f7f8fa; }
    [data-testid="stSidebar"] { background: #111827; color: #f9fafb; }
    [data-testid="stSidebar"] * { color: #f9fafb; }
    [data-testid="stSidebar"] code {
        background: #1f2937; color: #dbeafe !important;
    }
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] button,
    [data-testid="stSidebar"] button * {
        color: #111827 !important;
    }
    .op-card {
        border: 1px solid #e5e7eb; border-radius: 14px; padding: 1rem;
        background: white; margin-bottom: .75rem;
    }
    .op-kicker { color: #2563eb; font-size: .8rem; font-weight: 700; letter-spacing: .08em; }
    .op-muted { color: #6b7280; font-size: .9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _init_state() -> None:
    defaults = {
        "thread_id": f"demo-{uuid4().hex[:8]}",
        "messages": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _client(base_url: str) -> OpsPilotClient:
    return OpsPilotClient(base_url)


def _render_citations(citations: list[dict[str, object]]) -> None:
    if not citations:
        return
    with st.expander(f"来源证据 · {len(citations)} 条"):
        for citation in citations:
            st.markdown(
                f"**[{citation['rank']}] {citation['title']}**  \n"
                f"`{citation['source']}` · chunk `{citation['chunk_id']}` · "
                f"综合分 `{citation['score']:.3f}`"
            )
            st.caption(str(citation["excerpt"]))


def _render_trace(response: dict[str, object]) -> None:
    with st.expander("Agent 执行轨迹"):
        left, right, third = st.columns(3)
        left.metric("查询改写", int(response["rewrite_count"]))
        right.metric("证据分", f"{float(response['evidence_score']):.3f}")
        third.metric("检索次数", len(response["attempts"]))
        st.code(" → ".join(response["execution_path"]), language=None)
        st.caption(str(response["evidence_reason"]))
        st.dataframe(response["attempts"], width="stretch", hide_index=True)


def _chat_tab(client: OpsPilotClient) -> None:
    st.subheader("企业知识问答")
    st.caption("LangGraph 会自动判断证据、改写弱查询并在证据不足时拒答。")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                _render_citations(message.get("citations", []))
                if message.get("trace"):
                    _render_trace(message["trace"])

    if question := st.chat_input("例如：为什么销售人员能看到其他部门的订单？"):
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                with st.spinner("正在检索并验证证据…"):
                    response = client.ask(question, st.session_state.thread_id)
            except OpsPilotAPIError as exc:
                st.error(str(exc))
                return
            st.markdown(response["answer"])
            _render_citations(response["citations"])
            _render_trace(response)
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": response["answer"],
                    "citations": response["citations"],
                    "trace": response,
                }
            )


def main() -> None:
    _init_state()
    base_url = os.getenv("OPSPILOT_API_URL", "http://127.0.0.1:8000")
    client = _client(base_url)

    with st.sidebar:
        st.markdown("## OpsPilot")
        st.caption("Agentic RAG · Interview Demo")
        try:
            info = client.system_info()
            st.success("API 已连接")
            st.markdown(
                f"**模式** `{info['rag_mode']}`  \n"
                f"**索引** `{info['index_backend']}`  \n"
                f"**状态** `{info['persistence_backend']}`  \n"
                f"**检索** `{info['retrieval_strategy']}`  \n"
                f"**重排** `{info['reranker_provider']}`"
            )
        except OpsPilotAPIError:
            st.error("API 未连接")
            st.caption(f"请启动：{base_url}")
        st.divider()
        st.text_input("会话 thread_id", key="thread_id")
        if st.button("清空当前对话", width="stretch"):
            st.session_state.messages = []
            st.session_state.thread_id = f"demo-{uuid4().hex[:8]}"
            st.rerun()

    st.markdown(
        '<div class="op-kicker">ENTERPRISE AI OPERATIONS</div>',
        unsafe_allow_html=True,
    )
    st.title("OpsPilot 智能运维助手")
    _chat_tab(client)


if __name__ == "__main__":
    main()
