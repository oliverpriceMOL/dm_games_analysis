/**
 * Published Puzzles page — sortable table of dated puzzles with
 * click-to-expand detail panels showing row breakdown, wrong-guess
 * distributions, timing curves, and failure correlations.
 */

import { COLORS, hsl, hsla, nearestInteraction, horizontalInteraction } from './charts.js';
import {
    DIM_COLORS, DIM_COLORS_A,
    BASE_COLORS, WRONG_KEYS, WRONG_LABELS, PRED_KEYS,
    baseColorForKey, outcomeForKey,
    initToggle, syncToggle,
    stripePattern, hollowPattern, fillForOutcome,
    createRadarChart,
    badge, stars, tierClass, dimBar,
    renderPhiMatrix,
} from './utils.js';
import { SOLVE_ORDER_BUCKETS, SOLVE_ORDER_COLORS, SOLVE_ORDER_LABELS } from './crosstabs.js';

/* ── State ──────────────────────────────────────────────────────── */

let puzzles = [];        // [{key, p, diff}] — sorted
let chartInstances = []; // table radar Chart.js instances
let detailChartInstances = []; // modal detail Chart.js instances
let expandedKey = null;  // currently expanded puzzle key
let showPercent = true;
let includeAbandons = true;
let sortCol = 'date';
let sortDir = 1;

/* ── Public API ─────────────────────────────────────────────────── */

export function render(explorerData, difficultyData) {
    const dated = explorerData.puzzles || {};
    const diffPuzzles = difficultyData.puzzles || {};
    const dims = difficultyData.dimensions || [];
    const dimLabels = difficultyData.dimension_labels || {};

    puzzles = Object.keys(dated).sort().map(key => ({
        key,
        p: dated[key],
        diff: diffPuzzles[key] || {},
        dims,
        dimLabels,
    }));

    buildTable();
}

/* ── Sortable table ─────────────────────────────────────────────── */

function sortPuzzles() {
    const cmp = (a, b) => {
        let av, bv;
        switch (sortCol) {
            case 'name':      return sortDir * a.p.name.localeCompare(b.p.name);
            case 'date':      return sortDir * a.key.localeCompare(b.key);
            case 'rating':    av = a.diff.rating || 0; bv = b.diff.rating || 0; break;
            case 'solve':     av = a.p.solve_rate; bv = b.p.solve_rate; break;
            case 'players':   av = a.p.players; bv = b.p.players; break;
            case 'time':      av = a.p.median_time; bv = b.p.median_time; break;
            default:          av = a.key; bv = b.key; return sortDir * av.localeCompare(bv);
        }
        return sortDir * ((av || 0) - (bv || 0));
    };
    puzzles.sort(cmp);
}

function arrow(col) {
    if (col !== sortCol) return '';
    return ` <span class="sort-arrow">${sortDir === 1 ? '▲' : '▼'}</span>`;
}

