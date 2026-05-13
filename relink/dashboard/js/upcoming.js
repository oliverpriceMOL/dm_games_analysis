/**
 * Upcoming Puzzles page — sortable table of undated (predicted-only) puzzles
 * with click-to-expand detail panels showing design features and predicted ratings.
 */

import {
    DIM_COLORS,
    createRadarChart,
    badge, stars, tierClass, dimBar,
} from './utils.js';

/* ── State ──────────────────────────────────────────────────────── */

let puzzles = [];        // [{key, p, diff}]
let chartInstances = [];
let expandedKey = null;
let sortCol = 'rating';
let sortDir = 1;

/* ── Public API ─────────────────────────────────────────────────── */

export function render(explorerData, difficultyData, simulatorData) {
    const undated = explorerData.undated_puzzles || {};
    const diffUndated = difficultyData.undated || {};
    const dims = difficultyData.dimensions || [];
    const dimLabels = difficultyData.dimension_labels || {};
    const simPuzzles = simulatorData?.puzzles || {};

    puzzles = Object.keys(undated).sort((a, b) => {
        const da = undated[a].name || '', db = undated[b].name || '';
        return da.localeCompare(db);
    }).map(key => {
        const p = undated[key];
        const diff = diffUndated[key] || {};
        // Merge predicted solve rate from simulator if available
        if (p.predicted_solve_rate == null && simPuzzles[key]?.simulated_solve_rate != null) {
            p.predicted_solve_rate = simPuzzles[key].simulated_solve_rate;
        }
        return { key, p, diff, dims, dimLabels };
    });

    buildTable();
}

/* ── Sort ────────────────────────────────────────────────────────── */

function sortPuzzles() {
    puzzles.sort((a, b) => {
        let av, bv;
        switch (sortCol) {
            case 'name':      return sortDir * a.p.name.localeCompare(b.p.name);
            case 'rating':    av = a.diff.rating || 0; bv = b.diff.rating || 0; break;
            case 'solve':     av = a.p.predicted_solve_rate || 0; bv = b.p.predicted_solve_rate || 0; break;
            case 'p2tiles':   av = a.p.pdl?.phase2TileCount || 0; bv = b.p.pdl?.phase2TileCount || 0; break;
            default:          av = a.diff.rating || 0; bv = b.diff.rating || 0; break;
        }
        return sortDir * ((av || 0) - (bv || 0));
    });
}

function arrow(col) {
    if (col !== sortCol) return '';
    return ` <span class="sort-arrow">${sortDir === 1 ? '▲' : '▼'}</span>`;
}

/* ── Table ───────────────────────────────────────────────────────── */

