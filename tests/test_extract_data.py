"""
Tests para los extractores de HTML de src/data/ (hallazgo WEB-02: eran el
código más frágil del repo — parsers de HTML de una web externa que puede
cambiar de estructura cualquier día — sin ningún test).

Incluye la cobertura del hallazgo DATA-05: si el contenedor esperado
aparece pero la estructura interna de la fila cambió, antes esto reventaba
con un KeyError genérico al construir el DataFrame vacío; ahora se
detecta y se devuelve un DataFrame vacío con las columnas correctas, con
un warning explícito.
"""
import pytest

from src.data.extract_subidas_bajadas import extraer_subidas_bajadas
from src.data.extract_clasificacion import extraer_clasificaciones
from src.data.extract_mercado import extraer_mercado
from src.data.extract_gameweek import extraer_gameweek


class TestExtraerSubidasBajadas:
    def test_extrae_una_fila_valida(self):
        html = """
        <table class="thin-scrollbar">
            <tr>
                <a class="btn btn-sw-link">K. Mbappé</a>
                <td class="td-right green">172</td>
            </tr>
        </table>
        """
        df = extraer_subidas_bajadas(html)
        assert list(df.columns) == ["date", "nombre", "variacion"]
        assert len(df) == 1
        assert df.iloc[0]["nombre"] == "K. Mbappé"
        assert df.iloc[0]["variacion"] == 0.172

    def test_sin_tablas_devuelve_vacio_con_columnas(self):
        df = extraer_subidas_bajadas("<html><body>Sin nada relevante</body></html>")
        assert list(df.columns) == ["date", "nombre", "variacion"]
        assert df.empty

    def test_tabla_presente_pero_estructura_interna_rota_no_revienta(self):
        # Reproduce el hallazgo DATA-05: el contenedor thin-scrollbar existe,
        # pero ninguna fila tiene los tags internos esperados (a.btn-sw-link,
        # td.td-right) — antes esto lanzaba KeyError al hacer
        # df['variacion'].astype(float) sobre un DataFrame sin esa columna.
        html = """
        <table class="thin-scrollbar">
            <tr><td>estructura completamente distinta</td></tr>
        </table>
        """
        df = extraer_subidas_bajadas(html)
        assert list(df.columns) == ["date", "nombre", "variacion"]
        assert df.empty


class TestExtraerClasificaciones:
    HTML_VALIDO = """
    <div class="panel panel-gameweek">
        <div class="gameweek-selector-inline">
            <a class="btn btn--secondary btn--md selected">Jornada 5</a>
        </div>
        <ul class="player-list player-list--primary">
            <li>
                <div class="player-row">
                    <div class="name">Dani</div>
                    <div class="position">1</div>
                    <div class="points">120</div>
                    <div class="played">45000000</div>
                </div>
            </li>
        </ul>
    </div>
    """

    def test_extrae_una_fila_valida(self):
        df = extraer_clasificaciones(self.HTML_VALIDO)
        assert list(df.columns) == ["jornada", "nombre", "posicion", "puntos", "valor_equipo"]
        assert len(df) == 1
        assert df.iloc[0]["jornada"] == 5
        assert df.iloc[0]["nombre"] == "Dani"

    def test_sin_paneles_devuelve_vacio_con_columnas(self):
        df = extraer_clasificaciones("<html><body>Sin nada relevante</body></html>")
        assert list(df.columns) == ["jornada", "nombre", "posicion", "puntos", "valor_equipo"]
        assert df.empty

    def test_panel_presente_pero_sin_player_row_no_revienta(self):
        # Reproduce el hallazgo DATA-05: panel + selector + lista de
        # jugadores presentes, pero ningún <li> tiene div.player-row —
        # antes esto lanzaba KeyError al hacer df['valor_equipo'] / 1e6
        # sobre un DataFrame sin esa columna.
        html = """
        <div class="panel panel-gameweek">
            <div class="gameweek-selector-inline">
                <a class="btn btn--secondary btn--md selected">Jornada 5</a>
            </div>
            <ul class="player-list player-list--primary">
                <li><div class="otra-estructura">sin player-row</div></li>
            </ul>
        </div>
        """
        df = extraer_clasificaciones(html)
        assert list(df.columns) == ["jornada", "nombre", "posicion", "puntos", "valor_equipo"]
        assert df.empty