function buildTable() {
    destroyCharts();
    sortPuzzles();

    const container = document.getElementById('published-table-container');
    if (!container) return;

    const dims = puzzles[0]?.dims || [];
    const dimLabels = puzzles[0]?.dimLabels || {};
    const radarLabelsShort = dims.map(d =>
        (dimLabels[d] || d).split(' ').map(w => w[0].toUpperCase()).join('')
    );
    const legendParts = dims.map((d, i) =>
        `<strong>${radarLabelsShort[i]}</strong> = ${dimLabels[d] || d}`
    );

    let html = `<p class="radar-legend">${legendParts.join(' · ')}</p>`;
    html += `<table id="published-table"><thead><tr>`;
    html += `<th class="sortable-th" data-col="name">Puzzle${arrow('name')}</th>`;
    html += `<th class="sortable-th" data-col="date">Date${arrow('date')}</th>`;
    html += `<th class="sortable-th" data-col="rating">Difficulty${arrow('rating')}</th>`;
    html += `<th class="sortable-th" data-col="solve">Solve Rate${arrow('solve')}</th>`;
    html += `<th class="sortable-th" data-col="players">Players${arrow('players')}</th>`;
    html += `<th class="sortable-th" data-col="time">Median Time${arrow('time')}</th>`;
    html += `<th>Profile</th>`;
    html += `</tr></thead><tbody>`;

    for (let i = 0; i < puzzles.length; i++) {
        const { key, p, diff } = puzzles[i];
        const rating = diff.rating || 0;
        const isExpanded = key === expandedKey;
        html += `<tr class="catalogue-row ${tierClass(rating)}${isExpanded ? ' expanded' : ''}" data-key="${key}">`;
        html += `<td><strong>${p.name}</strong></td>`;
        html += `<td>${p.date || '—'}</td>`;
        html += `<td>${stars(rating)}</td>`;
        html += `<td>${badge((p.solve_rate * 100).toFixed(0) + '%')}</td>`;
        html += `<td>${p.players}</td>`;
        html += `<td>${p.median_time.toFixed(1)}s</td>`;
        html += `<td><div class="table-radar-wrap"><canvas id="pub-radar-${i}" width="140" height="140"></canvas></div></td>`;
        html += `</tr>`;
    }
    html += `</tbody></table>`;
    container.innerHTML = html;

    // Render mini radars
    for (let i = 0; i < puzzles.length; i++) {
        const { diff, dims: d, dimLabels: dl } = puzzles[i];
        if (diff.profile) {
            createRadarChart(`pub-radar-${i}`, d, dl, diff.profile, { shortLabels: true });
        }
    }

    // Sort click handler
    container.querySelectorAll('.sortable-th').forEach(th => {
        th.addEventListener('click', (e) => {
            e.stopPropagation();
            const col = th.dataset.col;
            if (col === sortCol) { sortDir *= -1; }
            else { sortCol = col; sortDir = 1; }
            buildTable();
        });
    });

    // Row click → open modal
    container.querySelectorAll('.catalogue-row').forEach(row => {
        row.addEventListener('click', () => {
            const key = row.dataset.key;
            expandedKey = key;
            renderDetail(key);
        });
    });
}

/* ── Detail panel ───────────────────────────────────────────────── */

