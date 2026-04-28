/**
 * Overview page — headline stats, solve rate trend, key takeaways.
 */

import { COLORS, hsla } from './charts.js';

export function render(overview) {
    const el = document.getElementById('subtitle');
    el.textContent = `${overview.n_puzzles} puzzles analysed · ${overview.n_dated} with player data · ${overview.total_completions} total completions`;

    // Headline stat cards
    const grid = document.getElementById('stats-grid');
    const datesArr = overview.dates || [];
    const solveRates = datesArr.map(d => d.solve_rate);
    const playerCounts = datesArr.map(d => d.players || 0);
    const minSr = datesArr.length ? Math.min(...solveRates) : 0;
    const maxSr = datesArr.length ? Math.max(...solveRates) : 0;
    const minPlayers = datesArr.length ? Math.min(...playerCounts) : 0;
    const maxPlayers = datesArr.length ? Math.max(...playerCounts) : 0;

    const findings = [
        { value: overview.n_dated, label: 'Puzzles with player data' },
        { value: overview.total_completions, label: 'Total completions' },
        { value: `${minPlayers}–${maxPlayers}`, label: 'Daily player range' },
        { value: `${minSr.toFixed(0)}–${maxSr.toFixed(0)}%`, label: 'Solve rate range' },
    ];
    grid.innerHTML = '';
    findings.forEach(f => {
        grid.innerHTML += `<div class="stat-card"><div class="value">${f.value}</div><div class="label">${f.label}</div></div>`;
    });

    // Solve rate trend chart
    if (datesArr.length > 0) {
        const ctx = document.getElementById('chart-solve-trend').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: datesArr.map(d => d.label || d.date),
                datasets: [
                    {
                        label: 'Solve Rate %',
                        data: solveRates.map(v => v.toFixed(1)),
                        backgroundColor: solveRates.map(v =>
                            v >= 60 ? hsla(145, 60, 45, 0.7) : v >= 40 ? hsla(35, 90, 55, 0.7) : hsla(0, 70, 55, 0.7)
                        ),
                        yAxisID: 'y',
                    },
                    {
                        label: 'Players',
                        data: playerCounts,
                        type: 'line',
                        borderColor: COLORS[3],
                        backgroundColor: 'transparent',
                        yAxisID: 'y1',
                        pointRadius: 4,
                        borderWidth: 2,
                        tension: 0.3,
                    },
                ]
            },
            options: {
                plugins: {
                    tooltip: {
                        callbacks: {
                            footer: (items) => {
                                const d = datesArr[items[0].dataIndex];
                                return `${d.wins ?? '?'}W / ${d.losses ?? '?'}L`;
                            }
                        }
                    }
                },
                scales: {
                    y: { beginAtZero: true, max: 100, title: { display: true, text: 'Solve Rate %' } },
                    y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false },
                          title: { display: true, text: 'Players' } },
                }
            }
        });
    }

    // Solve rate distribution histogram
    if (overview.solve_rate_distribution) {
        renderDistribution(overview.solve_rate_distribution);
    }

    // Key takeaways
    const takeaways = document.getElementById('takeaways-content');
    if (datesArr.length > 0) {
        const easiest = datesArr.reduce((a, b) => a.solve_rate > b.solve_rate ? a : b);
        const hardest = datesArr.reduce((a, b) => a.solve_rate < b.solve_rate ? a : b);
        takeaways.innerHTML = `<ul style="padding-left:20px;color:var(--text);line-height:2;">
            <li>Solve rates ranged from <strong>${hardest.solve_rate.toFixed(0)}%</strong> (${hardest.label}: ${hardest.name}) to <strong>${easiest.solve_rate.toFixed(0)}%</strong> (${easiest.label}: ${easiest.name})</li>
            <li>Player counts grew from ~${minPlayers}/day to ~${maxPlayers}/day over the test period</li>
            <li>${overview.n_puzzles - overview.n_dated} additional puzzles have predicted difficulty ratings but no player data yet</li>
        </ul>`;
    }
}

