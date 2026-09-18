# HelpdeskAI — Autonomous Customer Support Platform

> Production-grade RAG helpdesk: create AI agents, ingest your knowledge base, embed a chat widget, and seamlessly hand off to human agents when the AI needs help. Built as a portfolio showcase for full-stack + AI engineering.

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL + pgvector](https://img.shields.io/badge/Postgres-pgvector-336791?style=flat&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Groq](https://img.shields.io/badge/LLM-Groq-F55036?style=flat)](https://groq.com/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)](https://redis.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Live demo:** https://helpdeskai.web.app · **Widget demo:** embed `<script src="/static/widget.js">` on any site · **API docs:** `http://localhost:8000/docs` (dev)

---

## Highlights

| Area | Capability |
|---|---|
| **LLM** | Direct `groq` SDK (`services/groq_client.py:54`) with per-loop `AsyncGroq` pools, timeout/retries, model prefix normalization |
| **Vector store** | **PostgreSQL + pgvector** (`services/vector_store.py:114`) — HNSW `vector_cosine_ops`, namespace isolation, SQLite fallback for tests |
| **Scraping** | `services/web_scraper.py` — extraction with favicon/`og:image`/`theme-color` branding, safe-URL checks, crawl concurrency limits |
| **Auth** | Magic-link OTP (`/auth/otp/request`, `/auth/otp/verify`), Google OAuth callback, password reset — Supabase JWT verification + cache |
| **Human Handoff** | Full state machine (`services/handoff_service.py:204`) + difficulty presets (easy/balanced/hard), LLM tool `transfer_to_human`, visitor email capture, fallback email (Brevo), presence (`services/presence.py`), atomic claim |
| **Team** | Owner-managed human agents, agent assignments, invite tokens, separate human-agent auth (`/human-agent/auth/*`) + dashboard |
| **Widget** | `static/widget.js` + `widget-panel.html/js` — signed deployment tokens, domain allowlist, SSE chat, WS live handoff, telemetry, embed snippet regeneration |

---

## Features

### 1. AI Agents
* Create agents per use-case (`POST /agents/create` — `api/agents/agents.py:102`) with name, model (`groq/llama-3.1-8b-instant` default), avatar upload (2 MB limit), and optional `website_url` for auto-branding.
* Per-agent `AgentConfig`: `retrieval_enabled`, `retrieval_top_k` (capped by `CHAT_RETRIEVAL_TOP_K_CAP`), `system_prompt_locked`, `vector_store_namespace = "{user_id}:{agent_id}"`, `human_handoff_enabled`, `human_handoff_difficulty`.
* Avatar → widget `logo_url` sync, theme color propagation, runtime cache invalidation (`services/chat_runtime.py`).

### 2. Knowledge Base & RAG
* Sources: PDF/TXT upload, pasted text, or URL (`POST /kb/*`, `POST /scrape/*`). File parsing via `services/file_parser.py`, chunking + S3-backed storage (`services/kb_source_storage.py`), quota enforcement (`services/storage_quota.py`).
* Async ingest queue (`services/ingest_queue.py` / `ingest_worker.py`) — spool to `/tmp/helpdeskai-ingest`, Jina embeddings (`JINA_EMBED_MODEL=jina-embeddings-v5-text-small`), `services/vector_store.py:upsert_texts`.
* Retrieval: `aretrieve_context` → `services/vector_store.py:search` (cosine `<=>`, `RAG_CONTEXT_MAX_CHARS=3500`), `build_messages` with `services/ai_prompt_builder.py`, streaming via `astream_answer_with_tools` (Groq).
* Context cache (`RAG_CONTEXT_CACHE_TTL_SECONDS=180`) and concurrency caps (`JINA_EMBED_MAX_CONCURRENCY=4`, `LLM_STREAM_MAX_CONCURRENCY=8`).

### 3. Embeddable Widget
* Per-agent deployment (`models/widget_deployment.py`) — `deployment_id`, `display_name`, `logo_url`, `initial_messages`, `theme`, `primary_color`, `allowed_domains`, `is_enabled`.
* Public APIs (`api/agents/widget_deployment.py`):
  * `GET /public/widget/{deployment_id}/config` — cached (`WIDGET_CONFIG_CACHE_TTL_SECONDS=300`), ETag, domain check
  * `POST /public/widget/{deployment_id}/chat` — SSE, rate-limited (Redis + in-memory fallback), abuse detection, handoff-aware streaming
  * `POST /public/widget/{deployment_id}/telemetry`, `POST /.../conversations/{id}/email`, `GET /.../token`, `WS /public/widget/ws/{conversation_id}`
* Owner APIs: `GET/PATCH /agents/{agent_id}/widget-deployment`, `POST /regenerate`, `POST /token` (signed via `utils/widget_security.py`).
* Frontend embed: `<script src="{base}/static/widget.js?v=2.1.2" data-deployment-id="{id}" defer></script>` — `widget-loader.js` + `widget-panel.{html,js}` handle SSE/WS, visitor tokens, and handoff UI states.

### 4. Human Handoff — State Machine
```
bot ──► collecting_email ──► queued ──► human ──► resolved
 │              │               │          │
 └─► queued ────┘               └─► resolved
```
* Trigger: LLM calls `transfer_to_human` tool (description varies by difficulty — `services/handoff_service.py:358`).
* Difficulty (`HANDOFF_DIFFICULTY_META`):
  * **Easy:** offer after 1 try, generous keyword match.
  * **Balanced (default):** 1–2 tries + 1 clarifying question.
  * **Hard:** 2–3 tries, require visitor to insist twice (server-gated via `should_allow_handoff`).
* Gating: `human_handoff_enabled` must be on **and** at least one `active` HumanAgent assigned to the agent (`_is_handoff_effectively_enabled`). Disabled → auto-recover `queued/collecting_email → bot`.
* Conversation (`models/handoff.py:Conversation`) scoped to `session_id`, WS fan-out via `_ws_registry` + `_human_registry`, `atomic_claim_conversation` (conditional `UPDATE ... WHERE status='queued'`), fallback email via `services/email_provider.py` (Brevo/`sib-api-v3-sdk`, 30-min throttle, presence-aware).

### 5. Team & Human Agents
* Owner: `api/owner_human_agents.py` — invite (`status=invited` + email), list, assign to agents, revoke. `api/owner_team.py` — analytics, conversations.
* Human: `api/human_agent.py` — login (JWT `human_agent` audience, `HUMAN_AGENT_JWT_TTL_HOURS=12`), WS dashboard, `claim` / `resolve` / `message`, presence heartbeat.
* Frontend: `frontend/src/pages/Team.tsx`, `frontend/src/pages/humanAgent/*` (Login, AcceptInvite, Dashboard) — real-time queue, conversation view, claim race handling (409).

### 6. Auth & Users
* Supabase JWT (`utils/jwt.py`, `services/supabase_auth.py` — 120s TTL, 2k LRU), OTP magic link, Google OAuth (`/auth/google/callback`, `/auth/oauth/exchange`), `POST /auth/refresh`, `POST /auth/upgrade/{tier}`.
* Password reset (`api/auth/password_reset.py`), credits/subscription (`schemas/user.py`), storage quota tiers (`FREE_STORAGE_LIMIT_MB=2`, `PAID=50`, `PRO=100`).

### 7. Dashboard & Landing
* `frontend/src/pages/Landing.tsx` — animated hero, channels grid (Slack/WhatsApp/Web/Gmail), feature cards, security section.
* `frontend/src/pages/Dashboard.tsx` — per-agent cards, knowledge base list, recent conversations, message counts.
* `frontend/src/pages/Agents.tsx` — creation with branding preview, model picker, scraping status.
* `frontend/src/components/BrandIcons.tsx` + `Icon3D.tsx` for consistent branding.

### 8. Production Hardening
* Rate limiting: `utils/rate_limit.py` + `services/redis_client.py` (Upstash/Redis, `RATE_LIMIT_REDIS_PREFIX`), widget sliding-window fallback (`FALLBACK_RATE_LIMIT_MAX_KEYS=1000`).
* Caching: Redis JSON for widget config, RAG context, auth; `CachedStaticFiles` (`main.py:204`) with immutable hashed builds.
* Observability: `request_logging_middleware` (`main.py:45`) with `X-Request-ID`, `CONVERSATION` state logs, `widget_chat_latency` (retrieval + TTFT).
* Security: `PublicWidgetCORSMiddleware`, domain allowlist (`_host_allowed`), `widget_security` abuse signatures, `verify_visitor_token`/`verify_widget_token`, `bcrypt` + `pyjwt`, `slowapi` throttling, `GZipMiddleware`.

---

## Architecture

```
                ┌─────────────┐
                │  Frontend   │  React + Vite + Tailwind + motion
                │             │  Landing / Dashboard / Agents / Team / HumanAgent
                └──────┬──────┘
                       │ apiFetch (/auth, /agents, /kb, /owner/*, /human-agent/*)
┌─────────┐      ┌─────▼─────┐      ┌──────────────┐
│ Visitor │◄────►│  FastAPI  │◄────►│  Postgres    │  users / agents / kb / kb_chunks (pgvector)
│ Widget  │ SSE/WS│  main.py  │      │  + pgvector  │  conversations / human_agents / assignments
└─────────┘      │           │      └──────────────┘
                 │           │      ┌──────────────┐
                 │           ├─────►│   Redis      │  rate limit / cache / presence
                 │           │      └──────────────┘
                 │           │      ┌──────────────┐
                 │           ├─────►│  Groq + Jina │  groq/llama-3.1-* + jina-embeddings-v5
                 └───────────┘      └──────────────┘
                       │                    │
                 static/widget.js    ingest_worker (spool → embed → upsert)
                 Brevo email fallback  Supabase auth  S3/KB storage
```

Request flow for a widget message: `visitor → widget-panel.js (SSE)` → `POST /public/widget/{id}/chat` → domain/rate/abuse check → `get_or_create_conversation` → history + `aretrieve_context` (pgvector) → `build_messages` (with `handoff_policy` if enabled) → `astream_answer_with_tools` → tool `transfer_to_human` → `transition_status` + `broadcast_to_conversation`/`broadcast_to_humans_for_agent` + `WS` → fallback email if queued + presence check.

---

## Tech Stack

| Layer | Tech | Notes |
|---|---|---|
| **Backend** | FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.0, Alembic, SlowAPI | Typed schemas, `BackgroundSession` for thread-safe writes |
| **DB** | PostgreSQL + pgvector (`vector(1024)` + HNSW `vector_cosine_ops`) | `alembic/env.py`, migrations `2026_09_*` |
| **Cache / Realtime** | Redis / Upstash Redis | `CACHE_REDIS_PREFIX=helpdeskai:`, pub/sub ready (`ENABLE_PG_NOTIFY`) |
| **LLM / Embed** | Groq SDK (`groq>=0.24`) + Jina AI | Sync `Groq` + per-loop `AsyncGroq`, `JINA_EMBED_MODEL` |
| **Auth** | Supabase JWT + JWT (human agents), bcrypt, pyjwt | OTP magic link + Google OAuth |
| **Storage** | S3-compatible (KB sources), pgvector (chunks) | `kb_source_storage`, `storage_quota` |
| **Email** | Brevo (sib-api-v3-sdk) | `services/email_provider.py`, mock outbox in dev (`/debug/emails`) |
| **Frontend** | React 19, React Router 7, Vite 6, Tailwind 4, motion, lucide-react | `frontend/src/pages/*`, `frontend/src/components/*` |
| **Widget** | Vanilla JS + HTML panel | `static/widget.js`, `widget-loader.js`, `widget-panel.{html,js}` |
| **Tooling** | `uv`, `pyproject.toml` (Python 3.13), `alembic`, `pytest` (sqlite in-memory) | `uv.lock`, `tests/*` |

---

## Quick Start

### Prerequisites
* Python 3.13, `uv` (or `pip`), Node 20+, PostgreSQL 15+ with `pgvector` extension, Redis (or Upstash URL)

### 1. Clone & install
```bash
git clone https://github.com/Khaleelhabeeb/helpdeskAi.git
cd helpdeskAi
uv sync                  # or: pip install -e .
cd frontend && npm install && cd ..
```

### 2. Configure env
```bash
cp .env.widget.example .env  # then edit
# Required:
# DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/helpdeskai
# GROQ_API_KEY=gsk_...
# JINA_API_KEY=jina_...
# SUPABASE_URL=...            SUPABASE_SERVICE_ROLE_KEY=...
# REDIS_URL=redis://localhost:6379/0  (or UPSTASH_REDIS_URL)
# JWT_SECRET=...  WIDGET_SECRET=...  FRONTEND_URL=http://localhost:3000
# BREVO_API_KEY=...  BREVO_SENDER_EMAIL=...  (for human handoff invites/fallback)
```

Key tuning knobs (all optional, see `.env.widget.example` + `services/*`):
`JINA_EMBEDDING_DIMENSION=1024`, `RAG_CONTEXT_MAX_CHARS=3500`, `CHAT_RETRIEVAL_TOP_K_CAP=3`, `RATE_LIMIT_MAX_REQUESTS=30`, `HUMAN_AGENT_JWT_TTL_HOURS=12`, `FREE_STORAGE_LIMIT_MB=2`.

### 3. Migrate DB
```bash
alembic upgrade head
# Creates: kb_chunks (vector), conversations, human_agents, agent_assignments, plus handoff toggle/difficulty columns
```

### 4. Run
```bash
# Backend
uv run uvicorn main:app --reload --port 8000
# Frontend (separate terminal)
cd frontend && npm run dev  # http://localhost:3000
```

Open `http://localhost:3000/login` → create agent → add KB (upload PDF or paste URL) → open **Widget** tab → copy embed script → test via `POST /public/widget/{deployment_id}/chat` or the preview panel.

### Widget embed (any site)
```html
<script src="https://your-api.com/static/widget.js?v=2.1.2"
        data-deployment-id="wd_abc123" defer></script>
```
Configure `allowed_domains` in the widget deployment settings; requests from other origins get `403`.

---

## Human Handoff — How to Demo

1. **Owner:** Dashboard → **Team** → Invite human agent (email) → assign to an agent → enable **Human Handoff** and pick **Difficulty** (Easy/Balanced/Hard) in **Agents → Settings**.
2. **Human:** Accept invite (`/human-agent/accept?token=...`), set password, login at `/human-agent/login`.
3. **Visitor:** Open the widget → send a message → say *"talk to a human"* (or stay vague — behavior changes with difficulty).
4. **Observe:** LLM calls `transfer_to_human` → conversation moves to `queued` (or `collecting_email` if email missing) → owner dashboard + human dashboard get `status_change` via WS → human **Claims** (atomic, 409 if raced) → WS `human` channel → visitor + human chat via `broadcast_to_conversation`.
5. **Fallback:** If no human is online for 30 min and `visitor_email` is known, Brevo sends a queued email (`services/email_provider.py:send_queued_fallback_email`).

---

## Testing

```bash
uv run pytest -q
# Uses sqlite in-memory (see tests/conftest.py) — pgvector operator falls back to unordered hits
# Covers: auth routes, kb limits, storage quota, chat runtime, rate limiting, models catalog
```

---

## Deployment Notes

* **Backend:** Any ASGI host (Fly, Render, Railway). Set `ENV=production` to hide `/docs`. Ensure `pgvector` extension is enabled and `alembic upgrade head` has run.
* **Frontend:** `npm run build` → deploy `dist` (hosted at https://helpdeskai.web.app). Set `FRONTEND_URL` and `VITE_API_URL` accordingly.
* **Widget:** `build_widget.py` hashes `widget-loader.js`/`widget-panel.*` for immutable caching (`main.py:CachedStaticFiles`); raw files get `max-age=60` so handoff fixes propagate fast.
* **Redis:** Provide `REDIS_URL` or `UPSTASH_REDIS_URL` — widget rate limiting and config cache degrade gracefully to in-memory + DB without it.

---

## Roadmap

* [ ] Real Slack/WhatsApp/Email inbound adapters (currently branded-channel placeholders)
* [ ] Multi-instance WS fan-out via `ENABLE_PG_NOTIFY=1` + `LISTEN` (stubbed in `handoff_service.py:pg_notify`)
* [ ] Conversation transcripts export + analytics per difficulty cohort
* [ ] End-to-end Playwright tests for widget handoff

---

## License

MIT — see [LICENSE](LICENSE). Built by [Khalil Habib Shariff](https://github.com/Khaleelhabeeb) . PRs and feedback welcome.
