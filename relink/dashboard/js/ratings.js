/**
 * Difficulty Ratings page renderer.
 * Shows 5-axis difficulty profiles, 1-5 star ratings, sortable table, radar charts,
 * and per-dimension rankings for all 39 puzzles.
 */

import { COLORS, hsl, hsla, nearestInteraction } from './charts.js';

const DIM_COLORS = {
    impostor_deception:   hsl(0, 70, 50),
    knowledge_demand:     hsl(35, 90, 55),
    punishment_risk:      hsl(145, 60, 45),
    connection_challenge: hsl(210, 70, 50),
    volatility:           hsl(270, 60, 55),
};
const DIM_COLORS_A = {
    impostor_deception:   hsla(0, 70, 50, 0.25),
    knowledge_demand:     hsla(35, 90, 55, 0.25),
    punishment_risk:      hsla(145, 60, 45, 0.25),
    connection_challenge: hsla(210, 70, 50, 0.25),
    volatility:           hsla(270, 60, 55, 0.25),
};
const TIER_COLORS = ['#27ae60', '#2ecc71', '#f39c12', '#e74c3c', '#c0392b'];

function stars(rating) {
    let s = '';
    for (let i = 1; i <= 5; i++) {
        s += i <= rating
            ? '<span class="star-on">★</span>'
            : '<span class="star-off">★</span>';
    }
    return `<span class="star-rating">${s}</span>`;
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

/* ── Main render ─────────────────────────────────────────── */

export function render(data) {
    const diff = data.difficulty;
    if (!diff) return;

    // Merge dated + undated into one list
    const all = [];
    for (const [key, p] of Object.entries(diff.puzzles || {})) {
        all.push({ ...p, _key: key, _sort: p.composite });
    }
    for (const [key, p] of Object.entries(diff.undated || {})) {
        all.push({ ...p, _key: key, _sort: p.composite });
    }
    all.sort((a, b) => a._sort - b._sort);

    renderValidation(diff);
    renderTable(all, diff);
    renderDimRankings(all, diff);
}

/* ── Validation stats ────────────────────────────────────── */

function renderValidation(diff) {
    const v = diff.validation || {};
    const grid = document.getElementById('ratings-validation-stats');
    if (!grid) return;
    grid.innerHTML = `
        <div class="stat-card"><div class="value">${Math.abs(v.spearman_rho || 0).toFixed(2)}</div>
            <div class="label">Spearman |ρ|</div></div>
        <div class="stat-card"><div class="value">${Math.abs(v.pearson_r || 0).toFixed(2)}</div>
            <div class="label">Pearson |r|</div></div>
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
    new Chart(canvas.getContext('2d'), {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'Dated puzzles',
                data: pts.map(p => ({ x: p.composite, y: p.solve_rate })),
                backgroundColor: pts.map(p => TIER_COLORS[p.rating - 1]),
                borderColor: pts.map(p => TIER_COLORS[p.rating - 1]),
                pointRadius: 7,
            }]
        },
        options: {
            interaction: nearestInteraction,
            scales: {
                x: { title: { display: true, text: 'Composite difficulty' }, min: 0.2, max: 0.6 },
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
                            return [
                                `Solve rate: ${p.solve_rate}%`,
                                `Composite: ${p.composite.toFixed(3)}`,
                                `Rating: ${'★'.repeat(p.rating)}${'☆'.repeat(5 - p.rating)} (${p.rating}/5)`,
                            ];
                        }
                    }
                },
                legend: { display: false },
            }
        }
    });
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
            if (sortCol === 'rating') { av = a.rating; bv = b.rating; }
            else if (sortCol === 'solve_rate') { av = a.solve_rate; bv = b.solve_rate; }
            else if (sortCol === 'composite') { av = a.composite; bv = b.composite; }
            else if (dims.includes(sortCol)) { av = a.profile[sortCol]; bv = b.profile[sortCol]; }
            else { av = a.composite; bv = b.composite; }
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
            html += `<tr${pred} class="${tierClass(p.rating)}">
                <td>${p.name}${p.has_player_data ? '' : ' <span class="explorer-pred-tag">PRED</span>'}</td>
                <td>${stars(p.rating)}</td>
                <td>${sr}</td>
                <td>${p.composite.toFixed(3)}</td>
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
                        data: dims.map(d => p.profile[d]),
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

    // Labels with values baked in: ["Impostor", "Deception", "72%"]
    const labels = dims.map(d => {
        const words = (dimLabels[d] || d).split(' ');
        words.push(`${Math.round(p.profile[d] * 100)}%`);
        return words;
    });
    const color = TIER_COLORS[p.rating - 1];
    const sr = p.has_player_data
        ? `${(p.solve_rate * 100).toFixed(0)}%`
        : `~${p.predicted_solve_rate}% (predicted)`;

    overlay = document.createElement('div');
    overlay.id = 'radar-modal-overlay';
    overlay.className = 'radar-modal-overlay';
    overlay.innerHTML = `<div class="radar-modal">
        <button class="radar-modal-close">&times;</button>
        <h3>${p.name} ${stars(p.rating)}</h3>
        <p class="radar-modal-meta">Solve rate: ${sr} · Composite: ${p.composite.toFixed(3)}</p>
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
                data: dims.map(d => p.profile[d]),
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
        const sorted = [...all].sort((a, b) => b.profile[dim] - a.profile[dim]).slice(0, 10);
        const color = DIM_COLORS[dim] || '#636e72';
        html += `<div class="card">
            <h3 style="color:${color}">${dimLabels[dim] || dim}</h3>
            <table><thead><tr><th>#</th><th>Puzzle</th><th>Score</th><th>Rating</th></tr></thead><tbody>`;
        sorted.forEach((p, i) => {
            html += `<tr>
                <td>${i + 1}</td>
                <td>${p.name}${p.has_player_data ? '' : ' <span class="explorer-pred-tag">PRED</span>'}</td>
                <td>${dimBar(p.profile[dim], dim)}</td>
                <td>${stars(p.rating)}</td>
            </tr>`;
        });
        html += `</tbody></table></div>`;
    }
    container.innerHTML = html;
}