function renderDetail(key) {
    destroyDetailCharts();
    const entry = puzzles.find(e => e.key === key);
    if (!entry) return;
    const { p, diff, dims, dimLabels } = entry;

    // Remove any existing modal
    const existing = document.querySelector('.puzzle-modal-overlay');
    if (existing) existing.remove();

    // Build modal
    const overlay = document.createElement('div');
    overlay.className = 'puzzle-modal-overlay';
    const modal = document.createElement('div');
    modal.className = 'puzzle-modal';

    let html = '<button class="puzzle-modal-close">&times;</button>';
    html += `<div style="display:flex;justify-content:space-between;align-items:center;">`;
    html += `<h3 style="margin:0;">${p.label}: ${p.name}</h3>`;
    html += `<span style="color:var(--muted);font-size:13px;">${p.wins}W / ${p.losses}L / ${p.incomplete}I · ${p.players} players</span>`;
    html += `</div>`;

    // ── Top row: radar + summary stats ──
    html += `<div style="display:flex;gap:24px;margin-top:16px;flex-wrap:wrap;">`;
    html += `<div style="min-width:280px;"><canvas id="detail-radar" width="280" height="280"></canvas></div>`;
    html += `<div style="flex:1;min-width:200px;">`;
    html += `<div class="stats-grid" style="margin-bottom:12px;">`;
    html += `<div class="stat-card"><div class="value">${(p.solve_rate * 100).toFixed(1)}%</div><div class="label">Solve Rate</div></div>`;
    html += `<div class="stat-card"><div class="value">${p.median_time.toFixed(1)}s</div><div class="label">Median Time</div></div>`;
    html += `<div class="stat-card"><div class="value">${p.mean_lives_at_win != null ? p.mean_lives_at_win.toFixed(1) : '—'}</div><div class="label">Mean Lives at Win</div></div>`;
    html += `<div class="stat-card"><div class="value">${stars(diff.rating || 0)}</div><div class="label">Difficulty Rating</div></div>`;
    html += `</div>`;
    html += `</div></div>`;

    // ── Row breakdown table ──
    html += `<h4 style="margin-top:20px;">Row Breakdown</h4>`;
    html += `<div style="overflow-x:auto;"><table><thead><tr>`;
    html += `<th>Row</th><th>Category</th><th>Manipulation</th><th>Abstraction</th>`;
    html += `<th>Knowledge</th><th>Domain</th><th>Impostor</th><th>1st Try</th>`;
    html += `<th>Avg Wrong</th><th>Top Wrong Answers</th>`;
    html += `</tr></thead><tbody>`;
    for (let rp = 0; rp < 4; rp++) {
        const r = p.rows[String(rp)];
        if (!r) continue;
        const topWrong = (r.top_wrong || []).slice(0, 3)
            .map(tw => `${tw[0]} (${tw[1]})`).join(', ') || '—';
        html += `<tr>`;
        html += `<td>${rp}</td><td>${r.category || '—'}</td>`;
        html += `<td>${r.manipulation}</td><td>${r.abstraction}</td>`;
        html += `<td>${r.knowledge}</td><td>${r.knowledgeDomain || '—'}</td>`;
        html += `<td>${r.impostor_word || '—'}</td>`;
        html += `<td>${badge((r.first_try_pct * 100).toFixed(0) + '%')}</td>`;
        html += `<td>${r.avg_wrong.toFixed(2)}</td>`;
        html += `<td style="font-size:12px;">${topWrong}</td>`;
        html += `</tr>`;
    }
    // Relink row
    const rl = p.relink;
    if (rl) {
        html += `<tr style="background:#f8f9fa;">`;
        html += `<td><em>Relink</em></td><td colspan="5">${rl.answer || '—'}</td>`;
        html += `<td>—</td>`;
        html += `<td>${badge((rl.first_try_pct * 100).toFixed(0) + '%')}</td>`;
        html += `<td>${rl.avg_attempts.toFixed(2)}</td><td>—</td>`;
        html += `</tr>`;
    }
    html += `</tbody></table></div>`;

    // ── Wrong-guess distribution ──
    html += `<div style="display:flex;align-items:center;gap:12px;margin-top:20px;flex-wrap:wrap;">`;
    html += `<h4 style="margin:0;">Wrong-Guess Distribution by Row</h4>`;
    html += `<div class="toggle-group" id="pub-wd-toggle">`;
    html += `<button class="toggle-btn${showPercent ? ' active' : ''}" data-mode="pct">%</button>`;
    html += `<button class="toggle-btn${!showPercent ? ' active' : ''}" data-mode="raw">Raw</button>`;
    html += `</div>`;
    html += `<div class="toggle-group" id="pub-ab-toggle">`;
    html += `<button class="toggle-btn${includeAbandons ? ' active' : ''}" data-mode="all">All players</button>`;
    html += `<button class="toggle-btn${!includeAbandons ? ' active' : ''}" data-mode="completed">Completed only</button>`;
    html += `</div>`;
    html += `</div>`;
    html += legendHtml();
    html += `<div class="chart-container" style="height:280px;margin-top:8px;"><canvas id="detail-wd"></canvas></div>`;

    // ── Solve-order distribution by row ──
    html += `<h4 style="margin-top:20px;">Solve Order by Row</h4>`;
    html += `<p style="color:var(--muted);font-size:13px;">For each row, the position at which players resolved it during the puzzle (1st / 2nd / 3rd / 4th of the four imposters rows). The Relink phase is always position 5 (since it follows all four imposters) or 'never' if the player lost or abandoned. Each bar is a 100% stack across all engaged players.</p>`;
    html += `<div class="chart-container" style="height:280px;"><canvas id="detail-so"></canvas></div>`;

    // ── Ever-solved binary by row ──
    html += `<h4 style="margin-top:20px;">Ever Solved by Row</h4>`;
    html += `<p style="color:var(--muted);font-size:13px;">Share of engaged players who eventually resolved each row (regardless of how many wrong guesses they took). The Relink bar is the share who completed the puzzle.</p>`;
    html += `<div class="chart-container" style="height:240px;"><canvas id="detail-ever"></canvas></div>`;

    // ── Total mistakes distribution ──
    html += `<h4 style="margin-top:20px;">Total Mistakes per Player</h4>`;
    const n = includeAbandons ? p.players : p.wins + p.losses;
    html += `<p style="color:var(--muted);font-size:13px;">n = ${n}</p>`;
    html += `<div class="chart-container" style="height:220px;"><canvas id="detail-md"></canvas></div>`;

    // ── Timing & Error curves ──
    if (p.timing) {
        const tm = p.timing;
        html += `<h4 style="margin-top:20px;">Timing &amp; Error Curves</h4>`;
        html += `<p style="color:var(--muted);font-size:13px;">Median time (left axis) and mean wrong guesses (right axis) at each solve position. CoM &lt; 1.5 = front-loaded.</p>`;
        html += `<div class="chart-container" style="height:260px;"><canvas id="detail-curve"></canvas></div>`;
        html += `<p style="font-size:12px;color:var(--muted);text-align:center;">`;
        html += `Timing CoM: <strong>${tm.timing_com != null ? tm.timing_com.toFixed(3) : '—'}</strong> · `;
        html += `Error CoM: <strong>${tm.error_com != null ? tm.error_com.toFixed(3) : '—'}</strong></p>`;
    }

    // ── Failure correlations ──
    const fc = p.failure_correlations;
    if (fc && Object.keys(fc.phi_matrix).length > 0) {
        html += `<h4 style="margin-top:20px;">Failure Correlations</h4>`;
        html += `<p style="color:var(--muted);font-size:13px;">Phi coefficient (&phi;) between row pairs — positive = correlated failures.</p>`;
        html += renderPhiMatrix(fc);
    }

    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Close handlers
    const closeModal = () => {
        destroyDetailCharts();
        overlay.remove();
        expandedKey = null;
    };
    modal.querySelector('.puzzle-modal-close').addEventListener('click', closeModal);
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeModal();
    });
    document.addEventListener('keydown', function onEsc(e) {
        if (e.key === 'Escape') { closeModal(); document.removeEventListener('keydown', onEsc); }
    });

    // ── Render charts ──
    if (diff.profile) {
        createRadarChart('detail-radar', dims, dimLabels, diff.profile, { large: true, showValues: true });
    }
    renderWrongDistChart('detail-wd', p);
    renderSolveOrderChart('detail-so', p);
    renderEverSolvedChart('detail-ever', p);
    renderMistakeDistChart('detail-md', p);
    if (p.timing) {
        renderDualCurveChart('detail-curve', p);
    }

    // ── Toggle handlers ──
    initToggle('pub-wd-toggle', (mode) => {
        showPercent = mode === 'pct';
        rebuildDetailCharts(p);
    });
    initToggle('pub-ab-toggle', (mode) => {
        includeAbandons = mode === 'all';
        rebuildDetailCharts(p);
    });
}

