import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

def plot_balances_por_equipo(df_ganancias: pd.DataFrame, output_folder: str = "graficas_jugadores") -> None:
    """
    Genera gráficas de balance acumulado por equipo y las guarda en archivos PNG.

    Args:
        df_ganancias (pd.DataFrame): DataFrame con las columnas ['id', 'equipo', 'ganancias', 'type'].
        output_folder (str): Carpeta donde se guardarán las imágenes. Por defecto "graficas_jugadores".

    """
    os.makedirs(output_folder, exist_ok=True)

    # Orden cronológico (ID más alto = más antiguo)
    ids_ordenados = sorted(df_ganancias["id"].unique(), reverse=True)

    # Lista de equipos tipo "gameweek"
    equipos = df_ganancias[df_ganancias["subtype"] == "clasificacion"]["equipo"].unique()
    # Ids inicio jornada
    inicio_jornada = df_ganancias[(df_ganancias["subtype"] == "start_jornada")]["id"].values
    for equipo in equipos:
        acumulado = []
        total = 0
        error = 0
        for idx in ids_ordenados:
            ganancias = df_ganancias[(df_ganancias["equipo"] == equipo) & (df_ganancias["id"] == idx)]["ganancias"].sum()
            total += ganancias
            acumulado.append((idx, total))
            if (idx in inicio_jornada) and (total < 0) and (total < error):    
                error = total
        ids = [x[0] for x in acumulado]
        balances = [x[1] for x in acumulado]

        plt.figure(figsize=(10, 6))
        plt.plot(ids, balances, marker='o', label=equipo)

        # Líneas verticales para "start_jornada"
        ids_gameweek = df_ganancias[(df_ganancias["type"] == "marks") & (df_ganancias["subtype"] == "start_jornada")]["id"].unique()
        for gid in ids_gameweek:
            plt.axvline(x=gid, color="red", linestyle="--", alpha=0.3)

        # Líneas verticales para "start_mercado"
        ids_market = df_ganancias[(df_ganancias["type"] == "marks") & (df_ganancias["subtype"] == "start_mercado")]["id"].unique()
        for gid in ids_market:
            plt.axvline(x=gid, color="grey", linestyle="--", alpha=0.3)

        plt.title(f"Balance acumulado - {equipo}")
        plt.xlabel("ID de evento (tiempo)")
        plt.ylabel("Balance (€)")
        plt.gca().invert_xaxis()  # Más reciente a la derecha
        plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
        plt.grid(True)
        plt.tight_layout()
        plt.legend()

        # Guardar archivo
        filename = os.path.join(output_folder, f"{equipo}.png")
        plt.savefig(filename)
        plt.close()

    print(f"✅ Gráficas individuales generadas en la carpeta '{output_folder}'")
