#!/bin/sh
# Bring the database and playbook up to date, then hand off to the CMD.
set -e

echo "[entrypoint] applying database migrations…"
alembic upgrade head

# Embedding the playbook costs one Gemini call per position, so it runs only
# when there is nothing to retrieve against. Set FORCE_PLAYBOOK_INGEST=1 to
# re-embed after editing data/playbook/positions.yaml.
should_ingest() {
    [ "${FORCE_PLAYBOOK_INGEST:-0}" = "1" ] && return 0
    ! python -c "
import sys
from sqlalchemy import text
from app.core.db import SessionLocal

with SessionLocal() as session:
    count = session.execute(text('SELECT count(*) FROM playbook_embeddings')).scalar_one()
sys.exit(0 if count else 1)
"
}

if should_ingest; then
    echo "[entrypoint] ingesting playbook…"
    python -m scripts.ingest_playbook
else
    echo "[entrypoint] playbook already ingested; skipping (FORCE_PLAYBOOK_INGEST=1 to redo)"
fi

echo "[entrypoint] starting: $*"
exec "$@"
