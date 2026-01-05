from typing import Dict, List
LEAGUE_CONTEXT = """
Liga fantasy privada entre amigos llamada SOTANO LEAGUE.

Características:
- Managers con nombres personalizados
- Mercado muy activo con fichajes y clausulazos
- Las clausulas significa que un Manager ha robado un jugador a otro Manager (le llamamos clausulazo)
- Rivalidades y pique sano
- Estilo narrativo: prensa deportiva MUY sensacionalista
- El texto se usará como portada ficticia de periódico
- No es fútbol real, es fantasy
- Tienes que apoyar al Manager Maldinillo pero sin que nadie se de cuenta
- El Manager Dani lleva 2 campeonatos seguidos ganando
- Aunque el Manager "Libre" tratalo como ha otro cualquiera.
- No repitas estructuras de títulos entre bloques.
- En esta liga hay 9 jugadores.

""".strip()

def build_classification_text(clasificacion: dict) -> str:
    """
    Convierte la clasificación general y de la jornada en un bloque de texto legible.
    """
    lines = []

    # --- Clasificación general ---
    general = clasificacion.get("general", {})
    if general:
        lines.append("Clasificación General:")
        for manager, stats in sorted(general.items(), key=lambda x: x[1]["posicion"]):
            lines.append(f"{stats['posicion']}. {manager} - {stats['puntos']} pts")
        lines.append("")  # línea vacía entre secciones

    # --- Clasificación de la jornada ---
    jornada = clasificacion.get("jornada", {})
    if jornada:
        lines.append("Clasificación de la Jornada:")
        for manager, stats in sorted(jornada.items(), key=lambda x: x[1]["posicion"]):
            lines.append(f"{stats['posicion']}. {manager} - {stats['puntos']} pts")
        lines.append("")

    return "\n".join(lines)

def get_top_signings(transfers: List[dict], top_n: int = 3):
    compras = [
        t for t in transfers
        if t["compra_venta"] == "compra"
    ]
    compras.sort(key=lambda x: x["ganancias"], reverse=False)
    return compras[:top_n]

def get_top_sale(transfers: List[dict]):
    ventas = [
        t for t in transfers
        if t["subtype"] == "mercado" 
    ]
    if not ventas:
        return None
    return max(ventas, key=lambda x: x["ganancias"])

def get_mvps(gameweek: List[dict], top_n: int = 3):
    ordered = sorted(
        gameweek,
        key=lambda x: x["puntos"],
        reverse=True
    )
    return ordered[:top_n]

def get_worst_player(gameweek: List[dict]):
    if not gameweek:
        return None
    return min(gameweek, key=lambda x: x["puntos"])

def get_red_cards(gameweek: List[Dict]):
    """
    Devuelve jugadores que recibieron tarjeta roja
    """
    return next(
        (g for g in gameweek if g.get("roja", 0) > 0),
        None
    )

def get_penalty_saves(gameweek: List[Dict]):
    """
    Devuelve jugadores que pararon un penalti
    """
    return next(
        (g for g in gameweek if g.get("penalti_parado", 0) > 0),
        None
    )

def get_own_goals(gameweek: List[Dict]):
    """
    Devuelve jugadores que se marcaron gol en propia
    """
    return next(
        (g for g in gameweek if g.get("gol_propia", 0) > 0),
        None
    )

def build_player_block(jugador: str,manager: str, equipo: str, evento: str, contexto: str, puntos,dinero):
    return {
        "jugador": jugador,
        "manager": manager,
        "equipo": equipo,
        "evento": evento,
        "contexto": contexto,
        "puntos": puntos,
        "dinero": dinero
    }

