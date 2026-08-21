from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.bootstrap import setup_project_root

ROOT_DIR = setup_project_root(__file__)

from src.memory.embedding_store import rebuild_embedding_index


def main() -> None:
    index = rebuild_embedding_index()
    print(f"Embedding model: {index['model_name']}")
    print(f"Memories indexed: {index['count']}")
    print(f"Embedding dimension: {index['dimension']}")
    print(f"Embeddings file: {index['embeddings_path']}")


if __name__ == "__main__":
    main()

