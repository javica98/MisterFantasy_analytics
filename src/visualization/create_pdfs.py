from datetime import datetime
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
from pypdf import PdfReader, PdfWriter
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from src.utils.photo_utils import manager_photo

def draw_kpi_centered(c, label, value, x, y,
                      label_size=9, value_size=13):

    c.setFont("Helvetica-Bold", value_size)
    c.drawCentredString(x, y - value_size - 4, str(value))


def df_to_wrapped_table_data(df, align="CENTER"):
    """
    Convierte un DataFrame en datos para Table usando Paragraph
    para que el texto haga salto de línea automático.
    """
    styles = getSampleStyleSheet()
    style = styles["Normal"]

    if align == "CENTER":
        style.alignment = 1
    elif align == "LEFT":
        style.alignment = 0
    elif align == "RIGHT":
        style.alignment = 2

    style.leading = 9  # altura de línea (ajustable)

    data = []
    # Header
    data.append([Paragraph(str(col), style) for col in df.columns])

    # Filas
    for row in df.values.tolist():
        data.append([Paragraph(str(cell), style) for cell in row])

    return data


# Estilo compartido por las 5 tablas del informe mensual — antes se repetía
# literal 5 veces (una por tabla), con riesgo de dejar alguna desincronizada
# si se cambiaba el color/fuente en las demás (hallazgo WEB-06).
_TABLE_STYLE = TableStyle([
    ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
])


def crear_tabla_pdf(c, df, col_widths, position, align="CENTER"):
    """Construye una Table de reportlab a partir de un DataFrame y la dibuja
    en `position` (x, y) sobre el canvas `c`, con el estilo compartido."""
    data = df_to_wrapped_table_data(df, align=align)
    table = Table(data, colWidths=col_widths)
    table.setStyle(_TABLE_STYLE)
    x, y = position
    table.wrapOn(c, 700, 200)
    table.drawOn(c, x, y)
    return table


def create_report(dir_template,
                  dir_reports,
                  clas_mensual,
                  mejor_jornada,
                  peor_jornada,
                  tabla_clausulas,
                  top3,
                  top3_fich,
                  top3_gan,
                  IMAGES_TEAMS_DIR,
                  DEFAULT_TEAM_IMAGE,
                  table_clas=(43, 485),
                  table_claus=(325, 485),
                  table_top3=(300, 275),
                  table_top3_fich=(43, 100),
                  table_top3_gan=(325, 100)):  # x, y de la tabla
    """
    Crea un PDF final fusionando una tabla sobre un template existente.

    table_clas: tupla (x, y) indicando la posición exacta de la tabla
                  desde la esquina inferior izquierda
    """
    # --------------------
    # Crear rutas dinámicas
    # --------------------
    os.makedirs(dir_reports, exist_ok=True)
    fecha_hoy = datetime.today().strftime("%Y-%m-%d")
    pdf_final_path = os.path.join(dir_reports, f"report_{fecha_hoy}.pdf")
    pdf_temp_path = os.path.join(dir_reports, f"temp_{fecha_hoy}.pdf")

    # --------------------
    # 1️⃣ Crear PDF temporal con canvas y tabla en coordenadas exactas
    # --------------------
    c = canvas.Canvas(pdf_temp_path, pagesize=A4)

    #CLASIFICACION MENSUAL
    crear_tabla_pdf(c, clas_mensual, [25, 150, 50], table_clas)

    #TABLA CLAUSULAS
    crear_tabla_pdf(c, tabla_clausulas, [75, 75, 75], table_claus)

    #MEJOR/PEOR
    escudo_path_mejor = manager_photo(mejor_jornada["equipo"],IMAGES_TEAMS_DIR,DEFAULT_TEAM_IMAGE)
    c.drawImage(
    escudo_path_mejor,
    x=49,
    y=278,
    width=100,
    height=100,
    preserveAspectRatio=True,
    mask='auto'
    )
    draw_kpi_centered(c, "Equipo", mejor_jornada["equipo"], 100, 300)
    draw_kpi_centered(c, "Puntos", mejor_jornada["puntos"], 100, 285)
    escudo_path_peor = manager_photo(peor_jornada["equipo"],IMAGES_TEAMS_DIR,DEFAULT_TEAM_IMAGE)
    c.drawImage(
    escudo_path_peor,
    x=159,
    y=278,
    width=100,
    height=100,
    preserveAspectRatio=True,
    mask='auto'
    )
    draw_kpi_centered(c, "Equipo", peor_jornada["equipo"], 208, 300)
    draw_kpi_centered(c, "Puntos", peor_jornada["puntos"], 208, 285)


    #TOP CLAUSULAS
    crear_tabla_pdf(c, top3, [70, 80, 80, 40], table_top3)

    #TOP FICHAJES
    crear_tabla_pdf(c, top3_fich, [100, 80, 45], table_top3_fich)

    #TOP GANANCIAS
    crear_tabla_pdf(c, top3_gan, [100, 80, 45], table_top3_gan)


    mes_actual = datetime.today().strftime("%B %Y")  # Ej: "December 2025"
    x=299
    y=823
    font_size=14
    c.setFont("Helvetica-Bold", font_size)
    c.setFillColor(colors.white)
    c.drawCentredString(x, y, mes_actual)

    c.save()
    # --------------------
    # 2️⃣ Fusionar PDF temporal sobre template existente
    # --------------------
    template_pdf = PdfReader(dir_template)
    temp_pdf = PdfReader(pdf_temp_path)
    writer = PdfWriter()

    # Fusionar página por página (solo primera página si template tiene una)
    for page_template, page_temp in zip(template_pdf.pages, temp_pdf.pages):
        page_template.merge_page(page_temp)
        writer.add_page(page_template)

    # Guardar PDF final
    with open(pdf_final_path, "wb") as f_out:
        writer.write(f_out)

    # Borrar PDF temporal
    os.remove(pdf_temp_path)

    print(f"PDF final guardado en {pdf_final_path}")