class TestExtraerMercado:
    HTML_VALIDO = """
    <div class="wrapper wrapper--spaced">
      <ul id="list-on-sale">
        <li>
          <div class="date">Maldinillo, Finaliza en 1d 6h</div>
          <div class="player-row">
            <div class="name">L. Boyé<svg><use href="#injury"></use></svg></div>
            <div class="underName">7.003.000 &euro;</div>
            <div class="player-position" data-position="4"></div>
            <div class="points">0</div>
            <div class="icons"><img class="team-logo" src="/teams/48.png"></div>
            <div class="avg">0.0</div>
          </div>
        </li>
      </ul>
    </div>
    """

    def test_extrae_un_jugador_valido(self):
        df = extraer_mercado(self.HTML_VALIDO)
        assert len(df) == 1
        row = df.iloc[0]
        assert row["manager"] == "Maldinillo"
        assert row["periodo"] == "1d 6h"
        assert row["jugador"] == "L. Boyé"
        assert row["precio"] == pytest.approx(7.003)
        assert row["posicionJugador"] == 4
        assert row["equipoLiga"] == "48"
        assert row["estado"] == "injury"

    def test_sin_contenedor_principal_devuelve_vacio(self):
        df = extraer_mercado("<html><body>Sin nada relevante</body></html>")
        assert df.empty

    def test_sin_jugadores_en_venta_devuelve_vacio(self):
        html = '<div class="wrapper wrapper--spaced">Nada en venta ahora mismo</div>'
        df = extraer_mercado(html)
        assert df.empty


class TestExtraerGameweek:
    HTML_VALIDO = """
    <div class="gameweek-wrapper">
      <div class="section-title"><h3>Jornada 3</h3></div>
      <div class="gameweek-match" data-status="played">
        <div class="info">
          <div class="scoreboard">
            <a class="btn btn-sw-link" href="/teams/15">Real Madrid</a>
            <span class="goals">2</span>
            <a class="btn btn-sw-link" href="/teams/3">Barça</a>
            <span class="goals">1</span>
          </div>
          <div class="team">
            <div class="user">
              <div class="name">Maldinillo</div>
              <ul>
                <li>
                  <strong>K. Mbappé</strong>
                  <span class="player-position" data-position="4"></span>
                  <span class="points">18</span>
                  <span class="events"><use href="#events-goal"></use><use href="#events-goal"></use></span>
                </li>
              </ul>
            </div>
          </div>
          <div class="team">
            <div class="user">
              <div class="name">Dani</div>
              <ul>
                <li>
                  <strong>Raphinha</strong>
                  <span class="player-position" data-position="4"></span>
                  <span class="points">10</span>
                  <span class="events"></span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
    """

    def test_extrae_ambos_jugadores_del_partido(self):
        df = extraer_gameweek(self.HTML_VALIDO)
        assert len(df) == 2
        assert set(df["NombreJugador"]) == {"K. Mbappé", "Raphinha"}
        mbappe = df[df["NombreJugador"] == "K. Mbappé"].iloc[0]
        assert mbappe["Jornada"] == 3
        assert mbappe["Manager"] == "Maldinillo"
        assert mbappe["Puntos"] == 18
        assert mbappe["Goles"] == 2
        assert mbappe["EquipoLocal"] == 15
        assert mbappe["EquipoVisitante"] == 3

    def test_jornada_que_aun_no_empieza_se_ignora(self):
        html = """
        <div class="gameweek-wrapper">
          <div class="gameweek-matches-summary">
            <div class="section-title"><h3>Empieza en 3 días</h3></div>
          </div>
        </div>
        """
        df = extraer_gameweek(html)
        assert df.empty

    def test_sin_gameweek_wrapper_devuelve_vacio(self):
        df = extraer_gameweek("<html><body>Sin nada relevante</body></html>")
        assert df.empty
