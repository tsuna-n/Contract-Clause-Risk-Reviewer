# Contract Clause Risk Reviewer — Backend (FastAPI)

Backend สำหรับระบบ **วิเคราะห์ความเสี่ยงของข้อสัญญา (clause) ด้วย AI** โดยใช้ grounded RAG:
รับไฟล์สัญญา → แยกเป็น clause → จำแนกประเภท → เทียบกับ playbook ของบริษัท → ให้คะแนนความเสี่ยง →
ตรวจทานด้วย LLM judge แล้วสรุปเป็นรายงานพร้อม citation

> ✅ **สถานะปัจจุบัน: Core review pipeline ทำงานได้จริงแล้ว (end-to-end)** — ทดสอบกับ Gemini API
> + Postgres/pgvector จริงแล้ว: upload → parse → segment → classify → match(RAG) → risk score →
> grounding judge → report พร้อม citation ที่ verify แล้วว่าอ้างอิงตรงกับ playbook จริง
> **Alembic migrations** ใช้งานแทน `create_all` แล้ว (ทดสอบ upgrade/downgrade cycle จริงกับ
> Postgres), **auth (`/auth/*`) มี integration test อัตโนมัติแล้ว** ครอบทั้ง JWT flow และ
> Google OAuth callback (mock ที่ authlib boundary — ดูหมายเหตุในหัวข้อ "ยังไม่ได้ทำ"),
> **contract/report repo ย้ายไป Redis แล้ว** (native TTL, scale ข้าม process/replica ได้จริง),
> และ **`/contracts/review` + `/contracts/{id}/override` มี integration test อัตโนมัติแล้ว**
> (mock LLM/orchestrator + auth + DB) ส่วนที่เหลือหลัก ๆ คือ frontend upload UI และการคลิกผ่าน
> Google login จริงในเบราว์เซอร์มือ ๆ อีกครั้งก่อนขึ้น production

---

## Tech stack

| ด้าน | เทคโนโลยี |
|------|-----------|
| Web framework | FastAPI + Uvicorn |
| Database | PostgreSQL (`pgvector/pgvector:pg16`) + SQLAlchemy 2.0 (psycopg 3) |
| Cache / queue | Redis 7 — contract/report repo (session-scoped, native TTL) |
| LLM | Google GenAI / Gemini (`gemini-3.5-flash` ค่า default, ตั้งผ่าน `LLM_MODEL`) |
| Embeddings | Gemini (`gemini-embedding-001`, 768 มิติ) |
| Retrieval | Hybrid: pgvector cosine (dense) + BM25 rerank (`rank-bm25`) |
| Parsing | PyMuPDF (PDF), python-docx (DOCX) |
| Auth | Google OAuth (Authlib) + JWT (python-jose) |
| Config | pydantic-settings (`.env`) |
| Observability | structlog (JSON logs + trace id ผ่าน stdlib `logging`) |
| Dev | pytest, ruff |

---

## โครงสร้างโปรเจกต์ (Project Structure)

จัดแบบเดียวกับ backend Node/Express: **request เข้า `routes/` → เรียก `services/` →
คุยกับ `repositories/` และ DB** ส่วนงาน AI ทั้งหมด (LLM, RAG, agents, guardrails)
ถูกรวมไว้ใน `app/ai/` โฟลเดอร์เดียว ไม่กระจายเป็นโฟลเดอร์ละ 2-3 ไฟล์

### 📊 ตารางสรุป: แต่ละส่วนทำอะไร

