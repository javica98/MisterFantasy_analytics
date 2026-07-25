"""
manage_memories.py — CLI para inspeccionar y depurar newspaper/memory/memories.jsonl

Antes solo se podía editar el JSONL a mano (ver src/memory/README.md). Este
script cubre los casos de mantenimiento habituales: listar, ver el detalle de
una memoria y borrar las incorrectas, reconstruyendo el índice de embeddings
si hace falta.

Uso:
    python scripts/manage_memories.py list [--category X] [--manager X] [--player X] [--query "texto"] [--limit N]
    python scripts/manage_memories.py show <id> [<id> ...]
    python scripts/manage_memories.py delete <id> [<id> ...] [--yes] [--rebuild-index]
    python scripts/manage_memories.py rebuild-index
"""

import argparse
import json
import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.memory.memory_store import (
    DEFAULT_MEMORY_PATH,
    delete_memories,
    read_memories,
    retrieve_by_keywords,
)


def cmd_list(args: argparse.Namespace) -> None:
    memories = read_memories(args.path)

    if args.category:
        memories = [m for m in memories if m.get("category") == args.category]
    if args.manager:
        memories = [m for m in memories if m.get("manager") == args.manager]
    if args.player:
        memories = [m for m in memories if m.get("player") == args.player]
    if args.query:
        memories = retrieve_by_keywords(args.query, path=args.path, top_k=args.limit or len(memories) or 1)

    if args.limit:
        memories = memories[: args.limit]

    if not memories:
        print("Sin resultados.")
        return

    for memory in memories:
        subject = " / ".join(p for p in [memory.get("manager"), memory.get("player")] if p)
        print(
            f"{memory.get('id', ''):<40} {memory.get('fecha', ''):<12} "
            f"[{memory.get('category', ''):<15}] {subject:<25} {memory.get('summary', '')[:80]}"
        )
    print(f"\n{len(memories)} memoria(s).")


def cmd_show(args: argparse.Namespace) -> None:
    by_id = {memory.get("id"): memory for memory in read_memories(args.path)}
    for memory_id in args.ids:
        memory = by_id.get(memory_id)
        if memory is None:
            print(f"[!] No existe una memoria con id={memory_id!r}")
            continue
        print(json.dumps(memory, ensure_ascii=False, indent=2))


def cmd_delete(args: argparse.Namespace) -> None:
    by_id = {memory.get("id"): memory for memory in read_memories(args.path)}

    unknown = [memory_id for memory_id in args.ids if memory_id not in by_id]
    for memory_id in unknown:
        print(f"[!] No existe una memoria con id={memory_id!r}, se omite.")

    known_ids = [memory_id for memory_id in args.ids if memory_id in by_id]
    if not known_ids:
        print("Nada que borrar.")
        return

    if not args.yes:
        print("Se borrarán las siguientes memorias:")
        for memory_id in known_ids:
            print(f"  - {memory_id}: {by_id[memory_id].get('summary', '')[:80]}")
        confirm = input(f"¿Confirmas borrar {len(known_ids)} memoria(s)? [y/N] ")
        if confirm.strip().lower() not in ("y", "yes", "s", "si", "sí"):
            print("Cancelado.")
            return

    removed = delete_memories(known_ids, args.path)
    print(f"Borrada(s) {removed} memoria(s).")

    if args.rebuild_index:
        _rebuild_index(args.path)


def cmd_rebuild_index(args: argparse.Namespace) -> None:
    _rebuild_index(args.path)


def _rebuild_index(path: str) -> None:
    from src.memory.embedding_store import rebuild_embedding_index

    index = rebuild_embedding_index(memory_path=path)
    print(f"Índice de embeddings reconstruido: {index['count']} memoria(s).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", default=str(DEFAULT_MEMORY_PATH), help="Ruta a memories.jsonl")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_list = subparsers.add_parser("list", help="Listar memorias (con filtros opcionales)")
    p_list.add_argument("--category")
    p_list.add_argument("--manager")
    p_list.add_argument("--player")
    p_list.add_argument("--query", help="Búsqueda lexical por texto (retrieve_by_keywords)")
    p_list.add_argument("--limit", type=int)
    p_list.set_defaults(func=cmd_list)

    p_show = subparsers.add_parser("show", help="Mostrar el JSON completo de una o varias memorias")
    p_show.add_argument("ids", nargs="+")
    p_show.set_defaults(func=cmd_show)

    p_delete = subparsers.add_parser("delete", help="Borrar una o varias memorias por id")
    p_delete.add_argument("ids", nargs="+")
    p_delete.add_argument("--yes", action="store_true", help="No pedir confirmación")
    p_delete.add_argument(
        "--rebuild-index", action="store_true", help="Reconstruir el índice de embeddings tras borrar"
    )
    p_delete.set_defaults(func=cmd_delete)

    p_rebuild = subparsers.add_parser("rebuild-index", help="Reconstruir el índice de embeddings")
    p_rebuild.set_defaults(func=cmd_rebuild_index)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
