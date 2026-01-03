import os
from PIL import Image, ImageDraw, ImageFont
import requests
from bs4 import BeautifulSoup
from src.utils.photo_utils import manager_photo
ZONES = {
    "top_bar":    (0, 0, 1080, 150),
    "main_left":  (0, 120, 760, 820),
    "main_right": (760, 120, 1080, 820),
    "bottom":     (0, 820, 1080, 1350),
}
#IMG_WIDTH = (1080/4)
IMG_WIDTH = 1080
IMG_HEIGHT = 1350


def download_player_image(player_name: str, team_name: str, save_dir: str = "player_images") -> str:
    """
    Busca en Bing Images una foto del jugador en marca.com y descarga la primera disponible.
    Devuelve la ruta local de la imagen descargada.
    """
    # Crear directorio si no existe
    os.makedirs(save_dir, exist_ok=True)

    # Construir query de búsqueda
    query = f'"{player_name}" "{team_name}" site:marca.com'
    url = f"https://www.bing.com/images/search?q={requests.utils.quote(query)}&qft=+filterui:imagesize-large&form=IRFLTR"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
    }

    # Hacer la petición a Bing
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error al buscar imagen: {response.status_code}")
        return ""

    # Parsear HTML con BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Buscar URLs de imágenes
    img_tags = soup.find_all("a", class_="iusc")
    if not img_tags:
        print("No se encontraron imágenes.")
        return ""

    # Extraer la primera URL de imagen grande
    first_img_tag = img_tags[0]
    m = first_img_tag.get("m")
    if not m:
        print("No se encontró URL en el tag.")
        return ""
    
    import json
    m_json = json.loads(m)
    img_url = m_json.get("murl")
    if not img_url:
        print("No hay URL de imagen en el JSON.")
        return ""

    # Descargar la imagen
    ext = os.path.splitext(img_url)[1].split("?")[0] or ".jpg"
    filename = f"{player_name.replace(' ', '_')}_{team_name.replace(' ', '_')}{ext}"
    save_path = os.path.join(save_dir, filename)

    try:
        img_resp = requests.get(img_url, headers=headers)
        with open(save_path, "wb") as f:
            f.write(img_resp.content)
        print(f"Imagen descargada: {save_path}")
        return save_path
    except Exception as e:
        print(f"Error al descargar la imagen: {e}")
        return ""

def get_cards_by_tipo(data: dict, tipos: list[str]) -> list:
    tipos = set(tipos)
    return [
        card
        for card in data.get("cards", [])
        if card.get("tipo") in tipos
    ]
def draw_text_with_outline(draw, position, text, font, fill="white", outline="black", outline_width=2):
    x, y = position
    # Dibujar contorno
    for dx in range(-outline_width, outline_width+1):
        for dy in range(-outline_width, outline_width+1):
            if dx != 0 or dy != 0:
                draw.text((x+dx, y+dy), text, font=font, fill=outline)
    # Dibujar texto principal
    draw.text((x, y), text, font=font, fill=fill)

def paste_center_background(base_img: Image.Image, bg_path: str, opacity: float = 0.15):
    """
    Pega una imagen de fondo centrada verticalmente sobre base_img
    con ancho igual al del card y opacidad dada.
    """
    # Abrir imagen de fondo
    bg = Image.open(bg_path).convert("RGBA")

    # Escalar imagen al ancho del card
    base_width, base_height = base_img.size
    w_percent = base_width / bg.width
    new_height = int(bg.height * w_percent)
    bg = bg.resize((base_width, new_height), Image.LANCZOS)

    # Aplicar opacidad
    if opacity < 1.0:
        alpha = bg.split()[3]
        alpha = alpha.point(lambda p: int(p * opacity))
        bg.putalpha(alpha)

    # Crear capa RGBA del card si no lo es
    if base_img.mode != "RGBA":
        base_img = base_img.convert("RGBA")

    # Posición vertical centrada
    y = (base_height - new_height) // 2

    # Pegar
    base_img.alpha_composite(bg, (0, y))
    return base_img
