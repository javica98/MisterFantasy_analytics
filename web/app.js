const state = {
  data: null,
  view: "home",
  selectedManager: null,
  selectedSeason: null,
  selectedIssue: 0,
  standingsTab: "league",
  usingFallback: false,
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
  seasons: [],
  activeSeason: null,
  managersBySeason: {},
};

init();

async function init() {
  injectWatermark();
  state.data = await loadData();
  state.selectedManager = state.data.managers[0]?.name ?? null;
  state.selectedSeason = state.data.activeSeason || state.data.seasons?.[0] || null;
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
    if (!response.ok) throw new Error(`app-data.json respondió ${response.status}`);
    return await response.json();
  } catch (error) {
    // Antes esto fallaba en silencio total: cualquier error (JSON corrupto,
    // 500, CORS...) caía al mismo fallback sin dejar rastro de por qué
    // (hallazgo WEB-09). Como mínimo lo dejamos en consola, y state.usingFallback
    // hace que render() muestre un aviso discreto en vez de fingir que todo va bien.
    console.warn("No se pudieron cargar los datos de la liga, usando fallback:", error);
    state.usingFallback = true;
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
  navItems.forEach((item) => {
    const active = item.dataset.view === state.view;
    item.classList.toggle("active", active);
    item.setAttribute("aria-selected", String(active));
  });
  const titles = { home: "Dashboard", stats: "Estadísticas", news: "Noticias" };
  pageTitle.textContent = titles[state.view];

  if (state.view === "home") renderHome();
  if (state.view === "stats") renderStats();
  if (state.view === "news") renderNews();

  renderFallbackBanner();
}

function renderFallbackBanner() {
  document.querySelector(".fallback-banner")?.remove();
  if (!state.usingFallback) return;

  const banner = document.createElement("div");
  banner.className = "fallback-banner";
  banner.setAttribute("role", "status");
  banner.textContent = "No se pudieron cargar los datos de la liga — mostrando datos de respaldo.";
  banner.style.cssText = "margin-bottom:16px;padding:10px 14px;border-radius:8px;background:rgba(255,183,126,0.12);border:1px solid rgba(255,183,126,0.3);color:var(--muted);font-size:13px";
  app.insertBefore(banner, app.firstChild);
}

