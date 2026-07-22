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

## โครงสร้างไดเรกทอรีและรายละเอียดไฟล์ (Directory & File Structure)

### 📌 โครงสร้างแบบภาพรวม (Directory Tree)

```text
apps/backend-fastapi/
├── alembic/                      # Database Migration scripts (Alembic)
│   ├── versions/                 # ไฟล์ Migration แต่ละเวอร์ชัน (Initial schema ฯลฯ)
│   ├── env.py                    # Script เชื่อมต่อ DB & SQLAlchemy MetaData
│   └── script.py.mako            # Template สร้าง Migration script ใหม่
├── app/                          # แพ็กเกจหลักของแอปพลิเคชัน FastAPI
│   ├── main.py                   # FastAPI Application Factory, Router wiring & Lifespan
│   ├── api/                      # HTTP layer: routers + dependency wiring
│   │   ├── deps.py               # Dependency Injection ที่เดียวจบ (Auth, Repos, LLM, Agents, Services)
│   │   ├── auth.py               # /auth (Google login, callback, /me, logout)
│   │   ├── contracts.py          # /contracts (Upload, Review, Override)
│   │   ├── evaluate.py           # /evaluate (Run evaluation benchmarks)
│   │   ├── health.py             # /health (Health & Readiness check)
│   │   └── playbook.py           # /playbook (Search & Manage playbook rules)
│   ├── core/                     # ระบบพื้นฐาน (Config, DB, Security, Logging, Exceptions)
│   │   ├── config.py             # Settings ชุดเดียวของทั้งระบบ (app + auth + llm + rag)
│   │   ├── db.py                 # SQLAlchemy engine, SessionLocal, Base, get_db
│   │   ├── security.py           # JWT sign/verify + Google OAuth client (Authlib)
│   │   ├── exceptions.py         # Custom Exception Classes & Handlers
│   │   └── logging.py            # Structured Logging (structlog)
│   ├── models/                   # SQLAlchemy ORM Models — ตารางทั้งหมดอยู่ที่นี่
│   │   ├── user.py               # ตาราง users
│   │   ├── audit.py              # ตาราง audit_overrides
│   │   └── playbook.py           # ตาราง playbook_embeddings (pgvector)
│   ├── schemas/                  # Data Transfer Objects (Pydantic Models)
│   │   ├── clause.py             # Clause, Offset & Clause Type schemas
│   │   ├── eval.py               # Evaluation Request, Metrics & Summary schemas
│   │   ├── playbook.py           # Playbook Position & Standard Clause schemas
│   │   ├── report.py             # Review Report & Risk Summary schemas
│   │   ├── taxonomy.py           # Clause Taxonomy & Category schemas
│   │   └── user.py               # UserOut (response ของ /auth/me)
│   ├── parsers/                  # Document Parsers & Normalization
│   │   ├── docx.py               # DOCX Document Parser
│   │   ├── pdf.py                # PDF Document Parser (PyMuPDF)
│   │   ├── normalizer.py         # Text Normalization & Clean up
│   │   └── models.py             # Parsed Document Data Structures
│   ├── llm/                      # LLM Integration & Structured Output
│   │   ├── client.py             # Google Gemini API Client Wrapper & Retries
│   │   └── structured.py         # LLM Structured Output Generator (Pydantic)
│   ├── prompts/                  # Prompt Templates (Jinja2)
│   │   ├── classifier.v1.jinja   # Prompt สำหรับ Clause Classification
│   │   ├── judge.v1.jinja        # Prompt สำหรับ Grounding & Compliance Judge
│   │   └── risk_scorer.v1.jinja  # Prompt สำหรับ Risk Assessment Scoring
│   ├── agents/                   # Multi-Agent Workflow Engine
│   │   ├── base.py               # Base Agent Interface
│   │   ├── segmenter.py          # Document Segmentation Agent
│   │   ├── classifier.py         # Clause Classifier Agent
│   │   ├── matcher.py            # Playbook Rule Matching Agent
│   │   ├── risk_scorer.py        # Risk Assessment & Scoring Agent
│   │   ├── judge.py              # Verification & Grounding Judge Agent
│   │   └── orchestrator.py       # Main Orchestrator Agent (Pipeline Coordinator)
│   ├── rag/                      # Grounded RAG & Retrieval Engine
│   │   ├── embedder.py           # Text Embedding Generation (Gemini Embeddings)
│   │   ├── vector_store.py       # PostgreSQL pgvector Vector Store Wrapper
│   │   ├── retriever.py          # Hybrid Search (Dense pgvector + BM25 Rerank)
│   │   ├── citation.py           # Citation Verification & Text Offset Matching
│   │   └── ingest.py             # Playbook Ingestion & Vector Indexing Pipeline
│   ├── guardrails/               # Safety & Accuracy Guardrails
│   │   ├── grounding.py          # Groundedness Check Engine
│   │   ├── citation_validity.py  # Citation Range & Excerpt Validation
│   │   ├── no_invented_fallback.py # Hallucination & Invented Rule Protection
│   │   └── disclaimer.py         # Legal Disclaimer Generator
│   ├── repositories/             # Data Access Layer (Repositories)
│   │   ├── contract_repo.py      # Contract Data Repo (Redis-backed / In-memory)
│   │   ├── report_repo.py        # Review Report Repo (Redis-backed / In-memory)
│   │   └── audit_repo.py         # Audit Override Logs Repo (PostgreSQL)
│   ├── services/                 # Business Logic Layer
│   │   ├── review_service.py     # Main Contract Review Service
│   │   ├── override_service.py   # Human Override & Re-aggregation Service
│   │   └── eval_service.py       # Evaluation Runner Service
│   └── evaluation/               # Evaluation & Benchmarking System
│       ├── metrics.py            # Precision, Recall, F1, Citation Accuracy Metrics
│       ├── runner.py             # Benchmark Test Runner
│       └── report.py             # Evaluation Report Formatter
├── scripts/                      # Utility Scripts
│   ├── ingest_playbook.py        # Script นำเข้า Playbook YAML เข้าสู่ Vector DB
│   └── run_eval.py               # Script คำสั่งรัน Evaluation Suite
├── data/                         # Data Fixtures & Datasets
│   ├── contracts/                # Sample contract text files (sample-001.txt, sample-002.txt)
│   ├── gold/annotations.jsonl    # Gold annotations ground truth dataset
│   └── playbook/positions.yaml   # Standard legal positions & Playbook rules
└── tests/                        # Test Suites
    ├── unit/                     # Unit tests (Guardrails, Parsers, Agents, Metrics)
    ├── integration/              # Integration tests (Health, Auth, Contracts API)
    └── eval/                     # Evaluation Regression Gate tests
```

