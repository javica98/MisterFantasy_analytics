from bs4 import BeautifulSoup
import re
import pandas as pd
import logging
from datetime import date
from collections import Counter

logger = logging.getLogger(__name__)


def extraer_gameweek(html: str) -> pd.DataFrame:
    """
    Extrae la información de una gameweek y la devuelve como DataFrame
    """

    try:
        soup = BeautifulSoup(html, "html.parser")

        filas = []
        hoy = date.today().isoformat()

        # Función auxiliar para extraer ID de equipo
        def extraer_team_id(href: str):
            m = re.search(r'teams/(\d+)', href)
            return int(m.group(1)) if m else None

        # 1. Buscar gameweek-wrapper
        for gw in soup.select('.gameweek-wrapper'):

            # 1.1 Comprobar que NO haya "Empieza en"
            summary_title = gw.select_one('.gameweek-matches-summary .section-title h3')
            if summary_title and summary_title.text.strip().startswith("Empieza en"):
                continue

            # 2.1 Date
            fecha = hoy

            # 2.2 Jornada (buscar SOLO fuera de matches-summary)
            jornada = None
            for title in gw.select(':scope > .section-title h3'):
                txt = title.text.strip()
                if txt.startswith("Jornada"):
                    jornada = txt.replace("Jornada", "").strip()
                    break

            if jornada is None:
                continue

            # 2.3 Partidos jugados
            partidos = gw.select('.gameweek-match[data-status="played"]')

            for partido in partidos:
                info = partido.select_one('.info')
                if not info:
                    continue

                # 3.1 Equipos y resultados
                equipos = info.select('.btn.btn-sw-link')
                goles = info.select('.scoreboard .goals')

                if len(equipos) < 2 or len(goles) < 2:
                    continue

                equipo_local = extraer_team_id(equipos[0].get('href', ''))
                equipo_visitante = extraer_team_id(equipos[1].get('href', ''))

                resultado_local = int(goles[0].text.strip())
                resultado_visitante = int(goles[1].text.strip())

                # 3.2 Equipos (local / visitante)
                teams = partido.select('.team')

                for idx, team in enumerate(teams):
                    # 4.1 EquipoJugador
                    equipo_jugador = equipo_local if idx == 0 else equipo_visitante

                    # 4.2 Managers
                    users = team.select('.user')

                    for user in users:
                        # 5.1 Manager
                        manager_tag = user.select_one('.name')
                        if not manager_tag:
                            continue
                        manager = manager_tag.text.strip()

                        # 5.2 Jugadores
                        jugadores = user.select('ul li')

                        for jugador in jugadores:
                            # 6.1 NombreJugador
                            nombre_tag = jugador.select_one('strong')
                            if not nombre_tag:
                                continue
                            nombre = nombre_tag.text.strip()

                            # 6.2 Posición
                            pos_tag = jugador.select_one('.player-position')
                            posicion = int(pos_tag['data-position']) if pos_tag and pos_tag.has_attr('data-position') else None

                            # 6.3 Puntos
                            puntos_tag = jugador.select_one('.points')
                            puntos = int(puntos_tag.text.strip()) if puntos_tag else 0

                            # 6.4 Eventos
                            eventos = jugador.select('.events use')
                            event_hrefs = [e.get('href', '') for e in eventos]

                            def contar_evento(nombre):
                                return sum(nombre in h for h in event_hrefs)

                            cambio = int(any("events-sub_out" in h for h in event_hrefs))
                            suplente = int(any("events-sub_in" in h for h in event_hrefs))

                            fila = {
                                "Date": fecha,
                                "Jornada": int(jornada),
                                "EquipoLocal": equipo_local,
                                "ResultadoLocal": resultado_local,
                                "EquipoVisitante": equipo_visitante,
                                "ResultadoVisitante": resultado_visitante,
                                "EquipoJugador": equipo_jugador,
                                "Manager": manager,
                                "NombreJugador": nombre,
                                "Posicion": posicion,
                                "Puntos": puntos,
                                "Suplente": suplente,
                                "Cambio": cambio,
                                "Goles": contar_evento("events-goal"),
                                "Asistencias": contar_evento("events-assist"),
                                "GolPropia": contar_evento("events-own_goal"),
                                "PenaltiMarcado": contar_evento("events-penalty"),
                                "PenaltiFallado": contar_evento("events-missed_penalty"),
                                "PenaltiParado": contar_evento("events-saved_penalty"),
                                "Amarilla": contar_evento("events-yellow"),
                                "Roja": int(any("events-red" in h for h in event_hrefs)),
                            }

                            filas.append(fila)

        df = pd.DataFrame(filas)

        # Normalización final de columnas numéricas
        int_cols = [
            "Jornada", "EquipoLocal", "EquipoVisitante", "EquipoJugador",
            "ResultadoLocal", "ResultadoVisitante",
            "Puntos", "Suplente", "Cambio", "Goles", "Asistencias",
            "GolPropia", "PenaltiMarcado", "PenaltiFallado",
            "PenaltiParado", "Amarilla", "Roja"
        ]

        for col in int_cols:
            if col in df.columns:
                df[col] = df[col].fillna(0).astype(int)

        return df

    except Exception as e:
        logger.exception(f"❌ Error general en extraer_gameweek: {e}")
        return pd.DataFrame()
