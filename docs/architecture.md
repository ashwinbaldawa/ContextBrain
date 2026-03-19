# API Intelligence Platform — "APIBrain"

## Strategic Plan & Architecture Blueprint

---

## 1. Executive Summary

Large healthcare organizations maintain hundreds of internal APIs across domains — eligibility, claims, benefits, provider networks, care management, pharmacy, and more. These APIs are registered in a centralized gateway (e.g., AXWAY), but **discovering the right API for a given business need remains a painful, people-dependent process** that can take days or weeks.

**APIBrain** is an AI-powered platform that sits on top of the existing API gateway and transforms how developers discover, understand, integrate, and operationalize APIs — especially for building AI agent capabilities.

### The Three Problems It Solves

| # | Problem Today | APIBrain Solution |
|---|--------------|-------------------|
| 1 | **Discovery is human-dependent** — developers ask around in Slack, meetings, and emails to find the right API | AI-powered semantic search over the entire API catalog with business-context understanding |
| 2 | **Integration is slow** — reading specs, understanding auth, writing wrappers takes days per API | Automated tool/wrapper code generation from specs + accumulated team annotations |
| 3 | **Knowledge is lost** — tribal knowledge about API quirks and best practices lives in people's heads | Persistent annotation system that captures and resurfaces institutional knowledge |

### Value Proposition

- **Weeks → Minutes**: API discovery goes from a multi-day people-chasing exercise to a 2-minute conversation
- **Days → Hours**: Integration code that took 2-3 days per API is generated in under an hour
- **Zero → Compounding**: Tribal knowledge that was previously lost between projects compounds over time
- **Isolated → Shared**: AI tools built by one team become immediately discoverable and reusable by others

---

## 2. Vision & Use Cases

### Primary Personas

**Persona 1: The AI Developer**
Building an AI-powered care coordination assistant. Needs to call 8 different internal APIs (eligibility, benefits, prior auth, provider search, care gaps, pharmacy, claims history, member profile). Today: 3-4 weeks just figuring out which APIs exist and writing integration code. With APIBrain: 2-3 days.

**Persona 2: The Application Developer**
Building a new member portal feature. Needs to integrate with 2-3 APIs but doesn't know which ones, what version, or who to ask. Today: a week of Slack messages and meetings. With APIBrain: an afternoon.

**Persona 3: The Architect / Tech Lead**
Designing a new microservice. Needs to understand what capabilities already exist as APIs to avoid duplication. Today: review meetings with multiple teams. With APIBrain: a comprehensive search in minutes.

**Persona 4: The API Producer**
Owns an API that other teams struggle to use correctly. Gets repeat questions about the same edge cases. Today: answers the same Slack DMs over and over. With APIBrain: documents it once as annotations, never answers the same question again.

### Use Case Scenarios

**Scenario A — "I need to check member eligibility"**
```
Developer: I need to verify if a member's plan covers behavioral health services.
            What API should I use?

APIBrain:  There are 2 relevant APIs:

           1. Benefits Eligibility API (v3.2)
              - Owner: Benefits Platform Team (contact: Jane Doe)
              - Endpoint: POST /v3/benefits/eligibility/check
              - Purpose: Checks plan-level benefit coverage by service category
              - ⚠️ Annotation: "Dental and vision have separate endpoints.
                This only covers medical + behavioral." (added by @dev_smith, 2025-03)

           2. Prior Authorization API (v2.1)
              - Owner: UM Platform Team (contact: John Roe)
              - Endpoint: GET /v2/prior-auth/status/{memberId}
              - Purpose: Checks if a specific procedure requires/has prior auth
              - ⚠️ Annotation: "Always call eligibility first — prior auth
                assumes active coverage." (added by @dev_jones, 2025-01)

           For your use case, you likely need #1 first to confirm coverage,
           then #2 if the specific service needs prior authorization.

           Want me to generate the integration code for either or both?
```

**Scenario B — "Generate the tool wrapper"**
```
Developer: Yes, generate a Python tool wrapper for the Benefits Eligibility API
           that I can use with Google ADK.

APIBrain:  [Generates complete, tested code]:
           - ADK tool definition with proper schema
           - HTTP call logic with AXWAY auth headers
           - Error handling for known edge cases (from annotations)
           - Response parsing and structured output
           - Usage example and test stub
```

**Scenario C — "Something didn't work as expected"**
```
Developer: The eligibility API returns an empty response when the member
           has a dependent-only plan. The spec doesn't mention this.

APIBrain:  Got it. I'll add this as an annotation to the Benefits Eligibility API:
           "Returns empty response for dependent-only plans. Must pass the
           subscriber's member ID with dependent relationship indicator."

           This will appear for all future queries and code generation
           involving this API.
```