| ไฟล์ / โฟลเดอร์ | หน้าที่ | เทียบกับ Node/Express |
|---|---|---|
| `app/main.py` | สร้าง FastAPI app, CORS, middleware, mount router | `server.js` / `app.js` |
| `app/config.py` | อ่าน `.env` เป็น `Settings` ชุดเดียวของทั้งระบบ | `config/index.js` |
| `app/database.py` | engine, `SessionLocal`, `Base`, `get_db` | `config/db.js` |
| `app/models.py` | ตาราง SQLAlchemy ทั้งหมด (`users`, `audit_overrides`, `playbook_embeddings`) | `models/` |
| `app/schemas.py` | Pydantic DTO + enum (`ClauseType`, `RiskLevel`) ที่ใช้ร่วมกันทั้งระบบ | `validators/` (DTO) |
| `app/errors.py` | `DomainError` + handler แปลงเป็น JSON response | `middlewares/errorHandler.js` |
| `app/security.py` | เซ็น/ตรวจ JWT + Google OAuth client (Authlib) | `utils/jwt.js` + passport config |
| `app/logger.py` | structured logging (JSON + trace id) | `utils/logger.js` |
| `app/parsers.py` | อ่าน PDF/DOCX → normalize ข้อความ + offset ต่อหน้า | `utils/` |
| `app/dependencies.py` | ประกอบ object graph ทั้งระบบ (DI) + `get_current_user` | `middlewares/auth.js` + DI container |
| `app/routes/` | 1 ไฟล์ = 1 กลุ่ม endpoint, `__init__.py` รวมเป็น `api_router` | `routes/*.js` + `routes/index.js` |
| `app/services/` | business logic — review / override / evaluation | `services/*.js` |
| `app/repositories/` | ชั้นเข้าถึงข้อมูล — contract + report (Redis), audit (Postgres) | `repositories/*.js` |
| `app/ai/` | เครื่องยนต์ AI ทั้งหมด — LLM, RAG, agents, guardrails, pipeline | (domain เฉพาะของโปรเจกต์นี้) |

> กฎง่าย ๆ: `routes/` ห้ามมี business logic (แค่รับ request → เรียก service → คืน response),
> `services/` ห้ามรู้จัก HTTP, `ai/` ห้ามรู้จักทั้ง HTTP และ DB session ของ request

### 📁 Directory Tree

```text
apps/backend-fastapi/
├── alembic/                    # Database migrations
│   ├── versions/               # ไฟล์ migration แต่ละเวอร์ชัน
│   └── env.py                  # ดึง DATABASE_URL จาก app.config + Base.metadata จาก app.models
├── app/
│   ├── main.py                 # ── entrypoint: create_app() + mount api_router
│   ├── config.py               # ── Settings (.env)
│   ├── database.py             # ── engine / SessionLocal / Base / get_db
│   ├── models.py               # ── ORM: users, audit_overrides, playbook_embeddings
│   ├── schemas.py              # ── Pydantic: taxonomy → playbook → clause → report → eval → user
│   ├── errors.py               # ── DomainError + exception handlers
│   ├── security.py             # ── JWT sign/verify + Google OAuth client
│   ├── logger.py               # ── structlog config
│   ├── parsers.py              # ── PDF/DOCX → ParsedDocument (text + page offsets)
│   ├── dependencies.py         # ── DI ที่เดียวจบ (repos, LLM, retriever, agents, services, auth)
│   ├── routes/                 # HTTP layer
│   │   ├── __init__.py         #    รวมทุก router เป็น api_router ตัวเดียว
│   │   ├── health.py           #    GET /health, /health/db
│   │   ├── auth.py             #    /auth/google/login, /callback, /me, /logout
│   │   ├── contracts.py        #    POST /contracts/review, /contracts/{id}/override
│   │   ├── playbook.py         #    GET /playbook/search
│   │   └── evaluate.py         #    POST /evaluate
│   ├── services/               # Business logic
│   │   ├── review.py           #    upload → parse → pipeline → เก็บ report (+ retention)
│   │   ├── override.py         #    human override + re-aggregate + เขียน audit log
│   │   └── evaluation.py       #    metrics + runner + format report + EvalService
│   ├── repositories/           # Data access
│   │   ├── contract.py         #    ParsedDocument ใน Redis (TTL) + in-memory สำหรับเทสต์
│   │   ├── report.py           #    ContractReviewReport ใน Redis (TTL) + in-memory
│   │   └── audit.py            #    audit log ถาวรใน Postgres
│   └── ai/                     # AI engine — อ่านไล่ตามลำดับ pipeline ได้เลย
│       ├── llm.py              #    LLMClient (Gemini) + structured output + render prompt
│       ├── retrieval.py        #    embedder → pgvector store → hybrid retriever → citation → ingest
│       ├── agents.py           #    Segmenter, Classifier, Matcher, RiskScorer, Judge
│       ├── guardrails.py       #    grounding, citation validity, no-invented-fallback, disclaimer
│       ├── pipeline.py         #    Orchestrator: รัน agent ทั้งเส้น + isolate failure ต่อ clause
│       └── prompts/*.jinja     #    prompt templates (classifier / risk_scorer / judge)
├── scripts/
│   ├── ingest_playbook.py      # positions.yaml → embedding → pgvector
│   └── run_eval.py             # รัน evaluation harness ผ่าน CLI
├── data/
│   ├── contracts/              # ข้อความสัญญาตัวอย่าง (sample-001.txt, sample-002.txt)
│   ├── gold/annotations.jsonl  # ground truth สำหรับวัดผล
│   └── playbook/positions.yaml # จุดยืน/ภาษามาตรฐานของบริษัท
└── tests/
    ├── unit/                   # guardrails, parsers, segmenter, metrics, timeouts
    ├── integration/            # health, auth, contracts API
    └── eval/                   # regression gate (skip ไว้ เพราะต้องเรียก LLM จริง)
```

