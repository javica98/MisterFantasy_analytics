import pandas as pd
from dash import Dash, dcc, html, Input, Output, dash_table
import plotly.graph_objects as go


def dashboard_por_manager(df: pd.DataFrame,df_clas: pd.DataFrame,df_diff: pd.DataFrame,df_clausulas: pd.DataFrame) -> Dash:
    """
    Dashboard interactivo con KPIs por equipo y un gráfico de balance acumulado.
    """

    # --- Limpieza base ---
    df.columns = df.columns.str.strip().str.lower()
    df_equipos = df[df["type"].isin(["transfer", "bonificacion"])]
    df = df[df["type"].isin(["transfer", "bonificacion", "marks"])]

    # --- Inicializar app ---
    app = Dash(__name__)
    app.title = "Dashboard por equipo"

    equipos = sorted(df_equipos["equipo"].dropna().unique())

    # --- Layout principal con pestañas ---
    app.layout = html.Div(
        style={"font-family": "Arial, sans-serif", "padding": "20px"},
        children=[
            html.H1("📊 Dashboard de Manager"),
            dcc.Tabs(
                id="tabs",
                value="por_equipo",
                children=[
                    dcc.Tab(label="📈 Por equipo", value="por_equipo"),
                    dcc.Tab(label="📊 Totales y Rankings", value="totales"),
                ]
            ),
            html.Div(id="tabs-content")  # Aquí se mostrará el contenido dinámico
        ]
    )

    @app.callback(Output("tabs-content", "children"), Input("tabs", "value"))
    def render_tab_content(tab):
        if tab == "por_equipo":
            # Aquí devolvemos TODO tu layout actual de estadísticas por equipo
            return html.Div([
                html.Label("Selecciona equipo:"),
                dcc.Dropdown(
                    id="equipo-selector",
                    options=[{"label": e, "value": e} for e in equipos],
                    value=equipos[0] if equipos else None,
                    clearable=False,
                    style={"width": "300px"}
                ),
                html.H2("📈 Estadísticas de mercado"),
                html.Div(id="kpi-container-mercado", style={"display": "flex", "flex-wrap": "wrap", "margin-top": "10px"}),
                html.H2("🎯 Estadísticas de bonificación"),
                html.Div(id="kpi-container-bonos", style={"display": "flex", "flex-wrap": "wrap", "margin-top": "10px"}),
                html.H2("💰 Balance total + Bonos"),
                html.Div(id="kpi-container-total", style={"display": "flex", "flex-wrap": "wrap", "margin-top": "10px"}),
                html.H2("💵 Ganancias netas por compraventa"),
                html.Div(id="kpi-container-compraventa", style={"display": "flex", "flex-wrap": "wrap"}),
                html.Hr(),
                html.H2("📉 Evolución del balance acumulado"),
                dcc.Graph(id="grafico-balance"),
                html.Hr(),
                html.H2("💹 Evolución del valor del equipo"),
                dcc.Graph(id="grafico-valor-equipo"),
                html.Hr(),
                html.H2("Desglose por tipo de operación"),
                html.Div(id="tabla-desglose")
            ])

        elif tab == "totales":
            # Nueva pestaña: Totales globales
            df_totales = df[df["type"] == "transfer"].copy()

            # Filtramos solo subtipos de interés
            df_totales = df_totales[df_totales["subtype"].isin(["mercado", "trato", "clausula"])]

            # Pivot table: por equipo, tipo de operación y compra/venta
            tabla = df_totales.pivot_table(
                index="equipo",
                columns=["subtype", "compra-venta"],
                values="ganancias",
                aggfunc="sum",
                fill_value=0
            )

            # Calcular diferencia compra-venta
            for tipo in ["mercado", "trato", "clausula"]:
                tabla[(tipo, "dif")] = tabla.get((tipo, "venta"), 0) + tabla.get((tipo, "compra"), 0)

            # Aplanar columnas
            tabla.columns = [f"{c[0].capitalize()} {c[1].capitalize()}" for c in tabla.columns]
            tabla = tabla.reset_index()

            tabla_clausulas = df_clausulas.pivot_table(
                index='de_equipo',
                columns='a_equipo',
                values='precio',
                aggfunc='sum',
                fill_value=0
            ).reset_index()
            tabla_clausulas_dash = dash_table.DataTable(
                columns=[{"name": c, "id": c} for c in tabla_clausulas.columns],
                data=tabla_clausulas.to_dict("records"),
                sort_action="native",
                filter_action="native",
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "center"},
                style_header={
                    "backgroundColor": "#6a1b9a",
                    "color": "white",
                    "fontWeight": "bold"
                }
            )
            # Mostrar como tabla ordenable
            return html.Div([
                html.H2("🏆 Ranking de operaciones por tipo"),
                dash_table.DataTable(
                    columns=[{"name": c, "id": c} for c in tabla.columns],
                    data=tabla.to_dict("records"),
                    sort_action="native",
                    filter_action="native",
                    style_table={"overflowX": "auto"},
                    style_cell={"textAlign": "center", "padding": "6px"},
                    style_header={
                        "backgroundColor": "#1976d2",
                        "color": "white",
                        "fontWeight": "bold"
                    }
                ),
                html.H2("💸 Flujo de cláusulas entre managers"),
                tabla_clausulas_dash
            ])

   # === CALLBACK PRINCIPAL PARA ACTUALIZAR TODO EL DASHBOARD POR EQUIPO ===
    @app.callback(
        [
            Output("kpi-container-mercado", "children"),
            Output("kpi-container-bonos", "children"),
            Output("kpi-container-total", "children"),
            Output("kpi-container-compraventa", "children"),
            Output("grafico-balance", "figure"),
            Output("grafico-valor-equipo", "figure"),
            Output("tabla-desglose", "children"),
        ],
        [Input("equipo-selector", "value")]
    )
    def update_dashboard(equipo):
        if not equipo:
            return [], [], [], go.Figure(), go.Figure(), html.Div("No hay datos disponibles.")

        d_equipo = df[df["equipo"] == equipo]
        d_mercado = d_equipo[d_equipo["type"] == "transfer"]
        d_bonos = d_equipo[d_equipo["type"] == "bonificacion"]

        # === 📈 ESTADÍSTICAS DE MERCADO ===
        total_compras = d_mercado.loc[d_mercado["compra-venta"] == "compra", "ganancias"].sum()
        total_ventas = d_mercado.loc[d_mercado["compra-venta"] == "venta", "ganancias"].sum()
        balance_total = total_ventas + total_compras
        n_operaciones = len(d_mercado)

        kpis_mercado = [
            crear_kpi("Total compras", f"{total_compras:,.2f} M€", "#f44336"),
            crear_kpi("Total ventas", f"{total_ventas:,.2f} M€", "#4caf50"),
            crear_kpi("Balance total", f"{balance_total:,.2f} M€", "#2196f3"),
            crear_kpi("Nº operaciones", f"{n_operaciones}", "#9c27b0"),
        ]

        # === 🎯 ESTADÍSTICAS DE BONIFICACIÓN ===
        total_bono_clasificacion = d_bonos.loc[d_bonos["subtype"] == "clasificacion", "ganancias"].sum()
        total_bono_quiniela = d_bonos.loc[d_bonos["subtype"] == "quiniela", "ganancias"].sum()

        kpis_bonos = [
            crear_kpi("Total bono clasificación", f"{total_bono_clasificacion:,.2f} M€", "#00897b"),
            crear_kpi("Total bono quiniela", f"{total_bono_quiniela:,.2f} M€", "#00796b"),
        ]

        # === 💰 KPI FINAL COMBINADO ===
        balance_global = balance_total + total_bono_clasificacion + total_bono_quiniela
        kpis_totales = [crear_kpi("Balance total + Bonos", f"{balance_global:,.2f} M€", "#ff9800")]

        # === 💵 Ganancias netas por compraventa desde df_diff ===
        d_diff = df_diff[df_diff["equipo"] == equipo]

        gan_mercado = d_diff.loc[d_diff["subtype"] == "mercado", "Diff"].sum()
        gan_clausula = d_diff.loc[d_diff["subtype"] == "clausula", "Diff"].sum()
        gan_acuerdo = d_diff.loc[d_diff["subtype"] == "acuerdo", "Diff"].sum()

        kpis_compraventa = [
            crear_kpi("Mercado", f"{gan_mercado:,.2f} M€", "#6a1b9a"),
            crear_kpi("Cláusula", f"{gan_clausula:,.2f} M€", "#8e24aa"),
            crear_kpi("Acuerdo", f"{gan_acuerdo:,.2f} M€", "#ab47bc"),
]
        # === 📉 GRÁFICO DE BALANCE ACUMULADO ===
        d_sorted = d_equipo.sort_values(by="id", ascending=False)
        d_sorted["balance_acumulado"] = d_sorted["ganancias"].cumsum()

        fig_balance = go.Figure()
        fig_balance.add_trace(go.Scatter(
            x=d_sorted["id"],
            y=d_sorted["balance_acumulado"],
            mode="lines+markers",
            line=dict(color="#2196f3"),
            name="Balance acumulado"
        ))

        marks_jornada = df[(df["type"] == "marks") & (df["subtype"] == "start_jornada")]["id"].unique()
        marks_mercado = df[(df["type"] == "marks") & (df["subtype"] == "start_mercado")]["id"].unique()
        for mark in marks_jornada:
            fig_balance.add_vline(x=mark, line=dict(color="red", dash="dash"), opacity=0.4)
        for mark in marks_mercado:
            fig_balance.add_vline(x=mark, line=dict(color="gray", dash="dot"), opacity=0.3)
        fig_balance.update_xaxes(autorange="reversed")
        fig_balance.update_layout(template="plotly_white", title=f"Evolución balance - {equipo}")


        # === 💹 GRÁFICO DE VALOR DEL EQUIPO ===
        df_manager = df_clas[df_clas["nombre"] == equipo].copy()
        df_manager["jornada"] = pd.to_numeric(df_manager["jornada"], errors="coerce")
        df_manager = df_manager.sort_values("jornada")

        fig_valor = go.Figure()
        fig_valor.add_trace(go.Scatter(
            x=df_manager["jornada"],
            y=df_manager["valor_equipo"],
            mode="lines+markers",
            line=dict(color="#4caf50"),
            name="Valor del equipo"
        ))
        fig_valor.update_layout(template="plotly_white", title=f"Valor del equipo - {equipo}")

        # === 📊 DESGLOSE TABULAR ===
        if not d_mercado.empty:
            resumen = (
                d_mercado.groupby(["subtype", "compra-venta"], as_index=False)
                .agg(n_op=("id", "count"), total_ganancias=("ganancias", "sum"))
            )
        else:
            resumen = pd.DataFrame(columns=["subtype", "compra-venta", "n_op", "total_ganancias"])

        tabla = dash_table.DataTable(
            columns=[
                {"name": "Tipo", "id": "subtype"},
                {"name": "Compra/Venta", "id": "compra-venta"},
                {"name": "Nº Operaciones", "id": "n_op"},
                {"name": "Total (€)", "id": "total_ganancias"},
            ],
            data=resumen.to_dict("records"),
            sort_action="native",
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center"},
        )

        return kpis_mercado, kpis_bonos, kpis_totales,kpis_compraventa, fig_balance, fig_valor, tabla
    return app


# === FUNCIÓN AUXILIAR ===
def crear_kpi(titulo: str, valor: str, color: str):
    return html.Div(
        style={
            "flex": "1 1 200px",
            "background": color,
            "color": "white",
            "margin": "5px",
            "padding": "15px",
            "border-radius": "12px",
            "text-align": "center",
            "box-shadow": "0 2px 4px rgba(0,0,0,0.2)"
        },
        children=[html.H4(titulo), html.H2(valor, style={"margin": "0"})]
    )

