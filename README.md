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
> **รายงานถาวร + accept risk + metadata ของสัญญา (2026-07-30)** — เคลียร์ roadmap ที่ค้างอยู่
> 3 ข้อ: รายงานย้ายจาก Redis (TTL) ไปเก็บใน **Postgres** ถาวรแล้ว (ตาราง `contract_reports`,
> หายเมื่อเจ้าของสั่งลบเท่านั้น — สลับกลับด้วย `REPORT_STORAGE=redis` ได้), เพิ่ม
> **`POST /contracts/{id}/accept`** ให้ผู้ตรวจ "รับรอง" ข้อสัญญาได้จริงพร้อมลง audit log
> (ถอนคืนได้ และ override จะล้างการรับรองให้เอง), และ pipeline **สกัด metadata ของสัญญา**
> (คู่สัญญา / วันที่ / มูลค่า / กฎหมายที่ใช้บังคับ) มาแสดงเป็นแผงหัวรายงาน โดยทุกค่าต้องเป็น
> ข้อความที่อยู่ในเอกสารจริงแบบคำต่อคำ ไม่งั้นถูกตัดทิ้ง
>
> **LLM call ผ่านสม่ำเสมอแล้ว + ตัดฟีเจอร์ export ออก (2026-07-30, รอบสอง)** — คอขวดที่ค้างอยู่
> ข้อแรกปิดแล้ว: ต้นเหตุคือ **thinking mode ของ GLM-4.6** ซึ่งกิน token ความคิดจากงบ `max_tokens`
> ก้อนเดียวกับคำตอบ คิดยาวเกินงบก็ได้ 200 ที่ `content` ว่างกลับมา (วัดจริง: call เดียวกัน
> 23.7 วิ/984 token ตอนเปิดคิด เทียบกับ **2.1 วิ/55 token** ตอนปิด) เพิ่ม `LLM_THINKING=disabled`
> เป็นค่า default + retry ชั้นบน SDK ที่ยิงซ้ำเฉพาะ failure ที่ถามใหม่แล้วมีโอกาสได้ ผลกับสัญญา
> ฉบับเดิมที่ eval เคยเสีย 6 ใน 8 clause: **8/8 ได้คำตอบ ไม่มีข้อไหนล้มเพราะ provider** และเร็วขึ้น
> จาก 47 วิ/clause เป็น 22.5 วิ/clause พร้อมกันนั้น**ตัดฟีเจอร์ export ออกทั้งหมด** (JSON/CSV/Print
> ฝั่งเบราว์เซอร์ + แผนทำ endpoint ฝั่ง server) และเพิ่ม **job ลบรายงานตามอายุ**
> (`scripts/purge_reports.py`) ซึ่งเป็น roadmap ข้อสุดท้ายที่ค้าง
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
| `apps/backend-fastapi` | FastAPI, SQLAlchemy, Postgres/pgvector, Redis, LLM (Gemini / Claude / OpenAI-compatible) | API + review pipeline (ดู [README ของ backend](apps/backend-fastapi/README.md)) |
| `apps/web` | React 19, Vite, Tailwind, react-router | Frontend (login, onboarding, หน้า review สัญญา) |
| `infrastructure` | Docker Compose | Postgres (pgvector) + Redis + api |

---

## ✅ สิ่งที่ทำแล้ว

