import os
from PIL import Image, ImageDraw, ImageFont
import requests
from bs4 import BeautifulSoup
from io import BytesIO
from src.utils.photo_utils import manager_photo
import json
from urllib.parse import urljoin

#IMG_WIDTH = (1080/4)
IMG_WIDTH = 1080 
IMG_HEIGHT = 1350
def create_clasification_card_horizontal(clasificacion_json,PATH_UTILS,width,height,IMAGES_TEAMS_DIR,DEFAULT_TEAM_IMAGE,font="Oswald-Bold.otf"):
    """
    Devuelve una imagen RGBA transparente con la clasificación horizontal.
    """
    font_path = os.path.join(PATH_UTILS, font)
    # --- 1. Ordenar por posición ---
    equipos = sorted(
        clasificacion_json.items(),
        key=lambda x: x[1]["posicion"]
    )

    n = len(equipos)
    col_w = width // n

    # --- 2. Crear canvas ---
    card = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)

    # --- 3. Alturas internas ---
    logo_h = int(height * 0.50)
    pts_h = height - logo_h

    # --- 4. Fuentes ---
    font_pts = ImageFont.truetype(font_path, int(pts_h * 0.6))

    for i, (team, data) in enumerate(equipos):
        x = i * col_w

        
        # --- ESCUDO ---
        logo_path=manager_photo(team, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE)
        logo = Image.open(logo_path).convert("RGBA")

        target_h = int(logo_h * 0.8)
        scale = target_h / logo.height
        logo = logo.resize((int(logo.width * scale), target_h), Image.LANCZOS)

        card.alpha_composite(
            logo,
            (
                x + col_w // 2 - logo.width // 2,
                logo_h // 2 - logo.height // 2
            )
        )

        # --- PUNTOS ---
        pts_text = str(data["puntos"])
        bbox = font_pts.getbbox(pts_text)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        draw.text(
            (
                x + col_w // 2 - w // 2,
                logo_h + pts_h // 2 - h // 2
            ),
            pts_text,
            font=font_pts,
            fill="#ff751f"
        )

    return card
def is_valid_photo(img_bytes: bytes, headers: dict) -> bool:
    # 1️⃣ Filtrar por Content-Type
    content_type = headers.get("Content-Type", "").lower()
    if "gif" in content_type:
        return False

    # 2️⃣ Filtrar por formato real
    try:
        img = Image.open(BytesIO(img_bytes))
        if img.format == "GIF":
            return False
    except Exception:
        return False

    return True