/* ── Legend for wrong-dist fill styles ─────────────────────────── */

function legendHtml() {
    let h = '<div style="display:flex;gap:16px;margin-top:8px;font-size:12px;color:var(--muted);flex-wrap:wrap;">';
    const sampleC = BASE_COLORS['1'];
    h += `<span><span style="display:inline-block;width:14px;height:14px;background:${sampleC};border-radius:2px;vertical-align:middle;margin-right:4px;"></span> Solved</span>`;
    h += `<span><span style="display:inline-block;width:14px;height:14px;background:repeating-linear-gradient(-45deg,${sampleC},${sampleC} 2px,rgba(255,255,255,0.55) 2px,rgba(255,255,255,0.55) 5px);border-radius:2px;vertical-align:middle;margin-right:4px;"></span> Lost</span>`;
    h += `<span><span style="display:inline-block;width:14px;height:14px;background:rgba(230,126,34,0.18);border:1.5px solid ${sampleC};border-radius:2px;vertical-align:middle;margin-right:4px;"></span> Abandoned</span>`;
    h += '<span style="margin-left:8px;">Wrong count: ';
    for (let i = 0; i <= 4; i++) h += `<span style="display:inline-block;width:14px;height:14px;background:${BASE_COLORS[String(i)]};border-radius:2px;vertical-align:middle;margin:0 2px;"></span>`;
    h += `<span style="display:inline-block;width:14px;height:14px;background:${BASE_COLORS['no_attempt']};border-radius:2px;vertical-align:middle;margin:0 2px;"></span>`;
    h += ' (0 → 4 → no attempt)</span>';
    h += '</div>';
    return h;
}

/* ── Wrong-guess distribution chart ───────────────────────────── */

