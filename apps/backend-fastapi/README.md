# Contract Clause Risk Reviewer — Backend (FastAPI)

Backend สำหรับระบบ **วิเคราะห์ความเสี่ยงของข้อสัญญา (clause) ด้วย AI** โดยใช้ grounded RAG:
รับไฟล์สัญญา → แยกเป็น clause → จำแนกประเภท → เทียบกับ playbook ของบริษัท → ให้คะแนนความเสี่ยง →
ตรวจทานด้วย LLM judge แล้วสรุปเป็นรายงานพร้อม citation

> ⚠️ **สถานะปัจจุบัน: SCAFFOLD (โครงสร้าง)** — ระบบพื้นฐาน (app factory, auth, DB, health, infra)
> **ทำงานได้จริงแล้ว** แต่ **ฟีเจอร์หลักของโปรดักต์ (review pipeline) ยังไม่ได้เขียน** — เป็น stub ที่
> `raise NotImplementedError` อยู่ **34 จุด** และมี **`TODO` 37 จุด** กระจายในโมดูลหลัก
> ยัง **ไม่พร้อมใช้งานจริง (production)** สำหรับการรีวิวสัญญา

---

## Tech stack

| ด้าน | เทคโนโลยี |
|------|-----------|
| Web framework | FastAPI + Uvicorn |
| Database | PostgreSQL (`pgvector/pgvector:pg16`) + SQLAlchemy 2.0 (psycopg 3) |
| Cache / queue | Redis 7 |
| LLM | Anthropic (`claude-opus-4-8`) |
| Parsing | PyMuPDF (PDF), python-docx (DOCX) |
| Auth | Google OAuth (Authlib) + JWT (python-jose) |
| Config | pydantic-settings (`.env`) |
| Observability | structlog |
| Dev | pytest, ruff |

---

## โครงสร้างไดเรกทอรี

```
apps/backend-fastapi/
├── app/                      # แพ็กเกจหลัก (entrypoint: app.main:app)
│   ├── main.py               # FastAPI app factory + lifespan + router wiring
│   ├── api/
│   │   ├── deps.py           # DI: DB engine/session, get_vector_store, get_llm_client
│   │   └── v1/               # contracts, playbook, evaluate, health
│   ├── core/                 # config, logging, exceptions, retention
│   ├── schemas/              # Pydantic models: clause, report, taxonomy, playbook, eval
│   ├── parsers/              # PDF/DOCX → ParsedDocument + normalizer
│   ├── llm/                  # LLM client wrapper + structured output
│   ├── rag/                  # embedder, retriever, vector_store, ingest, citation
│   ├── agents/               # segmenter → classifier → matcher → risk_scorer → judge → orchestrator
│   ├── services/             # review_service, override_service, eval_service
│   ├── repositories/         # contract_repo, report_repo, audit_repo
│   ├── evaluation/           # runner, metrics, report (eval harness)
│   ├── guardrails/           # grounding, citation_validity, disclaimer, no_invented_fallback
│   └── prompts/              # classifier/judge/risk_scorer .jinja templates
├── auth/                     # Google OAuth + JWT (config, jwt, oauth, router, schemas)
├── models/                   # SQLAlchemy ORM models (User)
├── scripts/                  # ingest_playbook.py, run_eval.py
├── data/                     # fixtures: taxonomy, playbook positions, gold annotations
└── tests/                    # unit, integration, eval (scaffolding)
```

### Review pipeline (เป้าหมาย)

```
upload → parse (PDF/DOCX) → segment → classify → match(playbook/RAG) → risk_scorer → judge → report
```
(ดู `app/agents/orchestrator.py`: `segment → classify → match → score → judge`)

---

## ✅ สิ่งที่ทำไปแล้ว (ทำงานได้จริง — ผ่านการทดสอบ)

- **App factory + entrypoint** `app.main:app` — boot ได้, CORS + `SessionMiddleware` (สำหรับ OAuth)
- **Health endpoints** — `GET /`, `GET /health`, `GET /health/db` (ต่อ Postgres จริงได้ → `database: connected`)
- **DB layer** (`app/api/deps.py`) — SQLAlchemy engine/session/`Base`, `get_db` dependency
- **สร้างตารางตอน startup** แบบ non-fatal (DB ล่มก็ยัง boot ได้) — ตาราง `users` ถูกสร้างจริง schema ถูกต้อง
- **Auth (Google OAuth + JWT)** — routes ครบ (`/auth/google/login`, `/auth/google/callback`, `/auth/me`, `/auth/logout`);
  ทดสอบแล้ว: JWT ถูกต้อง → คืน user จริงจาก DB, token ปลอม → `401`
- **Pydantic schemas** — โมเดลข้อมูลครบ (`ClauseReview`, `ContractReviewReport`, `RiskLevel`, `RetrievalHit`, eval)
- **Data fixtures** — taxonomy (12 clause types), playbook positions (ตัวอย่าง), gold annotations (`.jsonl`)
- **Prompt templates** — `classifier.v1`, `judge.v1`, `risk_scorer.v1` (jinja)
- **Infrastructure** — `docker-compose` ยก Postgres (pgvector) + Redis ได้จริง
- **Config** — pydantic-settings อ่าน `.env`

---

## ❌ สิ่งที่ต้องทำ / ต้องมี (ยังเป็น stub — `NotImplementedError`)

