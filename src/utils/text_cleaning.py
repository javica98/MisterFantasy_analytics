import re
import unicodedata

def limpiar_nombre(nombre: str) -> str:
    """
    Limpia y normaliza un nombre, eliminando símbolos y espacios innecesarios.
    """
    if not nombre:
        return ""

    nombre = nombre.strip()
    nombre = unicodedata.normalize('NFKD', nombre)
    nombre = re.sub(r'[^\w\s]', '', nombre, flags=re.UNICODE)
    return nombre

def limpiar_entero(texto: str) -> int | None:
    """
    Extrae y convierte una cadena con dígitos a entero.
    Devuelve None si no hay dígitos.
    """
    if not texto:
        return None

    texto = ''.join(filter(str.isdigit, texto))
    return int(texto) if texto else None

def limpiar_dinero(texto: str) -> int:
    """
    Extrae y convierte valores monetarios del tipo '€ 1.234.567' a enteros.
    """
    if not texto:
        return 0

    match = re.search(r'€\s*([\d\.\,]+)', texto)
    if match:
        valor = match.group(1)
        valor = valor.replace('.', '').replace(',', '').replace('+', '')
        return int(valor)

    return 0
