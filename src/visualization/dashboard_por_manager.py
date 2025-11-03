import pandas as pd
from dash import Dash, dcc, html, Input, Output
import plotly.graph_objects as go


def dashboard_por_manager(df: pd.DataFrame) -> Dash:
    """
    Dashboard interactivo con KPIs por equipo y un gráfico de balance acumulado.
    """

    # --- Limpieza base ---
    df.columns = df.columns.str.strip().str.lower()
    df = df[df["type"].isin(["transfer", "bonificacion", "marks"])]

    # --- Inicializar app ---
    app = Dash(__name__)
    app.title = "Dashboard por equipo"

    equipos = sorted(df["equipo"].dropna().unique())

    # --- Layout ---
    app.layout = html.Div(
        style={"font-family": "Arial, sans-serif", "padding": "20px"},
        children=[
            html.H1("📊 Estadísticas por equipo"),
            html.Label("Selecciona equipo:"),
            dcc.Dropdown(
                id="equipo-selector",
                options=[{"label": e, "value": e} for e in equipos],
                value=equipos[0] if equipos else None,
                clearable=False,
                style={"width": "300px"}
            ),
            html.H2("📈 Estadísticas de mercado"),
            html.Div(id="kpi-container-mercado", style={
                "display": "flex", "flex-wrap": "wrap", "margin-top": "10px"
            }),
            html.H2("🎯 Estadísticas de bonificación"),
            html.Div(id="kpi-container-bonos", style={
                "display": "flex", "flex-wrap": "wrap", "margin-top": "10px"
            }),
            html.H2("💰 Balance total + Bonos"),
            html.Div(id="kpi-container-total", style={
                "display": "flex", "flex-wrap": "wrap", "margin-top": "10px"
            }),
            html.Hr(),
            html.H2("📉 Evolución del balance acumulado"),
            dcc.Graph(id="grafico-balance"),
            html.Hr(),
            html.H2("Desglose por tipo de operación"),
            html.Div(id="tabla-desglose")
        ]
    )

    # --- Callbacks ---
    @app.callback(
        [Output("kpi-container-mercado", "children"),
         Output("kpi-container-bonos", "children"),
         Output("kpi-container-total", "children"),
         Output("grafico-balance", "figure"),
         Output("tabla-desglose", "children")],
        Input("equipo-selector", "value")
    )
    def update_dashboard(equipo):
        if not equipo:
            return [], [], [], go.Figure(), html.Div("No hay datos disponibles.")

        d_equipo = df[df["equipo"] == equipo]
        d_mercado = d_equipo[d_equipo["type"] == "transfer"]
        d_bonos = d_equipo[d_equipo["type"] == "bonificacion"]

        # === 📈 ESTADÍSTICAS DE MERCADO ===
        total_compras = d_mercado.loc[d_mercado["compra-venta"] == "compra", "ganancias"].sum()
        total_ventas = d_mercado.loc[d_mercado["compra-venta"] == "venta", "ganancias"].sum()
        balance_total = total_ventas + total_compras
        n_operaciones = len(d_mercado)

        kpis_mercado = [
            crear_kpi("Total compras", f"{total_compras:,.0f} €", "#f44336"),
            crear_kpi("Total ventas", f"{total_ventas:,.0f} €", "#4caf50"),
            crear_kpi("Balance total", f"{balance_total:,.0f} €", "#2196f3"),
            crear_kpi("Nº operaciones", f"{n_operaciones}", "#9c27b0"),
        ]

        # === 🎯 ESTADÍSTICAS DE BONIFICACIÓN ===
        total_bono_clasificacion = d_bonos.loc[d_bonos["subtype"] == "clasificacion", "ganancias"].sum()
        media_bono_clasificacion = d_bonos.loc[d_bonos["subtype"] == "clasificacion", "ganancias"].mean()
        total_bono_quiniela = d_bonos.loc[d_bonos["subtype"] == "quiniela", "ganancias"].sum()
        media_bono_quiniela = d_bonos.loc[d_bonos["subtype"] == "quiniela", "ganancias"].mean()

        kpis_bonos = [
            crear_kpi("Total bono clasificación", f"{total_bono_clasificacion:,.0f} €", "#00897b"),
            crear_kpi("Media bono clasificación", f"{media_bono_clasificacion:,.0f} €", "#26a69a"),
            crear_kpi("Total bono quiniela", f"{total_bono_quiniela:,.0f} €", "#00796b"),
            crear_kpi("Media bono quiniela", f"{media_bono_quiniela:,.0f} €", "#004d40"),
        ]

        # === 💰 KPI FINAL COMBINADO ===
        balance_global = balance_total + total_bono_clasificacion + total_bono_quiniela
        kpis_totales = [crear_kpi("Balance total + Bonos", f"{balance_global:,.0f} €", "#ff9800")]

       # === 📉 GRÁFICO DE BALANCE ACUMULADO ===
        # Ordenar cronológicamente por ID (mayor → más antiguo)
        d_sorted = d_equipo.sort_values(by="id", ascending=False)
        d_sorted["balance_acumulado"] = d_sorted["ganancias"].cumsum()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=d_sorted["id"],
            y=d_sorted["balance_acumulado"],
            mode="lines+markers",
            line=dict(color="#2196f3"),
            name="Balance acumulado"
        ))

        # Líneas verticales: inicio jornada / mercado
        marks_jornada = df[(df["type"] == "marks") & (df["subtype"] == "start_jornada")]["id"].unique()
        marks_mercado = df[(df["type"] == "marks") & (df["subtype"] == "start_mercado")]["id"].unique()

        for mark in marks_jornada:
            fig.add_vline(x=mark, line=dict(color="red", dash="dash", width=1), opacity=0.4)
        for mark in marks_mercado:
            fig.add_vline(x=mark, line=dict(color="gray", dash="dot", width=1), opacity=0.3)

        # Invertir eje X para que termine en ID 0
        fig.update_layout(
            title=f"Evolución del balance acumulado - {equipo}",
            xaxis_title="ID (tiempo)",
            yaxis_title="Balance (€)",
            template="plotly_white",
            height=400,
            xaxis=dict(autorange="reversed")  # 👈 ESTA LÍNEA INVIERTE EL EJE
        )

        # === 📊 DESGLOSE TABULAR ===
        if not d_mercado.empty:
            resumen = (
                d_mercado.groupby(["subtype", "compra-venta"], as_index=False)
                .agg(n_op=("id", "count"), total_ganancias=("ganancias", "sum"))
            )
        else:
            resumen = pd.DataFrame(columns=["subtype", "compra-venta", "n_op", "total_ganancias"])

        tabla = go.Figure(data=[
            go.Table(
                header=dict(
                    values=["Tipo", "Compra/Venta", "Nº Operaciones", "Total (€)"],
                    fill_color="#1976d2",
                    font=dict(color="white", size=14),
                    align="center"
                ),
                cells=dict(
                    values=[
                        resumen["subtype"],
                        resumen["compra-venta"],
                        resumen["n_op"],
                        resumen["total_ganancias"].round(0)
                    ],
                    fill_color=[["#f5f5f5", "white"] * (len(resumen)//2 + 1)],
                    align="center"
                )
            )
        ])
        tabla.update_layout(margin=dict(t=10, b=10))

        return kpis_mercado, kpis_bonos, kpis_totales, fig, dcc.Graph(figure=tabla)

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

