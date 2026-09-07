# Contract Clause Risk Reviewer — Web

React + TypeScript frontend for uploading contracts, reading review history,
accepting or overriding clause assessments, and managing the company playbook.

## Local development

Use Node.js 22.12+ and pnpm. From this directory:

```bash
corepack enable
pnpm install --frozen-lockfile
cp .env.example .env
pnpm dev
```

Set `VITE_API_BASE_URL` to the backend origin (default: `http://localhost:8000`).
The backend must be running and its `FRONTEND_URL` must match the frontend origin
(default: `http://localhost:5173`). See the [backend setup](../backend-fastapi/README.md)
for database migrations and authentication configuration.

## Verification

```bash
pnpm test
pnpm lint
pnpm build
```

The regression tests use Node's built-in test runner and cover report-specific
review decisions, stale responses from previously opened reports, updated clause
content, and stable store snapshots. They require no external services.

`pnpm build` checks TypeScript and emits `dist/`. Signed-in screens are loaded
on demand, so opening the login page does not download every application screen.
`pnpm preview` serves the build locally for inspection.

For deployment, use the supplied Dockerfile and nginx configuration. Set
`VITE_API_BASE_URL` at build time; changing the variable after building does not
change the bundled API URL. Configure SPA fallback to `index.html` when hosting
elsewhere so direct links such as `/contract?report=...` work.

## Uploads

PDF, DOCX and TXT are supported. DOCX tables are read in document order, including
nested tables and merged cells. Scanned PDFs require OCR before uploading; a file
with no readable text is rejected instead of producing an empty review.

Reviews depend on the configured model, playbook and storage services. Passing
the offline checks does not verify live authentication or model quality.