### 🔍 หมายเหตุที่ควรรู้

* **`app/dependencies.py` คือหัวใจของการ wiring** — `@lru_cache` = singleton ระดับ process
  (LLM client, retriever, repos, agent pipeline), ฟังก์ชันธรรมดา = ผูกกับ request
  (DB session, bearer token → `get_current_user`) การ override ตัวใดตัวหนึ่งใน
  `app.dependency_overrides` จะสลับทั้ง subtree ซึ่งเป็นวิธีที่เทสต์ใช้แทน LLM/Redis/auth
* **`app/models.py` vs `app/schemas.py`** — `models.py` คือตารางจริงใน Postgres (import แล้ว
  `Base.metadata` ครบ ซึ่ง Alembic autogenerate ใช้เทียบกับ DB), `schemas.py` คือรูปร่างข้อมูล
  ที่วิ่งผ่าน HTTP และระหว่าง layer
* **contract/report ไม่ได้อยู่ใน Postgres** — เป็นข้อมูล session-scoped เก็บใน Redis พร้อม TTL
  ส่วนที่อยู่ใน Postgres ถาวรมีแค่ `users`, `audit_overrides` และ `playbook_embeddings`
* **`alembic/env.py`** ดึง `sqlalchemy.url` จาก `Settings().database_url` เอง ไม่ต้องใส่
  connection string ซ้ำใน `alembic.ini`

### Review pipeline

```
upload → parse (PDF/DOCX) → segment → classify → match(playbook/RAG) → risk_scorer → judge → report
```
(ดู `app/ai/pipeline.py`: `segment → classify → match → score → judge`, มี retry 1 ครั้งถ้า
judge บอกว่า ungrounded, และ isolate failure ต่อ clause — clause ที่ error ไม่ทำให้ report ทั้งใบพัง)

---

## ✅ สิ่งที่ทำไปแล้ว (ทำงานได้จริง — ทดสอบกับ Gemini API + Postgres จริงแล้ว)

- **Core pipeline ทั้งเส้น** — ทดสอบ live: อัปโหลด `.docx` 2 clause (limitation of liability +
  termination) → ได้ report ที่ classify/match/score ถูกต้อง, citation อ้างอิง playbook position
  จริง, `verified=True` (ผ่าน grounding judge)
- **RAG แบบ hybrid** — dense (pgvector cosine) + BM25 rerank, ทดสอบว่า retrieve ตรง clause type จริง
- **LLM client (Gemini)** — retry ผ่าน SDK, cost tracking (`Usage`), structured output ผ่าน
  `response_schema` + fallback validate ด้วย pydantic, **timeout ต่อ call** (`LLM_TIMEOUT_SECONDS`,
  ค่า default 120s — ส่งเข้า SDK เป็น ms ผ่าน `HttpOptions.timeout`) กัน call ที่ค้างยึด worker ไว้
  ตลอดกาล; call ที่ timeout จะทำให้ clause นั้นตกเป็น `unknown` + "manual review required"
  ไม่ทำให้ทั้ง report ล่ม
