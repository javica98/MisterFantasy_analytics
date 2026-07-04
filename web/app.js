const state = {
  data: null,
  view: "home",
  selectedManager: null,
  selectedIssue: 0,
  standingsTab: "league",
  search: "",
};

const app = document.querySelector("#app");
const pageTitle = document.querySelector("#page-title");
const navItems = document.querySelectorAll(".nav-item");

const fallbackData = {
  league: {
    name: "Sotano League",
    season: "Temporada 2026",
    dateRange: "Última jornada",
    standings: [],
    poolStandings: [],
    managerOfMonth: { name: "Sin datos", subtitle: "Pendiente", description: "Genera datos para alimentar el dashboard." },
    playerOfMonth: { name: "Sin datos", description: "Sin jugador destacado todavía." },
    highlights: [],
    latestHeadline: {},
  },
  managers: [],
  news: [],
};

init();

async function init() {
  injectWatermark();
  state.data = await loadData();
  state.selectedManager = state.data.managers[0]?.name ?? null;
  bindEvents();
  render();
}

function injectWatermark() {
  const wm = document.createElement('div');
  wm.className = 'watermark';
  wm.setAttribute('aria-hidden', 'true');
  wm.textContent = Array(80).fill('SOTANO LEAGUE').join('   ');
  document.body.insertBefore(wm, document.body.firstChild);
}

async function loadData() {
  try {
    const response = await fetch("/web/data/app-data.json", { cache: "no-store" });
    if (!response.ok) throw new Error("No app data");
    return await response.json();
  } catch (error) {
    return fallbackData;
  }
}

function bindEvents() {
  navItems.forEach((item) => {
    item.addEventListener("click", () => {
      state.view = item.dataset.view;
      render();
    });
  });

}

function render() {
  navItems.forEach((item) => item.classList.toggle("active", item.dataset.view === state.view));
  const titles = { home: "Dashboard", stats: "Estadísticas", news: "Noticias" };
  pageTitle.textContent = titles[state.view];

  if (state.view === "home") renderHome();
  if (state.view === "stats") renderStats();
  if (state.view === "news") renderNews();
}

