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
| Backend | Parsers | PDF (PyMuPDF) / DOCX (python-docx) / TXT (เดา encoding: UTF-8 → cp874) → `ParsedDocument` |
| Backend | Guardrails | grounding, citation validity, no-invented-fallback — wired เข้า judge แล้ว |
| Backend | Schemas | Pydantic models: clause, report, taxonomy, playbook, eval |
| Backend | **Report history** | `GET /contracts` (สรุปรายงานของตัวเอง เรียงใหม่→เก่า) + `GET /contracts/{report_id}` (ฉบับเต็ม) + `DELETE /contracts/{report_id}` — Postgres ใช้ index `(session_id, created_at)`, Redis ใช้ sorted set ต่อ session, รายงานของคนอื่นตอบ `404` ไม่ใช่ `403` |
| Backend | **Data fixtures จาก CUAD** | `scripts/build_cuad_fixtures.py` แปลง CUAD v1 → สัญญาจริง 12 ฉบับ + gold 327 clause (91 clause มี label จาก annotation ของผู้เชี่ยวชาญ) + `.docx` ให้ลองอัปโหลด 3 ไฟล์ |
| Backend | **Playbook 36 จุดยืน** | ครบทั้ง 12 clause type อ้างอิงหมวดรีวิว 41 หมวดของ CUAD — `preferred`/`fallback` เป็นภาษาสัญญาจริงที่ guardrail ใช้เทียบ verbatim ได้ |
| Backend | Tests | 191 unit/integration tests ผ่านหมด (1 skipped — eval regression gate ที่ต้องยิง LLM จริง) |
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
| Frontend | **Accept / undo จริง** | ปุ่ม Accept Risk ยิง `POST /contracts/{id}/accept` แล้ว — ✓ ในรายการข้อสัญญามาจากรายงาน ไม่ใช่ state ในหน้า, กดซ้ำเพื่อถอนคืน, มีบรรทัดบอกว่าใครรับรองเมื่อไหร่ และติดไปกับ export/print ด้วย |
| Frontend | **แผง metadata ของสัญญา** | `ContractMetadataPanel` แสดงคู่สัญญา/วันที่/มูลค่า/กฎหมาย ทั้งหน้า `/contract` และรายงานใน `/manual` — ช่องที่เอกสารไม่ได้ระบุจะไม่ขึ้นเลย (ไม่แสดงขีดกลางให้ชวนสงสัยว่าพัง) |
| Frontend | **Export report** | ปุ่ม Export ทั้งหน้า `/contract` และหน้ารายงานใน `/manual` — **JSON** (รายงานเต็ม), **CSV** (แถวละ clause พร้อม BOM ให้ Excel อ่านภาษาไทยถูก + กัน CSV injection), และ **Print / Save as PDF** (`PrintableReport` portal ลง `<body>` แล้ว print stylesheet สลับมาแสดงแทนทั้งแอป) — ทำฝั่ง browser ล้วน ไม่ต้องมี endpoint |
| Frontend | **เตือนเมื่อ clause ประเมินไม่สำเร็จ** | รายงานที่มี `unknown` ขึ้น banner ระดับรายงานว่า "ยังไม่ได้วิเคราะห์ ไม่ใช่ว่าไม่มีความเสี่ยง" พร้อมบอกสาเหตุที่พบบ่อย (โควตา Gemini หมด) — badge สีเทารายข้ออ่านเหมือน "ผ่าน" ได้ง่ายเกินไป |
| Infra | Docker Compose | ยก Postgres (pgvector) + Redis ได้จริง |

---

## ❌ สิ่งที่ยังไม่ทำ