- **Guardrails wiring** — judge เช็ค citation validity + excerpt grounding + no-invented-fallback
  แบบ deterministic ก่อน แล้วค่อยถาม LLM เพิ่มสำหรับเช็ค rationale ที่ overreach
- **Override + audit log** — override เปลี่ยน risk level, re-aggregate summary, เขียน audit log ลง
  Postgres (permanent, ไม่มี TTL) — ทดสอบกับ DB จริงแล้ว
- **Data retention** — contract ดิบถูกลบทันทีหลัง orchestrator สร้าง report เสร็จ; report ถูก sweep
  ตาม TTL (`RETENTION_TTL_SECONDS`, default 8 ชม.) ต่อ session ตอนมี upload ใหม่จาก session เดิม
  — ตั้งไว้ **ต่ำกว่า** `ACCESS_TOKEN_EXPIRE_MINUTES` (12 ชม.) เสมอ เพื่อไม่ให้ report หมดอายุช้ากว่า
  token ที่ใช้ดึงมัน (override ต้องโหลด report ด้วย id ก่อน)
- **Evaluation harness** — `run_eval` รันทั้ง pipeline จริงต่อ gold contract, คำนวณ
  segmentation F1 / classification accuracy / risk accuracy / citation validity;
  `data/contracts/sample-00{1,2}.txt` สร้างให้ตรงกับ offset ใน `data/gold/annotations.jsonl` แล้ว
- **App factory + entrypoint** `app.main:app` — boot ได้, CORS + `SessionMiddleware` (สำหรับ OAuth),
  DomainError → JSON response ผ่าน `register_exception_handlers`
- **Health endpoints** — `GET /`, `GET /health`, `GET /health/db`
- **DB layer** — SQLAlchemy engine/session/`Base`, สร้าง extension `vector` + ตารางทั้งหมดตอน startup
  (non-fatal ถ้า DB ล่ม)
- **Auth (Google OAuth + JWT)** — routes ครบ; automated integration tests แล้ว
  (`tests/integration/test_auth.py`): JWT ถูก → คืน user จริง, token ปลอม/ไม่มี user/ไม่ส่ง token →
  `401`, `/auth/google/login` ยิง redirect ด้วย `redirect_uri` ที่ตั้งค่าไว้ถูกต้อง,
  `/auth/google/callback` สร้าง user ใหม่/อัปเดต user เดิมถูกต้อง + ออก JWT + redirect กลับ
  frontend, error path (`OAuthError`, ไม่มี email) → `400` — ดูหมายเหตุ mock ในหัวข้อ "ยังไม่ได้ทำ"
  ด้านล่าง; `/contracts/*` ทุก endpoint ต้อง auth แล้ว (session_id = user id, actor = user email)
- **Database migrations (Alembic)** — แทน `Base.metadata.create_all` แล้ว; `alembic/env.py` ดึง
  `target_metadata` จาก `Base.metadata` ของแอปเองและ `sqlalchemy.url` จาก `Settings().database_url`
  (ไม่มี connection string ซ้ำอยู่ใน `alembic.ini`) — migration แรก (`initial schema`) ครอบ
  `users` + `playbook_embeddings` (+ `CREATE EXTENSION IF NOT EXISTS vector`) + `audit_overrides`;
  ทดสอบ `upgrade head` → `downgrade base` → `upgrade head` กับ Postgres จริงแล้วว่า schema ตรงกับ
  ที่ `create_all` เคยสร้างไว้เป๊ะ ก่อน stamp DB dev ปัจจุบันเป็น head (ไม่ต้อง re-run DDL เพราะ
  ตารางตรงกันอยู่แล้ว)
- **Data fixtures** — taxonomy (12 clause types), playbook positions (3 ตัวอย่าง, ingest แล้ว),
  gold annotations + contract text ที่จับคู่กัน