| ส่วน | รายการ | รายละเอียด |
|------|--------|------------|
| Backend | App + entrypoint | FastAPI factory `app.main:app`, CORS, `SessionMiddleware` — boot ได้ |
| Backend | Health endpoints | `GET /`, `/health`, `/health/db` (ต่อ Postgres จริง → connected) |
| Backend | DB layer | SQLAlchemy engine/session/`Base`, `get_db` |
| Backend | **Alembic migrations** | แทน `create_all` แล้ว — `env.py` ดึง URL จาก app settings; 3 migration: initial (`users`/`playbook_embeddings`+`CREATE EXTENSION vector`/`audit_overrides`) → `contract_reports` → `audit_overrides.action` ทุกตัวทดสอบ upgrade/downgrade cycle กับ Postgres จริงแล้ว |
| Backend | Auth (OAuth + JWT) | routes `/auth/*` ครบ, User model — **integration test อัตโนมัติแล้ว**: JWT ถูก→คืน user, token ปลอม/ไม่มี user→`401`, OAuth login redirect + callback (create/update user, ออก JWT, error path) — mock ที่ authlib boundary |
| Backend | **Review pipeline** | `POST /contracts/review` — **ทดสอบ live กับ Gemini + pgvector จริงแล้ว** + integration test อัตโนมัติ (mocked LLM): parse→segment→classify→match(RAG)→score→judge→report พร้อม citation ที่ grounded |
| Backend | **Override + audit** | `POST /contracts/{id}/override` — เปลี่ยน risk level, re-aggregate, เขียน audit log ลง Postgres (ทดสอบแล้ว + integration test อัตโนมัติ) |
| Backend | **Accept risk (persist)** | `POST /contracts/{id}/accept` — ผู้ตรวจรับรองข้อสัญญาทีละข้อ เก็บ `accepted`/`accepted_by`/`accepted_at` ไว้ในรายงาน (refresh ไม่หาย), ถอนคืนได้ (`accepted=false`), ลง audit log ทั้งสองทิศทาง (`action` = `accept`/`unaccept`) และ override จะล้างการรับรองให้อัตโนมัติเพราะเป็นการรับรองคำตัดสินเดิม |
| Backend | **เก็บรายงานถาวร (Postgres)** | ตาราง `contract_reports` (payload JSONB + คอลัมน์ที่ history ใช้จริง) — ไม่มีวันหมดอายุ, `GET /contracts` อ่านจากคอลัมน์ไม่ต้อง deserialize รายงานทั้งฉบับ; `REPORT_STORAGE=redis` กลับไปใช้แบบ TTL เดิมได้ |
| Backend | **Contract metadata** | agent `MetadataExtractor` ยิง LLM 1 ครั้งต่อ**ฉบับ** (ไม่ใช่ต่อ clause) อ่านหัว+ท้ายเอกสาร → คู่สัญญา / วันที่ทำสัญญา / วันมีผล / วันสิ้นสุด / มูลค่า / กฎหมายที่ใช้บังคับ; ทุกค่าถูกเช็คกับตัวเอกสารแบบคำต่อคำ ค่าที่หาไม่เจอถูกทิ้ง (`ENABLE_METADATA_EXTRACTION=false` ปิดได้) |
| Backend | **Redis-backed repos** | contract repo อยู่บน Redis (native TTL) — ตัว report repo ย้ายไป Postgres แล้ว แต่ Redis ยังเป็นตัวเลือกอยู่ |
| Backend | **Playbook search + eval** | `GET /playbook/search`, `POST /evaluate` — ใช้งานได้จริง |
| Backend | **LLM client + RAG (สลับค่ายได้)** | provider adapter (`app/ai/providers.py`) — Gemini / Anthropic Claude / OpenAI-compatible (Z.AI GLM, DeepSeek, vLLM) เลือกด้วย `LLM_PROVIDER` ตัวเดียว, structured output ตามวิธีของแต่ละค่าย, hybrid retrieval (pgvector cosine + BM25) |
| Backend | **LLM call ทนทานขึ้น** | `LLM_THINKING=disabled` (default) ปิด thinking ของ reasoning model ที่กินงบ `max_tokens` จนตอบว่าง + retry ชั้นบน SDK เฉพาะ failure ที่ถามใหม่แล้วมีโอกาสได้ (timeout/429/5xx/คำตอบว่าง/JSON พัง) จำกัดด้วย `LLM_MAX_ATTEMPTS` และงบเวลา 1 timeout — 400/401 ไม่ retry |
| Backend | **Data-retention job** | `python -m scripts.purge_reports` ลบรายงานเก่ากว่า `REPORT_RETENTION_DAYS` (`--dry-run` นับก่อนได้) — ต้องตั้ง cron เอง เพราะการลบข้อมูลของคนอื่นไม่ควรเป็นผลพลอยได้ของ request |
| Backend | **Guardrail + สิทธิ์ playbook (2026-07-30)** | `is_grounded()` ไม่ใช่ substring ล้วนแล้ว — judge บังคับ excerpt ยาว ≥ 4 คำ (`MIN_CITATION_EXCERPT_WORDS`) เพราะเดิมอ้าง `"the"` ก็ผ่านและได้ badge "ตรวจสอบแล้ว" ส่วน metadata ยังใช้ 1 คำเพราะค่าอย่าง `"กฎหมายไทย"` สั้นโดยธรรมชาติ; retry ตอน ungrounded ส่ง `verdict.reason` กลับเข้า prompt แล้ว (เดิมส่ง prompt เดิมเป๊ะ ๆ = จ่าย token 2 เท่าเพื่อคำตอบเดิม); เขียน playbook จำกัดด้วย `PLAYBOOK_ADMIN_EMAILS` → `403` (อ่านยังเปิดให้ทุกคนที่ login) |
| Backend | **Hardening ระดับ request (2026-07-30)** | ปิด 4 จุดที่ request เดียวยึดหรือเปิดระบบได้: **auth ระดับ router** ที่ `/playbook/*` (6 ตัว) + `/evaluate` → `401` (ประกาศที่ router ไม่ใช่รายตัว endpoint ใหม่จึงปิดเอง), **ย้าย blocking I/O ออกจาก event loop** (`def` + `run_in_threadpool` ตอน review) — วัดจริง `/health` ตอบ 1.2–2.0 ms ระหว่าง review 18.9 วิ (เดิม 2.7 s), **เพดาน `MAX_UPLOAD_BYTES` 10 MB** (อ่านแบบ bounded → `413` ไม่ buffer ก่อน) + **`MAX_CLAUSES` 300** (เช็คหลัง segment ก่อนจ่ายค่า LLM), **`gold_set_path` ต้องอยู่ใน `data/gold/`** และ **`/auth/dev-login` ต้องมี 2 กลอน** (`APP_ENV=development` + `ENABLE_DEV_LOGIN=true`) |
| Backend | Parsers | PDF (PyMuPDF) / DOCX (python-docx) / TXT (เดา encoding: UTF-8 → cp874) → `ParsedDocument` |
| Backend | Guardrails | grounding, citation validity, no-invented-fallback — wired เข้า judge แล้ว |
| Backend | Schemas | Pydantic models: clause, report, taxonomy, playbook, eval |
| Backend | **Report history** | `GET /contracts` (สรุปรายงานของตัวเอง เรียงใหม่→เก่า) + `GET /contracts/{report_id}` (ฉบับเต็ม) + `DELETE /contracts/{report_id}` — Postgres ใช้ index `(session_id, created_at)`, Redis ใช้ sorted set ต่อ session, รายงานของคนอื่นตอบ `404` ไม่ใช่ `403` |
| Backend | **Data fixtures จาก CUAD** | `scripts/build_cuad_fixtures.py` แปลง CUAD v1 → สัญญาจริง 12 ฉบับ + gold 327 clause (91 clause มี label จาก annotation ของผู้เชี่ยวชาญ) + `.docx` ให้ลองอัปโหลด 3 ไฟล์ |
| Backend | **Playbook 36 จุดยืน** | ครบทั้ง 12 clause type อ้างอิงหมวดรีวิว 41 หมวดของ CUAD — `preferred`/`fallback` เป็นภาษาสัญญาจริงที่ guardrail ใช้เทียบ verbatim ได้ |
| Backend | Tests | 258 unit/integration tests ผ่านหมด (1 skipped — eval regression gate ที่ต้องยิง LLM จริง) |
| Backend | **หัวข้อสัญญาไทย** | `_HEADING_RE` รับ `ข้อ 1.` / `๑.` / เลขอารบิกตามด้วยตัวอักษรไทย (พยัญชนะ + สระหน้า `เ แ โ ใ ไ`) และ prefix `Section`/`Article`/`Clause` — สัญญาไทยตัด clause ตามข้อจริงแทน paragraph fallback โดยอังกฤษ 12 ฉบับเดิมไม่กระทบ |
| Frontend | Scaffold | React 19 + Vite + Tailwind + routing (`/login`, `/auth/callback`, `/manual`, `/contract`) |
| Frontend | Login UI | หน้า login + components (Google button, brand header, card, ฯลฯ) |
| Frontend | Auth flow | ต่อกับ backend ครบ: login redirect → callback เก็บ token → `fetchCurrentUser` (`/auth/me`), `RequireAuth` guard, logout |
| Frontend | **หน้าหลัก `/manual`** | ประวัติการตรวจจริงจาก `GET /contracts` ทางซ้าย (risk badge + จำนวน clause + วันที่) และอัปโหลด/รายงานทางขวา — ไม่มี mock data เหลือแล้ว |
| Frontend | **หน้าอัปโหลด** | ยิง `POST /contracts/review` จริง หลายไฟล์พร้อมกันได้ แต่ละไฟล์มีสถานะของตัวเอง (กำลังตรวจ / สำเร็จ / ล้มเหลวพร้อมเหตุผล) — ไม่มี progress bar ปลอมแล้ว |
| Frontend | **Detail + ภาพรวม** | กางดู clause ทีละข้อพร้อม rationale/citation/grounding verdict, แผงภาพรวมสรุปการกระจายความเสี่ยงและประเภท clause ที่พบ |
| Frontend | **Deep link เข้ารายงานเดิม** | `/contract?report=<id>` โหลดรายงานที่เก็บไว้มา override ต่อได้ — refresh ไม่หาย |
| Frontend | **API client layer** | `lib/api.ts` (bearer auth, แปลง error ทั้ง `{error,message}` และ `{detail}` ของ backend, 401 เคลียร์ token อัตโนมัติ) + `lib/contracts.ts` (DTO ตรงกับ `app/schemas/*` + mapper → view model) |
| Frontend | **Contract upload UI** | `/contract` — อัปโหลด `.pdf`/`.docx`/`.txt` ไป `POST /contracts/review` จริง พร้อม loading / error / empty state (จำกัดนามสกุลตามที่ backend parse ได้จริง) |
| Frontend | **Risk report view** | แสดง clause list พร้อม risk badge, excerpt, AI rationale, suggested fallback, citation (playbook position + excerpt), grounding verdict ของ judge และ disclaimer จาก report |
| Frontend | **Override UI** | sidebar ต่อ `POST /contracts/{id}/override` จริง — validate ก่อนส่ง, response แทน state ทั้งก้อน, summary/overall risk อัปเดตตาม |
| Frontend | **Accept / undo จริง** | ปุ่ม Accept Risk ยิง `POST /contracts/{id}/accept` แล้ว — ✓ ในรายการข้อสัญญามาจากรายงาน ไม่ใช่ state ในหน้า, กดซ้ำเพื่อถอนคืน, มีบรรทัดบอกว่าใครรับรองเมื่อไหร่ |
| Frontend | **แผง metadata ของสัญญา** | `ContractMetadataPanel` แสดงคู่สัญญา/วันที่/มูลค่า/กฎหมาย ทั้งหน้า `/contract` และรายงานใน `/manual` — ช่องที่เอกสารไม่ได้ระบุจะไม่ขึ้นเลย (ไม่แสดงขีดกลางให้ชวนสงสัยว่าพัง) |
| Frontend | **เตือนเมื่อ clause ประเมินไม่สำเร็จ** | รายงานที่มี `unknown` ขึ้น banner ระดับรายงานว่า "ยังไม่ได้วิเคราะห์ ไม่ใช่ว่าไม่มีความเสี่ยง" พร้อมบอกสาเหตุที่พบบ่อย (โควตา Gemini หมด) — badge สีเทารายข้ออ่านเหมือน "ผ่าน" ได้ง่ายเกินไป |
| Infra | Docker Compose | ยก Postgres (pgvector) + Redis ได้จริง |

