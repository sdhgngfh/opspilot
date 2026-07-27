from __future__ import annotations

import os
from contextlib import suppress
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
        "ticket": None,
        "ticket_thread_id": f"ticket-{uuid4().hex[:8]}",
        "access_token": None,
        "current_user": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _client(base_url: str) -> OpsPilotClient:
    return OpsPilotClient(
        base_url,
        access_token=st.session_state.access_token,
    )


def _render_citations(citations: list[dict[str, object]]) -> None:
    if not citations:
        return
    with st.expander(f"来源证据 · {len(citations)} 条"):
        for citation in citations:
            details = citation.get("retrieval_details", {})
            st.markdown(
                f"**[{citation['rank']}] {citation['title']}**  \n"
                f"`{citation['source']}` · chunk `{citation['chunk_id']}` · "
                f"综合分 `{citation['score']:.3f}`"
            )
            st.caption(str(citation["excerpt"]))
            st.json(details, expanded=False)


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


def _ticket_status(ticket: dict[str, object]) -> None:
    status = str(ticket["status"])
    color = {
        "awaiting_approval": "orange",
        "submitted": "green",
        "rejected": "red",
    }[status]
    st.markdown(f"状态：:{color}[**{status}**]")
    st.json(ticket["draft"], expanded=True)
    with st.expander("待执行工具调用与审计日志"):
        st.json(ticket["tool_call"])
        st.dataframe(ticket["audit_events"], width="stretch", hide_index=True)


def _ticket_tab(client: OpsPilotClient) -> None:
    st.subheader("工单工具与人工审批")
    st.caption("生成草稿不会写入业务库；只有人工批准后才执行 submit_ticket。")
    ticket = st.session_state.ticket
    if ticket is None:
        with st.form("ticket-create"):
            request_text = st.text_area(
                "运维请求",
                "销售人员可以看到其他部门订单，请创建权限修复工单。",
            )
            default_requester = (
                st.session_state.current_user["username"]
                if st.session_state.current_user
                else "local-demo-user"
            )
            requester = st.text_input("申请人", default_requester, disabled=True)
            submitted = st.form_submit_button("生成工单草稿", type="primary")
        if submitted:
            try:
                st.session_state.ticket = client.start_ticket(
                    request_text,
                    requester,
                    st.session_state.ticket_thread_id,
                )
                st.rerun()
            except OpsPilotAPIError as exc:
                st.error(str(exc))
        return

    _ticket_status(ticket)
    if ticket["status"] == "awaiting_approval":
        default_reviewer = (
            st.session_state.current_user["username"]
            if st.session_state.current_user
            else "ops-lead"
        )
        reviewer = st.text_input("审批人", default_reviewer, disabled=True)
        approve_col, reject_col = st.columns(2)
        if approve_col.button("批准并提交", type="primary", width="stretch"):
            try:
                st.session_state.ticket = client.review_ticket(
                    st.session_state.ticket_thread_id,
                    action="approve",
                    reviewer=reviewer,
                )
                st.rerun()
            except OpsPilotAPIError as exc:
                st.error(str(exc))
        if reject_col.button("拒绝", width="stretch"):
            try:
                st.session_state.ticket = client.review_ticket(
                    st.session_state.ticket_thread_id,
                    action="reject",
                    reviewer=reviewer,
                )
                st.rerun()
            except OpsPilotAPIError as exc:
                st.error(str(exc))

        with st.expander("修改后批准"):
            draft = ticket["draft"]
            with st.form("ticket-edit"):
                title = st.text_input("标题", str(draft["title"]))
                priority = st.selectbox(
                    "优先级",
                    ["low", "medium", "high", "critical"],
                    index=["low", "medium", "high", "critical"].index(
                        str(draft["priority"])
                    ),
                )
                edit_submitted = st.form_submit_button("提交修改并批准")
            if edit_submitted:
                try:
                    st.session_state.ticket = client.review_ticket(
                        st.session_state.ticket_thread_id,
                        action="edit",
                        reviewer=reviewer,
                        changes={"title": title, "priority": priority},
                    )
                    st.rerun()
                except OpsPilotAPIError as exc:
                    st.error(str(exc))
    if st.button("开始新的工单流程"):
        st.session_state.ticket = None
        st.session_state.ticket_thread_id = f"ticket-{uuid4().hex[:8]}"
        st.rerun()


