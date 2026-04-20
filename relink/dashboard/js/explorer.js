/**
 * Puzzle Explorer — multi-puzzle comparison page.
 * Renders a grid of puzzle cards with wrong-guess distributions,
 * PDL features, timing curves, failure correlations, simulator data,
 * and predicted distributions from the Monte Carlo model.
 */

import { COLORS, hsl, hsla, nearestInteraction, horizontalInteraction } from './charts.js';

// Base colors by wrong count
const BASE_COLORS = {
    '0': '#e74c3c',   // red — first try
    '1': '#f39c12',   // orange — 1 wrong
    '2': '#27ae60',   // green — 2 wrong
    '3': '#2980b9',   // blue — 3 wrong
    '4': '#8e44ad',   // purple — 4 wrong (sim only, positional wrongs)
    'no_attempt': '#c0392b', // dark red — never attempted
};

// Compound keys for the split wrong_dist (actual data)
const WRONG_KEYS = [
    '0_solved', '0_lost', '0_incomplete',
    '1_solved', '1_lost', '1_incomplete',
    '2_solved', '2_lost', '2_incomplete',
    '3_solved', '3_lost', '3_incomplete',
    '4_solved', '4_lost', '4_incomplete',
    'no_attempt_lost', 'no_attempt_incomplete',
];

// Human-readable labels
const WRONG_LABELS = {
    '0_solved': '0 wrong (solved)',
    '0_lost': '0 wrong (lost)', '0_incomplete': '0 wrong (abandoned)',
    '1_solved': '1 wrong (solved)', '1_lost': '1 wrong (lost)', '1_incomplete': '1 wrong (abandoned)',
    '2_solved': '2 wrong (solved)', '2_lost': '2 wrong (lost)', '2_incomplete': '2 wrong (abandoned)',
    '3_solved': '3 wrong (solved)', '3_lost': '3 wrong (lost)', '3_incomplete': '3 wrong (abandoned)',
    '4_solved': '4 wrong (solved)', '4_lost': '4 wrong (lost)',
    'no_attempt_lost': 'No attempt (lost)',
    'no_attempt_incomplete': 'No attempt (abandoned)',
};

// Map compound key → base color
function baseColorForKey(key) {
    if (key.startsWith('no_attempt')) return BASE_COLORS['no_attempt'];
    const n = key.charAt(0);
    return BASE_COLORS[n] || BASE_COLORS['4']; // 4+ all use darkest red
}

// Map compound key → outcome suffix
function outcomeForKey(key) {
    if (key.includes('_solved')) return 'solved';
    if (key.includes('_lost') || key === 'no_attempt_lost') return 'lost';
    return 'incomplete';
}

// Predicted keys — simulator now uses compound keys (solved/lost split, no incomplete)
const PRED_KEYS = [
    '0_solved', '0_lost',
    '1_solved', '1_lost',
    '2_solved', '2_lost',
    '3_solved', '3_lost',    '4_solved', '4_lost',    'no_attempt_lost',
];

let explorerData = null;
let selectedKeys = new Set();   // date strings for dated, lid strings for undated
let chartInstances = [];
let showPercent = true;
let displayMode = 'both';  // 'actual' | 'both' | 'predicted'
let includeAbandons = true;  // whether to include INCOMPLETE players

/* ── Stripe pattern generator for predicted bars ─────────────── */

const _patternCache = {};
function stripePattern(hexColor) {
    if (_patternCache[hexColor]) return _patternCache[hexColor];
    const c = document.createElement('canvas');
    c.width = 10; c.height = 10;
    const ctx = c.getContext('2d');
    ctx.fillStyle = hexColor;
    ctx.fillRect(0, 0, 10, 10);
    ctx.strokeStyle = 'rgba(255,255,255,0.55)';
    ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(-2, 12); ctx.lineTo(12, -2); ctx.stroke();
    const pat = ctx.createPattern(c, 'repeat');
    _patternCache[hexColor] = pat;
    return pat;
}

/* ── Hollow pattern for abandoned segments ───────────────────── */

const _hollowCache = {};
function hollowPattern(hexColor) {
    if (_hollowCache[hexColor]) return _hollowCache[hexColor];
    const c = document.createElement('canvas');
    c.width = 10; c.height = 10;
    const ctx = c.getContext('2d');
    // Light fill
    ctx.fillStyle = hexColor;
    ctx.globalAlpha = 0.18;
    ctx.fillRect(0, 0, 10, 10);
    ctx.globalAlpha = 1;
    // Dotted overlay
    ctx.strokeStyle = hexColor;
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 2]);
    ctx.beginPath(); ctx.moveTo(0, 5); ctx.lineTo(10, 5); ctx.stroke();
    const pat = ctx.createPattern(c, 'repeat');
    _hollowCache[hexColor] = pat;
    return pat;
}

/* ── Fill style for an outcome ──────────────────────────────── */

function fillForOutcome(hexColor, outcome) {
    if (outcome === 'solved') return hexColor;
    if (outcome === 'lost') return stripePattern(hexColor);
    return hollowPattern(hexColor); // incomplete / abandoned
}

/* ── Public API ─────────────────────────────────────────────────── */

export function render(data) {
    explorerData = data.puzzleExplorer;
    buildPicker();
}

/* ── Picker ─────────────────────────────────────────────────────── */