function renderHome() {
  const { league } = state.data;
  const activeStandings = state.standingsTab === "pool" ? league.poolStandings : league.standings;
  const standings = filterItems(activeStandings, ["manager"]);
  const tableTitle = state.standingsTab === "pool" ? "Clasificación de la porra" : "Clasificación de la liga";
  const pointsLabel = state.standingsTab === "pool" ? "Aciertos" : "Puntos";
  const headline = league.latestHeadline || {};

  app.innerHTML = `
  <div class="grid home-grid">

    <!-- TABLA -->
    <section class="card standings-card">
      <div class="card-header">
        <div>
          <p class="eyebrow">${league.name}</p>
          <h2>${tableTitle}</h2>
        </div>

        <div class="segmented">
          <button class="${state.standingsTab === "league" ? "active" : ""}" data-standings-tab="league">Liga</button>
          <button class="${state.standingsTab === "pool" ? "active" : ""}" data-standings-tab="pool">Porra</button>
        </div>
      </div>

      <div class="table">
        <div class="table-row table-head">
          <span>Rango</span><span>Manager</span><span>${pointsLabel}</span>
        </div>

        ${standings.map(row => `
          <div class="table-row">
            <span class="rank">#${row.rank ?? "?"}</span>
            <div class="team-cell">
              ${managerAvatar(row.manager)}
              <strong>${escapeHtml(row.manager)}</strong>
            </div>
            <span class="data">${row.points ?? 0}</span>
          </div>
        `).join("") || emptyRow("Sin clasificación disponible")}
      </div>
    </section>

    <!-- COLUMNA DERECHA -->
    <div class="side-column">

      <!-- Manager del mes -->
      <aside class="card pad spotlight">
        <p class="label">Manager del mes</p>
        <div class="spotlight-person">
          <div class="portrait">
            ${managerAvatar(league.managerOfMonth.name, 90)}
          </div>
          <div>
            <h2>${escapeHtml(league.managerOfMonth.name)}</h2>
            <p class="muted">${escapeHtml(league.managerOfMonth.subtitle || "Forma destacada")}</p>
          </div>
        </div>
        <p>${escapeHtml(league.managerOfMonth.description || "")}</p>
      </aside>

      <!-- Jugador del mes -->
      <article class="card pad metric success">
        <p class="label">Jugador del mes</p>
        <div style="display:flex;align-items:center;gap:10px;margin-top:12px">
          ${playerAvatar(league.playerOfMonth.name, 52)}
          <div class="value" style="margin:0">${escapeHtml(league.playerOfMonth.name)}</div>
        </div>
        <p class="muted" style="margin-top:6px">${escapeHtml(league.playerOfMonth.description || "")}</p>
      </article>

      <!-- Drama de liga -->
      <section class="card hero-card">
        <span class="chip">Drama de liga</span>
        <h2>${escapeHtml(headline.titulo || "La liga calienta motores")}</h2>
        <p>${escapeHtml([headline.subtitulo, ...(headline.texto || [])].filter(Boolean).join(" "))}</p>
      </section>

    </div>

  </div>

  <!-- KPIs generales -->
  <div style="margin-top:28px;margin-bottom:12px">
    <p class="eyebrow">Sotano League</p>
    <h2 style="margin:4px 0 0;font-size:20px">KPIs de la liga</h2>
  </div>

  <div class="grid metric-grid">

    <article class="card pad metric warning">
      <p class="label">💸 Jugador más caro</p>
      <div style="display:flex;align-items:center;gap:10px;margin-top:12px">
        ${playerAvatar(league.mostExpensiveBuy?.player ?? "", 48)}
        <div class="value" style="margin:0">${escapeHtml(league.mostExpensiveBuy?.player ?? "—")}</div>
      </div>
      <p class="muted" style="margin-top:6px">${escapeHtml(league.mostExpensiveBuy?.manager ?? "")}${league.mostExpensiveBuy?.amount ? " · " + league.mostExpensiveBuy.amount + " M" : ""}</p>
    </article>

    <article class="card pad metric warning">
      <p class="label">⚡ Clausulazo más caro</p>
      <div style="display:flex;align-items:center;gap:10px;margin-top:12px">
        ${playerAvatar(league.mostExpensiveClause?.player ?? "", 48)}
        <div class="value" style="margin:0">${escapeHtml(league.mostExpensiveClause?.player ?? "—")}</div>
      </div>
      <p class="muted" style="margin-top:6px">${escapeHtml(league.mostExpensiveClause?.manager ?? "")}${league.mostExpensiveClause?.amount ? " · " + league.mostExpensiveClause.amount + " M" : ""}</p>
    </article>

    <article class="card pad metric success">
      <p class="label">🏹 Más clausulazos realizados</p>
      <div style="display:flex;align-items:center;gap:10px;margin-top:12px">
        ${managerAvatar(league.mostClausesGiven?.manager ?? "", 48)}
        <div class="value" style="margin:0">${escapeHtml(league.mostClausesGiven?.manager ?? "—")}</div>
      </div>
      <p class="muted" style="margin-top:6px">${league.mostClausesGiven?.count ? league.mostClausesGiven.count + " clausulazos" : "Sin datos"}</p>
    </article>

    <article class="card pad metric">
      <p class="label">🛡️ Más clausulazos recibidos</p>
      <div style="display:flex;align-items:center;gap:10px;margin-top:12px">
        ${managerAvatar(league.mostClausesReceived?.manager ?? "", 48)}
        <div class="value" style="margin:0">${escapeHtml(league.mostClausesReceived?.manager ?? "—")}</div>
      </div>
      <p class="muted" style="margin-top:6px">${league.mostClausesReceived?.count ? league.mostClausesReceived.count + " recibidos" : "Sin datos"}</p>
    </article>

  </div>

  <!-- Top 3 del mes -->
  <div style="margin-top:28px;margin-bottom:12px">
    <p class="eyebrow">Sotano League · ${new Date().toLocaleString('es-ES', { month: 'long', year: 'numeric' })}</p>
    <h2 style="margin:4px 0 0;font-size:20px">Movimientos del mes</h2>
  </div>

  <div class="grid" style="grid-template-columns:1fr 1fr;gap:16px">

    <!-- Top 3 clausulazos -->
    <section class="card">
      <div class="card-header">
        <h3>⚡ Top 3 clausulazos más caros</h3>
      </div>
      <div class="table">
        <div class="table-row table-head" style="grid-template-columns:1fr 1fr 1fr 80px">
          <span>Jugador</span><span>De</span><span>A</span><span>€</span>
        </div>
        ${(league.topClauses ?? []).length ? (league.topClauses).map(row => `
          <div class="table-row" style="grid-template-columns:1fr 1fr 1fr 80px">
            <div style="display:flex;align-items:center;gap:8px">
              ${playerAvatar(row.player ?? "", 38)}
              <strong>${escapeHtml(row.player ?? "—")}</strong>
            </div>
            <span class="muted">${escapeHtml(row.from ?? "—")}</span>
            <span>${escapeHtml(row.to ?? "—")}</span>
            <span class="data">${row.amount ? row.amount + "M" : "—"}</span>
          </div>
        `).join("") : `
          <div class="table-row"><span></span><span class="muted">Sin datos disponibles</span><span></span><span></span></div>
        `}
      </div>
    </section>

    <!-- Top 3 fichajes de mercado -->
    <section class="card">
      <div class="card-header">
        <h3>💸 Top 3 fichajes de mercado</h3>
      </div>
      <div class="table">
        <div class="table-row table-head" style="grid-template-columns:1fr 1fr 80px">
          <span>Jugador</span><span>Manager</span><span>€</span>
        </div>
        ${(league.topTransfers ?? []).length ? (league.topTransfers).map(row => `
          <div class="table-row" style="grid-template-columns:1fr 1fr 80px">
            <div style="display:flex;align-items:center;gap:8px">
              ${playerAvatar(row.player ?? "", 38)}
              <strong>${escapeHtml(row.player ?? "—")}</strong>
            </div>
            <span class="muted">${escapeHtml(row.manager ?? "—")}</span>
            <span class="data">${row.amount ? row.amount + "M" : "—"}</span>
          </div>
        `).join("") : `
          <div class="table-row"><span></span><span class="muted">Sin datos disponibles</span><span></span></div>
        `}
      </div>
    </section>

  </div>
`;

  document.querySelectorAll("[data-standings-tab]").forEach(button => {
    button.addEventListener("click", () => {
      state.standingsTab = button.dataset.standingsTab;
      renderHome();
    });
  });
}