- **Redis-backed contract/report repos** — `RedisContractRepository`/`RedisReportRepository`
  (`app/repositories/contract.py`, `report.py`) แทนที่ dict ในหน่วยความจำต่อ process
  แล้ว: serialize เป็น JSON (`ParsedDocument`) / `model_dump_json()` (`ContractReviewReport`),
  ใช้ native Redis TTL (`SET ... EX`) แทนการ sweep เอง — ทดสอบ round-trip จริงกับ
  `contract-risk-redis` container แล้ว (save→get→delete ตรง, TTL ถูกตั้งจริง);
  `ContractRepository`/`ReportRepository` เป็น `Protocol` ตอนนี้ ส่วน
  `InMemoryContractRepository`/`InMemoryReportRepository` ยังอยู่ (ใช้ในเทสต์เพื่อไม่ต้องพึ่ง Redis
  จริง)
- **Integration tests สำหรับ `/contracts/review` และ `/contracts/{id}/override`**
  (`tests/integration/test_contracts.py`) — mock `Orchestrator`/LLM + auth + repos (in-memory) +
  audit DB (SQLite): happy path คืน report ถูกต้อง, ต้อง auth (`401` ถ้าไม่ส่ง token), unsupported
  file type → `422`, override เปลี่ยน risk + re-aggregate `overall_risk` + เขียน audit record
  ถูกต้อง (`old_risk`/`new_risk`/`actor`), report/clause ไม่มีจริง → `404`
- **Tests** — 46 unit/integration tests ผ่านหมด (`pytest tests/`; อีก 1 test เป็น eval regression
  gate ที่ skip ไว้เพราะต้องเรียก LLM จริง)

---

## ❌ สิ่งที่ยังไม่ได้ทำ

- **Frontend**: dashboard/reports (เมนู Sidebar) — ยังเป็น stub ฝั่ง `apps/web`
  (นอก scope ของ backend)
- **ประวัติรายงานย้อนหลัง**: ยังไม่มี `GET /contracts/{report_id}` — report อยู่ใน state ของหน้าเท่านั้น
- **Eval regression gate** (`tests/eval/test_regression.py`) — ยัง skip ไว้เพราะต้องเรียก LLM จริง
  (มี cost + ต้องมี quota); รันเองได้ผ่าน `python -m scripts.run_eval`

---

## การติดตั้งและรัน

### 1) Environment (`.env`)
สร้างไฟล์ `.env` ในโฟลเดอร์นี้ (ตัวอย่างค่า):
```env
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/contract_risk_db
REDIS_URL=redis://localhost:6379/0

# LLM (Google GenAI / Gemini)
GEMINI_API_KEY=...
LLM_MODEL=gemini-3.5-flash
EMBEDDING_MODEL=gemini-embedding-001

# Auth (Google OAuth + JWT)
GOOGLE_OAUTH_API=<google-client-id>
GOOGLE_KEY_SECRET=<google-client-secret>
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
FRONTEND_URL=http://localhost:5173
SESSION_SECRET_KEY=<random-secret>
JWT_SECRET_KEY=<random-secret>
```
> ⚠️ `.env` อยู่ใน `.gitignore` และเคยถูก purge ออกจาก git history — **ห้าม commit เข้า git**
>
> `DATABASE_URL` **ต้องใช้ scheme `postgresql+psycopg://`** (ไม่ใช่ `postgresql://` เฉย ๆ) เพราะ
> โปรเจกต์นี้ติดตั้ง `psycopg` (v3) ไม่ใช่ `psycopg2` — ใช้ scheme เดิมจะได้
> `ModuleNotFoundError: No module named 'psycopg2'`
>
> `LLM_MODEL`/`EMBEDDING_MODEL` ค่า default อาจต้องปรับตาม tier ของ API key — free tier บางบัญชี
> ไม่มี quota ให้ `gemini-2.5-pro`/`text-embedding-004` (deprecated ไปแล้วสำหรับบัญชีใหม่บางส่วน);
> เช็ค model ที่ใช้ได้จริงด้วย `client.models.list()` ถ้าเจอ `404`/`429` ตอนเรียก

