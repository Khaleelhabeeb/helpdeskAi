# HelpdeskAI — Autonomous Customer Support Platform

> Production-grade RAG helpdesk: create AI agents, ingest your knowledge base, give agents custom API actions, embed a chat widget or hosted help page, and hand off to humans when needed. Built as a portfolio showcase for full-stack + AI engineering.

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
| **AI Agents** | Create support agents with custom instructions, model choice, and branding |
| **Knowledge Base** | Upload PDFs, paste text, or crawl websites — agents answer from your content |
| **Custom API Actions** | Let agents call your own APIs (e.g. order status lookup) mid-conversation |
| **Answer Improvement** | See questions your agent couldn't answer, teach the right answer once |
| **Widget & Help page** | Embeddable chat bubble plus a hosted `/help` page, with your logo, colors, and domain lock |
| **Human Handoff** | Bot hands off to a human when stuck, with Easy / Balanced / Hard sensitivity |
| **Team & Inbox** | Invite human agents, assign them to agents, chat live with visitors |
| **Auth** | Magic-link login, Google login, password reset |

---

## Features

### 1. AI Agents
* Create one agent per use-case with a name, AI model, avatar, and optional website for auto-branding.
* Try it instantly in the Playground before embedding it anywhere.
* Per-agent settings for knowledge retrieval, system prompt, and human handoff.

### 2. Knowledge Base
* Add PDFs, pasted text, or website URLs. Everything becomes searchable for the agent.
* Files are processed in the background with storage limits per plan.
* Turn retrieval on/off and control how much context the agent uses.

### 3. Embeddable Widget & Help Page
* One embed script per agent with your logo, colors, and welcome messages.
* Or turn on a hosted help page (`/help/your-id`) with custom headline, description, and suggested questions — embed it via iframe.
* Lock it to your domains, disable anytime, and regenerate the snippet when needed.
* Visitors get streaming replies, email capture, and smooth handoff to humans.

### 4. Custom API Actions
* Give agents real abilities: order lookup, booking check, account status — any HTTP endpoint.
* Define method, URL with `{placeholders}`, parameters the agent must collect, and secret headers.
* Test each action with sample values before going live, then enable/disable anytime.
* Works in both the Playground and the live widget — the agent calls the API, reads the result, and answers naturally.

### 5. Improve Answers
* Every bot reply is tagged answered / unanswered. The Improve tab shows totals, unanswered rate, and top repeated questions (7 / 30 / 90 days).
* One click to teach the right answer or dismiss a false positive. Taught answers go live as knowledge and are reused next time.
* Fix answers right from the Inbox transcript with the Improve answer button.

### 6. Human Handoff
```
bot ──► collecting_email ──► queued ──► human ──► resolved
 │              │               │          │
 └─► queued ────┘               └─► resolved
```
* The bot hands off when the visitor asks for a human or it gets stuck.
* Sensitivity presets:
  * **Easy:** offers a human quickly.
  * **Balanced (default):** tries once or twice first.
  * **Hard:** only hands off when the visitor insists.
* Only works when enabled and at least one human is assigned — otherwise the bot carries on.
* If no human is online, the visitor can leave an email for follow-up.

### 7. Team, Inbox & Human Agents
* Invite human agents by email, assign them to agents, revoke access anytime.
* Shared Inbox with all conversations, status filters, and full transcripts.
* Human dashboard with live queue, one-click claim, reply, and resolve.

### 8. Auth & Users
* Magic-link email login, Google login, and password reset.
* Credit / subscription tiers with per-plan storage limits.

### 9. Dashboard
* Overview of agents, knowledge sources, and recent conversations.
* Agent creation with live branding preview and model picker.
* Analytics, billing, guides, and settings in one layout.

### 10. Production Hardening
* Rate limiting, caching, and request logging out of the box.
* Domain allowlisting, signed widget tokens, and abuse detection.
* Graceful fallback when Redis is unavailable.

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
