/**
 * Relink Phase PDL section.
 */
import { hsla } from './charts.js';

export function render(relinkData) {
    // Connection Identification manipulation chart
    _renderManipChart(
        relinkData.by_id_manip,
        document.getElementById('chart-relink-id-manip'),
        'Relink first-try %', hsla(210, 70, 50, 0.7));

    // Answer Construction manipulation chart
    _renderManipChart(
        relinkData.by_con_manip,
        document.getElementById('chart-relink-con-manip'),
        'Relink first-try %', hsla(270, 60, 55, 0.7));

    // By tile count chart
    const byT = relinkData.by_tiles;
    const tLabels = Object.keys(byT).sort();
    const ctx = document.getElementById('chart-relink-tiles').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: tLabels.map(t => t + ' tile' + (t === '1' ? '' : 's')),
            datasets: [
                { label: 'Relink first-try %', data: tLabels.map(t => (byT[t].mean_first_try * 100).toFixed(1)),
                   backgroundColor: hsla(210, 70, 50, 0.7), yAxisID: 'y' },
                { label: 'Puzzle solve rate %', data: tLabels.map(t => (byT[t].mean_solve_rate * 100).toFixed(1)),
                   backgroundColor: hsla(145, 60, 45, 0.7), yAxisID: 'y' },
            ]
        },
        options: {
            scales: { y: { beginAtZero: true, title: { display: true, text: '%' } } },
            plugins: {
                tooltip: {
                    callbacks: {
                        footer: (items) => {
                            const t = tLabels[items[0].dataIndex];
                            return `n = ${byT[t].n} puzzles · Avg attempts: ${byT[t].mean_attempts.toFixed(1)}`;
                        }
                    }
                }
            }
        }
    });
}

function _renderManipChart(byM, canvas, yLabel, color) {
    const mLabels = Object.keys(byM);
    const ctx = canvas.getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: mLabels,
            datasets: [
                { label: 'First-try %', data: mLabels.map(l => (byM[l].mean_first_try * 100).toFixed(1)),
                   backgroundColor: color },
            ]
        },
        options: {
            plugins: {
                tooltip: {
                    callbacks: {
                        footer: (items) => {
                            const l = items[0].label;
                            return `n = ${byM[l].n} puzzles · Avg attempts: ${byM[l].mean_attempts.toFixed(1)}`;
                        }
                    }
                }
            },
            scales: { y: { beginAtZero: true, title: { display: true, text: yLabel } } }
        }
    });
}
