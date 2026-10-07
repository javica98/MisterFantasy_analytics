"""
Exploración (solo lectura), 2ª pasada: pulsa cada botón de jornada en
feed#gameweek y guarda el POST + JSON de /ajax/sw/gameweek para cada una.
También abre la página de detalle de un partido jugado.

El usuario inicia sesión a mano en la ventana visible.

Uso:
    python scripts/explore_mister_gameweeks.py [carpeta_salida]
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://mister.mundodeportivo.com"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw/explore2")
OUT.mkdir(parents=True, exist_ok=True)

captured = []


def on_response(resp):
    try:
        if "/ajax/sw/gameweek" in resp.url or "/ajax/sw/" in resp.url and "match" in resp.url:
            captured.append({"url": resp.url, "post": resp.request.post_data, "body": resp.text()})
    except Exception:
        pass


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_context().new_page()
    page.on("response", on_response)

    page.goto(BASE, wait_until="domcontentloaded")
    print("\n👉 Inicia sesión en la ventana de Chromium (tienes 5 minutos)...\n")
    page.wait_for_selector("#fg-content", timeout=300_000)
    print("✅ Sesión detectada. Explorando jornadas (no toques la ventana)...")

    page.goto(f"{BASE}/feed#gameweek", wait_until="domcontentloaded")
    page.wait_for_selector(".gameweek-selector-inline button[data-id]", timeout=60_000)
    page.wait_for_timeout(2000)

    buttons = page.eval_on_selector_all(
        ".gameweek-selector-inline button[data-id]",
        "bs => bs.map(b => [b.dataset.id, b.textContent.trim()])",
    )
    print(f"  {len(buttons)} botones de jornada")

    for gid, label in buttons[:9]:  # J1..J9: jugadas + la siguiente
        n_before = len(captured)
        try:
            btn = page.locator(f".gameweek-selector-inline button[data-id='{gid}']").first
            btn.scroll_into_view_if_needed(timeout=5000)
            btn.click(timeout=5000)
            page.wait_for_timeout(3000)
            (OUT / f"gameweek_{label.replace(' ', '')}_{gid}.html").write_text(page.content(), encoding="utf-8")
            print(f"  {label} ({gid}): {len(captured) - n_before} respuestas")
        except Exception as e:
            print(f"  ⚠️ {label}: {e}")

    # Detalle de un partido jugado (primer enlace a gameweek/<gw>/<match> de J7)
    j7 = next((gid for gid, label in buttons if label.strip() in ("J7", "Jornada 7")), None)
    if j7:
        page.locator(f".gameweek-selector-inline button[data-id='{j7}']").first.click()
        page.wait_for_timeout(3000)
        hrefs = page.eval_on_selector_all(
            f"a[href*='gameweek/{j7}/']", "as => as.map(a => a.getAttribute('href'))")
        if hrefs:
            page.goto(hrefs[0] if hrefs[0].startswith("http") else BASE + "/" + hrefs[0].lstrip("/"),
                      wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            (OUT / "match_detail.html").write_text(page.content(), encoding="utf-8")
            print(f"  💾 detalle de partido: {page.url}")

    (OUT / "gameweek_responses.json").write_text(
        json.dumps(captured, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n🏁 Hecho. {len(captured)} respuestas guardadas en {OUT}")
    browser.close()
