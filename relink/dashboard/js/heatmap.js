/**
 * Heatmap + Impostor Domain sections.
 */
import { hsl, hsla, COLORS, nearestInteraction } from './charts.js';

export function renderHeatmap(heatmap) {
    const container = document.getElementById('heatmap-container');
    const { manips, abstrs, values, annotations } = heatmap;
    let html = `<div class="heatmap-grid" style="grid-template-columns: 120px repeat(${manips.length}, 1fr);">`;
    html += '<div class="hm-header"></div>';
    manips.forEach(m => { html += `<div class="hm-header">${m}</div>`; });
    abstrs.forEach((a, ai) => {
        html += `<div class="hm-header" style="text-align:right;padding-right:8px;">${a}</div>`;
        values[ai].forEach((v, mi) => {
            if (v === null) {
                html += '<div class="hm-cell" style="background:#eee;color:#999;">—</div>';
            } else {
                const pct = v;
                const h = pct < 40 ? 0 : pct < 55 ? 30 : pct < 70 ? 120 : 150;
                const s = 65, l = 42;
                html += `<div class="hm-cell" style="background:${hsl(h,s,l)};">${annotations[ai][mi]}</div>`;
            }
        });
    });
    html += '</div>';
    container.innerHTML += html;
}

export function renderImpostorDomain(data) {
    const ctx1 = document.getElementById('chart-domain-dist').getContext('2d');
    new Chart(ctx1, {
        type: 'bar',
        data: {
            labels: ['Same Domain', 'Different Domain'],
            datasets: [
                { label: 'First-try %', data: [data.same_domain.mean_first_try,
                   data.diff_domain.mean_first_try],
                   backgroundColor: [hsla(210,70,50,0.7), hsla(35,90,55,0.7)] },
            ]
        },
        options: {
            plugins: {
                tooltip: {
                    callbacks: {
                        footer: (items) => {
                            const d = items[0].dataIndex === 0 ? data.same_domain : data.diff_domain;
                            return `n = ${d.n} rows · Avg wrong: ${d.mean_avg_wrong}`;
                        }
                    }
                }
            },
            scales: { y: { beginAtZero: true, title: { display: true, text: 'First-try correct %' } } }
        }
    });

    const bd = data.by_imp_domain;
    const labels = Object.keys(bd);
    const ctx2 = document.getElementById('chart-imp-domain').getContext('2d');
    new Chart(ctx2, {
        type: 'bar',
        data: {
            labels,
            datasets: [{ label: 'First-try %', data: labels.map(l => bd[l].mean_first_try),
                          backgroundColor: labels.map((_, i) => COLORS[i % COLORS.length]) }]
        },
        options: {
            indexAxis: 'y',
            plugins: {
                tooltip: {
                    callbacks: {
                        footer: (items) => {
                            const l = items[0].label;
                            return `n = ${bd[l].n} rows · Avg wrong: ${bd[l].mean_avg_wrong}`;
                        }
                    }
                }
            },
            scales: { x: { beginAtZero: true, title: { display: true, text: 'First-try %' } } }
        }
    });
}
