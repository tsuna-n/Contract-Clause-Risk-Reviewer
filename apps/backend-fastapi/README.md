# Contract Clause Risk Reviewer — Backend (FastAPI)

Backend สำหรับระบบ **วิเคราะห์ความเสี่ยงของข้อสัญญา (clause) ด้วย AI** โดยใช้ grounded RAG:
รับไฟล์สัญญา → แยกเป็น clause → จำแนกประเภท → เทียบกับ playbook ของบริษัท → ให้คะแนนความเสี่ยง →
ตรวจทานด้วย LLM judge แล้วสรุปเป็นรายงานพร้อม citation

> ✅ **สถานะปัจจุบัน: Core review pipeline ทำงานได้จริงแล้ว (end-to-end)** — ทดสอบกับ Gemini API
> + Postgres/pgvector จริงแล้ว: upload → parse → segment → classify → match(RAG) → risk score →
> grounding judge → report พร้อม citation ที่ verify แล้วว่าอ้างอิงตรงกับ playbook จริง
> ส่วนที่เหลือ (ดูหัวข้อ "ยังไม่ได้ทำ" ด้านล่าง) หลัก ๆ คือ Alembic migrations, frontend upload UI,
> และการทดสอบ Google OAuth ผ่าน browser จริง

---

## Tech stack

| ด้าน | เทคโนโลยี |
|------|-----------|
| Web framework | FastAPI + Uvicorn |
| Database | PostgreSQL (`pgvector/pgvector:pg16`) + SQLAlchemy 2.0 (psycopg 3) |
| Cache / queue | Redis 7 (ยกใน infra แล้ว, ยังไม่ได้ใช้งานในโค้ด — ดูหัวข้อ "ยังไม่ได้ทำ") |
| LLM | Google GenAI / Gemini (`gemini-3.5-flash` ค่า default, ตั้งผ่าน `LLM_MODEL`) |
| Embeddings | Gemini (`gemini-embedding-001`, 768 มิติ) |
| Retrieval | Hybrid: pgvector cosine (dense) + BM25 rerank (`rank-bm25`) |
| Parsing | PyMuPDF (PDF), python-docx (DOCX) |
| Auth | Google OAuth (Authlib) + JWT (python-jose) |
| Config | pydantic-settings (`.env`) |
| Observability | structlog (JSON logs + trace id ผ่าน stdlib `logging`) |
| Dev | pytest, ruff |

---

## โครงสร้างไดเรกทอรี

```
apps/backend-fastapi/
├── app/                      # แพ็กเกจหลัก (entrypoint: app.main:app)
│   ├── main.py               # FastAPI app factory + lifespan + router wiring
│   ├── api/
│   │   ├── deps.py           # DI: DB session, LLM client, embedder, vector store,
│   │   │                       retriever, orchestrator, judge, services (ทั้งหมด wired แล้ว)
│   │   └── v1/                contracts, playbook, evaluate, health
│   ├── core/                 # config, logging, exceptions, retention (ครบ)
│   ├── schemas/               Pydantic models: clause, report, taxonomy, playbook, eval
│   ├── parsers/               PDF/DOCX → ParsedDocument + normalizer (ครบ)
│   ├── llm/                   LLM client wrapper (Gemini) + structured output (ครบ)
│   ├── rag/                   embedder, retriever, vector_store (pgvector), ingest, citation (ครบ)
│   ├── agents/                segmenter → classifier → matcher → risk_scorer → judge → orchestrator (ครบ)
│   ├── services/               review_service, override_service, eval_service (ครบ)
│   ├── repositories/           contract_repo, report_repo (in-memory), audit_repo (Postgres, ครบ)
│   ├── evaluation/             runner, metrics, report (eval harness, ครบ)
│   ├── guardrails/             grounding, citation_validity, disclaimer, no_invented_fallback (ครบ)
│   └── prompts/                classifier/judge/risk_scorer .jinja templates + loader (`__init__.py`)
├── auth/                      Google OAuth + JWT (config, jwt, oauth, router, schemas)
├── models/                    SQLAlchemy ORM models (User)
├── scripts/                   ingest_playbook.py, run_eval.py (ครบ, ใช้งานได้จริง)
├── data/                      fixtures: taxonomy, playbook positions, gold annotations + contracts/*.txt
└── tests/                     unit (30 tests), integration, eval (regression gate skip ไว้ — ต้องมี live LLM)
```

### Review pipeline

```
upload → parse (PDF/DOCX) → segment → classify → match(playbook/RAG) → risk_scorer → judge → report
```
(ดู `app/agents/orchestrator.py`: `segment → classify → match → score → judge`, มี retry 1 ครั้งถ้า
judge บอกว่า ungrounded, และ isolate failure ต่อ clause — clause ที่ error ไม่ทำให้ report ทั้งใบพัง)

---

## ✅ สิ่งที่ทำไปแล้ว (ทำงานได้จริง — ทดสอบกับ Gemini API + Postgres จริงแล้ว)

- **Core pipeline ทั้งเส้น** — ทดสอบ live: อัปโหลด `.docx` 2 clause (limitation of liability +
  termination) → ได้ report ที่ classify/match/score ถูกต้อง, citation อ้างอิง playbook position
  จริง, `verified=True` (ผ่าน grounding judge)
- **RAG แบบ hybrid** — dense (pgvector cosine) + BM25 rerank, ทดสอบว่า retrieve ตรง clause type จริง
- **LLM client (Gemini)** — retry ผ่าน SDK, cost tracking (`Usage`), structured output ผ่าน
  `response_schema` + fallback validate ด้วย pydantic
