/**
 * Monte Carlo Simulator section — simulated vs actual, rows completed distributions.
 */
import { COLORS, hsla, hsl, nearestInteraction } from './charts.js';

export function render(data) {
    renderValidation(data.validation);
    renderScatter(data.puzzles);
    renderDistributions(data.puzzles);
    renderSummaryTable(data.puzzles);
    if (data.undated && Object.keys(data.undated).length > 0) {
        renderUndatedTable(data.undated);
    }
}

/* ── Validation headline ── */
function renderValidation(validation) {
    const el = document.getElementById('sim-validation');
    el.textContent = `Monte Carlo simulation (10,000 runs per puzzle): r = ${validation.r.toFixed(3)}, MAE = ${validation.mae.toFixed(1)}pp`;
}

/* ── Scatter: simulated vs actual ── */
function renderScatter(puzzles) {
    const dates = Object.keys(puzzles).sort();
    const items = dates.map(d => puzzles[d]);

    const ctx = document.getElementById('chart-sim-scatter').getContext('2d');
    new Chart(ctx, {
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
                    label: 'Perfect prediction',
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
                        title: (items) => items[0].dataIndex < dates.length ? items[items.length - 1].raw ? items[0].label : '' : '',
                        label: (ctx) => {
                            if (ctx.datasetIndex !== 0) return '';
                            const p = items[ctx.dataIndex];
                            return [
                                p.name,
                                `Simulated: ${(p.solve_rate * 100).toFixed(1)}%`,
                                `Actual: ${p.actual_solve_rate.toFixed(1)}%`,
                            ];
                        }
                    }
                }
            },
            scales: {
                x: { title: { display: true, text: 'Simulated solve rate %' }, min: 0, max: 100 },
                y: { title: { display: true, text: 'Actual solve rate %' }, min: 0, max: 100 },
            }
        }
    });
}

/* ── Rows completed distribution chart ── */
function renderDistributions(puzzles) {
    const dates = Object.keys(puzzles).sort();
    const labels = dates.map(d => puzzles[d].label || d);

    const colors = [
        '#e74c3c',    // 0 rows - red
        '#f39c12',    // 1 row - orange
        '#27ae60',    // 2 rows - green
        '#2980b9',    // 3 rows - blue
        '#8e44ad',    // 4 rows (won) - purple
    ];

    const datasets = [];
    for (let r = 0; r <= 4; r++) {
        datasets.push({
            label: r === 4 ? 'Won (4 rows + relink)' : `${r} rows`,
            data: dates.map(d => puzzles[d].rows_completed_pct[r]),
            backgroundColor: colors[r],
        });
    }

    const ctx = document.getElementById('chart-sim-dist').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: {
            plugins: {
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.raw.toFixed(1)}%`
                    }
                }
            },
            scales: {
                x: { stacked: true },
                y: { stacked: true, max: 100, title: { display: true, text: 'Percentage of simulated players' } }
            }
        }
    });
}

/* ── Summary table ── */
function renderSummaryTable(puzzles) {
    const tbody = document.querySelector('#sim-table tbody');
    const dates = Object.keys(puzzles).sort();

    for (const d of dates) {
        const p = puzzles[d];
        const simPct = (p.solve_rate * 100).toFixed(1);
        const actPct = p.actual_solve_rate.toFixed(1);
        const delta = (p.solve_rate * 100 - p.actual_solve_rate).toFixed(1);
        const absDelta = Math.abs(parseFloat(delta));
        const cls = absDelta < 10 ? 'badge-green' : absDelta < 20 ? 'badge-amber' : 'badge-red';

        tbody.innerHTML += `<tr>
            <td>${p.name}</td>
            <td>${p.label || d}</td>
            <td>${simPct}%</td>
            <td>${actPct}%</td>
            <td><span class="badge ${cls}">${delta > 0 ? '+' : ''}${delta}pp</span></td>
            <td>${p.manipulationComplexity ?? '—'}</td>
            <td>${p.abstractionComplexity ?? '—'}</td>
            <td>${p.phase2TileCount ?? '—'}</td>
            <td>${p.mean_lives_at_win ? p.mean_lives_at_win.toFixed(1) : '—'}</td>
        </tr>`;
    }
}

/* ── Undated / no-data puzzles prediction table ── */
function renderUndatedTable(undated) {
    const container = document.getElementById('sim-undated');
    if (!container) return;

    // Sort by solve rate (hardest first)
    const keys = Object.keys(undated);
    keys.sort((a, b) => undated[a].solve_rate - undated[b].solve_rate);

    let html = '<table><thead><tr><th>Puzzle</th><th>Date</th><th>Predicted Solve Rate</th><th>Manip.</th><th>Abstr.</th><th>P2 Tiles</th><th>Mean Lives</th><th>Rows Completed Distribution</th></tr></thead><tbody>';

    for (const lid of keys) {
        const p = undated[lid];
        const simPct = (p.solve_rate * 100).toFixed(1);
        const badge = p.solve_rate < 0.3 ? 'badge-red' : p.solve_rate > 0.7 ? 'badge-green' : 'badge-amber';
        const dateStr = p.date || '<em>undated</em>';

        // Mini distribution bar
        const dist = p.rows_completed_pct || [];
        const colors = ['#e74c3c', '#f39c12', '#27ae60', '#2980b9', '#8e44ad'];
        let bar = '<div style="display:flex;height:16px;border-radius:3px;overflow:hidden;min-width:120px;" title="';
        bar += dist.map((v, i) => `${i === 4 ? 'Won' : i + ' rows'}: ${v.toFixed(1)}%`).join(', ');
        bar += '">';
        for (let i = 0; i <= 4; i++) {
            if (dist[i] > 0) {
                bar += `<div style="width:${dist[i]}%;background:${colors[i]}"></div>`;
            }
        }
        bar += '</div>';

        html += `<tr>
            <td>${p.name}</td>
            <td>${dateStr}</td>
            <td><span class="badge ${badge}">${simPct}%</span></td>
            <td>${p.manipulationComplexity ?? '—'}</td>
            <td>${p.abstractionComplexity ?? '—'}</td>
            <td>${p.phase2TileCount ?? '—'}</td>
            <td>${p.mean_lives_at_win ? p.mean_lives_at_win.toFixed(1) : '—'}</td>
            <td>${bar}</td>
        </tr>`;
    }

    html += '</tbody></table>';
    container.innerHTML = html;
}