function renderStats() {
  const managers = filterItems(state.data.managers, ["name"]);
  const selected = state.data.managers.find(manager => manager.name === state.selectedManager) || managers[0] || state.data.managers[0];
  if (!selected) {
    app.innerHTML = `<div class="card pad"><h2>No hay datos de managers todavía</h2></div>`;
    return;
  }
  state.selectedManager = selected.name;

  app.innerHTML = `
    <div class="toolbar">
      <div style="display:flex;align-items:center;gap:16px">
        ${managerAvatar(selected.name, 72)}
        <div>
          <p class="eyebrow">Análisis por manager</p>
          <h2 style="margin:4px 0 0">${escapeHtml(selected.name)}</h2>
        </div>
      </div>
      <select class="select" id="manager-select">
        ${state.data.managers.map(manager => `
          <option value="${escapeAttr(manager.name)}" ${manager.name === selected.name ? "selected" : ""}>${escapeHtml(manager.name)}</option>
        `).join("")}
      </select>
    </div>

    <div class="grid" style="grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">

      <!-- Card rendimiento -->
      <article class="card pad metric">
        <p class="label">Rendimiento de la temporada</p>
        <div style="display:flex;gap:24px;margin-top:16px;flex-wrap:wrap">
          <div>
            <p class="muted" style="margin:0;font-size:13px">Posición</p>
            <div class="value" style="color:var(--green)">#${escapeHtml(String(selected.position ?? "—"))}</div>
          </div>
          <div>
            <p class="muted" style="margin:0;font-size:13px">Puntos totales</p>
            <div class="value">${escapeHtml(String(selected.totalPoints ?? "—"))}</div>
          </div>
          <div>
            <p class="muted" style="margin:0;font-size:13px">Media por jornada</p>
            <div class="value">${escapeHtml(String(selected.average ?? "—"))}</div>
          </div>
          <div>
            <p class="muted" style="margin:0;font-size:13px">Desviación típica</p>
            <div class="value">${escapeHtml(String(selected.stdDev ?? "—"))}</div>
          </div>
          <div style="width:100%;height:1px;background:var(--border-soft);margin:4px 0"></div>
          <div>
            <p class="muted" style="margin:0;font-size:13px">⚽ Goles</p>
            <div class="value" style="font-size:20px">${escapeHtml(String(selected.goals ?? "—"))}</div>
          </div>
          <div>
            <p class="muted" style="margin:0;font-size:13px">🎯 Asistencias</p>
            <div class="value" style="font-size:20px">${escapeHtml(String(selected.assists ?? "—"))}</div>
          </div>
          <div>
            <p class="muted" style="margin:0;font-size:13px">🟥 Tarjetas rojas</p>
            <div class="value" style="font-size:20px;color:var(--rose)">${escapeHtml(String(selected.redCards ?? "—"))}</div>
          </div>
        </div>
      </article>

      <!-- Card jugadores clave -->
      <article class="card pad">
        <p class="label">Jugadores clave</p>
        <div style="display:grid;gap:12px;margin-top:16px">

          <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-radius:8px;background:rgba(78,222,163,0.08);border:1px solid rgba(78,222,163,0.18)">
            <div style="display:flex;align-items:center;gap:10px">
              ${playerAvatar(selected.bestPlayerHistoric?.name ?? "", 52)}
              <div>
                <p class="muted" style="margin:0;font-size:11px;text-transform:uppercase;letter-spacing:.06em">🏆 Mejor histórico</p>
                <strong>${escapeHtml(selected.bestPlayerHistoric?.name ?? "—")}</strong>
                <p class="muted" style="margin:2px 0 0;font-size:13px">${escapeHtml(selected.bestPlayerHistoric?.team ?? "")} · ${escapeHtml(selected.bestPlayerHistoric?.position ?? "")}</p>
              </div>
            </div>
            <span style="color:var(--green);font-family:var(--mono);font-weight:700;font-size:18px">${selected.bestPlayerHistoric?.points ?? "—"} pts</span>
          </div>

          <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-radius:8px;background:rgba(255,183,126,0.08);border:1px solid rgba(255,183,126,0.18)">
            <div style="display:flex;align-items:center;gap:10px">
              ${playerAvatar(selected.bestPlayer?.name ?? "", 52)}
              <div>
                <p class="muted" style="margin:0;font-size:11px;text-transform:uppercase;letter-spacing:.06em">⭐ Mejor actual</p>
                <strong>${escapeHtml(selected.bestPlayer?.name ?? "—")}</strong>
                <p class="muted" style="margin:2px 0 0;font-size:13px">${escapeHtml(selected.bestPlayer?.team ?? "")} · ${escapeHtml(selected.bestPlayer?.position ?? "")}</p>
              </div>
            </div>
            <span style="color:var(--primary);font-family:var(--mono);font-weight:700;font-size:18px">${selected.bestPlayer?.points ?? "—"} pts</span>
          </div>

          <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-radius:8px;background:rgba(255,77,117,0.08);border:1px solid rgba(255,77,117,0.18)">
            <div style="display:flex;align-items:center;gap:10px">
              ${playerAvatar(selected.worstPlayer?.name ?? "", 52)}
              <div>
                <p class="muted" style="margin:0;font-size:11px;text-transform:uppercase;letter-spacing:.06em">📉 Peor actual</p>
                <strong>${escapeHtml(selected.worstPlayer?.name ?? "—")}</strong>
                <p class="muted" style="margin:2px 0 0;font-size:13px">${escapeHtml(selected.worstPlayer?.team ?? "")} · ${escapeHtml(selected.worstPlayer?.position ?? "")}</p>
              </div>
            </div>
            <span style="color:var(--rose);font-family:var(--mono);font-weight:700;font-size:18px">${selected.worstPlayer?.points ?? "—"} pts</span>
          </div>

        </div>
      </article>

    </div>

    <div class="grid stats-grid" style="margin-top:16px">
      <section class="card pad span-7">
        <div class="card-header" style="padding:0 0 16px;border-bottom:0">
          <h3>Rendimiento histórico</h3>
          <span class="muted">Últimas 8 jornadas</span>
        </div>
        <div class="chart">
          ${selected.form.slice(-8).map(value => `
            <div style="display:flex;flex-direction:column;align-items:center;flex:1;gap:4px">
              <span style="font-family:var(--mono);font-size:11px;color:var(--muted)">${value}</span>
              <span class="chart-bar" style="height:${Math.max(12, value * 2.6)}px;width:100%" title="${value} pts"></span>
            </div>
          `).join("")}
        </div>
      </section>

      <section class="card pad span-5">
        <h3>Mercado</h3>
        <div class="bars" style="margin-top:18px">
          ${absoluteBarRow("Mercado libre", selected.market?.mercado ?? 0)}
          ${absoluteBarRow("Cláusulas", selected.market?.clausulas ?? 0)}
          ${absoluteBarRow("Acuerdos", selected.market?.acuerdos ?? 0)}
        </div>
      </section>

    </div>
  `;

  document.querySelector("#manager-select").addEventListener("change", (event) => {
    state.selectedManager = event.target.value;
    renderStats();
  });
}