- **Guardrails wiring** — judge เช็ค citation validity + excerpt grounding + no-invented-fallback
  แบบ deterministic ก่อน แล้วค่อยถาม LLM เพิ่มสำหรับเช็ค rationale ที่ overreach
- **Override + audit log** — override เปลี่ยน risk level, re-aggregate summary, เขียน audit log ลง
  Postgres (permanent, ไม่มี TTL) — ทดสอบกับ DB จริงแล้ว
- **Data retention** — contract ดิบถูกลบทันทีหลัง orchestrator สร้าง report เสร็จ; report ถูก sweep
  ตาม TTL (`RETENTION_TTL_SECONDS`) ต่อ session ตอนมี upload ใหม่จาก session เดิม
- **Evaluation harness** — `run_eval` รันทั้ง pipeline จริงต่อ gold contract, คำนวณ
  segmentation F1 / classification accuracy / risk accuracy / citation validity;
  `data/contracts/sample-00{1,2}.txt` สร้างให้ตรงกับ offset ใน `data/gold/annotations.jsonl` แล้ว
- **App factory + entrypoint** `app.main:app` — boot ได้, CORS + `SessionMiddleware` (สำหรับ OAuth),
  DomainError → JSON response ผ่าน `register_exception_handlers`
- **Health endpoints** — `GET /`, `GET /health`, `GET /health/db`
- **DB layer** — SQLAlchemy engine/session/`Base`, สร้าง extension `vector` + ตารางทั้งหมดตอน startup
  (non-fatal ถ้า DB ล่ม)
- **Auth (Google OAuth + JWT)** — routes ครบ, ทดสอบแล้ว: JWT ถูก → คืน user จริง, token ปลอม → `401`;
  `/contracts/*` ทุก endpoint ต้อง auth แล้ว (session_id = user id, actor = user email)
- **Data fixtures** — taxonomy (12 clause types), playbook positions (3 ตัวอย่าง, ingest แล้ว),
  gold annotations + contract text ที่จับคู่กัน
- **Tests** — 30 unit/integration tests ผ่านหมด (`pytest tests/`)

---

## ❌ สิ่งที่ยังไม่ได้ทำ

- **Database migrations** — ยังใช้ `Base.metadata.create_all` ตอน startup; ยังไม่มี Alembic
  (ใช้ได้กับ MVP แต่ไม่เหมาะกับ schema change ใน production)
- **Redis** — ยกใน `docker-compose` แล้วแต่โค้ดยังไม่ได้ใช้งานจริง (contract/report repo เป็น
  in-memory ต่อ process — พอสำหรับรันเดี่ยว แต่ไม่ scale ข้าม process/replica)
- **Google OAuth end-to-end** — โค้ดต่อสายไว้ครบแล้ว แต่ต้องทดสอบผ่าน browser จริงกับ Google
  credentials จริง (ยังไม่ได้ทำในรอบนี้)
- **Frontend**: หน้าอัปโหลดสัญญา, dashboard/reports, risk report view — ยังเป็น stub ฝั่ง `apps/web`
- **Eval regression gate** (`tests/eval/test_regression.py`) — ยัง skip ไว้เพราะต้องเรียก LLM จริง
  (มี cost + ต้องมี quota); รันเองได้ผ่าน `python -m scripts.run_eval`
- **Integration tests สำหรับ `/contracts/review` และ `/contracts/{id}/override`** — ยังไม่มี (ต้อง
  mock auth + DB + LLM ซึ่งใช้เวลาตั้ง fixture มากกว่าที่ทำในรอบนี้); ปัจจุบัน verify ผ่านการรัน
  live end-to-end ด้วยมือแทน

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

### 3) ติดตั้ง dependencies + รัน
```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```
เปิด API docs ที่ http://localhost:8000/docs

> **หมายเหตุ:** entrypoint คือ `app.main:app` เท่านั้น (ตรงกับ `infrastructure/docker-compose.yml`)

### 4) ingest playbook เข้า vector store (ต้องทำก่อน `/contracts/review` จะ match อะไรได้)
```bash
python -m scripts.ingest_playbook   # data/playbook/positions.yaml -> pgvector
```

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
| `data/taxonomy/clause_types.yaml` | ประเภท clause 12 แบบ (sync กับ `app/schemas/taxonomy.py`) |
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
| GET | `/auth/google/login` | ⚠️ ต้องมี Google credentials จริง |
| GET | `/auth/google/callback` | ⚠️ ต้องมี Google credentials จริง |
| GET | `/auth/me` | ✅ |
| POST | `/auth/logout` | ✅ |
| POST | `/contracts/review` | ✅ ต้อง auth (Bearer JWT) |
| POST | `/contracts/{report_id}/override` | ✅ ต้อง auth (Bearer JWT) |
| GET | `/playbook/search` | ✅ |
| POST | `/evaluate` | ✅ |

---

## Roadmap ที่เหลือ

1. **Alembic migrations** แทน `create_all`
2. **Frontend**: upload UI + report view ต่อกับ `/contracts/review`
3. **Google OAuth** — ทดสอบ end-to-end ผ่าน browser จริง
4. **Redis-backed session store** ถ้าต้อง scale ข้าม process/replica
5. **Integration tests** สำหรับ `/contracts/review` และ `/contracts/{id}/override` (mock auth+LLM+DB)
