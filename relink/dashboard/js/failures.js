/**
 * Correlated Failures section — phi coefficient heatmaps per puzzle and aggregate analysis.
 */
import { hsla } from './charts.js';

export function render(data) {
    renderPerPuzzle(data.per_puzzle);
    renderAggregate(data.aggregate);
    document.getElementById('failures-n').textContent = `${data.n_pairs} row-pair observations across ${Object.keys(data.per_puzzle).length} puzzles.`;
}

/* ── Per-puzzle phi heatmaps ── */
function renderPerPuzzle(perPuzzle) {
    const container = document.getElementById('failure-puzzles');
    const dates = Object.keys(perPuzzle).sort();

    for (const date of dates) {
        const pz = perPuzzle[date];
        const card = document.createElement('div');
        card.className = 'card';

        // Format date label
        const d = new Date(date + 'T00:00:00');
        const label = d.toLocaleDateString('en-GB', { month: 'short', day: 'numeric' });

        let html = `<h3>${pz.name} <span style="color:var(--muted);font-weight:400">(${label}, n=${pz.n_players})</span></h3>`;

        // Row names from category data
        const cats = pz.row_categories || {};
        const rowName = (r) => cats[r] || `Row ${r + 1}`;

        // Row failure rates as small badges
        html += '<div style="margin-bottom:12px;font-size:12px;">';
        for (let r = 0; r < 4; r++) {
            const rate = pz.row_failure_rates[r];
            if (rate === undefined) continue;
            const pct = (rate * 100).toFixed(0);
            const cls = rate > 0.5 ? 'badge-red' : rate > 0.3 ? 'badge-amber' : 'badge-green';
            html += `<span class="badge ${cls}" style="margin-right:6px">${rowName(r)}: ${pct}% fail</span>`;
        }
        html += '</div>';

        // 4×4 phi matrix
        html += '<div class="confusion-grid" style="grid-template-columns: 90px repeat(4, 90px);">';
        html += '<div class="confusion-cell confusion-header"></div>';
        for (let c = 0; c < 4; c++) html += `<div class="confusion-cell confusion-header" title="${rowName(c)}">${rowName(c)}</div>`;

        for (let r = 0; r < 4; r++) {
            html += `<div class="confusion-cell confusion-header" title="${rowName(r)}">${rowName(r)}</div>`;
            for (let c = 0; c < 4; c++) {
                if (r === c) {
                    html += '<div class="confusion-cell" style="background:#f8f9fa;color:var(--muted)">—</div>';
                } else {
                    const key = r < c ? `${r}-${c}` : `${c}-${r}`;
                    const phi = pz.phi_matrix[key];
                    if (phi !== undefined) {
                        const bg = phiColor(phi);
                        html += `<div class="confusion-cell" style="background:${bg};color:#fff" title="φ = ${phi.toFixed(3)}">${phi.toFixed(2)}</div>`;
                    } else {
                        html += '<div class="confusion-cell" style="background:#f8f9fa;color:var(--muted)">—</div>';
                    }
                }
            }
        }
        html += '</div>';

        card.innerHTML = html;
        container.appendChild(card);
    }
}

/* ── Aggregate analysis ── */
function renderAggregate(aggregate) {
    const container = document.getElementById('failure-aggregate');
    const features = {
        same_manipulation: 'Same Manipulation Type',
        same_abstraction: 'Same Abstraction Type',
        same_domain: 'Same Knowledge Domain'
    };

    let html = '<table><thead><tr><th>Feature</th><th>Same</th><th>Different</th><th>Difference</th></tr></thead><tbody>';

    for (const [key, label] of Object.entries(features)) {
        const d = aggregate[key];
        if (!d) continue;
        const samePhi = d.same.mean_phi;
        const diffPhi = d.different.mean_phi;
        const delta = samePhi - diffPhi;
        const arrow = delta > 0.02 ? '↑' : delta < -0.02 ? '↓' : '≈';
        const cls = delta > 0.02 ? 'badge-red' : delta < -0.02 ? 'badge-green' : 'badge-amber';

        html += `<tr>
            <td><strong>${label}</strong></td>
            <td>φ = ${samePhi.toFixed(3)} <span style="color:var(--muted)">(n=${d.same.n})</span></td>
            <td>φ = ${diffPhi.toFixed(3)} <span style="color:var(--muted)">(n=${d.different.n})</span></td>
            <td><span class="badge ${cls}">${arrow} ${Math.abs(delta).toFixed(3)}</span></td>
        </tr>`;
    }

    html += '</tbody></table>';
    html += '<p style="color:var(--muted);font-size:12px;margin-top:10px;">Phi coefficient (φ) measures correlation between row failures. Higher φ = rows that tend to be failed together. Positive difference means rows sharing this feature are more likely to be failed together.</p>';
    container.innerHTML = html;
}

/* ── Phi colour: blue (negative/independent) → white (0) → red (correlated) ── */
function phiColor(phi) {
    // Clamp to [-0.5, 0.5] for colour mapping
    const clamped = Math.max(-0.5, Math.min(0.5, phi));
    if (clamped >= 0) {
        const t = clamped / 0.5;
        const r = Math.round(220 - t * 20);
        const g = Math.round(220 - t * 120);
        const b = Math.round(220 - t * 170);
        return `rgb(${r}, ${g}, ${b})`;
    } else {
        const t = -clamped / 0.5;
        const r = Math.round(220 - t * 170);
        const g = Math.round(220 - t * 120);
        const b = Math.round(220 - t * 20);
        return `rgb(${r}, ${g}, ${b})`;
    }
}