def draw_multiline_text(tipo,draw, text, x, y, font, max_width, measure_only=False, line_spacing=3, paragraph_spacing=0, fill="white", stroke_fill="black", stroke_width=2):
    """
    Dibuja texto multilínea con ajuste de ancho, contorno y espaciado.
    - fill: color del texto
    - stroke_fill: color del borde
    - stroke_width: grosor del borde
    - line_spacing: espacio entre líneas
    - paragraph_spacing: espacio extra al final del párrafo
    """
    if (tipo == "standard") or (tipo == "reduced"):
        paragraph_spacing=-10
    lines = []
    words = text.split()
    while words:
        line_words = []
        while words:
            line_words.append(words.pop(0))
            test_line = " ".join(line_words + words[:1])
            bbox = font.getbbox(test_line)
            line_width = bbox[2] - bbox[0]
            if line_width > max_width:
                break
        line = " ".join(line_words)
        lines.append(line)
    if ((tipo == "Portada") or (tipo == "Clasificacion")):
        for line in lines:
            if not measure_only:
                draw.text((x, y), line, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
            bbox = font.getbbox(line)
            y += bbox[3] - bbox[1] + line_spacing
        y += paragraph_spacing - line_spacing
    else:
        for line in lines:
            if not measure_only:
                draw.text((x, y), line, font=font, fill="black")
            bbox = font.getbbox(line)
            y += bbox[3] - bbox[1] + line_spacing
        y += paragraph_spacing - line_spacing     
    return y
def create_template(canvas,PATH_UTILS):
    TOPBAR_PATH = "TopBar.png"
    BOTTONBAR_PATH = "BottonBar.png"
    COLUMN_PATH = "Column.png"
    
    image_path_topbar = os.path.join(PATH_UTILS, TOPBAR_PATH)
    image_path_bottonbar = os.path.join(PATH_UTILS, BOTTONBAR_PATH)
    image_path_column = os.path.join(PATH_UTILS, COLUMN_PATH)

    # --- 1. Pegar barra superior ---
    topbar = Image.open(image_path_topbar).convert("RGBA")
    canvas.alpha_composite(topbar, (0, 0))
    # --- 2. Pegar barra inferior ---
    bottonbar = Image.open(image_path_bottonbar).convert("RGBA")
    canvas.alpha_composite(bottonbar, (0, 1052))
    # --- 3. Pegar columna derecha ---
    columnbar = Image.open(image_path_column).convert("RGBA")
    canvas.alpha_composite(columnbar, (810, 0))
    # --- 4. Pegar Logo ---
    logo = create_logo(PATH_UTILS)
    canvas.paste(logo, (-145, -200), logo)  

    return canvas
def create_card(card_info, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,tipo):
    # Fuentes
    title_font = ImageFont.truetype("impact.ttf", 20)
    subtitle_font = ImageFont.truetype("arial.ttf", 15)
    text_font = ImageFont.truetype("arial.ttf", 10) 
    card_width = IMG_WIDTH/4
    if tipo == "rumores":
        card_width = IMG_WIDTH/3
        text_font = ImageFont.truetype("arial.ttf", 15)
    if tipo == "Clasificacion":
        text_font = ImageFont.truetype("arial.ttf", 15)
    if tipo == "Portada":
        title_font = ImageFont.truetype("impact.ttf", 70)
        subtitle_font = ImageFont.truetype("arial.ttf", 20)
        text_font = ImageFont.truetype("arial.ttf", 15) 
        card_width = IMG_WIDTH *0.75
    x_margin = 10
    max_width = card_width - 2 * x_margin

    # --- 1. Calcular altura total ---
    y = 10
    if tipo != "rumores":
        y = draw_multiline_text(tipo,None, card_info["titulo"], x_margin, y, title_font, max_width, measure_only=True)
        y += 15
    y = draw_multiline_text(tipo,None, card_info["subtitulo"], x_margin, y, subtitle_font, max_width, measure_only=True)
    y += 25
    if tipo != "reduced":
        for frase in card_info["texto"]:
            y = draw_multiline_text(tipo,None, frase, x_margin, y, text_font, max_width, measure_only=True)
            y += 15
    final_height = y + 40  # margen inferior

    # --- 2. Crear imagen con altura calculada ---
    if (tipo == "standard") or (tipo == "reduced"):
        img = Image.new("RGBA", (int(card_width), int(final_height)), (255, 255, 255, 255))
    else:
        img = Image.new("RGBA", (int(card_width), int(final_height)), (255, 255, 255, 0))
    # --- 3. Pegar imagen de fondo centrada ---
    escudo_manager = manager_photo(card_info.get("manager", ""), IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE)
    if (tipo != "rumores") and (tipo != "Portada"):
        img = paste_center_background(img, escudo_manager, opacity=0.30)

    # --- 4. Dibujar texto encima ---
    draw = ImageDraw.Draw(img)
    y = 10
    if tipo != "rumores":
        y = draw_multiline_text(tipo,draw, card_info["titulo"], x_margin, y, title_font, max_width)
        y += 15
    y = draw_multiline_text(tipo,draw, card_info["subtitulo"], x_margin, y, subtitle_font, max_width)
    y += 25
    if tipo != "reduced":
        for frase in card_info["texto"]:
            y = draw_multiline_text(tipo,draw, frase, x_margin, y, text_font, max_width)
            y += 15

    return img
def create_portada(canvas,card_info, PATH_UTILS):
    PORTADA_PATH = "Portada.jpg"
    download_player_image(card_info["jugador"],card_info["equipo"],PATH_UTILS)
    image_path_portada = os.path.join(PATH_UTILS, PORTADA_PATH)
    # --- 2. Pegar foto portada ---
    portada = Image.open(image_path_portada).convert("RGBA")

    min_width = IMG_WIDTH * 0.75
    w, h = portada.size

    if w < min_width:
        scale = min_width / w
        portada = portada.resize(
            (int(w * scale), int(h * scale)),
            Image.LANCZOS
        )
    canvas.alpha_composite(portada, (0, 0))    
    return canvas
def create_logo(PATH_UTILS):
    LOGO_PATH = "LogoBajando.png"
    image_path_logo = os.path.join(PATH_UTILS, LOGO_PATH)
    # --- 4. Pegar logo rotado ---
    MAX_LOGO_WIDTH = 575 

    logo = Image.open(image_path_logo).convert("RGBA")

    # Escalar manteniendo proporción
    w, h = logo.size
    scale = MAX_LOGO_WIDTH / w
    # Escalar manteniendo proporción
    w, h = logo.size
    scale = MAX_LOGO_WIDTH / w
    logo = logo.resize(
        (int(w * scale), int(h * scale)),
        Image.LANCZOS
    )
    logo_rotado = logo.rotate(
    25,
    expand=True,
    resample=Image.BICUBIC
    )

    return logo_rotado
def create_botton(canvas,cards,peor,corner_card, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE):
    peorcard = create_card(peor[0], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard")
    mvps1 = create_card(cards[0], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard")
    mvps2 = create_card(cards[1], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard")
    if corner_card is None:
        corner = create_card(cards[2], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard")
    else:
        corner = create_card(corner_card, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard")
    canvas.alpha_composite(peorcard, (0,1100))
    canvas.alpha_composite(mvps1, (270,1100))
    canvas.alpha_composite(mvps2, (540,1100))
    canvas.alpha_composite(corner, (810,1100))
    return canvas
def create_columns(canvas,columns, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE):
    big1 = create_card(columns[1], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard")
    canvas.alpha_composite(big1, (810, 75))

    if len(columns) > 6:
        reduced1 = create_card(columns[2], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"reduced")
        reduced2 = create_card(columns[3], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"reduced")
        reduced3 = create_card(columns[4], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"reduced")
        reduced4 = create_card(columns[5], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"reduced")
        reduced5 = create_card(columns[6], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"reduced")
        canvas.alpha_composite(reduced1, (810, 325))
        canvas.alpha_composite(reduced2, (810, 475))
        canvas.alpha_composite(reduced3, (810, 625))
        canvas.alpha_composite(reduced4, (810, 775))
        canvas.alpha_composite(reduced5, (810, 925))
    elif len(columns) > 5:
        big2 = create_card(columns[2], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard")
        reduced1 = create_card(columns[3], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"reduced")
        reduced2 = create_card(columns[4], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"reduced")
        reduced3 = create_card(columns[5], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"reduced")
        canvas.alpha_composite(big2, (810, 325))
        canvas.alpha_composite(reduced1, (810, 575))
        canvas.alpha_composite(reduced2, (810, 725))
        canvas.alpha_composite(reduced3, (810, 875))
    elif len(columns) > 4:
        big2 = create_card(columns[2], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard")
        big3 = create_card(columns[3], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard")
        reduced1 = create_card(columns[4], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"reduced")
        canvas.alpha_composite(big2, (810, 325))
        canvas.alpha_composite(big3, (810, 575))
        canvas.alpha_composite(reduced1, (810, 825))
    else:
        big2 = create_card(columns[2], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard")
        big3 = create_card(columns[3], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard")
        canvas.alpha_composite(big2, (810, 425))
        canvas.alpha_composite(big3, (810, 775))
    return canvas
def create_pdf(cards, PATH_UTILS,IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE):
   # --- CONFIG ---
    fichajes = get_cards_by_tipo(cards,["Fichaje destacado"])
    mvps = get_cards_by_tipo(cards,["MVP de la jornada"]) 
    peor = get_cards_by_tipo(cards,["Peor actuación de la jornada"])
    column_cards =get_cards_by_tipo(cards,["Fichaje destacado","Venta récord","Expulsión","Héroe bajo palos","Gol en propia"])
    
    # --- 1. Crear canvas base ---
    canvas = Image.new(
        "RGBA",
        (IMG_WIDTH, IMG_HEIGHT),
        (255, 255, 255, 255)
    )
    # --- 2. Creo Portada y botton ---
    if fichajes[0].get("dinero")> 40:
        create_portada(canvas,fichajes[0],PATH_UTILS)
        create_template(canvas,PATH_UTILS)
        portada_text = create_card(fichajes[0], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"Portada")
        create_botton(canvas,mvps,peor,None, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE)
    else:
        create_portada(mvps[0],PATH_UTILS)
        create_template(canvas,PATH_UTILS)
        portada_text = create_card(mvps[0], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"Portada")
        create_botton(canvas,mvps,peor,fichajes[0], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE)    
    
    
    canvas.alpha_composite(portada_text, (0,550))

    
    # --- 3. Creo Rumores ---
    rumores = create_card(get_cards_by_tipo(cards,["rumor"])[0], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"rumores")
    canvas.alpha_composite(rumores, (400,30))

    # --- 4. Creo Clasificacion ---
    clasificacion = create_card(get_cards_by_tipo(cards,["clasificacion"])[0], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"Clasificacion")
    canvas.alpha_composite(clasificacion, (525,150))

    # --- 5. Creo Columna Izquierda ---
    create_columns(canvas,column_cards, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE)
    
    return canvas