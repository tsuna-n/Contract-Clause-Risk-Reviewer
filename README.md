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
>
> **เลิกใช้ mock data ทั้งระบบ + ประวัติรายงานใช้งานได้ (2026-07-26)** — fixture ของ backend
> สร้างจาก **CUAD v1** (สัญญาการค้าจริง 510 ฉบับ annotate โดยผู้เชี่ยวชาญ) ผ่าน
> `scripts/build_cuad_fixtures.py`, playbook ขยายเป็น 36 จุดยืนครอบทั้ง 12 clause type,
> ฝั่ง frontend ตัด `infroData` (รายการแชทปลอม 5 รายการ) กับหน้าอัปโหลดที่แกล้งเดิน progress bar
> ทิ้งทั้งหมด แล้วต่อกับ **`GET /contracts`** / **`GET /contracts/{id}`** ที่เพิ่งเพิ่มเข้าไป —
> refresh แล้วรายงานไม่หายอีกต่อไป ดู [README ของ backend](apps/backend-fastapi/README.md)
> สำหรับรายละเอียด

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
| Backend | **Report history** | `GET /contracts` (สรุปรายงานของ session เรียงใหม่→เก่า) + `GET /contracts/{report_id}` (ฉบับเต็ม) — Redis เก็บ sorted set ต่อ session เป็น index, รายงานของคนอื่นตอบ `404` ไม่ใช่ `403` |
| Backend | **Data fixtures จาก CUAD** | `scripts/build_cuad_fixtures.py` แปลง CUAD v1 → สัญญาจริง 12 ฉบับ + gold 327 clause (91 clause มี label จาก annotation ของผู้เชี่ยวชาญ) + `.docx` ให้ลองอัปโหลด 3 ไฟล์ |
| Backend | **Playbook 36 จุดยืน** | ครบทั้ง 12 clause type อ้างอิงหมวดรีวิว 41 หมวดของ CUAD — `preferred`/`fallback` เป็นภาษาสัญญาจริงที่ guardrail ใช้เทียบ verbatim ได้ |
| Backend | Tests | 82 unit/integration tests ผ่านหมด |
| Frontend | Scaffold | React 19 + Vite + Tailwind + routing (`/login`, `/auth/callback`, `/manual`, `/contract`) |
| Frontend | Login UI | หน้า login + components (Google button, brand header, card, ฯลฯ) |
| Frontend | Auth flow | ต่อกับ backend ครบ: login redirect → callback เก็บ token → `fetchCurrentUser` (`/auth/me`), `RequireAuth` guard, logout |
| Frontend | **หน้าหลัก `/manual`** | ประวัติการตรวจจริงจาก `GET /contracts` ทางซ้าย (risk badge + จำนวน clause + วันที่) และอัปโหลด/รายงานทางขวา — ไม่มี mock data เหลือแล้ว |
| Frontend | **หน้าอัปโหลด** | ยิง `POST /contracts/review` จริง หลายไฟล์พร้อมกันได้ แต่ละไฟล์มีสถานะของตัวเอง (กำลังตรวจ / สำเร็จ / ล้มเหลวพร้อมเหตุผล) — ไม่มี progress bar ปลอมแล้ว |
| Frontend | **Detail + ภาพรวม** | กางดู clause ทีละข้อพร้อม rationale/citation/grounding verdict, แผงภาพรวมสรุปการกระจายความเสี่ยงและประเภท clause ที่พบ |
| Frontend | **Deep link เข้ารายงานเดิม** | `/contract?report=<id>` โหลดรายงานที่เก็บไว้มา override ต่อได้ — refresh ไม่หาย |
| Frontend | **API client layer** | `lib/api.ts` (bearer auth, แปลง error ทั้ง `{error,message}` และ `{detail}` ของ backend, 401 เคลียร์ token อัตโนมัติ) + `lib/contracts.ts` (DTO ตรงกับ `app/schemas/*` + mapper → view model) |
| Frontend | **Contract upload UI** | `/contract` — อัปโหลด `.pdf`/`.docx` ไป `POST /contracts/review` จริง พร้อม loading / error / empty state (จำกัดนามสกุลตามที่ backend parse ได้จริง) |
| Frontend | **Risk report view** | แสดง clause list พร้อม risk badge, excerpt, AI rationale, suggested fallback, citation (playbook position + excerpt), grounding verdict ของ judge และ disclaimer จาก report |
| Frontend | **Override UI** | sidebar ต่อ `POST /contracts/{id}/override` จริง — validate ก่อนส่ง, response แทน state ทั้งก้อน, summary/overall risk อัปเดตตาม |
| Frontend | **Export report** | ปุ่ม Export ทั้งหน้า `/contract` และหน้ารายงานใน `/manual` — **JSON** (รายงานเต็ม), **CSV** (แถวละ clause พร้อม BOM ให้ Excel อ่านภาษาไทยถูก + กัน CSV injection), และ **Print / Save as PDF** (`PrintableReport` portal ลง `<body>` แล้ว print stylesheet สลับมาแสดงแทนทั้งแอป) — ทำฝั่ง browser ล้วน ไม่ต้องมี endpoint |
| Frontend | **เตือนเมื่อ clause ประเมินไม่สำเร็จ** | รายงานที่มี `unknown` ขึ้น banner ระดับรายงานว่า "ยังไม่ได้วิเคราะห์ ไม่ใช่ว่าไม่มีความเสี่ยง" พร้อมบอกสาเหตุที่พบบ่อย (โควตา Gemini หมด) — badge สีเทารายข้ออ่านเหมือน "ผ่าน" ได้ง่ายเกินไป |
| Infra | Docker Compose | ยก Postgres (pgvector) + Redis ได้จริง |

