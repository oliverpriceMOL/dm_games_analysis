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