def _documents_tab(client: OpsPilotClient) -> None:
    st.subheader("知识库管理")
    uploaded = st.file_uploader("上传 Markdown、TXT 或 PDF", type=["md", "txt", "pdf"])
    replace = st.checkbox("同名文件存在时覆盖")
    classification = st.selectbox(
        "文档等级",
        ["internal", "restricted", "public"],
    )
    roles_text = st.text_input("允许角色（逗号分隔）", "admin,support")
    departments_text = st.text_input("允许部门（逗号分隔）", "it")
    if uploaded and st.button("上传并重建索引", type="primary"):
        try:
            with st.spinner("正在解析文档并重建索引…"):
                result = client.upload_document(
                    uploaded.name,
                    uploaded.getvalue(),
                    uploaded.type or "application/octet-stream",
                    replace=replace,
                    allowed_roles=[
                        item.strip() for item in roles_text.split(",") if item.strip()
                    ],
                    allowed_departments=[
                        item.strip()
                        for item in departments_text.split(",")
                        if item.strip()
                    ],
                    classification=classification,
                )
            st.success(
                f"完成：{result['documents']} 份文档，{result['chunks']} 个分块。"
            )
            st.json(result)
        except OpsPilotAPIError as exc:
            st.error(str(exc))


def main() -> None:
    _init_state()
    base_url = os.getenv("OPSPILOT_API_URL", "http://127.0.0.1:8000")
    client = _client(base_url)
    info: dict[str, object] | None = None
    with suppress(OpsPilotAPIError):
        info = client.system_info()

    if info and info.get("auth_enabled") and not st.session_state.access_token:
        st.markdown('<div class="op-kicker">SECURE ACCESS</div>', unsafe_allow_html=True)
        st.title("登录 OpsPilot")
        if info.get("auth_provider") == "oidc":
            st.caption("粘贴企业身份平台签发的 OIDC Access Token。")
            with st.form("oidc-login"):
                access_token = st.text_input("企业 Access Token", type="password")
                submitted = st.form_submit_button("验证并登录", type="primary")
            if submitted:
                client.set_access_token(access_token)
                try:
                    current_user = client.me()
                    st.session_state.access_token = access_token
                    st.session_state.current_user = current_user
                    st.rerun()
                except OpsPilotAPIError as exc:
                    st.error(str(exc))
        else:
            with st.form("login"):
                username = st.text_input("用户名")
                password = st.text_input("密码", type="password")
                submitted = st.form_submit_button("登录", type="primary")
            if submitted:
                try:
                    token = client.login(username, password)
                    st.session_state.access_token = token["access_token"]
                    st.rerun()
                except OpsPilotAPIError as exc:
                    st.error(str(exc))
        return

    if info and info.get("auth_enabled"):
        try:
            st.session_state.current_user = client.me()
        except OpsPilotAPIError:
            st.session_state.access_token = None
            st.session_state.current_user = None
            st.rerun()

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
                f"**重排** `{info['reranker_provider']}`  \n"
                f"**追踪** `{'on' if info['tracing_enabled'] else 'off'}`"
            )
        except OpsPilotAPIError:
            st.error("API 未连接")
            st.caption(f"请启动：{base_url}")
        st.divider()
        if st.session_state.current_user:
            user = st.session_state.current_user
            st.markdown(f"**用户** `{user['username']}`")
            st.caption(
                f"角色：{', '.join(user['roles'])} · "
                f"部门：{', '.join(user['departments'])}"
            )
            if st.button("退出登录", width="stretch"):
                st.session_state.access_token = None
                st.session_state.current_user = None
                st.session_state.messages = []
                st.rerun()
        st.text_input("会话 thread_id", key="thread_id")
        if st.button("清空当前对话", width="stretch"):
            st.session_state.messages = []
            st.session_state.thread_id = f"demo-{uuid4().hex[:8]}"
            st.rerun()

    st.markdown('<div class="op-kicker">ENTERPRISE AI OPERATIONS</div>', unsafe_allow_html=True)
    st.title("OpsPilot 智能运维助手")
    chat, tickets, documents = st.tabs(["知识问答", "工单审批", "知识库"])
    with chat:
        _chat_tab(client)
    with tickets:
        _ticket_tab(client)
    with documents:
        _documents_tab(client)


if __name__ == "__main__":
    main()