---

## ❌ สิ่งที่ยังไม่ทำ

| ส่วน | รายการ | รายละเอียด |
|------|--------|------------|
| Backend | Contract metadata | ยังไม่ดึงคู่สัญญา / วันที่ / มูลค่าสัญญา ออกมาจากเอกสาร — `ContractReviewReport` ไม่มีฟิลด์พวกนี้ (UI จึงไม่แสดง แทนที่จะเดาข้อมูลเอง) |
| Backend | Accept risk | มีแต่ override + audit log ยังไม่มี endpoint สำหรับ "accept" — ฝั่ง UI จึงเก็บเป็น local review progress เท่านั้น |
| Backend | Export report (server-side) | ยังไม่มี endpoint export — ฝั่ง frontend ทำ JSON/CSV/Print เองได้แล้วจากรายงานที่อยู่ในเบราว์เซอร์ จะต้องมี endpoint ก็ต่อเมื่ออยาก export โดยไม่เปิดหน้าเว็บ (เช่น ส่งเมล/แบตช์) |
| Backend | เก็บรายงานถาวร | รายงานอยู่ใน Redis ตาม `retention_ttl_seconds` — ประวัติเป็น "ย้อนหลังเท่าที่ยังไม่หมดอายุ" ไม่ใช่คลังถาวร ถ้าต้องเก็บยาวต้องย้ายไป Postgres |
| Backend | Clause-level accuracy ที่วัดแล้ว | gold set พร้อมใช้แล้วแต่ยังไม่ได้รัน `POST /evaluate` เต็มชุด (327 clause ≈ 1,300 LLM call) — โควตา Gemini free tier อยู่ที่ 20 request/วัน |

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
→ อัปโหลดสัญญาได้เลย

> ⚠️ `/contract` อยู่หลัง `RequireAuth` และทุก request ต้องมี bearer token —
> ถ้าเปิดตรง ๆ โดยยังไม่ login จะถูกส่งกลับไป `/login`
>
> ⚠️ `frontend_url` ใน `.env` ของ backend ต้องตรงกับ origin ของ frontend (`http://localhost:5173`)
> ไม่งั้น CORS จะบล็อก

รายละเอียด env / setup / roadmap ของ backend: [`apps/backend-fastapi/README.md`](apps/backend-fastapi/README.md)

---

## เปิดจากมือถือ / เครื่องอื่นใน LAN

ต้องแก้ 4 จุดให้ชี้ที่ **IP ของเครื่อง dev** (ดูด้วย `ip -4 -o addr show scope global`) ไม่ใช่ `localhost`
— เพราะเบราว์เซอร์บนมือถือ resolve `localhost` เป็นตัวมันเอง ไม่ใช่เครื่อง dev:

| ที่ | ต้องเป็น |
|-----|----------|
| `apps/web/.env` → `VITE_API_BASE_URL` | `http://<LAN_IP>:8000` |
| `apps/backend-fastapi/.env` → `FRONTEND_URL` | `http://<LAN_IP>:5173` (ใช้เป็น CORS allow-list ด้วย) |
| uvicorn | `--host 0.0.0.0` (default ผูกแค่ 127.0.0.1 เครื่องอื่นต่อไม่ได้) |
| vite | `server.host: true` — ตั้งไว้ใน `vite.config.ts` แล้ว |

จากนั้นเปิด `http://<LAN_IP>:5173` บนมือถือได้เลย

> ### ⚠️ Google login ใช้ผ่าน LAN **ไม่ได้** และแก้ที่ฝั่งเราไม่ได้
>
> Google รับ redirect URI แค่ 2 แบบ: loopback (`http://localhost`, `http://127.0.0.1`)
> หรือ **https บนโดเมนจริง** — private IP บน http โดนปฏิเสธตั้งแต่ต้น
> ทดสอบกับ endpoint จริงของ Google ด้วย client id ของโปรเจกต์นี้แล้ว (2026-07-26):
>
> | redirect_uri | ผลจาก Google |
> |--------------|--------------|
> | `http://localhost:8000/auth/google/callback` | ✅ ขึ้นหน้า Sign in |
> | `http://127.0.0.1:8000/auth/google/callback` | ⚠️ `redirect_uri_mismatch` — รูปแบบผ่าน แค่ยังไม่ได้ลงทะเบียนใน Console |
> | `http://172.20.10.2:8000/auth/google/callback` | ❌ `invalid_request` — **ลงทะเบียนใน Console ไม่ได้เลย** |
>
> error สองตัวนี้ต่างกันและนั่นคือหลักฐาน: IP ใน LAN ไม่ได้แค่ "ยังไม่ลงทะเบียน" แต่ Google
> ไม่ยอมรับรูปแบบนี้ตั้งแต่แรก และเพราะมันพังตั้งแต่ก่อนถึงหน้า consent → callback ของเราไม่ถูกเรียก
> → ไม่มีอะไร redirect กลับ `/login?error=...` ผู้ใช้เลยค้างอยู่ที่หน้า error ของ Google
>
> **หน้า `/login` จึงตรวจให้แล้ว** — ถ้า `VITE_API_BASE_URL` ไม่ใช่ loopback/https ปุ่ม
> "Continue with Google" จะถูก disable พร้อมบอกเหตุผล แล้วดัน **Dev Mode Quick Sign In**
> (`GET /auth/dev-login` → JWT ทันที) ขึ้นมาเป็นปุ่มหลักแทน
>
> ถ้าอยากได้ Google login จริงผ่านมือถือ ต้องมี **HTTPS บนโดเมนจริง** — ทางที่ง่ายสุดคือ tunnel
> (`cloudflared` / `ngrok`) แล้วเอา URL ที่ได้ไปใส่ทั้ง Authorized redirect URI ใน Google Console,
> `GOOGLE_REDIRECT_URI` และ `VITE_API_BASE_URL` (ยังไม่ได้ติดตั้ง tunnel ตัวไหนไว้ในเครื่องนี้)

> ### 🔓 `/auth/dev-login` เปิดประตูทิ้งไว้
>
> endpoint นี้ออก JWT ให้ **อีเมลอะไรก็ได้ที่ส่งมา** โดยไม่ตรวจอะไรเลย
> (`?email=someone@example.com`) กันไว้แค่ `APP_ENV != development` เท่านั้น — ระหว่างเปิด LAN
> ใครก็ตามที่อยู่วงเดียวกันล็อกอินเป็นใครก็ได้ ใช้เฉพาะตอน dev และอย่า deploy โดยที่ `APP_ENV`
> ยังเป็น `development`

---

## สัญญาระหว่าง Frontend ↔ Backend

ฝั่ง frontend แปลง DTO ของ backend เป็น view model ที่ `apps/web/src/lib/contracts.ts`
ที่เดียว — component อื่นไม่ต้องรู้จัก snake_case หรือ shape ของ API เลย