function buildPicker() {
    const grid = document.getElementById('explorer-grid');
    const dated = explorerData.puzzles || {};
    const undated = explorerData.undated_puzzles || {};
    const datedKeys = Object.keys(dated).sort();
    const undatedKeys = Object.keys(undated).sort((a, b) => {
        const da = undated[a].date || '', db = undated[b].date || '';
        return da.localeCompare(db) || a.localeCompare(b);
    });

    grid.innerHTML = '';

    // Dated puzzles (with player data)
    if (datedKeys.length) {
        const heading = document.createElement('div');
        heading.className = 'explorer-picker-heading';
        heading.innerHTML = `<span>With player data (${datedKeys.length})</span>` +
            `<span class="explorer-heading-btns">` +
            `<button class="explorer-btn-sm" data-action="select" data-group="dated">Select</button>` +
            `<button class="explorer-btn-sm" data-action="clear" data-group="dated">Clear</button>` +
            `</span>`;
        grid.appendChild(heading);
    }
    for (const d of datedKeys) {
        const p = dated[d];
        const pct = (p.solve_rate * 100).toFixed(0);
        const badgeClass = pct >= 60 ? 'badge-green' : pct >= 40 ? 'badge-amber' : 'badge-red';
        const label = document.createElement('label');
        label.className = 'explorer-chip';
        label.innerHTML = `<input type="checkbox" value="${d}" class="explorer-cb" data-type="dated">` +
            `<span class="explorer-chip-text">${p.label}: ${p.name}</span>` +
            `<span class="badge ${badgeClass}">${pct}%</span>`;
        grid.appendChild(label);
    }

    // Undated puzzles (predicted only)
    if (undatedKeys.length) {
        const heading = document.createElement('div');
        heading.className = 'explorer-picker-heading';
        heading.innerHTML = `<span>Predicted only (${undatedKeys.length})</span>` +
            `<span class="explorer-heading-btns">` +
            `<button class="explorer-btn-sm" data-action="select" data-group="undated">Select</button>` +
            `<button class="explorer-btn-sm" data-action="clear" data-group="undated">Clear</button>` +
            `</span>`;
        grid.appendChild(heading);
    }
    for (const lid of undatedKeys) {
        const p = undated[lid];
        const pct = (p.predicted_solve_rate || 0).toFixed(0);
        const badgeClass = pct >= 60 ? 'badge-green' : pct >= 40 ? 'badge-amber' : 'badge-red';
        const label = document.createElement('label');
        label.className = 'explorer-chip explorer-chip-predicted';
        label.innerHTML = `<input type="checkbox" value="${lid}" class="explorer-cb" data-type="undated">` +
            `<span class="explorer-chip-text">${p.label || p.name}</span>` +
            `<span class="badge ${badgeClass}">${pct}%</span>` +
            `<span class="explorer-pred-tag">pred</span>`;
        grid.appendChild(label);
    }

    grid.addEventListener('change', () => {
        selectedKeys = new Set(
            Array.from(grid.querySelectorAll('.explorer-cb:checked')).map(cb => cb.value)
        );
        updateContent();
    });

    document.getElementById('explorer-select-all').addEventListener('click', () => {
        grid.querySelectorAll('.explorer-cb').forEach(cb => { cb.checked = true; });
        selectedKeys = new Set([...datedKeys, ...undatedKeys]);
        updateContent();
    });

    document.getElementById('explorer-clear').addEventListener('click', () => {
        grid.querySelectorAll('.explorer-cb').forEach(cb => { cb.checked = false; });
        selectedKeys.clear();
        updateContent();
    });

    // Per-group select/clear buttons
    grid.addEventListener('click', e => {
        const btn = e.target.closest('.explorer-btn-sm');
        if (!btn) return;
        const action = btn.dataset.action;
        const group = btn.dataset.group;
        const keys = group === 'dated' ? datedKeys : undatedKeys;
        grid.querySelectorAll(`.explorer-cb[data-type="${group}"]`).forEach(cb => {
            cb.checked = action === 'select';
        });
        for (const k of keys) {
            if (action === 'select') selectedKeys.add(k);
            else selectedKeys.delete(k);
        }
        updateContent();
    });
}

/* ── Resolve selected keys to puzzle objects ────────────────────── */

function getSelectedPuzzles() {
    const dated = explorerData.puzzles || {};
    const undated = explorerData.undated_puzzles || {};
    const result = []; // [{key, puzzle, isDated}]
    for (const k of [...selectedKeys].sort()) {
        if (dated[k]) {
            result.push({ key: k, puzzle: dated[k], isDated: true });
        } else if (undated[k]) {
            result.push({ key: k, puzzle: undated[k], isDated: false });
        }
    }
    return result;
}

/* ── Compute fixed axis limits across the full dataset ──────────── */

function getAxisLimits() {
    const puzzles = explorerData.puzzles || {};
    let maxTiming = 0, maxError = 0;
    for (const p of Object.values(puzzles)) {
        if (!p.timing) continue;
        for (const v of p.timing.timing_curve) {
            if (v != null && v > maxTiming) maxTiming = v;
        }
        for (const v of p.timing.error_curve) {
            if (v != null && v > maxError) maxError = v;
        }
    }
    return {
        maxTiming: Math.ceil(maxTiming / 10) * 10,
        maxError: Math.ceil(maxError * 2) / 2,
    };
}

/* ── Content update ─────────────────────────────────────────────── */

function puzzleTitle(p) {
    const hasDateLabel = p.label && p.label !== p.name;
    return hasDateLabel ? `${p.label}: ${p.name}` : p.name;
}