| ส่วน | รายการ | รายละเอียด |
|------|--------|------------|
| Backend | Export report (server-side) | ยังไม่มี endpoint export — ฝั่ง frontend ทำ JSON/CSV/Print เองได้แล้วจากรายงานที่อยู่ในเบราว์เซอร์ จะต้องมี endpoint ก็ต่อเมื่ออยาก export โดยไม่เปิดหน้าเว็บ (เช่น ส่งเมล/แบตช์) |
| Backend | Clause-level accuracy ที่เชื่อถือได้ | รันไปแล้ว 1 สัญญา (ดูตารางด้านล่าง) แต่ **ตัวเลขยังใช้ตัดสิน pipeline ไม่ได้** เพราะ 6 ใน 8 clause ล้มเพราะ provider ไม่ใช่เพราะตอบผิด — ต้องแก้เรื่อง LLM ก่อนแล้วค่อยรันเต็มชุด (327 clause ≈ 1,300+ call) |
| Backend | ลบข้อมูลตามกำหนดเวลา | รายงานเก็บถาวรใน Postgres แล้ว จึงไม่มีอะไรลบตัวเองอีก — ถ้าต้องมี data-retention policy ต้องเขียน job ลบเอง (หรือกลับไปใช้ `REPORT_STORAGE=redis`) |

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