function renderNews() {
  const issues = filterItems(state.data.news, ["title", "subtitle", "summary", "date"]);
  const selected = issues[state.selectedIssue] || issues[0] || state.data.news[0];
  if (!selected) {
    app.innerHTML = `<div class="card pad"><h2>No hay noticias generadas todavía</h2><p class="muted">Cuando exista news_cards.json aparecerán aquí.</p></div>`;
    return;
  }

  app.innerHTML = `
    <div class="news-layout">
      <aside class="card pad">
        <p class="label">Timeline</p>
        <h2>Jornadas</h2>
        <div class="timeline">
          ${issues.map((issue, index) => `
            <button class="issue-button ${issue.date === selected.date ? "active" : ""}" data-issue="${index}">
              <span class="chip">${escapeHtml(issue.date)}</span>
              <strong>${escapeHtml(issue.title)}</strong>
              <span class="muted">${escapeHtml(issue.subtitle)}</span>
            </button>
          `).join("")}
        </div>
      </aside>

      <section>
        <article class="card hero-card">
          <span class="chip">${escapeHtml(selected.date)}</span>
          <h2>${escapeHtml(selected.title)}</h2>
          <p>${escapeHtml(selected.summary || selected.subtitle)}</p>
        </article>

        <div class="news-grid" style="margin-top:16px">
          ${selected.cards.map(card => `
            <article class="article-card">
              <span class="chip">${escapeHtml(card.type || "noticia")}</span>
              <h3>${escapeHtml(card.title || "Sin titular")}</h3>
              <p><strong>${escapeHtml(card.subtitle || "")}</strong></p>
              ${(card.text || []).map(text => `<p>${escapeHtml(text)}</p>`).join("")}
            </article>
          `).join("")}
        </div>
      </section>
    </div>
  `;

  document.querySelectorAll(".issue-button").forEach(button => {
    button.addEventListener("click", () => {
      state.selectedIssue = Number(button.dataset.issue);
      renderNews();
    });
  });
}