function updateContent() {
    chartInstances.forEach(c => c.destroy());
    chartInstances = [];

    const container = document.getElementById('explorer-content');
    const selected = getSelectedPuzzles();

    if (selected.length === 0) {
        container.innerHTML = '<p style="color:var(--muted);padding:20px;">Select one or more puzzles above to explore.</p>';
        return;
    }

    const limits = getAxisLimits();
    let html = '';

    // ── Solve Rate Distribution ──
    html += '<div class="card" style="margin-top:20px;">';
    html += '<h3>Solve Rate Distribution</h3>';
    html += '<p style="color:var(--muted);font-size:13px;margin-bottom:12px;">';
    html += 'Distribution of solve rates across selected puzzles. Empirical rates shown solid, predicted rates shown striped.</p>';
    html += '<div class="chart-container" style="height:260px;"><canvas id="sr-dist-chart"></canvas></div>';
    html += '<div id="sr-dist-stats" style="text-align:center;margin-top:8px;font-size:13px;color:var(--muted);"></div>';
    html += '</div>';

    // ── Summary comparison table ──
    html += '<div class="card" style="margin-top:20px;"><h3>Summary</h3>';
    html += '<div style="overflow-x:auto;"><table><thead><tr>';
    html += '<th>Puzzle</th><th>Date</th><th>Players</th><th>W / L / I</th>';
    html += '<th>Solve Rate</th><th>Rating</th><th>Median Time</th>';
    html += '<th>Manip.</th><th>Abstr.</th><th>P2 Tiles</th>';
    html += '<th>Predicted</th><th>&Delta;</th><th>Mean Lives</th><th>Rows Completed</th>';
    html += '</tr></thead><tbody>';
    for (const { puzzle: p, isDated } of selected) {
        const sr = isDated ? (p.solve_rate * 100).toFixed(1) : '—';
        const predSr = p.predicted_solve_rate != null ? p.predicted_solve_rate.toFixed(1) : (p.simulator?.simulated_solve_rate?.toFixed(1) || '—');
        const delta = isDated && predSr !== '—'
            ? (parseFloat(predSr) - p.solve_rate * 100).toFixed(1) : '—';
        html += '<tr>';
        html += `<td><strong>${p.name}</strong>${isDated ? '' : ' <span class="explorer-pred-tag">pred</span>'}</td>`;
        html += `<td>${p.date || '—'}</td>`;
        html += `<td>${isDated ? p.players : '—'}</td>`;
        html += `<td>${isDated ? `${p.wins} / ${p.losses} / ${p.incomplete}` : '—'}</td>`;
        html += `<td>${isDated ? badge(sr + '%') : '—'}</td>`;
        // Difficulty rating
        const diff = p.difficulty;
        if (diff) {
            const starHtml = Array.from({length: 5}, (_, i) =>
                `<span style="color:${i < diff.rating ? '#f39c12' : '#dfe6e9'}">★</span>`).join('');
            html += `<td><span style="font-size:14px;letter-spacing:1px">${starHtml}</span></td>`;
        } else {
            html += '<td>—</td>';
        }
        html += `<td>${isDated ? p.median_time.toFixed(1) + 's' : '—'}</td>`;
        html += `<td>${p.pdl.manipulationComplexity}</td><td>${p.pdl.abstractionComplexity}</td>`;
        html += `<td>${p.pdl.phase2TileCount}</td>`;
        html += `<td>${predSr !== '—' ? badge(predSr + '%') : '—'}</td>`;
        html += `<td>${delta !== '—' ? (delta > 0 ? '+' : '') + delta + 'pp' : '—'}</td>`;
        // Mean lives at win
        const ml = p.mean_lives_at_win;
        html += `<td>${ml != null ? ml.toFixed(1) : '—'}</td>`;
        // Rows completed distribution mini bar
        const dist = p.rows_completed_pct || [];
        if (dist.length) {
            const rcColors = ['#e74c3c', '#f39c12', '#27ae60', '#2980b9', '#8e44ad'];
            let bar = '<div style="display:flex;height:16px;border-radius:3px;overflow:hidden;min-width:120px;" title="';
            bar += dist.map((v, i) => `${i === 4 ? 'Won' : i + ' rows'}: ${v.toFixed(1)}%`).join(', ');
            bar += '">';
            for (let i = 0; i <= 4; i++) {
                if (dist[i] > 0) bar += `<div style="width:${dist[i]}%;background:${rcColors[i]}"></div>`;
            }
            bar += '</div>';
            html += `<td>${bar}</td>`;
        } else {
            html += '<td>—</td>';
        }
        html += '</tr>';
    }
    html += '</tbody></table></div></div>';

    // ── Wrong-guess distribution charts (toggle: actual / both / predicted) ──
    html += '<div class="card" style="margin-top:20px;">';
    html += '<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;flex-wrap:wrap;">';
    html += '<h3 style="margin:0;">Wrong-Guess Distributions by Row</h3>';
    html += '<div class="toggle-group" id="wd-toggle">';
    html += '<button class="toggle-btn active" data-mode="pct">%</button>';
    html += '<button class="toggle-btn" data-mode="raw">Raw</button>';
    html += '</div>';
    const anyDated = selected.some(s => s.isDated);
    if (anyDated) {
        html += '<div class="toggle-group" id="dp-toggle">';
        html += `<button class="toggle-btn${displayMode === 'actual' ? ' active' : ''}" data-mode="actual">Actual</button>`;
        html += `<button class="toggle-btn${displayMode === 'both' ? ' active' : ''}" data-mode="both">Both</button>`;
        html += `<button class="toggle-btn${displayMode === 'predicted' ? ' active' : ''}" data-mode="predicted">Predicted</button>`;
        html += '</div>';
        html += '<div class="toggle-group" id="ab-toggle">';
        html += `<button class="toggle-btn${includeAbandons ? ' active' : ''}" data-mode="all">All players</button>`;
        html += `<button class="toggle-btn${!includeAbandons ? ' active' : ''}" data-mode="completed">Completed only</button>`;
        html += '</div>';
    }
    html += '</div>';
    html += '<p style="color:var(--muted);font-size:13px;margin-bottom:8px;">';
    html += 'Stacked bars show wrong guesses per row. Fill style indicates row outcome:</p>';
    html += '<div style="display:flex;gap:16px;margin-bottom:15px;font-size:12px;color:var(--muted);flex-wrap:wrap;">';
    html += '<span><span style="display:inline-block;width:14px;height:14px;background:#f39c12;border-radius:2px;vertical-align:middle;margin-right:4px;"></span> Solved</span>';
    html += '<span><span style="display:inline-block;width:14px;height:14px;background:repeating-linear-gradient(-45deg,#f39c12,#f39c12 2px,rgba(255,255,255,0.55) 2px,rgba(255,255,255,0.55) 5px);border-radius:2px;vertical-align:middle;margin-right:4px;"></span> Row unsolved (lost)</span>';
    html += '<span><span style="display:inline-block;width:14px;height:14px;background:rgba(243,156,18,0.18);border:1.5px solid #f39c12;border-radius:2px;vertical-align:middle;margin-right:4px;"></span> Row unsolved (abandoned)</span>';
    html += '</div>';
    html += '<div class="explorer-cards">';
    for (const { key, puzzle: p, isDated } of selected) {
        const safeKey = key.replace(/[^a-zA-Z0-9]/g, '');
        html += `<div class="explorer-puzzle-card">`;
        html += `<h4>${puzzleTitle(p)}${isDated ? '' : ' <span class="explorer-pred-tag">pred</span>'}</h4>`;
        html += `<div class="chart-container" style="height:260px;"><canvas id="wd-${safeKey}"></canvas></div>`;
        html += '</div>';
    }
    html += '</div></div>';

    // ── Whole-puzzle mistake distribution (toggle: actual / both / predicted) ──
    html += '<div class="card" style="margin-top:20px;">';
    html += '<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;flex-wrap:wrap;">';
    html += '<h3 style="margin:0;">Total Mistakes per Player</h3>';
    html += '<div class="toggle-group" id="md-toggle">';
    html += '<button class="toggle-btn active" data-mode="pct">%</button>';
    html += '<button class="toggle-btn" data-mode="raw">Raw</button>';
    html += '</div>';
    if (anyDated) {
        html += '<div class="toggle-group" id="dp-toggle-md">';
        html += `<button class="toggle-btn${displayMode === 'actual' ? ' active' : ''}" data-mode="actual">Actual</button>`;
        html += `<button class="toggle-btn${displayMode === 'both' ? ' active' : ''}" data-mode="both">Both</button>`;
        html += `<button class="toggle-btn${displayMode === 'predicted' ? ' active' : ''}" data-mode="predicted">Predicted</button>`;
        html += '</div>';
        html += '<div class="toggle-group" id="ab-toggle-md">';
        html += `<button class="toggle-btn${includeAbandons ? ' active' : ''}" data-mode="all">All players</button>`;
        html += `<button class="toggle-btn${!includeAbandons ? ' active' : ''}" data-mode="completed">Completed only</button>`;
        html += '</div>';
    }
    html += '</div>';
    html += '<p style="color:var(--muted);font-size:13px;margin-bottom:15px;">';
    html += 'Distribution of total wrong guesses (imposters + relink) per player.</p>';
    html += '<div class="explorer-cards">';
    for (const { key, puzzle: p, isDated } of selected) {
        const safeKey = key.replace(/[^a-zA-Z0-9]/g, '');
        const n = isDated ? (includeAbandons ? p.players : p.wins + p.losses) : null;
        const nLabel = n != null ? ` <span style="color:var(--muted);font-weight:400;font-size:12px;">(n=${n})</span>` : '';
        html += `<div class="explorer-puzzle-card">`;
        html += `<h4>${puzzleTitle(p)}${nLabel}${isDated ? '' : ' <span class="explorer-pred-tag">pred</span>'}</h4>`;
        html += `<div class="chart-container" style="height:220px;"><canvas id="md-${safeKey}"></canvas></div>`;
        html += '</div>';
    }
    html += '</div></div>';

    // ── Row detail table ── (only for puzzles with player data or PDL metadata)
    html += '<div class="card" style="margin-top:20px;"><h3>Row Details</h3>';
    html += '<div style="overflow-x:auto;"><table><thead><tr>';
    html += '<th>Puzzle</th><th>Row</th><th>Category</th><th>Manipulation</th><th>Abstraction</th>';
    html += '<th>Knowledge</th><th>Domain</th><th>Impostor</th><th>1st Try</th>';
    html += '<th>Avg Wrong</th><th>Diff.</th><th>Top Wrong</th>';
    html += '</tr></thead><tbody>';
    for (const { puzzle: p, isDated } of selected) {
        const rowSpan = isDated ? 5 : 4;
        for (let rp = 0; rp < 4; rp++) {
            const r = p.rows[String(rp)];
            if (!r) continue;
            const firstRow = rp === 0;
            html += '<tr>';
            if (firstRow) {
                html += `<td rowspan="${rowSpan}" style="vertical-align:top;font-weight:600;border-right:2px solid var(--border);">`;
                html += puzzleTitle(p);
                if (!isDated) html += '<br><span class="explorer-pred-tag">pred</span>';
                html += '</td>';
            }
            html += `<td>${rp}</td><td>${r.category || '—'}</td>`;
            html += `<td>${r.manipulation}</td><td>${r.abstraction}</td>`;
            html += `<td>${r.knowledge}</td><td>${r.knowledgeDomain || '—'}</td>`;
            html += `<td>${r.impostor_word || '—'}</td>`;
            if (isDated) {
                const topWrong = (r.top_wrong || []).slice(0, 3)
                    .map(tw => `${tw[0]} (${tw[1]})`).join(', ') || '—';
                html += `<td>${badge((r.first_try_pct * 100).toFixed(0) + '%')}</td>`;
                html += `<td>${r.avg_wrong.toFixed(2)}</td>`;
                // Row difficulty score
                const rs = p.difficulty?.row_scores?.[String(rp)];
                html += `<td>${rs ? rs.rating + '/5' : '—'}</td>`;
                html += `<td style="font-size:12px;">${topWrong}</td>`;
            } else if (r.first_try_pct != null) {
                // Predicted row stats from simulator
                html += `<td>${badge('~' + (r.first_try_pct * 100).toFixed(0) + '%')}</td>`;
                html += `<td>~${r.avg_wrong.toFixed(2)}</td>`;
                const rs = p.difficulty?.row_scores?.[String(rp)];
                html += `<td>${rs ? rs.rating + '/5' : '—'}</td>`;
                html += '<td>—</td>';
            } else {
                html += '<td>—</td><td>—</td><td>—</td><td>—</td>';
            }
            html += '</tr>';
        }
        // Relink row (only for dated puzzles with actual data)
        if (isDated) {
            const rl = p.relink;
            html += '<tr style="background:#f8f9fa;">';
            html += `<td><em>Relink</em></td><td colspan="5">${rl.answer || '—'}</td>`;
            html += '<td>—</td>';
            html += `<td>${badge((rl.first_try_pct * 100).toFixed(0) + '%')}</td>`;
            html += `<td>${rl.avg_attempts.toFixed(2)}</td>`;
            html += '<td>—</td><td>—</td>';
            html += '</tr>';
        }
    }
    html += '</tbody></table></div></div>';

    // ── Timing & Error curves (dated puzzles only) ──
    const datedSelected = selected.filter(s => s.isDated);
    if (datedSelected.length) {
        html += '<div class="card" style="margin-top:20px;"><h3>Timing &amp; Error Curves</h3>';
        html += '<p style="color:var(--muted);font-size:13px;margin-bottom:15px;">';
        html += 'Median time between correct guesses (purple, left axis) and mean wrong guesses (orange, right axis) at each solve position. ';
        html += 'Fixed axes across all puzzles for comparison. CoM &lt; 1.5 = front-loaded, &gt; 1.5 = back-loaded.</p>';
        html += '<div class="explorer-cards">';
        for (const { key, puzzle: p } of datedSelected) {
            const safeKey = key.replace(/[^a-zA-Z0-9]/g, '');
            const tm = p.timing;
            html += `<div class="explorer-puzzle-card">`;
            html += `<h4>${puzzleTitle(p)}: ${p.name}</h4>`;
            html += `<div class="chart-container" style="height:240px;"><canvas id="curve-${safeKey}"></canvas></div>`;
            html += `<p style="font-size:12px;color:var(--muted);text-align:center;">`;
            html += `Timing CoM: <strong>${tm.timing_com != null ? tm.timing_com.toFixed(3) : '—'}</strong> · `;
            html += `Error CoM: <strong>${tm.error_com != null ? tm.error_com.toFixed(3) : '—'}</strong></p>`;
            html += '</div>';
        }
        html += '</div></div>';
    }

    // ── Failure correlations (dated puzzles only) ──
    const hasAnyFailure = datedSelected.some(s =>
        s.puzzle.failure_correlations && Object.keys(s.puzzle.failure_correlations.phi_matrix).length > 0);
    if (hasAnyFailure) {
        html += '<div class="card" style="margin-top:20px;"><h3>Failure Correlations</h3>';
        html += '<p style="color:var(--muted);font-size:13px;margin-bottom:15px;">';
        html += 'Phi coefficient (&phi;) between row pairs — positive = correlated failures.</p>';
        html += '<div class="explorer-cards">';
        for (const { puzzle: p } of datedSelected) {
            const fc = p.failure_correlations;
            if (!fc || !Object.keys(fc.phi_matrix).length) continue;
            html += `<div class="explorer-puzzle-card">`;
            html += `<h4>${puzzleTitle(p)}</h4>`;
            html += renderPhiMatrix(fc);
            html += '</div>';
        }
        html += '</div></div>';
    }

    container.innerHTML = html;

    // ── Render Chart.js charts ──
    renderSolveRateDist('sr-dist-chart', selected);
    for (const { key, puzzle: p, isDated } of selected) {
        const safeKey = key.replace(/[^a-zA-Z0-9]/g, '');
        const mode = isDated ? displayMode : 'predicted';
        renderWrongDistChart(`wd-${safeKey}`, p, showPercent, mode);
        renderMistakeDistChart(`md-${safeKey}`, p, showPercent, mode);
        if (isDated) {
            renderDualCurveChart(`curve-${safeKey}`, p, limits);
        }
    }

    // ── Toggle handlers ──
    initToggle('wd-toggle', (mode) => {
        showPercent = mode === 'pct';
        syncToggle('md-toggle', mode);
        rebuildAllCharts(selected, limits);
    });
    initToggle('md-toggle', (mode) => {
        showPercent = mode === 'pct';
        syncToggle('wd-toggle', mode);
        rebuildAllCharts(selected, limits);
    });
    initToggle('dp-toggle', (mode) => {
        displayMode = mode;
        syncToggle('dp-toggle-md', mode);
        rebuildAllCharts(selected, limits);
    });
    initToggle('dp-toggle-md', (mode) => {
        displayMode = mode;
        syncToggle('dp-toggle', mode);
        rebuildAllCharts(selected, limits);
    });
    initToggle('ab-toggle', (mode) => {
        includeAbandons = mode === 'all';
        syncToggle('ab-toggle-md', mode);
        rebuildAllCharts(selected, limits);
    });
    initToggle('ab-toggle-md', (mode) => {
        includeAbandons = mode === 'all';
        syncToggle('ab-toggle', mode);
        rebuildAllCharts(selected, limits);
    });
}

