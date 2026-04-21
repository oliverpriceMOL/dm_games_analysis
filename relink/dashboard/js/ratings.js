/**
 * Difficulty Ratings page renderer.
 * Shows 5-axis difficulty profiles, 1-5 star ratings, sortable table, radar charts,
 * and per-dimension rankings for all 39 puzzles.
 */

import { COLORS, hsl, hsla, nearestInteraction } from './charts.js';

const DIM_COLORS = {
    manipulation:      hsl(0, 70, 50),
    abstraction:       hsl(35, 90, 55),
    domain_mismatch:   hsl(145, 60, 45),
    knowledge:         hsl(210, 70, 50),
    relink_challenge:  hsl(270, 60, 55),
};
const DIM_COLORS_A = {
    manipulation:      hsla(0, 70, 50, 0.25),
    abstraction:       hsla(35, 90, 55, 0.25),
    domain_mismatch:   hsla(145, 60, 45, 0.25),
    knowledge:         hsla(210, 70, 50, 0.25),
    relink_challenge:  hsla(270, 60, 55, 0.25),
};
const TIER_COLORS = ['#27ae60', '#2ecc71', '#f39c12', '#e74c3c', '#c0392b'];

// Toggle state: 'actual' or 'predicted'
let profileMode = 'actual';

function stars(rating) {
    let s = '';
    for (let i = 1; i <= 5; i++) {
        s += `<span class="diff-seg${i <= rating ? ' on' : ''}"></span>`;
    }
    return `<span class="diff-bar" data-tier="${rating}">${s}</span>`;
}

function dimBar(val, dim) {
    const pct = Math.round(val * 100);
    const color = DIM_COLORS[dim] || '#636e72';
    return `<div class="dim-bar-wrap">
        <div class="dim-bar" style="width:${pct}%;max-width:60px;background:${color}"></div>
        <span class="dim-bar-label">${pct}%</span>
    </div>`;
}

function tierClass(rating) { return `rating-tier-${rating}`; }

/** Create a conic gradient that sweeps through dimension colours (with alpha). */
function createConicGradient(ctx2d, cx, cy, dims) {
    const n = dims.length;
    // Radar charts start at top (-90°) and go clockwise
    const startAngle = -Math.PI / 2;
    const grad = ctx2d.createConicGradient(startAngle, cx, cy);
    for (let i = 0; i < n; i++) {
        const stop = i / n;
        grad.addColorStop(stop, DIM_COLORS_A[dims[i]] || 'rgba(99,110,114,0.25)');
    }
    grad.addColorStop(1, DIM_COLORS_A[dims[0]] || 'rgba(99,110,114,0.25)');
    return grad;
}

/** Get the active profile for a puzzle depending on profileMode. */
function activeProfile(p) {
    if (profileMode === 'predicted' && p.predicted_profile) return p.predicted_profile;
    return p.profile;
}
function activeComposite(p) {
    if (profileMode === 'predicted' && p.predicted_composite != null) return p.predicted_composite;
    return p.composite;
}
function activeRating(p) {
    if (profileMode === 'predicted' && p.predicted_rating != null) return p.predicted_rating;
    return p.rating;
}

/* ── Main render ─────────────────────────────────────────── */

let _diff = null;

export function render(data) {
    _diff = data.difficulty;
    if (!_diff) return;
    profileMode = 'actual';
    buildAll();
}

function buildAll() {
    const diff = _diff;
    const all = [];
    for (const [key, p] of Object.entries(diff.puzzles || {})) {
        all.push({ ...p, _key: key, _sort: activeComposite(p) });
    }
    for (const [key, p] of Object.entries(diff.undated || {})) {
        all.push({ ...p, _key: key, _sort: activeComposite(p) });
    }
    all.sort((a, b) => a._sort - b._sort);

    renderToggle(diff);
    renderValidation(diff);
    renderTable(all, diff);
    renderDimRankings(all, diff);
}

/* ── Actual / Predicted toggle ───────────────────────────── */

function renderToggle(diff) {
    const anchor = document.getElementById('ratings-validation-stats');
    if (!anchor) return;
    let wrap = document.getElementById('ratings-mode-toggle');
    if (!wrap) {
        wrap = document.createElement('div');
        wrap.id = 'ratings-mode-toggle';
        wrap.className = 'toggle-group';
        anchor.parentElement.insertBefore(wrap, anchor);
    }
    wrap.innerHTML = `
        <button class="toggle-btn${profileMode === 'actual' ? ' active' : ''}" data-mode="actual">Actual</button>
        <button class="toggle-btn${profileMode === 'predicted' ? ' active' : ''}" data-mode="predicted">Predicted</button>`;
    wrap.querySelectorAll('.toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const mode = btn.dataset.mode;
            if (mode === profileMode) return;
            profileMode = mode;
            buildAll();
        });
    });
}