### 📑 รายละเอียดหน้าที่ของแต่ละส่วน (File Explanations)

#### 1. Core Application (`app/`)
* **`app/main.py`** — จุดเริ่มต้นของแอปพลิเคชัน FastAPI กำหนด CORS, Middleware, Lifespan hooks และลงทะเบียน API Routers ทั้งหมด
* **`app/core/`**:
  * `config.py`: `Settings` ชุดเดียวของทั้งระบบ (core / auth / llm / rag / feature flags) โหลดผ่าน Pydantic BaseSettings — ฟิลด์ที่ไม่มี default (`DATABASE_URL`, secrets ของ auth) บังคับต้องมี ไม่งั้นแอปไม่ boot
  * `db.py`: ทุกอย่างที่คุยกับ Postgres เริ่มที่นี่ — `engine`, `SessionLocal`, `Base`, `get_db`
  * `security.py`: Sign/Decode JWT + Google OAuth client (Authlib) — ตัว endpoint อยู่ที่ `app/api/auth.py`
  * `exceptions.py`: นิยาม Custom Exception (เช่น `NotFoundError`, `DocumentParseError`) และ Exception Handlers
  * `logging.py`: ตั้งค่า Structured JSON Logging ด้วย `structlog` พร้อม Context Tracking (Trace ID)
