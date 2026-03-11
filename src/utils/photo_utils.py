import re
import unicodedata
import os, sys
from typing import Optional


# Directorios de imágenes

def manager_photo(team_name, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE):
    """
    Devuelve la ruta de la imagen del equipo según su nombre.
    Si no existe, devuelve una imagen por defecto.
    """
    team_images = {
        "Chamacónicos": "chamacónicos.png",
        "Dani": "dani.png",
        "De la Guettir FC": "de_la_guettir_fc.png",
        "Jotabetrbb": "jotabetrbb.png",
        "Juanba": "juanba.png",
        "Libre": "libre.png",
        "Los marinero": "los_marinero.png",
        "Maldinillo 💥": "maldinillo.png",
        "MuchaSalsa": "muchasalsa.png",
    }

    filename = team_images.get(team_name, DEFAULT_TEAM_IMAGE)
    image_path = os.path.join(IMAGES_TEAMS_DIR, filename)

    # Fallback de seguridad
    if not os.path.exists(image_path):
        image_path = os.path.join(IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE)

    return image_path


def remove_background_image(
    input_path: str,
    output_path: Optional[str] = None,
    threshold: int = 30,
) -> str:
    """
    Elimina el fondo de una imagen y la guarda en PNG con transparencia.

    Estrategia:
    - Si `rembg` está disponible, usa un modelo de segmentación.
    - Si no, aplica un fallback simple con Pillow eliminando colores
      cercanos al del píxel superior izquierdo.
    """
    if output_path is None:
        root, _ = os.path.splitext(input_path)
        output_path = f"{root}_no_bg.png"

    with open(input_path, "rb") as in_file:
        input_bytes = in_file.read()

    # Primer intento: rembg (mejor calidad).
    try:
        from rembg import remove  # type: ignore

        output_bytes = remove(input_bytes)
        with open(output_path, "wb") as out_file:
            out_file.write(output_bytes)
        return output_path
    except Exception:
        # Fallback: quitar color de fondo por proximidad al pixel de la esquina.
        pass

    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("No se pudo eliminar el fondo: instala 'rembg' o 'pillow'.") from exc

    image = Image.open(input_path).convert("RGBA")
    data = image.getdata()
    bg_r, bg_g, bg_b, _ = image.getpixel((0, 0))

    new_data = []
    for pixel in data:
        r, g, b, a = pixel
        if (
            abs(r - bg_r) <= threshold
            and abs(g - bg_g) <= threshold
            and abs(b - bg_b) <= threshold
        ):
            new_data.append((r, g, b, 0))
        else:
            new_data.append((r, g, b, a))

    image.putdata(new_data)
    image.save(output_path, "PNG")
    return output_path
