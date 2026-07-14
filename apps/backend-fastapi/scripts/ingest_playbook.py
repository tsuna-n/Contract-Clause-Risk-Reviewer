"""CLI: ingest the playbook YAML into the vector store.

Usage:
    python -m scripts.ingest_playbook [path/to/positions.yaml]
"""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    """Load playbook positions, embed them, and upsert into the vector store.

    TODO: wire ``rag.ingest.load_positions`` -> ``rag.ingest.ingest`` with the
    configured embedder and vector store.
    """
    path = argv[1] if len(argv) > 1 else "data/playbook/positions.yaml"
    print(f"[ingest_playbook] would ingest positions from {path}")
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
