# Contract Clause Risk Reviewer

AI-assisted contract review against a company's playbook. Upload a contract,
inspect clause assessments with policy citations, and record human decisions
through acceptance or risk overrides.

The application parses documents, segments them into clauses, classifies each
clause, retrieves relevant playbook positions, scores risk, and verifies the
assessment with deterministic checks and an optional LLM judge. Reports retain
original text, rationale, fallback language, citations, and review status.

## Repository

| Directory | Purpose |
|---|---|
| [apps/backend-fastapi](apps/backend-fastapi/README.md) | FastAPI API, authentication, parsers, AI pipeline, storage, migrations, and evaluation |
| [apps/web](apps/web/README.md) | React 19, TypeScript, Vite, and Tailwind frontend |
| [infrastructure](infrastructure/docker-compose.yml) | PostgreSQL with pgvector, Redis, API, and web containers |
| [reports](reports/optimization-2026-09-17.md) | Measurements, evaluation results, and verification evidence |

## Features

- PDF, DOCX, and TXT uploads, including English and Thai numbered headings.
- Classification across 12 clause types and four risk levels: `low`, `medium`,
  `high`, and `unknown`.
- Hybrid retrieval using pgvector cosine similarity and BM25, with room for
  the dominant subject and secondary subjects in mixed clauses.
- Citations and fallbacks copied directly from retrieved playbook positions;
  model output is constrained to their IDs.
- Explicit Section, Appendix, Schedule, and Exhibit references resolved to
  bounded contract excerpts with source spans.
- Grounding verification, one corrective scoring retry with judge feedback,
  and isolation of provider failures to the affected clause.
- Metadata extracted once per document and retained only when found verbatim.
- Google OAuth, bearer JWT authentication, report ownership checks, and an
  explicitly enabled development sign-in option.
- Persistent history, deletion, human acceptance/retraction, risk overrides,
  and an audit trail in PostgreSQL.
- Playbook CRUD and search, evaluation tools, system status, and configurable
  storage and retention.

Human acceptance and AI verification are separate states. Unknown risks and
unverified assessments need human review; a valid citation ID alone does not
establish that the model's reasoning is correct.

## Quick start

Use Python 3.12+, Node.js 22.12+, pnpm, and Docker Compose. Start from the
repository root unless a directory change is shown.

### Start storage services

```bash
docker compose -f infrastructure/docker-compose.yml up -d postgres redis
```

Compose publishes PostgreSQL on 5432 and Redis on 6379. If another application
occupies those ports, use separate project services and update their published
ports and backend URLs. The latest local evaluation used PostgreSQL on 55432.

### Configure and run the backend

```bash
cd apps/backend-fastapi
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Edit `.env`: supply the OpenRouter key, generate independent session and JWT
signing secrets, and configure Google OAuth credentials. The example selects
DeepSeek and the tested eight-clause concurrency setting. Local testing without
Google requires both `APP_ENV=development` and `ENABLE_DEV_LOGIN=true`.

```bash
alembic upgrade head
python -m scripts.ingest_playbook
uvicorn app.main:app --reload
```

The API is at `http://localhost:8000`, with interactive documentation at
`http://localhost:8000/docs`. Ingest the playbook before requesting reviews.
See the [backend README](apps/backend-fastapi/README.md) for complete setup.

### Run the frontend

Open another terminal at the repository root:

```bash
cd apps/web
pnpm install --frozen-lockfile
cp .env.example .env
pnpm dev
```

Open `http://localhost:5173/login`. `VITE_API_BASE_URL` must point to the API,
and the backend's `FRONTEND_URL` must match the frontend origin. Sign in, open
`/manual`, and upload a contract. Reopen reports through
`/contract?report=<report_id>`.

### Run all services in containers

Configure `apps/backend-fastapi/.env` first, then run from the repository root:

```bash
docker compose -f infrastructure/docker-compose.yml up --build -d
```

The API entrypoint applies migrations and ingests the playbook when its store
is empty. Set `FORCE_PLAYBOOK_INGEST=1` on the API container to force ingestion.
Compose overrides database and Redis URLs with service names; browser-facing
URLs continue to use the published host ports.

## Selected AI configuration

The user-selected model is DeepSeek through OpenRouter. GPT-OSS reports are
historical experiments, not the current selection.

```dotenv
LLM_PROVIDER=openrouter
LLM_MODEL=deepseek/deepseek-v4.1-flash
LLM_OPENROUTER_PROVIDERS=[]
LLM_THINKING=disabled
REVIEW_CONCURRENCY=8
EMBEDDING_PROVIDER=openrouter
EMBEDDING_MODEL=google/gemini-embedding-001
EMBEDDING_DIM=768
ENABLE_JUDGE=true
```

Supply `OPENROUTER_API_KEY` only in the private environment. An empty endpoint
allow-list lets OpenRouter route to compatible endpoints; do not carry over
the Groq/Cerebras restriction used for GPT-OSS. The generic code default for
concurrency remains one because provider rate limits vary; eight was verified
with this DeepSeek configuration.

Adapters support Gemini, Anthropic, Z.AI, OpenRouter, and other OpenAI-compatible
hosts. Embeddings are independent of chat. Changing only the chat model does
not require re-ingestion. Changing the embedding provider or model does; a
dimension change also needs a migration because the vector column is 768-dimensional.