**4 ข้อที่ต้องรู้ก่อนสลับ:**

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
| `POST /contracts/{report_id}/accept` | ปุ่ม Accept Risk | JSON body (`clause_id`, `accepted`, `note` ไม่บังคับ) — ไม่แตะ risk level เลย คืน report ทั้งก้อน; `accepted=false` = ถอนการรับรอง |
| `DELETE /contracts/{report_id}` | ปุ่มลบใน Sidebar | `204` เมื่อลบสำเร็จ, `404` ถ้าไม่ใช่รายงานของตัวเอง |
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
- **รับเฉพาะ `.pdf`, `.docx` และ `.txt`** — นามสกุลอื่น backend ตอบ `422 document_parse_error`
  (ดูตาราง [ไฟล์สัญญาแบบไหนใช้ได้](#ไฟล์สัญญาแบบไหนใช้ได้) ด้านล่าง)
- **`metadata` ของสัญญาเป็น "คำที่เอกสารเขียนไว้" ไม่ใช่ค่าที่ parse แล้ว** — `agreement_date`
  อาจเป็น `"1st day of August, 2013"` ตรง ๆ อย่าเอาไป `new Date()` หรือจัดรูปแบบใหม่ เพราะจะกลาย
  เป็นการตีความแทนการอ้างอิง และทุกฟิลด์ว่างได้หมด (เอกสารไม่ได้ระบุ = ไม่ต้องแสดง)
- **การ review ใช้เวลาหลายนาที ไม่ใช่หลักวินาที** — วัดจริงได้ ~45 วิ/clause (83 วิ สำหรับ 3 clause,
  **6 นาที 15 วิ สำหรับ 8 clause** วัดเมื่อ 2026-07-28) เพราะ pipeline เดินทีละ clause และยิง LLM
  ~4 ครั้งต่อ clause — ต้อง loading state ที่ชัดเจนและอย่าเขียนว่า "about a minute"
  บวกอีก 1 call ต่อ**ฉบับ**สำหรับ metadata (วัดกับ GLM-4.6 ได้ ~113 วิ ตอนส่งข้อความ 9k ตัวอักษร
  จึงหั่นเหลือหัว 4k + ท้าย 2.5k ให้ห่างเพดาน `LLM_TIMEOUT_SECONDS` 120 วิ)
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
> ไฟล์ใหญ่มากจะกินแรมและใช้เวลานาน (ราว 45 วิ/clause)

---

## ผล evaluation ครั้งแรก (2026-07-30) — และสิ่งที่มันบอก

รัน 1 สัญญา (`ticketscominc-sponsorship-agreement`, 8 clause) ด้วยคอนฟิกปัจจุบัน
(`LLM_PROVIDER=zai`, `glm-4.6`, `LLM_TIMEOUT_SECONDS=120`) ใช้เวลา ~70 นาที:

| เมตริก | ผล | อ่านยังไง |
|--------|-----|-----------|
| `segmentation_f1` | **100.00%** | ตัด clause ตรงกับ gold ทุกข้อ — ขั้นนี้ไม่ใช้ LLM เลย จึงเป็นตัวเลขที่เชื่อได้ |
| `classification_accuracy` | 50.00% | จาก clause ที่มี label แค่ 4 ข้อ (2 ถูก) — sample เล็กเกินกว่าจะสรุปอะไร |
| `risk_accuracy` | 0.00% | **ไม่ได้แปลว่าโมเดลตอบผิด** — clause ที่ประเมินไม่สำเร็จถูกนับเป็น `unknown` ซึ่งไม่ตรงกับ gold เสมอ |
| `citation_validity` | 100.00% | citation ที่ออกมาชี้ playbook position จริงทุกอัน |

**6 ใน 8 clause ล้มระหว่างทาง** และสาเหตุอยู่ที่ฝั่ง provider ทั้งหมด:

| อาการ | จำนวน | คืออะไร |
|-------|-------|---------|
| `openai.APITimeoutError` | 3 | call เดียวใช้เกิน `LLM_TIMEOUT_SECONDS` (120 วิ) |
| structured output ตอบสตริงว่าง | 3 | `_RiskAssessment` ×2, `_LLMVerdict` ×1 — พังตอน validate JSON (`ContractMetadata` ก็โดนอีก 1 ครั้ง) |

pipeline ทำงานตามที่ออกแบบไว้ทุกอย่าง: clause ที่ล้มกลายเป็น `unknown` + "manual review required"
รายงานยังออกครบ และ UI ขึ้น banner เตือนว่า "ยังไม่ได้วิเคราะห์ ไม่ใช่ว่าไม่มีความเสี่ยง" —
แต่ **ตัวเลข accuracy ชุดนี้วัด provider ไม่ได้วัด pipeline** จึงยังไม่ควรเอาไปอ้างอิง

**ก่อนจะรันเต็มชุด (1,300+ call) ควรแก้เรื่องนี้ก่อน** ไม่งั้นจะจ่ายค่า LLM ทั้งชุดเพื่อได้ตัวเลขที่
แปลไม่ได้ ทางที่น่าลอง: เพิ่ม `LLM_TIMEOUT_SECONDS`, ตรวจว่า `max_tokens` ของ GLM ถูกโหมด
thinking กินจนไม่เหลือให้ตอบหรือเปล่า, หรือสลับกลับไป `LLM_PROVIDER=gemini` ที่เคยรันผ่านมาก่อน

---

## Roadmap ที่เหลือ

เส้นทางหลัก (login → upload → review → accept/override → export → เปิดรายงานเดิม) ใช้งานได้จริง
ครบแล้ว และ roadmap เดิม 3 ใน 4 ข้อ (accept risk / เก็บรายงานถาวร / contract metadata) ปิดไปแล้ว
เมื่อ 2026-07-30 เหลือ:

1. **ทำให้ LLM call ผ่านอย่างสม่ำเสมอ** — ดูหัวข้อผล evaluation ด้านบน นี่คือคอขวดจริงของทั้งระบบ
   ตอนนี้ ไม่ใช่แค่เรื่องของ eval
2. **รัน evaluation เต็มชุด** — gold set 12 ฉบับ 327 clause พร้อมแล้ว รันบางส่วนก่อนได้:

   ```bash
   cd apps/backend-fastapi
   .venv/bin/python -m scripts.run_eval --contract ticketscominc-sponsorship-agreement  # ฉบับสั้นสุด
   .venv/bin/python -m scripts.run_eval --limit 3      # 3 ฉบับแรก
   .venv/bin/python -m scripts.run_eval                # เต็มชุด
   ```

3. **Export ฝั่ง server** — ตอนนี้ทำในเบราว์เซอร์ทั้งหมด (JSON/CSV/Print) จะต้องมี endpoint
   ก็ต่อเมื่ออยาก export โดยไม่เปิดหน้าเว็บ เช่น ส่งเมลหรือทำเป็นแบตช์
4. **Data-retention policy** — พอรายงานเก็บถาวรใน Postgres แล้วก็ไม่มีอะไรลบตัวเองอีก
   ถ้าต้องมีนโยบายลบตามอายุ ต้องเขียน job เอง
