/**
 * PDL Cross-tabs bar charts + aggregate difficulty table.
 */
import { makeBarChart } from './charts.js';

const WRONG_COLORS = {
    '0': '#00b894', '1': '#fdcb6e', '2': '#e17055',
    '3': '#d63031', 'no_attempt_lost': '#6d2c2c',
};
const WRONG_LABELS = {
    '0': '0 wrong', '1': '1 wrong', '2': '2 wrong',
    '3': '3 wrong', 'no_attempt_lost': 'No attempt (lost)',
};

export function render(chartData) {
    makeBarChart('chart-manip', chartData['Manipulation'], false);
    makeBarChart('chart-abstr', chartData['Abstraction'], false);
    makeBarChart('chart-know', chartData['Knowledge'], false);
    makeBarChart('chart-domain', chartData['Knowledge Domain'], true);

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

function renderAggregateTable(agg) {
    const container = document.getElementById('pdl-agg-table');
    if (!agg || !Object.keys(agg).length) { container.style.display = 'none'; return; }

    let html = '<h3>Average Difficulty by PDL Feature</h3>';
    html += '<p style="color:var(--muted);font-size:13px;margin-bottom:15px;">';
    html += 'Average first-try rate and wrong guesses across all dated rows, grouped by PDL category. ';
    html += 'Shows what distribution shapes are typical for each feature value.</p>';
    html += '<div style="overflow-x:auto;"><table><thead><tr>';
    html += '<th>PDL Axis</th><th>Category</th><th>Avg 1st Try</th><th>Avg Wrong</th>';
    html += '<th>n Rows</th><th>Wrong-Guess Distribution</th>';
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
            html += '</tr>';
        }
    }
    html += '</tbody></table></div>';
    container.innerHTML = html;
}
