"""
run_utils.py — Script de utilidades para desarrollo.

Uso:
    # Eliminar fondo de imágenes en newspaper/photos/
    RUN_BG_TEST=1 python scripts/run_utils.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.bootstrap import setup_project_root

ROOT_DIR = setup_project_root(__file__)

from src.utils.photo_utils import remove_background_image


def test_remove_background_photos() -> None:
    """Elimina el fondo de todas las imágenes en newspaper/photos/."""
    photos_dir = ROOT_DIR / "newspaper" / "photos"
    output_dir = photos_dir / "no_bg"
    output_dir.mkdir(parents=True, exist_ok=True)

    valid_ext = {".png", ".jpg", ".jpeg", ".webp"}
    images = [p for p in photos_dir.iterdir() if p.is_file() and p.suffix.lower() in valid_ext]

    if not images:
        print("No se encontraron imágenes para procesar en:", photos_dir)
        return

    print(f"Procesando {len(images)} imágenes en {photos_dir}")
    for image_path in images:
        out_path = output_dir / f"{image_path.stem}_no_bg.png"
        try:
            remove_background_image(str(image_path), str(out_path))
            print("OK:", out_path)
        except Exception as exc:
            print("ERROR:", image_path, "-", exc)


if __name__ == "__main__":
    if os.getenv("RUN_BG_TEST", "0") == "1":
        test_remove_background_photos()
    else:
        print("Usa RUN_BG_TEST=1 para ejecutar la eliminación de fondos.")
        print("Ejemplo: RUN_BG_TEST=1 python scripts/run_utils.py")
