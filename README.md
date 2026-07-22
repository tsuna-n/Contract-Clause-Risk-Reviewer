# Contract Clause Risk Reviewer

ระบบวิเคราะห์ **ความเสี่ยงของข้อสัญญา (clause) ด้วย AI** โดยใช้ grounded RAG —
อัปโหลดสัญญา → แยกเป็น clause → จำแนกประเภท → เทียบกับ playbook ของบริษัท →
ให้คะแนนความเสี่ยง → ตรวจทานด้วย LLM judge → สรุปเป็นรายงานพร้อม citation

> ✅ **สถานะ: ใช้งานได้จริงครบวงจร (frontend ↔ backend end-to-end)** — ทดสอบกับ Gemini API +
> Postgres/pgvector จริง: upload → parse → segment → classify → match(RAG) → risk score →
> grounding judge → report พร้อม citation ที่ verify แล้ว ระบบ auth / DB / infra ก็ทำงานได้แล้วเช่นกัน
> **DB migrations ใช้ Alembic แล้ว** (เลิกใช้ `create_all`), **auth มี integration test
> อัตโนมัติแล้ว** (JWT + Google OAuth callback, mock ที่ authlib boundary), **contract/report repo
> ย้ายไป Redis แล้ว** (native TTL, scale ข้าม process/replica ได้จริง), และ **`/contracts/review` +
> `/contracts/{id}/override` มี integration test อัตโนมัติแล้ว**
>
> **หน้า `/contract` ต่อ backend จริงแล้ว (2026-07-21)** — เลิกใช้ mock data ทั้งหมด: อัปโหลด
> `.docx`/`.pdf` → เรียก `POST /contracts/review` จริง → แสดง clause/risk/citation จาก report
> จริง → override risk ผ่าน `POST /contracts/{id}/override` แล้ว summary กับ overall risk คำนวณใหม่
> ตาม response ทดสอบด้วย Playwright ขับ UI จริงกับ backend จริง (console error = 0)
>
> **Google login ใช้งานได้จริงแล้ว (ยืนยัน 2026-07-22)** — login ผ่านบัญชี Google จริงสำเร็จ
> (มี row จริงใน `users`: Google `sub` 21 หลัก + profile photo จาก `lh3.googleusercontent.com`),
> client id/secret ตรวจสอบกับ Google endpoint จริงแล้วว่าใช้ได้ และทุก error path (ยกเลิกที่หน้า
> consent / session หลุด) redirect กลับ `/login?error=<code>` พร้อมข้อความที่อ่านรู้เรื่อง
> ส่วนที่เหลือคือ **Sidebar menu / dashboard ยังเป็น stub** — ดู
> [README ของ backend](apps/backend-fastapi/README.md) สำหรับรายละเอียด

## โครงสร้าง repo (monorepo)

| ส่วน | เทคโนโลยี | คำอธิบาย |
|------|-----------|----------|
| `apps/backend-fastapi` | FastAPI, SQLAlchemy, Postgres/pgvector, Redis, Gemini | API + review pipeline (ดู [README ของ backend](apps/backend-fastapi/README.md)) |
| `apps/web` | React 19, Vite, Tailwind, react-router | Frontend (login, onboarding, หน้า review สัญญา) |
| `infrastructure` | Docker Compose | Postgres (pgvector) + Redis + api |

---

## ✅ สิ่งที่ทำแล้ว