| Endpoint | ใช้ที่ไหน | หมายเหตุ |
|----------|-----------|----------|
| `POST /contracts/review` | หน้าอัปโหลด (`/manual`) และ `/contract` | `multipart/form-data` field ชื่อ `file` — คืน report ฉบับเต็มเลย ไม่ต้องดึงซ้ำ |
| `GET /contracts` | ประวัติใน Sidebar | คืน **`ReportSummary`** (ไม่มี `reviews`) เรียงใหม่→เก่า |
| `GET /contracts/{report_id}` | เปิดรายงานเดิม / deep link `?report=` | รายงานของ session อื่นตอบ `404` |
| `POST /contracts/{report_id}/override` | override risk | รับค่าเป็น **JSON body** (`clause_id`, `new_risk`, `reason`) — คืน report ทั้งก้อนที่อัปเดตแล้ว |
| `GET /playbook`, `POST/PUT/DELETE /playbook/{id}`, `GET /playbook/search` | หน้า `/playbook` | |
| `POST /evaluate` | หน้า `/evaluate` | |
| `GET /`, `/health`, `/health/db` | หน้า `/system` | |
| `GET /auth/me` | โหลดข้อมูล user | |

**ข้อควรระวังที่ทำให้ frontend เพี้ยนได้ (เจอมาแล้วตอนต่อจริง):**

- **Risk level มีแค่ `low` / `medium` / `high` / `unknown`** (ตัวเล็ก) — ไม่มี `CRITICAL`
  และ `unknown` เกิดขึ้นจริงเมื่อ pipeline วิเคราะห์ clause นั้นไม่สำเร็จ ต้องมีทางแสดงผลเสมอ
- **`citations` ว่างและ `suggested_fallback` เป็น `null` ได้** เมื่อ playbook ไม่มีจุดยืนที่ตรงกัน
- **`heading` มักเป็นข้อความ clause ทั้งย่อหน้า** ไม่ใช่หัวข้อสั้น ๆ — ถ้าเอาไปใช้เป็น title ตรง ๆ
  จะได้ย่อหน้ายาวเป็นหัวข้อ (mapper จึงเลือกจาก `clause_type` ก่อน แล้วค่อย fallback ไปดึงหัวข้อ
  จากต้นประโยค รองรับรูปแบบ `"ข้อ 5. ..."` ภาษาไทยด้วย)