function renderWrongDistChart(canvasId, puzzle) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const distField = includeAbandons ? 'wrong_dist' : 'wrong_dist_completed';
    const activeKeys = includeAbandons
        ? WRONG_KEYS
        : WRONG_KEYS.filter(k => !k.endsWith('_incomplete') && k !== 'no_attempt_incomplete');

    const labels = [0, 1, 2, 3].map(i =>
        puzzle.rows?.[String(i)]?.category || `Row ${i}`
    ).concat(['Relink']);

    // Per-row totals for % conversion
    const totals = [0, 0, 0, 0, 0];
    for (const key of activeKeys) {
        for (let rp = 0; rp < 4; rp++) {
            totals[rp] += (puzzle.rows?.[String(rp)]?.[distField]?.[key] || 0);
        }
        totals[4] += (puzzle.relink?.[distField]?.[key] || 0);
    }

    const datasets = [];
    for (const key of activeKeys) {
        const color = baseColorForKey(key);
        const outcome = outcomeForKey(key);
        const raw = [];
        for (let rp = 0; rp < 4; rp++) raw.push(puzzle.rows?.[String(rp)]?.[distField]?.[key] || 0);
        raw.push(puzzle.relink?.[distField]?.[key] || 0);
        const data = showPercent
            ? raw.map((v, i) => totals[i] > 0 ? +(v / totals[i] * 100).toFixed(1) : 0)
            : raw;
        datasets.push({
            label: WRONG_LABELS[key] || key,
            data,
            backgroundColor: fillForOutcome(color, outcome),
            borderColor: outcome !== 'solved' ? color : undefined,
            borderWidth: outcome === 'incomplete' ? 1.5 : 0,
            stack: 'actual',
        });
    }

    const chart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: { labels, datasets },
        options: {
            indexAxis: 'y',
            interaction: horizontalInteraction,
            scales: {
                x: { stacked: true, max: showPercent ? 100 : undefined, title: { display: true, text: showPercent ? '% of players' : 'Players' } },
                y: { stacked: true },
            },
            plugins: { legend: { display: false }, tooltip: { callbacks: {
                label(ctx) { return showPercent ? `${ctx.dataset.label}: ${ctx.raw.toFixed(1)}%` : `${ctx.dataset.label}: ${ctx.raw}`; }
            } } },
        }
    });
    detailChartInstances.push(chart);
}

/* ── Solve-order distribution by row ───────────────────────────── */

function renderSolveOrderChart(canvasId, puzzle) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const distField = includeAbandons ? 'solve_order_dist' : 'solve_order_dist_completed';
    const labels = [];
    const perRowDist = [];
    for (let rp = 0; rp < 4; rp++) {
        const r = puzzle.rows?.[String(rp)];
        if (!r) continue;
        labels.push(`Row ${rp}: ${r.category || ''}`.trim().replace(/:\s*$/, ''));
        perRowDist.push(r[distField] || r.solve_order_dist || {});
    }
    if (puzzle.relink?.solve_order_dist) {
        labels.push('Relink');
        perRowDist.push(puzzle.relink[distField] || puzzle.relink.solve_order_dist);
    }

    const datasets = SOLVE_ORDER_BUCKETS.map(b => ({
        label: SOLVE_ORDER_LABELS[b],
        data: perRowDist.map(d => d[b] || 0),
        backgroundColor: SOLVE_ORDER_COLORS[b],
        borderWidth: 0,
        stack: 'so',
    }));

    const chart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: { labels, datasets },
        options: {
            indexAxis: 'y',
            interaction: horizontalInteraction,
            scales: {
                x: { stacked: true, max: 100, beginAtZero: true,
                      title: { display: true, text: 'Share of attempts (%)' } },
                y: { stacked: true },
            },
            plugins: {
                legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.raw.toFixed(1)}%`,
                    }
                },
            },
        }
    });
    detailChartInstances.push(chart);
}

/* ── Ever-solved binary by row ─────────────────────────────────── */

function renderEverSolvedChart(canvasId, puzzle) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const distField = includeAbandons ? 'solve_order_dist' : 'solve_order_dist_completed';
    const labels = [];
    const everPct = [];
    const everColors = [];

    const everFromDist = (sod) => {
        if (!sod) return null;
        return SOLVE_ORDER_BUCKETS
            .filter(b => b !== 'never')
            .reduce((s, b) => s + (sod[b] || 0), 0);
    };

    for (let rp = 0; rp < 4; rp++) {
        const r = puzzle.rows?.[String(rp)];
        if (!r) continue;
        const ev = everFromDist(r[distField] || r.solve_order_dist);
        if (ev == null) continue;
        labels.push(`Row ${rp}: ${r.category || ''}`.trim().replace(/:\s*$/, ''));
        everPct.push(+ev.toFixed(1));
        everColors.push(SOLVE_ORDER_COLORS['1st']);
    }
    if (puzzle.relink?.solve_order_dist) {
        const ev = everFromDist(puzzle.relink[distField] || puzzle.relink.solve_order_dist);
        if (ev != null) {
            labels.push('Relink');
            everPct.push(+ev.toFixed(1));
            everColors.push(SOLVE_ORDER_COLORS['5th']);
        }
    }

    const chart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: '% ever solved',
                data: everPct,
                backgroundColor: everColors,
                borderWidth: 0,
            }],
        },
        options: {
            indexAxis: 'y',
            interaction: horizontalInteraction,
            scales: {
                x: { beginAtZero: true, max: 100,
                      title: { display: true, text: '% of engaged players' } },
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.raw.toFixed(1)}% ever solved`,
                    }
                },
            },
        }
    });
    detailChartInstances.push(chart);
}