function renderHome() {
  const { league } = state.data;
  const standings = (state.standingsTab === "pool" ? league.poolStandings : league.standings) || [];
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

        <div class="segmented" role="tablist" aria-label="Tipo de clasificación">
          <button class="${state.standingsTab === "league" ? "active" : ""}" data-standings-tab="league" role="tab" aria-selected="${state.standingsTab === "league"}">Liga</button>
          <button class="${state.standingsTab === "pool" ? "active" : ""}" data-standings-tab="pool" role="tab" aria-selected="${state.standingsTab === "pool"}">Porra</button>
        </div>
      </div>

      ${renderStandingsTable(standings, pointsLabel)}
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
  const seasons = state.data.seasons || [];
  if (!state.selectedSeason || !seasons.includes(state.selectedSeason)) {
    state.selectedSeason = state.data.activeSeason || seasons[0] || null;
  }
  const managers = (state.data.managersBySeason || {})[state.selectedSeason] || state.data.managers || [];
  const selected = managers.find(manager => manager.name === state.selectedManager) || managers[0];
  if (!selected) {
    app.innerHTML = `<div class="card pad"><h2>No hay datos de managers todavía</h2></div>`;
    return;
  }
  state.selectedManager = selected.name;

  const form = selected.seasonForm || selected.form || [];
  const lastPoints = form.length ? form[form.length - 1] : null;
  const prevPoints = form.length > 1 ? form[form.length - 2] : null;
  let formDeltaBadge = "";
  if (lastPoints !== null && prevPoints) {
    const deltaPct = Math.round(((lastPoints - prevPoints) / prevPoints) * 100);
    const sign = deltaPct >= 0 ? "+" : "";
    formDeltaBadge = `<span class="delta-badge ${deltaPct >= 0 ? "positive" : "negative"}">${sign}${deltaPct}%</span>`;
  }
  const marketTotal = (selected.market?.mercado ?? 0) + (selected.market?.clausulas ?? 0) + (selected.market?.acuerdos ?? 0);
  const TOTAL_JORNADAS = 38;
  const recentForm = form.slice(0, TOTAL_JORNADAS);
  for (let i = recentForm.length; i < TOTAL_JORNADAS; i++) recentForm.push(null);
  const maxFormValue = Math.max(1, ...recentForm.filter(value => value !== null));

  app.innerHTML = `
    <div class="stats-fade">
    <div class="manager-picker" role="tablist" aria-label="Seleccionar manager">
      ${managers.map(manager => `
        <button
          class="manager-picker-item ${manager.name === selected.name ? "active" : ""}"
          data-manager="${escapeAttr(manager.name)}"
          role="tab"
          aria-selected="${manager.name === selected.name}"
          title="${escapeAttr(manager.name)}"
        >
          <span class="avatar-ring">${managerAvatar(manager.name, 52)}</span>
          <span class="picker-name">${escapeHtml(manager.name)}</span>
        </button>
      `).join("")}
    </div>

    <div class="toolbar">
      <div style="display:flex;align-items:center;gap:16px">
        ${managerAvatar(selected.name, 72)}
        <div>
          <p class="eyebrow">Análisis por manager</p>
          <h2 style="margin:4px 0 0">${escapeHtml(selected.name)}</h2>
        </div>
      </div>
      ${seasons.length > 1 ? `
        <select class="select" id="season-select" style="min-width:120px" aria-label="Temporada">
          ${seasons.map(season => `
            <option value="${escapeAttr(season)}" ${season === state.selectedSeason ? "selected" : ""}>${escapeHtml(season)}</option>
          `).join("")}
        </select>
      ` : ""}
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
        <div class="chart-stat-header">
          <div>
            <p class="label" style="margin:0">Rendimiento histórico</p>
            <div class="chart-stat-value">
              <div class="value" style="margin:0">${lastPoints ?? "—"}</div>
              ${formDeltaBadge}
            </div>
          </div>
          <span class="period-chip">${form.length}/${TOTAL_JORNADAS} jornadas</span>
        </div>
        <div class="chart">
          ${recentForm.map((value, index) => value === null ? `
            <div class="chart-col">
              <div class="chart-track" title="Jornada ${index + 1}: sin jugar"></div>
            </div>
          ` : `
            <div class="chart-col">
              <div class="chart-track">
                <span class="chart-bar" style="height:${Math.max(6, Math.round((value / maxFormValue) * 100))}%" title="Jornada ${index + 1}: ${value} pts"></span>
              </div>
            </div>
          `).join("")}
        </div>
      </section>

      <section class="card pad span-5">
        <div class="chart-stat-header">
          <div>
            <p class="label" style="margin:0">Mercado</p>
            <div class="chart-stat-value">
              <div class="value" style="margin:0">${marketTotal}</div>
              <span class="muted" style="font-size:12px">compras totales</span>
            </div>
          </div>
          <span class="period-chip">Temporada</span>
        </div>
        <div class="bars" style="margin-top:18px">
          ${absoluteBarRow("Mercado libre", selected.market?.mercado ?? 0)}
          ${absoluteBarRow("Cláusulas", selected.market?.clausulas ?? 0)}
          ${absoluteBarRow("Acuerdos", selected.market?.acuerdos ?? 0)}
        </div>
      </section>

    </div>
    </div>
  `;

  document.querySelectorAll(".manager-picker-item").forEach(button => {
    button.addEventListener("click", () => {
      state.selectedManager = button.dataset.manager;
      renderStats();
    });
  });

  document.querySelector("#season-select")?.addEventListener("change", (event) => {
    state.selectedSeason = event.target.value;
    state.selectedManager = null; // se resuelve al primer manager disponible de la nueva temporada
    renderStats();
  });
}

