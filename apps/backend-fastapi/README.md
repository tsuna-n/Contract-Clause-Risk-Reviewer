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
| LLM | สลับค่ายได้ผ่าน `LLM_PROVIDER`: Gemini (default) / Anthropic Claude / OpenAI-compatible (Z.AI GLM, DeepSeek, vLLM) — ดู [สลับค่าย AI](#สลับค่าย-ai-ผ่าน-env) |
| Embeddings | ตั้งแยกจาก LLM ผ่าน `EMBEDDING_PROVIDER` (default: Gemini `gemini-embedding-001`, 768 มิติ) |
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
| `app/models.py` | ตาราง SQLAlchemy ทั้งหมด (`users`, `audit_overrides`, `playbook_embeddings`, `contract_reports`) | `models/` |
| `app/schemas.py` | Pydantic DTO + enum (`ClauseType`, `RiskLevel`) ที่ใช้ร่วมกันทั้งระบบ | `validators/` (DTO) |
| `app/errors.py` | `DomainError` + handler แปลงเป็น JSON response | `middlewares/errorHandler.js` |
| `app/security.py` | เซ็น/ตรวจ JWT + Google OAuth client (Authlib) | `utils/jwt.js` + passport config |
| `app/logger.py` | structured logging (JSON + trace id) | `utils/logger.js` |
| `app/parsers.py` | อ่าน PDF/DOCX → normalize ข้อความ + offset ต่อหน้า | `utils/` |
| `app/dependencies.py` | ประกอบ object graph ทั้งระบบ (DI) + `get_current_user` | `middlewares/auth.js` + DI container |
| `app/routes/` | 1 ไฟล์ = 1 กลุ่ม endpoint, `__init__.py` รวมเป็น `api_router` | `routes/*.js` + `routes/index.js` |
| `app/services/` | business logic — review / override / evaluation | `services/*.js` |
| `app/repositories/` | ชั้นเข้าถึงข้อมูล — contract (Redis), report (Postgres, สลับเป็น Redis ได้), audit (Postgres) | `repositories/*.js` |
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
│       ├── providers.py        #    adapter รายค่าย (Gemini / Claude / OpenAI-compatible) + Usage
│       ├── llm.py              #    LLMClient (บางมาก — delegate ให้ providers) + render prompt
│       ├── retrieval.py        #    embedder → pgvector store → hybrid retriever → citation → ingest
│       ├── agents.py           #    Segmenter, Classifier, Matcher, RiskScorer, Judge
│       ├── guardrails.py       #    grounding, citation validity, no-invented-fallback, disclaimer
│       ├── pipeline.py         #    Orchestrator: รัน agent ทั้งเส้น + isolate failure ต่อ clause
│       └── prompts/*.jinja     #    prompt templates (classifier / risk_scorer / judge)
├── scripts/
│   ├── ingest_playbook.py      # positions.yaml → embedding → pgvector
│   ├── build_cuad_fixtures.py  # CUAD v1 → data/contracts + data/gold + data/samples
│   ├── run_eval.py             # รัน evaluation harness ผ่าน CLI
│   └── purge_reports.py        # ลบรายงานเก่ากว่า REPORT_RETENTION_DAYS (ต้องตั้ง cron เอง)
├── data/
│   ├── contracts/              # สัญญาจริงจาก CUAD 12 ฉบับ (.txt) — input ของ eval
│   ├── samples/                # 3 ฉบับในนั้นแปลงเป็น .docx ไว้ลองอัปโหลดที่ UI
│   ├── gold/annotations.jsonl  # ground truth สำหรับวัดผล (span + clause_type + risk)
│   └── playbook/positions.yaml # จุดยืน/ภาษามาตรฐานของบริษัท (36 ตำแหน่ง ครบ 12 clause type)
└── tests/
    ├── unit/                   # guardrails, parsers, segmenter, metrics, timeouts, providers/retry, report repo
    ├── integration/            # health, auth, contracts API
    ├── live/                   # ยิง provider จริง — deselect เป็น default (`pytest -m live_llm`)
    └── eval/                   # regression gate บน gold set (live_llm เหมือนกัน)
```

### 🔍 หมายเหตุที่ควรรู้

* **`app/dependencies.py` คือหัวใจของการ wiring** — `@lru_cache` = singleton ระดับ process
  (LLM client, retriever, repos, agent pipeline), ฟังก์ชันธรรมดา = ผูกกับ request
  (DB session, bearer token → `get_current_user`) การ override ตัวใดตัวหนึ่งใน
  `app.dependency_overrides` จะสลับทั้ง subtree ซึ่งเป็นวิธีที่เทสต์ใช้แทน LLM/Redis/auth
* **`app/models.py` vs `app/schemas.py`** — `models.py` คือตารางจริงใน Postgres (import แล้ว
  `Base.metadata` ครบ ซึ่ง Alembic autogenerate ใช้เทียบกับ DB), `schemas.py` คือรูปร่างข้อมูล
  ที่วิ่งผ่าน HTTP และระหว่าง layer
* **ข้อความสัญญาดิบไม่เคยลงตาราง** — เก็บใน Redis ระหว่าง pipeline ทำงานแล้วลบทิ้งทันทีที่ได้
  report; ส่วนที่อยู่ใน Postgres ถาวรคือ `users`, `audit_overrides`, `playbook_embeddings`
  และ **`contract_reports`** (รายงานที่ผลิตแล้ว — อยู่จนกว่าเจ้าของจะสั่งลบ, สลับกลับไปเก็บใน
  Redis ตาม TTL ได้ด้วย `REPORT_STORAGE=redis`)
* **`alembic/env.py`** ดึง `sqlalchemy.url` จาก `Settings().database_url` เอง ไม่ต้องใส่
  connection string ซ้ำใน `alembic.ini`

### Review pipeline

```
upload → parse (PDF/DOCX) → segment → classify → match(playbook/RAG) → risk_scorer → judge → report
                          └────────→ metadata extractor ─────────────────────────────────↗
```
(ดู `app/ai/pipeline.py`: `segment → classify → match → score → judge`, มี retry 1 ครั้งถ้า
judge บอกว่า ungrounded, และ isolate failure ต่อ clause — clause ที่ error ไม่ทำให้ report ทั้งใบพัง)

`MetadataExtractor` อยู่นอกสายนั้น: ยิง LLM ครั้งเดียวต่อ**ฉบับ** อ่านหัว 4k + ท้าย 2.5k ตัวอักษร
เพื่อดึงคู่สัญญา/วันที่/มูลค่า/กฎหมายที่ใช้บังคับ แล้วทิ้งค่าที่หาไม่เจอในเอกสารแบบคำต่อคำ —
ล้มเหลวก็ได้แค่ metadata ว่าง รายงานยังออกครบ (ปิดด้วย `ENABLE_METADATA_EXTRACTION=false`)

---

## ✅ สิ่งที่ทำไปแล้ว (ทำงานได้จริง — ทดสอบกับ Gemini API + Postgres จริงแล้ว)

- **Core pipeline ทั้งเส้น** — ทดสอบ live: อัปโหลด `.docx` 2 clause (limitation of liability +
  termination) → ได้ report ที่ classify/match/score ถูกต้อง, citation อ้างอิง playbook position
  จริง, `verified=True` (ผ่าน grounding judge)
- **RAG แบบ hybrid** — dense (pgvector cosine) + BM25 rerank, ทดสอบว่า retrieve ตรง clause type จริง
- **LLM client** — cost tracking (`Usage`), structured output ตามวิธีของแต่ละค่าย + validate ด้วย
  pydantic, **timeout ต่อ call** (`LLM_TIMEOUT_SECONDS`, ค่า default 120s — ส่งเข้า SDK เป็น ms ผ่าน
  `HttpOptions.timeout` ของ Gemini, เป็นวินาทีของ Anthropic/OpenAI) กัน call ที่ค้างยึด worker ไว้
  ตลอดกาล; call ที่ล้มจนหมด retry จะทำให้ clause นั้นตกเป็น `unknown` + "manual review required"
  ไม่ทำให้ทั้ง report ล่ม
- **Retry ชั้นบน SDK** — `LLMClient._call` ยิงซ้ำเฉพาะ failure ที่ "ถามใหม่แล้วมีโอกาสได้"
  (`providers.is_transient`): timeout / 429 / 5xx **และคำตอบที่พังเอง** — 200 ที่ `content` ว่าง
  (`EmptyCompletionError`) หรือ JSON ที่ validate ไม่ผ่าน ซึ่ง SDK ของทุกค่ายถือว่า request สำเร็จ
  แล้วจึงไม่ retry ให้; 400/401/404 ไม่ retry เพราะตอบเหมือนเดิมทุกครั้ง งบ retry จำกัดสองชั้น —
  `LLM_MAX_ATTEMPTS` (default 3) และเวลาจริงอีก 1 timeout (`LLM_TIMEOUT_SECONDS`) เพื่อไม่ให้
  clause เดียวกิน 3×120 วิ
- **Guardrails wiring** — judge เช็ค citation validity + excerpt grounding + no-invented-fallback
  แบบ deterministic ก่อน แล้วค่อยถาม LLM เพิ่มสำหรับเช็ค rationale ที่ overreach
- **Override + audit log** — override เปลี่ยน risk level, re-aggregate summary, เขียน audit log ลง
  Postgres (permanent, ไม่มี TTL) — ทดสอบกับ DB จริงแล้ว
- **Accept risk แบบ persist** — `POST /contracts/{id}/accept` ตั้ง `accepted`/`accepted_by`/
  `accepted_at` บน clause review นั้น (ไม่แตะ risk level เลย — การรับรองแปลว่า "เห็นด้วย"
  ไม่ใช่ "แก้"), ถอนคืนได้ด้วย `accepted=false`, ลง audit ทั้งสองทิศทางผ่านคอลัมน์ `action`
  (`override`/`accept`/`unaccept`) และการ override จะล้างการรับรองทิ้งเพราะมันรับรองคำตัดสินเดิม
- **เก็บรายงานถาวรใน Postgres** — ตาราง `contract_reports`: `payload` (JSONB ของ
  `ContractReviewReport` ทั้งก้อน) + คอลัมน์ที่ history ใช้จริง (`session_id`, `created_at`,
  `filename`, `overall_risk`, `summary`, `clause_count`) เพื่อให้ `GET /contracts` อ่าน sidebar
  ได้โดยไม่ต้อง deserialize clause ทุกข้อของทุกรายงาน; index composite
  `(session_id, created_at)` ตรงกับ query เดียวที่มี — เลือก backend ด้วย `REPORT_STORAGE`
  (`postgres` default / `redis` = พฤติกรรม TTL แบบเดิม) ทดสอบทั้งสามตัว (memory/redis/postgres)
  ด้วยชุดเทสต์เดียวกันใน `tests/unit/test_report_repository.py`
- **Contract metadata** — `MetadataExtractor` (1 call ต่อฉบับ) → `ContractReviewReport.metadata`;
  ทุกค่าเป็นข้อความจากเอกสารแบบคำต่อคำ ตรวจด้วย `is_grounded()` ตัวเดียวกับที่ judge ใช้ ค่าที่
  หาไม่เจอถูกทิ้งเป็น `null` (ทดสอบกับ CUAD จริงแล้ว: ได้คู่สัญญา 2 ราย + `"1st day of August,
  2013"` + `"the laws of the State of Texas"` ครบ)
- **Data retention** — contract ดิบถูกลบทันทีหลัง orchestrator สร้าง report เสร็จ; รายงานที่ผลิต
  แล้วเก็บถาวรใน Postgres (`RETENTION_TTL_SECONDS` มีผลเฉพาะตอน `REPORT_STORAGE=redis`
  ซึ่งถ้าใช้ต้องตั้งไว้ **ต่ำกว่า** `ACCESS_TOKEN_EXPIRE_MINUTES` เสมอ เพื่อไม่ให้ report หมดอายุ
  ช้ากว่า token ที่ใช้ดึงมัน)
- **Data-retention job** — `python -m scripts.purge_reports` ลบรายงานที่เก่ากว่า
  `REPORT_RETENTION_DAYS` (default `None` = เก็บจนเจ้าของสั่งลบ) ผ่าน
  `PostgresReportRepository.purge_older_than()` — `--dry-run` นับก่อนได้ด้วย query เดียวกับที่ลบจริง,
  `--older-than-days N` สั่งทับค่าใน `.env` ได้ **ไม่มีอะไรในแอปเรียกมันเอง**: การลบข้อมูลของคนอื่น
  ไม่ควรเป็นผลพลอยได้ของการอัปโหลดครั้งถัดไป จึงต้องตั้ง cron/systemd timer เอง (ตัวอย่างอยู่ใน
  docstring ของสคริปต์) และ `purge_older_than` เจตนาไม่อยู่ใน `ReportRepository` protocol เพื่อให้
  โค้ดที่ทำงานตอน request เอื้อมข้าม session ไม่ได้ — ตอน `REPORT_STORAGE=redis` สคริปต์จบทันที
  เพราะคีย์มี TTL ของตัวเองอยู่แล้ว
- **Evaluation harness** — `run_eval` รันทั้ง pipeline จริงต่อ gold contract, คำนวณ
  segmentation F1 / classification accuracy / risk accuracy / citation validity;
  fixture ทั้งหมดสร้างด้วย `scripts.build_cuad_fixtures` จึงตรงกับ offset ของ
  `normalize()` และขอบเขต clause ที่ `Segmenter` ผลิตจริงเสมอ — **รันสคริปต์ใหม่ทุกครั้งที่แก้
  segmenter หรือ normalizer**
- **gold clause ที่ไม่มี `clause_type`** — CUAD annotate แค่ 41 หมวด ครอบไม่ครบ taxonomy 12 ตัว
  (ไม่มี confidentiality / force majeure) clause ที่ CUAD ไม่ได้ทำ label จึงถูกเขียนลง gold
  แบบมีแค่ `span` `run_eval` จะนับให้ในส่วน segmentation แต่ข้ามในส่วน classification/risk —
  ถ้าเดา label เองจะกลายเป็นวัด pipeline เทียบกับการเดา
- **`risk_level` ใน gold เป็น policy ไม่ใช่ข้อมูล** — CUAD บอกได้แค่ว่า clause นี้ *เป็น* liability cap
  ไม่ได้บอกว่ารับได้หรือไม่ ตาราง `CATEGORY_RISK` ใน `build_cuad_fixtures.py` คือ risk appetite
  ที่ playbook ยึด แก้ที่ไหนต้องแก้อีกที่ให้ตรงกัน
- **App factory + entrypoint** `app.main:app` — boot ได้, CORS + `SessionMiddleware` (สำหรับ OAuth),
  DomainError → JSON response ผ่าน `register_exception_handlers`
- **Health endpoints** — `GET /`, `GET /health`, `GET /health/db`
- **DB layer** — SQLAlchemy engine/session/`Base` + `get_db` (schema เป็นหน้าที่ของ Alembic แล้ว
  ไม่ได้สร้างตารางตอน startup อีกต่อไป — ดูหัวข้อ migrations ด้านล่าง)
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
- **Request hardening (2026-07-30)** — ปิด 4 จุดที่ทำให้ request เดียวยึดหรือเปิดระบบทั้งตัว:
  auth ระดับ router ที่ `/playbook/*` + `/evaluate`, endpoint ที่ทำงาน blocking ย้ายออกจาก event
  loop (`def` ธรรมดา + `run_in_threadpool()` สำหรับ review), เพดาน `MAX_UPLOAD_BYTES` (อ่านแบบ
  bounded → `413` ไม่ buffer ไฟล์ทั้งก้อนก่อน) กับ `MAX_CLAUSES` (เช็คหลัง segment ก่อนจ่ายค่า LLM),
  และ `/auth/dev-login` ต้องเปิด 2 กลอน (`APP_ENV=development` **และ** `ENABLE_DEV_LOGIN=true`)
  — ทุกข้อยืนยันด้วย `curl` กับเซิร์ฟเวอร์จริง ดูรายละเอียดในหัวข้อข้อควรระวังท้ายไฟล์
- **Tests** — **268 unit/integration ผ่านหมด ไม่มี skip เหลือ** (`pytest`) บวก **11 live test
  ที่ยิง provider จริง** ซึ่ง deselect เป็น default (`pytest -m live_llm`, ~3 นาที)
- **Live test ที่ยิง LLM จริง (2026-07-31)** — `tests/live/` + `tests/eval/test_regression.py`
  ปิดช่องที่ mock มองไม่เห็น: schema-constrained output ต้องได้ data ไม่ใช่ markdown, ทุก clause
  ต้องได้คำตอบจริง (ไม่ตกไปที่ `"Automated review failed"`), citation ต้องชี้ playbook position ที่มี
  อยู่จริงและ excerpt ต้องเป็นคำต่อคำ, fallback ต้องมาจาก playbook, metadata ต้องอยู่ในเอกสารจริง
  — รายละเอียดที่ [Live tests](#live-tests-ที่ยิง-provider-จริง)

---

## ❌ สิ่งที่ยังไม่ได้ทำ

**ไม่เหลือข้อไหนที่เป็นงานค้างแล้ว (2026-07-31)** — สามข้อที่เคยอยู่ตรงนี้ปิดครบ:

| ข้อเดิม | สถานะ |
|---------|-------|
| รัน evaluation บน gold label ชุดใหม่ | ✅ รันแล้ว 2026-07-31 (3 ฉบับ / 90 clause, 18 นาที) — ดู [ผลบน label ชุดใหม่](#ผล-eval-บน-label-ชุดใหม่-2026-07-31) |
| Eval regression gate ที่ skip ไว้ | ✅ เลิก skip แล้ว — เป็น `live_llm` gate บนสัญญาสั้นสุด 1 ฉบับ (~3 นาที) |
| integration test ที่ยิง LLM จริง | ✅ `tests/live/` 10 ตัว ยิง Z.AI + pgvector จริง |

เหลือแค่ข้อเดียวที่ **ตั้งใจไม่ทำ** และไม่ใช่งานโค้ด: **cron ของ retention job** — ตัว job
(`python -m scripts.purge_reports`) พร้อมใช้แล้ว แต่ค่า default คือเก็บรายงานไว้จนเจ้าของสั่งลบ
เพราะการลบกู้คืนไม่ได้และตัวสัญญาหายไปด้วย ยืนยันอีกครั้งเมื่อ 2026-07-31 ว่าจะไม่ตั้ง จนกว่าจะมี
นโยบายเก็บข้อมูลจริง

---

## การติดตั้งและรัน

### 1) Environment (`.env`)
สร้างไฟล์ `.env` ในโฟลเดอร์นี้ (ตัวอย่างค่า):
```env
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/contract_risk_db
REDIS_URL=redis://localhost:6379/0

# LLM (ค่าย default = Gemini; สลับค่ายดูหัวข้อถัดไป)
LLM_PROVIDER=gemini
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
ENABLE_DEV_LOGIN=true              # dev เท่านั้น! ต้องมีคู่กับ APP_ENV=development ไม่งั้น /auth/dev-login ปิด
PLAYBOOK_ADMIN_EMAILS=             # ว่าง = ทุกคนที่ login แก้ playbook ได้; ใส่อีเมล (คั่นด้วย ,) = คนอื่นได้ 403 ตอนเขียน

# เพดานต่อ 1 request (ค่าที่เห็นคือ default)
MAX_UPLOAD_BYTES=10485760          # 10 MB — เกินนี้ตอบ 413 โดยไม่อ่านไฟล์ทั้งก้อนเข้า memory
MAX_CLAUSES=300                    # เกินนี้ตอบ 413 หลัง segment ก่อนจ่ายค่า LLM (eval ไม่ติดเพดานนี้)

# Storage + feature flags (ค่าที่เห็นคือ default — ไม่ใส่ก็ได้)
REPORT_STORAGE=postgres            # postgres = เก็บถาวร | redis = หมดอายุตาม TTL
REPORT_RETENTION_DAYS=             # ว่าง = เก็บจนเจ้าของสั่งลบ; ตั้งแล้วต้องมี cron เรียก purge_reports
ENABLE_METADATA_EXTRACTION=true    # false = ประหยัด 1 LLM call/ฉบับ แลกกับไม่มีแผงคู่สัญญา/วันที่

# ความทนทานของ LLM call (ค่าที่เห็นคือ default)
LLM_THINKING=disabled              # disabled | auto — ดูหัวข้อ "thinking mode" ด้านล่าง
LLM_MAX_ATTEMPTS=3                 # จำนวนครั้งต่อ 1 logical call (นับครั้งแรกด้วย)
LLM_RETRY_BACKOFF_SECONDS=1.0      # หน่วงครั้งแรก แล้วคูณสองทุกครั้ง
LLM_TIMEOUT_SECONDS=120            # เพดานต่อ call — เป็นงบเวลาของ retry ทั้งชุดด้วย
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

### สลับค่าย AI ผ่าน `.env`

`LLM_PROVIDER` รับ 4 ค่า — `gemini` (default) / `anthropic` / `openai` / `zai` — โดยมี adapter จริง
3 ตัวใน `app/ai/providers.py` (`zai` คือ adapter แบบ OpenAI-compatible ที่เติม endpoint กับ model
ของ Z.AI ให้แล้ว) SDK ทั้งสามติดตั้งมาให้ครบตั้งแต่แรกและ `import` แบบ lazy ตัวที่ไม่ได้ใช้จึงไม่ถูก
โหลด — **สลับค่ายคือแก้ `.env` แล้ว restart เท่านั้น ไม่ต้องแตะโค้ด**

| ค่าย | ตั้งใน `.env` | model default | หมายเหตุ |
|------|--------------|---------------|----------|
| Gemini | `LLM_PROVIDER=gemini` + `GEMINI_API_KEY` | `gemini-3.5-flash` | ค่าเดิมของโปรเจกต์ |
| Claude | `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` | `claude-opus-5` | ไม่มี embedding API → retrieval ตกไปใช้ Gemini อัตโนมัติ |
| Z.AI (GLM) | `LLM_PROVIDER=zai` + `ZAI_API_KEY` | `glm-4.6` | เติม `https://api.z.ai/api/paas/v4` ให้เอง |
| OpenAI-compatible | `LLM_PROVIDER=openai` + `OPENAI_API_KEY` + `LLM_MODEL` + `LLM_BASE_URL` | — | ครอบคลุม OpenAI, DeepSeek, Ollama, vLLM; **ต้องระบุ `LLM_MODEL` เอง** |

ตัวแปรที่เพิ่มมา (ไม่ตั้งก็ได้ทั้งหมด ยกเว้นคีย์ของค่ายที่เลือก):

```env
LLM_PROVIDER=anthropic          # gemini | anthropic | openai | zai
ANTHROPIC_API_KEY=sk-ant-...    # หรือ OPENAI_API_KEY / ZAI_API_KEY ตามค่าย
LLM_API_KEY=...                 # คีย์กลาง ใช้แทนคีย์รายค่ายด้านบนได้
LLM_MODEL=claude-opus-5         # ไม่ตั้ง = ใช้ default ของค่ายนั้น
LLM_BASE_URL=...                # เฉพาะ host แบบ OpenAI-compatible

EMBEDDING_PROVIDER=gemini       # ไม่ตั้ง = ตามค่าย LLM ถ้าค่ายนั้น embed ได้ ไม่งั้นเป็น gemini
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_API_KEY=...           # ไม่ตั้ง = ใช้คีย์ของ EMBEDDING_PROVIDER
EMBEDDING_BASE_URL=...
```

**ข้อควรระวัง 3 ข้อ:**

1. **สลับค่ายแล้วต้องแก้ `LLM_MODEL` ด้วย** ถ้าเคยตั้งไว้ — ระบบตรวจให้แล้ว: ตั้ง
   `LLM_PROVIDER=anthropic` ทั้งที่ `LLM_MODEL=gemini-3.5-flash` จะขึ้น
   `ProviderConfigError: LLM_MODEL='gemini-3.5-flash' is a gemini model but the provider is
   anthropic` ตั้งแต่เรียกครั้งแรก แทนที่จะไปเจอ 404 ของฝั่ง vendor ที่ไม่บอกว่าตัวไหนผิด
   (ชื่อ model ที่ไม่รู้จัก เช่น fine-tune ของตัวเอง ปล่อยผ่านหมด)
2. **เปลี่ยน embedding = ต้อง re-ingest** — vector จากคนละ model เทียบ cosine กันไม่ได้ ถ้า
   `EMBEDDING_DIM` เปลี่ยนด้วยต้องเขียน Alembic migration ใหม่ (`ALTER COLUMN`) เพราะ migration
   `0c41a8268ed0` hardcode `VECTOR(dim=768)` ไว้ แล้วรัน `python -m scripts.ingest_playbook`
3. **restart เสมอ** — `get_settings()`, `get_llm_client()`, `get_embedder()` เป็น `@lru_cache`
   ทั้งหมด แก้ `.env` ระหว่างรันไม่มีผล และ `uvicorn --reload` ก็ไม่ reload เพราะจับแค่ไฟล์ `.py`

**Structured output** ต่างกันตามค่าย แต่ agent ไม่ต้องรู้: Gemini ใช้ `response_schema`, Claude ใช้
`messages.parse(output_format=...)`, ส่วน OpenAI-compatible ลอง `json_schema` แบบ strict ก่อน แล้ว
fallback เป็น `json_object` พร้อมแนบ schema ไปใน system prompt ถ้า host นั้นไม่รองรับ (จำผลไว้
ต่อ instance ไม่ยิงซ้ำทุก clause) — ทุกทางจบด้วย pydantic validate เหมือนกัน guardrail จึงไม่ต้องแยกเคส

> **Z.AI ไม่ได้ "ปฏิเสธ" `json_schema` — มันรับแล้วตอบ markdown มาเฉย ๆ** (ทดสอบกับ
> `api.z.ai` จริงเมื่อ 2026-07-30) เงื่อนไข fallback จึงเช็ค 2 อย่าง: host ปฏิเสธพารามิเตอร์ (400)
> **หรือ** ตอบมาแล้ว validate ไม่ผ่าน (`is_malformed_answer`) — ส่วน timeout/5xx ไม่นับ เพราะไม่ได้
> บอกอะไรเกี่ยวกับความสามารถของ host และ flag นี้จำไว้ตลอด process (timeout ครั้งเดียวไม่ควรทำให้
> ทั้ง run เสีย strict validation) และจะตั้งเป็น "host นี้ทำไม่ได้" ก็ต่อเมื่อ fallback ทำงานสำเร็จจริง

### thinking mode: `LLM_THINKING`

reasoning model กิน token ความคิดจาก **งบ `max_tokens` ก้อนเดียวกับคำตอบ** — คิดยาวเกินงบก็ได้
200 ที่ `content` ว่างเปล่ากลับมา ซึ่งคือสาเหตุที่ eval รอบ 2026-07-30 เสีย 3 clause
(`_RiskAssessment` ×2, `_LLMVerdict` ×1) และเป็นเหตุผลที่ค่า default คือ `disabled`

วัดกับ GLM-4.6 ด้วย prompt ของ risk scorer เอง (call เดียว, prompt เดียวกัน):

| `LLM_THINKING` | เวลา | output token | reasoning |
|----------------|------|--------------|-----------|
| `auto` (คิดก่อนตอบ) | 23.7 วิ | 984 | 4,556 ตัวอักษร |
| `disabled` | **2.1 วิ** | 55 | — |

พารามิเตอร์นี้เป็นของ Z.AI (`thinking: {"type": "disabled"}` ส่งผ่าน `extra_body`) ไม่ใช่ของ OpenAI
host อื่นที่ไม่รู้จักจะตอบ 400 → adapter จะเลิกส่งแล้วจำไว้ (probe-and-remember แบบเดียวกับ
`json_schema`) ส่วน Gemini/Anthropic ไม่ต้องสั่ง: Gemini ขอ thinking level เป็นราย call อยู่แล้ว และ
Anthropic ไม่คิดยาวถ้าไม่ส่ง `effort`

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
python -m scripts.run_eval                                              # เต็มชุด
python -m scripts.run_eval --limit 3                                    # 3 สัญญาแรก
python -m scripts.run_eval --contract ticketscominc-sponsorship-agreement   # เจาะจงฉบับ
```

> ⚠️ gold set มี 327 clause และ pipeline ยิง LLM ราว 4 ครั้งต่อ clause — เต็มชุดคือ ~1,300 request
> (หลักชั่วโมง) ลองน้อย ๆ ก่อนด้วย `--contract` ซึ่งเลือกฉบับสั้นได้ ต่างจาก `--limit` ที่ตัด
> จากหัวไฟล์ (ฉบับแรกในไฟล์คือฉบับที่มี 47 clause) — `POST /evaluate` ก็ส่ง `limit` ได้เหมือนกัน
> (จำนวน**สัญญา** ไม่ใช่ clause)

### Live tests ที่ยิง provider จริง

```bash
pytest                       # 268 ตัว — mock ที่ขอบ provider, ฟรี, ออฟไลน์, ~3 วินาที
pytest -m live_llm           # 11 ตัว — ยิง Z.AI + pgvector จริง, ~3 นาที, เสียค่า LLM
pytest -m live_llm -k structured   # 1 call ~3 วินาที: เช็คแค่ว่า structured output ยังใช้ได้
```

`live_llm` ถูก **deselect เป็นค่า default** ผ่าน `addopts` ใน `pyproject.toml` — `pytest` เปล่า ๆ
จึงยังฟรีและออฟไลน์เหมือนเดิม ส่วน `-m` ที่พิมพ์เองจะ override ตัวใน `addopts` ให้อัตโนมัติ
(pytest ใช้ตัวหลังสุด) ซึ่งคือกลไกที่ทำให้ `-m live_llm` เป็นการ "สั่งให้ยิงจริง" อย่างจงใจ

| ไฟล์ | เช็คอะไร |
|------|----------|
| `tests/live/test_live_pipeline.py` | 10 ตัว — structured output ต้องได้ data ไม่ใช่ markdown, ทุก clause ต้องได้คำตอบจริง, สัญญาไทยตัดได้ 3 ข้อ, citation ชี้ position จริง + excerpt คำต่อคำ ≥ 4 คำ, fallback มาจาก playbook, metadata อยู่ในเอกสารจริง, badge `verified` ต้องมีอะไรรองรับ |
| `tests/eval/test_regression.py` | 1 ตัว — รัน eval harness บนสัญญาสั้นสุด 1 ฉบับ แล้วกัน `segmentation_f1` ≥ 95% กับ `citation_validity` = 100% |

**ทำไม regression gate ไม่กัน `classification_accuracy` / `risk_accuracy` ด้วย** — สัญญาฉบับนั้นมี
label แค่ 4 ข้อ ขยับ 1 ข้อ = ขยับตัวเลข 25 จุด ตั้ง threshold ตรงนั้นคือตั้งให้ fail เพราะ noise
สองตัวนั้นวัดด้วย `scripts.run_eval` บน sample ที่ใหญ่พอแทน (ดู [ผล eval บน label
ชุดใหม่](#ผล-eval-บน-label-ชุดใหม่-2026-07-31))

> ⚠️ ต้องมี `.env` ที่มีคีย์จริง + Postgres ที่ ingest playbook แล้ว ถ้าไม่มี provider ที่ใช้ได้
> ชุดนี้จะ **skip พร้อมบอกเหตุผล** ไม่ใช่ fail — เพราะ "คีย์หมดอายุ" กับ "โมเดลแย่ลง" ไม่ควรอ่าน
> เหมือนกัน

### ลบรายงานเก่าตามนโยบาย retention
```bash
python -m scripts.purge_reports --dry-run              # นับก่อน ไม่ลบ
python -m scripts.purge_reports --older-than-days 90   # ลบที่เก่ากว่า 90 วัน
python -m scripts.purge_reports                        # ใช้ REPORT_RETENTION_DAYS จาก .env
```

> ⚠️ ลบแล้วไม่มีทางกู้ และตัวสัญญาหายไปด้วย (`payload` เก็บ clause text ทั้งฉบับ) — สคริปต์จึงบังคับ
> ให้ระบุกรอบเวลาแบบชัดเจน ไม่มี default ซ่อนไว้ ถ้าไม่ตั้ง `REPORT_RETENTION_DAYS` และไม่ส่ง flag
> มันจะบอกว่า "ไม่มีนโยบาย retention" แล้วจบด้วย exit 0 โดยไม่ลบอะไร
>
> **ไม่มีอะไรเรียกมันเอง** — ต้องตั้ง cron/systemd timer ถ้าอยากให้นโยบายมีผลจริง

### เพดานของ gold label ที่มาจาก CUAD

> ✅ **ซ่อมแล้วเมื่อ 2026-07-30** — หัวข้อนี้เก็บไว้เพราะมันคือหลักฐานว่าทำไมต้องซ่อม และเพราะ
> ตัวเลข eval ทุกชุดที่บันทึกไว้ก่อนหน้านั้นวัดกับ label ชุดเก่า วิธีใหม่อยู่ท้ายหัวข้อ

`classification_accuracy` **วัดการจับคู่ label ของ fixture ปนอยู่ด้วย ไม่ใช่ความแม่นของ classifier
เพียว ๆ** — เรื่องเดียวกับที่ `risk_accuracy` รอบแรกวัด provider ไม่ได้วัด pipeline

กฎเดิมให้ label กับ clause จาก **CUAD annotation ที่ offset ตกอยู่ในข้อนั้น**
(นับจำนวน category ที่ตก ตัวไหนมากสุดชนะ) แต่ CUAD ไม่ได้ annotate ว่า "ข้อนี้เป็นข้อประเภทอะไร"
มันตอบคำถาม 41 ข้อเกี่ยวกับสัญญา แล้วไฮไลต์ **วลี** ที่เป็นคำตอบ — วลีนั้นมักอยู่ในข้อที่ว่าด้วย
เรื่องอื่น ตรวจของจริง 3 ฉบับแรกด้วยการยิงเฉพาะ classifier + retriever (2026-07-30):

| clause จริง (ขึ้นต้นด้วย) | `cuad_categories` ที่ตกในข้อนั้น | gold | classifier ตอบ |
|---|---|---|---|
| `6.02. Termination. This Agreement may be terminated only:` | `Change Of Control` | `other` | `termination` ✅ |
| `13. Warranty. SIERRA warrants that the Product shall be free from defects` | `Insurance` | `other` | `warranty` ✅ |
| `9.07. Successors and Assigns.` | `Anti-Assignment`, `Minimum Commitment` | `payment_terms` | `other` ✅ |
| `1.01. Distribution Right. ...exclusive right to sell` | `Anti-Assignment`, `Covenant Not To Sue`, `Exclusivity` | `other` | `intellectual_property` |

สามแถวแรก **classifier ตอบถูก gold ผิด** — และแถวที่ 3 แพ้เพราะ tie-break: `Anti-Assignment`
(→`other`) กับ `Minimum Commitment` (→`payment_terms`) ได้ 1 คะแนนเท่ากัน แล้วกฎ "เสมอให้เอียงไป
ทางที่เสี่ยงกว่า" เลือก `payment_terms` ให้ข้อที่ว่าด้วยการโอนสิทธิ์

**นี่เป็นเหตุผลที่ `payment_terms` ได้ 25%** ไม่ใช่เพราะ playbook ครอบไม่พอ (`payment_terms` มี
จุดยืนอยู่ 5 อัน มากสุดในทุกประเภท — และการจำแนกประเภทไม่ได้ใช้ playbook เลย)

**สิ่งที่แก้ (2026-07-30):** label มาจาก category ที่ **ครอบคลุมข้อนั้นมากที่สุด** และถูกตัดทิ้ง
ถ้าครอบไม่ถึง `MIN_LABEL_COVERAGE` = 0.15 (ข้อนั้นกลายเป็นข้อไม่มี label ซึ่ง `run_eval` ข้ามให้
อยู่แล้ว) `Candidate.annotations` เก็บ span ของไฮไลต์แล้ว — `answer_start` + `len(answer["text"])`
ซึ่งเดิมทิ้ง — และ `covered_characters()` นับอักขระทับกันแบบ union เพราะไฮไลต์ category เดียวกัน
ซ้อนกันเองได้ (บวกดิบ ๆ ได้ coverage 116% ในข้อ Insurance จริง ๆ)

เกณฑ์เลือกจากการวัด ไม่ใช่เดา และ **เปลี่ยนใจหลังวัด**: ตั้ง 0.3 ก่อนตาม histogram ที่เป็น bimodal
(33 ข้อเหนือ 80%, 16 ข้อใต้ 20%) แต่ preview ฟ้องว่าหยาบเกินไป — ทิ้ง `governing_law` ของข้อ
`9.05. Applicable Law` และ `warranty` ของ `5.01. Products Warranty` ที่ CUAD ไฮไลต์ถูกแล้ว
เพียงแต่ไฮไลต์แค่ประโยคเดียวในข้อยาว (91 → 66 label) จึงลงมาที่ 0.15 = 91 → 82 label

ผลลัพธ์: **span ทั้ง 327 ข้อและตัวสัญญาทั้ง 12 ไฟล์ไม่เปลี่ยนเลย** (ตรวจด้วย md5 + เทียบ span
ทุกคู่) `segmentation_f1` จึงยังเทียบข้ามการเปลี่ยนนี้ได้ ส่วน `classification_accuracy` กับ
`risk_accuracy` เทียบไม่ได้ ทุก label ที่เหลือมี `label_coverage` ติดมาในไฟล์ (ต่ำสุด 0.158 /
กลาง 0.675 / สูงสุด 0.991) และข้อที่ CUAD แตะแต่ครอบไม่ถึงเกณฑ์ยังเก็บ `cuad_categories` ไว้
เพื่อให้แยกออกว่า "CUAD ไม่ได้พูดถึงข้อนี้" ต่างจาก "พูดถึงแต่หลักฐานเบาเกินกว่าจะตั้ง label"

**ต้นทุน (ไม่ใช่ของฟรี):** label หาย 9 อัน — 2 อันในนั้นเถียงได้ว่าถูก (`5. Consideration` =
`payment_terms`, `22. Assignment` = `other`) และ `11. Trademarks` เปลี่ยนจาก
`intellectual_property` → `other` เพราะตอนนี้ coverage ตัดสินแทนการนับจำนวน category

**สิ่งที่ตั้งใจไม่ทำ:** ดัน `classification_accuracy` ด้วยการแก้ prompt ให้เดาตาม label ที่ผิด หรือ
ให้คะแนนจากหัวข้อของ clause (`13. Warranty` → `warranty`) — นั่นคือวัด pipeline เทียบกับ heuristic
ของตัวเอง ไม่ใช่เทียบกับผู้เชี่ยวชาญ

### ผล eval บน label ชุดใหม่ (2026-07-31)

รัน `python -m scripts.run_eval --limit 3` (3 ฉบับ / 90 clause / label 22 ข้อ) ใช้เวลา **18 นาที
10 วินาที** — เร็วกว่า ~33 นาทีที่ประเมินไว้ คอนฟิกเดียวกับรอบก่อน (`zai` / `glm-4.6` /
`LLM_THINKING=disabled`) ต่างกันแค่ไม้บรรทัด:

| เมตริก | label เก่า (n=26) | **label ใหม่ (n=22)** | อ่านยังไง |
|--------|-------------------|----------------------|-----------|
| `segmentation_f1` | 100.00% | **100.00%** | เทียบข้ามได้จริงเพราะ span 327 ข้อไม่ถูกแตะ — และไม่ใช้ LLM |
| `classification_accuracy` | 57.69% | **45.45%** | **ลดลง 12 จุด** — อธิบายด้านล่าง |
| `risk_accuracy` | 50.00% | **50.00%** | ยืนเท่าเดิม |
| `citation_validity` | 100.00% | **100.00%** | ไม่มี citation ที่ชี้ position ปลอมเลย |

**ตัวเลข classification ที่ลดลงไม่ได้แปลว่า pipeline แย่ลง — pipeline ไม่ถูกแตะเลย** ไม้บรรทัด
เปลี่ยนอย่างเดียว และเปลี่ยนไปในทางที่ **ตัด label ที่ classifier เคยตอบถูกออก**: 57.69% ของ 26 คือ
ถูก 15 ข้อ, 45.45% ของ 22 คือถูก 10 ข้อ — label หายไป 4 แต่ข้อที่ถูกหายไป 5 นั่นคือราคาที่รู้อยู่แล้ว
ตอนเลือกเกณฑ์ `MIN_LABEL_COVERAGE` (ดูหัวข้อก่อนหน้า: label ที่เถียงได้ว่าถูกก็หายไปด้วย 2 อัน)

**ที่เพี้ยนหนักสุดคือ `non_compete`** (n=7, acc 28.57%) โดยตอบเป็น `intellectual_property` ไป 3 ข้อ
— ซึ่งสมเหตุสมผลกับตัวเอกสาร เพราะข้อห้ามแข่งขันใน CUAD มักเขียนรวมอยู่กับข้อสงวนสิทธิ์ในทรัพย์สิน
ทางปัญญา ส่วน `termination` (3/3) กับ `governing_law` (3/3) ยังเต็มทั้งคู่

**ข้อสังเกตจาก log ที่ไม่โผล่ในเมตริก:** GLM-4.6 ตอบกลับมาเป็น **list ของข้อความภาษาจีนที่ไม่
เกี่ยวอะไรเลย** แทนที่จะเป็น object ตาม schema อยู่ 1 ครั้ง — retry ชั้นบน SDK จับได้และยิงซ้ำจนได้
คำตอบที่ถูกรูป (`attempt 1/3 failed (ValidationError ...); retrying in 1.0s`) นี่คือ failure ชนิดที่
mock มองไม่เห็นและเป็นเหตุผลที่ `tests/live/` มีอยู่

**ยังไม่ได้รันเต็มชุด 327 clause** — ตัดสินใจว่าพอแค่ `--limit 3` (2026-07-31) เพราะ n=22 พอให้เทียบ
กับตัวเลขเก่าได้ตรง ๆ แล้ว ส่วนเต็มชุดคือ ~1,300 call / ~2 ชม.

### สร้าง data fixtures ใหม่จาก CUAD
```bash
python -m scripts.build_cuad_fixtures --cuad ~/project/cuad
```
เขียนทับ `data/contracts/`, `data/gold/annotations.jsonl` และ `data/samples/` — ต้องรันใหม่
ทุกครั้งที่แก้ `Segmenter` หรือ `normalize()` เพราะ gold span ผูกกับผลลัพธ์ของสองอย่างนั้น

---

## ข้อมูล (Data fixtures)

| ไฟล์ | คำอธิบาย |
|------|----------|
| `data/playbook/positions.yaml` | จุดยืน/ภาษามาตรฐานของบริษัท 36 ตำแหน่ง ครบทั้ง 12 clause type (preferred/fallback + `risk_if_absent`) — เขียนด้วยมือ อ้างอิงหมวดรีวิว 41 หมวดของ CUAD |
| `data/contracts/*.txt` | สัญญาการค้าจริง 12 ฉบับจาก CUAD v1 (คัดโดยสคริปต์ ไม่ได้เลือกด้วยมือ) |
| `data/gold/annotations.jsonl` | gold set: 327 clause span, **82** clause มี `clause_type`/`risk_level` + `label_coverage` (สัดส่วนของข้อที่ไฮไลต์ CUAD ครอบ) — ข้อที่ CUAD แตะแต่ครอบไม่ถึง `MIN_LABEL_COVERAGE` เก็บ `cuad_categories` ไว้แต่ไม่มี label |
| `data/samples/*.docx` | 3 ฉบับที่สั้นที่สุดแปลงเป็น `.docx` — เอาไว้ลากใส่หน้าอัปโหลดเพื่อทดสอบ |

ทั้งสามอย่างหลังสร้างใหม่ได้ด้วย:

```bash
python -m scripts.build_cuad_fixtures --cuad ~/project/cuad   # ต้องมี data.zip ของ CUAD
```

> ข้อความสัญญามาจาก [CUAD v1](https://www.atticusprojectai.org/cuad) (The Atticus Project,
> CC BY 4.0) — คัดตามเกณฑ์ในสคริปต์: ยาว 8k–20k ตัวอักษร, มีหัวข้อแบบเลขข้อ ≥ 8 หัวข้อ,
> มี annotation ≥ 8 หมวด แล้วเลือกแบบ greedy ให้ครอบ clause type ได้กว้างที่สุด
>
> **ห้ามแก้ `.txt` ด้วยมือ** — gold span เป็น character offset ของข้อความหลัง `normalize()`
> แก้ตัวอักษรเดียวก็ทำให้ annotation เพี้ยนทั้งไฟล์โดยไม่มีอะไรเตือน

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
| GET | `/contracts` | ✅ ต้อง auth; คืน `ReportSummary` ของ session ตัวเอง เรียงใหม่→เก่า |
| GET | `/contracts/{report_id}` | ✅ ต้อง auth; ของ session อื่น → `404` (ไม่ใช่ `403` เพราะ `403` = ยืนยันว่า id นี้มีอยู่จริง) |
| POST | `/contracts/{report_id}/override` | ✅ ต้อง auth; ตรวจเจ้าของ report ด้วย; automated test (mocked LLM) + ทดสอบกับ DB จริงแล้ว |
| POST | `/contracts/{report_id}/accept` | ✅ ต้อง auth; รับรอง/ถอนการรับรอง clause (`clause_id`, `accepted`, `note`) — ไม่แตะ risk level, ลง audit ทั้งสองทิศทาง |
| DELETE | `/contracts/{report_id}` | ✅ ต้อง auth; `204`/`404` (ของ session อื่นตอบ `404` เหมือนกัน) |
| GET | `/playbook` · `POST /playbook` · `GET/PUT/DELETE /playbook/{id}` | ✅ CRUD ครบ |
| GET | `/playbook/search` | ✅ |
| POST | `/evaluate` | ✅ |

> **ไม่มี endpoint export และไม่ได้ลืม** — ตัดออกจากขอบเขตเมื่อ 2026-07-30 พร้อมกับปุ่ม
> JSON/CSV/Print ฝั่ง frontend รายงานอ่านผ่าน `GET /contracts/{report_id}` บนหน้าเว็บทางเดียว
> (บันทึกไว้ตรงนี้เพื่อไม่ให้ใครเห็นช่องว่างแล้วเติมกลับเข้ามา — มันไม่ใช่งานที่ค้าง)

---

## Roadmap ที่เหลือ

**Backend ใช้งานได้ครบทุกเส้นทางหลักแล้ว และ roadmap เดิมปิดหมดแล้วเมื่อ 2026-07-31** (รวม Google
OAuth ที่ login จริงผ่านแล้ว, ประวัติรายงานถาวร, accept/override + audit, metadata ของสัญญา, gold
label ที่ให้จาก coverage, eval บนไม้บรรทัดใหม่ และ live test ที่ยิง provider จริง)

**ไม่มีงานโค้ดค้างแล้ว** สิ่งที่เหลือเป็นการตัดสินใจเชิงนโยบายกับงานวัดผลที่เลือกไม่ทำ:

- **cron ของ retention job** — ตั้งใจไม่ตั้ง (ยืนยัน 2026-07-31) จนกว่าจะมีนโยบายเก็บข้อมูลจริง
  ตัว job พร้อมใช้แล้ว: `python -m scripts.purge_reports --dry-run`
- **eval เต็มชุด 327 clause** — เลือกหยุดที่ `--limit 3` (n=22) เพราะเทียบกับตัวเลขเก่าได้ตรงแล้ว
  เต็มชุดคือ ~1,300 call / ~2 ชม. ถ้าอยากได้: `python -m scripts.run_eval`
- **คุณภาพ gold label ยังเป็นเพดานของตัวเลขความแม่น** — ไม่ใช่บั๊ก แต่เป็นข้อจำกัดที่รู้ตัว: CUAD
  ไม่ได้จำแนกประเภทข้อสัญญา การจะดัน `classification_accuracy` ให้สูงกว่านี้อย่างมีความหมายต้อง
  annotate เองโดยคน ไม่ใช่แก้ prompt (ดู [เพดานของ gold
  label](#เพดานของ-gold-label-ที่มาจาก-cuad))

---

# 🧠 เจาะลึก: logic ของ backend ทำงานยังไง

ส่วนนี้เดินตาม **request จริงหนึ่งเส้น** (`POST /contracts/review`) ตั้งแต่ HTTP วิ่งเข้ามา
จนได้ report กลับออกไป โดยแปะ **โค้ดจริงจากไฟล์** แล้วอธิบายเป็น **คอมเมนต์ในโค้ดทีละบรรทัด**

วิธีอ่านสัญลักษณ์ในคอมเมนต์:

| สัญลักษณ์ | หมายความว่า |
|---|---|
| `# ↑ ...` | อธิบายบรรทัดที่อยู่เหนือมัน |
| `# ❓ ...` | คำถามที่คนอ่านโค้ดมักสงสัย พร้อมคำตอบ |
| `# 🔑 ...` | จุดที่พลาดแล้วเจ็บ — ห้ามแก้โดยไม่เข้าใจ |
| `# 📌 ...` | หลักการที่ใช้ซ้ำทั้งโปรเจกต์ ไม่ใช่แค่ตรงนี้ |
| `# ⚠️ ...` | ข้อจำกัด/ปัญหาที่ยังไม่ได้แก้ในโค้ดจริง |

> **หมายเหตุ:** คอมเมนต์ภาษาไทยเหล่านี้มีเฉพาะในเอกสารนี้เพื่อการเรียนรู้ —
> โค้ดจริงในไฟล์ใช้คอมเมนต์ภาษาอังกฤษและเขียนเฉพาะจุดที่จำเป็นตามสไตล์ของโปรเจกต์

**เนื้อหาส่วนนี้แบ่งเป็น 3 บท:**

1. [📚 ปูพื้นก่อน](#-ปูพื้นก่อน-10-คอนเซปต์ที่โผล่ซ้ำทั้ง-codebase) — 10 คอนเซปต์ที่โผล่ซ้ำทุกไฟล์
   (`Depends`, `yield` dependency, `@lru_cache`, `Protocol` vs `ABC`, ...)
2. **ขั้น [0]–[12]** — เดินตาม `POST /contracts/review` ตั้งแต่ boot จนได้ report
3. [🔐 ภาคผนวก: OAuth flow](#-ภาคผนวก-oauth-flow--ตั้งแต่กดปุ่ม-sign-in-with-google-จนได้-jwt) —
   ขั้น [A]–[F] ว่า JWT ที่ใช้ในขั้น [3] มาจากไหน

## แผนที่ทั้งเส้น

```text
HTTP POST /contracts/review  (multipart: file=contract.docx, Authorization: Bearer <jwt>)
  │
  │  [0] main.create_app()      ── app ถูกสร้างตอน boot: CORS, SessionMiddleware, error handler
  ▼
  │  [1] config.get_settings()  ── อ่าน .env ครั้งเดียว cache ไว้ทั้ง process
  ▼
routes/contracts.py::review_contract
  │  [2] Depends(get_current_user)   ── bearer token → User (401 ถ้าไม่ผ่าน)
  │  [3] Depends(get_review_service) ── ประกอบ object graph ทั้งก้อน (DI)
  ▼
services/review.py::ReviewService.review_upload
  │  [4] เลือก parser จากนามสกุลไฟล์ → parsers.parse_docx / parse_pdf
  │  [5] contracts.save()   ── เก็บข้อความดิบชั่วคราวใน Redis
  ▼
ai/pipeline.py::Orchestrator.review
  │  [6] Segmenter    ── regex ล้วน ไม่ใช้ LLM
  │  └─ วนทีละ clause: ────────────────────────────────────┐
  │       [7]  Classifier   → LLM (structured output)      │
  │       [8]  Matcher      → Retriever (pgvector + BM25)  │
  │       [9]  RiskScorer   → LLM (structured output)      │
  │       [10] Judge        → guardrails ก่อน แล้วค่อย LLM │
  │  ◄──────────────────────────────────────────────────────┘
  │  [11] aggregate() ── รวมเป็น summary + overall risk
  ▼
  │  [12] contracts.delete() + reports.save()  ── ทิ้งสัญญาดิบ เก็บแต่ report
  ▼
HTTP 200  ContractReviewReport (JSON)
```

---

## 📚 ปูพื้นก่อน: 10 คอนเซปต์ที่โผล่ซ้ำทั้ง codebase

ถ้าเข้าใจ 10 ข้อนี้ก่อน จะอ่านโค้ดส่วนที่เหลือได้ลื่นมาก เพราะทุกไฟล์ใช้ pattern เดิมซ้ำ ๆ

### 1. `Depends()` — Dependency Injection ของ FastAPI

```python
def review_contract(
    file: UploadFile,
    current_user: User = Depends(get_current_user),   # ← ตรงนี้
): ...
```

**มันทำงานยังไง:** `Depends(get_current_user)` **ไม่ใช่การเรียกฟังก์ชัน** — สังเกตว่าไม่มี `()`
ต่อท้าย `get_current_user` เราแค่ *ส่งตัวฟังก์ชันเข้าไป* FastAPI จะเป็นคนเรียกให้เองตอนมี request
เข้ามา แล้วเอาค่าที่ได้มายัดใส่พารามิเตอร์ `current_user`

**ลำดับเหตุการณ์จริงเมื่อ request เข้ามา:**
```text
1. FastAPI เห็นว่า review_contract ต้องการ current_user
2. → เรียก get_current_user() ก่อน
3. → แต่ get_current_user เองก็ต้องการ credentials กับ db (มี Depends อีกชั้น!)
4. → FastAPI จึงเรียก _bearer_scheme(request) และ get_db() ก่อนอีกที
5. → ไล่ย้อนกลับขึ้นมาจนครบ แล้วค่อยเรียก review_contract
```
เรียกว่า **dependency tree** — FastAPI แก้ให้เองทั้งต้นไม้ เราแค่ประกาศว่า "ฉันต้องการอะไร"

**ทำไมถึงคุ้มที่จะเรียนรู้ pattern นี้:** เพราะมันทำให้เทสต์สลับของได้
```python
app.dependency_overrides[get_current_user] = lambda: current_user   # test_contracts.py:112
```
บรรทัดเดียวนี้ = "ต่อจากนี้ไม่ต้องตรวจ token จริง ใช้ user ปลอมตัวนี้แทน" โดย**ไม่ต้องแก้โค้ด
production แม้แต่ตัวอักษรเดียว**

### 2. `= Depends(...)` ที่ดูเหมือน default value

หลายคนงงว่าทำไม `current_user: User = Depends(...)` ถึงเขียนเหมือนค่า default
คำตอบ: มัน**คือ**ค่า default จริง ๆ ในสายตา Python — `Depends` เป็นแค่ object ธรรมดาตัวหนึ่ง
FastAPI อ่าน signature ของฟังก์ชัน (ผ่าน `inspect`) เห็นว่า default เป็น object ชนิด `Depends`
ก็เลยรู้ว่า "อันนี้ไม่ใช่ค่า default นะ แต่เป็นคำสั่งให้ฉันไปหามาให้"

> ⚠️ นี่คือสาเหตุที่ `pyproject.toml` ต้องมีบรรทัดนี้:
> ```toml
> [tool.ruff.lint.flake8-bugbear]
> extend-immutable-calls = ["fastapi.Depends"]
> ```
> เพราะ linter กฎ B008 ห้าม "เรียกฟังก์ชันใน default argument" (ปกติเป็นบั๊กจริง เช่น
> `def f(x = [])`) แต่กรณีของ FastAPI เป็นข้อยกเว้นที่ตั้งใจ จึงต้องบอก ruff ว่าอันนี้ผ่านได้

### 3. `yield` ใน dependency = โค้ดที่รันหลัง response ถูกส่ง

```python
def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db          # ← ส่ง session ให้ endpoint ใช้ แล้ว "หยุดค้าง" ตรงนี้
    finally:
        db.close()        # ← รันหลัง endpoint ทำงานเสร็จ (สำเร็จหรือ error ก็ตาม)
```

**อ่านยังไง:** ฟังก์ชันที่มี `yield` คือ generator — มันไม่ได้ทำงานรวดเดียวจบ แต่ "หยุดพัก"
ตรง `yield` แล้วรอ FastAPI มาปลุกต่อ

| จังหวะ | เกิดอะไรขึ้น |
|---|---|
| ก่อน `yield` | สร้าง session (setup) |
| ตรง `yield` | ส่ง session ให้ endpoint ใช้ แล้วโค้ดหยุดรอตรงนี้ |
| หลัง `yield` | endpoint ทำงานเสร็จแล้ว → `finally` ปิด session (teardown) |

**ทำไมสำคัญ:** ถ้าไม่ปิด session ทุก request จะยึด connection จาก pool ไว้
พอ pool หมด (default 5 connections) แอปจะค้างทั้งระบบ `finally` การันตีว่าปิดแน่นอน
**แม้ endpoint จะโยน exception**

### 4. `@lru_cache` = วิธีทำ singleton แบบ Python

```python
@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`lru_cache` จำ "ผลลัพธ์ของ argument ชุดนี้" ไว้ พอไม่มี argument เลย = จำผลลัพธ์เดียว
เรียกกี่ครั้งก็ได้ object เดิมกลับมาเสมอ

```python
get_settings() is get_settings()   # True — object เดียวกันเป๊ะ
```

**เทียบกับวิธีอื่น:** เขียน global variable + `if _instance is None` เองก็ได้ แต่ต้องจัดการ
thread safety เองและโค้ดยาวกว่า `@lru_cache` เป็น idiom มาตรฐานของ Python สำหรับงานนี้

**กฎเหล็กที่ห้ามลืม:** อย่าใส่ `@lru_cache` ให้ฟังก์ชันที่ผลลัพธ์ผูกกับ request
สังเกตว่าใน `dependencies.py` มีตัวเดียวที่**ไม่มี** decorator นี้:
```python
def get_override_service(db: Session = Depends(get_db)) -> OverrideService:
```
เพราะมันถือ `db` session ของ request นั้น ถ้า cache ไว้ = request ที่ 2 จะได้ session
ที่ถูก `close()` ไปแล้ว → พังทันที

### 5. `from __future__ import annotations`

บรรทัดนี้อยู่บนหัวไฟล์เกือบทุกไฟล์ในโปรเจกต์ มันสั่งว่า **"อย่า evaluate type hint ตอน import
ให้เก็บไว้เป็น string เฉย ๆ"**

**แก้ปัญหา 3 อย่าง:**
```python
def add(self, other: Usage) -> None:      # ← Usage คือคลาสที่กำลังนิยามอยู่!
```
1. อ้างถึงคลาสตัวเองได้โดยไม่ต้องใส่ quote (`"Usage"`)
2. ลด circular import — `schemas.py` กับ `parsers.py` อ้างถึงกันได้โดยไม่ต้องระวัง
3. import เร็วขึ้นเล็กน้อย เพราะไม่ต้องสร้าง object ของ type hint

### 6. `Protocol` vs `ABC` — สองวิธีนิยาม interface

```python
class Embedder(Protocol):                      # ← structural typing
    def embed(self, texts: list[str]) -> list[list[float]]: ...

class Agent[InputT, OutputT](ABC):             # ← nominal typing
    @abstractmethod
    def run(self, payload: InputT) -> OutputT: ...
```

| | `Protocol` | `ABC` |
|---|---|---|
| หลักการ | "มีเมธอดครบก็ใช้ได้" (duck typing) | "ต้องประกาศว่าสืบทอดมา" |
| ต้อง `class X(Embedder)` ไหม | **ไม่ต้อง** | ต้อง |
| บังคับตอนไหน | ตอน type check (mypy) | ตอน runtime — สร้าง object ไม่ได้ถ้าไม่ implement |

**ทำไมโปรเจกต์นี้ใช้ทั้งสองแบบ:**
* **storage/adapter ใช้ `Protocol`** — `DummyEmbedder` ไม่ได้เขียนว่า `class DummyEmbedder(Embedder)`
  เลยสักตัว แต่ใช้แทนกันได้เพราะมีเมธอด `embed()` เหมือนกัน ทำให้เทสต์สร้างของปลอมง่ายมาก
* **agent ใช้ `ABC`** — เพราะอยากให้ **พังทันทีตอนสร้าง object** ถ้าลืม implement `run()`
  ไม่ใช่ปล่อยให้ไปพังกลาง pipeline ตอนรันจริง

### 7. pydantic vs dataclass — ใช้ตัวไหนเมื่อไหร่

```python
class Clause(BaseModel):        # pydantic — จาก app/schemas.py
    id: str
    text: str

@dataclass
class ParsedDocument:           # dataclass — จาก app/parsers.py
    text: str
```

**กฎที่โปรเจกต์นี้ยึด:** *ข้อมูลมาจากภายนอกที่เชื่อไม่ได้ → pydantic / ข้อมูลภายในระบบ → dataclass*

| | pydantic `BaseModel` | `@dataclass` |
|---|---|---|
| validate ตอนสร้าง | ✅ ("abc" ใส่ใน `int` = error ทันที) | ❌ (ยัดอะไรก็เข้า) |
| แปลง JSON | ✅ `.model_dump_json()` | ต้องเขียนเอง |
| ความเร็ว | ช้ากว่า (จ่ายค่า validate) | เร็ว |
| ใช้ที่ไหนในโปรเจกต์ | `schemas.py` (ออก HTTP), `_RiskAssessment` (รับจาก LLM) | `ParsedDocument`, `Verdict`, `Usage` |

**ประเด็นสำคัญ:** `_RiskAssessment` ต้องเป็น pydantic เพราะ**คำตอบจาก LLM ถือเป็น input
ที่เชื่อไม่ได้** เหมือน request จากผู้ใช้ — โมเดลอาจตอบ field ไม่ครบหรือผิดชนิด

### 8. Generic syntax แบบใหม่ของ Python 3.12+

```python
class Agent[InputT, OutputT](ABC): ...              # คลาส generic
def complete_structured[T: BaseModel](...) -> T:    # เมธอด generic + ข้อจำกัด
```

สมัยก่อนต้องเขียน `InputT = TypeVar("InputT")` แยกไว้ข้างบนก่อน Python 3.12 เขียนในวงเล็บเหลี่ยม
ได้เลย ส่วน `[T: BaseModel]` อ่านว่า "T คืออะไรก็ได้ **ที่สืบทอดจาก BaseModel**"

**ได้อะไร:** editor รู้ว่า `complete_structured(response_model=_LLMVerdict)` คืน `_LLMVerdict`
(ไม่ใช่ `BaseModel` กว้าง ๆ) → พิมพ์ `.grounded` แล้วมี autocomplete และถ้าพิมพ์ผิดเห็นทันที
นี่คือเหตุผลที่ `requires-python = ">=3.12"` ใน `pyproject.toml`

### 9. `zip(..., strict=True)`

```python
for hit, dense, bm25 in zip(candidates, dense_scores, bm25_scores, strict=True):
```

`zip` ปกติจะ**หยุดเงียบ ๆ** ที่ list ที่สั้นที่สุด — ถ้า `bm25_scores` มี 3 ตัวแต่ `candidates`
มี 20 ตัว มันจะวนแค่ 3 รอบแล้วจบ **โดยไม่มี error** ข้อมูล 17 ตัวหายไปเฉย ๆ
`strict=True` เปลี่ยนความยาวไม่เท่ากันให้เป็น `ValueError` ทันที — บั๊กแบบนี้ถ้าไม่ดักไว้
จะกลายเป็น "ผลลัพธ์ดูปกติแต่ผิด" ซึ่งหายากที่สุด

### 10. Lazy import (import ข้างในฟังก์ชัน)

```python
def parse_pdf(data: bytes) -> ParsedDocument:
    import fitz  # PyMuPDF     ← ไม่ได้อยู่บนหัวไฟล์
```

ปกติ PEP 8 บอกให้ import ไว้บนสุด แต่ 3 กรณีนี้ตั้งใจฝ่าฝืน (`fitz`, `google.genai`, `rank_bm25`)
เพราะทั้งหมดเป็น library หนักที่โหลดช้า

**ผลที่ได้:** คนอัปโหลดแต่ `.docx` ไม่ต้องเสียเวลาโหลด PDF engine, เทสต์ที่ไม่แตะ LLM
รันได้แม้ไม่มี `GEMINI_API_KEY` และแอป boot เร็วขึ้น

---

## [0] Boot — `app/main.py`

```python
# ── IMPORT: ทำไมต้องมีแต่ละตัว ────────────────────────────────────────────────
from contextlib import asynccontextmanager
# ↑ FastAPI พารามิเตอร์ lifespan= รับได้เฉพาะ "async context manager" เท่านั้น
#   decorator ตัวนี้แปลง async generator (ฟังก์ชันที่มี yield) → context manager ให้
#   ถ้าไม่มีตัวนี้ ต้องเขียนคลาสที่มี __aenter__/__aexit__ เองซึ่งยาวกว่ามาก

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# ↑ เบราว์เซอร์บล็อก request ข้าม origin (same-origin policy)
#   frontend อยู่ :5173 / backend อยู่ :8000 = คนละ origin
#   ไม่มีตัวนี้ = เรียก API จาก frontend ไม่ได้เลย ติด CORS error ทุก request

from starlette.middleware.sessions import SessionMiddleware
# ↑ มาจาก Starlette ไม่ใช่ FastAPI เพราะ FastAPI เป็น layer บาง ๆ ทับ Starlette
#   เรื่อง middleware/response/websocket จึงยืมของ Starlette ตรง ๆ
#   ตัวนี้จำเป็นสำหรับ OAuth (อธิบายเหตุผลด้านล่าง)

from app.config import get_settings
from app.errors import register_exception_handlers
from app.logger import configure_logging
from app.routes import api_router
# ↑ import "ก้อนเดียว" ที่รวม router ทุกไฟล์ไว้แล้ว
#   → เพิ่ม endpoint ใหม่ในอนาคตไม่ต้องแตะ main.py เลย


# ── LIFESPAN: โค้ดที่รันตอนแอปเกิด และตอนแอปตาย ────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown hooks."""
    configure_logging()   # ← ทุกอย่างก่อน yield = รันตอน "startup"
    yield                 # ← ตรงนี้คือช่วงที่แอปเปิดรับ request (ค้างอยู่ตรงนี้ทั้งชีวิตแอป)
    # ทุกอย่างหลัง yield = รันตอน "shutdown" (ตอนนี้ยังไม่มีอะไรต้องเก็บกวาด)
    #
    # 📌 สังเกต: ไม่มี create_all() ตรงนี้แล้ว — schema เป็นหน้าที่ของ Alembic
    #    ต้องรัน `alembic upgrade head` ก่อนสตาร์ทแอป (docker-entrypoint.sh ทำให้อยู่)


# ── FACTORY: ประกอบแอปขึ้นมาเป็นตัว ───────────────────────────────────────────
def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()   # ← อ่าน .env (ครั้งแรกที่เรียกเท่านั้น เพราะมี @lru_cache)

    app = FastAPI(title="Contract Clause Risk Reviewer", version="0.1.0", lifespan=lifespan)
    #                    ↑ title/version ไปโผล่ใน /docs (Swagger UI) ที่ FastAPI สร้างให้ฟรี

    register_exception_handlers(app)
    # ↑ ลงทะเบียนตัวแปลง DomainError → JSON response
    #   ต้องทำ "ก่อน" มี request เข้ามา เพราะ FastAPI เก็บ handler ไว้ใน app ตั้งแต่ตอนสร้าง

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],  # ← อนุญาตเฉพาะ origin เดียว ไม่ใช่ "*"
        #                                          เพราะ "*" ใช้คู่กับ credentials ไม่ได้
        #                                          และเปิดกว้างเกินจำเป็น = เว็บใครก็ยิง API เราได้
        allow_credentials=True,                 # ← ยอมให้แนบ cookie/Authorization header
        allow_methods=["*"],                    # ← GET/POST/PUT/... ครบ
        allow_headers=["*"],
    )

    # Required by Authlib's OAuth redirect flow to persist state across requests.
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)
    # ↑ ทำไมต้องมี session ทั้งที่ระบบใช้ JWT (stateless)?
    #   เพราะ OAuth เป็น flow ที่กินเวลา "ข้าม request":
    #     request 1: /auth/google/login  → Authlib สุ่มค่า state เก็บใส่ session แล้ว redirect ไป Google
    #     request 2: /auth/google/callback ← Google ส่งกลับมาพร้อม state
    #                Authlib ต้องเทียบ state สองตัวนี้เพื่อกัน CSRF
    #   ไม่มี middleware นี้ = state หายระหว่างทาง = callback พังด้วย "mismatching_state" ทุกครั้ง
    #
    # 📌 หมายเหตุ: middleware ที่ add ทีหลังจะอยู่ "ชั้นนอกสุด" (ทำงานก่อน)
    #    ลำดับนี้จึงเป็น: Session → CORS → route

    app.include_router(api_router)   # ← mount ทุก endpoint ทีเดียว
    return app


app = create_app()
# ↑ ตัวแปรนี้คือสิ่งที่ uvicorn ตามหา ตอนสั่ง `uvicorn app.main:app`
#                                                        ↑ ไฟล์  ↑ ชื่อตัวแปร
#
# ❓ ทำไมต้องมี create_app() แยก ในเมื่อสุดท้ายก็เรียกมันสร้าง global app อยู่ดี?
#   เพราะเทสต์ต้องการ "app ใหม่ที่สะอาด" ทุกครั้ง ที่ไม่มี dependency_overrides ค้างจากเทสต์ก่อน
#   ดู tests/integration/test_contracts.py:142 → TestClient(create_app())
#   ถ้ามีแต่ global app ตัวเดียว: เทสต์ A override auth ทิ้งไว้ → เทสต์ B ที่อยากเช็ค 401 จะได้ 200
#   กลายเป็นเทสต์ที่ผลลัพธ์ขึ้นกับ "ลำดับการรัน" ซึ่ง debug ยากมาก
```

> 💡 **dependency ที่ไม่มีใคร import แต่ลบไม่ได้:** `itsdangerous` ใน `pyproject.toml`
> ไม่ปรากฏใน `import` ของไฟล์ไหนเลย แต่ `SessionMiddleware` เรียกใช้มันข้างในเพื่อเซ็น
> session cookie — ถอดออกเมื่อไหร่แอป boot ไม่ขึ้นทันที
> (`python-multipart` ก็เป็นแบบเดียวกัน: FastAPI ใช้มันแกะ `UploadFile` จาก multipart form)

---

## [1] Settings — `app/config.py`

```python
from functools import lru_cache
# ↑ ใช้ทำ singleton (ดูท้ายไฟล์)

from pydantic_settings import BaseSettings, SettingsConfigDict
# ↑ ทำไมต้องเป็น pydantic_settings ไม่ใช่ os.getenv() ธรรมดา?
#   os.getenv("LLM_TIMEOUT_SECONDS") คืน str เสมอ → ต้อง int() เองทุกที่ → ลืมที่เดียวก็พัง
#   BaseSettings อ่าน type hint ของแต่ละ field แล้วแปลง + validate ให้อัตโนมัติ
#   ใส่ค่าที่แปลงไม่ได้ = ระเบิดตั้งแต่ boot ไม่ใช่ TypeError ตอนเอาไปคูณ 1000 กลาง request


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",    # ← อ่านค่าจากไฟล์นี้ (ถ้ามี env var จริงในระบบ ตัวจริงชนะ)
        extra="ignore",     # ← เจอ key ที่ไม่ได้ประกาศไว้ → เมินไปเลย ไม่ต้อง error
        #                      จำเป็น! เพราะ .env ไฟล์เดียวถูกใช้ร่วมกับ docker-compose
        #                      และ frontend ซึ่งมี key ที่ backend ไม่รู้จัก (เช่น VITE_*)
        #                      ถ้าไม่ ignore = pydantic โยน ValidationError ใส่ key ที่ไม่เกี่ยวกับมัน
    )

    # --- core ---
    database_url: str
    # ↑ 🔑 ไม่มีค่า default = "บังคับต้องมี" ถ้า .env ไม่มีบรรทัดนี้ แอป boot ไม่ขึ้น
    #   ตั้งใจให้เป็นแบบนี้: ถ้าใส่ default ปลอม ๆ ไว้ (เช่น "sqlite:///tmp.db")
    #   แอปจะสตาร์ทได้แต่ไปพังตอนมี user จริง — หรือแย่กว่า: jwt_secret_key ที่เป็น
    #   "changeme" จะขึ้น production โดยไม่มีใครทันสังเกต
    #   📌 หลักการ: พังตอน boot ดีกว่าพังตอนมีคนใช้

    app_env: str = "development"
    frontend_url: str = "http://localhost:5173"
    # ↑ มีค่า default = "ไม่ใส่ก็ได้" ใช้กับค่าที่ค่าเริ่มต้นปลอดภัยและใช้ได้จริงตอน dev
    ...
    llm_timeout_seconds: int = 120
    # ↑ หน่วยเป็น "วินาที" ตรงนี้ เพราะคนตั้งค่าอ่านง่ายกว่า
    #   แต่ SDK ของ Gemini รับเป็น "มิลลิวินาที" → ต้อง *1000 ตอนส่งเข้า (ดูขั้น [8])
    #   ⚠️ ค่านี้ทำสองหน้าที่: เพดานต่อ 1 call **และ** งบเวลาของ retry ทั้งชุด (ดู llm_max_attempts)

    llm_thinking: Literal["auto", "disabled"] = "disabled"
    # ↑ 🔑 reasoning model คิดก่อนตอบ และ token ความคิดถูกหักจาก max_tokens "ก้อนเดียวกับคำตอบ"
    #   คิดยาวเกินงบ = ได้ HTTP 200 ที่ content ว่างเปล่า — ไม่ใช่ error ที่ SDK จับให้
    #   วัดกับ GLM-4.6 ด้วย prompt ของ risk scorer เอง: 23.7 วิ / 984 output token ตอนเปิดคิด
    #   เทียบกับ 2.1 วิ / 55 token ตอนปิด → default จึงเป็น disabled
    #   ❓ ทำไมเป็น Literal ไม่ใช่ bool? เพราะ "auto" ไม่ได้แปลว่า "เปิด" แต่แปลว่า
    #     "ไม่สั่งอะไร ปล่อยตาม default ของโมเดล" ซึ่งเป็นคนละความหมายกับการสั่งให้คิด

    llm_max_attempts: int = 3
    # ↑ นับครั้งแรกด้วย (3 = ยิงแรก + retry 2) retry เฉพาะ failure ที่ providers.is_transient()
    #   บอกว่า "ถามใหม่แล้วมีโอกาสได้" — 400/401 ไม่ retry เพราะตอบเหมือนเดิมทุกครั้ง

    retention_ttl_seconds: int = 60 * 60 * 8
    # ↑ เขียน 60*60*8 แทน 28800 เพราะอ่านแล้วรู้ทันทีว่า "8 ชั่วโมง"
    #   Python คำนวณให้ตอน import ครั้งเดียว ไม่มีต้นทุน runtime
    #   ⚠️ มีผลเฉพาะ REPORT_STORAGE=redis — ฝั่ง Postgres ไม่มีอะไรหมดอายุเอง

    report_retention_days: int | None = None
    # ↑ None = เก็บจนเจ้าของสั่งลบ (ค่า default) ตั้งเป็นตัวเลข = "นโยบาย" ไม่ใช่ "กลไก":
    #   ไม่มีโค้ดใน request path อ่านค่านี้เลย เพราะการลบข้อมูลของคนอื่นไม่ควรเป็นผลพลอยได้
    #   ของการอัปโหลดครั้งถัดไป — ต้องมี cron เรียก scripts/purge_reports.py เอง


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()  # type: ignore[call-arg]
    # ↑ ❓ ทำไมต้อง @lru_cache?
    #   Settings() 1 ครั้ง = เปิดไฟล์ .env + parse + validate ทุก field ใหม่หมด
    #   ถ้าเรียกทุก request = disk I/O ฟรี ๆ ทุกครั้ง
    #   @lru_cache ทำให้ทั้ง process ใช้ object เดียวกัน → get_settings() is get_settings() == True
    #   ผลพลอยได้ที่สำคัญกว่า: การันตีว่าทุกส่วนของระบบเห็น config ชุดเดียวกันเป๊ะ
    #
    # ↑ ❓ ทำไมต้องมี # type: ignore[call-arg]?
    #   mypy เห็น Settings() ถูกเรียกโดยไม่ส่ง database_url (ซึ่งเป็น required field) → มันฟ้อง
    #   แต่มันไม่รู้ว่า BaseSettings ไปหาค่ามาจาก .env เองตอน runtime
    #   บรรทัดนี้คือการบอก mypy ว่า "รู้แล้ว ตรงนี้ตั้งใจ"
```

---

## [2] Route — `app/routes/contracts.py`

```python
from fastapi import APIRouter, Depends, UploadFile
# APIRouter  = จัดกลุ่ม endpoint + ตั้ง prefix ที่เดียว ไม่ต้องพิมพ์ "/contracts" ซ้ำทุกฟังก์ชัน
# Depends    = หัวใจของ DI (ดูคอนเซปต์ข้อ 1 ด้านบน)
# UploadFile = รับไฟล์จาก multipart form แบบ "spooled file":
#              ไฟล์เล็กอยู่ใน RAM, ไฟล์ใหญ่ล้นลงดิสก์อัตโนมัติ → อัปโหลด 100 MB ไม่ทำ RAM แตก
#              ⚠️ ต้องลง python-multipart ด้วย ไม่งั้น FastAPI error ตั้งแต่ startup

from app.dependencies import get_current_user, get_override_service, get_review_service
from app.models import User
# ↑ import มาเพื่อใช้เป็น "type hint" อย่างเดียว ไม่ได้เอามา query DB ตรงนี้
#   ประโยชน์: editor/mypy รู้ว่า current_user มี .id / .email → พิมพ์ผิดเห็นทันที

from app.schemas import ContractReviewReport, RiskLevel
from app.services.review import ReviewService

router = APIRouter(prefix="/contracts", tags=["contracts"])
#                  ↑ ทุก path ในไฟล์นี้     ↑ ชื่อกลุ่มใน Swagger UI (/docs)
#                    เติม /contracts ให้เอง    ทำให้เอกสารอ่านง่ายเวลามี endpoint เยอะ


@router.post("/review", response_model=ContractReviewReport)
#            ↑ path จริง = /contracts/review (prefix + path)
#                        ↑ ❓ มี return type hint แล้ว ทำไมต้องเขียน response_model อีก?
#                          เพราะมันทำ 3 อย่างที่ type hint ทำไม่ได้:
#                          1. กรอง field ที่ไม่ได้ประกาศไว้ทิ้งก่อนส่งออก (กันข้อมูลภายในรั่ว)
#                          2. serialize เป็น JSON ให้ถูกต้อง (datetime, Enum แปลงให้อัตโนมัติ)
#                          3. สร้าง OpenAPI schema → frontend generate type ตามได้
async def review_contract(
    file: UploadFile,
    # ↑ ไม่มีค่า default = FastAPI รู้ว่านี่คือ "ข้อมูลที่ต้องมาจาก request"
    #   และเพราะ type เป็น UploadFile มันจึงไปหาใน multipart body ให้เอง

    current_user: User = Depends(get_current_user),
    # ↑ อ่านว่า: "ก่อนจะรันฟังก์ชันนี้ ช่วยเรียก get_current_user() แล้วเอาผลมาใส่ตรงนี้ที"
    #   ถ้า get_current_user โยน HTTPException(401) ฟังก์ชันนี้จะ "ไม่ถูกเรียกเลย"
    #   → นี่คือวิธีทำ auth guard แบบ FastAPI: ไม่ต้องเขียน if ตรวจสิทธิ์ในทุก endpoint

    service: ReviewService = Depends(get_review_service),
    # ↑ ของจริงประกอบไว้ใน dependencies.py แล้ว route แค่ "ขอ" มาใช้
    #   ถ้า route สร้าง ReviewService(...) เองตรงนี้ = เทสต์แทนที่มันไม่ได้เลย
) -> ContractReviewReport:
    """Upload a contract and run the review pipeline."""
    data = await file.read()
    # ↑ ต้อง await เพราะ UploadFile.read() เป็น async (Starlette อ่านไฟล์แบบไม่บล็อก)
    #   และเพราะมี await ตรงนี้ ฟังก์ชันนี้จึงต้องเป็น async def
    #   ⚠️ จุดที่ยังไม่ได้แก้: ไม่มีการเช็ค len(data) ก่อน → อัปโหลดไฟล์ใหญ่แค่ไหนก็รับหมด

    return service.review_upload(
        filename=file.filename or "upload",
        # ↑ filename เป็น str | None (ผู้ใช้อาจส่ง multipart ที่ไม่มีชื่อไฟล์มา)
        #   `or "upload"` กัน None ไม่ให้ไหลลงไปพังใน service ตอน .rsplit(".")
        data=data,
        session_id=current_user.id,
        # ↑ ❓ ทำไม session_id = user id ไม่ทำ session id แยกต่างหาก?
        #   เพราะ "session" ที่นี่หมายถึง "ขอบเขตความเป็นเจ้าของข้อมูล" ไม่ใช่ browser session
        #   ผูกกับ user ตรง ๆ → report ของแต่ละคนแยกกันเองอัตโนมัติ
        #   และ RETENTION_TTL (8 ชม.) ถูกตั้งให้ต่ำกว่าอายุ token (12 ชม.) เสมอ
        #   เพื่อไม่ให้เกิดเคส "token ยังใช้ได้ แต่ report หายไปแล้ว" → กด override ไม่ได้
        #   (มีเทสต์ตรึงความสัมพันธ์นี้ไว้ที่ tests/unit/test_timeouts.py)
    )
    # 📌 สังเกตว่า route ทั้งฟังก์ชันมีแค่ 2 statement — นี่คือกฎของโปรเจกต์:
    #    routes/ = แปลงภาษา HTTP → ภาษา domain เท่านั้น
    #    ไม่มี if/else เชิงธุรกิจ ไม่มี query DB ไม่มีการคำนวณ
    #    เพราะอะไรที่อยู่ใน route จะทดสอบได้ผ่าน HTTP อย่างเดียว
    #    แต่ถ้าอยู่ใน service → เรียกทดสอบตรง ๆ ได้ และเอาไปใช้ใน CLI/worker ได้ด้วย
```

---

## [3] Auth dependency — `app/dependencies.py` + `app/security.py`

```python
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
# ↑ HTTPBearer ทำ 2 อย่าง: (1) แกะ header "Authorization: Bearer <token>" ให้
#   (2) ทำให้ Swagger UI (/docs) มีปุ่ม "Authorize" ให้ทดสอบ endpoint ที่ต้อง login ได้

_bearer_scheme = HTTPBearer(auto_error=False)
# ↑ ❓ ทำไม auto_error=False?
#   ค่า default (True) จะโยน 403 Forbidden ให้เองเมื่อไม่มี header ซึ่ง "ผิดความหมาย":
#     401 Unauthorized = ยังไม่ได้ login / token ใช้ไม่ได้   ← เคสของเรา
#     403 Forbidden    = login แล้ว แต่ไม่มีสิทธิ์ทำสิ่งนี้
#   ปิด auto_error แล้วจัดการเอง → คุม status code ได้ถูกต้อง
#   สำคัญกับ frontend ด้วย: lib/api.ts ใช้ 401 เป็นสัญญาณ "ล้าง token แล้วเด้งไปหน้า login"
#   ถ้าส่ง 403 ไป ผู้ใช้จะค้างอยู่หน้าเดิมโดยไม่รู้ว่าต้อง login ใหม่
#
# ↑ ตัวแปรขึ้นต้นด้วย _ = ใช้ภายในโมดูลนี้เท่านั้น (ธรรมเนียม Python ไม่ใช่การบังคับ)
#   สร้างครั้งเดียวตอน import แล้วใช้ซ้ำ ไม่ต้องสร้างใหม่ทุก request


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    # ↑ Depends ซ้อน Depends ได้ — dependency ก็มี dependency ของตัวเองได้
    #   type เป็น "| None" เพราะเราปิด auto_error ไว้ → ไม่มี header ก็ได้ None มา ไม่ error

    db: Session = Depends(get_db),
    # ↑ ได้ session ที่ผูกกับ request นี้ และจะถูกปิดอัตโนมัติหลัง response ถูกส่ง
    #   (จาก finally ใน get_db — ดูคอนเซปต์ข้อ 3)
) -> User:
    """Resolve the bearer token into the signed-in user, or raise ``401``."""
    if credentials is None:
        # ไม่ส่ง header Authorization มาเลย
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        # ↑ ใช้ status.HTTP_401_UNAUTHORIZED แทนเลข 401 ดิบ ๆ เพราะอ่านแล้วรู้ความหมายทันที
        #   และพิมพ์ผิดเป็น 4001 ไม่ได้ (constant ที่ไม่มีอยู่ = NameError ทันที)

    payload = decode_access_token(credentials.credentials)
    # ↑ .credentials คือส่วนที่อยู่หลังคำว่า "Bearer " (ตัว token ล้วน ๆ)
    #   ถ้า token ปลอม/หมดอายุ ฟังก์ชันนี้จะโยน 401 ออกไปเอง ไม่ต้องเช็คต่อ

    user = db.get(User, payload.get("sub"))
    # ↑ "sub" (subject) = มาตรฐาน JWT แปลว่า "token นี้เป็นของใคร" — เราเก็บ Google user id ไว้
    #   db.get(Model, pk) = ค้นด้วย primary key โดยเฉพาะ เร็วกว่า .query().filter().first()
    #   เพราะถ้า object นั้นอยู่ใน identity map ของ session อยู่แล้ว จะไม่ยิง SQL ซ้ำเลย
    #
    #   ❓ มี "sub" ใน token อยู่แล้ว ทำไมต้องเสียเวลา query DB อีก?
    #     ถ้าเชื่อ token อย่างเดียว: user ที่ถูกลบ/ถูกแบนไปแล้ว จะยังใช้ระบบได้
    #     ต่อไปอีกจนกว่า token จะหมดอายุ (12 ชม.) เพราะ JWT เพิกถอนกลางคันไม่ได้
    #     การ query ทำให้ "ลบ user แล้วมีผลทันที" — จ่ายแค่ primary key lookup ต่อ request
    #     ซึ่งถูกมาก เทียบกับความเสี่ยงที่ลดได้

    if user is None:
        # token เซ็นถูกต้อง แต่ user id ในนั้นไม่มีในระบบแล้ว (เช่น ถูกลบไป)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
    # ↑ ค่าที่ return ตรงนี้ = ค่าที่ไปโผล่ในพารามิเตอร์ current_user ของ route
```

```python
# app/security.py — ส่วนที่ตรวจ token จริง ๆ
from jose import JWTError, jwt
# ↑ python-jose: library สำหรับ JWT
#   JWTError เป็น exception "แม่" ที่ครอบทุกกรณีพัง (signature ผิด, หมดอายุ, รูปแบบเพี้ยน)


def decode_access_token(token: str) -> dict:
    """Verify a JWT and return its claims, or raise ``401``."""
    try:
        return jwt.decode(
            token,
            _settings.jwt_secret_key,              # ← กุญแจเดียวกับตอนเซ็น (HS256 = symmetric)
            algorithms=[_settings.jwt_algorithm],   # ← 🔒 จุดสำคัญด้านความปลอดภัย!
            # ↑ ต้องระบุเป็น list ตายตัวเสมอ ห้ามละ
            #   ถ้าไม่ระบุ library จะเชื่อ field "alg" ที่อยู่ใน header ของ token เอง
            #   ซึ่งผู้โจมตีแก้ได้ → ช่องโหว่คลาสสิก 2 แบบ:
            #     1. ตั้ง alg: "none" = token ไม่ต้องมีลายเซ็นเลย ปลอมได้ทันที
            #     2. สลับ RS256 → HS256 = เอา public key มาใช้เป็น secret ในการปลอม
            #   การ pin ไว้ = ผู้โจมตีเลือก algorithm แทนเราไม่ได้
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            # ↑ ❓ ทำไมข้อความเดียวครอบทุกสาเหตุ ไม่บอกให้ชัดว่า "หมดอายุ" หรือ "ลายเซ็นผิด"?
            #   ตั้งใจ — ข้อความที่ละเอียดเกินไปช่วยผู้โจมตีปรับวิธีโจมตี
            #   ("ลายเซ็นผิด" = เขารู้ว่าเดา payload ถูกแล้ว เหลือแค่หา key)
            #   ส่วนคนพัฒนายังเห็นสาเหตุจริงได้จาก log เพราะ...
        ) from exc
        # ↑ `from exc` = ผูก exception ต้นทางไว้ใน traceback
        #   log จะขึ้นว่า "The above exception was the direct cause of..." พร้อมสาเหตุจริง
        #   ถ้าไม่ใส่ from = ข้อมูลว่าพังเพราะอะไรหายไปเลย debug ยากมาก
```

---

## [4] DI wiring — `app/dependencies.py`

```python
# ── ชั้น infrastructure: ของที่แพงและใช้ร่วมกันทั้ง process ───────────────────
@lru_cache
def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
    #                                                     ↑ สำคัญมาก!
    # decode_responses=True → Redis คืน str แทน bytes
    # ถ้าไม่ใส่ จะได้ b'{"report_id":...}' แล้วต้อง .decode() เองทุกที่ที่อ่านค่า
    # ใส่ตรงนี้ที่เดียว = repo ทุกตัวป้อนค่าเข้า model_validate_json() ได้ตรง ๆ
    #
    # @lru_cache ตรงนี้จำเป็นมาก: Redis client มี connection pool อยู่ข้างใน
    # สร้างใหม่ทุก request = เปิด connection ใหม่เรื่อย ๆ จน Redis ปฏิเสธการเชื่อมต่อ


# ── ชั้น pipeline: ประกอบ agent ทั้ง 5 ตัวเข้าด้วยกัน ─────────────────────────
@lru_cache
def get_orchestrator() -> Orchestrator:
    """Build the shared segment -> classify -> match -> score -> judge pipeline."""
    llm = get_llm_client()
    # ↑ ดึงมาเก็บตัวแปรก่อน เพราะต้องใช้ซ้ำ 4 ครั้งข้างล่าง
    #   (จะเรียก get_llm_client() ซ้ำ 4 ครั้งก็ได้ผลเดียวกันเพราะมี @lru_cache
    #    แต่เขียนแบบนี้อ่านชัดกว่าว่า "agent ทุกตัวใช้ client ตัวเดียวกัน")

    return Orchestrator(
        segmenter=Segmenter(llm),          # ← รับ llm ไว้ตามโครง Agent แต่ไม่ได้ใช้ (ใช้ regex)
        classifier=Classifier(llm),
        matcher=Matcher(llm, get_retriever()),   # ← ตัวเดียวที่ต้องการของเพิ่มเป็นพิเศษ
        risk_scorer=RiskScorer(llm),
        judge=get_judge(),                 # ← judge ต้องใช้ known_positions ด้วย เลยแยกไปมี provider ของตัวเอง
    )
    # 📌 ใช้ keyword argument (segmenter=, classifier=) ไม่ใช่ positional
    #    เพราะทั้ง 5 ตัวเป็น "อะไรก็ไม่รู้ที่มี .run()" เหมือนกันหมด
    #    ถ้าเขียนเรียงเฉย ๆ แล้วสลับตำแหน่งผิด โค้ดจะยังรันได้แต่ผลลัพธ์เพี้ยนแบบหาสาเหตุยากมาก


@lru_cache
def get_review_service() -> ReviewService:
    return ReviewService(
        get_orchestrator(),
        get_contract_repo(),
        get_report_repo(),
        retention_ttl_seconds=get_settings().retention_ttl_seconds,
    )
    # ❓ ทำไมต้องมีไฟล์ "ประกอบร่าง" แยกแบบนี้ ให้ ReviewService สร้างของเองข้างในไม่ได้เหรอ?
    #   ถ้า ReviewService.__init__ เขียนว่า self.orchestrator = Orchestrator(...) เอง
    #   → เทสต์จะแทนที่มันไม่ได้เลย ต้องยิง Gemini จริงทุกครั้งที่รันเทสต์
    #   การรับของเข้ามาทาง __init__ (constructor injection) ทำให้เทสต์ยัดของปลอมเข้าไปได้:
    #       ReviewService(_FakeOrchestrator(), InMemoryContractRepository(), reports)
    #                                          ← tests/integration/test_contracts.py:109
    #   ผลลัพธ์: เทสต์ทั้งชุด 52 ตัวจบใน ~1.7 วินาที โดยไม่แตะ Gemini/Redis/Postgres จริงเลย


# ── ตัวเดียวในไฟล์ที่ "ห้าม" ใส่ @lru_cache ────────────────────────────────────
def get_override_service(db: Session = Depends(get_db)) -> OverrideService:
    """Return an override service bound to a request-scoped DB session."""
    return OverrideService(get_report_repo(), AuditRepository(db))
    #                      ↑ singleton (Redis)  ↑ ผูกกับ session ของ request นี้
    #
    # ❌ ถ้าเผลอใส่ @lru_cache ให้ฟังก์ชันนี้จะเกิดอะไร?
    #    request แรก: สร้าง OverrideService ที่ถือ session #1 → cache ไว้
    #    จบ request:  get_db() ทำ finally: db.close() → session #1 ตายแล้ว
    #    request ที่ 2: lru_cache คืนตัวเดิม → ใช้ session ที่ปิดไปแล้ว
    #                   → sqlalchemy.exc.ResourceClosedError หรือแย่กว่านั้นคือข้อมูลค้างจาก request ก่อน
    #
    # 📌 กฎจำง่าย: @lru_cache ได้เฉพาะของที่ "ไม่รู้จัก request" เท่านั้น
```

---

## [5] Service — `app/services/review.py`

```python
def review_upload(self, *, filename: str, data: bytes, session_id: str) -> ContractReviewReport:
    #                    ↑ ❓ เครื่องหมาย * โดด ๆ ตรงนี้คืออะไร?
    #                      = "ทุกพารามิเตอร์หลังจากนี้ต้องเรียกด้วยชื่อเท่านั้น" (keyword-only)
    #                      เรียก review_upload("a.pdf", data, "u1") → TypeError ทันที
    #                      ต้องเขียน review_upload(filename="a.pdf", data=..., session_id="u1")
    #                      ทำไมต้องบังคับ? เพราะพารามิเตอร์ 2 ตัวเป็น str เหมือนกัน
    #                      สลับ filename กับ session_id แล้วโค้ดยังรันได้ แต่ข้อมูลปนกันข้าม user
    """Parse an uploaded file and produce a stored review report."""

    self.reports.purge_expired(session_id, self.retention_ttl_seconds)
    # ↑ ❓ Redis มี TTL ในตัวอยู่แล้ว ทำไมยังต้องกวาดเอง?
    #   เพราะ service ตัวนี้ไม่รู้ว่าเบื้องหลังเป็น Redis หรือ dict:
    #     - RedisReportRepository  → เมธอดนี้เป็น no-op (Redis ลบเองด้วย TTL)
    #     - InMemoryReportRepository (ใช้ในเทสต์) → ไม่มีกลไกหมดอายุ ต้องมีคนสั่งกวาด
    #   service จึงเรียก "เสมอ" แล้วปล่อยให้แต่ละ repo ตัดสินใจเองว่าจะทำอะไร
    #   นี่คือราคาที่ยอมจ่ายเพื่อให้ service ไม่ผูกกับ storage ตัวใดตัวหนึ่ง

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    # ↑ rsplit(".", 1) = ตัดจากขวา 1 ครั้ง → "my.contract.final.pdf" ได้ ["my.contract.final", "pdf"]
    #   ถ้าใช้ split(".") ธรรมดาแล้ว [-1] ก็ได้ผลเดียวกัน แต่ rsplit เสียงานน้อยกว่าเพราะหยุดที่จุดแรกจากขวา
    #   .lower() → รับ "CONTRACT.PDF" ได้ด้วย
    #   if "." in filename → กันไฟล์ที่ไม่มีนามสกุลเลย (ไม่งั้นได้ทั้งชื่อไฟล์มาเป็น ext)

    parser = PARSERS.get(ext)
    # ↑ PARSERS = {"pdf": parse_pdf, "docx": parse_docx}  ← dict ที่ map นามสกุล → ฟังก์ชัน
    #   ❓ ทำไมใช้ dict ไม่ใช้ if/elif?
    #     1. เพิ่มไฟล์ประเภทใหม่ = เพิ่ม 1 บรรทัดใน dict ไม่ต้องแตะ service เลย
    #     2. .get() คืน None เมื่อไม่รู้จัก = ได้ด่านกรองไฟล์แปลกปลอมมาฟรี ๆ
    #        ไฟล์ .exe หรือ .zip ไม่มีทางหลุดไปถึง parser ได้เลย (allowlist ไม่ใช่ blocklist)

    if parser is None:
        raise DocumentParseError(f"unsupported file type: .{ext or 'unknown'}")
        # ↑ ❓ ทำไมไม่ raise HTTPException(422) ไปเลยให้จบ?
        #   เพราะกฎของโปรเจกต์: services/ ห้ามรู้จัก HTTP
        #   ถ้า service โยน HTTPException วันที่เอา service นี้ไปใช้ใน CLI หรือ cron job
        #   จะมี exception ของเว็บโผล่มาในที่ที่ไม่มีเว็บ ซึ่งไม่มีความหมายเลย
        #   DomainError พก status_code=422 ติดตัวมาเอง แล้วให้ errors.py แปลงเป็น HTTP ทีเดียว
        #
        #   `ext or 'unknown'` → ถ้า ext เป็น "" (falsy) ใช้คำว่า unknown แทน
        #   เพื่อไม่ให้ผู้ใช้เห็นข้อความประหลาดว่า "unsupported file type: ."

    try:
        document = parser(data)   # ← เรียกฟังก์ชันที่ได้จาก dict (parse_pdf หรือ parse_docx)
    except Exception as exc:  # noqa: BLE001 - surfaced to the client as 422
        # ↑ จับกว้างโดยตั้งใจ: PyMuPDF/python-docx โยน exception คนละแบบกันเมื่อไฟล์เสีย
        #   และเราไม่อยากต้องไล่ตามว่า library เวอร์ชันใหม่เพิ่ม exception อะไรมาอีก
        #   # noqa: BLE001 = ปิดคำเตือนของ ruff พร้อมเหตุผลกำกับ (ไม่ใช่ปิดเงียบ ๆ)
        raise DocumentParseError(f"failed to parse {filename}: {exc}") from exc
        # ↑ แปลง exception ของ library → ภาษาที่ระบบเราเข้าใจ พร้อมพก error เดิมไว้ใน traceback

    contract_id = uuid.uuid4().hex
    # ↑ uuid4 = สุ่มล้วน ๆ (ไม่อิงเวลา/MAC address) เดาไม่ได้
    #   .hex = ได้ "a3f2..." 32 ตัวอักษร แทน "a3f2-..." ที่มีขีด → เอาไปทำ Redis key ง่ายกว่า
    #   ❓ ทำไมไม่ใช้เลขรันนิ่ง 1, 2, 3? เพราะเดา id ของคนอื่นได้ทันที

    self.contracts.save(contract_id, document)
    try:
        report = self.orchestrator.review(document, contract_id=contract_id, session_id=session_id)
    finally:
        # Raw contract text isn't retained beyond producing the report.
        self.contracts.delete(contract_id)
        # ↑ ❓ ทำไมต้องอยู่ใน finally ไม่เขียนต่อจากบรรทัดบนเฉย ๆ?
        #   เพราะบรรทัดนี้ไม่ใช่ "การเก็บกวาด" แต่เป็น "นโยบายความเป็นส่วนตัว":
        #   ข้อความสัญญาดิบต้องหายทันทีที่ไม่จำเป็นแล้ว ไม่ว่าจะเกิดอะไรขึ้น
        #   ถ้าเขียนไว้นอก finally แล้ว pipeline โยน exception (เช่น Gemini ล่ม)
        #   → เนื้อหาสัญญาของลูกค้าจะค้างอยู่ใน Redis อีก 8 ชั่วโมงเต็มโดยไม่มีใครรู้
        #   finally การันตีว่ารันทุกเส้นทาง: สำเร็จ / error / แม้แต่ return กลางคัน

    self.reports.save(report)   # ← เก็บเฉพาะ "ผลวิเคราะห์" ไม่ใช่ตัวสัญญา
    return report
```

---

## [6] Parser — `app/parsers.py`

```python
def parse_pdf(data: bytes) -> ParsedDocument:
    """Parse PDF bytes into a :class:`ParsedDocument`, preserving page offsets."""
    import fitz  # PyMuPDF
    # ↑ ❓ ทำไม import อยู่ "ข้างในฟังก์ชัน" ทั้งที่ PEP 8 บอกให้ไว้บนหัวไฟล์?
    #   PyMuPDF เป็น C extension ขนาดใหญ่ โหลดช้า ได้ประโยชน์ 3 ข้อจากการ import ตรงนี้:
    #     1. คนที่อัปโหลดแต่ .docx ไม่ต้องโหลด PDF engine เลยตลอดอายุ process
    #     2. แอป boot เร็วขึ้น
    #     3. เทสต์ที่ไม่แตะ PDF รันได้แม้เครื่องนั้นไม่ได้ลง PyMuPDF
    #   (หลักการเดียวกันใช้กับ google.genai ใน ai/llm.py และ rank_bm25 ใน ai/retrieval.py)
    #   ⚠️ แลกกับ: ถ้า library หาย จะรู้ตอนมีคนอัปโหลด PDF ไม่ใช่ตอน boot

    doc = fitz.open(stream=data, filetype="pdf")
    #              ↑ stream= คือรับจาก bytes ในหน่วยความจำ ไม่ต้องเขียนไฟล์ลงดิสก์ก่อน
    #                (สำคัญ: ไฟล์สัญญาไม่ควรไปนอนอยู่บนดิสก์ของ server โดยไม่จำเป็น)
    #                filetype= ต้องระบุเพราะไม่มีนามสกุลไฟล์ให้มันเดา
    try:
        raw_pages = [page.get_text() for page in doc]   # ← ดึงข้อความทีละหน้า เก็บใส่ list
    finally:
        doc.close()
        # ↑ ต้องปิดเสมอ เพราะ fitz ถือ buffer ของ C ไว้ ซึ่ง garbage collector ของ Python
        #   จัดการให้ไม่ทันที → ไฟล์ใหญ่ ๆ หลายอันพร้อมกันทำ memory บวมได้

    # ── ประกอบข้อความทุกหน้าเป็นสตริงเดียว พร้อมจำว่าหน้าไหนอยู่ช่วงไหน ──
    text_parts: list[str] = []                 # ← สะสมชิ้นส่วนไว้ก่อน แล้วค่อย join ทีเดียว
    #                                             (ห้ามใช้ text += เพราะ str ใน Python แก้ไม่ได้
    #                                              การ += ทุกครั้ง = คัดลอกสตริงทั้งก้อนใหม่ → O(n²))
    spans: list[TextSpan] = []
    page_map: dict[int, tuple[int, int]] = {}  # ← {เลขหน้า: (ตำแหน่งเริ่ม, ตำแหน่งจบ)}
    offset = 0                                 # ← ตัวนับว่าตอนนี้เขียนไปถึงตัวอักษรที่เท่าไหร่แล้ว

    for page_number, raw_text in enumerate(raw_pages, start=1):
        #                                              ↑ เริ่มนับที่ 1 ไม่ใช่ 0 เพราะ "หน้า 1"
        #                                                คือสิ่งที่มนุษย์เข้าใจเวลาเปิดเอกสารดู
        page_text = normalize(raw_text)   # ← ยุบช่องว่าง + แปลง ligature (อธิบายด้านล่าง)
        if not page_text:
            continue                      # ← หน้าว่าง (เช่น หน้าที่มีแต่รูป) ข้ามไป ไม่นับ offset

        if text_parts:                    # ← ถ้าไม่ใช่หน้าแรก ให้คั่นด้วยบรรทัดว่าง
            text_parts.append("\n\n")
            offset += 2                   # ← 🔑 ต้องบวก 2 ด้วย! เพราะ "\n\n" ยาว 2 ตัวอักษร
            #                                ลืมบรรทัดนี้ = offset ของทุกหน้าถัดไปเพี้ยนหมด
            #                                → clause ชี้ไปผิดตำแหน่ง → citation ตรวจไม่ผ่าน

        start = offset
        text_parts.append(page_text)
        offset += len(page_text)          # ← เลื่อนตัวนับไปเท่าความยาวข้อความหน้านี้

        spans.append(TextSpan(start=start, end=offset, page=page_number))
        page_map[page_number] = (start, offset)

    return ParsedDocument(text="".join(text_parts), spans=spans, page_map=page_map)
    #                          ↑ join ทีเดียวตอนจบ = เร็วกว่าการต่อสตริงทีละครั้งมาก


# ❓ คำถามใหญ่: ทำไมต้องนั่งนับ offset ให้ยุ่งยาก ในเมื่อ LLM อ่านข้อความเปล่า ๆ ก็ได้?
#   เพราะ offset คือ "รากฐานของคำว่า grounded" ทั้งระบบ
#   ทุก clause ที่ pipeline ผลิตออกมาจะพก Span(start, end, page) ที่ชี้กลับไปต้นฉบับได้
#   → พิสูจน์ได้ว่าข้อความที่โมเดลอ้างถึง "มีอยู่จริงในเอกสาร" ไม่ใช่เชื่อคำโมเดลลอย ๆ
#   ถ้าไม่มีส่วนนี้ ระบบจะเหลือแค่ "เอาสัญญาไปถาม AI" ที่ตรวจสอบอะไรไม่ได้เลย


# ── ทำไม normalize ต้องแปลง ligature ──────────────────────────────────────────
_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff"}

def replace_ligatures(text: str) -> str:
    for lig, repl in _LIGATURES.items():
        text = text.replace(lig, repl)
    return text
# ↑ PDF จำนวนมากฝัง "อักขระควบ" มาแทนตัวอักษรปกติ — ตาเรามองเห็นเป็น "fi" เหมือนกันเป๊ะ
#   แต่คอมพิวเตอร์เห็นเป็นคนละ Unicode code point กันคนละตัว
#   ถ้าไม่แปลง: คำว่า "conﬁdential" ในสัญญา จะไม่ match กับ "confidential" ใน playbook
#   → guardrail is_grounded() ตีตก citation ที่จริง ๆ แล้วถูกต้อง
#   นี่คือบั๊กประเภทที่หาต้นตอยากมากถ้าไม่รู้ว่ามีจุดนี้อยู่ (เพราะ log พิมพ์ออกมาก็ดูเหมือนกัน)


# ── โครงสร้างข้อมูลที่ใช้: ทำไมเป็น dataclass ไม่ใช่ pydantic ─────────────────
@dataclass
class ParsedDocument:
    text: str
    spans: list[TextSpan] = field(default_factory=list)
    #                             ↑ ❓ ทำไมต้อง field(default_factory=list) ไม่เขียน = [] เฉย ๆ?
    #                               เพราะ = [] จะสร้าง list "ก้อนเดียว" แชร์กันทุก instance!
    #                               (บั๊กคลาสสิกของ Python: mutable default argument)
    #                               a = ParsedDocument("x"); a.spans.append(1)
    #                               b = ParsedDocument("y"); print(b.spans)  # → [1] ทั้งที่ไม่ได้ใส่
    #                               default_factory=list = เรียก list() ใหม่ทุกครั้งที่สร้าง object
    page_map: dict[int, tuple[int, int]] = field(default_factory=dict)

    def page_for_offset(self, offset: int) -> int | None:
        """Return the page number containing ``offset`` in ``text``."""
        for page, (start, end) in self.page_map.items():
            if start <= offset < end:   # ← ใช้ < ที่ปลาย ไม่ใช่ <= กัน offset สุดท้าย
                return page             #   ถูกนับซ้ำเป็นของสองหน้าพร้อมกัน
        return None
# ↑ ❓ ทำไมใช้ @dataclass ไม่ใช่ pydantic BaseModel เหมือนใน schemas.py?
#   กฎของโปรเจกต์: ข้อมูลจากภายนอกที่เชื่อไม่ได้ → pydantic / ข้อมูลภายในระบบ → dataclass
#   ParsedDocument ถูกสร้างโดยโค้ดของเราเองเท่านั้น ไม่เคยรับค่าจากผู้ใช้หรือ LLM ตรง ๆ
#   จึงไม่ต้องจ่ายค่า validation ทุกครั้งที่สร้าง object (ซึ่งเกิดขึ้นทุกการอัปโหลด)
```

---

## [7] Segmenter — `app/ai/agents.py` (ขั้นที่**ไม่**ใช้ LLM)

```python
from abc import ABC, abstractmethod
# ↑ ABC = Abstract Base Class — คลาสที่ "สร้าง object ตรง ๆ ไม่ได้ ต้องสืบทอดไปก่อน"
#   คู่กับ @abstractmethod = บังคับว่าคลาสลูกต้อง implement เมธอดนี้
#   ❓ ได้อะไร? ถ้าเขียนคลาส agent ใหม่แล้วลืมใส่ run() → Python error ตั้งแต่ตอนสร้าง object
#     ไม่ใช่ปล่อยให้ไป AttributeError กลาง pipeline ตอนรันจริง (ซึ่งอาจเป็นตอน deploy แล้ว)


class Agent[InputT, OutputT](ABC):
    #        ↑ generic syntax ของ Python 3.12+ (สมัยก่อนต้องประกาศ TypeVar แยกไว้ข้างบน)
    #          อ่านว่า: "Agent รับ input ชนิดหนึ่ง คืน output อีกชนิดหนึ่ง แล้วแต่คลาสลูกจะระบุ"
    #          ประโยชน์: editor รู้ว่า Segmenter.run() คืน list[Clause]
    #                    ส่วน Classifier.run() คืน ClauseType → ต่อ pipeline ผิดขั้นเห็นทันทีตอนพิมพ์
    """Base class for pipeline agents."""

    name: str = "agent"
    prompt_version: str = "v1"   # ← ตั้งใจไว้ให้ผูกผลลัพธ์กับเวอร์ชัน prompt
    #                               ⚠️ ตอนนี้ยังไม่มีใครอ่านค่านี้ไปบันทึกจริง (ดูข้อควรระวังท้ายบท)

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    @abstractmethod
    def run(self, payload: InputT) -> OutputT:
        """Execute the agent for a single unit of work."""
        raise NotImplementedError
        # ↑ @abstractmethod กันไว้ชั้นแรกแล้ว บรรทัดนี้เป็นชั้นที่สอง
        #   เผื่อกรณีที่คลาสลูกเรียก super().run() โดยไม่ตั้งใจ


class Segmenter(Agent[ParsedDocument, list[Clause]]):
    #                  ↑ input          ↑ output — ระบุชนิดจริงตรงนี้
    """Splits a parsed document into individual clauses."""

    name = "segmenter"

    def run(self, payload: ParsedDocument) -> list[Clause]:
        """Return the clauses found in ``payload``."""
        boundaries = self._heading_boundaries(payload.text)
        # ↑ หาว่า "หัวข้อ" แต่ละอันเริ่มที่ตัวอักษรตำแหน่งไหน เช่น [(0, "1. Term"), (420, "2. Payment")]

        if not boundaries:
            return self._paragraph_fallback(payload)
            # ↑ ❓ ทำไมต้องมีแผนสำรอง?
            #   สัญญาที่ไม่มีหัวข้อเลขกำกับมีอยู่จริง (เช่น จดหมายข้อตกลง)
            #   ถ้าไม่มี fallback ผู้ใช้จะได้ report ว่างเปล่าโดยไม่มีคำอธิบายว่าเกิดอะไรขึ้น
            #   ตัดตามบรรทัดว่างให้ผลหยาบกว่า แต่ยังใช้งานได้จริงและยัง verify ได้เหมือนเดิม

        return self._clauses_from_boundaries(payload, boundaries)

    @staticmethod
    def _heading_boundaries(text: str) -> list[tuple[int, str]]:
        #  ↑ @staticmethod = ไม่ต้องใช้ self เลย (ไม่แตะ state ของ object)
        #    บอกคนอ่านว่า "ฟังก์ชันนี้คำนวณล้วน ๆ ไม่มีผลข้างเคียง" และเทสต์แยกได้ง่าย
        boundaries: list[tuple[int, str]] = []
        offset = 0
        for line in text.split("\n"):
            if is_heading(line):                       # ← ใช้ regex ตัวเดียวกับที่ parsers.py ใช้
                boundaries.append((offset, line.strip()))
            offset += len(line) + 1                    # ← +1 คือตัว "\n" ที่ split กินไป
            #                                             🔑 ลืม +1 = ตำแหน่งเพี้ยนสะสมทีละบรรทัด
        return boundaries


# ❓❓ คำถามที่สำคัญที่สุดของขั้นนี้: ทำไมขั้นตอนแรกของ "AI pipeline" ถึงไม่ใช้ AI เลย?
#
#   สมมติให้ LLM ทำหน้าที่นี้แทน มันจะต้องตอบประมาณว่า
#       "clause ที่ 3 อยู่ช่วงตัวอักษรที่ 1200 ถึง 1850"
#   ปัญหาคือโมเดล "นับตัวอักษรไม่เป็น" มันเดาตัวเลขจากความรู้สึก → คลาดเคลื่อนแทบทุกครั้ง
#   พอ span ผิด → ข้อความที่ตัดออกมาผิด → citation อ้างผิด → guardrail ตีตกทั้งหมดอยู่ดี
#   สรุป: จ่ายเงินค่า token เพื่อให้ได้ผลที่แย่กว่า
#
#   regex ให้ offset ที่ถูกต้อง 100% ฟรี และเร็วกว่าเป็นพันเท่า
#   📌 หลักการที่ใช้ทั้งโปรเจกต์: ใช้ LLM เฉพาะงานที่ "ต้องเข้าใจความหมาย" เท่านั้น
#      (จำแนกประเภท / ประเมินความเสี่ยง)  ส่วนงานที่โค้ดทำได้แน่นอนกว่า ให้โค้ดทำ
#
# ❓ แล้วทำไมยังต้องสืบทอด Agent ทั้งที่ไม่เคยแตะ self.llm เลย?
#   เพื่อให้ Orchestrator เรียกทุกขั้นด้วยรูปแบบเดียวกัน (.run(payload))
#   โดยไม่ต้องรู้ว่าขั้นไหนใช้ LLM ขั้นไหนไม่ใช้
#   → วันที่อยากเปลี่ยน Segmenter ไปใช้ LLM (หรือกลับกัน) Orchestrator ไม่ต้องแก้สักบรรทัด
```

---

## [8] LLM client — `app/ai/llm.py`

> 📌 **อัปเดต 2026-07-28:** โค้ดที่ยกมาอธิบายด้านล่างนี้ (การสร้าง `google.genai.Client`, การ
> map `usage_metadata`, การเรียก `response_schema`) ย้ายไป `app/ai/providers.py` แล้ว เพราะตอนนี้
> รองรับหลายค่าย — `LLMClient` เหลือแค่ facade ที่เลือก backend ตาม `LLM_PROVIDER` แล้วสะสม `Usage`
> **หลักการทุกข้อที่อธิบายไว้ยังใช้ได้เหมือนเดิม** (lazy client, timeout เป็น ms เฉพาะฝั่ง Gemini,
> ทางสำรองตอน `parsed` เป็น `None`) แค่ย้ายไปอยู่ในไฟล์ adapter ของแต่ละค่าย
>
> 📌 **อัปเดต 2026-07-30:** `complete`/`complete_structured` ไม่เรียก backend ตรง ๆ อีกแล้ว —
> ทั้งคู่ผ่าน `LLMClient._call()` ที่ยิงซ้ำให้เมื่อ failure เป็นชนิดที่ถามใหม่แล้วมีโอกาสได้
> (`providers.is_transient`) และสะสม `Usage` เฉพาะครั้งที่ได้คำตอบ ส่วน "ทางสำรองตอน `parsed`
> เป็น `None`" ที่อธิบายไว้ด้านล่างยังอยู่ แต่ถ้าคำตอบว่างเปล่าจริง ๆ ตอนนี้จะโยน
> `EmptyCompletionError` ที่บอกว่า **หมดงบ token ไปกับการคิด** แทนที่จะให้ pydantic ฟ้อง
> `EOF while parsing a value` ซึ่งชี้ไปที่ schema ทั้งที่ต้นเหตุอยู่ที่ `LLM_THINKING`

```python
# ── ส่วนที่ 1: โหลด prompt จากไฟล์ ────────────────────────────────────────────
from jinja2 import Environment, FileSystemLoader, select_autoescape

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "prompts"),
    #                       ↑ __file__ = พาธของไฟล์ llm.py เอง
    #                         .parent / "prompts" = โฟลเดอร์ prompts ที่อยู่ข้าง ๆ กัน
    #                         ❓ ทำไมไม่เขียน "app/ai/prompts" ตรง ๆ?
    #                           เพราะพาธแบบนั้นอิงกับ "โฟลเดอร์ที่รันคำสั่ง" (cwd)
    #                           รันจาก repo root ได้ แต่รันจากที่อื่นจะหาไฟล์ไม่เจอ
    #                           วิธีนี้อิงตำแหน่งไฟล์จริง → รันจากไหนก็ถูกเสมอ

    autoescape=select_autoescape(disabled_extensions=("jinja",), default=False),
    # ↑ 🔑 ปิด HTML escaping "โดยตั้งใจ" — ตรงข้ามกับที่ทำในเว็บทั่วไป
    #   ปกติ Jinja มีไว้ทำ HTML จึงแปลง " < & ให้เป็น &quot; &lt; &amp; เพื่อกัน XSS
    #   แต่เรากำลังสร้าง "ข้อความ prompt" ส่งให้ LLM ไม่ใช่หน้าเว็บ
    #   ถ้าเปิดไว้: ข้อความสัญญาที่มีเครื่องหมายคำพูดจะกลายเป็น &quot; ในสายตาโมเดล
    #   → โมเดลคัดลอก excerpt ออกมาผิดเพี้ยน → grounding check ตีตกทุกอัน

    trim_blocks=True,      # ← ตัด newline หลังแท็ก {% ... %} ทิ้ง
    lstrip_blocks=True,    # ← ตัดช่องว่างหน้าแท็ก {% ... %} ทิ้ง
    # ↑ สองตัวนี้ทำให้ prompt ที่ออกมาไม่มีบรรทัดว่างเกะกะจากการจัดย่อหน้าในไฟล์ template
    #   สำคัญกว่าที่คิด: บรรทัดว่างเกินใน prompt ทำให้โมเดลตีความโครงสร้างเพี้ยนได้
)


# ── ส่วนที่ 2: เรียก LLM แบบบังคับรูปแบบผลลัพธ์ ────────────────────────────────
def complete_structured[T: BaseModel](
    #                    ↑ อ่านว่า "T คืออะไรก็ได้ ที่สืบทอดมาจาก BaseModel"
    #                      ทำให้ editor รู้ว่า complete_structured(response_model=_LLMVerdict)
    #                      คืนค่าเป็น _LLMVerdict (ไม่ใช่ BaseModel กว้าง ๆ) → มี autocomplete ครบ
    self, *, system: str, prompt: str, response_model: type[T], max_tokens: int = 4096
    #      ↑ keyword-only ทั้งหมด เพราะ system กับ prompt เป็น str เหมือนกัน สลับกันแล้วไม่มีใครรู้
    #                                   ↑ type[T] = "ตัวคลาสเอง" ไม่ใช่ instance
    #                                     ส่ง _LLMVerdict (คลาส) ไม่ใช่ _LLMVerdict() (object)
) -> T:
    """Return a validated ``response_model`` instance from the LLM."""
    from google.genai import types   # ← lazy import (เหตุผลเดียวกับ fitz)

    response = self._get_client().models.generate_content(
        model=self.model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            # ↑ แยก system ออกจาก prompt เพราะโมเดลให้น้ำหนักกับ system สูงกว่า
            #   ใช้บอก "บทบาท" (เช่น "You are a strict grounding verification judge")

            max_output_tokens=max_tokens,
            # ↑ เพดานความยาวคำตอบ — กันโมเดลร่ายยาวจนค่า token บานปลาย

            response_mime_type="application/json",
            response_schema=response_model,
            # ↑ 🔑 หัวใจของ "structured output": ส่งคลาส pydantic เข้าไปเป็น schema เลย
            #   SDK แปลงเป็น JSON Schema แล้วบังคับให้โมเดลตอบตามรูปนั้น
            #   ❓ ต่างจากการเขียนใน prompt ว่า "ตอบเป็น JSON นะ" ยังไง?
            #     การขอใน prompt = โมเดล "พยายาม" ทำตาม แต่บางครั้งใส่ ```json ครอบ
            #     หรือเติมคำอธิบายนำหน้า → json.loads() พัง
            #     response_schema = บังคับที่ระดับ decoding เลย ได้ JSON สะอาดเสมอ
        ),
    )

    self._record_usage(response)
    # ↑ สะสมจำนวน token ที่ใช้ไว้ใน self.usage สำหรับติดตามค่าใช้จ่าย
    #   ⚠️ ตอนนี้ยังไม่มีใครอ่านค่านี้ไปแสดงหรือ log (ดูข้อควรระวังท้ายบท)

    parsed = response.parsed
    if isinstance(parsed, response_model):
        return parsed                                    # ← ทางปกติ: SDK แปลงให้เรียบร้อยแล้ว
    return response_model.model_validate_json(response.text)   # ← ทางสำรอง: แปลงเองจาก text
    # ↑ ❓ ในเมื่อบังคับ schema ไปแล้ว ทำไมยังต้องมีทางสำรองอีก?
    #   เพราะ response.parsed เป็น None ได้ในบางกรณี (SDK บางเวอร์ชัน / คำตอบถูกตัดกลางคัน)
    #   ถ้าไม่ดักไว้แล้ว return None ออกไป → โค้ดข้างนอกจะไปพังที่
    #   "AttributeError: 'NoneType' has no attribute 'risk_level'" ซึ่งไกลจากต้นตอมาก
    #   📌 หลักการ: ตรวจให้พังใกล้ ๆ จุดที่ผิดจริง อย่าปล่อยให้ค่าพิการไหลลึกเข้าไปในระบบ


# ── ส่วนที่ 3: lazy client + timeout ──────────────────────────────────────────
def __init__(self, model: str | None = None, timeout_seconds: int | None = None) -> None:
    settings = get_settings()
    self.model = model or settings.llm_model
    #            ↑ รับค่ามาแทนได้ (เทสต์ใช้) แต่ถ้าไม่ส่งก็ใช้ค่าจาก .env
    self._client = None   # ← ยังไม่สร้าง client ตรงนี้!

def _get_client(self):
    """Lazily construct the underlying ``google.genai.Client``."""
    if self._client is None:
        from google import genai
        from google.genai import types

        self._client = genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(timeout=self._timeout_seconds * 1000),
            #                                                            ↑ 🔑 อย่าลืม!
            # SDK รับหน่วยเป็น "มิลลิวินาที" แต่ config ของเราเก็บเป็น "วินาที" (คนอ่านง่ายกว่า)
            # ผิดพลาด 1000 เท่าตรงนี้จะ "ยังทำงานได้" แค่ไร้ประโยชน์:
            #   ลืมคูณ → timeout 120 ms = ทุก request ตายหมด (เห็นทันที ยังดี)
            #   คูณเกิน → timeout 33 ชั่วโมง = เหมือนไม่มี timeout (ไม่มีใครรู้จนกว่าจะมี call ค้าง)
            # จึงมีเทสต์ tests/unit/test_timeouts.py ตรึงการแปลงหน่วยนี้ไว้โดยเฉพาะ
            #
            # และตั้งที่ "ตัว client" ไม่ใช่ราย call → ครอบทุกการเรียกผ่าน client นี้อัตโนมัติ
            # รวมถึง complete_structured ด้วย ไม่มีทางลืมใส่บางจุด
        )
    return self._client
    # ❓ ทำไมต้อง lazy (สร้างตอนใช้ครั้งแรก) ไม่สร้างใน __init__ ไปเลย?
    #   เพราะ get_llm_client() ถูกเรียกตอนประกอบ dependency graph ซึ่งเกิดขึ้น "ทุกครั้ง"
    #   ที่สร้าง app — รวมถึงในเทสต์ที่ไม่ยิง LLM เลยสักครั้ง
    #   ถ้าสร้าง client ทันทีใน __init__ เทสต์ทุกตัวจะพังทันทีถ้าเครื่องนั้นไม่มี GEMINI_API_KEY
    #   lazy = จ่ายราคาเมื่อใช้จริงเท่านั้น


# ❓ ภาพรวม: ทำไมต้องมี LLMClient ห่อ SDK อีกชั้น แทนที่จะเรียก genai ตรง ๆ ในแต่ละ agent?
#   เพราะมีเรื่องที่ต้องตั้งให้ "เหมือนกันทุกที่" อยู่หลายอย่าง: โมเดล, timeout, api key, การนับ token
#   ถ้า agent 4 ตัวเรียก SDK เอง = ต้องตั้งค่าซ้ำ 4 จุด และวันที่แก้จะลืมสักจุดเสมอ
#   📌 เคยเกิดขึ้นจริงในโปรเจกต์นี้: commit 9c12e40 แก้บั๊กที่ docstring เขียนว่ามี timeout
#      แต่ไม่เคยมีใครส่งค่า timeout เข้า SDK เลยแม้แต่ครั้งเดียว
```

---

## [9] Retrieval แบบ hybrid — `app/ai/retrieval.py`

```python
from typing import Protocol
# ↑ ใช้ประกาศ "interface แบบไม่ต้องสืบทอด" (ดูคอนเซปต์ข้อ 6)

from sqlalchemy.dialects.postgresql import insert
# ↑ 🔑 สังเกตว่า "ไม่ใช่" from sqlalchemy import insert ตัวธรรมดา!
#   ต้องใช้ตัวเฉพาะของ PostgreSQL เพราะมีเมธอด .on_conflict_do_update() ให้ใช้
#   (= คำสั่ง INSERT ... ON CONFLICT DO UPDATE ซึ่งเป็นของ Postgres โดยเฉพาะ)
#   ทำให้ re-ingest playbook ซ้ำได้เลยโดยไม่ต้องลบของเก่าก่อน — มี id ซ้ำก็อัปเดตทับ
#   ถ้าใช้ insert ตัวธรรมดา: รัน ingest รอบสองจะ IntegrityError เพราะ primary key ชน

from app.models import PlaybookEmbedding
# ↑ ตาราง ORM ที่เก็บ playbook + เวกเตอร์ — ตัวคอลัมน์ vector ประกาศไว้ใน app/models.py:
#       from pgvector.sqlalchemy import Vector
#       embedding = Column(Vector(get_settings().embedding_dim), nullable=False)
#   pgvector.sqlalchemy สอนให้ SQLAlchemy รู้จัก column type "vector" ของ Postgres
#   และแถมเมธอด .cosine_distance() ที่แปลงเป็น operator <=> ให้ (ใช้ใน PgVectorStore.query)
#   ไม่มี library ตัวนี้ = ต้องเขียน raw SQL เองทุกครั้งที่ค้นด้วยเวกเตอร์
#   ⚠️ ความกว้างของ vector ต้องตรงกับ EMBEDDING_DIM และ migration — เปลี่ยนแล้วต้อง re-ingest

import hashlib
# ↑ ใช้ 2 งานในไฟล์นี้:
#   1. DummyEmbedder — แฮชข้อความเป็นเวกเตอร์ปลอม "ที่ได้ค่าเดิมทุกครั้ง"
#      → เทสต์ให้ผลเหมือนเดิมทุกรอบ (deterministic) ไม่ต้องต่อเน็ต ไม่เสียเงิน
#   2. make_citation — สร้าง citation_id จาก (position_id + excerpt)
#      → excerpt เดิมได้ id เดิมเสมอ ไม่ต้องเก็บตัวนับหรือ query DB เพื่อหา id ถัดไป


def retrieve(self, clause: Clause, top_k: int = 5) -> list[RetrievalHit]:
    """Return the top playbook positions for ``clause``."""
    settings = get_settings()

    (vector,) = self.embedder.embed([clause.text])
    # ↑ ❓ วงเล็บกับจุลภาคตรงนี้คืออะไร? — คือ "tuple unpacking"
    #   embed() รับ list คืน list (เผื่อ embed หลายข้อความทีเดียว) แต่เราส่งไปแค่ 1
    #   (vector,) = [...] แปลว่า "ฉันคาดว่าใน list มี 1 ตัวพอดี เอาตัวนั้นออกมา"
    #   ถ้าได้กลับมา 0 หรือ 2 ตัว → ValueError ทันที
    #   เทียบกับการเขียน vector = ...embed([...])[0] ซึ่งจะเงียบ ๆ ถ้าได้มาเกิน (ปิดบั๊กไว้)

    if not settings.enable_hybrid_retrieval:
        return self.store.query(vector, top_k=top_k)   # ← โหมด dense อย่างเดียว (ปิดผ่าน .env ได้)

    candidates = self.store.query(vector, top_k=max(top_k * 4, top_k))
    # ↑ 🔑 ดึงมา "เผื่อ" 4 เท่าก่อน แล้วค่อยตัดเหลือ top_k ตอนจบ
    #   ❓ ทำไมต้องเผื่อ? เพราะ BM25 จัดอันดับใหม่ได้เฉพาะของที่มีอยู่ในตะกร้าแล้วเท่านั้น
    #   ถ้าดึงมาแค่ 5 ตัวตั้งแต่แรก → position ที่ dense จัดไว้อันดับ 7
    #   (ทั้งที่ BM25 จะยกให้เป็นอันดับ 1 เพราะมีคำว่า "indemnify" ตรงเป๊ะ)
    #   จะไม่มีโอกาสถูกพิจารณาเลย → rerank ไม่มีความหมาย
    #   📌 หลักการ recall-then-rerank: เปิดตะกร้าให้กว้างก่อน แล้วค่อยคัดให้แม่น

    if not candidates:
        return []   # ← ไม่มีอะไรให้ rerank ก็จบ (กัน ZeroDivisionError ข้างล่างด้วย)

    bm25_scores = self._bm25_scores(clause.text, candidates)
    dense_scores = [hit.score for hit in candidates]

    max_dense = max(dense_scores) or 1.0
    max_bm25 = max(bm25_scores) or 1.0
    # ↑ `or 1.0` = ถ้าค่าสูงสุดเป็น 0 (falsy) ให้ใช้ 1.0 แทน → กันหารด้วยศูนย์
    #   ⚠️ ข้อจำกัดที่ยังไม่ได้แก้: ถ้า max ติดลบ (cosine distance > 1 เป็นไปได้)
    #      การหารด้วยค่าลบจะทำให้ลำดับ "กลับหัว" — ควรใช้ max(ค่า, 1e-9) แทน

    seen: set[str] = set()
    blended: list[RetrievalHit] = []
    for hit, dense, bm25 in zip(candidates, dense_scores, bm25_scores, strict=True):
        #                                                              ↑ 🔑 สำคัญมาก
        # zip ปกติจะ "หยุดเงียบ ๆ" ที่ list ที่สั้นที่สุด — ถ้า bm25_scores มี 3 ตัว
        # แต่ candidates มี 20 ตัว มันจะวนแค่ 3 รอบแล้วจบ โดยไม่มี error ใด ๆ
        # → ผลลัพธ์ "ดูปกติแต่ผิด" ซึ่งเป็นบั๊กประเภทที่หายากที่สุด
        # strict=True เปลี่ยนความยาวไม่เท่ากันให้เป็น ValueError ทันที

        if hit.position.id in seen:
            continue          # ← กัน position เดียวกันโผล่ซ้ำในผลลัพธ์
        seen.add(hit.position.id)

        score = 0.5 * (dense / max_dense) + 0.5 * (bm25 / max_bm25)
        # ↑ ❓ ทำไมต้องหารด้วยค่าสูงสุดก่อนบวก? — เพราะสองคะแนนอยู่คนละสเกล
        #   dense (cosine) ≈ 0–1 / BM25 ไม่มีขอบเขตบน อาจถึง 15–20 ได้สบาย ๆ
        #   ถ้าบวกกันดิบ ๆ: 0.87 + 15.2 → BM25 กลบ dense จนหมด
        #   "hybrid 50/50" จะกลายเป็น "BM25 ล้วน" โดยที่โค้ดยังดูเหมือนถูกต้อง
        #   หารด้วย max ก่อน = ดึงทั้งคู่มาอยู่ช่วง 0–1 → น้ำหนัก 0.5/0.5 จึงมีความหมายจริง

        blended.append(RetrievalHit(position=hit.position, score=score, source="hybrid"))

    blended.sort(key=lambda hit: hit.score, reverse=True)   # ← เรียงมากไปน้อย
    return blended[:top_k]                                   # ← ตัดเหลือเท่าที่ขอจริง


# ❓ ทำไมต้องผสม 2 วิธี ใช้ vector search อย่างเดียวไม่พอเหรอ?
#   เพราะสองวิธีนี้ "พลาดคนละแบบ" และในโดเมนสัญญาความพลาดของ dense เจ็บมาก:
#
#   dense (embedding)  เก่ง: เข้าใจความหมายใกล้เคียง
#                            "ห้ามเปิดเผยข้อมูลแก่บุคคลที่สาม" ↔ "confidentiality obligations"
#                      พลาด: คำเฉพาะทางที่รูปคำสำคัญ — มองว่า "indemnify" กับ "compensate"
#                            คล้ายกัน ทั้งที่ทางกฎหมายคนละเรื่องกันเลย
#
#   BM25 (นับคำ)       เก่ง: คำเฉพาะทางกฎหมายที่ต้องตรงตัว — "force majeure", "indemnify"
#                      พลาด: ไม่รู้จักคำพ้องความหมายเลย ถ้าใช้คนละคำก็หาไม่เจอ
#
#   → ผสมกันคือการอุดจุดบอดของกันและกัน
```

---

## [10] Risk scorer + [11] Judge/Guardrails — หัวใจของคำว่า "grounded"

```python
# app/ai/agents.py — RiskScorer.run() (ตัดเฉพาะส่วนสำคัญ)

class _RiskAssessment(BaseModel):
    #   ↑ ขึ้นต้นด้วย _ = รูปแบบภายในของ agent ตัวนี้เท่านั้น ไม่ใช่ DTO ที่ออกทาง HTTP
    risk_level: RiskLevel
    rationale: str
    citations: list[_CitedPoint] = Field(default_factory=list)
    suggested_fallback: str | None = None
# ↑ ❓ ทำไมตัวนี้ต้องเป็น pydantic ทั้งที่ Verdict/Usage ใช้ dataclass?
#   เพราะคลาสนี้รับข้อมูล "จาก LLM" ซึ่งต้องถือว่าเป็น input ที่เชื่อไม่ได้ เหมือน request จากผู้ใช้
#   โมเดลอาจตอบ field ไม่ครบ ผิดชนิด หรือใส่ risk_level ที่ไม่มีใน enum
#   pydantic จับได้ทันทีตรงจุดที่รับเข้า แทนที่จะปล่อยให้ไปพังลึก ๆ ทีหลัง

hits_by_id = {hit.position.id: hit for hit in payload.hits}
# ↑ แปลง list → dict เพื่อค้นด้วย id ได้ในเวลาคงที่ O(1)
#   ถ้าไม่ทำ ต้องวน list ทุกครั้งที่โมเดลอ้าง id มา (O(n) ต่อครั้ง)

assessment = self.llm.complete_structured(
    system=_SCORER_SYSTEM_PROMPT, prompt=prompt, response_model=_RiskAssessment
)

citations = [
    make_citation(hits_by_id[c.playbook_position_id], _clean_excerpt(c.excerpt))
    for c in assessment.citations
    if c.playbook_position_id in hits_by_id
    # ↑ 🔑 บรรทัดนี้คือด่านกัน hallucination ด่านแรก
    #   โมเดลอาจอ้าง id ที่ "ไม่เคยถูกส่งให้มันเลย" — แต่งขึ้นมาเองหน้าตาเหมือนของจริง
    #   ถ้าไม่กรอง: hits_by_id[...] จะโยน KeyError → clause นี้ตกไปทั้งอัน
    #   (แล้วไปโดน except Exception ของ Orchestrator จับ กลายเป็น unknown ทั้งข้อ)
    #   กรองทิ้งแทน = citation ปลอมหายไป แต่ผลประเมินส่วนที่เหลือยังใช้ได้
    #   และ judge จะเป็นคนตรวจอีกชั้นว่าที่เหลือถูกต้องจริงไหม
]
```

```python
# _clean_excerpt — ตัวแก้บั๊กที่เคยทำให้ระบบ "ดูเหมือนพัง" ทั้งระบบ
_LABEL_PREFIX_RE = re.compile(r"^\s*(preferred|fallback)\s*:\s*", re.IGNORECASE)
#                              ↑ ^ = ต้องอยู่ต้นข้อความเท่านั้น
#                                    (ไม่งั้นจะไปตัดคำว่า "fallback:" ที่อยู่กลางประโยคด้วย)
#                                     re.IGNORECASE = รับทั้ง "Preferred:" และ "preferred:"
_WRAPPING_QUOTES = "\"'“”‘’"   # ← รวมอัญประกาศโค้งแบบที่ Word/PDF ชอบใส่มาด้วย

def _clean_excerpt(text: str) -> str:
    """Strip a stray "Preferred:"/"Fallback:" label and wrapping quotes."""
    return _LABEL_PREFIX_RE.sub("", text).strip().strip(_WRAPPING_QUOTES).strip()
    #                                     ↑ ตัดช่องว่าง → ตัดอัญประกาศ → ตัดช่องว่างอีกรอบ
    #                                       (ต้องตัดช่องว่างซ้ำ เพราะข้างในอัญประกาศอาจมีช่องว่างอีก)

# ❓ ทำไมต้องมีฟังก์ชันนี้? — นี่คือบั๊กที่เคยเกิดจริงและหาสาเหตุยากมาก
#   prompt แสดง playbook ให้โมเดลดูในรูปแบบนี้:
#       Preferred: Each party shall indemnify the other...
#   แล้วโมเดล "คัดลอกคำว่า Preferred: ติดมาด้วย" ตอนอ้าง excerpt กลับมา
#   → is_grounded() เทียบแบบ substring แล้วไม่เจอ (เพราะต้นฉบับไม่มีคำว่า "Preferred:")
#   → citation ที่จริง ๆ แล้ว "ถูกต้องทุกอัน" ถูกตีตกเกือบหมด
#   → รายงานทุกใบขึ้น verified=False โดยที่ไม่มีอะไรผิดเลยจริง ๆ
#
#   📌 บทเรียนสำคัญ: แก้ที่ prompt อย่างเดียวไม่พอ ต้องแก้ที่โค้ดด้วย
#      เพราะ prompt คือ "การขอร้อง" ไม่ใช่ "การบังคับ" — โมเดลทำตามบ้างไม่ทำตามบ้าง
#      โค้ดที่ทำความสะอาดผลลัพธ์คือด่านที่ควบคุมได้จริง
```

```python
# app/ai/agents.py — Judge.run()
# 📌 อ่านโครงของฟังก์ชันนี้ให้ดี: มันเรียงจาก "ตรวจที่ถูกและแน่นอนที่สุด" ไป "แพงและไม่แน่นอนที่สุด"

known_ids = set(self.known_positions)
# ↑ dict ใส่ set() ได้ key ออกมาเป็น set — เขียนสั้นกว่า set(self.known_positions.keys())
#   แปลงเป็น set เพราะจะเช็ค "มีอยู่ไหม" หลายครั้ง → set เร็วกว่า list มาก (O(1) vs O(n))

# ── ด่านที่ 1: citation ชี้ไป position ที่มีอยู่จริงไหม (โค้ดล้วน ฟรี) ──
unknown = invalid_citations(payload, known_ids)
if unknown:
    return Verdict(grounded=False, reason=f"citation(s) reference unknown ...", should_retry=True)
    #                                                                            ↑ ให้ลองใหม่ได้
    #   เพราะเป็นความผิดพลาดแบบ "โมเดลพลาด" ไม่ใช่ "ข้อมูลไม่พอ" → ลองอีกครั้งอาจได้ผลถูก

# ── ด่านที่ 2: ข้อความที่ยกมาอ้าง มีอยู่ในต้นฉบับจริงไหม (โค้ดล้วน ฟรี) ──
for citation in payload.citations:
    position = self.known_positions[citation.playbook_position_id]
    # ↑ ตรงนี้ใช้ [] เข้าถึงตรง ๆ ได้อย่างปลอดภัย เพราะด่านที่ 1 กรอง id ปลอมออกไปหมดแล้ว

    source_text = f"{position.preferred_language} {position.fallback_language}"
    # ↑ รวมข้อความทั้งสองแบบเป็นก้อนเดียวก่อนค้น เพราะโมเดลอาจยกมาจากอันไหนก็ได้

    if not is_grounded(citation.excerpt, source_text):
        return Verdict(grounded=False, reason=f"excerpt ... not grounded", should_retry=True)

# ── ด่านที่ 3: ข้อความที่แนะนำให้แก้ เป็นของ playbook จริงไหม (โค้ดล้วน ฟรี) ──
if not is_allowed_fallback(payload.suggested_fallback, list(self.known_positions.values())):
    return Verdict(grounded=False, reason="suggested fallback does not match ...", should_retry=True)
# ↑ ❓ ทำไมด่านนี้ต้องเทียบ "ตรงตัวอักษร" (verbatim) ไม่ยอมให้ใกล้เคียง?
#   เพราะ "ข้อความที่แนะนำ" คือสิ่งที่ผู้ใช้จะคัดลอกไปใส่ในสัญญาจริง
#   ถ้าปล่อยให้โมเดลแต่งเอง = ระบบกำลังร่างเอกสารทางกฎหมายให้ผู้ใช้โดยไม่มีทนายตรวจ
#   กติกาจึงเป็น: แนะนำได้เฉพาะถ้อยคำที่ฝ่ายกฎหมายเขียนไว้ใน playbook แล้วเท่านั้น
#   คำเดียวที่ต่างไปในสัญญา อาจเปลี่ยนความรับผิดทั้งฉบับ

# ── ด่านที่ 4: ถึงตรงนี้ค่อยจ่ายเงินเรียก LLM ──
if not get_settings().enable_judge:
    return Verdict(grounded=True, reason="deterministic checks passed")
    # ↑ feature flag: ปิด LLM judge ได้ผ่าน .env แต่ 3 ด่านแรกยังทำงานอยู่เสมอ
    #   → ประหยัดเงิน/เวลาได้ตอน dev โดยไม่เสียการตรวจสอบส่วนที่สำคัญที่สุดไป

llm_verdict = self.llm.complete_structured(...)


# ❓❓ ทำไมต้องเรียง 4 ด่านแบบนี้? ทำไมไม่ถาม LLM ตั้งแต่แรกให้จบ ๆ?
#
#   1. ถูกกว่า — ถ้า citation ชี้ไป id ที่ไม่มีอยู่จริง เรารู้ได้ฟรีด้วยโค้ด 1 บรรทัด
#      ไม่ต้องจ่ายค่า token เพื่อให้โมเดลมาบอกสิ่งที่เรารู้อยู่แล้ว
#
#   2. แน่นอนกว่า — คำถามว่า "ข้อความนี้มีอยู่ในต้นฉบับไหม" ตอบด้วยการเทียบ string ได้ถูก 100%
#      การเอาคำถามแบบนี้ไปถาม LLM = เปลี่ยนคำตอบที่ "แน่นอน" ให้กลายเป็น "น่าจะถูก"
#      ซึ่งเป็นการถอยหลัง
#
#   3. LLM ถูกเก็บไว้ตอบเฉพาะสิ่งที่โค้ดตอบไม่ได้จริง ๆ — เช่น
#      "rationale พูดเกินกว่าที่ playbook รองรับหรือเปล่า" ซึ่งต้องเข้าใจภาษาถึงจะตอบได้
#
#   📌 หลักการนี้ใช้ได้กับทุกระบบที่มี LLM: เอาโค้ดกรองให้เหลือน้อยที่สุดก่อน
#      แล้วค่อยส่งเฉพาะส่วนที่เหลือให้โมเดลตัดสิน
```

---

## [12] ประกอบร่าง + เก็บผล — `Orchestrator` และ error mapping

```python
def _review_clause(self, clause: Clause) -> ClauseReview:
    """Run one clause through classify -> match -> score -> judge."""
    try:
        clause.clause_type = self.classifier.run(clause)
        # ↑ เขียนทับ field ของ clause เลย (ค่าเริ่มต้นคือ ClauseType.OTHER)
        #   เพราะขั้นถัดไปต้องใช้ clause_type ในการสร้าง prompt

        hits = self.matcher.run(clause)                                    # ← RAG: ค้น playbook
        review = self.risk_scorer.run(RiskScorerInput(clause=clause, hits=hits))
        #                             ↑ ห่อ 2 ค่าเป็น object เดียว เพราะ Agent.run() รับ payload ตัวเดียว
        #                               (ถ้าให้ run รับหลาย argument ได้ interface จะไม่เหมือนกันทุก agent)

        verdict = self.judge.run(review)                                   # ← ตรวจว่า grounded ไหม

        if not verdict.grounded and verdict.should_retry:
            review = self.risk_scorer.run(RiskScorerInput(clause=clause, hits=hits))
            verdict = self.judge.run(review)
            # ⚠️ จุดที่ยังไม่ดีพอ: retry ส่ง input "ชุดเดิมเป๊ะ" กลับเข้าไปใหม่
            #    ทั้งที่ verdict.reason บอกอยู่แล้วว่าพลาดตรงไหน แต่ไม่ได้เอาไปบอกโมเดล
            #    → โอกาสสูงที่จะได้คำตอบเดิม = จ่ายค่า token 2 เท่าโดยไม่ได้อะไร
            #    ควรส่ง verdict.reason เข้า prompt รอบสอง (ดูข้อควรระวังท้ายบท)

        review.verified = verdict.grounded
        # ↑ ❓ ทำไมแค่ติดป้าย ไม่โยนทิ้งไปเลยถ้าไม่ผ่าน?
        #   เพราะผลวิเคราะห์ที่ "ยังไม่ผ่านการตรวจสอบ" ยังมีประโยชน์กับผู้ใช้อยู่
        #   ตราบใดที่บอกให้เขารู้ว่ามันยังไม่ผ่าน — การซ่อนไปเลยแย่กว่าการแสดงพร้อมป้ายกำกับ
        return review

    except Exception:
        # ↑ 🔑 จับกว้างมาก ซึ่งปกติถือเป็นนิสัยไม่ดี — แต่ตรงนี้ "ตั้งใจ" และเป็นจุดสำคัญของระบบ
        logger.warning("clause %s review failed", clause.id, exc_info=True)
        #                                                    ↑ ห้ามลืมเด็ดขาด!
        #   exc_info=True = พิมพ์ traceback เต็ม ๆ ลง log
        #   ถ้าไม่ใส่: except Exception จะกลายเป็น "กลืน error เงียบ ๆ"
        #   → ระบบดูเหมือนทำงานปกติ แต่ทุก clause ออกมาเป็น unknown โดยไม่มีใครรู้สาเหตุ
        #
        #   ❓ ทำไมต้องจับกว้างขนาดนี้?
        #     ลองนึกภาพสัญญา 40 ข้อ แล้ว clause ที่ 7 เจอ Gemini timeout พอดี
        #     ถ้าปล่อย exception ลอยขึ้นไป → ผู้ใช้ได้ HTTP 500
        #     → เสียผลของอีก 39 clause ที่วิเคราะห์สำเร็จแล้ว (และจ่ายค่า token ไปแล้ว)
        #     → ต้องอัปโหลดใหม่ทั้งไฟล์ และอาจเจอ error เดิมอีก
        #     การกั้นความเสียหายไว้แค่ clause เดียว = ผู้ใช้ยังได้รายงานที่ใช้งานได้
        #     📌 เรียก pattern นี้ว่า "fault boundary" — วางกำแพงกันพังไว้ตรงจุดที่พังได้บ่อย

        return ClauseReview(
            clause=clause,
            risk_level=RiskLevel.UNKNOWN,   # ← ไม่เดาว่าปลอดภัย ไม่เดาว่าอันตราย = บอกว่า "ไม่รู้"
            rationale="Automated review failed for this clause; manual review required.",
            #          ↑ บอกผู้ใช้ตรง ๆ ว่าข้อนี้ต้องให้คนตรวจเอง
            #            สำคัญมากในระบบที่เกี่ยวกับกฎหมาย: "ไม่รู้" ต้องแสดงว่าไม่รู้
            #            ห้ามแสร้งว่าข้อนี้ปลอดภัยเด็ดขาด
        )
```

```python
# app/ai/pipeline.py — aggregate(): รวมผลรายข้อ → ภาพรวมทั้งฉบับ
summary = RiskSummary()
for review in reviews:
    if review.risk_level == RiskLevel.HIGH:
        summary.high += 1
    elif review.risk_level == RiskLevel.MEDIUM:
        summary.medium += 1
    elif review.risk_level == RiskLevel.LOW:
        summary.low += 1
    else:
        summary.unknown += 1

# ── กฎ "ข้อที่แย่ที่สุดชนะ" (worst case wins) ──
if summary.high:            # ← เลข 0 เป็น falsy ใน Python → เขียนสั้นแทน `if summary.high > 0`
    overall = RiskLevel.HIGH
elif summary.medium:
    overall = RiskLevel.MEDIUM
elif summary.low:
    overall = RiskLevel.LOW
else:
    overall = RiskLevel.UNKNOWN
return summary, overall
# ↑ ❓ ทำไมไม่ใช้ค่าเฉลี่ยหรือให้คะแนนถ่วงน้ำหนัก?
#   ลองนึกภาพ: สัญญามี 30 ข้อความเสี่ยงต่ำ + 1 ข้อที่ระบุว่า "รับผิดไม่จำกัดวงเงิน"
#   ถ้าเฉลี่ย → ผลออกมาว่า "ความเสี่ยงต่ำ" ✅ ทั้งที่ข้อเดียวนั้นอาจทำบริษัทล้มได้
#   📌 สัญญาปลอดภัยได้แค่เท่าข้อที่อันตรายที่สุดของมัน — ค่าเฉลี่ยจะกลบสิ่งที่ต้องเห็นที่สุด
#
# ❓ ทำไมแยกเป็นฟังก์ชันต่างหาก ไม่เขียนรวมใน Orchestrator.review()?
#   เพราะ services/override.py:43 เรียกใช้ซ้ำตอนคนแก้ระดับความเสี่ยงเอง
#   → ตัวเลขสรุปคำนวณด้วยกฎเดียวกันเสมอ ไม่มีทางที่ 2 เส้นทางจะให้ผลต่างกัน
#   (ถ้า copy-paste logic ไปไว้ 2 ที่ วันหนึ่งจะแก้ที่เดียวลืมอีกที่แน่นอน)
```

```python
# app/errors.py — จุดเดียวในระบบที่แปลง error ของ domain → HTTP
class DomainError(Exception):
    status_code: int = 400          # ← ค่า default ของ error ทั่วไป
    code: str = "domain_error"      # ← รหัสที่ frontend เอาไปเทียบได้ (ไม่ใช่ข้อความให้คนอ่าน)

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DocumentParseError(DomainError):
    status_code = 422    # Unprocessable Entity — "รับ request ได้ แต่เนื้อหาข้างในใช้ไม่ได้"
    code = "document_parse_error"

class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"
# ↑ 📌 แต่ละ error พก status code ของตัวเองมาด้วย
#   → layer ล่างโยน error ตามความหมายของ domain ได้เลย โดยไม่ต้องรู้จัก HTTP
#   → ไม่ต้องมี if/elif ยาว ๆ ที่ route คอยแปลง error แต่ละชนิดเป็นเลข status


def register_exception_handlers(app) -> None:
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(DomainError)
    #  ↑ ลงทะเบียนกับ "คลาสแม่" ตัวเดียว → ครอบคลุมคลาสลูกทุกตัวอัตโนมัติ
    #    เพิ่ม error ชนิดใหม่ในอนาคต = แค่สืบทอด DomainError ไม่ต้องมาแก้ไฟล์นี้อีกเลย
    async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": exc.message},
            # ↑ รูปแบบเดียวกันทุก endpoint → frontend (lib/api.ts) เขียนตัวแปลง error ครั้งเดียว
            #   "error" = รหัสให้โปรแกรมเทียบ / "message" = ข้อความให้คนอ่าน
            #   แยกสองอย่างนี้ออกจากกันเสมอ เพราะข้อความให้คนอ่านเปลี่ยนได้ตลอด
            #   (แปลภาษา ปรับถ้อยคำ) แต่รหัสต้องคงที่ ไม่งั้น frontend พังทุกครั้งที่แก้คำ
        )
```

---

# 🔐 ภาคผนวก: OAuth flow — ตั้งแต่กดปุ่ม "Sign in with Google" จนได้ JWT

ส่วนก่อนหน้าเดินตาม request ที่ **มี token อยู่แล้ว** ส่วนนี้ย้อนไปดูว่า token นั้นมาจากไหน

OAuth ต่างจาก endpoint อื่นตรงที่มันไม่ใช่ request เดียวจบ แต่เป็น **การเต้นรำ 3 ฝ่าย**
(เบราว์เซอร์ ↔ backend ของเรา ↔ Google) ที่กินเวลาหลาย request และเราคุมได้แค่ 2 ใน 3 ฝ่าย
ความยุ่งยากเกือบทั้งหมดของโค้ดส่วนนี้มาจากข้อจำกัดข้อนั้น

## ภาพรวมทั้งวง

```text
[A] ผู้ใช้กดปุ่มที่หน้า /login
     window.location.href = "http://localhost:8000/auth/google/login"
     ↑ ใช้ full-page navigation ไม่ใช่ fetch()  ← เหตุผลอยู่ในขั้น [A]
     │
     ▼
[B] GET /auth/google/login   (backend ของเรา)
     Authlib สุ่มค่า state → เก็บลง session cookie → 302 ไป Google
     │
     ▼
[C] accounts.google.com — ผู้ใช้เลือกบัญชี + กด Allow
     (ตรงนี้อยู่นอกการควบคุมของเราทั้งหมด — ผู้ใช้กด "ยกเลิก" ได้)
     │
     ▼
[D] GET /auth/google/callback?code=...&state=...   (Google ส่งเบราว์เซอร์กลับมา)
     ├─ Authlib เทียบ state กับที่เก็บใน session → กัน CSRF
     ├─ เอา code ไปแลก token กับ Google (server-to-server ไม่ผ่านเบราว์เซอร์)
     ├─ upsert user ลง Postgres
     └─ ออก JWT ของ "เรา" เอง → 302 กลับ frontend พร้อม ?token=...
     │
     ▼
[E] frontend /auth/callback — เก็บ token ลง localStorage แล้วล้าง URL ทิ้ง
     │
     ▼
[F] ทุก request หลังจากนี้แนบ  Authorization: Bearer <jwt>
     → เข้าสู่ขั้น [3] ของบทก่อนหน้า
```

> 📌 **จุดที่คนมักเข้าใจผิด:** token ของ Google กับ JWT ของเราเป็นคนละใบ
> เราใช้ Google แค่ตอบคำถามว่า *"คนนี้คือใคร"* ครั้งเดียวตอน login
> จากนั้นเราออกบัตรผ่านของเราเองแล้วเลิกยุ่งกับ Google ไปเลย
> — token ของ Google ไม่เคยถูกเก็บ ไม่เคยถูกส่งต่อให้ frontend

---

## [A] ตั้งค่า OAuth client — `app/security.py`

```python
from authlib.integrations.starlette_client import OAuth
# ↑ ทำไมต้อง Authlib? เพราะ OAuth2/OIDC มีรายละเอียดที่ทำเองแล้วพลาดง่ายมาก:
#   สุ่ม state, เทียบ state, แลก code เป็น token, ตรวจลายเซ็น id_token ด้วย JWKS ของ Google,
#   เช็ค iss/aud/exp, และ refresh key เมื่อ Google หมุนกุญแจ
#   เขียนเองได้ แต่พลาดข้อเดียว = ช่องโหว่ auth ซึ่งเป็นประเภทที่เจ็บที่สุด

_settings = get_settings()   # ← อ่านครั้งเดียวตอน import (มี @lru_cache อยู่แล้ว)

oauth = OAuth()
oauth.register(
    name="google",
    # ↑ ชื่อนี้กลายเป็น oauth.google ที่เรียกใช้ใน routes/auth.py
    #   ถ้าวันหนึ่งเพิ่ม Microsoft login ก็ register(name="microsoft") เพิ่มอีกตัว

    client_id=_settings.google_oauth_api,
    client_secret=_settings.google_key_secret,
    # ↑ ได้มาจาก Google Cloud Console
    #   🔑 client_secret ต้องอยู่ฝั่ง server เท่านั้น ห้ามหลุดไป frontend เด็ดขาด
    #     นี่คือเหตุผลที่ flow นี้ต้องวิ่งผ่าน backend ไม่ใช่ให้ React คุยกับ Google ตรง ๆ

    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    # ↑ 🔑 บรรทัดเดียวที่แทน hard-code URL ได้ทั้งชุด
    #   URL นี้คือ "OIDC discovery document" — Google ประกาศไว้ว่า
    #     - authorization_endpoint อยู่ที่ไหน (หน้าเลือกบัญชี)
    #     - token_endpoint อยู่ที่ไหน (จุดแลก code เป็น token)
    #     - jwks_uri อยู่ที่ไหน (กุญแจสาธารณะสำหรับตรวจลายเซ็น id_token)
    #   Authlib ไปดึงเอง + cache ให้
    #   ❓ ทำไมไม่ hard-code 3 URL นั้นไปเลย?
    #     เพราะ Google หมุนกุญแจ (key rotation) เป็นระยะ และเคยย้าย endpoint มาแล้ว
    #     hard-code = วันหนึ่ง login พังโดยที่เราไม่ได้แก้อะไรเลย

    client_kwargs={"scope": "openid email profile"},
    # ↑ ขอสิทธิ์เท่าที่จำเป็นจริง ๆ เท่านั้น (principle of least privilege)
    #   openid  → เปิดโหมด OIDC ทำให้ได้ id_token ที่มี "sub" กลับมา
    #   email   → ได้อีเมล (ใช้เป็น actor ใน audit log)
    #   profile → ได้ชื่อกับรูป (ใช้แสดงใน UI)
    #   ❗ ยิ่งขอ scope มาก หน้า consent ของ Google ยิ่งน่ากลัว คนยิ่งกดยกเลิก
    #     และถ้าขอ scope ที่ Google ถือว่า sensitive จะต้องผ่านการ verify แอปด้วย
)
# 📌 สังเกตว่า oauth เป็นตัวแปรระดับโมดูล = สร้างครั้งเดียวตอน import
#    ไม่ได้อยู่ใน dependencies.py เพราะไม่มี state ต่อ request และเทสต์ monkeypatch
#    ที่ oauth.google ได้ตรง ๆ อยู่แล้ว (ดู tests/integration/test_auth.py:81)
```

---

## [B] เริ่ม flow — `GET /auth/google/login`

```python
@router.get("/google/login")
async def google_login(request: Request):
    """Kick off the Google OAuth flow."""
    return await oauth.google.authorize_redirect(request, get_settings().google_redirect_uri)
    #            ↑ เมธอดเดียวจบ แต่ข้างในทำ 4 อย่าง:
    #              1. สุ่มค่า state (สตริงสุ่มยาว ๆ)
    #              2. เก็บ state ลง session cookie   ← ต้องมี SessionMiddleware ถึงทำได้!
    #              3. ประกอบ URL ของ Google พร้อม client_id, scope, redirect_uri, state
    #              4. คืน RedirectResponse (302) ไป URL นั้น
    #
    #            ↑ ต้อง await เพราะรอบแรกมันอาจต้องไปโหลด discovery document จาก Google ก่อน
    #
    #            ↑ ❓ ทำไมต้องส่ง request เข้าไปด้วย?
    #              เพราะ Authlib ต้องเข้าถึง request.session เพื่อเก็บ state
    #              (SessionMiddleware เป็นคนแปะ .session ให้ทุก request)

# ❓ redirect_uri คืออะไร ทำไมต้องตรงเป๊ะกับที่ตั้งใน Google Console?
#   คือ "ที่อยู่ที่ Google จะส่งเบราว์เซอร์กลับมาหลังผู้ใช้อนุมัติ"
#   Google บังคับให้ตรงกับที่ลงทะเบียนไว้แบบตัวอักษรต่อตัวอักษร (รวม http/https, port, และ / ท้าย)
#   เพื่อกันไม่ให้ผู้โจมตีเอา client_id ของเราไปใช้ แล้วสั่งให้ Google ส่ง code ไปที่เว็บของเขาแทน
#   → ถ้าตั้งผิดแม้แต่ตัวเดียว จะเจอ error "redirect_uri_mismatch" ที่หน้า Google เลย
#     (เป็นปัญหาที่เจอบ่อยที่สุดตอน setup — เช็ค GOOGLE_REDIRECT_URI ใน .env ก่อนเสมอ)

# ❓ ทำไม frontend ต้องใช้ window.location.href ไม่ใช้ fetch() เรียก endpoint นี้?
#   เพราะปลายทางคือ "หน้าเว็บของ Google ที่ผู้ใช้ต้องเห็นและกดเอง"
#   fetch() จะตาม redirect ไปเงียบ ๆ แล้วได้ HTML ของ Google กลับมาเป็นสตริง — ไร้ประโยชน์
#   และผู้ใช้ไม่มีทางเห็นหน้าเลือกบัญชีเลย
#   ต้อง "พาเบราว์เซอร์ทั้งบานไป" เท่านั้น (full-page navigation)
#   📌 นี่คือเหตุผลรากที่ทำให้ทุก error path ของ flow นี้ต้องเป็น redirect ไม่ใช่ JSON (ดูขั้น [D])
```

---

## [C] ฝั่ง Google — ส่วนที่เราคุมไม่ได้

```text
ผู้ใช้เห็นหน้า accounts.google.com → เลือกบัญชี → กด "อนุญาต"

สิ่งที่อาจเกิดขึ้น (และโค้ดเราต้องรับมือทุกกรณี):
  ✅ กดอนุญาต            → Google เด้งกลับมาพร้อม ?code=...&state=...
  ❌ กดยกเลิก/ปิดแท็บ     → Google เด้งกลับมาพร้อม ?error=access_denied
  ❌ บัญชีถูก admin บล็อก  → ?error=admin_policy_enforced
  ❌ ผู้ใช้ค้างหน้านี้นานมาก จน session cookie ฝั่งเราหมดอายุ → state เทียบไม่ตรง

📌 ข้อสังเกตสำคัญ: เราไม่มีทางรู้ล่วงหน้าว่าผู้ใช้จะกลับมาเมื่อไหร่ หรือจะกลับมาไหม
   ทุกกรณีข้างบนจบลงที่ endpoint เดียวกันคือ /auth/google/callback
   → callback จึงต้องถูกเขียนแบบ "ทุกทางออกต้องพาผู้ใช้ไปที่ที่เขาทำอะไรต่อได้"
```

---

## [D] หัวใจของ flow — `GET /auth/google/callback`

```python
def _redirect_to_frontend(path: str, **params: str) -> RedirectResponse:
    """Redirect the browser back to the frontend."""
    query = f"?{urlencode(params)}" if params else ""
    #        ↑ urlencode จัดการ escape ให้ (ช่องว่าง, &, = ในค่า) — ห้ามต่อสตริงเอง
    return RedirectResponse(f"{get_settings().frontend_url}{path}{query}")
# ↑ ❓ ทำไมต้องมี helper ตัวนี้ ทำไมทุกทางออกต้องเป็น redirect?
#   เพราะ endpoint นี้ถูกเปิดด้วย "การพาเบราว์เซอร์มาทั้งบาน" ไม่ใช่ fetch()
#   ถ้าตอบ JSON {"error": "..."} กลับไป → ผู้ใช้จะจ้องหน้าจอขาว ๆ ที่มีข้อความ JSON ดิบ ๆ
#     อยู่บนโดเมนของ backend (:8000) โดยไม่มีปุ่ม ไม่มีลิงก์ ไม่มีทางกลับ
#   ต้องส่งเขากลับไปที่ frontend เสมอ พร้อมรหัสข้อผิดพลาดที่หน้า login เอาไปแปลเป็นข้อความได้


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Complete the OAuth flow: upsert the user and hand a JWT to the frontend."""

    # ── ด่านที่ 1: แลก code เป็น token (และเทียบ state กัน CSRF) ──
    try:
        token = await oauth.google.authorize_access_token(request)
        # ↑ เมธอดนี้ทำหลายอย่างในบรรทัดเดียว:
        #   1. อ่าน state จาก query แล้วเทียบกับที่เก็บไว้ใน session → ไม่ตรง = โยน error
        #   2. เอา code + client_secret ยิงไปที่ token_endpoint ของ Google
        #      🔑 ขั้นนี้เป็น server-to-server ไม่ผ่านเบราว์เซอร์
        #         → client_secret ไม่มีทางหลุดออกไปนอกเซิร์ฟเวอร์
        #   3. ตรวจลายเซ็นของ id_token ด้วยกุญแจสาธารณะจาก jwks_uri ของ Google
        #   4. แกะ claims ออกมาใส่ token["userinfo"]
        #
        #   ❓ ทำไม OAuth ต้องมีขั้น "แลก code" ให้ยุ่งยาก ส่ง token มาเลยไม่ได้เหรอ?
        #     เพราะ code วิ่งผ่านเบราว์เซอร์ (เห็นได้ใน URL, ติดใน history, ติดใน log ของ proxy)
        #     code จึงถูกออกแบบให้ "ใช้ได้ครั้งเดียว หมดอายุเร็ว และใช้ไม่ได้ถ้าไม่มี client_secret"
        #     ส่วน token ตัวจริงวิ่งในช่องทาง server-to-server ที่ไม่มีใครดักอ่านได้

    except OAuthError as exc:
        logger.warning("Google OAuth failed: %s: %s", exc.error, exc.description)
        return _redirect_to_frontend("/login", error=exc.error or "oauth_failed")
        # ↑ ครอบทั้ง "ผู้ใช้กดยกเลิก" (access_denied) และ "state ไม่ตรง" (mismatching_state)
        #   ส่ง exc.error (รหัสของ Google) ต่อไปให้ frontend ตรง ๆ
        #   → lib/auth.ts มีตาราง LOGIN_ERROR_MESSAGES แปลรหัสเป็นข้อความที่คนอ่านรู้เรื่อง
        #     และมีข้อความสำรองสำหรับรหัสที่ไม่รู้จัก → ไม่มีทางที่ผู้ใช้จะเจอหน้าจอเงียบ ๆ
        #
        #   `or "oauth_failed"` กันกรณี exc.error เป็น None (ไม่งั้นได้ ?error=None ซึ่งดูงง)

    # ── ด่านที่ 2: ข้อมูลที่ได้มาใช้งานได้จริงไหม ──
    userinfo = token.get("userinfo")
    if not userinfo or not userinfo.get("email"):
        logger.warning("Google OAuth returned no usable userinfo: %s", sorted(token))
        #                                                             ↑ log แค่ "ชื่อ key"
        #   🔑 ห้าม log ตัว token! เพราะข้างในมี access_token/id_token ของจริง
        #     ถ้า log หลุด = คนที่อ่าน log สวมรอยเป็นผู้ใช้คนนั้นได้
        #     sorted(token) ให้แค่รายชื่อ key → พอสำหรับ debug ว่า "ขาด key ไหนไป"
        return _redirect_to_frontend("/login", error="missing_email")

    # ── ด่านที่ 3: upsert user ──
    user_id = userinfo["sub"]  # Google's stable per-account identifier
    # ↑ 🔑 ทำไมใช้ "sub" เป็น primary key ไม่ใช้อีเมล?
    #   เพราะ "อีเมลเปลี่ยนได้ แต่ sub ไม่เปลี่ยน"
    #   ผู้ใช้เปลี่ยนอีเมลใน Google Workspace แล้ว sub ยังเป็นตัวเดิม
    #   ถ้าใช้อีเมลเป็น key: เปลี่ยนอีเมล = กลายเป็นคนใหม่ ประวัติทั้งหมดหายไป
    #   แย่กว่านั้น: องค์กรลบบัญชีเก่าแล้วสร้างใหม่ด้วยอีเมลเดิมให้พนักงานคนใหม่
    #   → คนใหม่จะได้ข้อมูลของคนเก่าไปทั้งหมด

    user = db.get(User, user_id)
    if user is None:
        user = User(id=user_id, email=userinfo["email"])
        db.add(user)          # ← ครั้งแรกที่ login = สร้าง user ให้เลย ไม่ต้องมีหน้า "สมัครสมาชิก"

    user.email = userinfo["email"]
    user.name = userinfo.get("name")
    user.picture = userinfo.get("picture")
    # ↑ เขียนทับทุกครั้งที่ login ทั้งกรณี user ใหม่และเก่า (นี่คือส่วน "update" ของ upsert)
    #   → เปลี่ยนรูปโปรไฟล์ใน Google แล้วมาล็อกอินใหม่ รูปในระบบเราอัปเดตตาม
    #   ใช้ .get() กับ name/picture เพราะเป็น optional (บางบัญชีไม่มี) แต่ใช้ [] กับ email
    #   เพราะด่านที่ 2 การันตีแล้วว่ามีแน่นอน

    db.commit()

    # ── ด่านที่ 4: ออกบัตรผ่านของเราเอง แล้วส่งกลับ frontend ──
    return _redirect_to_frontend("/auth/callback", token=create_access_token(subject=user_id))
    # ↑ 🔑 จุดที่เลิกยุ่งกับ Google อย่างถาวร
    #   token ของ Google ถูกทิ้งไปตรงนี้ ไม่เก็บ ไม่ส่งต่อ
    #   เราออก JWT ของเราเองที่มีแค่ {"sub": user_id, "exp": ...}
    #
    #   ❓ ทำไมไม่เก็บ Google token ไว้ใช้ต่อ?
    #     เพราะเราไม่ต้องการมันอีกแล้ว — เราไม่ได้จะไปอ่าน Gmail หรือ Drive ของผู้ใช้
    #     ใช้ Google แค่ตอบว่า "คนนี้คือใคร" ครั้งเดียวก็พอ
    #     📌 ไม่เก็บสิ่งที่ไม่ต้องใช้ = ไม่มีอะไรให้รั่ว
```

> ⚠️ **ข้อสังเกตด้านความปลอดภัยที่ยอมรับไว้:** JWT ถูกส่งกลับผ่าน **query string**
> (`?token=...`) ซึ่งโดยทั่วไปถือว่าไม่ดี เพราะ URL ติดอยู่ใน browser history และใน
> access log ของ proxy ที่คั่นกลาง โปรเจกต์นี้ลดความเสี่ยงด้วยการให้ frontend
> **ล้าง URL ทิ้งทันที** ที่รับ token (ดูขั้น [E]) และตั้งอายุ token ไว้ 12 ชม.
> ทางที่ปลอดภัยกว่าคือส่งเป็น `HttpOnly` cookie แต่จะต้องจัดการ CSRF เพิ่มอีกชุด

---

## [E] ฝั่ง frontend รับ token — `apps/web/src/lib/auth.ts`

```ts
// After Google login, the backend redirects to /auth/callback?token=...
export function consumeTokenFromUrl(): void {
  if (window.location.pathname !== '/auth/callback') return
  // ↑ ทำงานเฉพาะที่หน้านี้เท่านั้น กันการหยิบ ?token= จากหน้าอื่นโดยไม่ตั้งใจ

  const token = new URLSearchParams(window.location.search).get('token')
  if (token) setToken(token)     // ← เก็บลง localStorage คีย์ "access_token"

  window.history.replaceState({}, '', '/')
  // ↑ 🔑 ล้าง URL ทิ้งทันที — บรรทัดนี้สำคัญกว่าที่เห็น
  //   replaceState = "แทนที่" รายการปัจจุบันใน history ไม่ใช่ "เพิ่ม" รายการใหม่
  //   → URL ที่มี token หายออกจาก history ไปเลย กด Back ก็ไม่เจอ
  //   ถ้าใช้ pushState แทน: URL เดิมที่มี token จะยังค้างอยู่ใน history
  //   และถ้าไม่ล้างเลย: ผู้ใช้อาจ copy URL ทั้งบรรทัดส่งให้เพื่อน = ส่ง token ให้ไปด้วย
}
```

```tsx
// apps/web/src/page/callback.tsx — หน้าที่ผู้ใช้เห็นแวบเดียว
useEffect(() => {
  consumeTokenFromUrl();
  navigate(getToken() ? "/manual" : "/login", { replace: true });
  //                                            ↑ replace: true = ไม่เพิ่มหน้านี้เข้า history
  //                                              กด Back แล้วไม่ย้อนกลับมาหน้า callback อีก
}, [navigate]);
// ↑ เช็ค getToken() หลังเก็บเสร็จ แทนที่จะเชื่อว่าสำเร็จแน่นอน
//   → ถ้า localStorage ถูกปิด (โหมดส่วนตัวบางเบราว์เซอร์) จะเด้งกลับ /login แทนที่จะค้าง
```

---

## [F] ทุก request หลังจากนี้

```text
frontend: apiFetch() แนบ header  Authorization: Bearer <jwt>  ให้อัตโนมัติ
backend : get_current_user() ถอด JWT → query user → คืน User object  (= ขั้น [3])

logout  : POST /auth/logout ที่ backend ไม่ได้ทำอะไรเลยจริง ๆ นอกจากตอบข้อความ
          เพราะ JWT เป็น stateless — เพิกถอนกลางคันไม่ได้ frontend แค่ลบ token ทิ้ง
          ⚠️ แปลว่า token ที่หลุดออกไปยังใช้ได้จนหมดอายุ
             → นี่คือเหตุผลตรง ๆ ที่ ACCESS_TOKEN_EXPIRE_MINUTES ถูกลดจาก 7 วัน เหลือ 12 ชม.
               (commit 9c12e40 — "a week is a long blast radius for an app holding contracts")
```

---

## 🧪 flow นี้ถูกทดสอบยังไงโดยไม่ต้องมีคนกดจริง

`tests/integration/test_auth.py` **mock ที่ขอบของ Authlib** ไม่ใช่ที่ HTTP ของ Google:

```python
async def fake_authorize_access_token(request):
    return {"userinfo": {"sub": "google-sub-2", "email": "bob@example.com", "name": "Bob"}}

monkeypatch.setattr(oauth.google, "authorize_access_token", fake_authorize_access_token)
# ↑ ❓ ทำไม mock ตรงจุดนี้ ไม่ mock ที่ระดับ HTTP?
#   เพราะทุกอย่างที่อยู่ "ก่อน" จุดนี้เป็นความรับผิดชอบของ Google กับ Authlib
#   (ซึ่งทั้งคู่มีเทสต์ของตัวเองอยู่แล้ว) และของจริงต้องมีคนคลิกหน้า consent
#   ส่วนทุกอย่างที่อยู่ "หลัง" จุดนี้เป็นโค้ดของเรา 100%:
#     upsert user ถูกไหม / ออก JWT ที่ decode กลับมาได้ sub ตรงไหม / redirect ไปที่ถูกไหม
#     / error path ทั้ง 3 แบบพากลับ /login พร้อมรหัสที่ถูกต้องไหม
#   📌 หลักการ: mock ที่ "ขอบของสิ่งที่เราควบคุมได้" — ไม่ใกล้เกินจนไม่ได้ทดสอบอะไร
#      และไม่ไกลเกินจนกลายเป็นการทดสอบ library ของคนอื่น
```

ครอบทั้ง 6 กรณี: user ใหม่ / user เดิม (อัปเดตชื่อ-อีเมล) / กดยกเลิก (`access_denied`) /
ไม่มีอีเมล (`missing_email`) / session หลุด (`mismatching_state`) / redirect_uri ที่ส่งให้ Google
ตรงกับค่าใน settings

---

## 🧩 สรุปกฎที่ยึดตลอดทั้ง codebase

| กฎ | เหตุผล |
|---|---|
| **ใช้ regex/โค้ดธรรมดาแทน LLM ทุกครั้งที่ทำได้** | ถูกกว่า เร็วกว่า และให้ผลเดิมทุกครั้ง — LLM สงวนไว้สำหรับงานที่ต้องเข้าใจความหมายจริง ๆ |
| **ตรวจสอบเอาต์พุตของโมเดลด้วยโค้ด ไม่ใช่ด้วยโมเดล** | guardrail แบบ deterministic ตอบได้แน่นอน 100% ส่วน LLM judge ใช้เฉพาะสิ่งที่โค้ดตอบไม่ได้ |
| **pydantic สำหรับข้อมูลที่มาจากภายนอก / dataclass สำหรับข้อมูลภายใน** | validation มีราคา จ่ายเฉพาะตรงที่ข้อมูลเชื่อไม่ได้ (HTTP request, คำตอบ LLM) |
| **`Protocol` แทน ABC สำหรับ storage/adapter** | ตัวปลอมในเทสต์ไม่ต้องสืบทอดอะไร ขอแค่มีเมธอดครบ |
| **import ของหนักไว้ข้างในฟังก์ชัน** | `fitz`, `google.genai`, `rank_bm25` — boot เร็วขึ้น และเทสต์รันได้แม้ไม่มี dependency ครบ |
| **`@lru_cache` = ของระดับ process, ฟังก์ชันธรรมดา = ของระดับ request** | ของที่ผูกกับ DB session ห้าม cache เด็ดขาด |
| **`services/` ห้าม import `fastapi`** | business logic ต้องเรียกใช้จาก CLI/worker ได้ ไม่ผูกกับเว็บ |
| **แยก store ตามอายุข้อมูล ไม่ใช่ตามชนิดข้อมูล** | สัญญาดิบ = Redis + TTL (ต้องหาย), รายงาน + audit log = Postgres (ต้องอยู่จนเจ้าของสั่งลบ — รายงานย้ายฝั่งมาเมื่อ 2026-07-30 เพราะ TTL ทำให้ต้องจ่ายค่า pipeline ใหม่ทั้งฉบับ) |

---

## ⚠️ ข้อควรระวังที่ยังไม่ได้แก้ (จาก code review 2026-07-26, ทวนกับโค้ดจริงอีกครั้ง 2026-07-30)

เขียนไว้ตรงนี้เพื่อไม่ให้เอกสารอธิบาย logic ไปโดยไม่บอกจุดที่ยังมีปัญหา —
รายละเอียดและวิธีแก้อยู่ในผลรีวิว (ข้อที่แก้ไปแล้วถูกย้ายไปท้ายหัวข้อ):

1. **คุณภาพ gold label เป็นเพดานของ `classification_accuracy` / `risk_accuracy`** — ไม่ใช่บั๊กที่
   แก้ได้ในโค้ด: CUAD ตอบคำถาม 41 ข้อเกี่ยวกับสัญญา ไม่ได้จำแนกประเภทข้อสัญญา label จาก coverage
   (2026-07-30) แม่นกว่าเดิมแต่ยังเป็นการอนุมาน (ดู [เพดานของ gold
   label](#เพดานของ-gold-label-ที่มาจาก-cuad)) — วัดบนไม้บรรทัดใหม่แล้วเมื่อ 2026-07-31 ได้
   `classification 45.45%` / `risk 50.00%` และ **ตัวเลขที่ลดลงมาจากไม้บรรทัด ไม่ใช่จาก pipeline**
   (ดู [ผลรอบล่าสุด](#ผล-eval-บน-label-ชุดใหม่-2026-07-31))
2. **`non_compete` ถูกจำแนกเป็น `intellectual_property` บ่อย** (3 ใน 7 ข้อที่มี label) — ยังไม่ได้
   แก้ เพราะข้อห้ามแข่งขันใน CUAD มักเขียนรวมกับข้อสงวนสิทธิ์ IP จริง ๆ การจะรู้ว่าใครผิดต้องอ่าน
   ทีละข้อด้วยคน ไม่ใช่ขยับ prompt ตามตัวเลข

**9 ข้อที่แก้ไปแล้ว** (2 ข้อบนสุดแก้เมื่อ 2026-07-31, 5 ข้อล่างแก้เมื่อ 2026-07-30 พร้อมยืนยันด้วย
`curl`/รันจริง):

- ~~ยังไม่มีตัวเลข eval บน gold label ชุดใหม่~~ — รันแล้ว 2026-07-31 (`--limit 3`, 90 clause,
  18 นาที 10 วิ): `segmentation_f1` 100%, `citation_validity` 100%, `classification` 45.45%,
  `risk` 50.00%
- ~~ไม่มี integration test ที่ยิง LLM จริง~~ — `tests/live/` (10 ตัว) +
  `tests/eval/test_regression.py` ที่เลิก skip แล้ว รวม 11 ตัวใต้ marker `live_llm` ซึ่ง deselect
  เป็น default; รอบแรกที่รันจริงจับได้เลยว่า GLM-4.6 เคยตอบ list ภาษาจีนแทน object ตาม schema
  (retry ชั้นบน SDK กู้คืนได้)

- ~~retry ตอน ungrounded ส่ง prompt เดิมเป๊ะ ๆ~~ — `RiskScorerInput.feedback` ส่ง `verdict.reason`
  กลับเข้า prompt รอบสอง (`risk_scorer.v1.jinja` มีบล็อก "your previous answer was rejected")
  รอบแรกไม่มี feedback รอบสองมี — เทสต์ยืนยันทั้งสองทาง (`tests/unit/test_retry_feedback.py`)
- ~~`is_grounded()` เป็น substring check ล้วน~~ — เพิ่ม `min_words` และ judge ส่ง
  `MIN_CITATION_EXCERPT_WORDS = 4` (excerpt จริงที่ pipeline ผลิตยาว 20–40 คำ จึงห่างเพดานมาก)
  ส่วน metadata ยังใช้ default 1 คำเพราะค่าอย่าง `"กฎหมายไทย"` สั้นโดยธรรมชาติ — ถ้าบังคับ 4 คำ
  ตรงนั้นจะทิ้ง metadata ที่ถูกต้องทิ้ง
- ~~`/playbook/*` เป็น authentication ไม่ใช่ authorization~~ — `PLAYBOOK_ADMIN_EMAILS`
  (comma-separated, ไม่สนตัวพิมพ์ใหญ่เล็ก) จำกัดสิทธิ์ `POST`/`PUT`/`DELETE` เป็น `403`
  ส่วนการอ่านยังเปิดให้ทุกคนที่ login — ว่างไว้ = ทุกคนเขียนได้เหมือนเดิม (ไม่ทำให้หน้า
  `/playbook` ของ deployment เดิมพังตอนอัปเกรด)

- ~~Endpoint เป็น `async def` แต่ข้างในเป็น blocking I/O~~ — endpoint ที่ทำงาน blocking เปลี่ยนเป็น
  `def` ธรรมดาให้ FastAPI โยนเข้า threadpool แล้ว (`playbook.py` 6 ตัว, `evaluate.py`,
  `contracts.py` 5 ตัว) เหลือ `review_contract` เป็น `async` ตัวเดียวเพราะต้อง `await` ตัวอัปโหลด
  แล้วส่ง pipeline ต่อด้วย `run_in_threadpool()` — **วัดจริง: ระหว่าง review 18.9 วิกำลังทำงาน
  `/health` ตอบใน 1.2–2.0 ms** (เดิม 2.7 s) มี unit test กันไว้ด้วยว่า endpoint ที่เป็น `async`
  ต้องอยู่ใน allow-list เท่านั้น (`tests/unit/test_request_limits.py`)
- ~~`/playbook/*` ทั้ง 6 endpoint และ `POST /evaluate` ไม่ต้อง auth~~ — ประกาศ
  `dependencies=[Depends(get_current_user)]` **ที่ตัว router** ไม่ใช่รายตัว เพราะรูที่เกิดขึ้นคือ
  "ลืมใส่" ไม่ใช่ "ใส่ผิด" endpoint ที่เพิ่มเข้ามาใหม่จึงปิดโดยอัตโนมัติ (`curl` ยืนยัน: ทั้ง 6 ตัว
  + `/evaluate` → `401`, `/health` ยังเปิดตามเจตนา)
- ~~`EvalRequest.gold_set_path` เป็นพาธที่ client ส่งมาเอง~~ — `resolve_gold_set_path()` บังคับให้
  อยู่ใน `data/gold/` โดยเทียบหลัง `resolve()` เพื่อให้ `data/gold/../../.env` ถูกปฏิเสธจาก
  "ปลายทางที่มันชี้" ไม่ใช่จากรูปแบบข้อความ

อีก 2 ข้อจากรีวิวรอบ 2026-07-26 ที่แก้ไปนานแล้ว แต่ค้างอยู่ในลิสต์นี้จนถึง 2026-07-30:

- ~~`override_risk()` ไม่ได้เทียบ `report.session_id`~~ — ตรวจแล้วที่
  `services/override.py` (`_locate()`: `report.session_id != session_id` → `404`) และใช้ร่วมกับ
  `accept` ด้วย รายงานของคนอื่นตอบ `404` ไม่ใช่ `403`
- ~~`known_positions` อ่านจาก YAML แต่ retrieval อ่านจาก Postgres~~ — `get_known_positions()`
  อ่านจาก vector store แล้ว (YAML เหลือเป็น fallback ตอน DB ยังไม่ ingest) และเจตนาไม่ cache
  เพื่อให้ position ที่เพิ่มผ่าน `/playbook` ไม่ถูก judge ตีว่า "unknown"