| ส่วน | รายการ | รายละเอียด |
|------|--------|------------|
| Backend | App + entrypoint | FastAPI factory `app.main:app`, CORS, `SessionMiddleware` — boot ได้ |
| Backend | Health endpoints | `GET /`, `/health`, `/health/db` (ต่อ Postgres จริง → connected) |
| Backend | DB layer | SQLAlchemy engine/session/`Base`, `get_db` |
| Backend | **Alembic migrations** | แทน `create_all` แล้ว — `env.py` ดึง URL จาก app settings, migration แรกครอบ `users`/`playbook_embeddings`(+`CREATE EXTENSION vector`)/`audit_overrides`, ทดสอบ upgrade/downgrade cycle จริงแล้ว |
| Backend | Auth (OAuth + JWT) | routes `/auth/*` ครบ, User model — **integration test อัตโนมัติแล้ว**: JWT ถูก→คืน user, token ปลอม/ไม่มี user→`401`, OAuth login redirect + callback (create/update user, ออก JWT, error path) — mock ที่ authlib boundary |
| Backend | **Review pipeline** | `POST /contracts/review` — **ทดสอบ live กับ Gemini + pgvector จริงแล้ว** + integration test อัตโนมัติ (mocked LLM): parse→segment→classify→match(RAG)→score→judge→report พร้อม citation ที่ grounded |
| Backend | **Override + audit** | `POST /contracts/{id}/override` — เปลี่ยน risk level, re-aggregate, เขียน audit log ลง Postgres (ทดสอบแล้ว + integration test อัตโนมัติ) |
| Backend | **Redis-backed repos** | contract/report repo ย้ายจาก in-memory ไป Redis แล้ว (native TTL) — scale ข้าม process/replica ได้ |
| Backend | **Playbook search + eval** | `GET /playbook/search`, `POST /evaluate` — ใช้งานได้จริง |
| Backend | LLM client + RAG | Gemini client (structured output), hybrid retrieval (pgvector cosine + BM25) |
| Backend | Parsers | PDF (PyMuPDF) / DOCX (python-docx) → `ParsedDocument` |
| Backend | Guardrails | grounding, citation validity, no-invented-fallback — wired เข้า judge แล้ว |
| Backend | Schemas | Pydantic models: clause, report, taxonomy, playbook, eval |
| Backend | Data fixtures | taxonomy (12 clause types), playbook positions (ingest แล้ว), gold annotations + contract text ที่ตรงกัน |
| Backend | Tests | 46 unit/integration tests ผ่านหมด |
| Frontend | Scaffold | React 19 + Vite + Tailwind + routing (`/login`, `/auth/callback`, `/manual`, `/contract`) |
| Frontend | Login UI | หน้า login + components (Google button, brand header, card, ฯลฯ) |
| Frontend | Auth flow | ต่อกับ backend ครบ: login redirect → callback เก็บ token → `fetchCurrentUser` (`/auth/me`), `RequireAuth` guard, logout |
| Frontend | Welcome page | หน้า `/manual` (onboarding) + Sidebar — ปุ่ม Start พาไป `/contract` แล้ว |
| Frontend | **API client layer** | `lib/api.ts` (bearer auth, แปลง error ทั้ง `{error,message}` และ `{detail}` ของ backend, 401 เคลียร์ token อัตโนมัติ) + `lib/contracts.ts` (DTO ตรงกับ `app/schemas/*` + mapper → view model) |
| Frontend | **Contract upload UI** | `/contract` — อัปโหลด `.pdf`/`.docx` ไป `POST /contracts/review` จริง พร้อม loading / error / empty state (จำกัดนามสกุลตามที่ backend parse ได้จริง) |
| Frontend | **Risk report view** | แสดง clause list พร้อม risk badge, excerpt, AI rationale, suggested fallback, citation (playbook position + excerpt), grounding verdict ของ judge และ disclaimer จาก report |
| Frontend | **Override UI** | sidebar ต่อ `POST /contracts/{id}/override` จริง — validate ก่อนส่ง, response แทน state ทั้งก้อน, summary/overall risk อัปเดตตาม |
| Infra | Docker Compose | ยก Postgres (pgvector) + Redis ได้จริง |

---

## ❌ สิ่งที่ยังไม่ทำ

| ส่วน | รายการ | รายละเอียด |
|------|--------|------------|
| Backend | Contract metadata | ยังไม่ดึงคู่สัญญา / วันที่ / มูลค่าสัญญา ออกมาจากเอกสาร — `ContractReviewReport` ไม่มีฟิลด์พวกนี้ (UI จึงไม่แสดง แทนที่จะเดาข้อมูลเอง) |
| Backend | Accept risk | มีแต่ override + audit log ยังไม่มี endpoint สำหรับ "accept" — ฝั่ง UI จึงเก็บเป็น local review progress เท่านั้น |
| Backend | Export report | ยังไม่มี endpoint export รายงาน (PDF/CSV) |
| Frontend | Dashboard / Reports | เมนู Sidebar (Upload, Risk Assessment, Reports ฯลฯ) ยังเป็น `console.log` stub |
| Frontend | ประวัติรายงานย้อนหลัง | backend ไม่มี `GET /contracts/{id}` — report อยู่ใน state ของหน้าเท่านั้น refresh แล้วหาย |

---

## Quick start

```bash
# 1) ยก infra (Postgres + Redis)
docker compose -f infrastructure/docker-compose.yml up -d postgres redis

# 2) backend
cd apps/backend-fastapi
pip install -e ".[dev]"          # ต้องมีไฟล์ .env ก่อน (ดู README ของ backend)
alembic upgrade head              # สร้าง extension `vector` + ตารางทั้งหมด
python -m scripts.ingest_playbook  # โหลด playbook เข้า pgvector ก่อนใช้ /contracts/review
uvicorn app.main:app --reload    # http://localhost:8000/docs

# 3) frontend
cd apps/web
pnpm install
echo "VITE_API_BASE_URL=http://localhost:8000" > .env   # ชี้ไป backend
pnpm dev                         # http://localhost:5173
```

