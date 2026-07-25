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

from src.memory.memory_builder import build_memories
from src.memory.memory_store import DEFAULT_MEMORY_PATH, upsert_memories
from src.utils.file_utils import safe_read_json


def main() -> None:
    events_json = safe_read_json("newspaper/json/news_json.json")
    cards_json = safe_read_json("newspaper/json/cards/news_cards.json")

    memories = build_memories(events_json, cards_json)
    changed = upsert_memories(memories, DEFAULT_MEMORY_PATH)

    print(f"Memories built: {len(memories)}")
    print(f"Memories inserted/updated: {changed}")
    print(f"Memory store: {DEFAULT_MEMORY_PATH}")


if __name__ == "__main__":
    main()
