# Contract Clause Risk Reviewer

ระบบวิเคราะห์ **ความเสี่ยงของข้อสัญญา (clause) ด้วย AI** โดยใช้ grounded RAG —
อัปโหลดสัญญา → แยกเป็น clause → จำแนกประเภท → เทียบกับ playbook ของบริษัท →
ให้คะแนนความเสี่ยง → ตรวจทานด้วย LLM judge → สรุปเป็นรายงานพร้อม citation

> ✅ **สถานะ: Backend core pipeline ทำงานได้จริงแล้ว (end-to-end)** — ทดสอบกับ Gemini API +
> Postgres/pgvector จริง: upload → parse → segment → classify → match(RAG) → risk score →
> grounding judge → report พร้อม citation ที่ verify แล้ว ระบบ auth / DB / infra ก็ทำงานได้แล้วเช่นกัน
> ส่วนที่เหลือหลัก ๆ คือ **frontend upload/report UI** ยังเป็น stub — ดู
> [README ของ backend](apps/backend-fastapi/README.md) สำหรับรายละเอียด

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
| Backend | DB layer | SQLAlchemy engine/session/`Base`, `get_db`, สร้าง extension `vector` + ตารางทั้งหมดตอน startup |
| Backend | Auth (OAuth + JWT) | routes `/auth/*` ครบ, User model — **ทดสอบแล้ว**: JWT ถูก→คืน user, token ปลอม→`401` |
| Backend | **Review pipeline** | `POST /contracts/review` — **ทดสอบ live กับ Gemini + pgvector จริงแล้ว**: parse→segment→classify→match(RAG)→score→judge→report พร้อม citation ที่ grounded |
| Backend | **Override + audit** | `POST /contracts/{id}/override` — เปลี่ยน risk level, re-aggregate, เขียน audit log ลง Postgres (ทดสอบแล้ว) |
| Backend | **Playbook search + eval** | `GET /playbook/search`, `POST /evaluate` — ใช้งานได้จริง |
| Backend | LLM client + RAG | Gemini client (structured output), hybrid retrieval (pgvector cosine + BM25) |
| Backend | Parsers | PDF (PyMuPDF) / DOCX (python-docx) → `ParsedDocument` |
| Backend | Guardrails | grounding, citation validity, no-invented-fallback — wired เข้า judge แล้ว |
| Backend | Schemas | Pydantic models: clause, report, taxonomy, playbook, eval |
| Backend | Data fixtures | taxonomy (12 clause types), playbook positions (ingest แล้ว), gold annotations + contract text ที่ตรงกัน |
| Backend | Tests | 30 unit/integration tests ผ่านหมด |
| Frontend | Scaffold | React 19 + Vite + Tailwind + routing (`/login`, `/auth/callback`, `/manual`) |
| Frontend | Login UI | หน้า login + components (Google button, brand header, card, ฯลฯ) |
| Frontend | Auth flow | ต่อกับ backend ครบ: login redirect → callback เก็บ token → `fetchCurrentUser` (`/auth/me`), `RequireAuth` guard, logout |
| Frontend | Welcome page | หน้า `/manual` (onboarding) + Sidebar |
| Infra | Docker Compose | ยก Postgres (pgvector) + Redis ได้จริง |

---

## ❌ สิ่งที่ยังไม่ทำ

| ส่วน | รายการ | รายละเอียด |
|------|--------|------------|
| Backend | Alembic migrations | ยังใช้ `Base.metadata.create_all` ตอน startup |
| Backend | Redis | ยกใน infra แล้วแต่โค้ดยังไม่ได้ใช้ (repo เป็น in-memory ต่อ process) |
| Backend | Google OAuth e2e | โค้ดพร้อม แต่ต้องมี Google credentials จริง + ทดสอบผ่าน browser |
| Backend | Integration tests | `/contracts/review`, `/contracts/{id}/override` — ยังไม่มี (verify ด้วยการรัน live แทน) |
| Frontend | Contract upload UI | ยังไม่มีหน้าอัปโหลด/ส่งสัญญาไป backend |
| Frontend | Dashboard / Reports | เมนู Sidebar (Upload, Risk Assessment, Reports ฯลฯ) ยังเป็น `console.log` stub |
| Frontend | Risk report view | ยังไม่มี UI แสดงผลวิเคราะห์ความเสี่ยง / citation |

---

## Quick start

```bash
# 1) ยก infra (Postgres + Redis)
docker compose -f infrastructure/docker-compose.yml up -d postgres redis

# 2) backend
cd apps/backend-fastapi
pip install -e ".[dev]"          # ต้องมีไฟล์ .env ก่อน (ดู README ของ backend)
python -m scripts.ingest_playbook  # โหลด playbook เข้า pgvector ก่อนใช้ /contracts/review
uvicorn app.main:app --reload    # http://localhost:8000/docs

# 3) frontend
cd apps/web
pnpm install
pnpm dev                         # http://localhost:5173
```

รายละเอียด env / setup / roadmap ของ backend: [`apps/backend-fastapi/README.md`](apps/backend-fastapi/README.md)

---

## Roadmap ที่เหลือ

1. **Frontend**: upload UI + report view ต่อกับ `/contracts/review` (งานที่เหลือชิ้นใหญ่ที่สุด)
2. **Google OAuth** — ทดสอบ end-to-end ผ่าน browser จริง
3. **Alembic migrations** แทน `Base.metadata.create_all`
4. **Redis-backed session store** ถ้าต้อง scale ข้าม process/replica
5. **Integration tests** สำหรับ `/contracts/review` และ `/contracts/{id}/override`