---

## 3. System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         APIBrain Platform                           │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐ │
│  │  Ingestion    │  │  Intelligence │  │  Consumption Layer        │ │
│  │  Pipeline     │  │  Layer        │  │                           │ │
│  │              │  │              │  │  ┌─────────────────────┐  │ │
│  │  • AXWAY     │  │  • Semantic  │  │  │  Chat UI            │  │ │
│  │    Sync      │─▶│    Search   │─▶│  │  (Discovery)         │  │ │
│  │  • Confluence │  │  • Context  │  │  ├─────────────────────┤  │ │
│  │    Crawler   │  │    Assembly │  │  │  Code Generator      │  │ │
│  │  • Manual    │  │  • Ranking  │  │  │  (Integration)       │  │ │
│  │    Upload    │  │  • Feedback │  │  ├─────────────────────┤  │ │
│  │              │  │    Loop     │  │  │  Tool Registry       │  │ │
│  └──────────────┘  └──────────────┘  │  │  (Deployment)        │  │ │
│                                       │  ├─────────────────────┤  │ │
│                                       │  │  MCP Server          │  │ │
│                                       │  │  (Distribution)      │  │ │
│                                       │  └─────────────────────┘  │ │
│                                       └───────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Data Layer                                                   │   │
│  │  PostgreSQL + pgvector │ API Specs │ Annotations │ Usage Logs │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
         │                                         │
         ▼                                         ▼
┌─────────────────┐                     ┌────────────────────┐
│  AXWAY Gateway   │                     │  AI Agent Apps     │
│  (Source of Truth │                     │  (domagent-backend, │
│   for API specs)  │                     │   future agents)    │
└─────────────────┘                     └────────────────────┘
```

### Component Breakdown

#### 3.1 Ingestion Pipeline

**Purpose**: Pull API metadata from all sources into a unified, AI-readable format.

**Sources**:
| Source | What It Provides | Sync Frequency |
|--------|-----------------|----------------|
| AXWAY API Gateway | OpenAPI/Swagger specs, endpoint URLs, auth policies | Daily automated sync |
| Confluence/Wiki | Business context docs, integration guides, architecture diagrams | Weekly crawl |
| Manual Upload | Markdown docs, custom annotations, tribal knowledge | On-demand |
| Git Repos | README files, code examples, SDK docs | On push via webhook |

**Ingestion Process**:
1. **Extract** — Pull raw specs and docs from each source
2. **Normalize** — Convert everything to a unified schema (see Data Model)
3. **Enrich** — Use AI to generate business-context summaries from technical specs
4. **Embed** — Generate vector embeddings for semantic search
5. **Store** — Write to PostgreSQL + pgvector

**Key Design Decision**: The enrichment step is critical. Raw OpenAPI specs say things like `POST /v2/elig/chk`. The AI enrichment adds: "This endpoint checks whether a health plan member has active medical coverage for a specific service category. Used by care management and member services applications." This is what makes semantic search actually work.

#### 3.2 Intelligence Layer

**Purpose**: Understand developer queries and find the most relevant APIs.

**Components**:

**Semantic Search Engine**
- Vector similarity search over embedded API descriptions (pgvector, cosine similarity)
- Hybrid search: vector similarity + keyword matching for API names, endpoint paths
- Re-ranking: LLM-based re-ranking of top candidates for complex queries
- Filters: by domain, team, version, status (active/deprecated)

**Context Assembly**
- Once relevant APIs are found, assemble a rich context package:
  - API spec (relevant endpoints only, not the full spec)
  - Business description and use-case guidance
  - All annotations (team knowledge, gotchas, workarounds)
  - Related APIs (commonly used together)
  - Usage stats (how often this API is queried in APIBrain, trending)

**Feedback Loop**
- Track which search results developers actually use (click-through)
- Track annotation additions (indicates gaps in base docs)
- Use signals to improve ranking over time

#### 3.3 Consumption Layer

**Four interfaces, one backend:**

**A. Discovery Chat (Primary Interface)**
- Natural language interface for finding APIs
- Shows relevant APIs with business context, ownership, and annotations
- Suggests related APIs and common integration patterns
- Links to full specs on AXWAY for details

**B. Code Generator**
- Generates integration code from API specs + annotations
- Supports multiple output formats:
  - Raw Python/JS HTTP client code
  - Google ADK tool definitions
  - FastAPI endpoint wrappers
  - Test stubs and mock fixtures
- Includes auth setup, error handling, and known edge cases from annotations

**C. Tool Registry**
- Catalog of pre-generated, reviewed tool wrappers
- Version-tracked and linked to source API versions
- Searchable and composable (find tools, combine them for new agents)
- Review/approval workflow before tools go to production

**D. MCP Server (Future)**
- Exposes the tool registry as an MCP-compatible server
- Any MCP client can discover and invoke registered tools
- Bridges the gap to the broader agent ecosystem

#### 3.4 Data Layer

**Primary Database**: PostgreSQL 17 with pgvector extension

**Core Tables**:

```
api_catalog
├── id (UUID)
├── axway_id (VARCHAR) — reference to AXWAY registry
├── name (VARCHAR)
├── version (VARCHAR)
├── domain (VARCHAR) — e.g., "benefits", "claims", "pharmacy"
├── owner_team (VARCHAR)
├── owner_contact (VARCHAR)
├── status (ENUM) — active, deprecated, sunset
├── business_description (TEXT) — AI-enriched plain-English description
├── openapi_spec (JSONB) — full OpenAPI spec
├── auth_mechanism (VARCHAR) — e.g., "OAuth2", "API Key", "mTLS"
├── base_url_dev / _staging / _prod (VARCHAR)
├── embedding (vector(1536)) — for semantic search
├── last_synced_at (TIMESTAMP)
├── created_at / updated_at (TIMESTAMP)

