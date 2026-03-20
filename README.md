# 🧠 ContextBrain

**AI-powered Context Discovery Platform for Enterprise Organizations**

ContextBrain helps developers discover APIs, database schemas, documentation, and institutional knowledge using natural language search. Instead of chasing people across Slack and meetings, developers ask ContextBrain and get instant, context-rich answers — starting with API discovery today, and expanding to databases, docs, and more tomorrow.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.6+-orange)
![Gemini](https://img.shields.io/badge/Gemini-2.0--flash-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## The Problem

In large organizations with hundreds of internal APIs:

- **Discovery is people-dependent** — "Which API checks member eligibility?" requires asking 3 teams across 5 meetings
- **Knowledge is tribal** — API quirks and gotchas live in people's heads, not in docs
- **Onboarding is painful** — New developers spend weeks just learning what APIs exist

## The Solution

```
Developer:  I need to verify if a member's health plan covers behavioral health services.

ContextBrain:   Found 2 relevant APIs:

            1. Benefits Eligibility API (v3.2) — Benefits Platform Team
               POST /v3/benefits/eligibility/check
               ⚠️ "Dental and vision have separate endpoints." — @dev_smith

            2. Prior Authorization API (v2.1) — UM Platform Team
               GET /v2/prior-auth/status/{memberId}
               ⚠️ "Always call eligibility first." — @dev_jones
```

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | FastAPI (Python) | REST API server |
| **Relational DB** | PostgreSQL 17 | APIs, endpoints, annotations, usage logs |
| **Vector Store** | ChromaDB | Semantic search embeddings |
| **LLM** | Google Gemini 2.0 Flash | Conversational discovery, spec enrichment |
| **Embeddings** | Gemini text-embedding-004 | Vector embeddings (768 dimensions) |
| **Frontend** | React + TypeScript | Chat UI, catalog browser, spec uploader |

> **Vertex AI Ready**: The architecture is designed for easy migration to Vertex AI Vector Search and Vertex AI Gemini endpoints when you're ready to move to a fully managed GCP stack.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        ContextBrain                              │
│                                                              │
│  ┌────────────┐  ┌───────────────┐  ┌─────────────────────┐ │
│  │ Ingestion   │  │ Search Engine │  │ Chat UI             │ │
│  │ Pipeline    │─▶│ (ChromaDB +   │─▶│ + Spec Upload       │ │
│  │ (specs in)  │  │  Gemini)      │  │ + Annotations       │ │
│  └────────────┘  └───────────────┘  └─────────────────────┘ │
│                                                              │
│  ┌─────────────────────┐  ┌───────────────────────────────┐ │
│  │ PostgreSQL 17        │  │ ChromaDB                      │ │
│  │ APIs │ Endpoints     │  │ API embeddings                │ │
│  │ Annotations │ Logs   │  │ Endpoint embeddings           │ │
│  └─────────────────────┘  └───────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
         ▲                              ▲
         │                              │
  ┌──────┴──────┐              ┌────────┴────────┐
  │ API Gateway  │              │ Google Gemini    │
  │ (AXWAY, etc) │              │ LLM + Embeddings │
  └─────────────┘              └─────────────────┘
```

For the full architecture and strategic plan, see [docs/architecture.md](docs/architecture.md).

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 17
- A Google API key (for Gemini LLM + embeddings)

### Option A: Docker (Recommended)

```bash
# Clone the repo
git clone https://github.com/yourusername/contextbrain.git
cd contextbrain

# Configure environment
cp .env.example .env
# Edit .env — add your GOOGLE_API_KEY

# Start PostgreSQL + API server
docker compose up -d

# Initialize the database + ChromaDB
docker compose exec api python scripts/init_db.py

# Load sample APIs (optional, for demo)
docker compose exec api python scripts/seed_sample_apis.py

# API docs at http://localhost:8000/docs
```

### Option B: Local Development

```bash
# Clone and install
git clone https://github.com/yourusername/contextbrain.git
cd contextbrain
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env — add GOOGLE_API_KEY and DATABASE_URL

# Initialize database
python scripts/init_db.py

# Load sample APIs (optional)
python scripts/seed_sample_apis.py

# Run the API server
uvicorn src.main:app --reload --port 8000
```

### Verify it's working

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Search for an API
curl "http://localhost:8000/api/v1/search?q=check+member+eligibility"

# Chat with ContextBrain
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Which API checks if a member is eligible for behavioral health?"}'
```

## Project Structure

```
contextbrain/
├── src/
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Settings (Gemini, ChromaDB, PostgreSQL)
│   ├── database.py             # PostgreSQL connection + session
│   ├── models/
│   │   └── api_catalog.py      # SQLAlchemy ORM models
│   ├── schemas/
│   │   └── __init__.py         # Pydantic request/response schemas
│   ├── services/
│   │   ├── embedding.py        # Gemini text-embedding-004 integration
│   │   ├── vectorstore.py      # ChromaDB collection management
│   │   ├── ingestion.py        # Spec parsing + Gemini enrichment + storage
│   │   ├── search.py           # Hybrid search (ChromaDB vectors + SQL)
│   │   └── chat.py             # Conversational discovery (Gemini LLM)
│   ├── routers/
│   │   ├── ingest.py           # POST /ingest, POST /ingest/upload
│   │   ├── search.py           # GET /search, GET /apis, GET /apis/{id}
│   │   ├── chat.py             # POST /chat
│   │   └── annotations.py      # CRUD for developer annotations
│   └── utils/
│       └── openapi_parser.py   # OpenAPI 3.x / Swagger 2.x parser
├── docs/
│   └── architecture.md         # Full strategic plan
├── scripts/
│   ├── init_db.py              # Database + ChromaDB initialization
│   └── seed_sample_apis.py     # Load demo data
├── sample_specs/               # Example healthcare OpenAPI specs
├── frontend/
│   └── App.jsx                 # React chat UI with spec upload
├── tests/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Data Architecture

ContextBrain uses a **dual-store** architecture:

| Store | What it holds | Why |
|-------|--------------|-----|
| **PostgreSQL** | API metadata, endpoints, annotations, usage logs | Relational queries, joins, filtering, transactional integrity |
| **ChromaDB** | Vector embeddings for APIs and endpoints | Fast semantic similarity search |

When an API spec is ingested:
1. Parsed and stored in PostgreSQL (relational data)
2. Enriched with Gemini (business descriptions)
3. Embedded with `text-embedding-004` and stored in ChromaDB (vectors)

When a developer searches:
1. Query embedded with Gemini (`retrieval_query` task type)
2. ChromaDB returns top-K similar APIs and endpoints by cosine similarity
3. Full details fetched from PostgreSQL (endpoints, annotations, ownership)
4. Results merged, ranked, and returned

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/ingest` | Ingest an OpenAPI spec (JSON body) |
| `POST` | `/api/v1/ingest/upload` | Ingest from file upload (JSON/YAML) |
| `GET` | `/api/v1/search?q=...` | Semantic search across all APIs |
| `POST` | `/api/v1/chat` | Conversational API discovery |
| `GET` | `/api/v1/apis` | List all ingested APIs |
| `GET` | `/api/v1/apis/{id}` | Full API details with endpoints + annotations |
| `POST` | `/api/v1/annotations` | Add a developer annotation |
| `GET` | `/api/v1/annotations/{id}` | Get annotations for an API/endpoint |
| `DELETE`| `/api/v1/annotations/{id}` | Delete an annotation |
| `GET` | `/api/v1/health` | Health check with ChromaDB stats |

## Sample APIs (Included for Demo)

The `sample_specs/` directory includes example healthcare API specs:
- **Member Eligibility API** — Check member plan coverage
- **Claims Processing API** — Query claim processing status
- **Provider Network API** — Find in-network providers
- **Prior Authorization API** — Manage prior auth requests

Each comes with realistic developer annotations (gotchas, workarounds, tips).

## Vertex AI Migration Path

The current stack (ChromaDB + Gemini API) is designed to be swapped to a fully managed GCP stack:

| Current | Future (Vertex AI) |
|---------|--------------------|
| ChromaDB (local/self-hosted) | Vertex AI Vector Search (managed) |
| Gemini API (google-generativeai) | Vertex AI Gemini endpoint |
| text-embedding-004 (API) | textembedding-gecko@003 (Vertex) |

The `vectorstore.py` service has a clean interface — swap the implementation without changing any calling code. The `.env.example` includes placeholder Vertex AI config fields.

## Roadmap

- [x] Phase 1: API Discovery Engine (semantic search + chat + annotations)
- [x] Spec upload UI (drag & drop JSON, metadata form, live preview)
- [ ] Phase 2: Code Generation & Tool Factory
- [ ] Phase 3: Database Schema Discovery
- [ ] Phase 4: MCP Server + Multi-Agent Composition
- [ ] Vertex AI Vector Search integration
- [ ] AXWAY gateway auto-sync

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT — see [LICENSE](LICENSE) for details.
