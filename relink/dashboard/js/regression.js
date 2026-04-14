/**
 * Regression tables + forest plot.
 */
import { hsl, hsla } from './charts.js';

function makeRegTable(container, title, data, footer) {
    let html = `<div class="card"><h3>${title}</h3>`;
    html += '<table><thead><tr><th>Feature</th><th>Coefficient</th><th>Effect</th></tr></thead><tbody>';
    data.names.forEach((name, i) => {
        const c = data.coefs[i];
        const effect = i === 0 ? 'baseline' : (c > 0 ? '+' : '') + (c * 100).toFixed(1) + 'pp';
        const cls = i === 0 ? '' : (Math.abs(c) > 0.1 ? ' style="font-weight:600;"' : '');
        html += `<tr${cls}><td>${name}</td><td>${c.toFixed(4)}</td><td>${effect}</td></tr>`;
    });
    html += '</tbody></table>';
    html += `<p style="margin-top:10px;color:var(--muted);font-size:13px;">${footer}</p></div>`;
    container.innerHTML += html;
}

export function render(regressionData) {
    const tablesDiv = document.getElementById('regression-tables');
    makeRegTable(tablesDiv,
        `Puzzle-Level (n=${regressionData.puzzle.puzzle_labels.length})`,
        regressionData.puzzle,
        `R² = ${regressionData.puzzle.r2} · LOO-CV MAE = ${regressionData.puzzle.loo_mae}pp`
    );
    makeRegTable(tablesDiv,
        `Row-Level: All Rows (n=${regressionData.row.n})`,
        regressionData.row,
        `R² = ${regressionData.row.r2}`
    );

    // Position-controlled
    if (regressionData.pos_controlled.coefs.length > 0) {
        const posDiv = document.getElementById('regression-pos');
        makeRegTable(posDiv,
            `Row-Level: Position-Controlled (n=${regressionData.pos_controlled.n})`,
            regressionData.pos_controlled,
            `R² = ${regressionData.pos_controlled.r2} — Same features + mean attempt position as covariate`
        );
    }

    // Forest plot
    const rd = regressionData.row;
    const labels = rd.names.slice(1);
    const coefs = rd.coefs.slice(1).map(c => c * 100);
    const ctx = document.getElementById('chart-forest').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{ label: 'Effect on first-try % (pp)', data: coefs,
                          backgroundColor: coefs.map(c => c >= 0 ? hsla(150,60,45,0.7) : hsla(0,65,50,0.7)),
                          borderColor: coefs.map(c => c >= 0 ? hsl(150,60,45) : hsl(0,65,50)),
                          borderWidth: 1 }]
        },
        options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { title: { display: true, text: 'Effect on first-try correct % (pp)' },
                      grid: { color: (ctx) => ctx.tick.value === 0 ? '#2d3436' : '#eee' } }
            }
        }
    });
}