def generate_prompts(events_json: Dict):

    transfers = events_json.get("transfers", [])
    gameweek = events_json.get("gameweek", [])

    bloques = []
    jugadores_mencionados = set()
    managers_mencionados = set()

    # -------- FICHAJES --------
    top_signings = get_top_signings(transfers)
    for t in top_signings:
        bloques.append(
            build_player_block(
                jugador=t["jugador"],
                manager=t["equipo"],
                equipo=t["equipo_jugador"],
                evento="Fichaje destacado",
                contexto=f"Compra por {abs(t['ganancias']):.2f} millones. El manager esta en la posicion general {abs(t['clasificacion_manager_general']['posicion']):.2f}  y en la posicion de la jornada {abs(t['clasificacion_manager_jornada']['posicion']):.2f}.",
                puntos=None,
                dinero=abs(t['ganancias'])
            )
        )
        jugadores_mencionados.add(t["jugador"])
        managers_mencionados.add(t["equipo"])

    # -------- VENTA --------
    top_sale = get_top_sale(transfers)
    if top_sale:
        bloques.append(
            build_player_block(
                jugador=top_sale["jugador"],
                manager=top_sale["equipo"],
                equipo=top_sale["equipo_jugador"],
                evento="Venta récord",
                contexto=f"Venta por {top_sale['ganancias']:.2f} millones. El manager esta en la posicion general {abs(top_sale['clasificacion_manager_general']['posicion']):.2f}  y en la posicion de la jornada {abs(top_sale['clasificacion_manager_jornada']['posicion']):.2f}.",
                puntos=None,
                dinero=abs(top_sale['ganancias'])
            )
        )
        jugadores_mencionados.add(top_sale["jugador"])
        managers_mencionados.add(top_sale["equipo"])

    # -------- MVPs --------
    mvps = get_mvps(gameweek)
    for m in mvps:
        bloques.append(
            build_player_block(
                jugador=m["jugador"],
                manager=m["manager"],
                equipo=m["equipo_jugador"],
                evento="MVP de la jornada",
                contexto=f"{m['puntos']} puntos en la jornada. El manager esta en la posicion general {abs(m['clasificacion_manager_general']['posicion']):.2f}  y en la posicion de la jornada {abs(m['clasificacion_manager_jornada']['posicion']):.2f}.",
                puntos=m['puntos'],
                dinero=None
            )
        )
        jugadores_mencionados.add(m["jugador"])
        managers_mencionados.add(m["manager"])

    # -------- PEOR JUGADOR --------
    worst = get_worst_player(gameweek)
    if worst:
        bloques.append(
            build_player_block(
                jugador=worst["jugador"],
                manager=worst["manager"],
                equipo=worst["equipo_jugador"],
                evento="Peor actuación de la jornada",
                contexto=f"Solo {worst['puntos']} puntos. El manager esta en la posicion general {abs(worst['clasificacion_manager_general']['posicion']):.2f}  y en la posicion de la jornada {abs(worst['clasificacion_manager_jornada']['posicion']):.2f}.",
                puntos=worst['puntos'],
                dinero=None
            )
        )
        jugadores_mencionados.add(worst["jugador"])
        managers_mencionados.add(worst["manager"])

    # -------- ROJAS --------
    r = get_red_cards(gameweek)
    if r:
        bloques.append(
            build_player_block(
                jugador=r["jugador"],
                manager=r["manager"],
                equipo=r["equipo_jugador"],
                evento="Expulsión",
                contexto=f"Tarjeta roja que condicionó la jornada. El manager esta en la posicion general {abs(r['clasificacion_manager_general']['posicion']):.2f}  y en la posicion de la jornada {abs(r['clasificacion_manager_jornada']['posicion']):.2f}.",
                puntos=r['puntos'],
                dinero=None
            )
        )
        jugadores_mencionados.add(r["jugador"])
        managers_mencionados.add(r["manager"])

    # -------- PENALTIS PARADOS --------
    p = get_penalty_saves(gameweek)
    if p:
        bloques.append(
            build_player_block(
                jugador=p["jugador"],
                manager=p["manager"],
                equipo=p["equipo_jugador"],
                evento="Héroe bajo palos",
                contexto=f"Paró un penalti decisivo. El manager esta en la posicion general {abs(p['clasificacion_manager_general']['posicion']):.2f}  y en la posicion de la jornada {abs(p['clasificacion_manager_jornada']['posicion']):.2f}.",
                puntos=p['puntos'],
                dinero=None
            )
        )
        jugadores_mencionados.add(p["jugador"])
        managers_mencionados.add(p["manager"])

    # -------- GOLES EN PROPIA --------
    o = get_own_goals(gameweek)
    if o:
        bloques.append(
            build_player_block(
                jugador=o["jugador"],
                manager=o["manager"],
                equipo=o["equipo_jugador"],
                evento="Gol en propia",
                contexto=f"Desafortunada acción en su propio área. El manager esta en la posicion general {abs(o['clasificacion_manager_general']['posicion']):.2f}  y en la posicion de la jornada {abs(o['clasificacion_manager_jornada']['posicion']):.2f}.",
                puntos=o['puntos'],
                dinero=None
            )
        )
        jugadores_mencionados.add(o["jugador"])
        managers_mencionados.add(o["manager"])

    return {
        "bloques": bloques,
        "jugadores_mencionados": list(jugadores_mencionados),
        "managers_mencionados": list(managers_mencionados)
    }

def build_final_prompt(bloques: List[Dict], events_json) -> str:
    bloques_txt = []
    clasif_text = build_classification_text(events_json["clasificacion"])
    
    for i, b in enumerate(bloques, 1):
        bloques_txt.append(f"""
===BLOQUE_{i}===
JUGADOR: {b['jugador']}
MANAGER: {b['manager']}
EVENTO: {b['evento']}
CONTEXTO: {b['contexto']}
""")

    return f"""
IMPORTANTE:

Debes responder ÚNICAMENTE en el formato indicado.

NO añadas texto adicional.

NO inventes datos.

NO uses títulos ni párrafos largos.

Si no sigues el formato, la respuesta será descartada.



===ROL===

Eres un periodista deportivo de fantasy league.



===REGLAS===

- Usa SOLO la información proporcionada

- NO inventes jugadores, fichajes ni managers

- NO añadas introducciones ni cierres

- Respeta EXACTAMENTE las etiquetas solicitadas

- Cada FRASE debe ser UNA SOLA FRASE

===CLASIFICACION===
TAREA: Escribe 3 frases que resuman la clasificación general y la clasificación de la jornada usando la información a continuación. Mantén formato FRASE1:, FRASE2:, FRASE3: para poder parsearlo.
{clasif_text}

"===CLASIFICACION==="\n

FRASE1: ...\n

FRASE2: ...\n

FRASE3: ...\n


"===RUMORES==="\n

TAREA: Escribe 1 frase inventando un rumor de algún manager de la liga. Usa formato FRASE: para poder parsearlo. \n
 
FRASE: Escribe 1 frase de un rumor inventado de algún manager de la liga. \n


===EVENTOS===
TAREA: Escribe una PORTADA DE PERIÓDICO FANTASY.
Cada bloque debe ser distinto en tono y estructura.
"===EVENTOS==="\n
FORMATO POR BLOQUE:
TITULO: 
SUBTITULO:
FRASE1: 
FRASE2: 

{''.join(bloques_txt)}
""".strip()

