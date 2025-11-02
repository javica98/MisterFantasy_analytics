import pandas as pd
import logging

logger = logging.getLogger(__name__)

def find_last_position(new_notificaciones: pd.DataFrame, csv_notificaciones: pd.DataFrame):
    """
    Busca la posición de la última notificación del CSV que ya existe en las nuevas,
    usando el identificador único 'idTransfer'.

    Retorna:
        (idx_csv, idx_new): tupla con los índices en cada DataFrame,
                            o (None, None) si no hay coincidencia.
    """
    try:
        if "idTransfer" not in new_notificaciones.columns or "idTransfer" not in csv_notificaciones.columns:
            raise ValueError("Ambos DataFrames deben tener la columna 'idTransfer'.")

        first_transfer_csv = csv_notificaciones.loc[
            csv_notificaciones["type"] == "transfer", "idTransfer"
        ]
        if first_transfer_csv.empty:
            logger.warning("No hay transferencias en el CSV anterior.")
            return None, None

        first_id = first_transfer_csv.iloc[0]

        match_new = new_notificaciones.index[new_notificaciones["idTransfer"] == first_id]
        match_csv = csv_notificaciones.index[csv_notificaciones["idTransfer"] == first_id]

        if not match_new.empty and not match_csv.empty:
            idx_new = match_new[0]
            idx_csv = match_csv[0]
            logger.info(f"Coincidencia encontrada (id={first_id}) → new_index={idx_new}, csv_index={idx_csv}")
            return idx_csv, idx_new
        else:
            logger.warning("No se encontró coincidencia de ID entre CSV y nuevas notificaciones.")
            return None, None

    except Exception as e:
        logger.exception(f"Error en find_last_position: {e}")
        return None, None


def merge_feed_cards_until_match(csv_notificaciones: pd.DataFrame, new_notificaciones: pd.DataFrame) -> pd.DataFrame:
    """
    Fusiona las notificaciones nuevas con las antiguas sin duplicar, usando 'idTransfer'.
    Mantiene las filas nuevas (por encima de la coincidencia) y las antiguas (por debajo).
    """
    try:
        all_columns = [
            "type","subtype","mensaje","jugador","de_equipo","a_equipo","precio",
            "posicionJugador","puntosJugador","equipoLiga","name","money","position",
            "aciertos","points","jornada","date","idTransfer"
        ]

        # Asegurar columnas
        for col in all_columns:
            if col not in new_notificaciones.columns:
                new_notificaciones[col] = None
            if col not in csv_notificaciones.columns:
                csv_notificaciones[col] = None

        new_notificaciones = new_notificaciones[all_columns]
        csv_notificaciones = csv_notificaciones[all_columns]

        # Buscar coincidencia
        idx_csv, idx_new = find_last_position(new_notificaciones, csv_notificaciones)
        today = pd.Timestamp.today().date()

        if idx_csv is not None and idx_new is not None:
            # Filtrar por rangos definidos
            new_part = new_notificaciones.iloc[:idx_new].copy()
            old_part = csv_notificaciones.iloc[idx_csv:].copy()

            new_part["date"] = today
            merged = pd.concat([new_part, old_part], ignore_index=True)
            logger.info(f"Merge realizado con corte en new_index={idx_new}, csv_index={idx_csv}")
        else:
            # No hay coincidencia → concatenar todo
            new_notificaciones["date"] = today
            merged = pd.concat([new_notificaciones, csv_notificaciones], ignore_index=True)
            logger.warning("No hubo coincidencia, se añadieron todas las filas nuevas.")

        return merged

    except Exception as e:
        logger.exception(f"Error al fusionar notificaciones: {e}")
        # Devolver lo más seguro posible
        try:
            new_notificaciones["date"] = pd.Timestamp.today().date()
            return pd.concat([new_notificaciones, csv_notificaciones], ignore_index=True)
        except Exception as inner_e:
            logger.error(f"Error fatal en merge_feed_cards_until_match: {inner_e}")
            return csv_notificaciones.copy()