function initToggle(containerId, onChange) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.addEventListener('click', (e) => {
        const btn = e.target.closest('.toggle-btn');
        if (!btn) return;
        el.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        onChange(btn.dataset.mode);
    });
}

function syncToggle(containerId, mode) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.querySelectorAll('.toggle-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.mode === mode);
    });
}

function rebuildAllCharts(selected, limits) {
    chartInstances.forEach(c => c.destroy());
    chartInstances = [];
    renderSolveRateDist('sr-dist-chart', selected);
    for (const { key, puzzle: p, isDated } of selected) {
        const safeKey = key.replace(/[^a-zA-Z0-9]/g, '');
        const mode = isDated ? displayMode : 'predicted';
        renderWrongDistChart(`wd-${safeKey}`, p, showPercent, mode);
        renderMistakeDistChart(`md-${safeKey}`, p, showPercent, mode);
        if (isDated) {
            renderDualCurveChart(`curve-${safeKey}`, p, limits);
        }
    }
}

/* ── Solve Rate Distribution chart (KDE bell curve) ──────────────── */

function gaussianKDE(values, bandwidth, xMin, xMax, nPoints) {
    const xs = [];
    const ys = [];
    const step = (xMax - xMin) / (nPoints - 1);
    const n = values.length;
    if (n === 0) return { xs, ys };
    const bw = bandwidth || Math.max(
        1.06 * Math.sqrt(values.reduce((s, v) => s + (v - values.reduce((a, b) => a + b, 0) / n) ** 2, 0) / n) * Math.pow(n, -0.2),
        3
    );
    for (let i = 0; i < nPoints; i++) {
        const x = xMin + i * step;
        let density = 0;
        for (const v of values) {
            const z = (x - v) / bw;
            density += Math.exp(-0.5 * z * z) / (bw * Math.sqrt(2 * Math.PI));
        }
        density /= n;
        xs.push(x);
        ys.push(density);
    }
    return { xs, ys };
}

