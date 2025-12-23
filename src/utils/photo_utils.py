import re
import unicodedata
import os, sys
# Directorios de imágenes

def manager_photo(team_name,IMAGES_TEAMS_DIR,DEFAULT_TEAM_IMAGE):
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