* **`app/models/`**: SQLAlchemy ORM Models — ตารางทั้งหมดของระบบประกาศไว้ที่นี่ที่เดียว (`users`, `audit_overrides`, `playbook_embeddings`) การ `import app.models` จึงทำให้ `Base.metadata` ครบ ซึ่งเป็นสิ่งที่ Alembic autogenerate ใช้เทียบกับ DB จริง
* **`app/api/`**: ชั้น HTTP ทั้งหมด — router หนึ่งไฟล์ต่อหนึ่งกลุ่ม endpoint (ไม่มี prefix `/v1` จริง จึงไม่มีโฟลเดอร์ `v1/` หลอกตา)
  * `deps.py`: ที่เดียวที่ประกอบ object graph ทั้งระบบ — `@lru_cache` = singleton ระดับ process (LLM client, retriever, repos, agent pipeline), ฟังก์ชันธรรมดา = ผูกกับ request (DB session, bearer token → `get_current_user`) การ override ตัวใดตัวหนึ่งใน `app.dependency_overrides` จะสลับทั้ง subtree ซึ่งเป็นวิธีที่เทสต์ใช้แทน LLM/Redis/auth
  * `auth.py`: `/auth/google/login`, `/auth/google/callback`, `/auth/me`, `/auth/logout`
  * `contracts.py`: Endpoint หลักสำหรับ `/contracts/review` (อัปโหลดและประเมินสัญญา) และ `/contracts/{id}/override` (แก้ไขผลประเมิน)
  * `playbook.py`: Endpoint ค้นหาข้อกำหนดใน Playbook (`/playbook/search`)
  * `evaluate.py`: Endpoint สำหรับสั่งรัน Evaluation Benchmarks (`/evaluate`)
  * `health.py`: Endpoint สำหรับเช็กความพร้อมและสุขภาพของระบบ (`/health`, `/health/db`)
* **`app/schemas/`**: Pydantic Models สำหรับกำหนด Data Transfer Objects (DTO) และ Request/Response Schemas แยกตามโดเมน (`clause.py`, `playbook.py`, `report.py`, `eval.py`, `taxonomy.py`)
* **`app/parsers/`**:
  * `pdf.py` & `docx.py`: ตัวแกะและสกัดข้อความจากไฟล์ PDF (ใช้ PyMuPDF) และ DOCX (ใช้ python-docx)
  * `normalizer.py`: ทำความสะอาดข้อความ ตัดช่องว่างส่วนเกิน จัดระเบียบบรรทัดใหม่ให้เป็นมาตรฐาน
  * `models.py`: Data structure กลางผลลัพธ์การอ่านเอกสาร (`ParsedDocument`, `ParsedSection`)
* **`app/llm/` & `app/prompts/`**:
  * `client.py`: Wrapper สำหรับสื่อสารกับ Google Gemini API พร้อมระบบ Retry และ Cost/Usage Tracking
  * `structured.py`: ตัวช่วยบังคับ LLM ตอบผลลัพธ์กลับมาเป็น Structured JSON ตาม Pydantic Schema
  * `prompts/*.jinja`: ไฟล์แม่แบบ Prompt (Jinja2) สำหรับ Classifier, Risk Scorer และ Judge
* **`app/agents/`**: สถาปัตยกรรม Multi-Agent ทำงานร่วมกันแบบเป็นขั้นตอน:
  * `segmenter.py`: ตัดแบ่งเอกสารเป็นข้อสัญญาย่อย (Clause Segmentation)
  * `classifier.py`: จำแนกประเภทของ Clause ตาม Taxonomy
  * `matcher.py`: ค้นหาและจับคู่ Clause กับนโยบายกฎหมายใน Playbook ผ่าน RAG
  * `risk_scorer.py`: ประเมินระดับความเสี่ยง (High/Medium/Low) และให้เหตุผลสนับสนุน
  * `judge.py`: ตรวจสอบความถูกต้อง (Verification/Grounding Check)
  * `orchestrator.py`: ตัวคุม Pipeline (Orchestration Engine) จัดลำดับการรัน Agent ทั้งหมด
* **`app/rag/`**:
  * `embedder.py`: แปลงข้อความเป็น Vector Embedding (`gemini-embedding-001`)
  * `vector_store.py`: เชื่อมต่อและค้นหาข้อมูลใน PostgreSQL `pgvector`
  * `retriever.py`: ทำ Hybrid Search (Dense pgvector + BM25 Lexical Rerank)
  * `citation.py`: ตรวจสอบความสอดคล้องของการอ้างอิง Citation กลับไปยังข้อความตั้งต้น
  * `ingest.py`: สคริปต์สกัด Playbook YAML แปลงเป็น Embedding ลง Vector Store
