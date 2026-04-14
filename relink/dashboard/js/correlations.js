/**
 * Scatter plot correlations section.
 */
import { hsla } from './charts.js';

export function render(scatterData) {
    const container = document.getElementById('scatter-container');
    const feats = Object.keys(scatterData);

    // Build DOM
    feats.forEach((feat, fi) => {
        const d = scatterData[feat];
        const cardId = `scatter-${fi}`;
        container.innerHTML += `<div class="card"><h3>${d.label} vs Solve Rate</h3>
            <p style="color:var(--muted);font-size:12px;">Pearson r=${d.pearson_r} · Spearman ρ=${d.spearman_r}</p>
            <div class="chart-container"><canvas id="${cardId}"></canvas></div></div>`;
    });

    // Render charts
    feats.forEach((feat, fi) => {
        const d = scatterData[feat];
        const ctx = document.getElementById(`scatter-${fi}`).getContext('2d');
        const pts = d.xs.map((x, i) => ({ x, y: d.ys[i] }));
        const n = d.xs.length;
        const mx = d.xs.reduce((a,b) => a+b, 0) / n;
        const my = d.ys.reduce((a,b) => a+b, 0) / n;
        const ssxy = d.xs.reduce((s, x, i) => s + (x - mx) * (d.ys[i] - my), 0);
        const ssxx = d.xs.reduce((s, x) => s + (x - mx) ** 2, 0);
        const slope = ssxx ? ssxy / ssxx : 0;
        const intercept = my - slope * mx;
        const xMin = Math.min(...d.xs) - 0.5;
        const xMax = Math.max(...d.xs) + 0.5;

        const allInt = d.xs.every(x => Number.isInteger(x));
        const xScale = allInt ? {
            title: { display: true, text: d.label },
            min: Math.min(...d.xs) - 0.3,
            max: Math.max(...d.xs) + 0.3,
            ticks: { stepSize: 1, callback: (v) => Number.isInteger(v) ? v : '' }
        } : {
            title: { display: true, text: d.label },
        };

        new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [
                    { label: 'Puzzles', data: pts, backgroundColor: hsla(260,70,55,0.8),
                       pointRadius: 6, pointHoverRadius: 8 },
                    { label: 'Trend', data: [{x: xMin, y: intercept + slope * xMin},
                                               {x: xMax, y: intercept + slope * xMax}],
                       type: 'line', borderColor: hsla(0,70,55,0.5), borderDash: [6,3],
                       pointRadius: 0, borderWidth: 2 },
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                if (ctx.datasetIndex === 0) {
                                    const i = ctx.dataIndex;
                                    return `${d.labels[i]}: ${d.ys[i]}% solve rate`;
                                }
                                return '';
                            }
                        }
                    }
                },
                scales: {
                    x: xScale,
                    y: { title: { display: true, text: 'Solve Rate %' } },
                }
            }
        });
    });
}
