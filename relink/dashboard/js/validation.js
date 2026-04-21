/**
 * Model Validation page — simulator accuracy, transition probabilities,
 * correlated failures, and clustering archetypes.
 */

import { COLORS, hsla, hsl, nearestInteraction } from './charts.js';
import { difficultyColor, phiColor } from './utils.js';

/* ── Public API ─────────────────────────────────────────────────── */

export function render(data) {
    const sim = data.simulator;
    const trans = data.transitions;
    const fail = data.failures;
    const clust = data.clustering;

    renderAccuracy(sim);
    renderScatter(sim.puzzles);
    renderDeltaTable(sim.puzzles);
    renderDistributions(sim.puzzles);

    if (trans) renderTransitions(trans);
    if (fail) renderFailures(fail);
    if (clust) renderClustering(clust);
}

/* ── Accuracy headline stats ──────────────────────────────────── */

function renderAccuracy(sim) {
    const v = sim.validation || {};
    const grid = document.getElementById('val-stats-grid');
    if (!grid) return;

    const puzzles = sim.puzzles || {};
    const dates = Object.keys(puzzles).sort();
    const items = dates.map(d => puzzles[d]);

    // Spearman ρ: compute rank correlation
    const n = items.length;
    let spearman = '—';
    if (n >= 3) {
        const simRates = items.map(p => p.solve_rate * 100);
        const actRates = items.map(p => p.actual_solve_rate);
        const rankOf = (arr) => {
            const sorted = arr.map((v, i) => [v, i]).sort((a, b) => a[0] - b[0]);
            const ranks = new Array(arr.length);
            sorted.forEach(([, origIdx], sortIdx) => { ranks[origIdx] = sortIdx + 1; });
            return ranks;
        };
        const rSim = rankOf(simRates);
        const rAct = rankOf(actRates);
        const d2 = rSim.reduce((s, r, i) => s + (r - rAct[i]) ** 2, 0);
        spearman = (1 - (6 * d2) / (n * (n * n - 1))).toFixed(3);
    }

    // Pairwise ordering accuracy
    let pairwiseAcc = '—';
    if (n >= 2) {
        let correct = 0, total = 0;
        for (let i = 0; i < n; i++) {
            for (let j = i + 1; j < n; j++) {
                total++;
                const simDiff = items[i].solve_rate - items[j].solve_rate;
                const actDiff = items[i].actual_solve_rate - items[j].actual_solve_rate;
                if ((simDiff > 0 && actDiff > 0) || (simDiff < 0 && actDiff < 0) || (simDiff === 0 && actDiff === 0)) {
                    correct++;
                }
            }
        }
        pairwiseAcc = total > 0 ? `${(correct / total * 100).toFixed(0)}%` : '—';
    }

    grid.innerHTML = `
        <div class="stat-card"><div class="value">${(v.r || 0).toFixed(3)}</div><div class="label">Pearson r</div></div>
        <div class="stat-card"><div class="value">${(v.mae || 0).toFixed(1)}pp</div><div class="label">MAE</div></div>
        <div class="stat-card"><div class="value">${spearman}</div><div class="label">Spearman ρ</div></div>
        <div class="stat-card"><div class="value">${pairwiseAcc}</div><div class="label">Pairwise Ordering</div></div>
    `;
}

/* ── Predicted vs Actual scatter ──────────────────────────────── */