function buildTable() {
    destroyCharts();
    sortPuzzles();

    const container = document.getElementById('upcoming-table-container');
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
    html += `<table id="upcoming-table"><thead><tr>`;
    html += `<th class="sortable-th" data-col="name">Puzzle${arrow('name')}</th>`;
    html += `<th class="sortable-th" data-col="rating">Predicted Difficulty${arrow('rating')}</th>`;
    html += `<th class="sortable-th" data-col="solve">Predicted Solve Rate${arrow('solve')}</th>`;
    html += `<th class="sortable-th" data-col="p2tiles">P2 Tiles${arrow('p2tiles')}</th>`;
    html += `<th>Profile</th>`;
    html += `</tr></thead><tbody>`;

    for (let i = 0; i < puzzles.length; i++) {
        const { key, p, diff } = puzzles[i];
        const rating = diff.rating || 0;
        const predSr = p.predicted_solve_rate != null ? p.predicted_solve_rate.toFixed(0) + '%' : '—';
        const isExpanded = key === expandedKey;
        html += `<tr class="catalogue-row ${tierClass(rating)}${isExpanded ? ' expanded' : ''}" data-key="${key}">`;
        html += `<td><strong>${p.name}</strong> <span class="badge badge-predicted">Predicted</span></td>`;
        html += `<td>${stars(rating)}</td>`;
        html += `<td>${predSr !== '—' ? badge(predSr) : '—'}</td>`;
        html += `<td>${p.pdl?.phase2TileCount || '—'}</td>`;
        html += `<td><div class="table-radar-wrap"><canvas id="up-radar-${i}" width="140" height="140"></canvas></div></td>`;
        html += `</tr>`;
    }
    html += `</tbody></table>`;
    container.innerHTML = html;

    // Render mini radars
    for (let i = 0; i < puzzles.length; i++) {
        const { diff, dims: d, dimLabels: dl } = puzzles[i];
        if (diff.profile) {
            createRadarChart(`up-radar-${i}`, d, dl, diff.profile, { shortLabels: true });
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
    html += `<h3 style="margin:0;">${p.name} <span class="badge badge-predicted">Predicted</span></h3>`;

    // ── Top row: radar + design features ──
    html += `<div style="display:flex;gap:24px;margin-top:16px;flex-wrap:wrap;">`;
    html += `<div style="min-width:280px;"><canvas id="up-detail-radar" width="280" height="280"></canvas></div>`;
    html += `<div style="flex:1;min-width:200px;">`;
    html += `<div class="stats-grid" style="margin-bottom:12px;">`;
    html += `<div class="stat-card"><div class="value">${stars(diff.rating || 0)}</div><div class="label">Predicted Rating</div></div>`;
    const predSr = p.predicted_solve_rate != null ? p.predicted_solve_rate.toFixed(1) + '%' : '—';
    html += `<div class="stat-card"><div class="value">${predSr}</div><div class="label">Predicted Solve Rate</div></div>`;
    html += `<div class="stat-card"><div class="value">${p.pdl?.phase2TileCount || '—'}</div><div class="label">P2 Tiles</div></div>`;
    html += `</div>`;
    html += `</div></div>`;

    // ── Design features summary ──
    if (p.pdl) {
        html += `<h4 style="margin-top:20px;">Design Features</h4>`;
        html += `<div class="stats-grid">`;
        html += `<div class="stat-card"><div class="value">${p.pdl.manipulationComplexity || '—'}</div><div class="label">Manipulation Complexity</div></div>`;
        html += `<div class="stat-card"><div class="value">${p.pdl.abstractionComplexity || '—'}</div><div class="label">Abstraction Complexity</div></div>`;
        html += `<div class="stat-card"><div class="value">${p.pdl.knowledgeBreadth ?? '—'}</div><div class="label">Knowledge Breadth</div></div>`;
        html += `<div class="stat-card"><div class="value">${p.pdl.specialistGroupCount ?? '—'}</div><div class="label">Specialist Groups</div></div>`;
        html += `<div class="stat-card"><div class="value">${p.pdl.decoyCount ?? '—'}</div><div class="label">Decoy Groups</div></div>`;
        html += `<div class="stat-card"><div class="value">${p.pdl.phase2TileCount || '—'}</div><div class="label">P2 Tile Count</div></div>`;
        html += `</div>`;
    }

    // ── Row breakdown table (PDL only, no player stats) ──
    html += `<h4 style="margin-top:20px;">Row Breakdown</h4>`;
    html += `<div style="overflow-x:auto;"><table><thead><tr>`;
    html += `<th>Row</th><th>Category</th><th>Manipulation</th><th>Abstraction</th>`;
    html += `<th>Knowledge</th><th>Domain</th><th>Impostor</th>`;
    html += `</tr></thead><tbody>`;
    for (let rp = 0; rp < 4; rp++) {
        const r = p.rows?.[String(rp)];
        if (!r) continue;
        html += `<tr>`;
        html += `<td>${rp}</td><td>${r.category || '—'}</td>`;
        html += `<td>${r.manipulation}</td><td>${r.abstraction}</td>`;
        html += `<td>${r.knowledge}</td><td>${r.knowledgeDomain || '—'}</td>`;
        html += `<td>${r.impostor_word || '—'}</td>`;
        html += `</tr>`;
    }
    // Relink
    if (p.relink) {
        html += `<tr style="background:#f8f9fa;">`;
        html += `<td><em>Relink</em></td><td colspan="5">${p.relink.answer || '—'}</td><td>—</td>`;
        html += `</tr>`;
    }
    html += `</tbody></table></div>`;

    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Close handlers
    const closeModal = () => {
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

    // Render detail radar
    const detailCanvas = document.getElementById('up-detail-radar');
    if (diff.profile && detailCanvas) {
        createRadarChart('up-detail-radar', dims, dimLabels, diff.profile, { large: true, showValues: true });
    }
}

/* ── Cleanup ──────────────────────────────────────────────────── */

function destroyCharts() {
    chartInstances.forEach(c => c.destroy());
    chartInstances = [];
}
