"""CLI: ingest the playbook YAML into the vector store.

Usage:
    python -m scripts.ingest_playbook [path/to/positions.yaml]
"""

from __future__ import annotations

import sys

from app.api.deps import PLAYBOOK_PATH, get_embedder, get_vector_store
from app.rag.ingest import ingest, load_positions


def main(argv: list[str]) -> int:
    """Load playbook positions, embed them, and upsert into the vector store."""
    path = argv[1] if len(argv) > 1 else PLAYBOOK_PATH
    positions = load_positions(path)
    count = ingest(positions, get_embedder(), get_vector_store())
    print(f"[ingest_playbook] ingested {count} position(s) from {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