function renderScatter(puzzles) {
    const canvas = document.getElementById('chart-val-scatter');
    if (!canvas) return;
    const dates = Object.keys(puzzles).sort();
    const items = dates.map(d => puzzles[d]);

    new Chart(canvas.getContext('2d'), {
        type: 'scatter',
        data: {
            datasets: [
                {
                    label: 'Puzzles',
                    data: items.map(p => ({ x: p.solve_rate * 100, y: p.actual_solve_rate })),
                    backgroundColor: hsla(210, 70, 50, 0.8),
                    pointRadius: 8,
                    pointHoverRadius: 10,
                },
                {
                    label: 'y = x',
                    data: [{ x: 0, y: 0 }, { x: 100, y: 100 }],
                    type: 'line',
                    borderColor: '#b2bec3',
                    borderDash: [6, 3],
                    pointRadius: 0,
                    borderWidth: 1,
                }
            ]
        },
        options: {
            interaction: nearestInteraction,
            plugins: {
                tooltip: {
                    filter: (item) => item.datasetIndex === 0,
                    callbacks: {
                        title: (tipItems) => {
                            const idx = tipItems[0].dataIndex;
                            return items[idx]?.name || '';
                        },
                        label: (ctx) => {
                            const p = items[ctx.dataIndex];
                            return [
                                `Simulated: ${(p.solve_rate * 100).toFixed(1)}%`,
                                `Actual: ${p.actual_solve_rate.toFixed(1)}%`,
                            ];
                        }
                    }
                },
                legend: { display: false },
            },
            scales: {
                x: { title: { display: true, text: 'Simulated solve rate %' }, min: 0, max: 100 },
                y: { title: { display: true, text: 'Actual solve rate %' }, min: 0, max: 100 },
            }
        }
    });
}

/* ── Delta table ──────────────────────────────────────────────── */

function renderDeltaTable(puzzles) {
    const el = document.getElementById('val-delta-table');
    if (!el) return;
    const dates = Object.keys(puzzles).sort();

    let html = '<table><thead><tr><th>Puzzle</th><th>Date</th><th>Simulated</th><th>Actual</th><th>Δ</th></tr></thead><tbody>';
    for (const d of dates) {
        const p = puzzles[d];
        const simPct = (p.solve_rate * 100).toFixed(1);
        const actPct = p.actual_solve_rate.toFixed(1);
        const delta = (p.solve_rate * 100 - p.actual_solve_rate).toFixed(1);
        const absDelta = Math.abs(parseFloat(delta));
        const cls = absDelta < 10 ? 'badge-green' : absDelta < 20 ? 'badge-amber' : 'badge-red';
        html += `<tr><td>${p.name}</td><td>${p.label || d}</td><td>${simPct}%</td><td>${actPct}%</td>`;
        html += `<td><span class="badge ${cls}">${parseFloat(delta) > 0 ? '+' : ''}${delta}pp</span></td></tr>`;
    }
    html += '</tbody></table>';
    el.innerHTML = html;
}

/* ── Rows completed distribution ──────────────────────────────── */

