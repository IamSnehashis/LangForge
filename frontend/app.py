"""
LangForge Frontend - Streamlit UI
"""

import streamlit as st
import requests
import json
import time
from typing import Optional

# Configuration
API_BASE = "http://localhost:8000/api/v1"
st.set_page_config(
    page_title="LangForge",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: 700; color: #6C63FF; }
    .sub-header { font-size: 1rem; color: #888; margin-bottom: 1rem; }
    .msg-user { background: #1a1a2e; border-radius: 12px; padding: 10px 14px; margin: 4px 0; }
    .msg-assistant { background: #16213e; border-radius: 12px; padding: 10px 14px; margin: 4px 0; }
    .status-badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }
    .badge-green { background: #1a4731; color: #4ade80; }
    .badge-red { background: #4a1a1a; color: #f87171; }
    .stButton>button { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


# API Helpers

def get_headers() -> dict:
    token = st.session_state.get("token")
    if token:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return {"Content-Type": "application/json"}


def api_post(path: str, data: dict, auth: bool = True) -> Optional[dict]:
    try:
        headers = get_headers() if auth else {"Content-Type": "application/json"}
        resp = requests.post(f"{API_BASE}{path}", json=data, headers=headers, timeout=30)
        
        # Try to parse JSON regardless of status code
        try:
            result = resp.json()
        except Exception:
            st.error(f"Backend returned invalid response (status {resp.status_code}). Is the backend running?")
            return None
        
        if resp.status_code in (200, 201):
            return result
        else:
            detail = result.get('detail', 'Unknown error') if isinstance(result, dict) else str(result)
            st.error(f"Error {resp.status_code}: {detail}")
            return None

    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to backend at http://localhost:8000. Is it running?")
    except requests.exceptions.Timeout:
        st.error("❌ Request timed out. Backend may be overloaded.")
    except Exception as e:
        st.error(f"Request failed: {e}")
    return None

def api_get(path: str, params: dict = None) -> Optional[dict]:
    try:
        resp = requests.get(f"{API_BASE}{path}", headers=get_headers(), params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 401:
            st.session_state.clear()
            st.rerun()
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to backend.")
    except Exception as e:
        st.error(f"Request failed: {e}")
    return None


def api_delete(path: str) -> bool:
    try:
        resp = requests.delete(f"{API_BASE}{path}", headers=get_headers(), timeout=10)
        return resp.status_code == 204
    except Exception:
        return False


# Auth Pages

def show_auth_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="main-header">⚡ LangForge</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-header">Production GenAI Framework with integrated DBMS</div>', unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["🔑 Login", "📝 Register"])

        with tab1:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True, type="primary")
                if submitted:
                    result = api_post("/auth/login", {"email": email, "password": password}, auth=False)
                    if result:
                        st.session_state["token"] = result["access_token"]
                        st.session_state["user"] = result["user"]
                        st.success("✅ Logged in!")
                        st.rerun()

        with tab2:
            with st.form("register_form"):
                name = st.text_input("Name", placeholder="Your name")
                email = st.text_input("Email", placeholder="you@example.com", key="reg_email")
                password = st.text_input("Password", type="password", key="reg_pass")
                password2 = st.text_input("Confirm Password", type="password")
                submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")
                if submitted:
                    if password != password2:
                        st.error("Passwords do not match")
                    elif len(password) < 6:
                        st.error("Password must be at least 6 characters")
                    else:
                        result = api_post(
                            "/auth/register",
                            {"name": name, "email": email, "password": password},
                            auth=False,
                        )
                        if result:
                            st.session_state["token"] = result["access_token"]
                            st.session_state["user"] = result["user"]
                            st.success("✅ Account created!")
                            st.rerun()


# Sidebar

def show_sidebar():
    with st.sidebar:
        user = st.session_state.get("user", {})
        st.markdown(f"### 👤 {user.get('name', 'User')}")
        st.markdown(f"*{user.get('email', '')}*")
        st.divider()

        # Navigation
        page = st.radio(
            "Navigation",
            ["💬 Chat", "📄 Documents", "🤖 Agent", "📊 Dashboard"],
            label_visibility="collapsed",
        )

        st.divider()

        # Health status
        health = api_get("/health")
        if health:
            db_status = "🟢" if health.get("database_connected") else "🔴"
            llm_status = "🟢" if health.get("ollama_connected") else "🔴"
            st.markdown(f"**System Status**")
            st.markdown(f"{db_status} Database  •  {llm_status} LLM")
        
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    return page.split(" ", 1)[1] if " " in page else page


# Chat Page

def show_chat_page():
    st.markdown("## 💬 Chat")

    col1, col2 = st.columns([1, 3])

    with col1:
        st.markdown("**Conversations**")
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            result = api_post("/chat/", {"title": "New Chat"})
            if result:
                st.session_state["active_chat_id"] = result["chat_id"]
                st.rerun()

        chats = api_get("/chat/") or []
        for chat in chats:
            active = chat["chat_id"] == st.session_state.get("active_chat_id")
            label = f"{'▶ ' if active else ''}{chat['title'][:28]}"
            if st.button(label, key=f"chat_{chat['chat_id']}", use_container_width=True):
                st.session_state["active_chat_id"] = chat["chat_id"]
                st.rerun()

            if active:
                if st.button("🗑️ Delete", key=f"del_{chat['chat_id']}", use_container_width=True):
                    if api_delete(f"/chat/{chat['chat_id']}"):
                        st.session_state.pop("active_chat_id", None)
                        st.rerun()

    with col2:
        chat_id = st.session_state.get("active_chat_id")
        if not chat_id:
            st.info("👈 Select or create a conversation to start chatting")
            return

        chat_data = api_get(f"/chat/{chat_id}")
        if not chat_data:
            return

        # Display chat options
        use_rag = st.toggle("🔍 Enable RAG (use uploaded documents)", value=False)

        # Display messages
        messages = chat_data.get("messages", [])
        chat_container = st.container()
        with chat_container:
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                with st.chat_message(role, avatar="🧑" if role == "user" else "🤖"):
                    st.markdown(content)

        # Message input
        if prompt := st.chat_input("Ask anything..."):
            # Show user message immediately
            with st.chat_message("user", avatar="🧑"):
                st.markdown(prompt)

            # Stream response
            with st.chat_message("assistant", avatar="🤖"):
                response_placeholder = st.empty()
                full_response = ""

                try:
                    with requests.post(
                        f"{API_BASE}/chat/{chat_id}/messages/stream",
                        json={"content": prompt, "use_rag": use_rag},
                        headers=get_headers(),
                        stream=True,
                        timeout=120,
                    ) as resp:
                        for line in resp.iter_lines():
                            if line:
                                line = line.decode("utf-8")
                                if line.startswith("data: "):
                                    try:
                                        data = json.loads(line[6:])
                                        if data.get("type") == "token":
                                            full_response += data.get("content", "")
                                            response_placeholder.markdown(full_response + "▌")
                                        elif data.get("type") == "done":
                                            response_placeholder.markdown(full_response)
                                            break
                                        elif data.get("type") == "error":
                                            st.error(data.get("message"))
                                            break
                                    except json.JSONDecodeError:
                                        pass
                except Exception as e:
                    st.error(f"Streaming failed: {e}. Trying non-streaming...")
                    # Fallback to non-streaming
                    result = api_post(f"/chat/{chat_id}/messages", {"content": prompt, "use_rag": use_rag})
                    if result:
                        response_placeholder.markdown(result["content"])

            st.rerun()


# Documents Page

def show_documents_page():
    st.markdown("## 📄 Document Management & RAG")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("### Upload Document")
        uploaded = st.file_uploader(
            "Upload a document to add to your knowledge base",
            type=["txt", "pdf", "docx", "md", "csv", "py", "js", "json"],
            help="Supported formats: TXT, PDF, DOCX, MD, CSV, PY, JS, JSON",
        )
        if uploaded:
            if st.button("📤 Ingest Document", type="primary", use_container_width=True):
                with st.spinner("Uploading and generating embeddings..."):
                    try:
                        resp = requests.post(
                            f"{API_BASE}/documents/upload",
                            files={"file": (uploaded.name, uploaded.getvalue())},
                            headers={"Authorization": f"Bearer {st.session_state.get('token')}"},
                            timeout=120,
                        )
                        if resp.status_code == 201:
                            doc = resp.json()
                            st.success(f"✅ Ingested '{doc['original_filename']}' — {doc['chunk_count']} chunks")
                            st.rerun()
                        else:
                            st.error(f"Upload failed: {resp.json().get('detail', 'Unknown error')}")
                    except Exception as e:
                        st.error(f"Upload error: {e}")

    with col2:
        st.markdown("### RAG Query")
        query = st.text_area("Query your documents", placeholder="What is the main topic of my uploaded documents?")
        top_k = st.slider("Top K results", 1, 10, 5)
        if st.button("🔍 Search", type="primary", use_container_width=True):
            if query:
                with st.spinner("Searching..."):
                    result = api_post("/documents/query/rag", {"query": query, "top_k": top_k})
                    if result:
                        st.markdown(f"**Found {result['total_chunks']} relevant chunks:**")
                        for i, chunk in enumerate(result.get("chunks", []), 1):
                            with st.expander(f"Chunk {i}"):
                                st.text(chunk)

    st.divider()
    st.markdown("### My Documents")
    docs = api_get("/documents/") or []
    if not docs:
        st.info("No documents uploaded yet. Upload files above to enable RAG.")
        return

    for doc in docs:
        col_a, col_b, col_c, col_d = st.columns([3, 1, 1, 1])
        with col_a:
            st.markdown(f"📄 **{doc['original_filename']}**")
        with col_b:
            size_kb = (doc.get("file_size") or 0) / 1024
            st.markdown(f"{size_kb:.1f} KB")
        with col_c:
            st.markdown(f"{doc['chunk_count']} chunks")
        with col_d:
            if st.button("🗑️", key=f"doc_{doc['document_id']}"):
                if api_delete(f"/documents/{doc['document_id']}"):
                    st.success("Deleted")
                    st.rerun()


# Agent Page

def show_agent_page():
    st.markdown("## 🤖 ReAct Agent")

    # List available tools
    tools_data = api_get("/agents/tools") or {}
    tools = tools_data.get("tools", [])

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### Available Tools")
        for tool in tools:
            with st.expander(f"🔧 {tool['name']}"):
                st.write(tool["description"])

    with col2:
        st.markdown("### Run Agent")
        with st.form("agent_form"):
            query = st.text_area(
                "Task / Query",
                placeholder="Calculate 15% of 2847, then tell me the current time.",
                height=100,
            )
            agent_name = st.selectbox("Agent", ["react_agent"])
            submitted = st.form_submit_button("▶ Run Agent", type="primary", use_container_width=True)

        if submitted and query:
            with st.spinner("Agent is working... (this may take a minute)"):
                result = None
                try:
                    resp = requests.post(
                        f"{API_BASE}/agents/run",
                        json={"query": query, "agent_name": agent_name},
                        headers=get_headers(),
                        timeout=300,  # 5 minutes for multi-step agent
                    )
                    if resp.status_code == 200:
                        result = resp.json()
                    else:
                        try:
                            detail = resp.json().get("detail", "Unknown error")
                        except Exception:
                            detail = resp.text or "Unknown error"
                        st.error(f"Error {resp.status_code}: {detail}")
                except requests.exceptions.Timeout:
                    st.error("❌ Agent timed out after 5 minutes. Try a simpler query or check Ollama is running.")
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot connect to backend. Is it running on port 8000?")
                except Exception as e:
                    st.error(f"Request failed: {e}")

                if result:
                    st.success(f"**Final Answer:** {result['final_answer']}")
                    total_ms = result.get('total_duration_ms') or 0
                    st.markdown(f"*{result['total_steps']} steps · {total_ms:.0f}ms*")

                    st.markdown("### Execution Trace")
                    for step in result.get("steps", []):
                        action_icon = {
                            "think": "💭",
                            "tool_call": "🔧",
                            "final_answer": "✅",
                        }.get(step["action"], "➡️")
                        tool_label = f"[{step['tool_name']}]" if step.get("tool_name") else ""
                        with st.expander(
                            f"{action_icon} Step {step['step_number']}: "
                            f"{step['action'].replace('_', ' ').title()} {tool_label}"
                        ):
                            if step.get("action_input"):
                                st.markdown(f"**Input:** {step['action_input']}")
                            if step.get("action_output"):
                                st.markdown(f"**Output:** {step['action_output']}")
                            if step.get("duration_ms"):
                                st.caption(f"{step['duration_ms'] or 0:.0f}ms")

    st.divider()
    st.markdown("### Recent Agent Logs")
    logs = api_get("/agents/logs", {"limit": 20}) or []
    if logs:
        import pandas as pd
        df = pd.DataFrame([
            {
                "Time": log["timestamp"][:19].replace("T", " "),
                "Agent": log["agent_name"],
                "Action": log["action"],
                "Tool": log.get("tool_name") or "-",
                "Status": log["status"],
                "Duration (ms)": f"{log.get('duration_ms') or 0:.0f}",
            }
            for log in logs
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No agent logs yet. Run an agent task above.")

# Dashboard Page

def show_dashboard_page():
    st.markdown("## 📊 System Dashboard")

    health = api_get("/health") or {}
    chats = api_get("/chat/") or []
    docs = api_get("/documents/") or []
    agent_logs = api_get("/agents/logs", {"limit": 100}) or []

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💬 Total Chats", len(chats))
    with col2:
        st.metric("📄 Documents", len(docs))
    with col3:
        total_chunks = sum(d.get("chunk_count", 0) for d in docs)
        st.metric("🔢 Vector Chunks", total_chunks)
    with col4:
        st.metric("🤖 Agent Steps", len(agent_logs))

    st.divider()
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("### System Health")
        services = health.get("services", {})
        for svc, status in services.items():
            icon = "🟢" if "connect" in status or "running" in status else "🔴"
            st.markdown(f"{icon} **{svc.title()}**: {status}")

        st.markdown("---")
        st.markdown(f"**App Version:** {health.get('version', 'N/A')}")
        st.markdown(f"**Overall Status:** {health.get('status', 'N/A')}")

    with col_b:
        st.markdown("### Recent Conversations")
        if chats:
            for chat in chats[:5]:
                st.markdown(f"💬 {chat['title']} - *{chat['updated_at'][:10]}*")
        else:
            st.info("No conversations yet")

    st.divider()
    st.markdown("### Document Library")
    if docs:
        import pandas as pd
        df = pd.DataFrame([
            {
                "Filename": d["original_filename"],
                "Type": d.get("file_type", "-"),
                "Size (KB)": f"{(d.get('file_size') or 0) / 1024:.1f}",
                "Chunks": d["chunk_count"],
                "Uploaded": d["upload_date"][:10],
            }
            for d in docs
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No documents uploaded")


# Main App

def main():
    if not st.session_state.get("token"):
        show_auth_page()
        return

    page = show_sidebar()

    if page == "Chat":
        show_chat_page()
    elif page == "Documents":
        show_documents_page()
    elif page == "Agent":
        show_agent_page()
    elif page == "Dashboard":
        show_dashboard_page()


if __name__ == "__main__":
    main()
