const state = {
  data: null,
  view: "home",
  selectedManager: null,
  selectedSeason: null,
  // Se guarda la jornada ("J7"), no su índice: el índice cambia al cambiar de
  // temporada y antes hacía que Noticias abriera siempre en la J1.
  selectedIssueDate: null,
  standingsTab: "league",
  usingFallback: false,
};

const VIEWS = { home: "Dashboard", stats: "Estadísticas", news: "Noticias" };
const TOTAL_JORNADAS = 38;
const STALE_AFTER_DAYS = 3;

const app = document.querySelector("#app");
const pageTitle = document.querySelector("#page-title");
const navItems = document.querySelectorAll(".nav-item");
const freshnessPill = document.querySelector("#freshness");

const fallbackData = {
  league: {
    name: "Sotano League",
    season: "",
    standings: [],
    poolStandings: [],
    managerOfMonth: { name: "Sin datos", subtitle: "Pendiente", description: "Genera datos para alimentar el dashboard." },
    playerOfMonth: { name: "Sin datos", description: "Sin jugador destacado todavía." },
    latestHeadline: {},
  },
  managers: [],
  news: [],
  seasons: [],
  activeSeason: null,
  managersBySeason: {},
  newsBySeason: {},
};

let playerIndex = null;

installImageFallbacks();
init();

async function init() {
  injectWatermark();
  state.data = await loadData();
  playerIndex = buildPlayerIndex(state.data.playersMap || {});
  state.selectedSeason = currentSeason();
  state.view = VIEWS[location.hash.slice(1)] ? location.hash.slice(1) : "home";
  bindEvents();
  renderFreshness();
  render();
}

function injectWatermark() {
  const wm = document.createElement("div");
  wm.className = "watermark";
  wm.setAttribute("aria-hidden", "true");
  wm.textContent = Array(80).fill("SOTANO LEAGUE").join("   ");
  document.body.insertBefore(wm, document.body.firstChild);
}

async function loadData() {
  try {
    // Sin cache: "no-store": nginx sirve app-data.json con Cache-Control:
    // no-cache + ETag, así que el navegador revalida y solo lo vuelve a
    // descargar si ha cambiado.
    const response = await fetch("/web/data/app-data.json");
    if (!response.ok) throw new Error(`app-data.json respondió ${response.status}`);
    return await response.json();
  } catch (error) {
    console.warn("No se pudieron cargar los datos de la liga, usando fallback:", error);
    state.usingFallback = true;
    return fallbackData;
  }
}

// La temporada en curso es la última de `seasons` (vienen en orden
// ascendente); activeSeason es la que estaba en config.yaml al generar.
function currentSeason() {
  const seasons = state.data.seasons || [];
  return seasons.includes(state.data.activeSeason)
    ? state.data.activeSeason
    : seasons[seasons.length - 1] || null;
}

function bindEvents() {
  navItems.forEach((item) => {
    item.addEventListener("click", () => setView(item.dataset.view));
  });
  window.addEventListener("hashchange", () => {
    const view = location.hash.slice(1);
    if (VIEWS[view] && view !== state.view) setView(view);
  });
}

function setView(view) {
  state.view = view;
  if (location.hash.slice(1) !== view) history.replaceState(null, "", `#${view}`);
  render();
  window.scrollTo({ top: 0 });
}

// Las imágenes indican su respaldo con data-fallback en vez de onerror="..."
// inline, para que la CSP pueda prohibir scripts inline.
//   data-fallback="hide"  → ocultar la imagen
//   data-fallback="next"  → ocultarla y mostrar el elemento siguiente
//   data-fallback="/ruta" → cambiar a esa imagen (una sola vez)
function installImageFallbacks() {
  document.addEventListener("error", (event) => {
    const img = event.target;
    if (!(img instanceof HTMLImageElement) || !img.dataset.fallback) return;
    const fallback = img.dataset.fallback;
    delete img.dataset.fallback;
    if (fallback === "hide") {
      img.style.display = "none";
    } else if (fallback === "next") {
      img.style.display = "none";
      if (img.nextElementSibling) img.nextElementSibling.style.display = "";
    } else {
      img.src = fallback;
    }
  }, true);
}

