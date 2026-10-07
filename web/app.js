const state = {
  data: null,
  view: "home",
  selectedManager: null,
  // Cada vista recuerda su propia temporada: antes cambiar la temporada en
  // Managers arrastraba a Periódico sin avisar.
  statsSeason: null,
  newsSeason: null,
  // Se guarda la jornada ("J7"), no su índice.
  selectedIssueDate: null,
  standingsTab: "league",
  usingFallback: false,
  // Para animar el titular solo cuando cambia la edición, no en cada repintado.
  lastRevealedIssue: null,
};

const VIEWS = { home: "Portada", stats: "Managers", news: "Periódico" };
const TOTAL_JORNADAS = 38;
const STALE_AFTER_DAYS = 3;
const SOTANO_SIZE = 2;            // últimos puestos que forman "el sótano"
const FIRST_HALF_LAST_ROUND = 19; // primera vuelta: J1–J19

const app = document.querySelector("#app");
const pageTitle = document.querySelector("#page-title");
const navItems = document.querySelectorAll("[data-view]");
const freshnessPill = document.querySelector("#freshness");
const lightbox = document.querySelector("#lightbox");

const fallbackData = {
  league: {
    name: "Sotano League",
    season: "",
    standings: [],
    poolStandings: [],
    managerOfMonth: { name: "Sin datos", description: "Genera datos para alimentar la portada." },
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

// ── Iconos (SVG propios, trazo 1.75 sobre 24×24) ─────────────────────────────

const ICON_PATHS = {
  up: '<path d="M12 5l7 9H5z" fill="currentColor" stroke="none"/>',
  down: '<path d="M12 19l7-9H5z" fill="currentColor" stroke="none"/>',
  same: '<path d="M6 12h12"/>',
  stairs: '<path d="M3 5h5v5h5v5h5v5h3"/>',
  zoom: '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2M11 8v6M8 11h6"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  money: '<rect x="3" y="6" width="18" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M7 9.5v5M17 9.5v5"/>',
  bolt: '<path d="M13 3L5 13.5h6L10 21l9-11h-6z"/>',
  target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="0.8" fill="currentColor"/>',
  shield: '<path d="M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6z"/>',
  person: '<circle cx="12" cy="9" r="3.6"/><path d="M5 20c1.2-3.6 3.9-5.4 7-5.4s5.8 1.8 7 5.4"/>',
};

function icon(name, size = 18) {
  return `<svg class="icon icon-${name}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON_PATHS[name]}</svg>`;
}

let playerIndex = null;

installImageFallbacks();
init();

async function init() {
  state.data = await loadData();
  playerIndex = buildPlayerIndex(state.data.playersMap || {});
  state.statsSeason = state.newsSeason = currentSeason();
  state.view = VIEWS[location.hash.slice(1)] ? location.hash.slice(1) : "home";
  bindEvents();
  renderFreshness();
  render();
}

async function loadData() {
  try {
    // nginx sirve app-data.json con Cache-Control: no-cache + ETag: el
    // navegador revalida y solo lo vuelve a descargar si ha cambiado.
    const response = await fetch("/web/data/app-data.json");
    if (!response.ok) throw new Error(`app-data.json respondió ${response.status}`);
    return await response.json();
  } catch (error) {
    console.warn("No se pudieron cargar los datos de la liga, usando fallback:", error);
    state.usingFallback = true;
    return fallbackData;
  }
}

// La temporada en curso: la de config.yaml al generar, o la última de
// `seasons` (vienen en orden ascendente).
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
  lightbox?.addEventListener("click", (event) => {
    // Clic en el fondo (fuera de la imagen) o en "Cerrar" cierra el visor.
    if (event.target === lightbox || event.target.closest("[data-close]")) lightbox.close();
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
//   data-fallback="next"  → ocultarla y mostrar el elemento siguiente
//   data-fallback="hide"  → ocultarla
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

// Tras repintar con innerHTML el foco se perdía; lo devolvemos al control
// con la misma clave data-focus.
function rerender(renderFn, focusKey) {
  renderFn();
  if (!focusKey) return;
  app.querySelector(`[data-focus="${CSS.escape(focusKey)}"]`)?.focus({ preventScroll: true });
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
  freshnessPill.textContent = stale ? `Datos del ${label}` : `Actualizado el ${label}`;
  freshnessPill.title = `Datos generados el ${generated.toLocaleString("es-ES")}. Se actualizan cada mañana.`;
}

function fallbackBanner() {
  if (!state.usingFallback) return "";
  return `<div class="fallback-banner" role="status">No se pudieron cargar los datos de la liga. Recarga la página en un rato; mientras tanto ves datos de respaldo.</div>`;
}

function seasonSelect(id, value) {
  const seasons = state.data.seasons || [];
  if (seasons.length < 2) return "";
  return `
    <label class="season-select">
      <span class="visually-hidden">Temporada</span>
      <select class="select" id="${id}">
        ${seasons.map(season => `
          <option value="${escapeHtml(season)}" ${season === value ? "selected" : ""}>Temporada ${escapeHtml(season)}</option>
        `).join("")}
      </select>
    </label>
  `;
}

function issuesFor(season) {
  const source = (state.data.newsBySeason || {})[season] || (season === currentSeason() ? state.data.news : []) || [];
  return [...source].sort((a, b) => roundNumber(a.date) - roundNumber(b.date));
}

// ── Portada ──────────────────────────────────────────────────────────────────

function renderHome() {
  const { league } = state.data;
  const season = currentSeason();
  const isPool = state.standingsTab === "pool";
  const standings = (isPool ? league.poolStandings : league.standings) || [];
  const round = league.lastRound;
  const manager = league.managerOfMonth || {};
  const player = league.playerOfMonth || {};
  const issues = issuesFor(season);
  const latest = issues[issues.length - 1];
  const headline = normalizeCard(league.latestHeadline);

  app.innerHTML = `
  ${fallbackBanner()}

  <section class="front" aria-labelledby="front-title">
    ${latest ? `
      <button type="button" class="front-cover" data-open-issue="${escapeHtml(latest.date)}" aria-label="Abrir la edición de la jornada ${roundNumber(latest.date)} en el periódico">
        <img src="${escapeHtml(latest.coverLarge || latest.cover || state.data.defaultCover || "")}" alt="" width="450" height="562" decoding="async" data-fallback="hide">
      </button>` : ""}
    <div class="front-body">
      <div class="front-masthead">
        <img src="/assets/web/masthead.webp" alt="Bajando al Sótano" width="140" height="125">
        ${latest ? `<span class="edition">Edición de la jornada ${roundNumber(latest.date)}</span>` : ""}
      </div>
      <h2 id="front-title" class="headline">${escapeHtml(headline.title || "La liga calienta motores")}</h2>
      ${headline.subtitle ? `<p class="front-deck">${escapeHtml(headline.subtitle)}</p>` : ""}
      ${latest ? `<button type="button" class="link-button" data-open-issue="${escapeHtml(latest.date)}">Leer el periódico ${icon("arrow", 16)}</button>` : ""}
    </div>
    <div class="round-bar">
      <p class="round-bar-title">${round ? `Jornada ${round}` : "Última jornada"}</p>
      <div class="round-facts">
        <div class="fact">
          ${managerAvatar(manager.name, 64)}
          <div>
            <span class="fact-label">Manager de la jornada</span>
            <strong class="fact-name">${escapeHtml(manager.name || "—")}</strong>
            <span class="fact-meta">${escapeHtml(manager.description || "")}</span>
          </div>
        </div>
        <div class="fact">
          ${playerAvatar(player.name, 64)}
          <div>
            <span class="fact-label">Jugador de la jornada</span>
            <strong class="fact-name">${escapeHtml(player.name || "—")}</strong>
            <span class="fact-meta">${escapeHtml([player.points != null ? `${player.points} pts` : "", player.team, player.manager].filter(Boolean).join(" · "))}</span>
          </div>
        </div>
      </div>
    </div>
  </section>

  <div class="home-columns">
    <section class="slab standings" aria-labelledby="standings-title">
      <header class="slab-header">
        <div>
          <h2 id="standings-title">${isPool ? "Clasificación de la porra" : "Clasificación"}</h2>
          <p class="slab-sub">${isPool ? "Aciertos en la quiniela de cada jornada" : "Puntos del fantasy acumulados"}${league.season ? ` · ${escapeHtml(league.season)}` : ""}</p>
        </div>
        <div class="segmented" role="group" aria-label="Tipo de clasificación">
          <button type="button" class="${!isPool ? "active" : ""}" data-standings-tab="league" data-focus="tab-league" aria-pressed="${!isPool}">Liga</button>
          <button type="button" class="${isPool ? "active" : ""}" data-standings-tab="pool" data-focus="tab-pool" aria-pressed="${isPool}">Porra</button>
        </div>
      </header>
      ${renderStandingsTable(standings, { unit: isPool ? "aciertos" : "pts", sotano: !isPool, movement: true })}
    </section>

    <aside class="figures" aria-labelledby="figures-title">
      <h2 id="figures-title" class="section-title">En cifras</h2>
      <ul class="figure-list">
        ${figure("money", "Fichaje más caro", playerAvatar(league.mostExpensiveBuy?.player, 44), league.mostExpensiveBuy?.player,
          league.mostExpensiveBuy?.manager, formatMoney(league.mostExpensiveBuy?.amount))}
        ${figure("bolt", "Clausulazo más caro", playerAvatar(league.mostExpensiveClause?.player, 44), league.mostExpensiveClause?.player,
          league.mostExpensiveClause?.manager, formatMoney(league.mostExpensiveClause?.amount))}
        ${figure("target", "Más clausulazos dados", managerAvatar(league.mostClausesReceived?.manager, 44), league.mostClausesReceived?.manager,
          "", league.mostClausesReceived?.count ? `${league.mostClausesReceived.count}` : "")}
        ${figure("shield", "Más clausulazos sufridos", managerAvatar(league.mostClausesGiven?.manager, 44), league.mostClausesGiven?.manager,
          "", league.mostClausesGiven?.count ? `${league.mostClausesGiven.count}` : "")}
      </ul>
    </aside>
  </div>

  <section class="moves" aria-labelledby="moves-title">
    <h2 id="moves-title" class="section-title">Movimientos de la temporada</h2>
    <div class="moves-columns">
      ${movesList("Clausulazos más caros", (league.topClauses || []).map(row => ({
        player: row.player, meta: `${row.from || "?"} → ${row.to || "?"}`, amount: row.amount,
      })), "Nadie ha pagado una cláusula todavía.")}
      ${movesList("Fichajes de mercado más caros", (league.topTransfers || []).map(row => ({
        player: row.player, meta: row.manager, amount: row.amount,
      })), "Todavía no hay fichajes de mercado.")}
    </div>
  </section>
`;

  app.querySelectorAll("[data-standings-tab]").forEach(button => {
    button.addEventListener("click", () => {
      state.standingsTab = button.dataset.standingsTab;
      rerender(renderHome, button.dataset.focus);
    });
  });
  app.querySelectorAll("[data-open-issue]").forEach(button => {
    button.addEventListener("click", () => {
      state.newsSeason = season;
      state.selectedIssueDate = button.dataset.openIssue;
      setView("news");
    });
  });
}

function figure(iconName, label, avatarHtml, name, meta, value) {
  return `
    <li class="figure">
      <span class="figure-label">${icon(iconName, 16)} ${escapeHtml(label)}</span>
      <div class="figure-row">
        ${avatarHtml}
        <div class="figure-text">
          <strong>${escapeHtml(name || "—")}</strong>
          ${meta ? `<span>${escapeHtml(meta)}</span>` : ""}
        </div>
        ${value ? `<span class="figure-value">${escapeHtml(value)}</span>` : ""}
      </div>
    </li>
  `;
}

function movesList(title, rows, emptyText) {
  return `
    <div class="moves-list">
      <h3>${escapeHtml(title)}</h3>
      ${rows.length ? `<ol>
        ${rows.map((row, index) => `
          <li class="move">
            <span class="move-rank">${index + 1}</span>
            ${playerAvatar(row.player, 40)}
            <div class="move-text">
              <strong>${escapeHtml(row.player || "—")}</strong>
              <span>${escapeHtml(row.meta || "")}</span>
            </div>
            <span class="move-amount">${escapeHtml(formatMoney(row.amount) || "—")}</span>
          </li>
        `).join("")}
      </ol>` : `<p class="empty">${escapeHtml(emptyText)}</p>`}
    </div>
  `;
}

function renderStandingsTable(rows, { unit = "pts", sotano = false, movement = false } = {}) {
  if (!rows || !rows.length) return `<p class="empty on-ink">Todavía no hay clasificación para esta temporada.</p>`;
  const leaderPoints = rows[0]?.points ?? 0;
  const sotanoFrom = sotano && rows.length >= 6 ? rows.length - SOTANO_SIZE : Infinity;
  return `
    <ol class="standings-list">
      ${rows.map((row, index) => {
        const gap = leaderPoints - (row.points ?? 0);
        return `
          ${index === sotanoFrom ? `<li class="sotano-divider" aria-hidden="true">${icon("stairs", 18)} El sótano</li>` : ""}
          <li class="standing ${index >= sotanoFrom ? "in-sotano" : ""} ${index === 0 ? "leader" : ""}">
            <span class="standing-rank">${escapeHtml(row.rank ?? "?")}</span>
            ${movement ? movementBadge(row) : ""}
            ${managerAvatar(row.manager, 40)}
            <span class="standing-name">${escapeHtml(row.manager)}${index >= sotanoFrom ? '<span class="visually-hidden"> (en el sótano)</span>' : ""}</span>
            <span class="standing-gap">${index === 0 ? "Líder" : `−${gap}`}</span>
            <span class="standing-points">${escapeHtml(row.points ?? 0)}<small> ${escapeHtml(unit)}</small></span>
          </li>
        `;
      }).join("")}
    </ol>
  `;
}

function movementBadge(row) {
  if (row.prevRank == null) return `<span class="move-badge"></span>`;
  const diff = row.prevRank - row.rank;
  if (diff > 0) return `<span class="move-badge up" title="Sube ${diff} desde la actualización anterior">${icon("up", 14)}<span>${diff}</span><span class="visually-hidden"> puestos arriba</span></span>`;
  if (diff < 0) return `<span class="move-badge down" title="Baja ${-diff} desde la actualización anterior">${icon("down", 14)}<span>${-diff}</span><span class="visually-hidden"> puestos abajo</span></span>`;
  return `<span class="move-badge same" title="Mismo puesto que en la actualización anterior">${icon("same", 14)}<span class="visually-hidden">sin cambios</span></span>`;
}

// ── Managers ─────────────────────────────────────────────────────────────────

function renderStats() {
  const seasons = state.data.seasons || [];
  if (!seasons.includes(state.statsSeason)) state.statsSeason = currentSeason();
  const season = state.statsSeason;
  const managers = [...((state.data.managersBySeason || {})[season] || state.data.managers || [])]
    .sort((a, b) => (a.position ?? 99) - (b.position ?? 99));
  const selected = managers.find(manager => manager.name === state.selectedManager) || managers[0];
  if (!selected) {
    app.innerHTML = `${fallbackBanner()}<p class="empty">Todavía no hay datos de managers para esta temporada.</p>`;
    return;
  }
  state.selectedManager = selected.name;

  const form = selected.seasonForm || selected.form || [];
  const played = form.map((value, index) => ({ value, round: index + 1 })).filter(p => p.value !== null && p.value !== undefined);
  const last = played[played.length - 1] || null;
  const prev = played[played.length - 2] || null;
  const missing = form.filter(v => v === null).length;
  let delta = "";
  if (last && prev && prev.value > 0) {
    const pct = Math.round(((last.value - prev.value) / prev.value) * 100);
    delta = `<span class="delta ${pct >= 0 ? "up" : "down"}">${icon(pct >= 0 ? "up" : "down", 12)} ${pct >= 0 ? "+" : ""}${pct}% vs J${prev.round}</span>`;
  }

  const market = selected.market || {};
  const marketTotal = (market.mercado ?? 0) + (market.clausulas ?? 0) + (market.acuerdos ?? 0);
  const marketMax = Math.max(1, ...managers.flatMap(m => [m.market?.mercado ?? 0, m.market?.clausulas ?? 0, m.market?.acuerdos ?? 0]));

  app.innerHTML = `
    ${fallbackBanner()}
    <div class="picker-bar">
      <div class="manager-picker" role="group" aria-label="Elegir manager (ordenados por posición)">
        ${managers.map(manager => `
          <button
            type="button"
            class="picker-item ${manager.name === selected.name ? "active" : ""}"
            data-manager="${escapeHtml(manager.name)}"
            data-focus="manager-${escapeHtml(manager.name)}"
            aria-pressed="${manager.name === selected.name}"
          >
            <span class="picker-rank">${escapeHtml(manager.position ?? "")}</span>
            ${managerAvatar(manager.name, 48, true)}
            <span class="picker-name">${escapeHtml(manager.name)}</span>
          </button>
        `).join("")}
      </div>
      ${seasonSelect("season-select", season)}
    </div>

    <header class="manager-hero">
      ${managerAvatar(selected.name, 96)}
      <div>
        <h2 class="manager-name">${escapeHtml(selected.name)}</h2>
        <p class="manager-line">
          <span class="badge">${escapeHtml(selected.position ?? "—")}º</span>
          ${escapeHtml(selected.totalPoints ?? 0)} puntos · ${played.length} ${played.length === 1 ? "jornada" : "jornadas"} · Temporada ${escapeHtml(season ?? "")}
        </p>
      </div>
    </header>

    <div class="stats-columns">
      <section class="slab chart-slab" aria-labelledby="chart-title">
        <header class="slab-header">
          <div>
            <h2 id="chart-title">Puntos por jornada</h2>
            <p class="slab-sub">${last ? `J${last.round}: <strong>${last.value} pts</strong>` : "Sin jornadas todavía"} ${delta}</p>
          </div>
          <p class="legend"><span class="legend-bar"></span> ${escapeHtml(selected.name)} <span class="legend-line"></span> Media de la liga</p>
        </header>
        <div class="chart-host"></div>
        ${missing ? `<p class="slab-note">${missing === 1 ? "Una jornada no tiene datos" : `${missing} jornadas no tienen datos`} (recuadro discontinuo).</p>` : ""}
      </section>

      <section class="slab numbers" aria-labelledby="numbers-title">
        <h2 id="numbers-title" class="visually-hidden">Números de la temporada</h2>
        <dl class="number-grid">
          ${numberItem("Media por jornada", formatNumber(selected.average), "pts")}
          ${numberItem("Regularidad", selected.stdDev != null ? `±${formatNumber(selected.stdDev)}` : "—", "pts", "Cuánto varían sus puntos de una jornada a otra (desviación típica). Cuanto más bajo, más regular.")}
          ${numberItem("Goles", selected.goals)}
          ${numberItem("Asistencias", selected.assists)}
          ${numberItem("Rojas", selected.redCards, "", "", "warn")}
        </dl>
      </section>
    </div>

    <div class="stats-columns">
      <section class="key-players" aria-labelledby="players-title">
        <h2 id="players-title" class="section-title">Jugadores de la temporada</h2>
        ${keyPlayer("El mejor", selected.bestPlayerHistoric, "good")}
        ${keyPlayer("El peor", selected.worstPlayer, "bad")}
      </section>

      <section class="market" aria-labelledby="market-title">
        <h2 id="market-title" class="section-title">Mercado</h2>
        <p class="market-total"><strong>${marketTotal}</strong> compras${selected.marketSpend ? ` · ${escapeHtml(formatMoney(selected.marketSpend))} gastados` : ""}</p>
        <div class="bars">
          ${barRow("Mercado libre", market.mercado ?? 0, marketMax)}
          ${barRow("Cláusulas", market.clausulas ?? 0, marketMax)}
          ${barRow("Acuerdos", market.acuerdos ?? 0, marketMax)}
        </div>
      </section>
    </div>
  `;

  app.querySelectorAll(".picker-item").forEach(button => {
    button.addEventListener("click", () => {
      state.selectedManager = button.dataset.manager;
      rerender(renderStats, button.dataset.focus);
    });
  });
  app.querySelector("#season-select")?.addEventListener("change", (event) => {
    state.statsSeason = event.target.value;
    renderStats();
    app.querySelector("#season-select")?.focus({ preventScroll: true });
  });
  // El gráfico se dibuja tras maquetar, con el ancho real de su hueco, para
  // pintarlo a escala 1:1. Si no cabe, se ven las últimas jornadas.
  const host = app.querySelector(".chart-host");
  if (host) {
    host.innerHTML = renderFormChart(selected, managers, host.clientWidth);
    const chartScroll = host.querySelector(".chart-scroll");
    if (chartScroll) chartScroll.scrollLeft = chartScroll.scrollWidth;
  }
  // Mantener el manager activo a la vista dentro del selector desplazable (móvil).
  const picker = app.querySelector(".manager-picker");
  const active = picker?.querySelector(".active");
  if (picker && active && picker.scrollWidth > picker.clientWidth) {
    picker.scrollLeft = active.offsetLeft - (picker.clientWidth - active.offsetWidth) / 2;
  }
}

// Gráfico SVG: solo las jornadas jugadas (antes 38 pistas, casi todas
// vacías al principio de temporada), con la media de la liga como línea y
// el máximo/mínimo rotulados.
function renderFormChart(selected, managers, hostWidth) {
  const form = (selected.seasonForm || selected.form || []).slice(0, TOTAL_JORNADAS);
  const n = form.length;
  if (!n) return `<p class="empty on-ink">Sin jornadas jugadas todavía.</p>`;

  const average = form.map((_, i) => {
    const values = managers.map(m => (m.seasonForm || [])[i]).filter(v => v !== null && v !== undefined);
    return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  });
  const values = form.filter(v => v !== null && v !== undefined);
  const maxValue = Math.max(1, ...values, ...average.filter(v => v !== null));
  const minValue = Math.min(0, ...values);
  // Ancho real disponible: el SVG se pinta a escala 1:1 (antes un viewBox
  // pequeño se estiraba y con pocas jornadas salían barras y textos enormes).
  const padding = window.innerWidth <= 860 ? 32 : 44; // padding lateral de .chart-scroll
  const available = Math.max(260, (hostWidth || 600) - padding);
  const W = Math.round(Math.max(available, n * 26)), H = 220, top = 22, bottom = 26;
  const plotH = H - top - bottom;
  const step = W / n;
  const barW = Math.min(28, step * 0.56);
  const y = v => top + plotH * (1 - (v - minValue) / (maxValue - minValue || 1));
  const zeroY = y(0);
  const best = values.length ? Math.max(...values) : null;
  const worst = values.length ? Math.min(...values) : null;
  const labelEvery = n <= 12 ? 1 : 5;
  let bestDone = false, worstDone = false;

  const bars = form.map((v, i) => {
    const cx = step * i + step / 2;
    const round = i + 1;
    const xLabel = (round === 1 || round % labelEvery === 0 || round === n)
      ? `<text class="axis" x="${cx}" y="${H - 6}" text-anchor="middle">J${round}</text>` : "";
    if (v === null || v === undefined) {
      return `<rect class="bar-missing" x="${cx - barW / 2}" y="${top}" width="${barW}" height="${plotH}" rx="3"><title>Jornada ${round}: sin datos</title></rect>${xLabel}`;
    }
    const y1 = Math.min(y(v), zeroY), h = Math.max(2, Math.abs(zeroY - y(v)));
    let tag = "";
    if (v === best && !bestDone) { bestDone = true; tag = `<text class="peak" x="${cx}" y="${y1 - 6}" text-anchor="middle">${v}</text>`; }
    else if (v === worst && !worstDone && worst !== best) { worstDone = true; tag = `<text class="peak low" x="${cx}" y="${(v < 0 ? y1 + h + 14 : y1 - 6)}" text-anchor="middle">${v}</text>`; }
    return `<rect class="bar ${v < 0 ? "neg" : ""}" x="${cx - barW / 2}" y="${y1}" width="${barW}" height="${h}" rx="3"><title>Jornada ${round}: ${v} pts</title></rect>${tag}${xLabel}`;
  }).join("");

  const avgPoints = average.map((v, i) => v === null ? null : `${step * i + step / 2},${y(v).toFixed(1)}`).filter(Boolean).join(" ");
  const summary = form.map((v, i) => `J${i + 1}: ${v ?? "sin datos"}`).join(", ");

  return `
    <div class="chart-scroll">
      <svg class="form-chart" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Puntos por jornada de ${escapeHtml(selected.name)}. ${escapeHtml(summary)}">
        <line class="baseline" x1="0" x2="${W}" y1="${zeroY}" y2="${zeroY}"/>
        ${bars}
        ${avgPoints ? `<polyline class="avg-line" points="${avgPoints}"/>` : ""}
      </svg>
    </div>
  `;
}

function numberItem(label, value, unit = "", help = "", tone = "") {
  return `
    <div class="number ${tone}">
      <dt>${escapeHtml(label)}</dt>
      <dd><span class="number-value">${escapeHtml(value ?? "—")}</span>${unit ? ` <small>${escapeHtml(unit)}</small>` : ""}</dd>
      ${help ? `<dd class="number-help">${escapeHtml(help)}</dd>` : ""}
    </div>
  `;
}

function keyPlayer(label, player, tone) {
  const meta = [player?.team, player?.position].filter(Boolean).join(" · ");
  return `
    <div class="key-player ${tone}">
      ${playerAvatar(player?.name, 56)}
      <div class="key-player-text">
        <span class="key-player-label">${escapeHtml(label)}</span>
        <strong>${escapeHtml(player?.name || "—")}</strong>
        ${meta ? `<span>${escapeHtml(meta)}</span>` : ""}
      </div>
      <span class="key-player-points">${escapeHtml(player?.points ?? "—")}<small> pts</small></span>
    </div>
  `;
}

function barRow(label, value, max) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  return `
    <div class="bar-row">
      <div class="bar-meta"><span>${escapeHtml(label)}</span><strong>${value}</strong></div>
      <div class="bar-track"><span style="width:${pct}%"></span></div>
    </div>
  `;
}

// ── Periódico ────────────────────────────────────────────────────────────────

function cardSection(type) {
  const t = (type || "").toLowerCase();
  if (/fichaje|venta|cl[aá]usul|mercado|compra|traspaso/.test(t)) return "mercado";
  if (/rumor/.test(t)) return "rumor";
  return "jornada";
}

const SECTION_LABELS = { mercado: "Mercado", rumor: "Rumor", jornada: "Jornada" };

function renderNews() {
  const seasons = state.data.seasons || [];
  if (!seasons.includes(state.newsSeason)) state.newsSeason = currentSeason();
  const season = state.newsSeason;
  const issues = issuesFor(season);
  const selected = issues.find(issue => issue.date === state.selectedIssueDate) || issues[issues.length - 1];

  if (!selected) {
    app.innerHTML = `
      ${fallbackBanner()}
      <header class="paper-head">
        <img class="paper-masthead" src="/assets/web/masthead.webp" alt="Bajando al Sótano" width="160" height="143">
        ${seasonSelect("news-season-select", season)}
      </header>
      <p class="empty">Todavía no hay periódico para la temporada ${escapeHtml(season ?? "")}. Saldrá aquí en cuanto se publique la primera edición.</p>
    `;
    bindNewsSeasonSelect();
    return;
  }
  state.selectedIssueDate = selected.date;
  const reveal = state.lastRevealedIssue !== `${season}/${selected.date}`;
  state.lastRevealedIssue = `${season}/${selected.date}`;

  const cards = (selected.cards || []).map(normalizeCard);
  const SECTION_ORDER = { jornada: 0, mercado: 1, rumor: 2 };
  const stories = cards
    .filter((card, i) => !(i === 0 && card.type === "clasificacion"))
    .map((card, i) => ({ card, i }))
    .sort((a, b) => (SECTION_ORDER[cardSection(a.card.type)] - SECTION_ORDER[cardSection(b.card.type)]) || a.i - b.i)
    .map(({ card }) => card);
  const [lead, ...rest] = stories;
  const secondary = rest.slice(0, 4);
  const briefs = rest.slice(4);
  const defaultCover = state.data.defaultCover || "";
  const groups = [
    { label: "Primera vuelta", items: issues.filter(i => roundNumber(i.date) <= FIRST_HALF_LAST_ROUND) },
    { label: "Segunda vuelta", items: issues.filter(i => roundNumber(i.date) > FIRST_HALF_LAST_ROUND) },
  ].filter(g => g.items.length);

  app.innerHTML = `
    ${fallbackBanner()}
    <header class="paper-head">
      <img class="paper-masthead" src="/assets/web/masthead.webp" alt="Bajando al Sótano" width="160" height="143">
      <p class="paper-edition">Edición de la jornada ${roundNumber(selected.date)}<span>${issues.length} ${issues.length === 1 ? "edición" : "ediciones"} esta temporada</span></p>
      ${seasonSelect("news-season-select", season)}
    </header>

    <nav class="issue-strip" aria-label="Ediciones del periódico">
      ${groups.map(group => `
        <div class="issue-group">
          <span class="issue-group-label">${escapeHtml(group.label)}</span>
          <div class="issue-row">
            ${group.items.map(issue => `
              <button
                type="button"
                class="issue ${issue === selected ? "active" : ""}"
                data-issue="${escapeHtml(issue.date)}"
                data-focus="issue-${escapeHtml(issue.date)}"
                aria-pressed="${issue === selected}"
                aria-label="Jornada ${roundNumber(issue.date)}: ${escapeHtml(issue.title)}"
                title="${escapeHtml(issue.title)}"
              >
                <img src="${escapeHtml(issue.cover || defaultCover)}" ${defaultCover && issue.cover ? `data-fallback="${escapeHtml(defaultCover)}"` : `data-fallback="hide"`} alt="" width="72" height="90" loading="lazy" decoding="async">
                <span>J${roundNumber(issue.date)}</span>
              </button>
            `).join("")}
          </div>
        </div>
      `).join("")}
    </nav>

    <article class="paper-front">
      <button type="button" class="paper-cover" data-zoom aria-label="Ver la portada de la jornada ${roundNumber(selected.date)} a tamaño completo">
        <img src="${escapeHtml(selected.coverLarge || selected.cover || defaultCover)}" alt="" width="450" height="562" decoding="async" data-fallback="hide">
        <span class="zoom-hint">${icon("zoom", 18)} Ampliar</span>
      </button>
      <div class="paper-front-body">
        <h2 class="headline headline-xl ${reveal ? "reveal" : ""}">${escapeHtml(selected.title)}</h2>
        ${selected.subtitle ? `<p class="front-deck">${escapeHtml(selected.subtitle)}</p>` : ""}
        <p class="paper-summary">${escapeHtml(selected.summary || "")}</p>
        ${selected.standingsAtIssue?.length ? `
          <details class="issue-standings">
            <summary>Clasificación tras la jornada ${roundNumber(selected.date)}</summary>
            ${renderStandingsTable(selected.standingsAtIssue, { unit: "pts", sotano: true })}
          </details>` : ""}
      </div>
    </article>

    ${lead ? `
      <section class="stories" aria-label="Noticias de la edición">
        ${story(lead, "lead")}
        ${secondary.length ? `<div class="story-grid">${secondary.map(card => story(card, "secondary")).join("")}</div>` : ""}
        ${briefs.length ? `
          <div class="briefs">
            <h3 class="briefs-title">Breves</h3>
            <ul>${briefs.map(card => `
              <li>${sectionTag(card.type)}<strong>${escapeHtml(card.title || "Sin titular")}</strong>${card.subtitle ? ` <span>${escapeHtml(card.subtitle)}</span>` : ""}</li>
            `).join("")}</ul>
          </div>` : ""}
      </section>` : ""}
  `;

  app.querySelectorAll(".issue").forEach(button => {
    button.addEventListener("click", () => {
      state.selectedIssueDate = button.dataset.issue;
      rerender(renderNews, button.dataset.focus);
      // Si se ha cambiado de edición desde más abajo, subir hasta la portada nueva.
      const front = app.querySelector(".paper-front");
      if (front && front.getBoundingClientRect().top < 0) {
        const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        front.scrollIntoView({ block: "start", behavior: reduceMotion ? "auto" : "smooth" });
      }
    });
  });
  app.querySelector("[data-zoom]")?.addEventListener("click", () => openLightbox(selected));
  bindNewsSeasonSelect();

  // Centrar la edición activa moviendo solo la tira, no la página.
  const strip = app.querySelector(".issue-strip");
  const active = strip?.querySelector(".issue.active");
  if (strip && active) {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const left = active.getBoundingClientRect().left - strip.getBoundingClientRect().left + strip.scrollLeft;
    strip.scrollTo({ left: left - (strip.clientWidth - active.offsetWidth) / 2, behavior: reduceMotion ? "auto" : "smooth" });
  }
}

function story(card, size) {
  return `
    <article class="story story-${size} section-${cardSection(card.type)}">
      ${sectionTag(card.type)}
      <h3 class="headline">${escapeHtml(card.title || "Sin titular")}</h3>
      ${card.subtitle ? `<p class="story-deck">${escapeHtml(card.subtitle)}</p>` : ""}
      ${card.text.map(text => `<p>${escapeHtml(text)}</p>`).join("")}
    </article>
  `;
}

function sectionTag(type) {
  const section = cardSection(type);
  const label = type && type.toLowerCase() !== section ? prettyType(type) : SECTION_LABELS[section];
  return `<span class="tag tag-${section}">${escapeHtml(label)}</span>`;
}

function prettyType(type) {
  const t = String(type);
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function openLightbox(issue) {
  if (!lightbox) return;
  let img = lightbox.querySelector("img");
  if (!img) {
    img = document.createElement("img");
    img.width = 900;
    img.height = 1125;
    lightbox.append(img);
  }
  img.src = issue.coverLarge || issue.cover || "";
  img.alt = `Portada de Bajando al Sótano, jornada ${roundNumber(issue.date)}: ${issue.title}`;
  lightbox.showModal();
}

function bindNewsSeasonSelect() {
  app.querySelector("#news-season-select")?.addEventListener("change", (event) => {
    state.newsSeason = event.target.value;
    state.selectedIssueDate = null; // abre la última edición de esa temporada
    renderNews();
    app.querySelector("#news-season-select")?.focus({ preventScroll: true });
  });
}

// ── Helpers de datos ─────────────────────────────────────────────────────────

// Las cards llegan con claves en inglés (title/subtitle/text) desde
// regenerate_app_data.py; se aceptan también las originales en español.
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

const normalizeName = s => String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/\./g, "").trim();

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

// El apellido solo vale si no es ambiguo (dos "García" no comparten foto).
function findPlayerPhoto(name) {
  if (!name || !playerIndex) return null;
  if (playerIndex.map[name]) return playerIndex.map[name];
  const norm = normalizeName(name);
  if (playerIndex.exact.has(norm)) return playerIndex.exact.get(norm);
  const parts = norm.split(/\s+/);
  const candidates = playerIndex.bySurname.get(parts[parts.length - 1]) || [];
  if (candidates.length === 1) return candidates[0].url;
  if (candidates.length > 1 && parts.length > 1) {
    const initial = parts[0][0];
    const sameInitial = candidates.filter(c => c.parts.length > 1 && c.parts[0][0] === initial);
    if (sameInitial.length === 1) return sameInitial[0].url;
  }
  return null;
}

// Silueta neutra cuando no hay foto (las iniciales parecían una imagen rota).
function silhouette(size, round, hidden) {
  return `<span class="silhouette ${round ? "round" : ""}" style="${hidden ? "display:none;" : ""}width:${size}px;height:${size}px">${icon("person", Math.round(size * 0.6))}</span>`;
}

function playerAvatar(name, size = 36) {
  const url = findPlayerPhoto(name);
  if (!url) return silhouette(size, true, false);
  return `<img class="player-photo" src="${escapeHtml(url)}" alt="" width="${size}" height="${size}" loading="lazy" decoding="async" data-fallback="next" style="width:${size}px;height:${size}px">${silhouette(size, true, true)}`;
}

function managerAvatar(name, size = 60, decorative = false) {
  const fileName = String(name ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9áéíóúüñ\s]/gi, "")
    .trim()
    .replace(/\s+/g, "_");
  return `<img class="crest" src="/assets/web/${encodeURIComponent(fileName || "Default")}.png" alt="${decorative ? "" : escapeHtml(name ?? "")}" width="${size}" height="${size}" loading="lazy" decoding="async" data-fallback="next" style="width:${size}px;height:${size}px">${silhouette(size, false, true)}`;
}

function escapeHtml(value = "") {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
