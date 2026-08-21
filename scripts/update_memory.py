from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.bootstrap import setup_project_root

ROOT_DIR = setup_project_root(__file__)

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
