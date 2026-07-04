"""
bootstrap.py — Configura el entorno de ejecución para scripts del proyecto.

Uso en cualquier script de /scripts/:

    from src.utils.bootstrap import setup_project_root
    ROOT_DIR = setup_project_root()

Esto reemplaza el bloque boilerplate repetido en todos los scripts:
    CURRENT_FILE = Path(__file__).resolve()
    ROOT_DIR = CURRENT_FILE.parent.parent
    SRC_DIR = ROOT_DIR / "src"
    for p in (ROOT_DIR, SRC_DIR): sys.path.insert(0, str(p))
    os.chdir(ROOT_DIR)
"""

import os
import sys
from pathlib import Path


def setup_project_root(script_file: str | None = None) -> Path:
    """
    Configura ROOT_DIR, añade src al sys.path y cambia el cwd.

    Args:
        script_file: Pasar __file__ del script que llama. Si es None,
                     infiere la raíz subiendo 2 niveles desde este módulo.

    Returns:
        ROOT_DIR como Path.
    """
    if script_file is not None:
        root = Path(script_file).resolve().parent.parent
    else:
        # Este módulo está en src/utils/, subimos 2 niveles
        root = Path(__file__).resolve().parent.parent.parent

    src = root / "src"

    for p in (root, src):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))

    os.chdir(root)
    return root