function renderSolveRateDist(canvasId, selected) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    // Collect solve rates
    const points = selected.map(({ puzzle: p, isDated }) => ({
        rate: isDated ? p.solve_rate * 100 : (p.predicted_solve_rate ?? 0),
        name: p.name,
        label: p.label || p.name,
        isDated,
    }));

    const datedRates = points.filter(p => p.isDated).map(p => p.rate);
    const predRates = points.filter(p => !p.isDated).map(p => p.rate);
    const allRates = points.map(p => p.rate);

    // KDE curves — sample 200 points from 0 to 100
    const N_PTS = 200;
    const allKDE = gaussianKDE(allRates, null, 0, 100, N_PTS);
    const datedKDE = datedRates.length >= 2 ? gaussianKDE(datedRates, null, 0, 100, N_PTS) : null;
    const predKDE = predRates.length >= 2 ? gaussianKDE(predRates, null, 0, 100, N_PTS) : null;

    // Helper: look up density on a KDE curve at a given x
    function densityAt(kde, x) {
        if (!kde || !kde.xs.length) return 0;
        const step = (100 - 0) / (N_PTS - 1);
        const idx = Math.min(Math.max(Math.round(x / step), 0), N_PTS - 1);
        return kde.ys[idx];
    }

    // Summary stats
    const mean = allRates.length ? allRates.reduce((s, v) => s + v, 0) / allRates.length : 0;
    const sorted = [...allRates].sort((a, b) => a - b);
    const median = sorted.length === 0 ? 0
        : sorted.length % 2 === 0
            ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
            : sorted[Math.floor(sorted.length / 2)];

    // Place dots on the curve at their density height
    const datedScatter = points.filter(p => p.isDated)
        .map(p => ({ x: p.rate, y: densityAt(datedKDE || allKDE, p.rate), name: p.label + ': ' + p.name }));
    const predScatter = points.filter(p => !p.isDated)
        .map(p => ({ x: p.rate, y: densityAt(predKDE || allKDE, p.rate), name: p.label }));

    const datasets = [];
    const hasBothGroups = datedRates.length >= 2 && predRates.length >= 2;

    // Combined KDE curve (only when both groups present)
    if (hasBothGroups && allRates.length >= 2) {
        datasets.push({
            label: 'All selected',
            data: allKDE.xs.map((x, i) => ({ x, y: allKDE.ys[i] })),
            type: 'line',
            borderColor: hsl(0, 0, 65),
            backgroundColor: hsla(0, 0, 50, 0.06),
            borderWidth: 1.5,
            borderDash: [5, 3],
            fill: true,
            pointRadius: 0,
            tension: 0.4,
            order: 4,
        });
    }

    // Empirical KDE curve
    if (datedKDE) {
        datasets.push({
            label: 'Empirical',
            data: datedKDE.xs.map((x, i) => ({ x, y: datedKDE.ys[i] })),
            type: 'line',
            borderColor: hsl(210, 70, 50),
            backgroundColor: hsla(210, 70, 50, 0.15),
            borderWidth: 2,
            fill: true,
            pointRadius: 0,
            tension: 0.4,
            order: 3,
        });
    }

    // Predicted KDE curve
    if (predKDE) {
        datasets.push({
            label: 'Predicted',
            data: predKDE.xs.map((x, i) => ({ x, y: predKDE.ys[i] })),
            type: 'line',
            borderColor: hsl(270, 60, 55),
            backgroundColor: hsla(270, 60, 55, 0.12),
            borderWidth: 2,
            fill: true,
            pointRadius: 0,
            tension: 0.4,
            order: 3,
        });
    }

    // Scatter dots on the curve — empirical
    if (datedScatter.length) {
        datasets.push({
            label: datedKDE ? '_emp_dots' : 'Empirical',
            data: datedScatter,
            type: 'scatter',
            backgroundColor: hsl(210, 70, 50),
            borderColor: '#fff',
            borderWidth: 1.5,
            pointRadius: 5,
            pointHoverRadius: 7,
            order: 1,
        });
    }

    // Scatter dots on the curve — predicted
    if (predScatter.length) {
        datasets.push({
            label: predKDE ? '_pred_dots' : 'Predicted',
            data: predScatter,
            type: 'scatter',
            backgroundColor: hsl(270, 60, 55),
            borderColor: '#fff',
            borderWidth: 1.5,
            pointRadius: 5,
            pointStyle: 'triangle',
            pointHoverRadius: 7,
            order: 1,
        });
    }

    // Custom plugin: mean & median vertical lines inside chart area
    const verticalLines = {
        id: 'verticalLines',
        afterDatasetsDraw(chart) {
            if (!allRates.length) return;
            const { ctx: c, chartArea: { top, bottom, height }, scales: { x: xAxis } } = chart;
            const drawLine = (val, color, dashPattern, labelText, labelY) => {
                const xPx = xAxis.getPixelForValue(val);
                c.save();
                c.strokeStyle = color;
                c.lineWidth = 1.5;
                c.setLineDash(dashPattern);
                c.beginPath(); c.moveTo(xPx, top); c.lineTo(xPx, bottom); c.stroke();
                c.setLineDash([]);
                // Label inside chart, rotated
                c.fillStyle = color;
                c.font = 'bold 10px sans-serif';
                c.textAlign = 'left';
                c.translate(xPx + 4, top + 12);
                c.fillText(labelText, 0, 0);
                c.restore();
            };
            drawLine(mean, hsl(0, 70, 50), [5, 3], `Mean ${mean.toFixed(0)}%`, top + 14);
            if (Math.abs(mean - median) > 2) {
                drawLine(median, hsl(145, 60, 45), [3, 3], `Median ${median.toFixed(0)}%`, top + 14);
            }
        },
    };

    const ctx = canvas.getContext('2d');
    const chart = new Chart(ctx, {
        type: 'scatter',
        data: { datasets },
        options: {
            interaction: nearestInteraction,
            plugins: {
                tooltip: {
                    filter(item) {
                        return item.raw && item.raw.name;
                    },
                    callbacks: {
                        title(items) { return items[0]?.raw?.name || ''; },
                        label(item) {
                            return `Solve rate: ${item.raw.x.toFixed(1)}%`;
                        },
                    },
                },
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        boxWidth: 10,
                        filter(item) {
                            // Hide internal dot datasets (prefixed with _)
                            return !item.text.startsWith('_');
                        },
                    },
                },
            },
            scales: {
                x: {
                    type: 'linear',
                    min: 0,
                    max: 100,
                    title: { display: true, text: 'Solve Rate (%)' },
                    ticks: { callback: v => v + '%', stepSize: 10 },
                },
                y: {
                    beginAtZero: true,
                    ticks: { display: false },
                    grid: { display: false },
                    border: { display: false },
                },
            },
        },
        plugins: [verticalLines],
    });
    chartInstances.push(chart);

    // Stats line below chart
    const statsEl = document.getElementById('sr-dist-stats');
    if (statsEl) {
        const sd = allRates.length > 1
            ? Math.sqrt(allRates.reduce((s, v) => s + (v - mean) ** 2, 0) / (allRates.length - 1)) : 0;
        statsEl.textContent = `${allRates.length} puzzles · Mean ${mean.toFixed(1)}% · Median ${median.toFixed(1)}% · SD ${sd.toFixed(1)}pp · Range ${sorted.length ? sorted[0].toFixed(0) : 0}–${sorted.length ? sorted[sorted.length - 1].toFixed(0) : 0}%`;
    }
}