/* ── Validation stats ────────────────────────────────────── */

function renderValidation(diff) {
    const v = diff.validation || {};
    const grid = document.getElementById('ratings-validation-stats');
    if (!grid) return;

    const isPred = profileMode === 'predicted';
    const rho = isPred ? Math.abs(v.predicted_spearman_rho || 0) : Math.abs(v.spearman_rho || 0);
    const r = isPred ? Math.abs(v.predicted_pearson_r || 0) : Math.abs(v.pearson_r || 0);
    const modeLabel = isPred ? '(predicted)' : '(actual)';

    grid.innerHTML = `
        <div class="stat-card"><div class="value">${rho.toFixed(2)}</div>
            <div class="label">Spearman |ρ| ${modeLabel}</div></div>
        <div class="stat-card"><div class="value">${r.toFixed(2)}</div>
            <div class="label">Pearson |r| ${modeLabel}</div></div>
        <div class="stat-card"><div class="value">${v.n_dated || 0}</div>
            <div class="label">Dated puzzles</div></div>
        <div class="stat-card"><div class="value">${Object.keys(diff.puzzles || {}).length + Object.keys(diff.undated || {}).length}</div>
            <div class="label">Total rated</div></div>
    `;

    // Scatter: composite vs solve rate
    const canvas = document.getElementById('chart-ratings-scatter');
    if (!canvas) return;
    const pts = (v.composite_vs_solve_rate || []);
    if (!pts.length) return;
    // Destroy previous scatter if exists
    if (canvas._chartInstance) { canvas._chartInstance.destroy(); }
    const isPred2 = profileMode === 'predicted';
    const chart = new Chart(canvas.getContext('2d'), {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'Dated puzzles',
                data: pts.map(p => ({
                    x: isPred2 ? (p.predicted_composite ?? p.composite) : p.composite,
                    y: p.solve_rate
                })),
                backgroundColor: pts.map(p => {
                    const r = isPred2 ? (p.predicted_rating ?? p.rating) : p.rating;
                    return TIER_COLORS[r - 1];
                }),
                borderColor: pts.map(p => {
                    const r = isPred2 ? (p.predicted_rating ?? p.rating) : p.rating;
                    return TIER_COLORS[r - 1];
                }),
                pointRadius: 7,
            }]
        },
        options: {
            interaction: nearestInteraction,
            scales: {
                x: { title: { display: true, text: `Composite difficulty (${isPred2 ? 'predicted' : 'actual'})` }, min: 0.1, max: 0.6 },
                y: { title: { display: true, text: 'Actual solve rate %' }, min: 0, max: 100 },
            },
            plugins: {
                tooltip: {
                    filter: (item) => item.datasetIndex === 0,
                    callbacks: {
                        title: (items) => {
                            const p = pts[items[0].dataIndex];
                            return p.label;
                        },
                        label: (ctx) => {
                            const p = pts[ctx.dataIndex];
                            const comp = isPred2 ? (p.predicted_composite ?? p.composite) : p.composite;
                            const rating = isPred2 ? (p.predicted_rating ?? p.rating) : p.rating;
                            return [
                                `Solve rate: ${p.solve_rate}%`,
                                `Composite: ${comp.toFixed(3)}`,
                                `Rating: ${'■'.repeat(rating)}${'□'.repeat(5 - rating)} (${rating}/5)`,
                            ];
                        }
                    }
                },
                legend: { display: false },
            }
        }
    });
    canvas._chartInstance = chart;
}

/* ── Sortable table ──────────────────────────────────────── */

const tableCharts = [];  // track Chart instances for cleanup on re-sort