function renderDistributions(puzzles) {
    const canvas = document.getElementById('chart-val-dist');
    if (!canvas) return;
    const dates = Object.keys(puzzles).sort();
    const labels = dates.map(d => puzzles[d].label || d);
    const colors = ['#e74c3c', '#f39c12', '#27ae60', '#2980b9', '#8e44ad'];

    const datasets = [];
    for (let r = 0; r <= 4; r++) {
        datasets.push({
            label: r === 4 ? 'Won (4 rows + relink)' : `${r} rows`,
            data: dates.map(d => puzzles[d].rows_completed_pct[r]),
            backgroundColor: colors[r],
        });
    }

    new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: { labels, datasets },
        options: {
            plugins: { tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.raw.toFixed(1)}%` } } },
            scales: {
                x: { stacked: true },
                y: { stacked: true, max: 100, title: { display: true, text: '% of simulated players' } },
            }
        }
    });
}

/* ── Transitions ──────────────────────────────────────────────── */

function renderTransitions(data) {
    // N observations label
    const nEl = document.getElementById('trans-n');
    if (nEl) nEl.textContent = `Based on ${data.n_observations.toLocaleString()} IPW-weighted observations.`;

    renderPositionLives(data.by_position_lives);
    renderPdlFeatures(data.by_pdl_feature);
    renderDecoyEffect(data.by_decoy);
}

function renderPositionLives(byPosLives) {
    const container = document.getElementById('pos-lives-grid');
    if (!container) return;
    const positions = [0, 1, 2, 3];
    const livesVals = [1, 2, 3, 4];
    const posLabels = ['1st row', '2nd row', '3rd row', '4th row'];

    container.style.gridTemplateColumns = `80px repeat(${positions.length}, 1fr)`;
    container.innerHTML = '<div class="hm-header"></div>';
    positions.forEach((_, i) => { container.innerHTML += `<div class="hm-header">${posLabels[i]}</div>`; });

    for (const lives of livesVals.slice().reverse()) {
        container.innerHTML += `<div class="hm-header">${lives} ${lives === 1 ? 'life' : 'lives'}</div>`;
        for (const pos of positions) {
            const key = `${pos},${lives}`;
            const cell = byPosLives[key];
            if (cell && cell.n >= 5) {
                const pct = (cell.weighted_first_try * 100).toFixed(0);
                const bg = difficultyColor(cell.weighted_first_try);
                container.innerHTML += `<div class="hm-cell" style="background:${bg}" title="n=${cell.n}, mean wrong=${cell.weighted_mean_wrong.toFixed(2)}">${pct}%<br><span style="font-size:10px;opacity:0.8">n=${cell.n}</span></div>`;
            } else {
                container.innerHTML += `<div class="hm-cell" style="background:#dfe6e9;color:var(--muted)">${cell ? 'n=' + cell.n : '—'}</div>`;
            }
        }
    }
}

function renderPdlFeatures(byFeature) {
    const container = document.getElementById('trans-pdl-charts');
    if (!container) return;
    const featureLabels = {
        manipulation: 'By Manipulation Type',
        abstraction: 'By Abstraction Type',
        knowledge: 'By Knowledge Level',
        same_domain: 'By Same Domain'
    };

    for (const [feat, label] of Object.entries(featureLabels)) {
        const vals = byFeature[feat];
        if (!vals) continue;
        const keys = Object.keys(vals);
        const labels = keys.map(k => k === 'True' ? 'Same domain' : k === 'False' ? 'Different domain' : k);
        const firstTry = keys.map(k => (vals[k].weighted_first_try * 100));
        const meanWrong = keys.map(k => vals[k].weighted_mean_wrong);
        const ns = keys.map(k => vals[k].n);

        const canvasId = `trans-chart-${feat}`;
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `<h3>${label} (IPW-weighted)</h3><div class="chart-container"><canvas id="${canvasId}"></canvas></div>`;
        container.appendChild(card);

        new Chart(document.getElementById(canvasId).getContext('2d'), {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    { label: 'First-try correct %', data: firstTry.map(v => v.toFixed(1)),
                      backgroundColor: hsla(210, 70, 50, 0.7), yAxisID: 'y' },
                    { label: 'Avg wrong guesses', data: meanWrong.map(v => v.toFixed(2)),
                      backgroundColor: hsla(0, 70, 55, 0.7), yAxisID: 'y1' },
                ]
            },
            options: {
                plugins: { tooltip: { callbacks: { footer: (items) => `n = ${ns[items[0].dataIndex]} observations` } } },
                scales: {
                    y: { beginAtZero: true, position: 'left', title: { display: true, text: 'First-try %' } },
                    y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Avg wrong' } },
                }
            }
        });
    }
}

function renderDecoyEffect(byDecoy) {
    const noDecoy = byDecoy['False'];
    const hasDecoy = byDecoy['True'];
    if (!noDecoy || !hasDecoy) return;

    const canvas = document.getElementById('trans-chart-decoy');
    if (!canvas) return;
    new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels: ['No decoy involvement', 'In decoy group'],
            datasets: [{
                label: 'First-try correct %',
                data: [(noDecoy.weighted_first_try * 100).toFixed(1), (hasDecoy.weighted_first_try * 100).toFixed(1)],
                backgroundColor: [hsla(145, 60, 45, 0.7), hsla(0, 70, 55, 0.7)],
            }]
        },
        options: {
            plugins: { tooltip: { callbacks: { footer: (items) => {
                const d = items[0].dataIndex === 0 ? noDecoy : hasDecoy;
                return `n = ${d.n} obs · mean wrong = ${d.weighted_mean_wrong.toFixed(2)}`;
            } } } },
            scales: { y: { beginAtZero: true, max: 100, title: { display: true, text: 'First-try correct %' } } }
        }
    });
}

/* ── Correlated Failures ──────────────────────────────────────── */

function renderFailures(data) {
    const nEl = document.getElementById('failures-n');
    if (nEl) nEl.textContent = `${data.n_pairs} row-pair observations across ${Object.keys(data.per_puzzle).length} puzzles.`;

    renderAggregate(data.aggregate);
    renderPerPuzzle(data.per_puzzle);
}

function renderAggregate(aggregate) {
    const container = document.getElementById('failure-aggregate');
    if (!container) return;
    const features = {
        same_manipulation: 'Same Manipulation Type',
        same_abstraction: 'Same Abstraction Type',
        same_domain: 'Same Knowledge Domain'
    };

    let html = '<table><thead><tr><th>Feature</th><th>Same</th><th>Different</th><th>Difference</th></tr></thead><tbody>';
    for (const [key, label] of Object.entries(features)) {
        const d = aggregate[key];
        if (!d) continue;
        const samePhi = d.same.mean_phi;
        const diffPhi = d.different.mean_phi;
        const delta = samePhi - diffPhi;
        const arrow = delta > 0.02 ? '↑' : delta < -0.02 ? '↓' : '≈';
        const cls = delta > 0.02 ? 'badge-red' : delta < -0.02 ? 'badge-green' : 'badge-amber';
        html += `<tr><td><strong>${label}</strong></td>`;
        html += `<td>φ = ${samePhi.toFixed(3)} <span style="color:var(--muted)">(n=${d.same.n})</span></td>`;
        html += `<td>φ = ${diffPhi.toFixed(3)} <span style="color:var(--muted)">(n=${d.different.n})</span></td>`;
        html += `<td><span class="badge ${cls}">${arrow} ${Math.abs(delta).toFixed(3)}</span></td></tr>`;
    }
    html += '</tbody></table>';
    html += '<p style="color:var(--muted);font-size:12px;margin-top:10px;">Higher φ = rows tend to be failed together. Positive difference = sharing this feature increases correlated failure.</p>';
    container.innerHTML = html;
}

function renderPerPuzzle(perPuzzle) {
    const container = document.getElementById('failure-puzzles');
    if (!container) return;
    const dates = Object.keys(perPuzzle).sort();

    for (const date of dates) {
        const pz = perPuzzle[date];
        const card = document.createElement('div');
        card.className = 'card';

        const d = new Date(date + 'T00:00:00');
        const label = d.toLocaleDateString('en-GB', { month: 'short', day: 'numeric' });
        const cats = pz.row_categories || {};
        const rowName = (r) => cats[r] || `Row ${r + 1}`;

        let html = `<h3>${pz.name} <span style="color:var(--muted);font-weight:400">(${label}, n=${pz.n_players})</span></h3>`;
        html += '<div style="margin-bottom:12px;font-size:12px;">';
        for (let r = 0; r < 4; r++) {
            const rate = pz.row_failure_rates[r];
            if (rate === undefined) continue;
            const pct = (rate * 100).toFixed(0);
            const cls = rate > 0.5 ? 'badge-red' : rate > 0.3 ? 'badge-amber' : 'badge-green';
            html += `<span class="badge ${cls}" style="margin-right:6px">${rowName(r)}: ${pct}% fail</span>`;
        }
        html += '</div>';

        // 4×4 phi matrix
        html += '<div class="confusion-grid" style="grid-template-columns: 90px repeat(4, 90px);">';
        html += '<div class="confusion-cell confusion-header"></div>';
        for (let c = 0; c < 4; c++) html += `<div class="confusion-cell confusion-header" title="${rowName(c)}">${rowName(c)}</div>`;
        for (let r = 0; r < 4; r++) {
            html += `<div class="confusion-cell confusion-header" title="${rowName(r)}">${rowName(r)}</div>`;
            for (let c = 0; c < 4; c++) {
                if (r === c) {
                    html += '<div class="confusion-cell" style="background:#f8f9fa;color:var(--muted)">—</div>';
                } else {
                    const key = r < c ? `${r}-${c}` : `${c}-${r}`;
                    const phi = pz.phi_matrix[key];
                    if (phi !== undefined) {
                        const bg = phiColor(phi);
                        html += `<div class="confusion-cell" style="background:${bg};color:#fff" title="φ = ${phi.toFixed(3)}">${phi.toFixed(2)}</div>`;
                    } else {
                        html += '<div class="confusion-cell" style="background:#f8f9fa;color:var(--muted)">—</div>';
                    }
                }
            }
        }
        html += '</div>';
        card.innerHTML = html;
        container.appendChild(card);
    }
}

/* ── Clustering ───────────────────────────────────────────────── */

function renderClustering(clusterData) {
    // Puzzle clusters
    const pc = clusterData.puzzles;
    const cNames = Object.keys(pc);
    const ctx1 = document.getElementById('chart-puzzle-cluster');
    if (ctx1) {
        new Chart(ctx1.getContext('2d'), {
            type: 'bar',
            data: {
                labels: cNames,
                datasets: [
                    { label: 'Puzzles', data: cNames.map(c => pc[c].n_total), backgroundColor: cNames.map((_, i) => COLORS[i]) },
                    { label: 'Mean Solve Rate %', data: cNames.map(c => pc[c].mean_solve_rate),
                      type: 'line', borderColor: '#e74c3c', backgroundColor: 'transparent', yAxisID: 'y1', pointRadius: 6, borderWidth: 2 },
                ]
            },
            options: {
                plugins: { tooltip: { callbacks: { footer: (items) => {
                    const c = cNames[items[0].dataIndex];
                    return `${pc[c].n_dated} dated · Members: ${pc[c].members.slice(0, 4).join(', ')}${pc[c].members.length > 4 ? '…' : ''}`;
                } } } },
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: 'Count' } },
                    y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Solve Rate %' } },
                }
            }
        });
    }

    // Cluster members
    const membersDiv = document.getElementById('cluster-members');
    if (membersDiv) {
        cNames.forEach((c, i) => {
            membersDiv.innerHTML += `<p style="margin:5px 0;"><span style="display:inline-block;width:12px;height:12px;background:${COLORS[i]};border-radius:3px;margin-right:6px;vertical-align:middle;"></span><strong>${c}</strong> (${pc[c].n_total} puzzles, ${pc[c].n_dated} dated): ${pc[c].members.slice(0, 8).join(', ')}${pc[c].members.length > 8 ? '...' : ''}</p>`;
        });
    }

    // Row clusters
    const rc = clusterData.rows;
    const rNames = Object.keys(rc);
    const ctx2 = document.getElementById('chart-row-cluster');
    if (ctx2) {
        new Chart(ctx2.getContext('2d'), {
            type: 'bar',
            data: {
                labels: rNames,
                datasets: [{ label: 'First-try %', data: rNames.map(r => rc[r].mean_first_try), backgroundColor: rNames.map((_, i) => COLORS[i + 3]) }]
            },
            options: {
                plugins: { tooltip: { callbacks: { footer: (items) => {
                    const r = rNames[items[0].dataIndex];
                    return `n = ${rc[r].n} rows · Avg wrong: ${rc[r].mean_avg_wrong}`;
                } } } },
                scales: { y: { beginAtZero: true, title: { display: true, text: 'First-try correct %' } } }
            }
        });
    }
}
