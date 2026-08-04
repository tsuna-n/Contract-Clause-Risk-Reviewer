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
> **ปิด roadmap ครบทุกข้อ (2026-07-31)** — สามข้อสุดท้ายเคลียร์แล้ว: **รัน eval บน gold label
> ชุดใหม่** (3 ฉบับ / 90 clause / 18 นาที — `segmentation_f1` 100%, `citation_validity` 100%,
> `classification` 45.45%, `risk` 50.00%; ตัวเลข classification ที่ลดจาก 57.69% มาจาก
> **ไม้บรรทัดที่เปลี่ยน ไม่ใช่ pipeline ที่แย่ลง** — อธิบายที่ [ผล eval บน label
> ชุดใหม่](#ผล-eval-บน-label-ชุดใหม่-2026-07-31)), **เพิ่มชุดเทสต์ที่ยิง LLM จริง 11 ตัว**
> (`pytest -m live_llm`, ~3 นาที — deselect เป็น default จึงไม่ทำให้ `pytest` เปล่า ๆ เสียเงิน) และ
> **ยืนยันว่า cron ของ retention job จะไม่ตั้ง** จนกว่าจะมีนโยบายเก็บข้อมูลจริง ตอนนี้เทสต์คือ
> **268 ตัวออฟไลน์ ไม่มี skip เหลือ + 11 ตัว live**
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
| Backend | **LLM client + RAG (สลับค่ายได้)** | provider adapter (`app/ai/providers.py`) — Gemini / Anthropic Claude / OpenAI-compatible (Z.AI GLM, OpenRouter, DeepSeek, vLLM) เลือกด้วย `LLM_PROVIDER` ตัวเดียว, structured output ตามวิธีของแต่ละค่าย, hybrid retrieval (pgvector cosine + BM25) |
| Backend | **LLM call ทนทานขึ้น** | `LLM_THINKING=disabled` (default) ปิด thinking ของ reasoning model ที่กินงบ `max_tokens` จนตอบว่าง + retry ชั้นบน SDK เฉพาะ failure ที่ถามใหม่แล้วมีโอกาสได้ (timeout/429/5xx/คำตอบว่าง/JSON พัง) จำกัดด้วย `LLM_MAX_ATTEMPTS` และงบเวลา 1 timeout — 400/401 ไม่ retry |
| Backend | **Data-retention job** | `python -m scripts.purge_reports` ลบรายงานเก่ากว่า `REPORT_RETENTION_DAYS` (`--dry-run` นับก่อนได้) — ต้องตั้ง cron เอง เพราะการลบข้อมูลของคนอื่นไม่ควรเป็นผลพลอยได้ของ request |
| Backend | **Guardrail + สิทธิ์ playbook (2026-07-30)** | `is_grounded()` ไม่ใช่ substring ล้วนแล้ว — judge บังคับ excerpt ยาว ≥ 4 คำ (`MIN_CITATION_EXCERPT_WORDS`) เพราะเดิมอ้าง `"the"` ก็ผ่านและได้ badge "ตรวจสอบแล้ว" ส่วน metadata ยังใช้ 1 คำเพราะค่าอย่าง `"กฎหมายไทย"` สั้นโดยธรรมชาติ; retry ตอน ungrounded ส่ง `verdict.reason` กลับเข้า prompt แล้ว (เดิมส่ง prompt เดิมเป๊ะ ๆ = จ่าย token 2 เท่าเพื่อคำตอบเดิม); เขียน playbook จำกัดด้วย `PLAYBOOK_ADMIN_EMAILS` → `403` (อ่านยังเปิดให้ทุกคนที่ login) |
| Backend | **Hardening ระดับ request (2026-07-30)** | ปิด 4 จุดที่ request เดียวยึดหรือเปิดระบบได้: **auth ระดับ router** ที่ `/playbook/*` (6 ตัว) + `/evaluate` → `401` (ประกาศที่ router ไม่ใช่รายตัว endpoint ใหม่จึงปิดเอง), **ย้าย blocking I/O ออกจาก event loop** (`def` + `run_in_threadpool` ตอน review) — วัดจริง `/health` ตอบ 1.2–2.0 ms ระหว่าง review 18.9 วิ (เดิม 2.7 s), **เพดาน `MAX_UPLOAD_BYTES` 10 MB** (อ่านแบบ bounded → `413` ไม่ buffer ก่อน) + **`MAX_CLAUSES` 300** (เช็คหลัง segment ก่อนจ่ายค่า LLM), **`gold_set_path` ต้องอยู่ใน `data/gold/`** และ **`/auth/dev-login` ต้องมี 2 กลอน** (`APP_ENV=development` + `ENABLE_DEV_LOGIN=true`) |
| Backend | Parsers | PDF (PyMuPDF) / DOCX (python-docx) / TXT (เดา encoding: UTF-8 → cp874) → `ParsedDocument` |
| Backend | Guardrails | grounding, citation validity, no-invented-fallback — wired เข้า judge แล้ว |
| Backend | Schemas | Pydantic models: clause, report, taxonomy, playbook, eval |
| Backend | **Report history** | `GET /contracts` (สรุปรายงานของตัวเอง เรียงใหม่→เก่า) + `GET /contracts/{report_id}` (ฉบับเต็ม) + `DELETE /contracts/{report_id}` — Postgres ใช้ index `(session_id, created_at)`, Redis ใช้ sorted set ต่อ session, รายงานของคนอื่นตอบ `404` ไม่ใช่ `403` |
| Backend | **Data fixtures จาก CUAD** | `scripts/build_cuad_fixtures.py` แปลง CUAD v1 → สัญญาจริง 12 ฉบับ + gold 327 clause (82 clause มี label — เฉพาะข้อที่ไฮไลต์ของ CUAD ครอบคลุมมากพอ ดู `MIN_LABEL_COVERAGE`) + `.docx` ให้ลองอัปโหลด 3 ไฟล์ |
| Backend | **Playbook 36 จุดยืน** | ครบทั้ง 12 clause type อ้างอิงหมวดรีวิว 41 หมวดของ CUAD — `preferred`/`fallback` เป็นภาษาสัญญาจริงที่ guardrail ใช้เทียบ verbatim ได้ |
| Backend | Tests | **268 unit/integration tests ผ่านหมด ไม่มี skip เหลือ** (`pytest` — ฟรี ออฟไลน์ ~3 วิ) |
| Backend | **Live tests (2026-07-31)** | **11 ตัวที่ยิง Z.AI + pgvector จริง** (`pytest -m live_llm`, ~3 นาที) — `tests/live/` 10 ตัว (structured output ต้องได้ data ไม่ใช่ markdown, ทุก clause ต้องได้คำตอบจริง, citation ชี้ position จริง + excerpt คำต่อคำ, fallback มาจาก playbook, metadata อยู่ในเอกสารจริง) + eval regression gate ที่เลิก skip แล้ว; deselect เป็น default ผ่าน `addopts` จึงไม่จ่ายค่า LLM ทุกครั้งที่รัน `pytest` |
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

> ### สรุปสั้น: ไม่เหลืองานโค้ดค้างแล้ว (2026-07-31)
>
> เส้นทางใช้งานจริงทั้งเส้น — login → upload → review → accept/override → เปิดรายงานเดิม —
> ทำงานได้ครบ มีเทสต์ **268 ตัวออฟไลน์ (ไม่มี skip) + 11 ตัวที่ยิง provider จริง** คุมอยู่
> **3 ข้อที่เคยค้างตรงนี้ปิดหมดแล้ว:**
>
> | ข้อเดิม | สถานะ |
> |---|---|
> | eval บน label ชุดใหม่ | ✅ รันแล้ว 18 นาที 10 วิ — [ผลอยู่ด้านล่าง](#ผล-eval-บน-label-ชุดใหม่-2026-07-31) |
> | integration test ที่ยิง LLM จริง | ✅ `tests/live/` + eval regression gate ที่เลิก skip = 11 ตัวใต้ `pytest -m live_llm` |
> | cron ของ retention job | ✅ ตัดสินใจแล้วว่า **จะไม่ตั้ง** — ไม่ใช่งานค้างอีกต่อไป (เหตุผลด้านล่าง) |

**สิ่งที่ตั้งใจไม่ทำ ไม่ใช่สิ่งที่ทำไม่เสร็จ:**

| ส่วน | รายการ | ทำไมถึงไม่ทำ |
|------|--------|--------------|
| Backend | cron ของ retention job | **ตัดสินใจแล้วว่าไม่ตั้ง (2026-07-31)** — ตัว job พร้อมใช้ (`scripts/purge_reports.py`) แต่ค่า default คือเก็บรายงานไว้จนเจ้าของสั่งลบ เพราะการลบกู้คืนไม่ได้และตัวสัญญาหายไปด้วย การตั้ง cron ที่ลบข้อมูลของคนอื่นทุกคืนควรมาจากนโยบายเก็บข้อมูล ไม่ใช่มาจากความอยากให้ตาราง roadmap ว่าง — ถ้าจะตั้งทีหลัง: `echo "REPORT_RETENTION_DAYS=90" >> .env` แล้ว `--dry-run` ดูก่อนเสมอ |
| Backend | eval เต็มชุด 327 clause | เลือกหยุดที่ `--limit 3` (n=22) เพราะเทียบกับตัวเลขชุดเก่าได้ตรงแล้ว เต็มชุดคือ ~1,300 call / ~2 ชม. — `.venv/bin/python -m scripts.run_eval` ถ้าอยากได้ |
| Backend | ดัน `classification_accuracy` ให้สูงขึ้น | **เพดานอยู่ที่ gold label ไม่ใช่ที่ pipeline** — CUAD ตอบคำถาม 41 ข้อเกี่ยวกับสัญญา ไม่ได้จำแนกประเภทข้อสัญญา จะดันให้สูงอย่างมีความหมายต้อง annotate เองด้วยคน ส่วนการแก้ prompt ให้เดาตาม label คือวัด pipeline เทียบกับ heuristic ของตัวเอง |

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

`LLM_PROVIDER` ตัวเดียวเลือกได้ 5 ค่าย โดยมี adapter จริง 3 ตัวใน
[`app/ai/providers.py`](apps/backend-fastapi/app/ai/providers.py) — `zai` และ `openrouter` คือ
adapter แบบ OpenAI-compatible ที่เติม endpoint ของแต่ละเจ้าให้แล้ว (Z.AI ยังเติม model default
`glm-4.6` ให้ด้วย ส่วน OpenRouter ต้องระบุ `LLM_MODEL` เอง เพราะ catalogue เป็นของทุกค่ายรวมกัน
ไม่มีตัวไหน "เป็นของ" OpenRouter โดยตรง) ตัวเดียวกันนี้จึงใช้กับ DeepSeek, Ollama, vLLM ได้ด้วยการตั้ง
`LLM_BASE_URL` เอง SDK ทั้งสามติดตั้งมาให้ครบและ `import` แบบ lazy —
**ไม่ต้องแก้โค้ด ไม่ต้อง rebuild image**

| ค่าย | `LLM_PROVIDER` | คีย์ที่ต้องมี | model default |
|------|----------------|---------------|---------------|
| Google Gemini | `gemini` | `GEMINI_API_KEY` | `gemini-3.5-flash` |
| Anthropic Claude | `anthropic` | `ANTHROPIC_API_KEY` | `claude-opus-5` |
| Z.AI (GLM) | `zai` | `ZAI_API_KEY` | `glm-4.6` |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` + `LLM_MODEL` | — (ต้องระบุเอง เช่น `anthropic/claude-opus-5`) |
| OpenAI-compatible | `openai` | `OPENAI_API_KEY` + `LLM_MODEL` + `LLM_BASE_URL` | — (ต้องระบุเอง) |

**ตัวอย่าง: เปลี่ยนไปใช้ Claude Haiku 4.5**

```env
# --- LLM: Anthropic (Claude Haiku 4.5) ---
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-...
LLM_MODEL=claude-haiku-4-5

# --- Embeddings: ยังเป็น Gemini (ทั้ง Anthropic และ Z.AI ไม่มี embedding ให้ใช้) ---
EMBEDDING_PROVIDER=gemini
GEMINI_API_KEY=AIza...
EMBEDDING_MODEL=gemini-embedding-001
```

เคสนี้ **ไม่ต้อง re-ingest playbook** เพราะ embedding ยังเป็นโมเดลเดิม vector ใน pgvector จึงใช้ต่อได้
ทั้งหมด — เปลี่ยนแค่ว่าใครเป็นคนอ่านสัญญา

**ตัวอย่าง: เปลี่ยนไปใช้ OpenRouter**

OpenRouter คือ router เดียวที่พาไปหาโมเดลของหลายค่ายพร้อมกัน (Anthropic, Google, DeepSeek, Meta ฯลฯ)
ผ่านคีย์ใบเดียว — เข้ากับ adapter แบบ OpenAI-compatible ตัวเดียวกับ `zai` พอดี ต่างกันแค่ endpoint กับ
การที่ต้องระบุ `LLM_MODEL` เอง (ไม่มี default เพราะ catalogue เป็นของทุกค่ายรวมกัน):

```env
# --- LLM: OpenRouter (พาไปหา Claude Opus 5 ที่วิ่งผ่าน OpenRouter) ---
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
LLM_MODEL=anthropic/claude-opus-5   # ต้องมี prefix ของค่ายจริงเสมอ — ดูข้อ 7 ด้านล่าง

# --- Embeddings: ยังเป็น Gemini (OpenRouter ไม่มี endpoint embedding ให้เลย) ---
EMBEDDING_PROVIDER=gemini
GEMINI_API_KEY=AIza...
EMBEDDING_MODEL=gemini-embedding-001
```

ชื่อโมเดลอื่นที่ใช้ได้ตามรูปแบบ `<ค่าย>/<model>` เดียวกัน เช่น `google/gemini-3.5-flash`,
`deepseek/deepseek-chat`, `meta-llama/llama-3.3-70b-instruct` — ดูรายชื่อทั้งหมดที่
[openrouter.ai/models](https://openrouter.ai/models) เคสนี้ก็ **ไม่ต้อง re-ingest playbook**
เหมือนกัน เพราะ embedding ยังเป็น Gemini ตัวเดิม

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

คอนฟิกที่ `.env` ของ repo นี้ใช้อยู่ตอนนี้คือ **Z.AI GLM-4.7-flash อ่านสัญญา + Gemini ทำ embedding**
(ผลจริงของคำสั่งด้านบน เมื่อ 2026-08-01):

```
chat : OpenAICompatibleChatBackend -> glm-4.7-flash
embed: GeminiEmbedder -> gemini-embedding-001 (768 dim)
```

`zai` และ `openrouter` ใช้ adapter ตัวเดียวกับ `openai` ชื่อคลาสที่ขึ้นจึงเป็น
`OpenAICompatibleChatBackend` — ไม่ได้แปลว่าตั้งค่าผิด

**7 ข้อที่ต้องรู้ก่อนสลับ:**

1. **สลับค่ายแล้วต้องแก้ `LLM_MODEL` ด้วย** — ตั้ง `LLM_PROVIDER=anthropic` ทั้งที่
   `LLM_MODEL=gemini-3.5-flash` จะฟ้อง `ProviderConfigError` ตั้งแต่เรียกครั้งแรก แทนที่จะไปเจอ
   404 ของ vendor ที่ไม่บอกว่าตัวไหนผิด (ลบ `LLM_MODEL` ทิ้งก็ได้ = ใช้ default ของค่ายนั้น)
2. **คีย์ว่างถือว่าไม่ได้ตั้ง** — `ANTHROPIC_API_KEY=` เฉย ๆ จะฟ้องทันทีว่าตัวไหนขาด ไม่ปล่อยให้ไป
   ตาย 401 รายข้อจนได้รายงานที่ทุก clause เป็น `unknown` โดยไม่มีอะไรบอกสาเหตุ
3. **เปลี่ยน embedding = ต้อง re-ingest** — vector จากคนละโมเดลเทียบ cosine กันไม่ได้ ถ้า
   `EMBEDDING_DIM` เปลี่ยนด้วยต้องมี Alembic migration ใหม่ (`0c41a8268ed0` hardcode `VECTOR(768)`)
   แล้วรัน `python -m scripts.ingest_playbook`
4. **`zai` และ `openrouter` ทำ embedding ไม่ได้ มีแต่ chat** — `api.z.ai` เสิร์ฟเฉพาะโมเดล GLM
   (`/models` คืน 8 ตัว ไม่มี `embedding-*` เลย ขอไปได้ `400 code 1211 Unknown Model`) ชื่อ
   `embedding-2/3` เป็นของ BigModel ของ Zhipu คนละแพลตฟอร์มกัน ส่วน OpenRouter ไม่มี endpoint
   embedding ให้เลย (route แต่ chat completion) ดังนั้น `EMBEDDING_PROVIDER=zai` หรือ `openrouter`
   เฉย ๆ จะถูกปฏิเสธพร้อมบอกว่าต้องตั้งอะไร — ตั้ง `EMBEDDING_PROVIDER=gemini` (หรือไม่ตั้งเลยก็
   fallback ไป Gemini ให้) ถ้าบัญชีคุณมี embedding ที่ host อื่นค่อยระบุ `EMBEDDING_MODEL` +
   `EMBEDDING_BASE_URL` เอง (เคยตั้ง `EMBEDDING_PROVIDER=zai` + `EMBEDDING_MODEL=embedding-1` ไว้จริง
   เมื่อ 2026-08-01 ผลคือทุก clause กลายเป็น `unknown` เพราะ `400` ถูกกลืนตามข้อ 2 — vector ใน DB
   ไม่ได้เสียหายอะไร)
5. **restart เสมอ** — `get_settings()` / `get_llm_client()` / `get_embedder()` เป็น `@lru_cache`
   ทั้งหมด และ `uvicorn --reload` จับแค่ไฟล์ `.py` ไม่จับ `.env`
6. **ย้ายไปค่ายที่เป็น reasoning model ให้ดู `LLM_THINKING`** — ค่า default คือ `disabled` เพราะ
   token ความคิดถูกหักจากงบ `max_tokens` ก้อนเดียวกับคำตอบ (GLM-4.6: 23.7 วิ/984 token ตอนเปิด
   เทียบกับ 2.1 วิ/55 token ตอนปิด — และคิดเกินงบ = ได้ 200 ที่ `content` ว่าง) พารามิเตอร์นี้ส่งให้
   host แบบ OpenAI-compatible เท่านั้น; ตั้ง `LLM_THINKING=auto` ถ้าอยากได้คุณภาพจากการคิดยาว
   แล้วต้องขยับ `LLM_TIMEOUT_SECONDS` ตามด้วย
7. **`LLM_MODEL` บน `openrouter` ต้องมี prefix ของค่ายจริง** — OpenRouter re-sell โมเดลของทุกค่าย
   ภายใต้ชื่อเดิมของเจ้านั้น เช่น `anthropic/claude-opus-5`, `google/gemini-3.5-flash`,
   `deepseek/deepseek-chat` — ตัวเช็ค "โมเดลเจ้านี้ผิดค่าย" ในข้อ 1 จะไม่ทำงานกับ `openrouter` เพราะชื่อ
   ที่ขึ้นต้นด้วย `anthropic/` หรือ `google/` คือของถูกต้องอยู่แล้ว ไม่ใช่ `.env` ที่สลับค่ายไม่สุด —
   พิมพ์ผิด prefix จะไปเจอ 404 ของ OpenRouter ตรง ๆ แทน

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

> ⚠️ **มีเพดานขนาดไฟล์แล้ว** (แก้เมื่อ 2026-07-30 — ย่อหน้านี้เคยเขียนว่ายังไม่มี): route อ่านแบบ
> bounded ตาม `MAX_UPLOAD_BYTES` (default 10 MB) แล้วตอบ `413` โดยไม่ buffer ไฟล์ทั้งก้อนก่อน และ
> มี `MAX_CLAUSES` (default 300) เช็คหลัง segment ก่อนจ่ายค่า LLM → `413` เหมือนกัน
> ที่เหลือคือเรื่องเวลาล้วน ๆ: ราว 22 วิ/clause หลังปิด thinking mode

---

## ผล evaluation (2026-07-30) — ก่อน/หลังแก้ thinking mode

> ⚠️ **ตัวเลขทุกตารางในหัวข้อนี้วัดกับ gold label ชุดเก่า** (ก่อน relabel วันเดียวกัน — ดูหัวข้อ
> [ซ่อม gold label](#ซ่อม-gold-label-2026-07-30) ด้านล่าง) `classification_accuracy` กับ
> `risk_accuracy` **เทียบกับผลที่รันหลังจากนี้ไม่ได้** เพราะไม้บรรทัดเปลี่ยน ส่วน
> `segmentation_f1` เทียบได้ตามปกติ เพราะ span ทั้ง 327 ข้อไม่ถูกแตะ

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

`payment_terms` แม่นน้อยสุด (1 ใน 4) — ตอนแรกอ่านว่าเป็นเพราะ playbook ครอบไม่พอ **ซึ่งผิด**
(`payment_terms` มีจุดยืน 5 อัน มากสุดในทุกประเภท และการจำแนกประเภทไม่ได้ใช้ playbook เลย)
ต้นเหตุจริงคือ gold label — หัวข้อถัดไป

---

## ซ่อม gold label (2026-07-30)

ตรวจด้วยการยิงเฉพาะ classifier + retriever กับ 3 ฉบับแรก แล้วดู `cuad_categories` ของแต่ละข้อ พบว่า
**หลายกรณีโมเดลตอบถูกแต่ gold ผิด**:

| clause จริง | annotation ที่ตกในข้อนั้น | gold เก่า | classifier |
|---|---|---|---|
| `6.02. Termination. This Agreement may be terminated only:` | `Change Of Control` (11.0% ของข้อ) | `other` | `termination` ✅ |
| `13. Warranty. SIERRA warrants that the Product shall be free from defects` | `Insurance` (28.5%) | `other` | `warranty` ✅ |
| `9.07. Successors and Assigns.` | `Anti-Assignment` + `Minimum Commitment` (11.3%) | `payment_terms` | `other` ✅ |
| `3. RATE  Charterer agrees to pay...` | `Governing Law` (3.0%) | `other` | — |

**เพราะ CUAD ไม่ได้จำแนกประเภทข้อสัญญา** — มันตอบคำถาม 41 ข้อเกี่ยวกับสัญญาแล้วไฮไลต์ *วลี*
ที่เป็นคำตอบ ซึ่งมักอยู่ในข้อที่ว่าด้วยเรื่องอื่น กฎเดิมคือ "ข้อไหนที่ offset เริ่มต้นของไฮไลต์ตกอยู่
ข้อนั้นได้ label" จึงเปลี่ยนหลักฐานข้างเคียงให้เป็นประเภทของข้อ

**สิ่งที่แก้:** ให้ label จาก category ที่ **ครอบคลุมข้อนั้นมากที่สุด** และตัด label ทิ้งถ้าครอบไม่ถึง
`MIN_LABEL_COVERAGE` (ข้อนั้นกลายเป็นข้อไม่มี label ซึ่ง `run_eval` ข้ามให้ตั้งแต่แรกอยู่แล้ว) โดย
`Candidate.annotations` เก็บ span ของไฮไลต์แล้ว (`answer_start` + `len(answer["text"])` ซึ่งเดิม
ทิ้งไป) และนับอักขระทับกันแบบ union — บวกดิบ ๆ ได้ coverage 116% ในข้อ Insurance จริง ๆ

**เกณฑ์เลือกจากข้อมูล และเปลี่ยนใจหลังวัด:** ตั้ง 30% ก่อนตาม histogram ที่เป็น bimodal (33 ข้ออยู่
เหนือ 80%, 16 ข้ออยู่ใต้ 20%) แต่ preview ฟ้องว่าหยาบเกินไป — ทิ้ง `governing_law` ของข้อ
`9.05. Applicable Law` และ `warranty` ของ `5.01. Products Warranty` ที่ CUAD ไฮไลต์ถูกแล้วแต่
ไฮไลต์แค่ประโยคเดียวในข้อยาว จึงลงมาที่ **15%** ซึ่งตัดแค่หางล่างที่เถียงไม่ได้

| | เก่า | ใหม่ |
|---|---|---|
| clause span | 327 | **327 (ไม่เปลี่ยนเลย — md5 ของสัญญาทั้ง 12 ไฟล์เท่าเดิม)** |
| clause ที่มี label | 91 | **82** |
| clause type ที่มี label | 8 | 8 (`termination` 17, `other` 16, `non_compete` 15, `payment_terms` 9, `governing_law` 9, `intellectual_property` 8, `limitation_of_liability` 6, `warranty` 2) |
| `label_coverage` | — | ต่ำสุด 0.158 / กลาง 0.675 / สูงสุด 0.991 (เขียนลงไฟล์ gold ให้อ่านได้ว่า label ไหนมีหลักฐานหนักแค่ไหน) |

**ต้นทุนที่ยอมจ่าย ไม่ใช่ของฟรี:** label หายไป 9 อัน และ 2 อันในนั้นเถียงได้ว่าถูก
(`5. Consideration` = `payment_terms`, `22. Assignment` = `other`) กับอีก 1 ข้อที่เปลี่ยนไปทางแย่ลง
(`11. Trademarks` จาก `intellectual_property` → `other` เพราะตอนนี้ coverage ตัดสินแทนการนับ
จำนวน category)

**ตรวจแล้วว่า harness อ่านไฟล์ใหม่ได้** — รัน `run_eval` กับ stub orchestrator (ไม่ยิง LLM):
`segmentation_f1` 100%, ให้คะแนน 82 sample, ไม่พังกับฟิลด์ `label_coverage` หรือข้อที่มี
`cuad_categories` แต่ไม่มี label

---

## ผล eval บน label ชุดใหม่ (2026-07-31)

รัน `.venv/bin/python -m scripts.run_eval --limit 3` — 3 ฉบับ / 90 clause / label 22 ข้อ ใช้เวลา
**18 นาที 10 วินาที** (เร็วกว่า ~33 นาทีที่เคยประเมินไว้) คอนฟิกเดียวกับรอบก่อนทุกอย่าง
(`LLM_PROVIDER=zai`, `glm-4.6`, `LLM_THINKING=disabled`) — เปลี่ยนแค่ไม้บรรทัด:

| เมตริก | label เก่า (n=26) | **label ใหม่ (n=22)** | อ่านยังไง |
|--------|-------------------|----------------------|-----------|
| `segmentation_f1` | 100.00% | **100.00%** | เทียบข้ามกันได้จริง เพราะ span 327 ข้อไม่ถูกแตะ และขั้นนี้ไม่ใช้ LLM |
| `classification_accuracy` | 57.69% | **45.45%** | **ลดลง 12 จุด — อธิบายด้านล่าง** |
| `risk_accuracy` | 50.00% | **50.00%** | ยืนเท่าเดิม |
| `citation_validity` | 100.00% | **100.00%** | ไม่มี citation ที่ชี้ playbook position ปลอมเลยสักอัน |

### ตัวเลขที่ลดลงไม่ได้แปลว่า pipeline แย่ลง

**โค้ดของ pipeline ไม่ถูกแตะระหว่างสองรอบนี้เลย** สิ่งที่เปลี่ยนคือ gold label และมันเปลี่ยนไปใน
ทางที่ตัด label ที่ classifier เคยตอบถูกออกด้วย:

- 57.69% ของ 26 = ถูก **15** ข้อ
- 45.45% ของ 22 = ถูก **10** ข้อ
- label หายไป 4 ข้อ แต่ข้อที่เคยถูกหายไป **5** ข้อ

นี่คือราคาที่รู้อยู่แล้วตอนเลือกเกณฑ์ `MIN_LABEL_COVERAGE` — ตอนนั้นบันทึกไว้เองว่า label ที่หาย
9 อันมี 2 อันที่เถียงได้ว่าถูก การที่ตัวเลขลดจึงเป็นผลของการทำ label ให้เข้มขึ้น ไม่ใช่สัญญาณถดถอย
**เมตริกที่เทียบข้ามการเปลี่ยน label ได้จริง (`segmentation_f1`, `citation_validity`) ยืนที่ 100%
ทั้งคู่**

**จุดที่เพี้ยนหนักสุดคือ `non_compete`** (n=7, acc 28.57%) โดยตอบเป็น `intellectual_property`
ไป 3 ข้อ — ซึ่งตรงกับตัวเอกสาร เพราะข้อห้ามแข่งขันใน CUAD มักเขียนรวมอยู่กับข้อสงวนสิทธิ์ในทรัพย์สิน
ทางปัญญา ส่วน `termination` (3/3) และ `governing_law` (3/3) ยังเต็มทั้งคู่เหมือนรอบก่อน

### สิ่งที่ log จับได้แต่เมตริกไม่ได้บอก

ระหว่าง 90 clause นั้น GLM-4.6 ตอบกลับมาเป็น **list ของข้อความภาษาจีนที่ไม่เกี่ยวกับสัญญาเลย**
แทนที่จะเป็น object ตาม schema อยู่ 1 ครั้ง:

```
_RiskAssessment attempt 1/3 failed (ValidationError: 1 validation error for _RiskAssessment
  Input should be an object [type=model_type, input_value=['尔擔任嘉義縣議...'], input_type=list]);
  retrying in 1.0s
```

retry ชั้นบน SDK จับได้และยิงซ้ำจนได้คำตอบที่ถูกรูป clause นั้นจึงไม่หายไปจากรายงาน — **นี่คือ
failure ชนิดที่ mock มองไม่เห็น** และเป็นเหตุผลตรง ๆ ที่ `tests/live/` มีอยู่

---

## Roadmap ที่เหลือ

**ปิดครบแล้วเมื่อ 2026-07-31 — ไม่เหลืองานโค้ดค้าง** เส้นทางหลัก (login → upload → review →
accept/override → เปิดรายงานเดิม) ใช้งานได้จริงครบ, roadmap รอบ 2026-07-30 ปิดไปแล้ว (accept risk /
เก็บรายงานถาวร / contract metadata / LLM call ที่ผ่านสม่ำเสมอ / data-retention job; export ถูกตัด
ออกจากขอบเขต) และ 3 ข้อสุดท้ายปิดในรอบนี้:

1. ✅ **eval บน gold label ชุดใหม่** — รันแล้ว ผลอยู่ที่ [หัวข้อด้านบน](#ผล-eval-บน-label-ชุดใหม่-2026-07-31)
2. ✅ **test ที่ยิง LLM จริง** — `tests/live/` 10 ตัว + eval regression gate ที่เลิก skip แล้ว
   รวม 11 ตัวใต้ marker `live_llm` ซึ่ง deselect เป็น default
3. ✅ **cron ของ retention job** — ตัดสินใจแล้วว่า**ไม่ตั้ง** จนกว่าจะมีนโยบายเก็บข้อมูล ไม่ใช่
   งานค้างอีกต่อไป

```bash
cd apps/backend-fastapi

# --- เทสต์ ---
.venv/bin/pytest                    # 268 ตัว ออฟไลน์ ฟรี ~3 วินาที
.venv/bin/pytest -m live_llm        # 11 ตัว ยิง provider จริง ~3 นาที (เสียค่า LLM)

# --- วัดผล ---
.venv/bin/python -m scripts.run_eval --contract ticketscominc-sponsorship-agreement  # ฉบับสั้นสุด
.venv/bin/python -m scripts.run_eval --limit 3      # 3 ฉบับแรก (~18 นาที) ← ตัวเลขที่บันทึกไว้
.venv/bin/python -m scripts.run_eval                # เต็มชุด 327 clause (~2 ชม.) ยังไม่เคยรัน
```