/* ── Wrong-guess distribution chart ──────────────────────────────── */
// mode: 'actual' | 'predicted' | 'both'

function renderWrongDistChart(canvasId, puzzle, asPercent, mode) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const predDist = puzzle.predicted_wrong_dist || {};
    const predLabels = puzzle.predicted_row_labels || [];
    const showActual = mode === 'actual' || mode === 'both';
    const showPred = mode === 'predicted' || mode === 'both';
    const isBoth = mode === 'both';

    // Choose actual dist field based on abandon toggle
    const distField = includeAbandons ? 'wrong_dist' : 'wrong_dist_completed';
    // Active keys for actual data (compound keys with outcome split)
    const activeKeys = includeAbandons
        ? WRONG_KEYS
        : WRONG_KEYS.filter(k => !k.endsWith('_incomplete') && k !== 'no_attempt_incomplete');
    // Predicted keys (simulator uses compound keys, no _incomplete since it doesn't model abandonment)
    const activePredKeys = PRED_KEYS;

    // Row labels
    const labels = [0, 1, 2, 3].map(i => {
        if (showActual && puzzle.rows?.[String(i)]?.category) return puzzle.rows[String(i)].category;
        if (predLabels[i]) return predLabels[i];
        return `Row ${i}`;
    }).concat(['Relink']);

    // Build per-source totals for % conversion
    const actualTotals = [0, 0, 0, 0, 0];
    const predTotals = [0, 0, 0, 0, 0];
    for (const key of activeKeys) {
        for (let rp = 0; rp < 4; rp++) {
            actualTotals[rp] += (puzzle.rows?.[String(rp)]?.[distField]?.[key] || 0);
        }
        actualTotals[4] += (puzzle.relink?.[distField]?.[key] || 0);
    }
    for (const key of activePredKeys) {
        for (let rp = 0; rp < 4; rp++) {
            predTotals[rp] += (predDist[String(rp)]?.[key] || 0);
        }
        predTotals[4] += (predDist['4']?.[key] || 0);
    }

    const datasets = [];

    // Actual datasets — compound keys with outcome-based fill styles
    if (showActual) {
        for (const key of activeKeys) {
            const color = baseColorForKey(key);
            const outcome = outcomeForKey(key);
            const raw = [];
            for (let rp = 0; rp < 4; rp++) raw.push(puzzle.rows?.[String(rp)]?.[distField]?.[key] || 0);
            raw.push(puzzle.relink?.[distField]?.[key] || 0);
            const data = asPercent
                ? raw.map((v, i) => actualTotals[i] > 0 ? +(v / actualTotals[i] * 100).toFixed(1) : 0)
                : raw;
            datasets.push({
                label: isBoth ? `${WRONG_LABELS[key]} (actual)` : WRONG_LABELS[key],
                data,
                backgroundColor: fillForOutcome(color, outcome),
                borderColor: outcome !== 'solved' ? color : undefined,
                borderWidth: outcome === 'incomplete' ? 1.5 : 0,
                stack: 'actual',
            });
        }
    }

    // Predicted datasets — compound keys with outcome-based fill styles
    if (showPred) {
        for (const key of activePredKeys) {
            const color = baseColorForKey(key);
            const outcome = outcomeForKey(key);
            const raw = [];
            for (let rp = 0; rp < 4; rp++) raw.push(predDist[String(rp)]?.[key] || 0);
            raw.push(predDist['4']?.[key] || 0);
            const data = asPercent
                ? raw.map((v, i) => predTotals[i] > 0 ? +(v / predTotals[i] * 100).toFixed(1) : 0)
                : raw;
            const baseFill = fillForOutcome(color, outcome);
            datasets.push({
                label: isBoth ? `${WRONG_LABELS[key] || key} (pred)` : (WRONG_LABELS[key] || key),
                data,
                backgroundColor: isBoth ? stripePattern(color) : baseFill,
                borderColor: outcome !== 'solved' ? color : undefined,
                borderWidth: outcome === 'incomplete' ? 1.5 : 0,
                stack: 'predicted',
            });
        }
    }

    const chart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: { labels, datasets },
        options: {
            indexAxis: 'y',
            interaction: horizontalInteraction,
            scales: {
                x: {
                    stacked: true,
                    max: asPercent ? 100 : undefined,
                    title: { display: true, text: asPercent ? '% of players' : (showPred && !showActual ? 'Simulated players' : 'Players') },
                },
                y: { stacked: true },
            },
            plugins: {
                legend: {
                    display: false,
                },
                tooltip: {
                    callbacks: {
                        label(ctx) {
                            if (asPercent) return `${ctx.dataset.label}: ${ctx.raw.toFixed(1)}%`;
                            return `${ctx.dataset.label}: ${ctx.raw}`;
                        }
                    }
                }
            },
        }
    });
    chartInstances.push(chart);
}

