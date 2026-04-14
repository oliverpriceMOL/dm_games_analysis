/**
 * Puzzle & Row Clustering section.
 */
import { COLORS } from './charts.js';

export function render(clusterData) {
    const pc = clusterData.puzzles;
    const cNames = Object.keys(pc);
    const ctx1 = document.getElementById('chart-puzzle-cluster').getContext('2d');
    new Chart(ctx1, {
        type: 'bar',
        data: {
            labels: cNames,
            datasets: [
                { label: 'Puzzles', data: cNames.map(c => pc[c].n_total),
                   backgroundColor: cNames.map((_, i) => COLORS[i]) },
                { label: 'Mean Solve Rate %', data: cNames.map(c => pc[c].mean_solve_rate),
                   type: 'line', borderColor: '#d63031', backgroundColor: 'transparent',
                   yAxisID: 'y1', pointRadius: 6, borderWidth: 2 },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, title: { display: true, text: 'Count' } },
                y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false },
                       title: { display: true, text: 'Solve Rate %' } },
            }
        }
    });

    // Cluster members list
    const membersDiv = document.getElementById('cluster-members');
    cNames.forEach((c, i) => {
        membersDiv.innerHTML += `<p style="margin:5px 0;"><span style="display:inline-block;width:12px;height:12px;
            background:${COLORS[i]};border-radius:3px;margin-right:6px;vertical-align:middle;"></span>
            <strong>${c}</strong> (${pc[c].n_total} puzzles, ${pc[c].n_dated} dated):
            ${pc[c].members.slice(0, 8).join(', ')}${pc[c].members.length > 8 ? '...' : ''}</p>`;
    });

    const rc = clusterData.rows;
    const rNames = Object.keys(rc);
    const ctx2 = document.getElementById('chart-row-cluster').getContext('2d');
    new Chart(ctx2, {
        type: 'bar',
        data: {
            labels: rNames,
            datasets: [
                { label: 'First-try %', data: rNames.map(r => rc[r].mean_first_try),
                   backgroundColor: rNames.map((_, i) => COLORS[i + 3]) },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        afterBody: (items) => {
                            const r = rNames[items[0].dataIndex];
                            return `n = ${rc[r].n} rows\nAvg wrong: ${rc[r].mean_avg_wrong}`;
                        }
                    }
                }
            },
            scales: { y: { beginAtZero: true, title: { display: true, text: 'First-try correct %' } } }
        }
    });
}