// Tras repintar con innerHTML el foco se perdía (quien navega con teclado
// volvía al principio de la página). Devolvemos el foco al control que
// tenga la misma clave data-focus.
function rerender(renderFn, focusKey) {
  renderFn();
  if (!focusKey) return;
  const target = app.querySelector(`[data-focus="${CSS.escape(focusKey)}"]`);
  target?.focus({ preventScroll: true });
}

function render() {
  navItems.forEach((item) => {
    const active = item.dataset.view === state.view;
    item.classList.toggle("active", active);
    if (active) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
  pageTitle.textContent = VIEWS[state.view];
  document.title = `${VIEWS[state.view]} · Sotano League`;

  if (state.view === "home") renderHome();
  if (state.view === "stats") renderStats();
  if (state.view === "news") renderNews();
}

function renderFreshness() {
  if (!freshnessPill) return;
  const generated = state.data.generatedAt ? new Date(state.data.generatedAt) : null;
  if (!generated || Number.isNaN(generated.getTime())) {
    freshnessPill.hidden = true;
    return;
  }
  const ageDays = (Date.now() - generated.getTime()) / 86_400_000;
  const label = generated.toLocaleDateString("es-ES", { day: "numeric", month: "short" });
  const stale = ageDays > STALE_AFTER_DAYS;
  freshnessPill.classList.toggle("stale", stale);
  freshnessPill.querySelector(".freshness-text").textContent = stale ? `Datos del ${label}` : `Actualizado ${label}`;
  freshnessPill.title = `Datos generados el ${generated.toLocaleString("es-ES")}`;
}

function fallbackBanner() {
  if (!state.usingFallback) return "";
  return `<div class="fallback-banner" role="status">No se pudieron cargar los datos de la liga — mostrando datos de respaldo.</div>`;
}

function seasonSelect(id) {
  const seasons = state.data.seasons || [];
  if (seasons.length < 2) return "";
  return `
    <select class="select select-compact" id="${id}" aria-label="Temporada">
      ${seasons.map(season => `
        <option value="${escapeHtml(season)}" ${season === state.selectedSeason ? "selected" : ""}>Temporada ${escapeHtml(season)}</option>
      `).join("")}
    </select>
  `;
}

// Título de sección con el contexto (temporada) debajo, como subtítulo.
function sectionHeading(context, title) {
  return `
    <div class="section-heading">
      <h2>${escapeHtml(title)}</h2>
      <p class="muted small">${escapeHtml(context)}</p>
    </div>
  `;
}

// ── Home ─────────────────────────────────────────────────────────────────────

function renderHome() {
  const { league } = state.data;
  const isPool = state.standingsTab === "pool";
  const standings = (isPool ? league.poolStandings : league.standings) || [];
  const roundLabel = league.lastRound ? `J${league.lastRound}` : "Última jornada";
  const seasonLabel = league.season ? `Temporada ${league.season}` : league.name;
  const manager = league.managerOfMonth || {};
  const player = league.playerOfMonth || {};
  const headline = normalizeCard(league.latestHeadline);
  // El periódico puede ir por detrás de la clasificación: indicamos de qué
  // jornada es el titular para que no parezca de la última.
  const latestIssue = ((state.data.newsBySeason || {})[currentSeason()] || state.data.news || [])
    .reduce((max, issue) => Math.max(max, roundNumber(issue.date)), 0);
  const topClauses = league.topClauses || [];
  const topTransfers = league.topTransfers || [];

  app.innerHTML = `
  ${fallbackBanner()}
  <div class="grid home-grid">

    <section class="card standings-card">
      <div class="card-header">
        <div>
          <h2>${isPool ? "Clasificación de la porra" : "Clasificación de la liga"}</h2>
          <p class="card-sub">${escapeHtml(seasonLabel)}${league.lastRound ? ` · tras la J${league.lastRound}` : ""}</p>
        </div>

        <div class="segmented" role="group" aria-label="Tipo de clasificación">
          <button type="button" class="${!isPool ? "active" : ""}" data-standings-tab="league" data-focus="tab-league" aria-pressed="${!isPool}">Liga</button>
          <button type="button" class="${isPool ? "active" : ""}" data-standings-tab="pool" data-focus="tab-pool" aria-pressed="${isPool}">Porra</button>
        </div>
      </div>

      ${renderStandingsTable(standings, isPool ? "Aciertos" : "Puntos")}
    </section>

    <div class="side-column">

      <aside class="card pad spotlight">
        <div class="label-row">
          <p class="label">Manager de la jornada</p>
          <span class="chip">${escapeHtml(roundLabel)}</span>
        </div>
        <div class="spotlight-person">
          <div class="portrait">
            ${managerAvatar(manager.name, 90)}
          </div>
          <div>
            <h2>${escapeHtml(manager.name || "—")}</h2>
            <p class="muted">${escapeHtml(manager.subtitle || "Forma destacada")}</p>
          </div>
        </div>
        <p>${escapeHtml(manager.description || "")}</p>
      </aside>

      <article class="card pad metric success">
        <div class="label-row">
          <p class="label">Jugador de la jornada</p>
          <span class="chip">${escapeHtml(roundLabel)}</span>
        </div>
        <div class="person-row">
          ${playerAvatar(player.name, 52)}
          <div>
            <div class="value">${escapeHtml(player.name || "—")}</div>
            ${player.team || player.manager ? `<p class="muted small">${escapeHtml([player.team, player.manager].filter(Boolean).join(" · "))}</p>` : ""}
          </div>
        </div>
        <p class="muted small">${escapeHtml(player.description || "")}</p>
      </article>

      <section class="card hero-card">
        <h2>${escapeHtml(headline.title || "La liga calienta motores")}</h2>
        <p>${escapeHtml([headline.subtitle, ...headline.text].filter(Boolean).join(" "))}</p>
        <span class="chip">Drama de liga${latestIssue ? ` · J${latestIssue}` : ""}</span>
      </section>

    </div>

  </div>

  ${sectionHeading(seasonLabel, "KPIs de la liga")}

  <div class="grid metric-grid">
    ${kpiCard("💸 Fichaje más caro", playerAvatar(league.mostExpensiveBuy?.player, 48), league.mostExpensiveBuy?.player,
      [league.mostExpensiveBuy?.manager, formatMoney(league.mostExpensiveBuy?.amount)].filter(Boolean).join(" · "), "warning")}
    ${kpiCard("⚡ Clausulazo más caro", playerAvatar(league.mostExpensiveClause?.player, 48), league.mostExpensiveClause?.player,
      [league.mostExpensiveClause?.manager, formatMoney(league.mostExpensiveClause?.amount)].filter(Boolean).join(" · "), "warning")}
    ${kpiCard("🏹 Más clausulazos realizados", managerAvatar(league.mostClausesReceived?.manager, 48), league.mostClausesReceived?.manager,
      league.mostClausesReceived?.count ? `${league.mostClausesReceived.count} clausulazos` : "Sin datos", "success")}
    ${kpiCard("🛡️ Más clausulazos sufridos", managerAvatar(league.mostClausesGiven?.manager, 48), league.mostClausesGiven?.manager,
      league.mostClausesGiven?.count ? `${league.mostClausesGiven.count} sufridos` : "Sin datos", "")}
  </div>

  ${sectionHeading(seasonLabel, "Movimientos de la temporada")}

  <div class="grid two-col">

    <section class="card">
      <div class="card-header">
        <h3>⚡ Top ${topClauses.length || 5} clausulazos más caros</h3>
      </div>
      <div class="table">
        <div class="table-row table-head cols-clauses">
          <span>Jugador</span><span>De</span><span>A</span><span>Importe</span>
        </div>
        ${topClauses.map(row => `
          <div class="table-row cols-clauses">
            <div class="team-cell">
              ${playerAvatar(row.player, 32)}
              <strong>${escapeHtml(row.player || "—")}</strong>
            </div>
            <span class="muted">${escapeHtml(row.from || "—")}</span>
            <span>${escapeHtml(row.to || "—")}</span>
            <span class="data">${escapeHtml(formatMoney(row.amount) || "—")}</span>
          </div>
        `).join("") || emptyRow("Sin clausulazos esta temporada", "cols-clauses")}
      </div>
    </section>

    <section class="card">
      <div class="card-header">
        <h3>💸 Top ${topTransfers.length || 5} fichajes de mercado</h3>
      </div>
      <div class="table">
        <div class="table-row table-head cols-transfers">
          <span>Jugador</span><span>Manager</span><span>Importe</span>
        </div>
        ${topTransfers.map(row => `
          <div class="table-row cols-transfers">
            <div class="team-cell">
              ${playerAvatar(row.player, 38)}
              <strong>${escapeHtml(row.player || "—")}</strong>
            </div>
            <span class="muted">${escapeHtml(row.manager || "—")}</span>
            <span class="data">${escapeHtml(formatMoney(row.amount) || "—")}</span>
          </div>
        `).join("") || emptyRow("Sin fichajes esta temporada", "cols-transfers")}
      </div>
    </section>

  </div>
`;

  app.querySelectorAll("[data-standings-tab]").forEach(button => {
    button.addEventListener("click", () => {
      state.standingsTab = button.dataset.standingsTab;
      rerender(renderHome, button.dataset.focus);
    });
  });
}

function kpiCard(label, avatarHtml, value, meta, tone) {
  return `
    <article class="card pad metric ${tone}">
      <p class="label">${escapeHtml(label)}</p>
      <div class="person-row">
        ${avatarHtml}
        <div class="value">${escapeHtml(value || "—")}</div>
      </div>
      <p class="muted small">${escapeHtml(meta || "")}</p>
    </article>
  `;
}

// ── Estadísticas ─────────────────────────────────────────────────────────────

function renderStats() {
  const seasons = state.data.seasons || [];
  if (!state.selectedSeason || !seasons.includes(state.selectedSeason)) {
    state.selectedSeason = currentSeason();
  }
  const managers = (state.data.managersBySeason || {})[state.selectedSeason] || state.data.managers || [];
  const leader = managers.reduce((best, m) => (best && (best.position ?? 99) <= (m.position ?? 99) ? best : m), null);
  const selected = managers.find(manager => manager.name === state.selectedManager) || leader;
  if (!selected) {
    app.innerHTML = `${fallbackBanner()}<div class="card pad"><h2>No hay datos de managers todavía</h2></div>`;
    return;
  }
  state.selectedManager = selected.name;

  // seasonForm va indexado por jornada (posición i = jornada i+1) y trae
  // null en las jornadas que faltan en la BD.
  const form = selected.seasonForm || selected.form || [];
  const played = form.map((value, index) => ({ value, round: index + 1 })).filter(p => p.value !== null && p.value !== undefined);
  const last = played[played.length - 1] || null;
  const prev = played[played.length - 2] || null;
  let formDeltaBadge = "";
  if (last && prev && prev.value > 0) {
    const deltaPct = Math.round(((last.value - prev.value) / prev.value) * 100);
    const sign = deltaPct >= 0 ? "+" : "";
    formDeltaBadge = `<span class="delta-badge ${deltaPct >= 0 ? "positive" : "negative"}" title="Variación respecto a la J${prev.round} (${prev.value} pts)">${sign}${deltaPct}% vs J${prev.round}</span>`;
  }
  const chartForm = form.slice(0, TOTAL_JORNADAS);
  while (chartForm.length < TOTAL_JORNADAS) chartForm.push(undefined);
  const maxFormValue = Math.max(1, ...played.map(p => p.value));

  const market = selected.market || {};
  const marketTotal = (market.mercado ?? 0) + (market.clausulas ?? 0) + (market.acuerdos ?? 0);
  // Escala relativa al máximo de la temporada (antes era un 30 fijo y quien
  // pasaba de 30 compras salía con la barra llena igual que quien tenía 30).
  const marketMax = Math.max(1, ...managers.flatMap(m => [m.market?.mercado ?? 0, m.market?.clausulas ?? 0, m.market?.acuerdos ?? 0]));

  app.innerHTML = `
    ${fallbackBanner()}
    <div class="stats-fade">
    <div class="manager-picker" role="group" aria-label="Seleccionar manager">
      ${managers.map(manager => `
        <button
          type="button"
          class="manager-picker-item ${manager.name === selected.name ? "active" : ""}"
          data-manager="${escapeHtml(manager.name)}"
          data-focus="manager-${escapeHtml(manager.name)}"
          aria-pressed="${manager.name === selected.name}"
          title="${escapeHtml(manager.name)}"
        >
          <span class="avatar-ring">${managerAvatar(manager.name, 52, true)}</span>
          <span class="picker-name">${escapeHtml(manager.name)}</span>
        </button>
      `).join("")}
    </div>

    <div class="toolbar">
      <div class="person-row">
        ${managerAvatar(selected.name, 72)}
        <div>
          <h2 class="flush">${escapeHtml(selected.name)}</h2>
          <p class="muted small">${selected.position ? `#${escapeHtml(selected.position)} · ` : ""}${escapeHtml(selected.totalPoints ?? 0)} pts · Temporada ${escapeHtml(state.selectedSeason ?? "")}</p>
        </div>
      </div>
      ${seasonSelect("season-select")}
    </div>

    <div class="grid two-col">

      <article class="card pad metric">
        <p class="label">Rendimiento de la temporada</p>
        <div class="stat-list">
          ${miniStat("Posición", `#${selected.position ?? "—"}`, "accent-green")}
          ${miniStat("Puntos totales", selected.totalPoints)}
          ${miniStat("Media por jornada", formatNumber(selected.average))}
          ${miniStat("Desviación típica", formatNumber(selected.stdDev))}
          <div class="stat-divider"></div>
          ${miniStat("⚽ Goles", selected.goals, "small-value")}
          ${miniStat("🎯 Asistencias", selected.assists, "small-value")}
          ${miniStat("🟥 Tarjetas rojas", selected.redCards, "small-value accent-rose")}
        </div>
      </article>

      <article class="card pad">
        <p class="label">Jugadores clave</p>
        <div class="key-players">
          ${keyPlayer("🏆 Mejor de la temporada", selected.bestPlayerHistoric, "good")}
          ${keyPlayer("📉 Peor de la temporada", selected.worstPlayer, "bad")}
        </div>
      </article>

    </div>

    <div class="grid stats-grid">
      <section class="card pad span-7">
        <div class="chart-stat-header">
          <div>
            <p class="label flush">${last ? `Puntos en la J${last.round}` : "Rendimiento por jornada"}</p>
            <div class="chart-stat-value">
              <div class="value flush">${escapeHtml(last?.value ?? "—")}</div>
              ${formDeltaBadge}
            </div>
          </div>
          <span class="period-chip">${played.length}/${TOTAL_JORNADAS} jornadas</span>
        </div>
        <div class="chart" role="img" aria-label="Puntos por jornada de ${escapeHtml(selected.name)}: ${escapeHtml(played.map(p => `J${p.round} ${p.value}`).join(", "))}">
          ${chartForm.map((value, index) => {
            const round = index + 1;
            if (value === undefined) return `<div class="chart-col"><div class="chart-track" title="Jornada ${round}: sin jugar"></div></div>`;
            if (value === null) return `<div class="chart-col"><div class="chart-track missing" title="Jornada ${round}: sin datos"></div></div>`;
            return `
              <div class="chart-col">
                <div class="chart-track" title="Jornada ${round}: ${value} pts">
                  <span class="chart-bar" style="height:${Math.max(6, Math.round((Math.max(0, value) / maxFormValue) * 100))}%"></span>
                </div>
              </div>`;
          }).join("")}
        </div>
      </section>

      <section class="card pad span-5">
        <div class="chart-stat-header">
          <div>
            <p class="label flush">Mercado</p>
            <div class="chart-stat-value">
              <div class="value flush">${marketTotal}</div>
              <span class="muted small">compras totales</span>
            </div>
          </div>
          <span class="period-chip">Temporada</span>
        </div>
        <div class="bars">
          ${absoluteBarRow("Mercado libre", market.mercado ?? 0, marketMax)}
          ${absoluteBarRow("Cláusulas", market.clausulas ?? 0, marketMax)}
          ${absoluteBarRow("Acuerdos", market.acuerdos ?? 0, marketMax)}
        </div>
        ${selected.marketSpend ? `<p class="muted small market-spend">Gasto total: <strong>${escapeHtml(formatMoney(selected.marketSpend))}</strong></p>` : ""}
      </section>

    </div>
    </div>
  `;

  app.querySelectorAll(".manager-picker-item").forEach(button => {
    button.addEventListener("click", () => {
      state.selectedManager = button.dataset.manager;
      rerender(renderStats, button.dataset.focus);
    });
  });

  app.querySelector("#season-select")?.addEventListener("change", (event) => {
    state.selectedSeason = event.target.value;
    rerender(renderStats, null);
    app.querySelector("#season-select")?.focus({ preventScroll: true });
  });
}

function miniStat(label, value, extraClass = "") {
  return `
    <div class="mini-stat ${extraClass}">
      <p class="muted">${escapeHtml(label)}</p>
      <div class="value">${escapeHtml(value ?? "—")}</div>
    </div>
  `;
}

function keyPlayer(label, player, tone) {
  const meta = [player?.team, player?.position].filter(Boolean).join(" · ");
  return `
    <div class="key-player ${tone}">
      <div class="person-row">
        ${playerAvatar(player?.name, 52)}
        <div>
          <p class="key-player-label">${escapeHtml(label)}</p>
          <strong>${escapeHtml(player?.name || "—")}</strong>
          ${meta ? `<p class="muted small">${escapeHtml(meta)}</p>` : ""}
        </div>
      </div>
      <span class="key-player-points">${escapeHtml(player?.points ?? "—")} pts</span>
    </div>
  `;
}

function absoluteBarRow(label, value, max) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  return `
    <div class="bar-row">
      <div class="bar-meta"><span>${escapeHtml(label)}</span><strong>${value} ${value === 1 ? "compra" : "compras"}</strong></div>
      <div class="bar"><span style="width:${pct}%"></span></div>
    </div>
  `;
}

// ── Noticias ─────────────────────────────────────────────────────────────────

const CARD_TYPE_LABELS = {
  clasificacion: "Clasificación",
  rumor: "Rumor",
  fichaje: "Fichaje",
  jornada: "Jornada",
  noticia: "Noticia",
};

function renderNews() {
  const seasons = state.data.seasons || [];
  if (!state.selectedSeason || !seasons.includes(state.selectedSeason)) {
    state.selectedSeason = currentSeason();
  }
  const issuesSource = (state.data.newsBySeason || {})[state.selectedSeason] || state.data.news || [];
  // Timeline en orden ascendente (J1 → J38); por defecto se abre la última.
  const issues = [...issuesSource].sort((a, b) => roundNumber(a.date) - roundNumber(b.date));
  const selected = issues.find(issue => issue.date === state.selectedIssueDate) || issues[issues.length - 1];

  if (!selected) {
    app.innerHTML = `
      ${fallbackBanner()}
      <div class="toolbar">
        <h2 class="flush">Noticias</h2>
        ${seasonSelect("news-season-select")}
      </div>
      <div class="card pad"><h2>No hay noticias generadas todavía para ${escapeHtml(state.selectedSeason ?? "esta temporada")}</h2><p class="muted">Aparecerán aquí cuando se genere el periódico de la jornada.</p></div>
    `;
    bindNewsSeasonSelect();
    return;
  }
  state.selectedIssueDate = selected.date;
  const defaultCover = state.data.defaultCover || "";

  app.innerHTML = `
    ${fallbackBanner()}
    <div class="grid">
      <div class="card pad">
        <div class="toolbar flush-bottom">
          <div>
            <h2 class="flush">Jornadas</h2>
            <p class="card-sub">${issues.length} ${issues.length === 1 ? "edición" : "ediciones"} del periódico</p>
          </div>
          ${seasonSelect("news-season-select")}
        </div>
        <div class="jornada-carousel" role="group" aria-label="Ediciones del periódico">
          ${issues.map(issue => `
            <button
              type="button"
              class="jornada-card ${issue === selected ? "active" : ""}"
              data-issue="${escapeHtml(issue.date)}"
              data-focus="issue-${escapeHtml(issue.date)}"
              aria-pressed="${issue === selected}"
              aria-label="Jornada ${escapeHtml(roundNumber(issue.date))}: ${escapeHtml(issue.title)}"
              title="${escapeHtml(issue.title)}"
            >
              <img
                class="jornada-cover"
                src="${escapeHtml(issue.cover || defaultCover)}"
                ${defaultCover && issue.cover ? `data-fallback="${escapeHtml(defaultCover)}"` : `data-fallback="hide"`}
                alt=""
                width="96" height="128"
                loading="lazy" decoding="async"
              >
              <span class="jornada-dot"></span>
              <span class="jornada-label">${escapeHtml(issue.date)}</span>
            </button>
          `).join("")}
        </div>
      </div>

      <section>
        <article class="card hero-card">
          <h2>${escapeHtml(selected.title)}</h2>
          <p>${escapeHtml(selected.summary || selected.subtitle)}</p>
          <span class="chip">Jornada ${escapeHtml(roundNumber(selected.date))}</span>
        </article>

        ${renderStandingsAtIssue(selected)}

        <div class="news-grid">
          ${(selected.cards || []).map(raw => {
            const card = normalizeCard(raw);
            return `
              <article class="article-card">
                <h3>${escapeHtml(card.title || "Sin titular")}</h3>
                ${card.subtitle ? `<p><strong>${escapeHtml(card.subtitle)}</strong></p>` : ""}
                ${card.text.map(text => `<p>${escapeHtml(text)}</p>`).join("")}
                <span class="chip">${escapeHtml(cardTypeLabel(card.type))}</span>
              </article>
            `;
          }).join("")}
        </div>
      </section>
    </div>
  `;

  app.querySelectorAll(".jornada-card").forEach(button => {
    button.addEventListener("click", () => {
      state.selectedIssueDate = button.dataset.issue;
      rerender(renderNews, button.dataset.focus);
    });
  });
  bindNewsSeasonSelect();

  // Centrar la portada activa moviendo solo el carrusel: scrollIntoView
  // también desplazaba la página entera hasta el carrusel.
  const carousel = app.querySelector(".jornada-carousel");
  const active = app.querySelector(".jornada-card.active");
  if (carousel && active) {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    carousel.scrollTo({
      left: active.offsetLeft - (carousel.clientWidth - active.offsetWidth) / 2,
      behavior: reduceMotion ? "auto" : "smooth",
    });
  }
}

function bindNewsSeasonSelect() {
  app.querySelector("#news-season-select")?.addEventListener("change", (event) => {
    state.selectedSeason = event.target.value;
    state.selectedIssueDate = null; // abre la última jornada de esa temporada
    renderNews();
    app.querySelector("#news-season-select")?.focus({ preventScroll: true });
  });
}

function renderStandingsAtIssue(issue) {
  const rows = issue.standingsAtIssue;
  if (!rows || !rows.length) return "";

  return `
    <section class="card spaced">
      <div class="card-header">
        <h3>Clasificación en la ${escapeHtml(issue.date)}</h3>
      </div>
      ${renderStandingsTable(rows, "Puntos")}
    </section>
  `;
}

function renderStandingsTable(rows, pointsLabel = "Puntos", emptyText = "Sin clasificación disponible") {
  return `
    <div class="table">
      <div class="table-row table-head">
        <span>Rango</span><span>Manager</span><span>${escapeHtml(pointsLabel)}</span>
      </div>
      ${(rows || []).map(row => `
        <div class="table-row">
          <span class="rank">#${escapeHtml(row.rank ?? "?")}</span>
          <div class="team-cell">
            ${managerAvatar(row.manager, 40)}
            <strong>${escapeHtml(row.manager)}</strong>
          </div>
          <span class="data">${escapeHtml(row.points ?? 0)}</span>
        </div>
      `).join("") || emptyRow(emptyText)}
    </div>
  `;
}

function emptyRow(text, colsClass = "") {
  return `<div class="table-row ${colsClass}"><span class="muted empty-cell">${escapeHtml(text)}</span></div>`;
}

// ── Helpers de datos ─────────────────────────────────────────────────────────

// Las cards del periódico llegan en inglés (title/subtitle/text) desde
// regenerate_app_data.py; se aceptan también las claves originales en
// español del periódico por si algún JSON antiguo las trae. Antes la home
// leía solo las españolas y "Drama de liga" salía siempre vacío.
function normalizeCard(card) {
  const c = card || {};
  const text = c.text ?? c.texto ?? [];
  return {
    type: c.type ?? c.tipo ?? "",
    title: c.title ?? c.titulo ?? "",
    subtitle: c.subtitle ?? c.subtitulo ?? "",
    text: Array.isArray(text) ? text : [text].filter(Boolean),
  };
}

function cardTypeLabel(type) {
  if (!type) return "Noticia";
  return CARD_TYPE_LABELS[type.toLowerCase()] || type;
}

function roundNumber(label) {
  return parseInt(String(label).match(/\d+/)?.[0] ?? "0", 10);
}

function formatMoney(amount) {
  if (amount === null || amount === undefined || amount === "" || Number.isNaN(Number(amount))) return "";
  return `${Number(amount).toLocaleString("es-ES", { maximumFractionDigits: 1 })} M€`;
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("es-ES", { maximumFractionDigits: 1 });
}

// ── Avatares ─────────────────────────────────────────────────────────────────

function initials(name = "") {
  return String(name ?? "")
    .replace(/[^\p{L}\p{N}\s]/gu, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0])
    .join("")
    .toUpperCase() || "SL";
}

const normalizeName = s => String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/\./g, "").trim();

// Índice de fotos construido una vez (antes cada avatar recorría y
// normalizaba los ~560 nombres del mapa).
function buildPlayerIndex(map) {
  const exact = new Map();
  const bySurname = new Map();
  for (const [name, url] of Object.entries(map)) {
    const norm = normalizeName(name);
    exact.set(norm, url);
    const parts = norm.split(/\s+/);
    const surname = parts[parts.length - 1];
    if (!bySurname.has(surname)) bySurname.set(surname, []);
    bySurname.get(surname).push({ parts, url });
  }
  return { map, exact, bySurname };
}

// Busca la foto de un jugador. El apellido solo vale si no es ambiguo: antes
// se quedaba con el primer "García" del mapa aunque hubiera varios, y dos
// jugadores distintos acababan con la misma foto.
function findPlayerPhoto(name) {
  if (!name || !playerIndex) return null;
  if (playerIndex.map[name]) return playerIndex.map[name];
  const norm = normalizeName(name);
  if (playerIndex.exact.has(norm)) return playerIndex.exact.get(norm);

  const parts = norm.split(/\s+/);
  const candidates = playerIndex.bySurname.get(parts[parts.length - 1]) || [];
  if (candidates.length === 1) return candidates[0].url;
  if (candidates.length > 1 && parts.length > 1) {
    // Desempatar por la inicial del nombre: "Kylian Mbappé" ↔ "K. Mbappé".
    const initial = parts[0][0];
    const sameInitial = candidates.filter(c => c.parts.length > 1 && c.parts[0][0] === initial);
    if (sameInitial.length === 1) return sameInitial[0].url;
  }
  return null;
}

function playerAvatar(name, size = 36) {
  const url = findPlayerPhoto(name);
  const fallback = (hidden) => `<span class="player-initials" style="${hidden ? "display:none;" : ""}width:${size}px;height:${size}px;font-size:${Math.round(size * 0.35)}px">${escapeHtml(initials(name))}</span>`;
  if (!url) return fallback(false);
  return `<img class="player-photo" src="${escapeHtml(url)}" alt="" width="${size}" height="${size}" loading="lazy" decoding="async" data-fallback="next" style="width:${size}px;height:${size}px">${fallback(true)}`;
}

function managerAvatar(name, size = 60, decorative = false) {
  const fileName = String(name ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9áéíóúüñ\s]/gi, "")
    .trim()
    .replace(/\s+/g, "_");

  return `<img class="manager-photo" src="/assets/web/${encodeURIComponent(fileName || "Default")}.png" alt="${decorative ? "" : escapeHtml(name ?? "")}" width="${size}" height="${size}" loading="lazy" decoding="async" data-fallback="next" style="width:${size}px;height:${size}px"><span class="avatar" style="display:none;width:${size}px;height:${size}px;flex-basis:${size}px">${escapeHtml(initials(name))}</span>`;
}

function escapeHtml(value = "") {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
