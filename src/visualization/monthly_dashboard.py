import pandas as pd

def monthly_dashboard(df_jornadas: pd.DataFrame,
                      df_clas: pd.DataFrame,
                      df_clean: pd.DataFrame,
                      df_diff: pd.DataFrame,
                      df_clausulas: pd.DataFrame):
    # ========================
    # 1️⃣ Clasificación mensual
    # ========================
    def clasificacion_mensual(df_jornadas, df_clas):
        df_jornadas = df_jornadas.copy()
        df_jornadas["date"] = pd.to_datetime(df_jornadas["date"])
        ultimo_mes = df_jornadas["date"].max().to_period("M")
        jornadas_mes = df_jornadas[
            (df_jornadas["date"].dt.to_period("M") == ultimo_mes) &
            (df_jornadas["detalles"] == "En juego")
        ]
        jornadas_validas = jornadas_mes["jornada"].unique()

        clas_mes = df_clas[df_clas["jornada"].isin(jornadas_validas)]

        clas_mensual = (
            clas_mes
            .groupby("nombre", as_index=False)
            .agg({"puntos": "sum", "valor_equipo": "sum"})
            .sort_values("puntos", ascending=False)
            .reset_index(drop=True)
        )
        clas_mensual["posicion"] = clas_mensual.index + 1
        clas_mensual = clas_mensual[["posicion", "nombre", "puntos"]]
        clas_mensual = (
        clas_mensual[["posicion", "nombre", "puntos"]]
        .rename(columns={
            "posicion": "-",
            "nombre": "Equipo",
            "puntos": "Pts"
        })
    )
        return clas_mensual, clas_mes

    # ========================
    # 2️⃣ Mejor y peor jornada
    # ========================
    def mejores_peores_jornadas(clas_mes):
        mejor = clas_mes.sort_values("puntos", ascending=False).iloc[0]
        peor = clas_mes.sort_values("puntos", ascending=True).iloc[0]

        mejor_jornada = {
            "jornada": int(mejor["jornada"]),
            "equipo": mejor["nombre"],
            "puntos": int(mejor["puntos"])
        }

        peor_jornada = {
            "jornada": int(peor["jornada"]),
            "equipo": peor["nombre"],
            "puntos": int(peor["puntos"])
        }

        return mejor_jornada, peor_jornada

    # ========================
    # 3️⃣ Cláusulas por equipo
    # ========================
    def clausulas_por_equipo(df_clausulas, equipos):
        df = df_clausulas.copy()
        df["date"] = pd.to_datetime(df["date"])
        ultimo_mes = df["date"].max().to_period("M")
        df_mes = df[
            (df["date"].dt.to_period("M") == ultimo_mes) &
            (df["subtype"] == "clausula")
        ]

        realizadas = df_mes.groupby("a_equipo").agg(
            Clausulas_Realizadas=("precio", "count"),
            Dinero_Gastado=("precio", "sum")
        ).reset_index().rename(columns={"a_equipo": "Equipo"})

        recibidas = df_mes.groupby("de_equipo").agg(
            Clausulas_Recibidas=("precio", "count"),
            Dinero_Recibido=("precio", "sum")
        ).reset_index().rename(columns={"de_equipo": "Equipo"})

        base = pd.DataFrame({"Equipo": equipos})
        tabla_final = base.merge(realizadas, on="Equipo", how="left") \
                          .merge(recibidas, on="Equipo", how="left")

        tabla_final[["Clausulas_Realizadas","Dinero_Gastado",
                     "Clausulas_Recibidas","Dinero_Recibido"]] = \
            tabla_final[["Clausulas_Realizadas","Dinero_Gastado",
                         "Clausulas_Recibidas","Dinero_Recibido"]].fillna(0)

        tabla_final["Clausulas_Realizadas"] = tabla_final["Clausulas_Realizadas"].astype(int)
        tabla_final["Clausulas_Recibidas"] = tabla_final["Clausulas_Recibidas"].astype(int)
        tabla_final["Dinero_Gastado"] = tabla_final["Dinero_Gastado"].astype(float).round(2)
        tabla_final["Dinero_Recibido"] = tabla_final["Dinero_Recibido"].astype(float).round(2)

        tabla_final = tabla_final.sort_values("Equipo").reset_index(drop=True)
        # Crear nuevas columnas combinadas
        tabla_final["Realizadas (€)"] = tabla_final.apply(
            lambda row: f"{int(row['Clausulas_Realizadas'])} ({row['Dinero_Gastado']:.2f}M€)", axis=1
        )

        tabla_final["Recibidas (€)"] = tabla_final.apply(
            lambda row: f"{int(row['Clausulas_Recibidas'])} ({row['Dinero_Recibido']:.2f}M€)", axis=1
        )

        # Seleccionar solo las columnas finales para mostrar
        tabla_final_display = tabla_final[["Equipo", "Realizadas (€)", "Recibidas (€)"]].copy()
        return tabla_final_display, df_mes

    # ========================
    # 4️⃣ Top 3 cláusulas más caras
    # ========================
    def top3_clausulas(df_mes):
        top3 = df_mes.sort_values("precio", ascending=False).head(3)
        top3 = top3[["jugador", "de_equipo", "a_equipo", "precio"]].copy()
        top3["precio"] = top3["precio"].astype(float).round(2)
        top3["precio"] = top3.apply(
            lambda row: f"{row['precio']:.2f}M€", axis=1
        )
        top3 = top3[["jugador", "de_equipo", "a_equipo", "precio"]].rename(columns={
            "jugador": "Jugador",
            "de_equipo": "De",
            "a_equipo": "A",
            "precio": "€"
        })
            
        top3 = top3.reset_index(drop=True)
        return top3
    # ========================
    # 4  Fichajes top
    # ========================
    def top3_fichajes(df_clean):
        df = df_clean.copy()
        df["fecha"] = pd.to_datetime(df["fecha"])
        ultimo_mes = df["fecha"].max().to_period("M")
        df_mes = df[
            (df["fecha"].dt.to_period("M") == ultimo_mes) &
            (df["subtype"] == "mercado")&
            (df["compra-venta"] == "compra")
            
        ]
        top3 = df_mes.sort_values("ganancias", ascending=True).head(3)
        top3 = top3[["jugador", "equipo", "ganancias"]].copy()
        top3["ganancias"] = top3["ganancias"].astype(float).round(2)
        top3["ganancias"] = top3.apply(
            lambda row: f"{row['ganancias']:.2f}M€", axis=1
        )
        
        top3 = top3[["jugador", "equipo", "ganancias"]].rename(columns={
            "jugador": "Jugador",
            "equipo": "Equipo",
            "ganancias": "€"
        })
        top3 = top3.reset_index(drop=True)
        return top3
    # ========================
    # 4  Fichajes top
    # ========================
    def top3_ganancias(df_diff):
        df = df_diff.copy()
        df["fecha"] = pd.to_datetime(df["fecha"])
        ultimo_mes = df["fecha"].max().to_period("M")
        df_mes = df[
            (df["fecha"].dt.to_period("M") == ultimo_mes)&
            (df["subtype"] == "mercado")
        ]
        top3 = df_mes.sort_values("Diff", ascending=False).head(3)
        top3 = top3[["jugador", "equipo", "Diff"]].copy()
        top3["Diff"] = top3["Diff"].astype(float).round(2)
        top3["Diff"] = top3.apply(
            lambda row: f"{row['Diff']:.2f}M€", axis=1
        )
        top3 = top3[["jugador", "equipo", "Diff"]].rename(columns={
            "jugador": "Jugador",
            "equipo": "Equipo",
            "ganaDiffncias": "€"
        })
        top3 = top3.reset_index(drop=True)
        return top3
    # ========================
    # Ejecutar submétodos
    # ========================
    clas_mensual, clas_mes = clasificacion_mensual(df_jornadas, df_clas)
    mejor_jornada, peor_jornada = mejores_peores_jornadas(clas_mes)
    tabla_clausulas, df_claus_mes = clausulas_por_equipo(df_clausulas, clas_mensual["Equipo"])
    top3 = top3_clausulas(df_claus_mes)
    top3_fich = top3_fichajes(df_clean)
    top3_gan = top3_ganancias(df_diff)


    
    return clas_mensual,mejor_jornada,peor_jornada,tabla_clausulas,top3,top3_fich,top3_gan