/* ── Whole-puzzle mistake distribution chart ─────────────────────── */
// mode: 'actual' | 'predicted' | 'both'

function renderMistakeDistChart(canvasId, puzzle, asPercent, mode) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const showActual = mode === 'actual' || mode === 'both';
    const showPred = mode === 'predicted' || mode === 'both';
    const isBoth = mode === 'both';

    // Choose actual dist based on abandon toggle
    const actualDist = includeAbandons
        ? (puzzle.mistake_dist || {})
        : (puzzle.mistake_dist_completed || puzzle.mistake_dist || {});
    const predDist = puzzle.predicted_mistake_dist || {};

    // Determine label range from whichever sources are shown
    let maxKey = 0;
    if (showActual) maxKey = Math.max(maxKey, ...Object.keys(actualDist).map(Number).filter(n => !isNaN(n)));
    if (showPred) maxKey = Math.max(maxKey, ...Object.keys(predDist).map(Number).filter(n => !isNaN(n)));
    maxKey = Math.max(maxKey, 4);
    const cap = Math.min(maxKey, 4);  // game max is 4 mistakes

    const labels = [];
    for (let i = 0; i <= cap; i++) labels.push(String(i));

    const colorForIdx = (i) => {
        if (i === 0) return '#27ae60';  // green — 0 mistakes (best)
        if (i === 1) return '#2980b9';  // blue
        if (i === 2) return '#f39c12';  // orange
        if (i === 3) return '#e74c3c';  // red
        return '#c0392b';               // dark red — 4 mistakes (worst)
    };

    const datasets = [];

    if (showActual) {
        const rawValues = labels.map(l => actualDist[l] || 0);
        const total = rawValues.reduce((a, b) => a + b, 0);
        const data = asPercent
            ? rawValues.map(v => total > 0 ? +(v / total * 100).toFixed(1) : 0)
            : rawValues;
        datasets.push({
            label: isBoth ? 'Actual' : 'Players',
            data,
            backgroundColor: labels.map((_, i) => colorForIdx(i)),
        });
    }

    if (showPred) {
        const rawValues = labels.map(l => predDist[l] || 0);
        const total = rawValues.reduce((a, b) => a + b, 0);
        const data = asPercent
            ? rawValues.map(v => total > 0 ? +(v / total * 100).toFixed(1) : 0)
            : rawValues;
        datasets.push({
            label: isBoth ? 'Predicted' : 'Simulated players',
            data,
            backgroundColor: isBoth
                ? labels.map((_, i) => stripePattern(colorForIdx(i)))
                : labels.map((_, i) => colorForIdx(i)),
        });
    }

    const chart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: { labels, datasets },
        options: {
            indexAxis: 'y',
            interaction: horizontalInteraction,
            scales: {
                x: {
                    beginAtZero: true,
                    title: { display: true, text: asPercent ? '% of players' : 'Count', font: { size: 11 } },
                },
                y: { title: { display: true, text: 'Total wrong guesses', font: { size: 11 } } },
            },
            plugins: {
                legend: { display: isBoth, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
                tooltip: {
                    callbacks: {
                        label(ctx) {
                            if (asPercent) return `${ctx.dataset.label}: ${ctx.raw.toFixed(1)}%`;
                            return `${ctx.dataset.label}: ${ctx.raw}`;
                        }
                    }
                }
            },
        }
    });
    chartInstances.push(chart);
}

