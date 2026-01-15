# src/scraper/login.py
import time
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from src.utils.config_loader import load_config

logger = logging.getLogger(__name__)

def scroll_infinite(page, scroll_pause=1.5, max_scrolls=50):
    """Hace scroll infinito en la página para cargar todo el contenido."""
    try:
        last_height = page.evaluate("() => document.body.scrollHeight")
    except Exception as e:
        logger.warning("No se pudo obtener altura inicial del documento: %s", e)
        return

    for i in range(max_scrolls):
        try:
            page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(scroll_pause)
            new_height = page.evaluate("() => document.body.scrollHeight")
            if new_height == last_height:
                logger.info("Scroll finalizado tras %d iteraciones ✅", i + 1)
                break
            last_height = new_height
        except Exception as e:
            logger.warning("Error durante scroll en iteración %d: %s", i + 1, e)
            break
    else:
        logger.warning("⚠️ Límite de scroll alcanzado, puede que haya más contenido.")

def guardar_html(content, nombre_archivo, project_root=None):
    """Guarda HTML en data/raw/ y devuelve la ruta guardada."""
    if project_root is None:
        project_root = Path(__file__).resolve().parents[2]
    carpeta = Path(project_root) / "data" / "raw"
    carpeta.mkdir(parents=True, exist_ok=True)

    ruta_completa = carpeta / nombre_archivo
    with open(ruta_completa, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("💾 Guardado en: %s", ruta_completa)
    return ruta_completa

def safe_click(locator, description="", timeout=5000):
    """Intenta esperar y clickar un locator, devolviendo True/False."""
    try:
        locator.wait_for(state="visible", timeout=timeout)
        locator.scroll_into_view_if_needed()
        locator.click()
        logger.debug("Clicked: %s", description or locator)
        return True
    except PlaywrightTimeoutError:
        logger.debug("Timeout al buscar: %s", description)
        return False
    except Exception as e:
        logger.warning("Error al clickar %s: %s", description, e)
        return False

def login():
    """
    Realiza login y guarda los HTMLs necesarios en data/raw.
    Devuelve un dict con las rutas guardadas.
    Lanza excepción si el login falla críticamente.
    """
    cfg = load_config()
    base_url = cfg["env"].get("MISTER_BASE_URL", "https://mister.mundodeportivo.com")
    email = cfg["env"].get("MISTER_USERNAME")
    password = cfg["env"].get("MISTER_PASSWORD")

    # Parámetros configurables (opcional en config.yaml bajo 'scraper')
    scraper_cfg = cfg.get("scraper", {})
    scroll_pause = scraper_cfg.get("scroll_pause", 2)
    max_scrolls = scraper_cfg.get("max_scrolls", 60)
    headless = scraper_cfg.get("headless", True)  # recomendable True en Actions

    if not (email and password):
        raise RuntimeError("MISTER_USERNAME o MISTER_PASSWORD no definidos en .env / secrets")

    saved_paths = {}

    # Ejecutar Playwright
    with sync_playwright() as p:
        browser = None
        try:
            # En entornos como Actions es necesario deshabilitar sandbox
            launch_args = {"headless": headless, "args": ["--no-sandbox", "--disable-setuid-sandbox"]}
            browser = p.chromium.launch(**launch_args)
            context = browser.new_context()
            page = context.new_page()

            # Construir URL de login (usando el patrón que ya usabas)
            login_url = f"{base_url}/new-onboarding/auth/email/check?email={email}"
            logger.info("🌍 Navegando a: %s", login_url)
            page.goto(login_url, wait_until="domcontentloaded", timeout=60000)

            # Intentar aceptar cookies (español/inglés variantes)
            try:
                accepted = False
                for text in ("Aceptar", "Accept", "Got it"):
                    if safe_click(page.locator(f"button:has-text('{text}')"), description=f"cookie-{text}", timeout=5000):
                        logger.info("🍪 Cookies aceptadas (%s) ✅", text)
                        accepted = True
                        break
                if not accepted:
                    logger.debug("No había banner de cookies detectable.")
            except Exception:
                logger.debug("No se pudo manejar banner de cookies (no crítico).")

            # Pulsar 'Continue with password' o su alternativa
            if not safe_click(page.locator("button:has-text('Continue with password')"), "Continue with password", timeout=30000):
                # intentar alternativa en español
                safe_click(page.locator("button:has-text('Continuar con contraseña')"), "Continuar con contraseña", timeout=10000)

            # Rellenar contraseña
            try:
                password_input = page.locator("input[type='password']")
                password_input.wait_for(state="visible", timeout=30000)
                password_input.fill(password)
                logger.info("🔑 Contraseña introducida")
            except PlaywrightTimeoutError:
                raise RuntimeError("El campo de contraseña no apareció tras el intento de login.")

            # Submit
            if not safe_click(page.locator("button[type='submit']"), "submit", timeout=30000):
                logger.warning("No se pudo pulsar el botón submit de forma normal; intentando presionar Enter.")
                try:
                    password_input.press("Enter")
                except Exception:
                    raise RuntimeError("No se pudo enviar el formulario de login.")

            logger.info("⏳ Esperando posible publicidad (hasta 60s)...")
            # Intentar cerrar pop-ups si aparecen
            try:
                page.wait_for_timeout(2000)
                for _ in range(6):  # pequeños intentos para cerrar popups
                    try:
                        ad_close = page.locator("#ssmInterClose21614")
                        if ad_close.is_visible():
                            ad_close.click()
                            logger.info("🧹 Pop-up publicitario cerrado ✅")
                            break
                    except Exception:
                        pass
                    page.wait_for_timeout(1000)
            except Exception:
                logger.debug("No apareció publicidad o no pudo cerrarse (no crítico).")

            # Esperar contenido principal
            try:
                page.wait_for_selector("#fg-content", timeout=60000)
                logger.info("✅ Login exitoso y contenido principal cargado.")
            except PlaywrightTimeoutError:
                logger.warning("⚠️ No se detectó el contenido principal tras login. Continuando, puede que la página tenga estructura distinta.")

            # Scrollear y guardar dashboard
            scroll_infinite(page, scroll_pause=scroll_pause, max_scrolls=max_scrolls)
            saved_paths["dashboard"] = guardar_html(page.content(), "dashboard.html")

            # Otras secciones
            rutas = {
                "market": "mercado.html",
                "team": "mi_equipo.html",
                "standings": "clasificacion.html",
                "feed#gameweek":"gameweek.html",
                "feed#pool-private":"quiniela.html"
            }

            for ruta_name, archivo in rutas.items():
                url = f"{base_url}/{ruta_name}"
                logger.info("➡️ Navegando a: %s", url)
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                except PlaywrightTimeoutError:
                    logger.warning("Timeout al cargar %s, intentando continuar.", url)

                # intentar cerrar pop-up local
                try:
                    ad_close = page.locator("#ssmInterClose21614")
                    if ad_close.is_visible():
                        ad_close.click()
                        logger.info("🧹 Pop-up publicitario cerrado ✅")
                except Exception:
                    pass

                scroll_infinite(page, scroll_pause=scroll_pause, max_scrolls=max_scrolls)
                saved_paths[ruta_name] = guardar_html(page.content(), archivo)

            # Subidas/Bajadas
            ruta = "market#market"
            archivoSB = "MarketSubidasBajadas.html"
            url_sb = f"{base_url}/{ruta}"
            logger.info("➡️ Navegando a: %s", url_sb)
            try:
                page.goto(url_sb, wait_until="domcontentloaded", timeout=60000)
            except PlaywrightTimeoutError:
                logger.warning("Timeout al cargar %s, intentando continuar.", url_sb)

            # Intentar cerrar pop-ups
            try:
                ad_close = page.locator("#ssmInterClose21614")
                if ad_close.is_visible():
                    ad_close.click()
                    logger.info("🧹 Pop-up publicitario cerrado ✅")
            except Exception:
                pass

            # Intentar click en 'Bajadas' (si existe)
            try:
                if not safe_click(page.locator("button:has-text('Bajadas')"), "Bajadas", timeout=5000):
                    logger.debug("Botón 'Bajadas' no encontrado o no visible.")
                else:
                    logger.info("BOTON BAJADAS PULSADO")
            except Exception:
                logger.debug("Error al pulsar Bajadas, continuando.")

            saved_paths["subidas_bajadas"] = guardar_html(page.content(), archivoSB)
            logger.info("✅ Todos los HTML guardados correctamente.")

        except Exception as exc:
            logger.exception("Error crítico durante login/scrape: %s", exc)
            raise
        finally:
            if browser:
                try:
                    browser.close()
                except Exception:
                    logger.debug("Error cerrando el navegador, ignorado.")
    return saved_paths

if __name__ == "__main__":
    # Configura logging básico si se ejecuta directamente
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    paths = login()
    print("Saved files:", paths)
