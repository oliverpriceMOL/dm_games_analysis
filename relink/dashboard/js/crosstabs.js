/**
 * PDL Cross-tabs bar charts + aggregate difficulty table.
 */
import { makeBarChart } from './charts.js';

// Wrong-count palette (project standard). orange → green → blue → purple → lighter red → darker red.
const WRONG_COLORS = {
    '0': '#f39c12', '1': '#27ae60', '2': '#2980b9',
    '3': '#8e44ad', '4': '#e74c3c', 'no_attempt_lost': '#641e16',
};
const WRONG_LABELS = {
    '0': '0 wrong', '1': '1 wrong', '2': '2 wrong',
    '3': '3 wrong', 'no_attempt_lost': 'No attempt (lost)',
};

export const SOLVE_ORDER_BUCKETS = ['1st', '2nd', '3rd', '4th', '5th', 'never'];
export const SOLVE_ORDER_COLORS = {
    '1st': '#1e8449', '2nd': '#82e0aa', '3rd': '#f39c12',
    '4th': '#e74c3c', '5th': '#8e44ad', 'never': '#641e16',
};
export const SOLVE_ORDER_LABELS = {
    '1st': 'Solved 1st', '2nd': 'Solved 2nd', '3rd': 'Solved 3rd',
    '4th': 'Solved 4th', '5th': 'Solved (Relink)', 'never': 'Never solved',
};

export function makeSolveOrderStackedChart(canvasId, axisData, horizontal) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    const indexAxis = horizontal ? 'y' : 'x';
    const datasets = SOLVE_ORDER_BUCKETS.map(b => ({
        label: SOLVE_ORDER_LABELS[b],
        data: axisData.solve_order_dist.map(d => d[b]),
        backgroundColor: SOLVE_ORDER_COLORS[b],
        borderColor: SOLVE_ORDER_COLORS[b],
        borderWidth: 0,
    }));
    new Chart(ctx, {
        type: 'bar',
        data: { labels: axisData.labels, datasets },
        options: {
            indexAxis,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: (item) => `${item.dataset.label}: ${item.parsed[horizontal ? 'x' : 'y'].toFixed(1)}%`,
                        footer: (items) => `n = ${axisData.n[items[0].dataIndex]} rows`,
                    }
                },
                legend: { position: 'bottom' },
            },
            scales: horizontal ? {
                x: { beginAtZero: true, max: 100, stacked: true,
                      title: { display: true, text: 'Share of attempts (%)' } },
                y: { stacked: true },
            } : {
                x: { stacked: true },
                y: { beginAtZero: true, max: 100, stacked: true,
                      title: { display: true, text: 'Share of attempts (%)' } },
            },
        }
    });
}

export function render(chartData) {
    makeBarChart('chart-manip', chartData['Manipulation'], false);
    makeBarChart('chart-abstr', chartData['Abstraction'], false);
    makeBarChart('chart-know', chartData['Knowledge'], false);
    makeBarChart('chart-domain', chartData['Knowledge Domain'], true);

    makeSolveOrderStackedChart('chart-manip-so', chartData['Manipulation'], false);
    makeSolveOrderStackedChart('chart-abstr-so', chartData['Abstraction'], false);
    makeSolveOrderStackedChart('chart-know-so', chartData['Knowledge'], false);
    makeSolveOrderStackedChart('chart-domain-so', chartData['Knowledge Domain'], true);

    renderAggregateTable(chartData.pdl_aggregates);
}

function badge(val) {
    const n = parseFloat(val);
    const cls = n >= 60 ? 'badge-green' : n >= 40 ? 'badge-amber' : 'badge-red';
    return `<span class="badge ${cls}" style="white-space:nowrap;">${val}</span>`;
}

function renderMiniDistBar(wd) {
    const keys = ['0', '1', '2', '3', 'no_attempt_lost'];
    const total = keys.reduce((s, k) => s + (wd[k] || 0), 0);
    if (total === 0) return '\u2014';
    let html = '<div style="display:flex;height:14px;border-radius:4px;overflow:hidden;min-width:100px;">';
    for (const k of keys) {
        const pct = ((wd[k] || 0) / total * 100).toFixed(1);
        if (pct > 0) {
            html += `<div style="width:${pct}%;background:${WRONG_COLORS[k]}" title="${WRONG_LABELS[k]}: ${pct}%"></div>`;
        }
    }
    html += '</div>';
    return html;
}

export function renderSolveOrderMiniBar(sod) {
    if (!sod) return '\u2014';
    const total = SOLVE_ORDER_BUCKETS.reduce((s, k) => s + (sod[k] || 0), 0);
    if (total <= 0) return '\u2014';
    let html = '<div style="display:flex;height:14px;border-radius:4px;overflow:hidden;min-width:100px;">';
    for (const k of SOLVE_ORDER_BUCKETS) {
        const pct = sod[k] || 0;
        if (pct > 0) {
            html += `<div style="width:${pct}%;background:${SOLVE_ORDER_COLORS[k]}" title="${SOLVE_ORDER_LABELS[k]}: ${pct.toFixed(1)}%"></div>`;
        }
    }
    html += '</div>';
    return html;
}

function renderAggregateTable(agg) {
    const container = document.getElementById('pdl-agg-table');
    if (!agg || !Object.keys(agg).length) { container.style.display = 'none'; return; }

    let html = '<h3>Average Difficulty by PDL Feature</h3>';
    html += '<p style="color:var(--muted);font-size:13px;margin-bottom:15px;">';
    html += 'Average first-try rate and wrong guesses across all dated rows, grouped by PDL category. ';
    html += 'Shows what distribution shapes are typical for each feature value.</p>';
    html += '<div style="overflow-x:auto;"><table><thead><tr>';
    html += '<th>PDL Axis</th><th>Category</th><th>Avg 1st Try</th><th>Avg Wrong</th>';
    html += '<th>n Rows</th><th>Wrong-Guess Distribution</th><th>Solve Order (1st&rarr;never)</th>';
    html += '</tr></thead><tbody>';
    const axisLabels = {
        manipulation: 'Manipulation', abstraction: 'Abstraction',
        knowledge: 'Knowledge', same_domain: 'Same Domain',
    };
    for (const [axis, cats] of Object.entries(agg)) {
        const catEntries = Object.entries(cats);
        for (let ci = 0; ci < catEntries.length; ci++) {
            const [cat, info] = catEntries[ci];
            html += '<tr>';
            if (ci === 0) {
                html += `<td rowspan="${catEntries.length}" style="font-weight:600;vertical-align:top;border-right:2px solid var(--border);">${axisLabels[axis] || axis}</td>`;
            }
            html += `<td>${cat}</td>`;
            html += `<td>${badge((info.avg_first_try_pct * 100).toFixed(0) + '%')}</td>`;
            html += `<td>${info.avg_wrong.toFixed(2)}</td>`;
            html += `<td>${info.n_rows}</td>`;
            const wd = info.actual_wrong_dist;
            if (wd) {
                html += '<td style="min-width:120px;">' + renderMiniDistBar(wd) + '</td>';
            } else {
                html += '<td>\u2014</td>';
            }
            const sod = info.solve_order_dist;
            html += '<td style="min-width:120px;">' + renderSolveOrderMiniBar(sod) + '</td>';
            html += '</tr>';
        }
    }
    html += '</tbody></table></div>';
    container.innerHTML = html;
}