### 2) ยก infrastructure (Postgres + Redis)
```bash
docker compose -f ../../infrastructure/docker-compose.yml up -d postgres redis
```

### 3) ติดตั้ง dependencies + migrate DB + รัน
```bash
pip install -e ".[dev]"
alembic upgrade head             # สร้าง extension `vector` + ตาราง users/playbook_embeddings/audit_overrides
uvicorn app.main:app --reload --port 8000
```
เปิด API docs ที่ http://localhost:8000/docs

> **หมายเหตุ:** entrypoint คือ `app.main:app` เท่านั้น (ตรงกับ `infrastructure/docker-compose.yml`)
> ตั้งแต่มี Alembic แล้ว แอปจะ**ไม่**สร้างตารางเองตอน startup อีกต่อไป — ต้องรัน
> `alembic upgrade head` ก่อนเสมอ (ครั้งแรก หรือหลัง pull migration ใหม่)

### 4) ingest playbook เข้า vector store (ต้องทำก่อน `/contracts/review` จะ match อะไรได้)
```bash
python -m scripts.ingest_playbook   # data/playbook/positions.yaml -> pgvector
```

### DB migrations (Alembic)
```bash
alembic upgrade head              # apply ทุก migration ที่ยังไม่ได้ apply
alembic revision --autogenerate -m "describe change"   # สร้าง migration ใหม่หลังแก้ ORM model
alembic downgrade -1              # ถอย migration ล่าสุด 1 ขั้น
```
`alembic/env.py` ดึง `sqlalchemy.url` จาก `Settings().database_url` (อ่านจาก `.env` เดียวกับแอป)
เอง ไม่ต้องตั้งซ้ำใน `alembic.ini`

### รันทั้งหมดด้วย Docker Compose
```bash
docker compose -f ../../infrastructure/docker-compose.yml up -d   # postgres + redis + api
```

### รัน evaluation harness
```bash
python -m scripts.run_eval          # data/gold/annotations.jsonl -> metrics report
```

---

## ข้อมูล (Data fixtures)

| ไฟล์ | คำอธิบาย |
|------|----------|
| `data/playbook/positions.yaml` | จุดยืน/ภาษามาตรฐานของบริษัท (preferred/fallback + `risk_if_absent`) |
| `data/gold/annotations.jsonl` | gold set สำหรับ evaluation harness |
| `data/contracts/sample-00{1,2}.txt` | ข้อความสัญญาตัวอย่าง ตรงกับ offset ใน gold annotations |

---

## Endpoints ทั้งหมด

| Method | Path | สถานะ |
|--------|------|-------|
| GET | `/` | ✅ |
| GET | `/health` | ✅ |
| GET | `/health/db` | ✅ |
| GET | `/auth/google/login` | ✅ automated test + login จริงกับบัญชี Google จริงผ่านแล้ว |
| GET | `/auth/google/callback` | ✅ automated test + login จริงผ่านแล้ว; ทุก error path redirect กลับ `/login?error=<code>` |
| GET | `/auth/me` | ✅ |
| POST | `/auth/logout` | ✅ |
| POST | `/contracts/review` | ✅ ต้อง auth (Bearer JWT); automated test (mocked LLM) + ทดสอบ live กับ Gemini จริงแล้ว |
| POST | `/contracts/{report_id}/override` | ✅ ต้อง auth (Bearer JWT); automated test (mocked LLM) + ทดสอบกับ DB จริงแล้ว |
| GET | `/playbook/search` | ✅ |
| POST | `/evaluate` | ✅ |

---

## Roadmap ที่เหลือ

**Backend ใช้งานได้ครบทุกเส้นทางหลักแล้ว** (รวม Google OAuth ที่ login จริงผ่านแล้ว) เหลือ:

1. **`GET /contracts/{report_id}`** — ให้ frontend deep-link กลับเข้ารายงานเดิมได้ (ตอนนี้ refresh แล้วหาย)
2. **Export report (PDF/CSV)** และ **accept-risk แบบ persist** — ยังไม่มี endpoint