---

## ❌ สิ่งที่ยังไม่ทำ

| ส่วน | รายการ | รายละเอียด |
|------|--------|------------|
| Backend | **gold label ของ eval ยังไม่ตรงกับ clause จริง** | คอขวดของทุกตัวเลขความแม่น: label มาจาก CUAD annotation ที่บังเอิญตกอยู่ในข้อนั้น ทำให้ข้อที่ขึ้นหัวว่า `13. Warranty` เป็น gold `other` และ `9.07 Successors and Assigns` เป็น gold `payment_terms` — **classifier ตอบถูกแต่ถูกนับว่าผิด** ต้องแก้ที่วิธีสร้าง label (ใช้ span ของไฮไลต์ที่ CUAD ให้มา แทน offset ตัวเดียว) |
| Backend | integration test ที่ยิง LLM จริง | เทสต์ทั้ง 258 ตัว mock ที่ขอบ provider — บั๊กแบบ "Z.AI รับ `json_schema` แล้วตอบ markdown" ผ่าน mock ได้สบาย เจอตอนรันจริงเท่านั้น |
| Backend | Clause-level accuracy เต็มชุด | รันแล้ว 3 ฉบับ / 90 clause (gold label 26 ข้อ): `classification 57.69%`, `risk 50.00%`, `segmentation 100%`, `citation 100%`, ไม่มี clause ล้มเพราะ provider เลย — เหลือเต็มชุด 12 ฉบับ / 327 clause (≈ 1,300 call, ~2 ชม.) |
| Backend | cron ของ retention job | **ตั้งใจไม่ตั้ง** — ตัว job พร้อมใช้แล้ว (`scripts/purge_reports.py`) แต่ค่า default คือเก็บรายงานไว้จนเจ้าของสั่งลบ เพราะการลบกู้คืนไม่ได้และตัวสัญญาหายไปด้วย ให้ตั้ง `REPORT_RETENTION_DAYS` + cron ตอนมีนโยบายเก็บข้อมูลจริง (ตัวอย่าง crontab อยู่ใน docstring ของสคริปต์) |

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