function renderNews() {
  const seasons = state.data.seasons || [];
  if (!state.selectedSeason || !seasons.includes(state.selectedSeason)) {
    state.selectedSeason = state.data.activeSeason || seasons[0] || null;
  }
  const issues = (state.data.newsBySeason || {})[state.selectedSeason] || state.data.news || [];
  const selected = issues[state.selectedIssue] || issues[0];

  const seasonSelectHtml = seasons.length > 1 ? `
    <select class="select" id="news-season-select" style="min-width:120px" aria-label="Temporada">
      ${seasons.map(season => `
        <option value="${escapeAttr(season)}" ${season === state.selectedSeason ? "selected" : ""}>${escapeHtml(season)}</option>
      `).join("")}
    </select>
  ` : "";

  if (!selected) {
    app.innerHTML = `
      <div class="toolbar">
        <h2 style="margin:0">Noticias</h2>
        ${seasonSelectHtml}
      </div>
      <div class="card pad"><h2>No hay noticias generadas todavía para ${escapeHtml(state.selectedSeason ?? "esta temporada")}</h2><p class="muted">Cuando exista news_cards.json aparecerán aquí.</p></div>
    `;
    document.querySelector("#news-season-select")?.addEventListener("change", (event) => {
      state.selectedSeason = event.target.value;
      state.selectedIssue = 0;
      renderNews();
    });
    return;
  }

  app.innerHTML = `
    <div class="grid" style="gap:16px">
      <div class="card pad">
        <div class="toolbar" style="margin-bottom:0">
          <div>
            <p class="label">Timeline</p>
            <h2 style="margin:2px 0 0">Jornadas</h2>
          </div>
          ${seasonSelectHtml}
        </div>
        <div class="jornada-carousel" role="tablist" aria-label="Ediciones del periódico">
          ${issues.map((issue, index) => `
            <button
              class="jornada-card ${issue.date === selected.date ? "active" : ""}"
              data-issue="${index}"
              role="tab"
              aria-selected="${issue.date === selected.date}"
              title="${escapeAttr(issue.title)}"
              style="background-image:url('/newspaper/photos/Portada_Jornada.jpg')"
            >
              <span class="jornada-dot"></span>
              <span class="jornada-label">${escapeHtml(issue.date)}</span>
            </button>
          `).join("")}
        </div>
      </div>

      <section>
        <article class="card hero-card">
          <span class="chip">${escapeHtml(selected.date)}</span>
          <h2>${escapeHtml(selected.title)}</h2>
          <p>${escapeHtml(selected.summary || selected.subtitle)}</p>
        </article>

        ${renderStandingsAtIssue(selected)}

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

  document.querySelectorAll(".jornada-card").forEach(button => {
    button.addEventListener("click", () => {
      state.selectedIssue = Number(button.dataset.issue);
      renderNews();
    });
  });

  document.querySelector("#news-season-select")?.addEventListener("change", (event) => {
    state.selectedSeason = event.target.value;
    state.selectedIssue = 0;
    renderNews();
  });

  document.querySelector(".jornada-card.active")?.scrollIntoView({
    inline: "center",
    block: "nearest",
    behavior: "smooth",
  });
}

function renderStandingsAtIssue(issue) {
  const rows = issue.standingsAtIssue;
  if (!rows || !rows.length) return "";

  return `
    <section class="card" style="margin-top:16px">
      <div class="card-header">
        <h3>Clasificación en ${escapeHtml(issue.date)}</h3>
      </div>
      ${renderStandingsTable(rows, "Puntos")}
    </section>
  `;
}

// Compartida por renderHome() y renderStandingsAtIssue() — antes cada una
// reescribía la misma tabla Rango/Manager/Puntos casi idéntica por su lado
// (hallazgo WEB-08).
function renderStandingsTable(rows, pointsLabel = "Puntos", emptyText = "Sin clasificación disponible") {
  return `
    <div class="table">
      <div class="table-row table-head">
        <span>Rango</span><span>Manager</span><span>${escapeHtml(pointsLabel)}</span>
      </div>
      ${(rows || []).map(row => `
        <div class="table-row">
          <span class="rank">#${row.rank ?? "?"}</span>
          <div class="team-cell">
            ${managerAvatar(row.manager)}
            <strong>${escapeHtml(row.manager)}</strong>
          </div>
          <span class="data">${row.points ?? 0}</span>
        </div>
      `).join("") || emptyRow(emptyText)}
    </div>
  `;
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