- **รับเฉพาะ `.pdf` และ `.docx`** — นามสกุลอื่น backend ตอบ `422 document_parse_error`
  (ดูตาราง [ไฟล์สัญญาแบบไหนใช้ได้](#ไฟล์สัญญาแบบไหนใช้ได้) ด้านล่าง)
- **`ContractReviewReport` ไม่มี metadata ของสัญญา** (คู่สัญญา / วันที่ / มูลค่า) — มีแค่ `filename`
  ที่ติดมากับการอัปโหลด อย่าเดาข้อมูลพวกนี้ขึ้นมาแสดงเอง
- **การ review ใช้เวลาหลายนาที ไม่ใช่หลักวินาที** — วัดจริงได้ ~45 วิ/clause (83 วิ สำหรับ 3 clause,
  **6 นาที 15 วิ สำหรับ 8 clause** วัดเมื่อ 2026-07-28) เพราะ pipeline เดินทีละ clause และยิง LLM
  ~4 ครั้งต่อ clause — ต้อง loading state ที่ชัดเจนและอย่าเขียนว่า "about a minute"
- **Export ทำฝั่ง browser ล้วน** — ไม่มี endpoint และไม่ต้องมี: ตอนรายงานขึ้นจอแล้ว `ContractReport`
  อยู่ใน memory ครบ เหลือแค่ serialize (`lib/export.ts`) สิ่งเดียวที่ไม่ติดไปคือ `span.start/end`
  ซึ่ง mapper ตัดทิ้งตั้งแต่ก่อนถึง UI อยู่แล้ว
- **โควตา Gemini หมดแล้วยังตอบ `200`** — pipeline แยก failure ของแต่ละ clause ออกจากกัน (ตั้งใจ)
  ดังนั้นเมื่อโดน `429` ทั้งฉบับ จะได้ report ที่ทุก clause เป็น `unknown` พร้อม rationale ว่า
  "Automated review failed for this clause" ไม่ใช่ error ระดับ request — UI ต้องแสดง `unknown`
  ให้เห็นชัด อย่าตีความว่า "ไม่มีความเสี่ยง"

---

## ไฟล์สัญญาแบบไหนใช้ได้

ทดสอบจริงกับ parser + segmenter ของ backend (2026-07-28) — ผลตามนี้:

| ไฟล์ | ผล | หมายเหตุ |
|------|-----|----------|
| `.docx` / `.pdf` หัวข้อเลขอังกฤษ (`1. Confidentiality`) | ✅ ดีที่สุด | ตัด clause ตามหัวข้อ ตรงตามข้อสัญญาจริง |
| `.docx` / `.pdf` หัวข้อไทย (`ข้อ 1.` / `1. การรักษาความลับ`) | ⚠️ ใช้ได้แต่ตัดหยาบ | ตกไปใช้ **paragraph fallback** — 1 ย่อหน้า = 1 clause |
| หัวข้อพิมพ์เล็ก / bullet / `ARTICLE I` / `Section 4.` | ⚠️ ใช้ได้แต่ตัดหยาบ | paragraph fallback เหมือนกัน |
| **PDF สแกน / ถ่ายรูป (ไม่มี text layer)** | ❌ ได้รายงานเปล่า | backend ตอบ `200` แต่ได้ **0 clause** — UI ขึ้น banner เตือนแล้ว ต้อง OCR ก่อน |
| PDF ใส่รหัสผ่าน | ❌ `422` | `document closed or encrypted` — ต้องปลดรหัสก่อน |
| `.doc` (Word เก่า) / `.txt` / `.rtf` / ไม่มีนามสกุล | ❌ `422` | `unsupported file type` — ต้อง Save As เป็น `.docx` หรือ `.pdf` |

**ทำไมหัวข้อไทยถึงตัดหยาบ:** ตัวตัด clause ใช้ regex `^\s*(\d+(\.\d+)*)[.)]?\s+[A-Z]` ใน
`app/parsers.py` ซึ่งบังคับว่าต้องเป็น **อักษรอังกฤษตัวใหญ่ A–Z** ต่อท้ายเลขข้อ ตัวอักษรไทยจึงไม่เข้า
เงื่อนไข (`\d` รับเลขไทย `๑` ได้ แต่ `[A-Z]` ไม่รับ `ค`) — ยังใช้งานได้เพราะมี paragraph fallback
แต่ขอบเขต clause จะตามย่อหน้าแทนที่จะตามข้อสัญญา ถ้าจะรองรับสัญญาไทยเต็มที่ต้องแก้ regex ตัวนี้

> ⚠️ **ยังไม่มีการจำกัดขนาดไฟล์** — route อ่านไฟล์ทั้งก้อนเข้า memory (`await file.read()`)
> ไฟล์ใหญ่มากจะกินแรมและใช้เวลานาน (ราว 45 วิ/clause)

---

## Roadmap ที่เหลือ

เส้นทางหลัก (login → upload → review → override → export → เปิดรายงานเดิม) ใช้งานได้จริงครบแล้ว
— ที่เหลือทุกข้อต้องแก้ฝั่ง backend ก่อน ทำใน frontend อย่างเดียวไม่ได้:

1. **Accept risk แบบ persist** — ต้องมี endpoint + audit ฝั่ง backend ก่อน ตอนนี้เป็น local state
2. **เก็บรายงานถาวร** — ตอนนี้อยู่ใน Redis ตาม TTL หมดอายุแล้วหายจากประวัติ ถ้าต้องเก็บยาว
   ต้องมีตารางใน Postgres
3. **Contract metadata extraction** — ถ้าอยากได้ panel คู่สัญญา/วันที่/มูลค่า ต้องให้ pipeline
   สกัดออกมาใส่ `ContractReviewReport` ก่อน (CUAD มี annotation หมวด Parties / Agreement Date /
   Effective Date อยู่แล้ว ใช้เป็น gold set ได้ทันที)
4. **รัน evaluation เต็มชุด** — gold set 12 ฉบับพร้อมแล้ว แต่ต้องมีโควตา Gemini พอ