function renderTable(all, diff) {
    const container = document.getElementById('ratings-table-container');
    if (!container) return;

    const dims = diff.dimensions || [];
    const dimLabels = diff.dimension_labels || {};
    const radarLabelsFull = dims.map(d => (dimLabels[d] || d).split(' '));
    // Short abbreviations for inline radar axis labels
    const radarLabelsShort = dims.map(d => {
        const l = dimLabels[d] || d;
        return l.split(' ').map(w => w[0].toUpperCase()).join('');
    });

    let sortCol = 'composite';
    let sortDir = 1; // 1 = asc, -1 = desc

    function build() {
        // Destroy previous chart instances
        tableCharts.forEach(c => c.destroy());
        tableCharts.length = 0;

        const sorted = [...all].sort((a, b) => {
            let av, bv;
            if (sortCol === 'name') { av = a.name; bv = b.name; return sortDir * av.localeCompare(bv); }
            if (sortCol === 'rating') { av = activeRating(a); bv = activeRating(b); }
            else if (sortCol === 'solve_rate') { av = a.solve_rate; bv = b.solve_rate; }
            else if (sortCol === 'composite') { av = activeComposite(a); bv = activeComposite(b); }
            else if (dims.includes(sortCol)) { av = activeProfile(a)[sortCol]; bv = activeProfile(b)[sortCol]; }
            else { av = activeComposite(a); bv = activeComposite(b); }
            return sortDir * ((av || 0) - (bv || 0));
        });

        const arrow = (col) => {
            if (col !== sortCol) return '';
            return `<span class="sort-arrow">${sortDir === 1 ? '▲' : '▼'}</span>`;
        };

        // Build abbreviation legend
        const legendParts = dims.map((d, i) => `<strong>${radarLabelsShort[i]}</strong> = ${dimLabels[d] || d}`);
        let html = `<p class="radar-legend">${legendParts.join(' · ')}</p>`;
        html += `<table><thead><tr>
            <th class="sortable-th" data-col="name">Puzzle${arrow('name')}</th>
            <th class="sortable-th" data-col="rating">Rating${arrow('rating')}</th>
            <th class="sortable-th" data-col="solve_rate">Solve Rate${arrow('solve_rate')}</th>
            <th class="sortable-th" data-col="composite">Composite${arrow('composite')}</th>
            <th>Profile</th>
        </tr></thead><tbody>`;

        for (let i = 0; i < sorted.length; i++) {
            const p = sorted[i];
            const pred = p.has_player_data ? '' : ' style="opacity:0.7;font-style:italic"';
            const sr = p.has_player_data
                ? `${(p.solve_rate * 100).toFixed(0)}%`
                : `~${p.predicted_solve_rate}%`;
            const canvasId = `tbl-radar-${i}`;
            const rating = activeRating(p);
            const comp = activeComposite(p);
            html += `<tr${pred} class="${tierClass(rating)}">
                <td>${p.name}${p.has_player_data ? '' : ' <span class="explorer-pred-tag">PRED</span>'}</td>
                <td>${stars(rating)}</td>
                <td>${sr}</td>
                <td>${comp.toFixed(3)}</td>
                <td><div class="table-radar-wrap"><canvas id="${canvasId}" width="140" height="140"></canvas></div></td>
            </tr>`;
        }
        html += `</tbody></table>`;
        container.innerHTML = html;

        // Render mini radars inside table cells
        for (let i = 0; i < sorted.length; i++) {
            const p = sorted[i];
            const canvas = document.getElementById(`tbl-radar-${i}`);
            if (!canvas) continue;
            const ptColors = dims.map(d => DIM_COLORS[d] || '#636e72');
            const ptColorsA = dims.map(d => DIM_COLORS_A[d] || 'rgba(99,110,114,0.25)');
            // Conic gradient for fill
            const ctx2d = canvas.getContext('2d');
            const cx = 70, cy = 70;
            const grad = createConicGradient(ctx2d, cx, cy, dims);
            const chart = new Chart(ctx2d, {
                type: 'radar',
                data: {
                    labels: radarLabelsShort,
                    datasets: [{
                        data: dims.map(d => activeProfile(p)[d]),
                        backgroundColor: grad,
                        borderWidth: 1.5,
                        segment: { borderColor: (ctx) => ptColors[ctx.p0DataIndex] },
                        pointBackgroundColor: ptColors,
                        pointBorderColor: ptColors,
                        pointRadius: 3,
                    }]
                },
                options: {
                    responsive: false,
                    animation: false,
                    interaction: nearestInteraction,
                    scales: {
                        r: {
                            min: 0, max: 1, beginAtZero: true,
                            ticks: { display: false },
                            pointLabels: { display: true, font: { size: 9 }, color: ptColors },
                            grid: { color: '#dfe6e920' },
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title: (items) => {
                                    const idx = items[0].dataIndex;
                                    return (dimLabels[dims[idx]] || dims[idx]);
                                },
                                label: (ctx) => `${(ctx.raw * 100).toFixed(0)}%`
                            }
                        }
                    }
                }
            });
            tableCharts.push(chart);
        }

        // Attach click handlers to open modal
        for (let i = 0; i < sorted.length; i++) {
            const canvas = document.getElementById(`tbl-radar-${i}`);
            if (!canvas) continue;
            canvas.style.cursor = 'pointer';
            canvas.addEventListener('click', () => showRadarModal(sorted[i], dims, dimLabels));
        }

        // Attach sort handlers
        container.querySelectorAll('.sortable-th').forEach(th => {
            th.addEventListener('click', () => {
                const col = th.dataset.col;
                if (sortCol === col) { sortDir *= -1; }
                else { sortCol = col; sortDir = col === 'name' ? 1 : -1; }
                build();
            });
        });
    }
    build();
}