def download_player_image(player, team, save_dir="player_images"):
    """
    Busca y descarga la primera imagen válida del jugador.
    1) Intenta descargar directamente de Bing.
    2) Si hay página de origen, descarga la imagen real desde allí.
    Devuelve la ruta local de la imagen descargada o "" si falla.
    """
    os.makedirs(save_dir, exist_ok=True)
    query = f"{player} {team} jugador"
    url = f"https://www.bing.com/images/search?q={requests.utils.quote(query)}&form=HDRSC2"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/116.0.0.0 Safari/537.36"
    }

    html = requests.get(url, headers=headers, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")
    img_tags = soup.find_all("a", class_="iusc")

    for tag in img_tags:
        m_attr = tag.get("m")
        if not m_attr:
            continue

        try:
            data = json.loads(m_attr)
            img_url = data.get("murl")      # URL de la página de origen
            print(img_url)
            # Descargar la imagen final
            resp = requests.get(img_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue

            image = Image.open(BytesIO(resp.content)).convert("RGB")
            save_path = os.path.join(save_dir, f"{player.replace(' ', '_')}.jpg")
            image.save(save_path, "JPEG", quality=95)
            print(f"Imagen descargada en: {save_path}")
            return save_path

        except Exception as e:
            print(f"Error procesando una imagen: {e}")
            continue

    print("No se encontró ninguna imagen válida.")
    return ""
def get_cards_by_tipo(data: dict, tipos: list[str]) -> list:
    tipos = set(tipos)
    return [
        card
        for card in data.get("cards", [])
        if card.get("tipo") in tipos
    ]
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
def draw_multiline_text(tipo,draw, text, x, y, font, max_width, measure_only=False, line_spacing=3, paragraph_spacing=0, fill="#ff751f", stroke_fill="black", stroke_width=2,titulo=False):
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
    if ((tipo == "Portada") or (tipo == "Right_box") or titulo):
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
def create_template(canvas,tipo,PATH_UTILS):
    TOPBAR_PATH = "Top_"+tipo+".png"
    BOTTONBAR_PATH = "BottonBar.png"
    COLUMN_PATH = "Column.png"


    image_path_topbar = os.path.join(PATH_UTILS, TOPBAR_PATH)
    image_path_bottonbar = os.path.join(PATH_UTILS, BOTTONBAR_PATH)
    image_path_column = os.path.join(PATH_UTILS, COLUMN_PATH)

    # --- 1. Pegar barra superior --
    topbar = Image.open(image_path_topbar).convert("RGBA")
    canvas.alpha_composite(topbar, (375, 0))
    # --- 2. Pegar barra inferior ---
    bottonbar = Image.open(image_path_bottonbar).convert("RGBA")
    canvas.alpha_composite(bottonbar, (0, 1052))
    # --- 3. Pegar columna derecha ---
    #columnbar = Image.open(image_path_column).convert("RGBA")
    #canvas.alpha_composite(columnbar, (810, 0))
    # --- 4. Pegar Po ---
    logo = create_logo(PATH_UTILS)
    canvas.paste(logo, (-145, -200), logo)  

    return canvas
def create_card(card_info, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,tipo, PATH_UTILS, measure_only=False):
    FONT_PATH = "Extenda.ttf"
    font_title_path = os.path.join(PATH_UTILS, FONT_PATH)
    # Fuentes
    title_font = ImageFont.truetype(font_title_path, 40)
    subtitle_font = ImageFont.truetype("arial.ttf", 15)
    text_font = ImageFont.truetype("arial.ttf", 10) 
    card_width = IMG_WIDTH/4
    if (tipo == "Right_box"):
        card_width = IMG_WIDTH/3
        text_font = ImageFont.truetype("arial.ttf", 15)
    if tipo == "Portada":
        title_font = ImageFont.truetype(font_title_path, 125)
        subtitle_font = ImageFont.truetype("arial.ttf", 20)
        text_font = ImageFont.truetype("arial.ttf", 15) 
        card_width = IMG_WIDTH *0.75
    x_margin = 10
    max_width = card_width - 2 * x_margin

    # --- 1. Calcular altura total ---
    y = 10
    if (tipo != "Right_box"):
        y = draw_multiline_text(tipo,None, card_info["titulo"], x_margin, y, title_font, max_width, measure_only=True,titulo = True)
        y += 15
    y = draw_multiline_text(tipo,None, card_info["subtitulo"], x_margin, y, subtitle_font, max_width, measure_only=True)
    
    if tipo != "reduced":
        y += 25
        for frase in card_info["texto"]:
            y = draw_multiline_text(tipo,None, frase, x_margin, y, text_font, max_width, measure_only=True)
            y += 15
    final_height = y + 40  # margen inferior

    # --- 2. Crear imagen con altura calculada ---
    if (tipo == "standard") or (tipo == "reduced"):
        img = Image.new("RGBA", (int(card_width), int(final_height)), (255, 255, 255, 255))
    elif(tipo == "Right_box"):
        img = Image.new("RGBA", (int(card_width), int(final_height)), (0, 0, 0, 100))
    else:    
        img = Image.new("RGBA", (int(card_width), int(final_height)), (255, 255, 255, 0))
    # --- 3. Pegar imagen de fondo centrada ---
    escudo_manager = manager_photo(card_info.get("manager", ""), IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE)
    if (tipo != "Portada"):
        img = paste_center_background(img, escudo_manager, opacity=0.30)

    # --- 4. Dibujar texto encima ---
    draw = ImageDraw.Draw(img)
    y = 10
    if (tipo != "Right_box"):
        y = draw_multiline_text(tipo,draw, card_info["titulo"], x_margin, y, title_font, max_width,titulo = True)
        y += 20
    y = draw_multiline_text(tipo,draw, card_info["subtitulo"], x_margin, y, subtitle_font, max_width)
    y += 25
    if tipo != "reduced":
        for frase in card_info["texto"]:
            y = draw_multiline_text(tipo,draw, frase, x_margin, y, text_font, max_width)
            y += 15
    if measure_only:
        return final_height
    else:
        return img
def create_portada(canvas,card_info, PATH_UTILS):
    PORTADA_PATH = "Portada.jpg"
    download_player_image(card_info["jugador"],card_info["equipo"],PATH_UTILS)
    image_path_portada = os.path.join(PATH_UTILS, PORTADA_PATH)
    # --- 2. Pegar foto portada ---
    portada = Image.open(image_path_portada).convert("RGBA")

    min_width = IMG_WIDTH
    min_height = IMG_HEIGHT * 0.8
    w, h = portada.size

    if w < min_width:
        scale = min_width / w
        portada = portada.resize(
            (int(w * scale), int(h * scale)),
            Image.LANCZOS
        )
    w, h = portada.size
    if h < min_height:
        scale = min_height / h
        portada = portada.resize(
            (int(w * scale), int(h * scale)),
            Image.LANCZOS
        )


    target_center_x = IMG_WIDTH * 3 / 8
    w, h = portada.size

    x = int(target_center_x - w / 2)   
    canvas.alpha_composite(portada, (x, 0))    
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
def create_botton(canvas,cards,peor,corner_card, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE, PATH_UTILS):
    peorcard = create_card(peor[0], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard", PATH_UTILS)
    
    if corner_card is None:
        mvps1 = create_card(cards[0], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard", PATH_UTILS)
        mvps2 = create_card(cards[1], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard", PATH_UTILS)
        corner = create_card(cards[2], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard", PATH_UTILS)
    else:
        mvps1 = create_card(cards[1], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard", PATH_UTILS)
        mvps2 = create_card(cards[2], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard", PATH_UTILS)
        corner = create_card(corner_card, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"standard", PATH_UTILS)
    canvas.alpha_composite(peorcard, (0,1100))
    canvas.alpha_composite(mvps1, (270,1100))
    canvas.alpha_composite(mvps2, (540,1100))
    canvas.alpha_composite(corner, (810,1100))
    return canvas
def create_columns(canvas,columns, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE, PATH_UTILS):
    cards = []

    # construir lista lógica
    for c in columns:
        cards.append(("reduced", c))

    measured = []

    for tipo, data in cards:
        h = create_card(data, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE, tipo, PATH_UTILS, measure_only=True)
        measured.append((tipo, data, h))

    cursor_y = 1100   # margen inferior
    GAP = 0

    for tipo, data, h in reversed(measured):
        y = cursor_y - h

        card_img = create_card(data, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE, tipo, PATH_UTILS)
        canvas.alpha_composite(card_img, (810, y))

        cursor_y = y - GAP


    return canvas
def create_pdf(tipo,cards,clasificacion_json, PATH_UTILS,IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE):
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
        create_template(canvas,tipo,PATH_UTILS)
        portada_text = create_card(fichajes[0], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"Portada", PATH_UTILS)
        create_botton(canvas,mvps,peor,None, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE, PATH_UTILS)
    else:
        create_portada(canvas,mvps[0],PATH_UTILS)
        create_template(canvas,tipo,PATH_UTILS)
        portada_text = create_card(mvps[0], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"Portada", PATH_UTILS)
        create_botton(canvas,mvps,peor,fichajes[0], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE, PATH_UTILS)    
    
    
    canvas.alpha_composite(portada_text, (0,550))

    card_general = create_clasification_card_horizontal(clasificacion_json["general"],PATH_UTILS,width=600,height=75,IMAGES_TEAMS_DIR=IMAGES_TEAMS_DIR,DEFAULT_TEAM_IMAGE=DEFAULT_TEAM_IMAGE)
    canvas.alpha_composite(card_general, (490, 0))
    card_jornada = create_clasification_card_horizontal(clasificacion_json["jornada"],PATH_UTILS,width=600,height=75,IMAGES_TEAMS_DIR=IMAGES_TEAMS_DIR,DEFAULT_TEAM_IMAGE=DEFAULT_TEAM_IMAGE)
    canvas.alpha_composite(card_jornada, (490, 75))
    # --- 3. Creo Rumores ---
    rumores = create_card(get_cards_by_tipo(cards,["rumor"])[0], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"Right_box", PATH_UTILS)
    canvas.alpha_composite(rumores, (720,200))

    # --- 4. Creo Clasificacion ---
    clasificacion = create_card(get_cards_by_tipo(cards,["clasificacion"])[0], IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE,"Right_box", PATH_UTILS)
    canvas.alpha_composite(clasificacion, (720,200))

    # --- 5. Creo Columna Izquierda ---
    create_columns(canvas,column_cards, IMAGES_TEAMS_DIR, DEFAULT_TEAM_IMAGE, PATH_UTILS)
    
    return canvas