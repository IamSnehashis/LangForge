# ⚡ LangForge

**Production-Oriented GenAI Framework with Integrated DBMS**

LangForge is a full-stack AI application framework that tightly integrates database management with modern AI pipelines — streaming LLM responses, Retrieval-Augmented Generation (RAG), and multi-step agent orchestration.

---

## 🏗️ Architecture

```
User → Streamlit UI → FastAPI Backend → PostgreSQL/SQLite DBMS
                   ↓                  ↓
              Ollama LLM         FAISS Vector Store
                   ↓
          Streaming Response ← Agent Orchestration
```

### Core Components

| Component | Technology | Role |
|-----------|-----------|------|
| Frontend | Streamlit | Chat UI, document management, dashboard |
| Backend API | FastAPI | REST endpoints, middleware |
| Database | PostgreSQL / SQLite | Users, chats, docs, embeddings, agent logs |
| LLM | Ollama (local) | Privacy-first inference, embeddings |
| Vector Store | FAISS | Semantic search for RAG |
| Auth | JWT + bcrypt | Per-user session isolation |

---

## 🗄️ Database Schema

```
users          chats          messages
─────────      ──────         ────────
user_id (PK)   chat_id (PK)   message_id (PK)
name           user_id (FK)   chat_id (FK)
email          title          role (user/assistant)
hashed_pass    created_at     content
is_active      updated_at     token_count
created_at                    created_at

documents      embeddings         agent_logs
─────────      ──────────         ──────────
document_id    embedding_id (PK)  log_id (PK)
user_id (FK)   document_id (FK)   user_id (FK)
filename       faiss_index_id     session_id
file_path      vector_reference   agent_name
file_size      chunk_text         action
file_type      chunk_index        action_input
chunk_count    created_at         action_output
upload_date                       tool_name
                                   step_number
                                   duration_ms
                                   status
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running

### 1. Clone & Install

```bash
git clone <repo-url>
cd langforge

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Ollama

```bash
# Pull required models
ollama pull llama3.2          # Chat model
ollama pull nomic-embed-text  # Embedding model for RAG

# Start Ollama server (if not already running)
ollama serve
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env if needed (defaults work for local dev with SQLite)
```

### 4. Start Backend

```bash
# From project root
uvicorn backend.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### 5. Start Frontend

```bash
streamlit run frontend/app.py
```

Frontend available at: http://localhost:8501

---

## 🐳 Docker Deployment

```bash
cd docker
docker compose up -d

# Pull Ollama models inside container
docker exec langforge_ollama ollama pull llama3.2
docker exec langforge_ollama ollama pull nomic-embed-text
```

---

## 📡 API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Login, get JWT |
| GET | `/api/v1/auth/me` | Get current user |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat/` | Create chat session |
| GET | `/api/v1/chat/` | List user's chats |
| GET | `/api/v1/chat/{id}` | Get chat + messages |
| DELETE | `/api/v1/chat/{id}` | Delete chat |
| POST | `/api/v1/chat/{id}/messages/stream` | **Streaming SSE response** |
| POST | `/api/v1/chat/{id}/messages` | Non-streaming response |

### Documents & RAG
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents/upload` | Upload & ingest file |
| GET | `/api/v1/documents/` | List documents |
| DELETE | `/api/v1/documents/{id}` | Delete document |
| POST | `/api/v1/documents/query/rag` | RAG vector search |

### Agents
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/agents/run` | Execute ReAct agent |
| GET | `/api/v1/agents/logs` | View execution traces |
| GET | `/api/v1/agents/tools` | List available tools |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check + service status |

---

## 🔧 Features

### ✅ Implemented
- **JWT Authentication** — per-user isolation, bcrypt password hashing
- **Token-level Streaming** — real async SSE streaming via Ollama
- **FAISS RAG** — document ingestion, chunking, embedding, retrieval
- **ReAct Agent** — multi-step reasoning with 4 built-in tools
- **Full DB Persistence** — all chats, messages, docs, agent traces stored
- **Modular Architecture** — clean separation of API, service, DB layers

### 🔧 Built-in Agent Tools
- **calculator** — safe arithmetic expression evaluator
- **string_ops** — string manipulation (upper/lower/reverse/length)
- **current_time** — returns UTC timestamp
- **knowledge_search** — static knowledge base lookup

### 📋 Planned
- Dockerized deployment (see `docker/`)
- Telemetry & monitoring
- Additional agent tools (web search, code execution)
- Multi-model support

---

## 📁 Project Structure

```
langforge/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── api/
│   │   ├── auth.py          # Authentication endpoints
│   │   ├── chat.py          # Chat + streaming endpoints
│   │   ├── documents.py     # Document upload + RAG
│   │   ├── agents.py        # Agent orchestration
│   │   └── health.py        # Health check
│   ├── core/
│   │   ├── config.py        # Settings (pydantic-settings)
│   │   └── security.py      # JWT, password hashing
│   ├── db/
│   │   └── database.py      # SQLAlchemy async engine
│   ├── models/
│   │   └── models.py        # ORM models (all tables)
│   ├── schemas/
│   │   └── schemas.py       # Pydantic request/response schemas
│   └── services/
│       ├── user_service.py  # User CRUD
│       ├── chat_service.py  # Chat/message CRUD
│       ├── llm_service.py   # Ollama integration
│       ├── rag_service.py   # FAISS + document ingestion
│       └── agent_service.py # ReAct agent + tool execution
├── frontend/
│   └── app.py               # Streamlit UI
├── docker/
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   └── Dockerfile.frontend
├── requirements.txt
├── .env.example
└── README.md
```
