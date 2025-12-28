import pandas as pd
import re
import numpy as np

def abreviar_nombre(nombre):
    partes = nombre.split()
    if len(partes) <= 1:
        return nombre  # Nombre simple, no se toca
    # Primera letra del primer nombre + "." + resto del nombre
    return partes[0][0] + ". " + " ".join(partes[1:])

def transformar_detalles(valor):
    if isinstance(valor, str):
        # Buscar "Empieza en X día(s)"
        match = re.search(r'Empieza en (\d+) día', valor)
        if match:
            return int(match.group(1))
    # Para todo lo demás
    return 0.5    

def procesar_model_data(csv_mercado, csv_subidasBajadas, csv_jornada, csv_notificaciones_clean):
    # --- Normalizar fechas ---
    csv_mercado["date"] = pd.to_datetime(csv_mercado["date"], errors="coerce")
    csv_subidasBajadas["date"] = pd.to_datetime(csv_subidasBajadas["date"], errors="coerce")
    csv_jornada["date"] = pd.to_datetime(csv_jornada["date"], errors="coerce")
    csv_notificaciones_clean["fecha"] = pd.to_datetime(csv_notificaciones_clean["fecha"], errors="coerce")
    
    # --- Normalizar nombres de jugadores ---
    csv_mercado["jugador"] = csv_mercado["jugador"].astype(str).str.strip().str.upper()
    csv_subidasBajadas["nombre"] = csv_subidasBajadas["nombre"].astype(str).str.strip().str.upper()
    csv_subidasBajadas["nombre"] = csv_subidasBajadas["nombre"].apply(abreviar_nombre)
    csv_notificaciones_clean["jugador"] = csv_notificaciones_clean["jugador"].astype(str).str.strip().str.upper()
    csv_notificaciones_clean["jugador"] = csv_notificaciones_clean["jugador"].apply(abreviar_nombre)


    columnas_mercado = [
        "date",
        "jugador",
        "precio",
        "posicionJugador",
        "puntosJugador",
        "equipoLiga",
        "avgPoints",
        "estado"
    ]
    mapeo_estado = {
    np.nan: 0,       # NaN → 0
    'injury': 1,
    'red': 2,
    'doubt': 3,
    'other': 4,
    'five': 5
}
    csv_mercado["estado"] = csv_mercado["estado"].map(mapeo_estado)

    mercado_libre = csv_mercado[
        csv_mercado["manager"] == "Libre"
    ][columnas_mercado]

    mercado_subida = mercado_libre.merge(
        csv_subidasBajadas,
        left_on=["date", "jugador"],
        right_on=["date", "nombre"],
        how="left"
    )
    mercado_subida = mercado_subida.drop(columns=["nombre"], errors="ignore")

    csv_jornada = csv_jornada[(csv_jornada["detalles"] != "En juego") & (csv_jornada["detalles"] != "Finalizada")].copy()
    csv_jornada["detalles"] = csv_jornada["detalles"].apply(transformar_detalles)
    mercado_subida_jornada = mercado_subida.merge(
        csv_jornada,
        on="date",
        how="left"
    )

    columnas_notificaciones = ["fecha", "equipo", "jugador", "ganancias"]
    csv_notificaciones_clean = csv_notificaciones_clean.copy()
    csv_notificaciones_clean["fecha"] -= pd.Timedelta(days=1)


    notificaciones_ventas = csv_notificaciones_clean[
        (csv_notificaciones_clean["compra-venta"] == "compra") &
        (csv_notificaciones_clean["subtype"] == "mercado")
    ][columnas_notificaciones]

    notificaciones_pujas = csv_notificaciones_clean[
        (csv_notificaciones_clean["compra-venta"] == "compra") &
        (csv_notificaciones_clean["subtype"] == "Puja")
    ][columnas_notificaciones]

    mercado_subida_jornada_compras = mercado_subida_jornada.merge(
        notificaciones_ventas,
        left_on=["date", "jugador"],
        right_on=["fecha", "jugador"],
        how="left"
    )
    mercado_subida_jornada_compras = mercado_subida_jornada_compras.drop(columns=["fecha"], errors="ignore")

    pujas_agrupadas = (
    notificaciones_pujas
    .groupby(["fecha", "jugador"])
    .size()
    .reset_index(name="num_pujas")
    )
    mercado_final = mercado_subida_jornada_compras.merge(
    pujas_agrupadas,
    left_on=["date", "jugador"],
    right_on=["fecha", "jugador"],
    how="left"
    )
    mercado_final["num_pujas"] = mercado_final["num_pujas"].fillna(0).astype(int)
    mercado_final = mercado_final.drop(columns=["fecha"], errors="ignore")


    return mercado_final
