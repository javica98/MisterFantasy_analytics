from __future__ import annotations

import os
import sys
from pathlib import Path


CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parent.parent
SRC_DIR = ROOT_DIR / "src"

for path in (ROOT_DIR, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.chdir(ROOT_DIR)

from src.memory.embedding_store import rebuild_embedding_index


def main() -> None:
    index = rebuild_embedding_index()
    print(f"Embedding model: {index['model_name']}")
    print(f"Memories indexed: {index['count']}")
    print(f"Embedding dimension: {index['dimension']}")
    print(f"Embeddings file: {index['embeddings_path']}")


if __name__ == "__main__":
    main()