function statCard(label, value, meta) {
  return `
    <article class="card pad metric">
      <p class="label">${escapeHtml(label)}</p>
      <div class="value">${escapeHtml(value)}</div>
      <p class="muted">${escapeHtml(meta)}</p>
    </article>
  `;
}

function barRow(label, value) {
  return `
    <div class="bar-row">
      <div class="bar-meta"><span>${escapeHtml(label)}</span><strong>${value}%</strong></div>
      <div class="bar"><span style="width:${value}%"></span></div>
    </div>
  `;
}

function absoluteBarRow(label, value) {
  const max = 30; // máximo razonable de compras por tipo para escalar la barra
  const pct = Math.min(100, Math.round((value / max) * 100));
  return `
    <div class="bar-row">
      <div class="bar-meta"><span>${escapeHtml(label)}</span><strong>${value} compras</strong></div>
      <div class="bar"><span style="width:${pct}%"></span></div>
    </div>
  `;
}

function playerBox(label, player, tone) {
  return `
    <div class="player-card">
      <span class="chip">${escapeHtml(label)}</span>
      <h3>${escapeHtml(player.name)}</h3>
      <p class="muted">${escapeHtml(player.team || "")} · ${escapeHtml(player.position || "")}</p>
      <div class="value" style="color:${tone === "success" ? "var(--green)" : "var(--primary)"}">${player.points} pts</div>
    </div>
  `;
}