/* ── Whole-puzzle mistake distribution ─────────────────────────── */

function renderMistakeDistChart(canvasId, puzzle) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const dist = includeAbandons
        ? (puzzle.mistake_dist || {})
        : (puzzle.mistake_dist_completed || puzzle.mistake_dist || {});

    const maxKey = Math.min(Math.max(4, ...Object.keys(dist).map(Number).filter(n => !isNaN(n))), 4);
    const labels = [];
    for (let i = 0; i <= maxKey; i++) labels.push(String(i));

    const rawValues = labels.map(l => dist[l] || 0);
    const total = rawValues.reduce((a, b) => a + b, 0);
    const data = showPercent
        ? rawValues.map(v => total > 0 ? +(v / total * 100).toFixed(1) : 0)
        : rawValues;

    const chart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: { labels, datasets: [{ label: 'Players', data, backgroundColor: labels.map(l => BASE_COLORS[l] || BASE_COLORS['4']) }] },
        options: {
            indexAxis: 'y',
            interaction: horizontalInteraction,
            scales: {
                x: { beginAtZero: true, title: { display: true, text: showPercent ? '% of players' : 'Count', font: { size: 11 } } },
                y: { title: { display: true, text: 'Total wrong guesses', font: { size: 11 } } },
            },
            plugins: { legend: { display: false }, tooltip: { callbacks: {
                label(ctx) { return showPercent ? `${ctx.dataset.label}: ${ctx.raw.toFixed(1)}%` : `${ctx.dataset.label}: ${ctx.raw}`; }
            } } },
        }
    });
    detailChartInstances.push(chart);
}

/* ── Dual-axis timing + error curve ───────────────────────────── */

function renderDualCurveChart(canvasId, puzzle) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !puzzle.timing) return;

    const tm = puzzle.timing;
    const positions = ['Pos 0', 'Pos 1', 'Pos 2', 'Pos 3'];

    const chart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            labels: positions,
            datasets: [
                {
                    label: 'Median time (s)',
                    data: tm.timing_curve,
                    borderColor: COLORS[0],
                    backgroundColor: hsla(0, 70, 55, 0.12),
                    fill: true, tension: 0.3, pointRadius: 4, yAxisID: 'y',
                },
                {
                    label: 'Mean wrong guesses',
                    data: tm.error_curve,
                    borderColor: COLORS[2],
                    backgroundColor: hsla(145, 60, 45, 0.12),
                    fill: true, tension: 0.3, pointRadius: 4, yAxisID: 'y1',
                },
            ],
        },
        options: {
            scales: {
                y: { type: 'linear', position: 'left', beginAtZero: true,
                     title: { display: true, text: 'Time (s)', font: { size: 11 }, color: COLORS[0] },
                     ticks: { color: COLORS[0] }, grid: { drawOnChartArea: true } },
                y1: { type: 'linear', position: 'right', beginAtZero: true,
                      title: { display: true, text: 'Wrong guesses', font: { size: 11 }, color: COLORS[2] },
                      ticks: { color: COLORS[2] }, grid: { drawOnChartArea: false } },
                x: { title: { display: false } },
            },
            plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } },
        }
    });
    detailChartInstances.push(chart);
}

/* ── Chart cleanup ────────────────────────────────────────────── */

function destroyCharts() {
    chartInstances.forEach(c => c.destroy());
    chartInstances = [];
}

function destroyDetailCharts() {
    detailChartInstances.forEach(c => c.destroy());
    detailChartInstances = [];
}

function rebuildDetailCharts(puzzle) {
    // Rebuild just the detail charts by re-rendering the detail panel
    if (expandedKey) renderDetail(expandedKey);
}
