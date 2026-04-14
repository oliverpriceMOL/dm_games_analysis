/**
 * Decoy Analysis section.
 */
import { hsla } from './charts.js';

export function render(decoyData) {
    const ctx = document.getElementById('chart-decoy-compare').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['No Decoys', 'Has Decoys'],
            datasets: [
                { label: 'Mean Solve Rate %', data: [
                    (decoyData.no_decoys.mean_solve_rate * 100).toFixed(1),
                    (decoyData.has_decoys.mean_solve_rate * 100).toFixed(1)],
                   backgroundColor: [hsla(260,70,55,0.7), hsla(170,70,45,0.7)] },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        afterBody: (items) => {
                            const i = items[0].dataIndex;
                            const d = i === 0 ? decoyData.no_decoys : decoyData.has_decoys;
                            return `n = ${d.n} puzzles\nAvg wrong/row: ${d.mean_avg_wrong.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: { y: { beginAtZero: true, title: { display: true, text: 'Solve Rate %' } } }
        }
    });

    const hits = decoyData.hit_analysis;
    if (hits.length > 0) {
        const ctx2 = document.getElementById('chart-decoy-hits').getContext('2d');
        new Chart(ctx2, {
            type: 'bar',
            data: {
                labels: hits.map(h => h.label + ' ' + h.name.substring(0, 15)),
                datasets: [
                    { label: 'Decoy-matching wrong guesses', data: hits.map(h => h.decoy_wrong),
                       backgroundColor: hsla(0,65,50,0.7) },
                    { label: 'Other wrong guesses', data: hits.map(h => h.total_wrong - h.decoy_wrong),
                       backgroundColor: hsla(220,30,70,0.5) },
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: { x: { stacked: true }, y: { stacked: true,
                    title: { display: true, text: 'Wrong guesses' } } },
                plugins: {
                    tooltip: {
                        callbacks: {
                            afterBody: (items) => {
                                const i = items[0].dataIndex;
                                return `Hit rate: ${(hits[i].hit_rate * 100).toFixed(0)}%\nDecoys: ${hits[i].descriptions.join('; ')}`;
                            }
                        }
                    }
                }
            }
        });
    }
}