จากนั้น login ที่ `/login` (Google OAuth) → เด้งกลับมาที่ `/auth/callback` เก็บ JWT → `/manual`
→ กด **Start** → `/contract` แล้วอัปโหลดสัญญาได้เลย

> ⚠️ `/contract` อยู่หลัง `RequireAuth` และทุก request ต้องมี bearer token —
> ถ้าเปิดตรง ๆ โดยยังไม่ login จะถูกส่งกลับไป `/login`
>
> ⚠️ `frontend_url` ใน `.env` ของ backend ต้องตรงกับ origin ของ frontend (`http://localhost:5173`)
> ไม่งั้น CORS จะบล็อก

รายละเอียด env / setup / roadmap ของ backend: [`apps/backend-fastapi/README.md`](apps/backend-fastapi/README.md)

---

## สัญญาระหว่าง Frontend ↔ Backend

ฝั่ง frontend แปลง DTO ของ backend เป็น view model ที่ `apps/web/src/lib/contracts.ts`
ที่เดียว — component อื่นไม่ต้องรู้จัก snake_case หรือ shape ของ API เลย

| Endpoint | ใช้ที่ไหน | หมายเหตุ |
|----------|-----------|----------|
| `POST /contracts/review` | อัปโหลดสัญญา | `multipart/form-data` field ชื่อ `file` |
| `POST /contracts/{report_id}/override` | override risk | รับค่าเป็น **query params** (`clause_id`, `new_risk`, `reason`) ไม่ใช่ body — คืน report ทั้งก้อนที่อัปเดตแล้ว |
| `GET /auth/me` | โหลดข้อมูล user | |

**ข้อควรระวังที่ทำให้ frontend เพี้ยนได้ (เจอมาแล้วตอนต่อจริง):**

- **Risk level มีแค่ `low` / `medium` / `high` / `unknown`** (ตัวเล็ก) — ไม่มี `CRITICAL`
  และ `unknown` เกิดขึ้นจริงเมื่อ pipeline วิเคราะห์ clause นั้นไม่สำเร็จ ต้องมีทางแสดงผลเสมอ
- **`citations` ว่างและ `suggested_fallback` เป็น `null` ได้** เมื่อ playbook ไม่มีจุดยืนที่ตรงกัน
- **`heading` มักเป็นข้อความ clause ทั้งย่อหน้า** ไม่ใช่หัวข้อสั้น ๆ — ถ้าเอาไปใช้เป็น title ตรง ๆ
  จะได้ย่อหน้ายาวเป็นหัวข้อ (mapper จึงเลือกจาก `clause_type` ก่อน แล้วค่อย fallback ไปดึงหัวข้อ
  จากต้นประโยค รองรับรูปแบบ `"ข้อ 5. ..."` ภาษาไทยด้วย)
- **รับเฉพาะ `.pdf` และ `.docx`** — นามสกุลอื่น backend ตอบ `422 document_parse_error`
- **`ContractReviewReport` ไม่มี metadata ของสัญญา** (คู่สัญญา / วันที่ / มูลค่า) — อย่าเดาข้อมูลพวกนี้
  ขึ้นมาแสดงเอง
- **การ review ใช้เวลาราว 1 นาที** (วัดได้ ~83 วิ สำหรับ 3 clause) — ต้องมี loading state ที่ชัดเจน

---

## Roadmap ที่เหลือ

เส้นทางหลัก (login → upload → review → override) ใช้งานได้จริงครบแล้ว — เหลือ:

1. **เก็บ/ดูรายงานย้อนหลัง** — เพิ่ม `GET /contracts/{report_id}` ฝั่ง backend แล้วให้ frontend
   deep-link เข้ารายงานเดิมได้ (ตอนนี้ refresh แล้ว report หาย)
2. **Export Report** — ยังไม่มีทั้ง endpoint และปุ่ม
3. **Accept risk แบบ persist** — ต้องมี endpoint + audit ฝั่ง backend ก่อน ตอนนี้เป็น local state
5. **Sidebar / dashboard** — เมนูยังเป็น `console.log` stub
6. **Contract metadata extraction** — ถ้าอยากได้ panel คู่สัญญา/วันที่/มูลค่า ต้องให้ pipeline
   สกัดออกมาใส่ `ContractReviewReport` ก่อน