/* ── Radar modal ──────────────────────────────────────── */

let modalChart = null;

function showRadarModal(p, dims, dimLabels) {
    // Remove existing modal if any
    let overlay = document.getElementById('radar-modal-overlay');
    if (overlay) overlay.remove();

    // Labels with values baked in: ["Manipulation", "72%"]
    const prof = activeProfile(p);
    const labels = dims.map(d => {
        const words = (dimLabels[d] || d).split(' ');
        words.push(`${Math.round(prof[d] * 100)}%`);
        return words;
    });
    const rating = activeRating(p);
    const color = TIER_COLORS[rating - 1];
    const sr = p.has_player_data
        ? `${(p.solve_rate * 100).toFixed(0)}%`
        : `~${p.predicted_solve_rate}% (predicted)`;
    const comp = activeComposite(p);

    overlay = document.createElement('div');
    overlay.id = 'radar-modal-overlay';
    overlay.className = 'radar-modal-overlay';
    overlay.innerHTML = `<div class="radar-modal">
        <button class="radar-modal-close">&times;</button>
        <h3>${p.name} ${stars(rating)}</h3>
        <p class="radar-modal-meta">Solve rate: ${sr} · Composite: ${comp.toFixed(3)}</p>
        <div class="radar-modal-body">
            <div class="radar-modal-chart"><canvas id="modal-radar-canvas" width="300" height="300"></canvas></div>
        </div>
    </div>`;
    document.body.appendChild(overlay);

    // Close handlers
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeRadarModal();
    });
    overlay.querySelector('.radar-modal-close').addEventListener('click', closeRadarModal);
    document.addEventListener('keydown', modalEscHandler);

    // Render large radar with per-dimension colours
    const canvas = document.getElementById('modal-radar-canvas');
    if (modalChart) { modalChart.destroy(); modalChart = null; }
    const dimColors = dims.map(d => DIM_COLORS[d] || '#636e72');
    const dimColorsA = dims.map(d => DIM_COLORS_A[d] || 'rgba(99,110,114,0.25)');
    const ctx2d = canvas.getContext('2d');
    const grad = createConicGradient(ctx2d, 150, 150, dims);
    modalChart = new Chart(ctx2d, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                data: dims.map(d => prof[d]),
                backgroundColor: grad,
                borderWidth: 2,
                segment: { borderColor: (ctx) => dimColors[ctx.p0DataIndex] },
                pointBackgroundColor: dimColors,
                pointBorderColor: dimColors,
                pointRadius: 5,
                pointHoverRadius: 7,
            }]
        },
        options: {
            responsive: false,
            animation: { duration: 200 },
            interaction: nearestInteraction,
            scales: {
                r: {
                    min: 0, max: 1, beginAtZero: true,
                    ticks: { stepSize: 0.25, display: false },
                    pointLabels: {
                        font: { size: 12, weight: 'bold' },
                        color: dimColors,
                    },
                    grid: { color: '#dfe6e940' },
                    angleLines: { color: '#dfe6e940' },
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${(ctx.raw * 100).toFixed(0)}%`
                    }
                }
            }
        }
    });
}

function modalEscHandler(e) {
    if (e.key === 'Escape') closeRadarModal();
}

function closeRadarModal() {
    const overlay = document.getElementById('radar-modal-overlay');
    if (overlay) overlay.remove();
    if (modalChart) { modalChart.destroy(); modalChart = null; }
    document.removeEventListener('keydown', modalEscHandler);
}

/* ── Dimension rankings ──────────────────────────────────── */

function renderDimRankings(all, diff) {
    const container = document.getElementById('ratings-dim-rankings');
    if (!container) return;

    const dims = diff.dimensions || [];
    const dimLabels = diff.dimension_labels || {};

    let html = '';
    for (const dim of dims) {
        const sorted = [...all].sort((a, b) => activeProfile(b)[dim] - activeProfile(a)[dim]).slice(0, 10);
        const color = DIM_COLORS[dim] || '#636e72';
        html += `<div class="card">
            <h3 style="color:${color}">${dimLabels[dim] || dim}</h3>
            <table><thead><tr><th>#</th><th>Puzzle</th><th>Score</th><th>Rating</th></tr></thead><tbody>`;
        sorted.forEach((p, i) => {
            html += `<tr>
                <td>${i + 1}</td>
                <td>${p.name}${p.has_player_data ? '' : ' <span class="explorer-pred-tag">PRED</span>'}</td>
                <td>${dimBar(activeProfile(p)[dim], dim)}</td>
                <td>${stars(activeRating(p))}</td>
            </tr>`;
        });
        html += `</tbody></table></div>`;
    }
    container.innerHTML = html;
}