/* ── Dual-axis timing + error curve chart ───────────────────────── */

function renderDualCurveChart(canvasId, puzzle, limits) {
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
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    yAxisID: 'y',
                },
                {
                    label: 'Mean wrong guesses',
                    data: tm.error_curve,
                    borderColor: COLORS[2],
                    backgroundColor: hsla(145, 60, 45, 0.12),
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    yAxisID: 'y1',
                },
            ],
        },
        options: {
            scales: {
                y: {
                    type: 'linear',
                    position: 'left',
                    beginAtZero: true,
                    max: limits.maxTiming,
                    title: { display: true, text: 'Time (s)', font: { size: 11 }, color: COLORS[0] },
                    ticks: { color: COLORS[0] },
                    grid: { drawOnChartArea: true },
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    beginAtZero: true,
                    max: limits.maxError,
                    title: { display: true, text: 'Wrong guesses', font: { size: 11 }, color: COLORS[2] },
                    ticks: { color: COLORS[2] },
                    grid: { drawOnChartArea: false },
                },
                x: { title: { display: false } },
            },
            plugins: {
                legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
            },
        }
    });
    chartInstances.push(chart);
}

/* ── Phi matrix renderer ────────────────────────────────────────── */

function renderPhiMatrix(fc) {
    const pairs = Object.keys(fc.phi_matrix).sort();
    const failRates = fc.row_failure_rates || {};

    let html = '<div style="display:flex;gap:24px;flex-wrap:wrap;">';

    html += '<div>';
    html += '<table style="font-size:12px;"><thead><tr><th>Pair</th><th>&phi;</th></tr></thead><tbody>';
    for (const pair of pairs) {
        const phi = fc.phi_matrix[pair];
        const color = phi > 0.15 ? 'var(--danger)' : phi < -0.05 ? 'var(--accent2)' : 'var(--muted)';
        html += `<tr><td>Row ${pair}</td><td style="color:${color};font-weight:600;">${phi.toFixed(3)}</td></tr>`;
    }
    html += '</tbody></table></div>';

    if (Object.keys(failRates).length) {
        html += '<div>';
        html += '<table style="font-size:12px;"><thead><tr><th>Row</th><th>Failure Rate</th></tr></thead><tbody>';
        for (const [rp, rate] of Object.entries(failRates).sort()) {
            html += `<tr><td>Row ${rp}</td><td>${(rate * 100).toFixed(1)}%</td></tr>`;
        }
        html += '</tbody></table></div>';
    }

    html += '</div>';
    return html;
}

/* ── Badge helper ───────────────────────────────────────────────── */

function badge(val) {
    const n = parseFloat(val);
    const cls = n >= 60 ? 'badge-green' : n >= 40 ? 'badge-amber' : 'badge-red';
    return `<span class="badge ${cls}" style="white-space:nowrap;">${val}</span>`;
}