Restart the backend after changing `.env`. Settings and clients are cached per
process; Python source reload does not reliably reload environment files.

## Latest ten-contract evaluation

On 18 September 2026 in Asia/Bangkok, the selected pipeline reviewed the same
ten CUAD fixtures as the earlier DeepSeek run: 281 clauses, with classification
and risk labels on 72. Fixture, gold, and playbook hashes match.

| Metric | Earlier DeepSeek run | Selected configuration |
|---|---:|---:|
| Clause concurrency | 4 | 8 |
| Time for ten contracts | 16 min 23 sec | 6 min 14 sec |
| Classification agreement with gold | 76.39% | 77.78% |
| Risk agreement with gold | 52.78% | 59.72% |
| Pipeline failures | 0 | 0 |

Measured latency improved **2.63 times**. All 281 citation IDs are valid; all
168 cited assessments passed deterministic source/fallback checks; all 40
referenced excerpts match their fixture spans. Rationale length is a median
of 49 words and a maximum of 85 words.

The run has **115 unknown risks** and **163/281 judge-verified assessments**.
Gold risk labels are inferred from CUAD categories, not independent expert
legal judgments. Segmentation gold was generated by the same segmenter.
These single-run measurements used embedding cache; they are not an SLA or
a statistical significance test. Unknown and unverified results need review.

Evidence:

- [Optimization report](reports/optimization-2026-09-17.md)
- [Complete matched comparison](reports/deepseek-v3-vs-v6-c8-2026-09-18.json)
- [Selected run and configuration](reports/optimize-ten-deepseek-v6-c8-2026-09-18/results.json)
- [Source, settings, and citation audit](reports/optimize-ten-deepseek-v6-c8-2026-09-18/completion-audit.json)

The original unchanged DeepSeek/concurrency-one benchmark was stopped after
repeated empty completions and only one completed contract. Its full accuracy
and latency are unknown; it is not the table's baseline.

## Verification and evaluation

Latest pipeline validation: **248 unit tests and 70 integration tests**.
Default backend tests exclude paid live-model tests.

```bash
cd apps/backend-fastapi
.venv/bin/pytest
.venv/bin/ruff check app scripts tests
```

Frontend checks, from `apps/web`:

```bash
pnpm test
pnpm lint
pnpm build
```

Evaluate the saved configuration with real providers from the backend directory
using a fresh output directory:

```bash
.venv/bin/python -u -m scripts.full_gold_eval \
  --limit 10 --output ../../reports/deepseek-current-new
```

The runner saves checkpoints, reports, metrics, settings, and source/data hashes.
It consumes API quota but does not create user reports in the database. Rescore
saved runs without model calls using `scripts.compare_saved_evals`. The full
fixture set contains 12 contracts, 327 spans, and 82 labelled clauses.

The live regression gate requires segmentation F1 of at least 95% and citation
validity of 100%. Classification and risk accuracy have no repository pass
threshold. Scores from before the 30 July 2026 gold relabelling are not directly
comparable to the current set.

## Uploads and report behavior

| Format | Reader | Notes |
|---|---|---|
| PDF | PyMuPDF | Needs a text layer; scanned documents require OCR before upload |
| DOCX | python-docx | Paragraphs and tables in document order, including nested tables |
| TXT | Text decoder | UTF-8 and cp874 input supported |

Empty or unsupported documents return HTTP 422. `MAX_UPLOAD_BYTES` defaults to
10 MiB; `MAX_CLAUSES` defaults to 300 and is checked before clause review calls.
Oversized inputs return HTTP 413.

The frontend maps DTOs in `apps/web/src/lib/contracts.ts`. Risk values are
lowercase, citations may be empty, and fallback may be null. Metadata is
verbatim text rather than normalized dates or amounts. Parsed documents are
deleted from temporary Redis storage after review; reports retain clause text.

## Authentication, deployment, and retention

Google sign-in uses full-page navigation to `/auth/google/login`. The callback
returns to the frontend with a JWT or error code. API requests use
`Authorization: Bearer <token>`. Logout clears the OAuth cookie and frontend
token; issued JWTs remain valid until expiry.

For LAN development, bind API and Vite to an accessible host, configure reachable
`VITE_API_BASE_URL` and `FRONTEND_URL` origins, and restart/rebuild as needed.
Browser addresses must not use Compose service names. Google OAuth needs an
accepted, registered redirect URI. Development sign-in requires both switches;
it does not verify email ownership and must remain disabled in production.

PostgreSQL reports persist until owner deletion. `REPORT_STORAGE=redis` uses
native TTL instead. `REPORT_RETENTION_DAYS` does not schedule deletion by itself.
Inspect the maintenance job before scheduling:

```bash
python -m scripts.purge_reports --older-than-days 90 --dry-run
```

An empty `PLAYBOOK_ADMIN_EMAILS` permits every signed-in user to edit policy.
Set its comma-separated allow-list to restrict writes; reads remain available
to signed-in users. Reports belonging to another user return HTTP 404.

Export endpoints and browser JSON/CSV/print controls are outside current scope.
Retention scheduling requires an explicit deployment policy.