// Gaussian KDE over solve-rate values [0..100]. Bandwidth via Silverman's rule
// (h = 1.06 * std * n^(-1/5)), floored to keep small samples readable.
function kdeCurve(values, xs) {
    if (!values.length) return xs.map(() => 0);
    const n = values.length;
    const mean = values.reduce((a, b) => a + b, 0) / n;
    const variance = values.reduce((a, b) => a + (b - mean) ** 2, 0) / n;
    const std = Math.sqrt(variance);
    const h = Math.max(1.06 * std * Math.pow(n, -1 / 5), 4);
    const norm = 1 / (n * h * Math.sqrt(2 * Math.PI));
    return xs.map(x => {
        let sum = 0;
        for (const v of values) {
            const z = (x - v) / h;
            sum += Math.exp(-0.5 * z * z);
        }
        return norm * sum;
    });
}

function gradientByX(ctx, area) {
    const g = ctx.createLinearGradient(area.left, 0, area.right, 0);
    g.addColorStop(0.00, hsla(0, 70, 55, 0.45));
    g.addColorStop(0.40, hsla(0, 70, 55, 0.45));
    g.addColorStop(0.50, hsla(35, 90, 55, 0.45));
    g.addColorStop(0.60, hsla(145, 60, 45, 0.45));
    g.addColorStop(1.00, hsla(145, 60, 45, 0.45));
    return g;
}

function renderDistribution(data) {
    const canvas = document.getElementById('chart-solve-distribution');
    if (!canvas) return;
    const actual = data.actual || [];
    const predicted = data.predicted || [];

    const buttons = document.querySelectorAll('#dist-toggle .toggle-btn');
    const counts = { actual: actual.length, predicted: predicted.length,
                      both: actual.length + predicted.length };
    buttons.forEach(b => {
        const txt = b.textContent.replace(/\s*\(\d+\)$/, '');
        b.textContent = `${txt} (${counts[b.dataset.mode]})`;
    });

    const sources = {
        actual,
        predicted,
        both: actual.concat(predicted),
    };

    const xs = Array.from({ length: 101 }, (_, i) => i);

    function curveFor(mode) {
        return kdeCurve(sources[mode].map(p => p.solve_rate), xs);
    }

    let currentMode = 'both';

    const chart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            labels: xs,
            datasets: [{
                label: 'Density',
                data: curveFor(currentMode),
                borderColor: 'rgba(60,60,80,0.85)',
                borderWidth: 2,
                fill: true,
                backgroundColor: (ctx) => {
                    const { chart } = ctx;
                    const area = chart.chartArea;
                    if (!area) return 'rgba(0,0,0,0.1)';
                    return gradientByX(chart.ctx, area);
                },
                tension: 0.35,
                pointRadius: 0,
                pointHoverRadius: 4,
            }],
        },
        options: {
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        title: (items) => `${items[0].label}% solve rate`,
                        label: () => '',
                        afterBody: (items) => {
                            const x = Number(items[0].label);
                            const window = 5;
                            const near = sources[currentMode]
                                .filter(p => Math.abs(p.solve_rate - x) <= window)
                                .sort((a, b) => Math.abs(a.solve_rate - x) - Math.abs(b.solve_rate - x));
                            if (!near.length) return ['(no puzzles within ±5%)'];
                            const top = near.slice(0, 4).map(p =>
                                `  ${p.label ? p.label + ': ' : ''}${p.name} (${p.solve_rate.toFixed(0)}%)`);
                            const more = near.length > 4 ? [`  …and ${near.length - 4} more within ±5%`] : [];
                            return ['Within ±5%:', ...top, ...more];
                        },
                    },
                },
            },
            scales: {
                x: {
                    type: 'linear',
                    min: 0,
                    max: 100,
                    title: { display: true, text: 'Solve rate (%)' },
                    ticks: { stepSize: 10 },
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Density' },
                    ticks: { display: false },
                },
            },
            interaction: { mode: 'index', intersect: false },
        },
    });

    function setMode(mode) {
        currentMode = mode;
        chart.data.datasets[0].data = curveFor(mode);
        chart.update();
        buttons.forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
    }

    buttons.forEach(b => {
        b.addEventListener('click', () => setMode(b.dataset.mode));
    });
}
