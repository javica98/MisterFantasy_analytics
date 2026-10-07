"""
Exploración (solo lectura) de Mister para diseñar el nuevo scraper.

Abre un Chromium VISIBLE: el usuario inicia sesión a mano. En cuanto se
detecta la sesión (#fg-content), recorre feed#gameweek y standings,
visita cada jornada del selector y guarda:
  - HTML de cada página/jornada
  - Todas las respuestas JSON/XHR del dominio de Mister (endpoints internos)
  - Un índice (index.json) con lo visitado

Uso:
    python scripts/explore_mister.py [carpeta_salida]
"""
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://mister.mundodeportivo.com"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw/explore")
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "xhr").mkdir(exist_ok=True)

index = {"pages": [], "xhr": []}
xhr_n = 0


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:80]


def on_response(resp):
    global xhr_n
    try:
        if "mundodeportivo.com" not in resp.url:
            return
        if resp.request.resource_type not in ("xhr", "fetch"):
            return
        body = resp.text()
        xhr_n += 1
        name = f"{xhr_n:04d}_{slug(resp.url.split('?')[0].replace(BASE, ''))}.txt"
        post = resp.request.post_data or ""
        (OUT / "xhr" / name).write_text(
            f"URL: {resp.url}\nMETHOD: {resp.request.method}\nPOST: {post}\n"
            f"STATUS: {resp.status}\n\n{body}",
            encoding="utf-8",
        )
        index["xhr"].append({"file": name, "url": resp.url, "method": resp.request.method, "post": post})
    except Exception:
        pass


def save(page, name):
    path = OUT / f"{name}.html"
    path.write_text(page.content(), encoding="utf-8")
    index["pages"].append({"name": name, "url": page.url})
    print(f"  💾 {path}")


def scroll(page, n=15):
    last = 0
    for _ in range(n):
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1200)
        h = page.evaluate("() => document.body.scrollHeight")
        if h == last:
            break
        last = h


def gameweek_links(page):
    """Devuelve [(texto, href)] de los selectores de jornada visibles."""
    return page.evaluate(
        """() => [...document.querySelectorAll(
              '.gameweek-selector-inline a, .gameweek-selector a, [class*=gameweek-selector] a')]
            .map(a => [a.textContent.trim(), a.getAttribute('href') || '', a.className])"""
    )


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context()
    page = ctx.new_page()
    page.on("response", on_response)

    page.goto(BASE, wait_until="domcontentloaded")
    print("\n👉 Inicia sesión en la ventana de Chromium (tienes 5 minutos)...\n")
    page.wait_for_selector("#fg-content", timeout=300_000)
    print("✅ Sesión detectada. Explorando (no toques la ventana)...")
    page.wait_for_timeout(3000)

    for ruta in ("feed#gameweek", "standings", "feed#pool-private", "feed"):
        page.goto(f"{BASE}/{ruta}", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        scroll(page)
        save(page, slug(ruta))

        links = gameweek_links(page)
        (OUT / f"{slug(ruta)}_selector.json").write_text(
            json.dumps(links, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {ruta}: {len(links)} enlaces en selector de jornada")

        # Visitar cada jornada del selector (por click, el href puede ser '#')
        seen = set()
        for text, href, _cls in links:
            if not re.search(r"\d", text) or text in seen:
                continue
            seen.add(text)
            try:
                loc = page.locator(
                    "[class*=gameweek-selector] a", has_text=re.compile(rf"^\s*{re.escape(text)}\s*$")
                ).first
                if href and not href.startswith("#") and "javascript" not in href:
                    page.goto(href if href.startswith("http") else BASE + href,
                              wait_until="domcontentloaded")
                else:
                    loc.scroll_into_view_if_needed(timeout=5000)
                    loc.click(timeout=5000)
                page.wait_for_timeout(2500)
                scroll(page, 5)
                save(page, f"{slug(ruta)}__J{slug(text)}")
            except Exception as e:
                print(f"  ⚠️ No se pudo abrir {ruta} / {text}: {e}")
        time.sleep(1)

    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n🏁 Hecho. {len(index['pages'])} páginas y {len(index['xhr'])} respuestas XHR en {OUT}")
    browser.close()