function filterItems(items, keys) {
  if (!state.search) return items || [];
  return (items || []).filter(item =>
    keys.some(key => String(item[key] || "").toLowerCase().includes(state.search))
  );
}

function emptyRow(text) {
  return `<div class="table-row"><span></span><strong>${escapeHtml(text)}</strong><span></span></div>`;
}

function initials(name = "") {
  return String(name)
    .replace(/[^\p{L}\p{N}\s]/gu, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0])
    .join("")
    .toUpperCase() || "SL";
}

// Mapa de nombres de manager a su escudo en assets/
const MANAGER_SHIELDS = {
  "Chamacónicos":   "/assets/chamacónicos.png",
  "Dani":           "/assets/dani.png",
  "De la Guettir FC": "/assets/de_la_guettir_fc.png",
  "Jotabetrbb":     "/assets/jotabetrbb.png",
  "Juanba":         "/assets/juanba.png",
  "Libre":          "/assets/libre.png",
  "Los marinero":   "/assets/los_marinero.png",
  "Maldinillo 💥":  "/assets/maldinillo.png",
  "Maldinillo":     "/assets/maldinillo.png",
  "MuchaSalsa":     "/assets/muchasalsa.png",
  "muchasalsa":     "/assets/muchasalsa.png",
};

function playerAvatar(name, size = 36) {
  const map = state.data?.playersMap || {};

  // 1. Búsqueda exacta
  let url = map[name];

  if (!url && name) {
    // Normaliza texto: minúsculas y sin acentos para comparar
    const norm = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

    const inputNorm = norm(name);
    const mapKeys   = Object.keys(map);

    // 2. Match por apellido(s): última palabra del nombre
    //    Cubre "Kylian Mbappé" ↔ "K. Mbappé" (mismo apellido "mbappe")
    const inputSurname = inputNorm.split(/\s+/).at(-1);
    const byLastName   = mapKeys.find(k => norm(k).split(/\s+/).at(-1) === inputSurname);
    if (byLastName) url = map[byLastName];

    // 3. Match por apellido compuesto (últimas 2 palabras)
    //    Cubre "De Bruyne" ↔ "K. De Bruyne"
    if (!url) {
      const inputSurname2 = inputNorm.split(/\s+/).slice(-2).join(' ');
      const by2 = mapKeys.find(k => norm(k).endsWith(inputSurname2));
      if (by2) url = map[by2];
    }
  }

  if (url) {
    return `<img src="${escapeAttr(url)}" alt="${escapeAttr(name)}"
      onerror="this.style.display='none'"
      style="width:${size}px;height:${size}px;border-radius:50%;object-fit:cover;border:1px solid rgba(255,255,255,0.12);flex-shrink:0;">`;
  }
  // Fallback: iniciales
  return `<span style="display:inline-flex;align-items:center;justify-content:center;width:${size}px;height:${size}px;border-radius:50%;background:#1e1e1e;border:1px solid #2a2a2a;font-family:var(--mono);font-size:${Math.round(size*0.35)}px;font-weight:700;color:#888;flex-shrink:0;">${initials(name)}</span>`;
}

function managerAvatar(name, size = 60) {
  const fileName = String(name)
    .toLowerCase()
    .replace(/[^a-z0-9áéíóúüñ\s]/gi, "")
    .trim()
    .replace(/\s+/g, "_");

  const src = `/assets/web/${fileName}.png`;

  return `
    <img 
      src="${src}" 
      alt="${escapeAttr(name)}"
      onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"
      style="width:${size}px;height:${size}px;border-radius:10px;object-fit:cover;border:1px solid rgba(255,255,255,0.08);image-rendering:auto;"
    >
    <span class="avatar" style="display:none;width:${size}px;height:${size}px">
      ${initials(name)}
    </span>
  `;
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value = "") {
  return escapeHtml(value);
}