### API endpoints ที่ยังไม่ทำ
| Endpoint | สถานะ |
|----------|-------|
| `POST /contracts/review` | ❌ `NotImplementedError` (500) |
| `POST /contracts/{id}/override` | ❌ ยังไม่ทำ |
| `GET /playbook/search` | ❌ `NotImplementedError` (500) |
| `POST /evaluate` | ❌ `NotImplementedError` (500) |

### โมดูลที่ต้อง implement
- **Parsers** (`app/parsers/`) — `pdf.py`, `docx.py` แปลงไฟล์ → `ParsedDocument`
- **LLM client** (`app/llm/`) — `client.py`, `structured.py` (เรียก Anthropic + structured output)
- **RAG** (`app/rag/`) — `embedder`, `retriever`, `vector_store` (pgvector), `ingest`, `citation`
- **DI providers** (`app/api/deps.py`) — `get_vector_store()`, `get_llm_client()`
- **Agents** (`app/agents/`) — `base`, `segmenter`, `classifier`, `matcher`, `risk_scorer`, `judge`, `orchestrator`
- **Services** (`app/services/`) — `review_service`, `override_service`, `eval_service`
- **Repositories** (`app/repositories/`) — `contract_repo`, `report_repo`, `audit_repo`
- **Evaluation** (`app/evaluation/`) — `runner`, `metrics`, `report`
- **Guardrails** (`app/guardrails/`) — grounding, citation validity, disclaimer, no-invented-fallback
- **Core** — `retention.py` (session/data TTL), `exceptions.py`
- **Scripts** — `ingest_playbook.py`, `run_eval.py`

### งานระบบที่ยังขาด
- **Google OAuth end-to-end** — โค้ดต่อสายไว้แล้ว แต่ต้องมี Google client id/secret จริง + browser redirect (ยังไม่ได้ทดสอบจริง)
- **Database migrations** — ปัจจุบันใช้ `Base.metadata.create_all` ตอน startup; ยังไม่มี Alembic
- **Tests** — มีโครง `tests/` แต่ยังไม่ได้เขียน; ต้อง `pip install -e ".[dev]"` ก่อน (pytest อยู่ใน dev extras)

---

## การติดตั้งและรัน

### 1) Environment (`.env`)
สร้างไฟล์ `.env` ในโฟลเดอร์นี้ (ตัวอย่างค่า):
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/contract_risk_db
REDIS_URL=redis://localhost:6379/0

# LLM
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-opus-4-8

# Auth (Google OAuth + JWT)
GOOGLE_OAUTH_API=<google-client-id>
GOOGLE_KEY_SECRET=<google-client-secret>
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
FRONTEND_URL=http://localhost:5173
SESSION_SECRET_KEY=<random-secret>
JWT_SECRET_KEY=<random-secret>
```
> ⚠️ `.env` อยู่ใน `.gitignore` และเคยถูก purge ออกจาก git history — **ห้าม commit เข้า git**

### 2) ยก infrastructure (Postgres + Redis)
```bash
docker compose -f ../../infrastructure/docker-compose.yml up -d postgres redis
```

### 3) ติดตั้ง dependencies + รัน
```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```
เปิด API docs ที่ http://localhost:8000/docs

> **หมายเหตุ:** entrypoint คือ `app.main:app` เท่านั้น (ตรงกับ `infrastructure/docker-compose.yml`)

### รันทั้งหมดด้วย Docker Compose
```bash
docker compose -f ../../infrastructure/docker-compose.yml up -d   # postgres + redis + api
```

---

## ข้อมูล (Data fixtures)

| ไฟล์ | คำอธิบาย |
|------|----------|
| `data/taxonomy/clause_types.yaml` | ประเภท clause 12 แบบ (sync กับ `app/schemas/taxonomy.py`) |
| `data/playbook/positions.yaml` | จุดยืน/ภาษามาตรฐานของบริษัท (preferred/fallback + `risk_if_absent`) |
| `data/gold/annotations.jsonl` | gold set สำหรับ evaluation harness |
| `data/contracts/` | ที่วางไฟล์สัญญาสำหรับทดสอบ |

---

## Endpoints ทั้งหมด

| Method | Path | สถานะ |
|--------|------|-------|
| GET | `/` | ✅ |
| GET | `/health` | ✅ |
| GET | `/health/db` | ✅ |
| GET | `/auth/google/login` | ⚠️ ต้องมี Google credentials |
| GET | `/auth/google/callback` | ⚠️ ต้องมี Google credentials |
| GET | `/auth/me` | ✅ |
| POST | `/auth/logout` | ✅ |
| POST | `/contracts/review` | ❌ TODO |
| POST | `/contracts/{report_id}/override` | ❌ TODO |
| GET | `/playbook/search` | ❌ TODO |
| POST | `/evaluate` | ❌ TODO |

---

## Roadmap ที่แนะนำ (ลำดับการ implement)

1. **LLM client** (`app/llm/`) — พื้นฐานที่ agents ทุกตัวต้องใช้
2. **Parsers** (`app/parsers/`) — PDF/DOCX → text
3. **RAG** (`app/rag/`) + `get_vector_store()` — playbook retrieval (`/playbook/search` ใช้งานได้)
4. **Agents + Orchestrator** — segment → classify → match → score → judge
5. **review_service** → เปิดใช้ `POST /contracts/review` (หัวใจของโปรดักต์)
6. **Guardrails** — grounding / citation validity
7. **Evaluation harness** → `POST /evaluate` + `scripts/run_eval.py`
8. **Tests + Alembic migrations**
