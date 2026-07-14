# Contract Clause Risk Reviewer

ระบบวิเคราะห์ **ความเสี่ยงของข้อสัญญา (clause) ด้วย AI** โดยใช้ grounded RAG —
อัปโหลดสัญญา → แยกเป็น clause → จำแนกประเภท → เทียบกับ playbook ของบริษัท →
ให้คะแนนความเสี่ยง → ตรวจทานด้วย LLM judge → สรุปเป็นรายงานพร้อม citation

> ⚠️ **สถานะ: MVP กำลังพัฒนา (scaffold)** — ระบบ auth / DB / โครงสร้าง / UI พื้นฐาน **ทำงานได้แล้ว**
> แต่ **core pipeline ของการรีวิวสัญญายังไม่ได้ implement** (เป็น `NotImplementedError` stub)
> ยังใช้งานรีวิวสัญญาจริงไม่ได้

## โครงสร้าง repo (monorepo)

| ส่วน | เทคโนโลยี | คำอธิบาย |
|------|-----------|----------|
| `apps/backend-fastapi` | FastAPI, SQLAlchemy, Postgres/pgvector, Redis, Anthropic | API + review pipeline (ดู [README ของ backend](apps/backend-fastapi/README.md)) |
| `apps/web` | React 19, Vite, Tailwind, react-router | Frontend (login, workspace UI) |
| `infrastructure` | Docker Compose | Postgres (pgvector) + Redis + api |

---

## ✅ สิ่งที่ทำแล้ว

| ส่วน | รายการ | รายละเอียด |
|------|--------|------------|
| Backend | App + entrypoint | FastAPI factory `app.main:app`, CORS, `SessionMiddleware` — boot ได้ |
| Backend | Health endpoints | `GET /`, `/health`, `/health/db` (ต่อ Postgres จริง → connected) |
| Backend | DB layer | SQLAlchemy engine/session/`Base`, `get_db`, สร้างตาราง `users` ตอน startup (non-fatal) |
| Backend | Auth (OAuth + JWT) | routes `/auth/*` ครบ, User model — **ทดสอบแล้ว**: JWT ถูก→คืน user, token ปลอม→`401` |
| Backend | Schemas | Pydantic models: clause, report, taxonomy, playbook, eval |
| Backend | Data fixtures | taxonomy (12 clause types), playbook positions, gold annotations (`.jsonl`) |
| Backend | Prompt templates | `classifier.v1`, `judge.v1`, `risk_scorer.v1` (jinja) |
| Frontend | Scaffold | React 19 + Vite + Tailwind + routing (`/login`, `/auth/callback`, `/manual`) |
| Frontend | Login UI | หน้า login + components (Google button, brand header, card, ฯลฯ) |
| Frontend | Auth flow | ต่อกับ backend ครบ: login redirect → callback เก็บ token → `fetchCurrentUser` (`/auth/me`), `RequireAuth` guard, logout |
| Frontend | Welcome page | หน้า `/manual` (onboarding) + Sidebar |
| Infra | Docker Compose | ยก Postgres (pgvector) + Redis ได้จริง |

---

## ❌ สิ่งที่ยังไม่ทำ

| ส่วน | รายการ | รายละเอียด |
|------|--------|------------|
| Backend | `POST /contracts/review` | ❌ `NotImplementedError` (หัวใจของโปรดักต์) |
| Backend | `POST /contracts/{id}/override` | ❌ ยังไม่ทำ |
| Backend | `GET /playbook/search` | ❌ `NotImplementedError` |
| Backend | `POST /evaluate` | ❌ `NotImplementedError` |
| Backend | Parsers | `app/parsers/` — PDF/DOCX → `ParsedDocument` |
| Backend | LLM client | `app/llm/` — เรียก Anthropic + structured output |
| Backend | RAG | `app/rag/` — embedder, retriever, vector_store (pgvector), ingest, citation |
| Backend | Agents | `app/agents/` — segmenter → classifier → matcher → risk_scorer → judge → orchestrator |
| Backend | Services / Repositories | review/override/eval service, contract/report/audit repo |
| Backend | Evaluation + Guardrails | eval runner/metrics, grounding, citation validity, disclaimer |
| Backend | DI providers | `get_vector_store()`, `get_llm_client()` |
| Backend | Migrations / Tests | ยังไม่มี Alembic; ยังไม่ได้เขียน test (มีแต่โครง) |
| Backend | Google OAuth e2e | โค้ดพร้อม แต่ต้องมี Google credentials จริง + ทดสอบผ่าน browser |
| Frontend | Contract upload UI | ยังไม่มีหน้าอัปโหลด/ส่งสัญญาไป backend |
| Frontend | Dashboard / Reports | เมนู Sidebar (Upload, Risk Assessment, Reports ฯลฯ) ยังเป็น `console.log` stub |
| Frontend | Risk report view | ยังไม่มี UI แสดงผลวิเคราะห์ความเสี่ยง / citation |

> รวมทั้งหมด backend มี **`NotImplementedError` 34 จุด + `TODO` 37 จุด**

---

## Quick start

```bash
# 1) ยก infra (Postgres + Redis)
docker compose -f infrastructure/docker-compose.yml up -d postgres redis

# 2) backend
cd apps/backend-fastapi
pip install -e ".[dev]"          # ต้องมีไฟล์ .env ก่อน (ดู README ของ backend)
uvicorn app.main:app --reload    # http://localhost:8000/docs

# 3) frontend
cd apps/web
pnpm install
pnpm dev                         # http://localhost:5173
```

รายละเอียด env / setup / roadmap ของ backend: [`apps/backend-fastapi/README.md`](apps/backend-fastapi/README.md)

---

## Roadmap ที่แนะนำ (ลำดับ implement)

1. **LLM client** (`app/llm/`) — พื้นฐานที่ agents ทุกตัวต้องใช้
2. **Parsers** (`app/parsers/`) — PDF/DOCX → text
3. **RAG** + `get_vector_store()` — เปิดใช้ `GET /playbook/search`
4. **Agents + Orchestrator** — segment → classify → match → score → judge
5. **review_service** → เปิดใช้ `POST /contracts/review`
6. **Frontend**: upload UI + report view ต่อกับ `/contracts/review`
7. **Guardrails → Evaluation → Tests / migrations**
