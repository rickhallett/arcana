---
title: "Arcana: Session Report — 2026-04-09"
category: review
status: active
created: 2026-04-09
---

# Arcana: Session Report — 2026-04-09

**Session duration:** ~311k tokens (single continuous session)
**Operator:** Kai Hallett
**Agent:** Chango (Claude Opus 4.6, 1M context)
**Repository:** [rickhallett/arcana](https://github.com/rickhallett/arcana)

---

## Executive Summary

Built a complete multi-agent research analyst pipeline from zero to deployed in a single session. The system ingests documents (PDF, images, web pages), extracts and indexes content via RAG, and answers research questions with cited, fact-checked briefings. Deployed to a live Kubernetes cluster on ryzen32 over Tailscale with seven green pods and zero restarts.

The project serves as a portfolio demonstration for an AI Engineer (Build & Deployment Focus) role at a UK risk/fraud detection firm. Domain-neutral by design — demonstrates first-principles AI engineering applicable to any vertical.

---

## What Was Built

### Architecture: "The Spine"

LangGraph orchestrates a pipeline DAG inside a FastAPI gateway. Four specialised workers run as independent processes (locally) or K8s pods (cluster), communicating via NATS core request/reply. ChromaDB stores vector embeddings, SQLite stores metadata and reports.

```
Gateway (FastAPI + LangGraph Orchestrator + Dashboard)
    │
    ├── arcana.extract ──→ Extractor Worker (GPT-4o Vision + PyMuPDF)
    ├── arcana.embed   ──→ Embedder Worker (OpenAI text-embedding-3-small)
    ├── arcana.analyse ──→ Analyst Worker (Claude Sonnet)
    └── arcana.check   ──→ Checker Worker (GPT-4o Structured Output)
    │
    ├── ChromaDB (vector store)
    ├── SQLite/PostgreSQL (metadata, reports, extracted text)
    └── NATS (message bus)
```

### Multi-Provider LLM Strategy

| Provider | Model | Worker | Rationale |
|---|---|---|---|
| OpenAI | GPT-4o (vision) | Extractor | Strongest document layout understanding |
| OpenAI | text-embedding-3-small | Embedder | Cheap, fast, industry default |
| Anthropic | Claude Sonnet | Analyst | Better nuanced synthesis and long-context |
| OpenAI | GPT-4o | Checker | JSON schema enforcement for claim verification |

### Pipeline Flows

**Ingestion:** Upload PDF → PyMuPDF extract → chunk (500 tokens, 50 overlap) → OpenAI embeddings → ChromaDB index → extracted text persisted to DB

**Query:** Question → ChromaDB similarity search (top-10) → Claude draft briefing with [N] citations → GPT-4o fact-check each claim (supported/unsupported/partial) → confidence score → final report

---

## Metrics

| Metric | Value |
|---|---|
| Commits | 41 |
| Source files | 95 |
| Python source lines | 1,347 |
| Test lines | 1,271 |
| Tests passing | 78 |
| Dependencies | 24 core + dev tooling |
| K8s manifests | 10 |
| Demo documents indexed | 5 (139 pages, 368K chars) |

### Performance (Local, Observed)

| Operation | Duration | Notes |
|---|---|---|
| PDF extraction (28 pages) | 90ms | PyMuPDF, no LLM call |
| Embedding (28 pages) | ~3s | OpenAI API, 281 chunks |
| Full ingestion pipeline | ~4s | Extract + embed end-to-end |
| Full query pipeline | ~15-19s | Retrieve + Claude analysis + GPT-4o fact-check |
| Query confidence | 100% | 7/7 and 9/9 claims supported in test queries |

---

## Session Timeline

### Phase 1: Design (Brainstorming)

- Analysed the job description and identified key demonstration requirements
- Explored three architectural approaches: monolithic graph, microservice fleet, hybrid spine
- Selected **Approach C: "The Spine"** — LangGraph orchestrator + distributed worker pods
- Design decisions validated through structured Q&A:
  - Domain: Research analyst (universally legible)
  - Stack: LangGraph (to tick the JD box) + NATS (for distribution) + multi-provider LLM
  - Visibility: FastAPI dashboard + LangSmith tracing
  - Deployment: Local K8s on Linux box (AWS-adjacent without the cloud bill)
  - Timeline: ~1 month
- Design spec written and committed: `docs/superpowers/specs/2026-04-08-arcana-design.md`
- Codex adversarial review surfaced 3 high-severity gaps:
  1. File handoff under-specified across pod boundaries → added RWX PVC + checksum contract
  2. JetStream reliability deferred → promoted retry/DLQ/idempotency into core architecture
  3. Tracing data policy missing → added environment-gated trace levels with redaction

### Phase 2: Planning

- 23-task implementation plan written with TDD steps and complete code
- Plan saved to: `docs/superpowers/plans/2026-04-08-arcana.md`

### Phase 3: Implementation (Subagent-Driven)

Five phases executed via subagent dispatch:

**Foundation (Tasks 1-7):**
- Project scaffolding with uv, ruff, hatchling
- pydantic-settings config with `ARCANA_` env prefix
- Structured JSON logger with correlation IDs
- Pydantic models for all NATS message contracts and report schemas
- File handoff store with SHA256 checksum verification
- Async SQLite document store (jobs, reports, extracted text)
- ChromaDB vector store wrapper

**Workers (Tasks 8-13):**
- BaseWorker ABC with NATS subscribe, idempotency tracking, health check
- ExtractorWorker: PyMuPDF + GPT-4o vision
- EmbedderWorker: RecursiveCharacterTextSplitter + OpenAI embeddings + ChromaDB
- AnalystWorker: Claude with citation extraction via regex
- CheckerWorker: GPT-4o structured JSON output with markdown fence stripping
- Worker entrypoint with WORKER_TYPE dispatch + staggered startup

**Orchestration (Tasks 14-17):**
- TypedDict state schemas for ingest and query graphs
- NATSDispatcher with exponential backoff retry (3 attempts, base 2s, max 16s) and DLQ
- LangGraph ingestion graph: extract → embed with conditional failure routing
- LangGraph query graph: retrieve → analyse → check → synthesise with graceful degradation

**Gateway (Tasks 18-19):**
- FastAPI application factory with async lifespan
- REST endpoints: health, jobs CRUD, upload, query, text extraction
- Jinja2 + HTMX dashboard: documents view, query view, pipeline view
- Dark theme, no JS build tooling, server-rendered

**Deployment (Tasks 20-23):**
- Docker Compose: NATS + ChromaDB + PostgreSQL for local dev
- Single Dockerfile with uv, gateway + worker entrypoints
- 10 K8s manifests with kustomize: namespace, PVCs, secrets, StatefulSet, deployments
- README with Mermaid architecture diagram, quickstart, design decisions

### Phase 4: Local Smoke Test

- Docker Compose infrastructure started (NATS, ChromaDB, PostgreSQL)
- Gateway + 4 workers started locally
- **Critical bug found and fixed:** JetStream stream intercepting core NATS request/reply
  - Root cause: ARCANA JetStream stream subjects (`arcana.>`) matched the request subjects, causing JetStream to respond with publish acks instead of routing to workers
  - Fix: deleted the JetStream stream, switched workers to core NATS subscribe with queue groups
  - This was a genuine distributed systems debugging session — traced through NATS permissions, DNS resolution, JetStream API calls, and request/reply semantics
- Full ingestion pipeline verified: CRS AI Regulation paper → 281 chunks in 3 seconds
- Full query pipeline verified: "What are the key differences between US federal and state approaches to AI regulation?" → 18.7s, 9/9 claims supported, 100% confidence

### Phase 5: Cluster Deployment (ryzen32)

- SSH over Tailscale to ryzen32 (Arch Linux, k3s v1.34.6)
- Container image built and imported into k3s containerd (316MB)
- ARCANA namespace created with secrets injected via `kubectl create secret` (never written to disk)
- Multiple deployment iterations to resolve:
  - RWX PVC not supported by k3s local-path provisioner → switched to RWO
  - Gateway crash on PostgreSQL URL in aiosqlite → switched to SQLite on pod
  - Cross-namespace DNS: `nats.halo-fleet` doesn't resolve from `arcana` namespace → FQDN fix
  - NATS auth + JetStream API: `$JS.API.>` subjects not matched by `>` wildcard → removed auth for dev cluster, switched to core NATS
  - Worker thundering herd on NATS subscribe → staggered startup + retry with backoff
- **Final state: 7 pods, all Running, 0 restarts, NATS auth restored**

### Phase 6: LangSmith Integration

- LangSmith tracing enabled via environment variables in gateway lifespan and worker entrypoint
- `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` set from Settings
- `trace_level` "metadata" mode hides inputs/outputs for production use

### Phase 7: Error Handling (P2)

- Analyst node handles worker error responses without crashing the graph
- Checker failures degrade gracefully: unchecked draft with empty claims proceeds to synthesis
- Query route catches all exceptions, returns structured error response (never 500)
- Partial results saved when possible (draft without fact-check)

### Phase 8: Stain Inlet (P3)

- Discovered existing `research.py` in Stain with `fetch_papers_from_arcana()` — inlet was already sketched
- Fixed two bugs:
  1. Status check: `"complete"` → `"completed"` (matches Arcana's actual response)
  2. Data source: switched from `report.answer` (query briefing) to `/api/jobs/{id}/text` (raw extracted text)
- Added `extracted_text` table to Arcana's document store
- Added `/api/jobs/{id}/text` endpoint returning raw extracted document text
- Both repos committed: Arcana (text endpoint) + Stain (inlet fix)

### Phase 9: Demo Document Loading (P4)

Five documents ingested and indexed:

| Document | Pages | Characters |
|---|---|---|
| Attention Is All You Need (Vaswani et al.) | 15 | 39,526 |
| CRS: Regulating Artificial Intelligence | 31 | 120,434 |
| Stanford AI Index 2025: Policy & Governance | 44 | 78,589 |
| State of State AI Legislation 2025 | 21 | 60,144 |
| America's AI Action Plan 2025 | 28 | 69,877 |
| **Total** | **139** | **368,570** |

Cross-corpus query verified: "How does the transformer architecture relate to current AI policy proposals?" — analyst correctly identified that the papers don't directly connect (honest answer, not hallucinated correlation).

---

## Bugs Found and Fixed During Deployment

| Bug | Root Cause | Fix | Lesson |
|---|---|---|---|
| `uv sync --dev` doesn't install extras | Dev deps in `[project.optional-dependencies]` not `[dependency-groups]` | Moved to `[dependency-groups]` | uv's `--dev` flag only works with dependency-groups |
| ChromaDB test isolation | `chromadb.Client()` is a singleton, shared state across tests | `EphemeralClient` + UUID-namespaced collections | In-memory ChromaDB needs explicit isolation |
| `.gitignore` swallowing `src/arcana/store/` | Unanchored `store/` pattern | Changed to `/store/` | Anchor gitignore patterns to repo root |
| Starlette 1.0 TemplateResponse | Signature changed from `(name, context)` to `(request, name)` | Updated all template calls | Pin or test against framework major versions |
| JetStream intercepting request/reply | ARCANA stream subjects match worker request subjects | Deleted JetStream stream, use core NATS | JetStream and core NATS request/reply conflict on overlapping subjects |
| Cross-namespace DNS | `nats.halo-fleet` doesn't resolve from `arcana` namespace | Use FQDN: `nats.halo-fleet.svc.cluster.local` | Always use FQDN for cross-namespace K8s services |
| RWX PVC on k3s | local-path provisioner doesn't support ReadWriteMany | Changed to ReadWriteOnce (single-node cluster) | Check storage class capabilities before specifying access modes |
| Gateway using PostgreSQL URL with aiosqlite | Dockerfile doesn't include asyncpg | Used SQLite on gateway pod | Match DB driver to installed dependencies |
| `asyncio` NameError in retry loop | Missing import | Added `import asyncio` | Subagent-generated code needs import verification |
| OpenAI 429 quota exceeded | Wrong API key loaded from zshrc | User provided correct key | Multiple API keys in env — verify the right one is active |
| Worker error responses crash graph nodes | `result["text"]` KeyError when worker returns `{"error": ...}` | Added `"error" in result` guard before accessing fields | Always validate NATS response shape before destructuring |

---

## Architecture Decisions Made Under Fire

1. **Core NATS over JetStream for request/reply.** JetStream's push subscribe creates consumer creation API calls that are fragile under auth and timing. Core NATS request/reply with queue groups is simpler, works with auth, and doesn't conflict with existing streams. JetStream is reserved for event sourcing (fire-and-forget), not synchronous dispatch.

2. **SQLite over PostgreSQL for the gateway.** The demo doesn't need PostgreSQL — SQLite with WAL mode handles the gateway's workload. PostgreSQL manifests are in the repo for the "production considerations" interview moment.

3. **Staggered worker startup.** Four workers connecting to NATS simultaneously on a resource-constrained node causes a thundering herd. Staggering by 3 seconds per worker type eliminates the race.

4. **Graceful degradation on checker failure.** If fact-checking fails (quota, timeout, bad JSON), the pipeline still returns the analyst's draft with empty claims and 0% confidence. Partial results are more useful than 500 errors.

---

## JD Coverage Matrix

| JD Requirement | Evidence |
|---|---|
| Multi-agent pipelines (LLMs, VLMs, OCR) | 4 workers: GPT-4o vision, Claude, OpenAI embeddings |
| End-to-end AI systems (RAG, orchestration, memory) | LangGraph StateGraph + ChromaDB + typed state |
| Deploy, monitor, iterate in cloud | 7-pod K8s cluster, LangSmith tracing, structured JSON logs |
| Scalability, reliability | Independent worker scaling, NATS queue groups, retry + DLQ |
| LangChain/LangGraph familiarity | Central to the architecture |
| Strong Python engineering | 78 tests, ruff-formatted, Pydantic models, async throughout |
| Bias toward practical delivery | Working system deployed to real cluster, not slides |
| Collaborative team player | Clean README, documented decisions, conventional structure |

---

## Files Delivered

```
arcana/
├── pyproject.toml                          # 24 deps, hatchling build
├── Dockerfile                              # Single image, gateway + worker entrypoints
├── docker-compose.yaml                     # Local dev: NATS, ChromaDB, PostgreSQL
├── README.md                               # Mermaid diagram, quickstart, design decisions
├── src/arcana/
│   ├── config.py                           # pydantic-settings, ARCANA_ prefix
│   ├── log.py                              # Structured JSON logger
│   ├── models/{events,reports}.py          # Pydantic contracts
│   ├── store/{database,documents,files,vectors}.py  # Storage layer
│   ├── workers/{base,extractor,embedder,analyst,checker,__main__}.py  # 4 workers
│   ├── orchestrator/{state,nats_dispatch,ingest,query}.py  # LangGraph graphs
│   └── gateway/{app,routes,templates/}.py  # FastAPI + Jinja2 + HTMX
├── tests/                                  # 78 tests
├── k8s/                                    # 10 manifests with kustomize
├── demo-docs/                              # 5 PDFs (8.6MB)
└── docs/
    └── superpowers/
        ├── specs/2026-04-08-arcana-design.md   # Design spec
        └── plans/2026-04-08-arcana.md          # 23-task implementation plan
```

---

## What's Next

1. **Rebuild ryzen32 image** with latest fixes (core NATS, error handling, text endpoint)
2. **LangSmith dashboard walkthrough** — verify traces appear with timing/token data
3. **Stain integration test** — run `stain research update` against the live Arcana instance
4. **Interview prep** — rehearse the 6-minute demo walkthrough from the spec
5. **NATS auth hardening** — proper account-based config with JetStream API permissions for future event sourcing work

---

*Report generated by Chango. 41 commits. 78 tests. 7 green pods. One session.*