api_endpoints
├── id (UUID)
├── api_id (FK → api_catalog)
├── method (VARCHAR) — GET, POST, etc.
├── path (VARCHAR) — /v2/benefits/eligibility/check
├── summary (TEXT) — short description
├── business_description (TEXT) — AI-enriched
├── request_schema (JSONB)
├── response_schema (JSONB)
├── embedding (vector(1536))

annotations
├── id (UUID)
├── target_type (ENUM) — api, endpoint
├── target_id (UUID)
├── content (TEXT) — the annotation
├── author (VARCHAR) — who added it
├── category (ENUM) — gotcha, workaround, tip, correction, deprecation
├── verified (BOOLEAN) — confirmed by API owner
├── created_at (TIMESTAMP)

generated_tools
├── id (UUID)
├── api_id (FK → api_catalog)
├── endpoint_ids (UUID[]) — which endpoints are covered
├── framework (ENUM) — adk, langchain, raw_python, raw_js
├── code (TEXT) — generated tool code
├── status (ENUM) — draft, reviewed, approved, deployed
├── reviewed_by (VARCHAR)
├── deployed_at (TIMESTAMP)
├── created_at / updated_at (TIMESTAMP)

usage_logs
├── id (UUID)
├── query (TEXT) — what the developer asked
├── results (JSONB) — which APIs were returned
├── selected_api_id (UUID) — which one they clicked/used
├── action (ENUM) — viewed, generated_code, annotated, feedback
├── user_id (VARCHAR)
├── created_at (TIMESTAMP)
```

---

## 4. Phased Delivery Plan

### Phase 1: API Discovery Engine (Weeks 1-6)
**Goal**: Solve the #1 pain point — finding the right API.

| Week | Deliverable |
|------|-------------|
| 1-2 | **Ingestion pipeline**: Script to pull OpenAPI specs from AXWAY (or manual bulk import). Normalize into `api_catalog` and `api_endpoints` tables. AI-enrichment of business descriptions using Claude. |
| 3 | **Semantic search**: pgvector embeddings for all APIs and endpoints. Hybrid search (vector + keyword). Basic relevance ranking. |
| 4-5 | **Chat interface**: FastAPI backend with `/search` and `/chat` endpoints. React frontend — simple chat UI where developers ask questions in natural language. Display results with API name, description, owner, endpoints, and direct links to AXWAY. |
| 6 | **Annotations v1**: Ability to add/view annotations on any API or endpoint. Annotations surface automatically in search results and chat responses. |

**MVP Success Criteria**:
- Developer can type "I need to check member eligibility" and get the right API(s) in under 5 seconds
- At least 80% of test queries return a relevant result in the top 3
- Annotations are visible to all users immediately after creation

**Tech Stack**:
- Backend: FastAPI (Python 3.11+)
- Database: PostgreSQL 17 + pgvector
- AI: Claude API (claude-sonnet-4) for enrichment, search reranking, and chat
- Frontend: React + TypeScript
- Infra: Cloud Run + Cloud SQL (aligns with existing domagent-backend setup)

### Phase 2: Code Generation & Tool Factory (Weeks 7-12)
**Goal**: Go from "I found the API" to "I have working integration code."

| Week | Deliverable |
|------|-------------|
| 7-8 | **Code generation engine**: Given an API spec + annotations + target framework, generate complete integration code. Support raw Python (httpx/requests), Google ADK tool definitions, and FastAPI wrappers. |
| 9-10 | **Tool registry**: Catalog of generated tools with status tracking (draft → reviewed → approved → deployed). Search and browse interface. Version linking to source API versions. |
| 11-12 | **Review workflow**: Code review interface where generated tools can be reviewed, edited, and approved before going to production. Automated validation (syntax check, schema validation, basic test execution). |

**Success Criteria**:
- Generated code compiles/runs without modification for 70%+ of APIs
- Tool generation time < 30 seconds
- At least 5 reusable tools in the registry by end of phase

### Phase 3: Knowledge Flywheel & Advanced Features (Weeks 13-18)
**Goal**: Make the system self-improving and expand coverage.

| Week | Deliverable |
|------|-------------|
| 13-14 | **Advanced annotations**: Categorized annotations (gotcha, workaround, tip, deprecation). API owner verification workflow. Auto-suggest annotations from common code generation failures. |
| 15-16 | **Database discovery**: Extend the same semantic search to database schemas. Register databases with table/column descriptions. Generate SQL query code or ORM models alongside API tools. |
| 17-18 | **Usage analytics dashboard**: Which APIs are most searched, most annotated, most tool-generated. Identify documentation gaps (many searches, few clicks). Surface to API owners for improvement. |

### Phase 4: Platform Maturity (Weeks 19-24)
**Goal**: Enterprise readiness and ecosystem integration.

| Week | Deliverable |
|------|-------------|
| 19-20 | **MCP server**: Expose the tool registry as an MCP server. Any MCP-compatible client can discover and use approved tools. |
| 21-22 | **AXWAY auto-sync**: Automated bidirectional sync — new APIs in AXWAY auto-appear in APIBrain; annotations from APIBrain can feed back as supplementary docs in AXWAY. Webhook-based real-time sync. |
| 23-24 | **Multi-agent composition**: Interface for composing multiple tools into agent workflows. "I need an agent that does eligibility + prior auth + provider search" → generates a complete multi-tool agent scaffold. |

---

## 5. Architecture Decisions & Rationale

### Why PostgreSQL + pgvector (not a dedicated vector DB)?

- Already in use for domagent-backend (Cloud SQL)
- API catalog is inherently relational (APIs → endpoints → annotations → tools)
- pgvector handles the scale perfectly (hundreds of APIs, not millions of documents)
- Single database to manage, backup, and secure — important for healthcare compliance
- Hybrid queries (vector similarity + filters) are natural in SQL

### Why Claude for AI layer (not OpenAI / Gemini)?

- Already in use for domagent-backend
- Superior at code generation with context (specs + annotations)
- Tool use / function calling is well-suited for the chat interface
- Consistent with org's existing AI investments

### Why build vs. buy?

- **Context Hub (chub)** is open-source and community-driven — great for public APIs but doesn't support internal/proprietary API catalogs behind a firewall
- **No existing product** combines API discovery + code generation + annotation + tool deployment for internal enterprise APIs
- The core components (pgvector search, LLM-based generation) are straightforward to build
- Full control over data residency, auth, and audit — essential for healthcare/HIPAA

### Why code generation over runtime execution?

- **Safety**: Generated code is reviewed by a human before it touches production. In healthcare, a bad runtime API call could access PHI or trigger clinical actions
- **Compliance**: Audit trail is clear — code was generated, reviewed, approved, deployed
- **Reliability**: No runtime dependency on the AI layer. If APIBrain goes down, all existing tools continue to work
- **Performance**: No latency overhead in production. Tools are pre-compiled, not generated on the fly

---

## 6. Security & Compliance Considerations

### Data Classification
- API specs: Internal/Confidential (no PHI)
- Annotations: Internal (no PHI — enforce via policy)
- Generated code: Internal (no PHI — code templates only, no real data)
- Usage logs: Internal (developer queries, no member data)

### Access Control
- RBAC with roles: Viewer (search/browse), Contributor (annotate, generate), Approver (review/deploy tools), Admin (manage catalog, sync config)
- SSO integration with org's identity provider
- API ownership verification for annotation approval

### HIPAA Alignment
- No PHI stored or processed in APIBrain at any point
- All AI calls use Claude API with appropriate data handling agreements
- Audit logging on all actions (search, generate, annotate, deploy)
- Generated code handles PHI safely at runtime (auth tokens, encryption, minimal data exposure) — enforced via code generation templates

### Network Security
- APIBrain deployed behind VPC (same as domagent-backend)
- Access to AXWAY admin API via internal network only
- Claude API calls routed through approved egress

---

## 7. Success Metrics

### Phase 1 (Discovery)
| Metric | Target | How Measured |
|--------|--------|-------------|
| API discovery time | < 5 minutes (from > 1 week today) | User surveys + usage logs |
| Search relevance | Top-3 accuracy > 80% | Manual evaluation on test queries |
| Catalog coverage | > 80% of active APIs indexed | AXWAY sync completeness |
| Adoption | > 30 developers using monthly | Usage logs |

### Phase 2 (Code Generation)
| Metric | Target | How Measured |
|--------|--------|-------------|
| Code correctness | > 70% runs without modification | Developer feedback |
| Integration time | < 2 hours per API (from 2-3 days) | Time tracking |
| Tool reuse rate | > 40% of tools used by 2+ teams | Tool registry logs |

### Phase 3+ (Knowledge Flywheel)
| Metric | Target | How Measured |
|--------|--------|-------------|
| Annotation growth | > 100 annotations in 6 months | Database count |
| Knowledge reuse | > 60% of annotations viewed by others | Usage logs |
| Repeat questions | < 10% of queries are duplicates of past queries | Query similarity analysis |

---

## 8. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| **AXWAY API access** — may not have admin API or export capability | Blocks automated ingestion | Medium | Manual bulk import as fallback; engage AXWAY admin team early |
| **Spec quality** — many APIs may have incomplete or outdated OpenAPI specs | Poor search results and code generation | High | AI enrichment compensates; annotations capture what specs miss; flag low-quality specs to API owners |
| **Adoption** — developers stick with existing habits (asking around) | Low ROI | Medium | Integrate into existing workflows (Slack bot, IDE plugin); executive sponsorship; showcase wins |
| **AI hallucination** — Claude generates plausible but wrong integration code | Broken code, wasted time | Medium | Always include source spec alongside generated code; automated validation; human review requirement |
| **Annotation quality** — incorrect or outdated annotations mislead developers | Wrong code, API misuse | Low | Annotation verification by API owners; expiry dates; reporting mechanism |

---

## 9. Team & Resource Requirements

### Minimum Viable Team
| Role | Effort | Responsibility |
|------|--------|---------------|
| Backend Developer | 1 FTE | FastAPI, ingestion pipeline, search, code generation |
| Frontend Developer | 0.5 FTE | React chat UI, tool registry browse, review interface |
| DevOps / Infra | 0.25 FTE | Cloud Run deployment, Cloud SQL, CI/CD |
| API Governance Lead | 0.25 FTE | Catalog accuracy, API owner coordination, annotation quality |

### Infrastructure Costs (Estimated Monthly)
| Resource | Specification | Est. Cost |
|----------|--------------|-----------|
| Cloud Run | 2 vCPU, 4 GB RAM, always-on | ~$100 |
| Cloud SQL PostgreSQL | 2 vCPU, 8 GB RAM, 50 GB storage, pgvector | ~$200 |
| Claude API | ~500K tokens/day (search + generation) | ~$300 |
| Total | | ~$600/month |

---

## 10. Future Vision — The API Intelligence Ecosystem

Once the foundation is in place, APIBrain evolves from a discovery tool into the **central intelligence layer for all API-driven development** in the organization:

**Near term (6-12 months)**:
- Every new AI agent project starts at APIBrain instead of Slack
- Tool library grows organically as teams contribute
- API quality improves as annotation feedback reaches API owners
- Database schemas become searchable alongside APIs

**Medium term (1-2 years)**:
- APIBrain becomes the default entry point for all integration work, not just AI
- Auto-detection of API changes (spec diffs) triggers re-generation of affected tools
- Cross-API dependency mapping — "if you change this endpoint, these 12 tools break"
- A2A (Agent-to-Agent) capability — agents discover and use other agents' capabilities

**Long term (2+ years)**:
- Self-healing integrations — when an API changes, affected tools auto-update and re-test
- Predictive API recommendations — "teams building care management apps typically also need these 5 APIs"
- Organization-wide API health score — coverage, documentation quality, annotation density, reuse rate

---

*This document is a living plan. It should be revisited and updated as Phase 1 learnings emerge and organizational priorities evolve.*
