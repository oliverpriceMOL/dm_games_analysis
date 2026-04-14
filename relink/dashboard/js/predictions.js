/**
 * Difficulty Predictions section.
 */
import { hsla } from './charts.js';

export function render(predData, clusterData) {
    // Subtitle
    const subtitleEl = document.getElementById('pred-subtitle');
    subtitleEl.textContent = `Predicted solve rate for all puzzles based on row-level PDL regression. Validation: r = ${predData.validation.r}, MAE = ${predData.validation.mae}pp`;

    // Scatter: predicted vs actual
    const dated = predData.all.filter(p => p.actual !== null);
    const ctx = document.getElementById('chart-pred-scatter').getContext('2d');
    new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [
                { label: 'Puzzles', data: dated.map(p => ({ x: p.predicted, y: p.actual })),
                   backgroundColor: hsla(260, 70, 55, 0.8), pointRadius: 7, pointHoverRadius: 9 },
                { label: 'Perfect prediction', data: [{x: 0, y: 0}, {x: 100, y: 100}],
                   type: 'line', borderColor: '#b2bec3', borderDash: [6, 3],
                   pointRadius: 0, borderWidth: 1 },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            if (ctx.datasetIndex === 0) {
                                const p = dated[ctx.dataIndex];
                                return `${p.name}: predicted ${p.predicted}%, actual ${p.actual}%`;
                            }
                            return '';
                        }
                    }
                }
            },
            scales: {
                x: { title: { display: true, text: 'Predicted solve rate %' }, min: 0, max: 100 },
                y: { title: { display: true, text: 'Actual solve rate %' }, min: 0, max: 100 },
            }
        }
    });

    // Prediction table
    const tbody = document.querySelector('#pred-table tbody');
    const clusterNames = Object.keys(clusterData.puzzles);
    predData.all.sort((a, b) => a.predicted - b.predicted).forEach(p => {
        const badge = p.predicted < 30 ? 'badge-red' : p.predicted > 70 ? 'badge-green' : 'badge-amber';
        const delta = p.actual !== null ? (p.actual - p.predicted).toFixed(1) + 'pp' : '—';
        const cName = clusterNames[p.cluster] || '?';
        tbody.innerHTML += `<tr>
            <td>${p.name}</td>
            <td>${p.date || '<em>undated</em>'}</td>
            <td><span class="badge ${badge}">${p.predicted.toFixed(1)}%</span></td>
            <td>${p.actual !== null ? p.actual.toFixed(1) + '%' : '—'}</td>
            <td>${delta}</td>
            <td>${p.manipComplexity} manip / ${p.abstrComplexity} abstr</td>
            <td>${cName}</td>
        </tr>`;
    });
}