## เลือกค่าย AI (สลับได้ด้วย `.env` อย่างเดียว)

`LLM_PROVIDER` ตัวเดียวเลือกได้ 4 ค่าย โดยมี adapter จริง 3 ตัวใน
[`app/ai/providers.py`](apps/backend-fastapi/app/ai/providers.py) — `zai` คือ adapter แบบ
OpenAI-compatible ที่เติม endpoint/model ของ Z.AI ให้แล้ว ตัวเดียวกันนี้จึงใช้กับ DeepSeek, Ollama,
vLLM ได้ด้วยการตั้ง `LLM_BASE_URL` เอง SDK ทั้งสามติดตั้งมาให้ครบและ `import` แบบ lazy —
**ไม่ต้องแก้โค้ด ไม่ต้อง rebuild image**

| ค่าย | `LLM_PROVIDER` | คีย์ที่ต้องมี | model default |
|------|----------------|---------------|---------------|
| Google Gemini | `gemini` | `GEMINI_API_KEY` | `gemini-3.5-flash` |
| Anthropic Claude | `anthropic` | `ANTHROPIC_API_KEY` | `claude-opus-5` |
| Z.AI (GLM) | `zai` | `ZAI_API_KEY` | `glm-4.6` |
| OpenAI-compatible | `openai` | `OPENAI_API_KEY` + `LLM_MODEL` + `LLM_BASE_URL` | — (ต้องระบุเอง) |

**ตัวอย่าง: เปลี่ยนไปใช้ Claude Haiku 4.5**

```env
# --- LLM: Anthropic (Claude Haiku 4.5) ---
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-...
LLM_MODEL=claude-haiku-4-5

# --- Embeddings: ยังเป็น Gemini (Anthropic ไม่มี embedding API) ---
EMBEDDING_PROVIDER=gemini
GEMINI_API_KEY=AIza...
EMBEDDING_MODEL=gemini-embedding-001
```

เคสนี้ **ไม่ต้อง re-ingest playbook** เพราะ embedding ยังเป็นโมเดลเดิม vector ใน pgvector จึงใช้ต่อได้
ทั้งหมด — เปลี่ยนแค่ว่าใครเป็นคนอ่านสัญญา

ตรวจว่าได้ค่ายที่ตั้งใจหลัง restart:

```bash
cd apps/backend-fastapi && .venv/bin/python -c "
from app.ai.providers import build_chat_backend
from app.ai.retrieval import build_embedder
from app.config import get_settings
b = build_chat_backend(get_settings()); e = build_embedder()
print('chat :', type(b).__name__, '->', b.model)
print('embed:', type(e).__name__, '->', e.model, f'({e.dim} dim)')
"
```

คอนฟิกที่ `.env` ของ repo นี้ใช้อยู่ตอนนี้คือ **Z.AI GLM-4.6 อ่านสัญญา + Gemini ทำ embedding**
(ผลจริงของคำสั่งด้านบน เมื่อ 2026-07-30):

```
chat : OpenAICompatibleChatBackend -> glm-4.6
embed: GeminiEmbedder -> gemini-embedding-001 (768 dim)
```

`zai` ใช้ adapter ตัวเดียวกับ `openai` ชื่อคลาสที่ขึ้นจึงเป็น `OpenAICompatibleChatBackend` —
ไม่ได้แปลว่าตั้งค่าผิด

**5 ข้อที่ต้องรู้ก่อนสลับ:**

1. **สลับค่ายแล้วต้องแก้ `LLM_MODEL` ด้วย** — ตั้ง `LLM_PROVIDER=anthropic` ทั้งที่
   `LLM_MODEL=gemini-3.5-flash` จะฟ้อง `ProviderConfigError` ตั้งแต่เรียกครั้งแรก แทนที่จะไปเจอ
   404 ของ vendor ที่ไม่บอกว่าตัวไหนผิด (ลบ `LLM_MODEL` ทิ้งก็ได้ = ใช้ default ของค่ายนั้น)
2. **คีย์ว่างถือว่าไม่ได้ตั้ง** — `ANTHROPIC_API_KEY=` เฉย ๆ จะฟ้องทันทีว่าตัวไหนขาด ไม่ปล่อยให้ไป
   ตาย 401 รายข้อจนได้รายงานที่ทุก clause เป็น `unknown` โดยไม่มีอะไรบอกสาเหตุ
3. **เปลี่ยน embedding = ต้อง re-ingest** — vector จากคนละโมเดลเทียบ cosine กันไม่ได้ ถ้า
   `EMBEDDING_DIM` เปลี่ยนด้วยต้องมี Alembic migration ใหม่ (`0c41a8268ed0` hardcode `VECTOR(768)`)
   แล้วรัน `python -m scripts.ingest_playbook`
4. **restart เสมอ** — `get_settings()` / `get_llm_client()` / `get_embedder()` เป็น `@lru_cache`
   ทั้งหมด และ `uvicorn --reload` จับแค่ไฟล์ `.py` ไม่จับ `.env`
5. **ย้ายไปค่ายที่เป็น reasoning model ให้ดู `LLM_THINKING`** — ค่า default คือ `disabled` เพราะ
   token ความคิดถูกหักจากงบ `max_tokens` ก้อนเดียวกับคำตอบ (GLM-4.6: 23.7 วิ/984 token ตอนเปิด
   เทียบกับ 2.1 วิ/55 token ตอนปิด — และคิดเกินงบ = ได้ 200 ที่ `content` ว่าง) พารามิเตอร์นี้ส่งให้
   host แบบ OpenAI-compatible เท่านั้น; ตั้ง `LLM_THINKING=auto` ถ้าอยากได้คุณภาพจากการคิดยาว
   แล้วต้องขยับ `LLM_TIMEOUT_SECONDS` ตามด้วย

