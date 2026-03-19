# 🧠 APIBrain

**AI-powered API Discovery Platform for Enterprise Organizations**

APIBrain sits on top of your existing API gateway and transforms how developers discover, understand, and integrate internal APIs. Instead of chasing people across Slack and meetings to find the right API, developers ask APIBrain in natural language and get instant, context-rich answers.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-blue)
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

APIBrain:   Found 2 relevant APIs:

            1. Benefits Eligibility API (v3.2) — Benefits Platform Team
               POST /v3/benefits/eligibility/check
               Checks plan-level benefit coverage by service category.
               ⚠️ "Dental and vision have separate endpoints." — @dev_smith

            2. Prior Authorization API (v2.1) — UM Platform Team
               GET /v2/prior-auth/status/{memberId}
               ⚠️ "Always call eligibility first." — @dev_jones
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    APIBrain                          │
│                                                     │
│  ┌─────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  Ingestion   │  │  Search  │  │  Chat UI      │  │
│  │  Pipeline    │─▶│  Engine  │─▶│  + Annotations│  │
│  │  (specs in)  │  │ (pgvector│  │  (devs query) │  │
│  └─────────────┘  └──────────┘  └───────────────┘  │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  PostgreSQL + pgvector                       │    │
│  │  APIs │ Endpoints │ Annotations │ Embeddings │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
         ▲
         │
  ┌──────┴──────┐
  │ API Gateway  │  (AXWAY, Kong, Apigee, etc.)
  │ OpenAPI Specs│
  └─────────────┘
```

For the full architecture and strategic plan, see [docs/architecture.md](docs/architecture.md).

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 17 with pgvector extension
- An Anthropic API key (Claude)

### Option A: Docker (Recommended)

```bash
# Clone the repo
git clone https://github.com/yourusername/apibrain.git
cd apibrain

# Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Start everything
docker compose up -d

# Initialize the database
docker compose exec api python scripts/init_db.py

# Load sample APIs (optional, for demo)
docker compose exec api python scripts/seed_sample_apis.py

# Open http://localhost:3000 for the UI
# API docs at http://localhost:8000/docs
```

### Option B: Local Development

```bash
# Clone and install
git clone https://github.com/yourusername/apibrain.git
cd apibrain
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Set up PostgreSQL with pgvector
# (see docs/architecture.md for detailed setup)

# Configure
cp .env.example .env
# Edit .env with your database URL and Anthropic API key

# Initialize database
python scripts/init_db.py

# Load sample APIs (optional)
python scripts/seed_sample_apis.py

# Run the API server
uvicorn src.main:app --reload --port 8000
```

## Project Structure

```
apibrain/
├── src/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Application settings
│   ├── database.py          # Database connection and session management
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── api_catalog.py   # API and endpoint models
│   │   └── annotation.py    # Annotation model
│   ├── schemas/             # Pydantic request/response schemas
│   │   ├── api.py
│   │   ├── search.py
│   │   └── annotation.py
│   ├── services/            # Business logic
│   │   ├── ingestion.py     # OpenAPI spec parser + AI enrichment
│   │   ├── embedding.py     # Vector embedding generation
│   │   ├── search.py        # Semantic + hybrid search
│   │   └── chat.py          # Conversational discovery (Claude)
│   ├── routers/             # API route handlers
│   │   ├── ingest.py
│   │   ├── search.py
│   │   ├── chat.py
│   │   └── annotations.py
│   └── utils/
│       └── openapi_parser.py
├── docs/
│   ├── architecture.md      # Full architecture & strategic plan
│   └── api-reference.md     # API endpoint documentation
├── scripts/
│   ├── init_db.py           # Database initialization
│   └── seed_sample_apis.py  # Load sample data for demo
├── sample_specs/            # Example OpenAPI specs
├── tests/
├── frontend/                # React chat UI (coming soon)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/ingest` | Ingest an OpenAPI spec (JSON/YAML) |
| `POST` | `/api/v1/ingest/bulk` | Ingest multiple specs from a directory |
| `GET` | `/api/v1/search?q=...` | Semantic search across all APIs |
| `POST` | `/api/v1/chat` | Conversational API discovery |
| `GET` | `/api/v1/apis` | List all ingested APIs |
| `GET` | `/api/v1/apis/{id}` | Get API details with endpoints and annotations |
| `POST` | `/api/v1/annotations` | Add an annotation to an API or endpoint |
| `GET` | `/api/v1/annotations/{target_id}` | Get annotations for an API/endpoint |
| `GET` | `/api/v1/health` | Health check |

## How It Works

### 1. Ingest APIs
Upload OpenAPI/Swagger specs. APIBrain parses every endpoint, uses Claude to generate business-friendly descriptions, and creates vector embeddings for semantic search.

### 2. Discover APIs
Ask questions in natural language. APIBrain searches semantically across all indexed APIs and returns the most relevant results with business context, ownership info, and community annotations.

### 3. Annotate & Learn
When developers discover gotchas, workarounds, or tips, they add annotations. These persist and appear automatically in future search results — building institutional knowledge over time.

## Sample APIs (Included for Demo)

The `sample_specs/` directory includes example healthcare API specs:
- **Member Eligibility API** — Check member plan coverage
- **Claims Status API** — Query claim processing status
- **Provider Search API** — Find in-network providers

## Roadmap

- [x] Phase 1: API Discovery Engine (semantic search + chat + annotations)
- [ ] Phase 2: Code Generation & Tool Factory
- [ ] Phase 3: Database Schema Discovery
- [ ] Phase 4: MCP Server + Multi-Agent Composition

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT — see [LICENSE](LICENSE) for details.