* **`app/guardrails/`**: ระบบ Guardrails ป้องกัน AI มโน (Hallucination) ตรวจสอบว่าคำตอบอ้างอิงจากเนื้อหาจริง (`grounding.py`), ความถูกต้องของ Citation (`citation_validity.py`), ป้องกันการสร้างกฎปลอม (`no_invented_fallback.py`) และแปะคำเตือนทางกฎหมาย (`disclaimer.py`)
* **`app/repositories/`**: Data Access Layer สำหรับจัดการข้อมูลคงสภาพ:
  * `contract_repo.py` & `report_repo.py`: จัดเก็บ Parsed Document และ Review Report ลง Redis (พร้อม native TTL) และมี In-memory fallback สำหรับการทดสอบ
  * `audit_repo.py`: บันทึก Audit Log การ Override แก้ไขผลการประเมินลง PostgreSQL
* **`app/services/`**: Business Logic Layer สำหรับประมวลผลระบบ:
  * `review_service.py`: ดำเนินการรีวิวสัญญาแบบ end-to-end — รวมถึงการบังคับ retention (ลบ contract ดิบทันทีหลังได้ report และ sweep report เก่าของ session นั้นตาม TTL)
  * `override_service.py`: จัดการการปรับแก้ไขผลวิเคราะห์โดยมนุษย์ (Human Override)
  * `eval_service.py`: ประมวลผลระบบทดสอบวัดผล AI
* **`app/evaluation/`**: ระบบประเมินประสิทธิภาพ AI ประกอบด้วย `metrics.py` (คำนวณ Precision/Recall/F1/Citation Accuracy), `runner.py` (ตัวรัน Benchmark — รับ orchestrator เข้ามาเป็นพารามิเตอร์ ไม่ไปดึงเองจาก `deps`) และ `report.py` (สรุปรายงาน)

#### 2. Authentication (`app/core/security.py` + `app/api/auth.py`)
* `app/core/config.py`: JWT Secret Key, Algorithm, Expiry และ OAuth Client settings (รวมอยู่ใน `Settings` ชุดเดียวกับ config ที่เหลือ)
* `app/core/security.py`: Sign & Decode JWT + Google OAuth2 Authorization Flow (Authlib integration)
* `app/api/auth.py`: API Endpoints สำหรับ Login (`/auth/google/login`), OAuth Callback, Get Current User (`/auth/me`), Logout
* `app/api/deps.py` → `get_current_user`: dependency ที่แปลง bearer token เป็น `User` (หรือโยน `401`)
* `app/schemas/user.py` / `app/models/user.py`: Pydantic response schema และ SQLAlchemy ORM Model ของตาราง `users`

#### 3. Database Migration (`alembic/`)
* `alembic/env.py`: สคริปต์การตั้งค่า Alembic migration โดยอ่าน `DATABASE_URL` จาก `app.core.config` และ `Base.metadata`
* `alembic/versions/*.py`: ไฟล์ Migration สคริปต์ (ประกอบด้วย Initial Schema สำหรับตาราง `users`, `playbook_embeddings`, `audit_overrides` และ extension `vector`)

#### 4. Scripts & Datasets (`scripts/` & `data/`)
* `scripts/ingest_playbook.py`: สคริปต์สำหรับอ่าน `positions.yaml` แล้วฝัง Embedding ลง PostgreSQL Vector DB
* `scripts/run_eval.py`: สคริปต์สำหรับสั่งรัน Benchmark วัดผลระบบ AI ผ่าน CLI
* `data/playbook/positions.yaml`: ไฟล์กำหนดกฎมาตรฐาน นโยบายทางกฎหมาย และคำแนะนำการปรับแก้สัญญา
* `data/gold/annotations.jsonl`: ชุดข้อมูล Ground Truth สำหรับวัดผลความแม่นยำของ AI


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
  (`app/repositories/contract_repo.py`, `report_repo.py`) แทนที่ dict ในหน่วยความจำต่อ process
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
