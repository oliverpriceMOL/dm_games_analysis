/**
 * Relink Phase PDL section.
 */
import { hsla } from './charts.js';

export function render(relinkData) {
    const byM = relinkData.by_manip;
    const mLabels = Object.keys(byM);
    const ctx1 = document.getElementById('chart-relink-manip').getContext('2d');
    new Chart(ctx1, {
        type: 'bar',
        data: {
            labels: mLabels,
            datasets: [
                { label: 'First-try %', data: mLabels.map(l => (byM[l].mean_first_try * 100).toFixed(1)),
                   backgroundColor: hsla(260,70,55,0.7) },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        afterBody: (items) => {
                            const l = items[0].label;
                            return `n = ${byM[l].n} puzzles\nAvg attempts: ${byM[l].mean_attempts.toFixed(1)}`;
                        }
                    }
                }
            },
            scales: { y: { beginAtZero: true, title: { display: true, text: 'Relink first-try %' } } }
        }
    });

    const byT = relinkData.by_tiles;
    const tLabels = Object.keys(byT).sort();
    const ctx2 = document.getElementById('chart-relink-tiles').getContext('2d');
    new Chart(ctx2, {
        type: 'bar',
        data: {
            labels: tLabels.map(t => t + ' tile' + (t === '1' ? '' : 's')),
            datasets: [
                { label: 'Relink first-try %', data: tLabels.map(t => (byT[t].mean_first_try * 100).toFixed(1)),
                   backgroundColor: hsla(260, 70, 55, 0.7), yAxisID: 'y' },
                { label: 'Puzzle solve rate %', data: tLabels.map(t => (byT[t].mean_solve_rate * 100).toFixed(1)),
                   backgroundColor: hsla(170, 70, 45, 0.7), yAxisID: 'y' },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: { y: { beginAtZero: true, title: { display: true, text: '%' } } },
            plugins: {
                tooltip: {
                    callbacks: {
                        afterBody: (items) => {
                            const t = tLabels[items[0].dataIndex];
                            return `n = ${byT[t].n} puzzles\nAvg attempts: ${byT[t].mean_attempts.toFixed(1)}`;
                        }
                    }
                }
            }
        }
    });
}
