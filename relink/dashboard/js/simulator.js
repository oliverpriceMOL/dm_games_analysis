/**
 * Monte Carlo Simulator section — simulated vs actual, rows completed distributions.
 */
import { COLORS, hsla, hsl } from './charts.js';

export function render(data) {
    renderValidation(data.validation);
    renderScatter(data.puzzles);
    renderDistributions(data.puzzles);
    renderSummaryTable(data.puzzles);
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
                    backgroundColor: hsla(160, 70, 40, 0.8),
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
            responsive: true, maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            if (ctx.datasetIndex === 0) {
                                const p = items[ctx.dataIndex];
                                return `${p.name}: simulated ${(p.solve_rate * 100).toFixed(1)}%, actual ${p.actual_solve_rate.toFixed(1)}%`;
                            }
                            return '';
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
        hsla(0, 70, 50, 0.8),    // 0 rows - red
        hsla(30, 70, 50, 0.8),   // 1 row - orange
        hsla(50, 70, 50, 0.8),   // 2 rows - yellow
        hsla(90, 50, 45, 0.8),   // 3 rows - light green
        hsla(160, 70, 40, 0.8),  // 4 rows (won) - green
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
            responsive: true, maintainAspectRatio: false,
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
            <td>${p.mean_lives_at_win ? p.mean_lives_at_win.toFixed(1) : '—'}</td>
            <td>${p.n_sims.toLocaleString()}</td>
        </tr>`;
    }
}