ตารางเต็ม + ตัวแปรทุกตัว (`LLM_API_KEY`, `EMBEDDING_API_KEY`, `LLM_BASE_URL` ฯลฯ):
[README ของ backend → สลับค่าย AI](apps/backend-fastapi/README.md#สลับค่าย-ai-ผ่าน-env)

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

> ### 🔓 `/auth/dev-login` ยังเป็นประตูหลัง — แต่มี 2 กลอนแล้ว (2026-07-30)
>
> endpoint นี้ออก JWT ให้ **อีเมลอะไรก็ได้ที่ส่งมา** โดยไม่ตรวจอะไรเลย
> (`?email=someone@example.com`) ระหว่างเปิด LAN ใครที่อยู่วงเดียวกันก็ล็อกอินเป็นใครก็ได้
>
> เดิมกันไว้แค่ `APP_ENV != development` ซึ่งไม่พอ เพราะ `APP_ENV` **มีค่า default เป็น
> `development`** อยู่แล้ว — deploy ที่ไม่เคยตั้งตัวแปรนี้เลยจึงเปิดประตูทิ้งไว้ ตอนนี้ต้องเปิดครบ
> ทั้งสองอย่าง: `APP_ENV=development` **และ** `ENABLE_DEV_LOGIN=true` (default `false`) ไม่ครบ
> ทั้งคู่จะ redirect กลับ `/login?error=dev_login_disabled` โดยไม่ออก token ให้เลย
>
> เครื่อง dev นี้ตั้ง `ENABLE_DEV_LOGIN=true` ไว้ใน `.env` แล้ว (ไม่ขึ้น git) ปุ่ม Dev Mode Quick
> Sign In จึงยังใช้ได้เหมือนเดิม — **production อย่าตั้งตัวแปรนี้**

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
| `POST /contracts/{report_id}/accept` | ปุ่ม Accept Risk | JSON body (`clause_id`, `accepted`, `note` ไม่บังคับ) — ไม่แตะ risk level เลย คืน report ทั้งก้อน; `accepted=false` = ถอนการรับรอง |
| `DELETE /contracts/{report_id}` | ปุ่มลบใน Sidebar | `204` เมื่อลบสำเร็จ, `404` ถ้าไม่ใช่รายงานของตัวเอง |
| `GET /playbook`, `POST/PUT/DELETE /playbook/{id}`, `GET /playbook/search` | หน้า `/playbook` | |
| `POST /evaluate` | หน้า `/evaluate` | |
| `GET /`, `/health`, `/health/db` | หน้า `/system` | |
| `GET /auth/me` | โหลดข้อมูล user | |

**ข้อควรระวังที่ทำให้ frontend เพี้ยนได้ (เจอมาแล้วตอนต่อจริง):**

- **Risk level มีแค่ `low` / `medium` / `high` / `unknown`** (ตัวเล็ก) — ไม่มี `CRITICAL`
  และ `unknown` เกิดขึ้นจริง ต้องมีทางแสดงผลเสมอ **โดยมี 2 สาเหตุที่ต่างกันมาก** และแยกได้จาก
  `rationale`: (1) call ล้มจนหมด retry → `"Automated review failed for this clause"` (2) playbook
  ไม่มีจุดยืนที่เกี่ยวข้อง → LLM อธิบายเป็นภาษาคนว่าจุดยืนที่ได้มาไม่ตรงกับ clause นี้ ซึ่งเป็น
  คำตอบที่ตั้งใจ ไม่ใช่ความผิดพลาด — หลังปิด thinking mode (2026-07-30) แบบ (2) กลายเป็นสาเหตุ
  หลักของ `unknown` แทนแบบ (1)
- **`citations` ว่างและ `suggested_fallback` เป็น `null` ได้** เมื่อ playbook ไม่มีจุดยืนที่ตรงกัน
- **`heading` มักเป็นข้อความ clause ทั้งย่อหน้า** ไม่ใช่หัวข้อสั้น ๆ — ถ้าเอาไปใช้เป็น title ตรง ๆ
  จะได้ย่อหน้ายาวเป็นหัวข้อ (mapper จึงเลือกจาก `clause_type` ก่อน แล้วค่อย fallback ไปดึงหัวข้อ
  จากต้นประโยค รองรับรูปแบบ `"ข้อ 5. ..."` ภาษาไทยด้วย)
- **รับเฉพาะ `.pdf`, `.docx` และ `.txt`** — นามสกุลอื่น backend ตอบ `422 document_parse_error`
  (ดูตาราง [ไฟล์สัญญาแบบไหนใช้ได้](#ไฟล์สัญญาแบบไหนใช้ได้) ด้านล่าง)
- **`metadata` ของสัญญาเป็น "คำที่เอกสารเขียนไว้" ไม่ใช่ค่าที่ parse แล้ว** — `agreement_date`
  อาจเป็น `"1st day of August, 2013"` ตรง ๆ อย่าเอาไป `new Date()` หรือจัดรูปแบบใหม่ เพราะจะกลาย
  เป็นการตีความแทนการอ้างอิง และทุกฟิลด์ว่างได้หมด (เอกสารไม่ได้ระบุ = ไม่ต้องแสดง)
- **การ review ใช้เวลาหลายนาที ไม่ใช่หลักวินาที** — วัดจริงหลังปิด thinking mode (2026-07-30):
  **~22 วิ/clause** (42 วิ สำหรับ 3 clause, **3 นาที สำหรับ 8 clause**) เร็วขึ้นราวเท่าตัวจากเดิม
  ~47 วิ/clause แต่ยังเป็นหน่วยนาทีอยู่ เพราะ pipeline เดินทีละ clause และยิง LLM ~4 ครั้งต่อ clause
  — ต้อง loading state ที่ชัดเจนและอย่าเขียนว่า "about a minute" บวกอีก 1 call ต่อ**ฉบับ**
  สำหรับ metadata (ตอนเปิด thinking เคยวัดได้ ~113 วิ ตอนส่งข้อความ 9k ตัวอักษร จึงหั่นเหลือหัว 4k
  + ท้าย 2.5k ให้ห่างเพดาน `LLM_TIMEOUT_SECONDS` 120 วิ — ขอบนั้นยังอยู่ ไม่ได้ถอยกลับ)
- **ไม่มีทาง export รายงานออกจากระบบ** — ตัดออกตั้งใจ (2026-07-30) ทั้งฝั่ง browser และ endpoint
  ถ้าจะเอากลับต้องเริ่มจาก `ContractReport` ที่อยู่ใน memory ตอนรายงานขึ้นจอ (`lib/contracts.ts`)
- **โควตาหมด/คีย์ผิดแล้วยังตอบ `200`** — pipeline แยก failure ของแต่ละ clause ออกจากกัน (ตั้งใจ)
  ดังนั้นเมื่อโดน `429` ทั้งฉบับ จะได้ report ที่ทุก clause เป็น `unknown` พร้อม rationale ว่า
  "Automated review failed for this clause" ไม่ใช่ error ระดับ request — UI ต้องแสดง `unknown`
  ให้เห็นชัด อย่าตีความว่า "ไม่มีความเสี่ยง" (`429` ถูก retry ให้แล้วตามงบ `LLM_MAX_ATTEMPTS`
  แต่โควตาที่หมดจริงคือหมดทั้งวัน retry ไม่ช่วย — จะช้าลงเล็กน้อยแล้วได้ผลเดิม)

---

## ไฟล์สัญญาแบบไหนใช้ได้

ทดสอบจริงกับ parser + segmenter ของ backend (2026-07-28) — ผลตามนี้:

| ไฟล์ | ผล | หมายเหตุ |
|------|-----|----------|
| `.docx` / `.pdf` / `.txt` หัวข้อเลขอังกฤษ (`1. Confidentiality`, `2.3 Term`, `12) Termination`) | ✅ ดีที่สุด | ตัด clause ตามหัวข้อ ตรงตามข้อสัญญาจริง |
| `.docx` / `.pdf` / `.txt` **หัวข้อไทย** (`ข้อ 1. การรักษาความลับ`, `1. การเลิกสัญญา`, `๑. เงื่อนไข`) | ✅ รองรับแล้ว | ตัดตามข้อจริงเหมือนอังกฤษ (เพิ่ม 2026-07-28) |
| `.txt` เข้ารหัส cp874 / UTF-8 (มีหรือไม่มี BOM) | ✅ รองรับแล้ว | เดา encoding ให้เอง (เพิ่ม 2026-07-28) — ไฟล์ที่ decode ไม่ออกยัง review ได้ แต่ตัวอักษรเสียบางส่วน |
| นำหน้าด้วย `Section 4.` / `Article 7.` / `Clause 9` / `ข้อที่ 2.` | ✅ รองรับแล้ว | prefix พวกนี้เข้าเงื่อนไขหัวข้อแล้ว |
| หัวข้อพิมพ์เล็ก (`1. confidentiality`) / bullet / เลขโรมัน (`ARTICLE I`) | ⚠️ ใช้ได้แต่ตัดหยาบ | ตกไปใช้ **paragraph fallback** — 1 ย่อหน้า = 1 clause |
| **PDF สแกน / ถ่ายรูป (ไม่มี text layer)** | ❌ ได้รายงานเปล่า | backend ตอบ `200` แต่ได้ **0 clause** — UI ขึ้น banner เตือนแล้ว ต้อง OCR ก่อน |
| PDF ใส่รหัสผ่าน | ❌ `422` | `document closed or encrypted` — ต้องปลดรหัสก่อน |
| `.doc` (Word เก่า) / `.rtf` / `.md` / ไม่มีนามสกุล | ❌ `422` | `unsupported file type` — ต้อง Save As เป็น `.docx`, `.pdf` หรือ `.txt` |

**`.txt` รองรับแล้ว (2026-07-28):** `parse_txt` ใน `app/parsers.py` — ไม่มีหน้ากระดาษเหมือน DOCX
จึงนับเป็นหน้าเดียว (`page_map == {1: (0, len(text))}`) และเดา encoding ตามลำดับ `utf-8-sig`
(ครอบคลุม UTF-8 ธรรมดา + ตัด BOM ที่ Notepad ใส่มา) → `cp874` (โค้ดเพจไทยของ Windows คือสิ่งที่
ไฟล์ไทยที่ Save เป็น "ANSI" เป็นจริง ๆ) → สุดท้าย `utf-8` แบบ `errors="replace"` เพื่อไม่ให้อัปโหลด
พังเพราะไบต์เสียไม่กี่ตัว

**ไฟล์ตัวอย่างไว้เทส** (`apps/backend-fastapi/data/`):

| ไฟล์ | ข้อ | ใช้เทสอะไร |
|------|-----|------------|
| `data/samples/thai-nda-short.txt` | 3 | smoke test เร็วสุด — `.txt` + หัวข้อไทย (~2 นาที) |
| `data/samples/thai-software-service-agreement.txt` | 11 | สัญญาไทยเต็มฉบับ ครอบคลุม 8 clause type รวมข้อเสี่ยงจริง (ความรับผิดไม่จำกัด, non-compete 5 ปีไม่จำกัดพื้นที่, ชำระเงิน 60 วัน) — ~8 นาที |
| `data/samples/*.docx` (3 ไฟล์) | — | เทส DOCX parser |
| `data/contracts/*.txt` (12 ไฟล์) | — | สัญญาจริงจาก CUAD — อัปโหลดตรงได้แล้วตั้งแต่รองรับ `.txt` |

**หัวข้อไทยรองรับแล้ว (2026-07-28):** เดิม regex ใน `app/parsers.py` คือ
`^\s*(\d+(\.\d+)*)[.)]?\s+[A-Z]` ซึ่งบังคับ **อักษรอังกฤษตัวใหญ่ A–Z** ต่อท้ายเลขข้อ ตัวอักษรไทย
จึงไม่เข้าเงื่อนไข (`\d` รับเลขไทย `๑` ได้ แต่ `[A-Z]` ไม่รับ `ค`) สัญญาไทยเลยตกไปใช้ paragraph
fallback ทั้งฉบับ ตอนนี้ `_HEADING_RE` รับเพิ่ม:

- prefix `ข้อ` / `ข้อที่` / `Article` / `Section` / `Clause` หน้าเลขข้อ
- เลขไทย `๐–๙` คู่กับเลขอารบิก
- ตัวอักษรไทยขึ้นต้นชื่อหัวข้อ — พยัญชนะ `ก–ฮ` **และสระหน้า `เ แ โ ใ ไ`** ซึ่งเขียนนำหน้าพยัญชนะ
  จึงเป็นอักขระตัวแรกของคำจริง ๆ (`เงื่อนไข`, `ใบแจ้งหนี้`, `ไม่แข่งขัน`)

ยังคงต้องมีตัวอักษรตามหลังเลขเสมอ เพื่อไม่ให้บรรทัดที่ขึ้นต้นด้วยตัวเลข (`500,000 baht payable…`,
`1.5% per month`) ถูกนับเป็นหัวข้อ — ทดสอบแล้วว่า **สัญญาอังกฤษจริงทั้ง 12 ฉบับใน `data/contracts`
นับหัวข้อได้เท่าเดิมทุกฉบับ (0/12 เปลี่ยน)** และฝั่ง frontend ตัดเลขซ้ำออกจาก title แล้ว
(`CLAUSE_NUMBERING` ใน `lib/contracts.ts`) ไม่งั้นจะได้ `1. ข้อ 1. การรักษาความลับ`

> ⚠️ **ยังไม่มีการจำกัดขนาดไฟล์** — route อ่านไฟล์ทั้งก้อนเข้า memory (`await file.read()`)
> ไฟล์ใหญ่มากจะกินแรมและใช้เวลานาน (ราว 22 วิ/clause หลังปิด thinking mode)

---

## ผล evaluation (2026-07-30) — ก่อน/หลังแก้ thinking mode

รัน 1 สัญญาเดิมทั้งสองครั้ง (`ticketscominc-sponsorship-agreement`, 8 clause) คอนฟิกเดียวกัน
(`LLM_PROVIDER=zai`, `glm-4.6`, `LLM_TIMEOUT_SECONDS=120`) ต่างกันแค่ `LLM_THINKING`:

| เมตริก | ก่อน (thinking เปิด) | หลัง (`LLM_THINKING=disabled`) | อ่านยังไง |
|--------|---------------------|-------------------------------|-----------|
| `segmentation_f1` | 100.00% | **100.00%** | ตัด clause ตรงกับ gold ทุกข้อ — ขั้นนี้ไม่ใช้ LLM เลย จึงเป็นตัวเลขที่เชื่อได้ |
| `classification_accuracy` | 50.00% | 50.00% | จาก clause ที่มี label แค่ 4 ข้อ (2 ถูก) — sample เล็กเกินกว่าจะสรุปอะไร |
| `risk_accuracy` | 0.00% | 25.00% | เดิม 0% เพราะ clause ที่ล้มถูกนับเป็น `unknown` ซึ่งไม่ตรง gold เสมอ ตอนนี้ที่ยังไม่ตรงคือ clause ที่ playbook ไม่ครอบ |
| `citation_validity` | 100.00% | **100.00%** | citation ที่ออกมาชี้ playbook position จริงทุกอัน |
| clause ที่ล้มเพราะ provider | **6 / 8** | **0 / 8** | ← ตัวเลขที่สำคัญที่สุดในตารางนี้ |
| เวลา review 8 clause | ~6 นาที 15 วิ | **3 นาที 0 วิ** | 22.5 วิ/clause เทียบกับ 47 วิ/clause (จับเวลา `Orchestrator.review()` ตรง ๆ กับสัญญาฉบับเดียวกัน — ตัว eval รอบแรกใช้ ~70 นาทีเพราะรอ timeout 120 วิ ซ้ำ ๆ) |

**ต้นเหตุของ 6 ใน 8 คือเรื่องเดียว** ไม่ใช่สองเรื่องอย่างที่บันทึกไว้ตอนแรก (`APITimeoutError` 3 ครั้ง
+ structured output ตอบสตริงว่าง 3 ครั้ง): GLM-4.6 คิดก่อนตอบ และ **token ความคิดถูกหักจากงบ
`max_tokens` ก้อนเดียวกับคำตอบ** — คิดยาวก็ช้าจนเกิน timeout, คิดยาวเกินงบก็ได้ 200 ที่ `content`
ว่างเปล่า วัดกับ prompt ของ risk scorer เอง: **23.7 วิ / 984 output token** ตอนเปิดคิด เทียบกับ
**2.1 วิ / 55 token** ตอนปิด

สิ่งที่แก้ไป (รายละเอียดใน [README ของ backend](apps/backend-fastapi/README.md#thinking-mode-llm_thinking)):

1. **`LLM_THINKING=disabled` เป็นค่า default** — ส่ง `thinking: {"type": "disabled"}` ให้ host แบบ
   OpenAI-compatible; host ที่ไม่รู้จักพารามิเตอร์นี้ตอบ 400 → adapter เลิกส่งแล้วจำไว้
2. **retry ชั้นบน SDK** — SDK ของทุกค่าย retry แค่ปัญหา transport แต่ 200 ที่ตอบว่างหรือ JSON พัง
   มันถือว่า "สำเร็จ" `LLMClient._call` จึงยิงซ้ำเองเฉพาะ failure ที่ถามใหม่แล้วมีโอกาสได้
3. **เจอบั๊กเก่าตอนทดสอบจริง** — Z.AI ไม่ได้ปฏิเสธ `json_schema` แต่ **รับแล้วตอบ markdown มา**
   โค้ดเดิมอาศัย error ตรงนั้นเป็นสัญญาณ fallback ไป `json_object` ซึ่งทำให้ timeout ครั้งเดียวก็
   ปิด strict validation ทิ้งทั้ง run เงื่อนไขตอนนี้แยก "host ตอบไม่ตรงรูป" ออกจาก "เน็ตมีปัญหา"
   และจะจำว่า host ทำไม่ได้ ก็ต่อเมื่อ fallback ทำงานสำเร็จจริง

### รอบขยาย: 3 ฉบับ 90 clause (2026-07-30)

รันต่อด้วย `--limit 3` (90 clause, มี gold label 26 ข้อ — sample ใหญ่กว่ารอบแรก 6 เท่า) ใช้เวลา
~33 นาที **ไม่มี clause ไหนล้มเพราะ provider เลยทั้ง 90 ข้อ**:

| เมตริก | 1 ฉบับ (8 clause) | **3 ฉบับ (90 clause)** | อ่านยังไง |
|--------|------------------|------------------------|-----------|
| `segmentation_f1` | 100.00% | **100.00%** | ยืนที่ 100% ทั้งสองรอบ และไม่ใช้ LLM — ตัวเลขที่เชื่อได้ที่สุดในตาราง |
| `classification_accuracy` | 50.00% (n=4) | **57.69%** (n=26) | เริ่มมีความหมายแล้วที่ n=26 |
| `risk_accuracy` | 25.00% | **50.00%** | ครึ่งหนึ่งของ clause ที่มี label ให้ระดับความเสี่ยงตรง gold |
| `citation_validity` | 100.00% | **100.00%** | citation ทุกอันชี้ playbook position จริง ไม่มีที่มั่วเลย |
| clause ล้มเพราะ provider | 0 / 8 | **0 / 90** | คอนฟิกหลังแก้ thinking mode ยืนระยะได้จริง |

**classification แยกตามประเภท clause** (ตัวเลขคือความแม่นของการจำแนกประเภท ไม่ใช่ความเสี่ยง):

| clause type | n | acc | | clause type | n | acc |
|---|---|---|---|---|---|---|
| `termination` | 3 | **100%** | | `non_compete` | 6 | 50% |
| `governing_law` | 3 | **100%** | | `intellectual_property` | 2 | 50% |
| `warranty` | 1 | **100%** | | `limitation_of_liability` | 2 | 50% |
| `other` | 5 | 40% | | `payment_terms` | 4 | **25%** |

`payment_terms` แม่นน้อยสุด (1 ใน 4) และเป็นประเภทเดียวกับที่รอบแรกตอบ `unknown` เพราะ playbook
ไม่มีจุดยืนที่ตรง — สองรอบชี้ไปที่เดียวกัน คอขวดถัดไปคือ **ความครอบคลุมของ playbook** ไม่ใช่
provider ส่วน `other` 40% เป็นเรื่องคาดหมาย: มันคือถังรวมของ clause ที่ taxonomy 12 ตัวไม่มีชื่อให้

---

## Roadmap ที่เหลือ

เส้นทางหลัก (login → upload → review → accept/override → เปิดรายงานเดิม) ใช้งานได้จริงครบแล้ว
และ roadmap เดิมปิดไปหมดแล้วเมื่อ 2026-07-30 — accept risk / เก็บรายงานถาวร / contract metadata /
LLM call ที่ผ่านสม่ำเสมอ / data-retention job ส่วน export ถูกตัดออกจากขอบเขต เหลือ:

1. **สร้าง gold label ให้ตรงกับ clause จริง** — คอขวดของทุกตัวเลขความแม่น และเป็นงาน backend
   ชิ้นใหญ่สุดที่เหลือ: `build_cuad_fixtures.py` ให้ label จาก CUAD annotation ที่ offset ตกอยู่ใน
   ข้อนั้น แต่ CUAD ไฮไลต์ **วลีที่เป็นคำตอบของคำถาม 41 ข้อ** ไม่ได้บอกว่า "ข้อนี้เป็นข้อประเภทอะไร"
   ผลคือข้อที่ขึ้นหัวว่า `13. Warranty` เป็น gold `other` (เพราะ annotation เดียวที่ตกในข้อนั้นคือ
   `Insurance`) และ classifier ที่ตอบ `warranty` ถูกนับว่าผิด — ทางที่ตั้งใจไว้คือใช้ span ของ
   ไฮไลต์ (`answer["text"]` ที่ตอนนี้ถูกทิ้ง) แทน offset เริ่มต้นตัวเดียว รายละเอียดพร้อมตาราง
   หลักฐาน: [เพดานของ gold label](apps/backend-fastapi/README.md#เพดานของ-gold-label-ที่มาจาก-cuad)
2. **integration test ที่ยิง LLM จริงอย่างน้อย 1 เส้น** — เทสต์ 258 ตัว mock ที่ขอบ provider
   ทั้งหมด บั๊กแบบ "Z.AI รับ `json_schema` แล้วตอบ markdown มา" ผ่าน mock ได้สบาย ๆ
3. **ตั้ง cron ให้ retention job** — สคริปต์พร้อมแล้ว (`python -m scripts.purge_reports`) ตั้งใจ
   ไม่ตั้งให้ เพราะกรอบเวลาเก็บข้อมูลเป็นนโยบายที่ต้องตัดสินใจเอง (ลบแล้วกู้ไม่ได้)

รันชุดวัดผลได้ตามนี้:

```bash
cd apps/backend-fastapi
.venv/bin/python -m scripts.run_eval --contract ticketscominc-sponsorship-agreement  # ฉบับสั้นสุด
.venv/bin/python -m scripts.run_eval --limit 3      # 3 ฉบับแรก (~33 นาที)
.venv/bin/python -m scripts.run_eval                # เต็มชุด 327 clause (~2 ชม.)
```
