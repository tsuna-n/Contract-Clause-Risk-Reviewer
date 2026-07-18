"""CLI: ingest the playbook YAML into the vector store.

Usage:
    python -m scripts.ingest_playbook [path/to/positions.yaml]
"""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    """Load playbook positions, embed them, and upsert into the vector store."""
    from app.api.deps import get_embedder, get_vector_store
    from app.rag.ingest import ingest, load_positions

    path = argv[1] if len(argv) > 1 else "data/playbook/positions.yaml"
    positions = load_positions(path)
    count = ingest(positions, get_embedder(), get_vector_store())
    print(f"[ingest_playbook] ingested {count} position(s) from {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
