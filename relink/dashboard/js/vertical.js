/**
 * Vertical Inference section: summary cards, curve charts, per-puzzle table with sparklines.
 */
import { drawSparkline } from './charts.js';

const CURVE_COLORS = ['#e74c3c', '#f39c12', '#27ae60', '#2980b9', '#8e44ad', '#e67e22', '#1abc9c', '#636e72'];

/** Centre of mass: weighted position average (0-indexed). Lower = front-loaded. */
function com(curve) {
    if (!curve || curve.length === 0) return null;
    let wSum = 0, total = 0;
    for (let i = 0; i < curve.length; i++) {
        const v = curve[i];
        if (v == null) continue;
        wSum += v * i;
        total += v;
    }
    return total > 0 ? wSum / total : null;
}

export function render(viData) {
    const ct = viData.crosstabs;
    const summ = viData.summary;

    // Summary cards
    const summDiv = document.getElementById('vi-summary');
    const tc = summ.timing_curve || [];
    const ec = summ.error_curve || [];
    const tDrop = tc[0] > 0 ? ((tc[0] - tc[3]) / tc[0] * 100).toFixed(0) : '?';
    const eDrop = (ec[0] && ec[0] > 0 && ec[3] != null) ? ((ec[0] - ec[3]) / ec[0] * 100).toFixed(0) : '?';
    let sh = `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:15px;">`;
    sh += `<div class="stat-card"><div class="value">${tc[0]}s → ${tc[3]}s</div><div class="label">Timing: start→1st correct → 3rd→4th correct</div></div>`;
    sh += `<div class="stat-card"><div class="value">${tDrop}%</div><div class="label">Timing drop</div></div>`;
    sh += `<div class="stat-card"><div class="value">${summ.mean_timing_auc}</div><div class="label">Mean timing CoM (1.5=flat)</div></div>`;
    sh += `<div class="stat-card"><div class="value">${summ.n_sped_up}/${summ.n_total}</div><div class="label">Puzzles that sped up (<1.5)</div></div>`;
    sh += `<div class="stat-card"><div class="value">${ec[0]} → ${ec[3]}</div><div class="label">Errors: 1st → 4th row solved</div></div>`;
    sh += `<div class="stat-card"><div class="value">${eDrop}%</div><div class="label">Error drop</div></div>`;
    sh += `<div class="stat-card"><div class="value">${summ.mean_error_auc}</div><div class="label">Mean error CoM (1.5=flat)</div></div>`;
    sh += `<div class="stat-card"><div class="value">${summ.n_more_accurate}/${summ.n_total}</div><div class="label">Errors front-loaded (<1.5)</div></div>`;
    sh += `</div>`;
    summDiv.innerHTML = sh;

    // Two-panel curve charts per PDL feature axis
    const container = document.getElementById('vi-curve-charts');
    const features = Object.keys(ct);
    const timingLabels = ['Start→1st', '1st→2nd', '2nd→3rd', '3rd→4th'];
    const errorLabels = ['1st solved', '2nd solved', '3rd solved', '4th solved'];

    // Build DOM first
    features.forEach((feat, fi) => {
        const axis = ct[feat];
        const cats = Object.keys(axis.categories);

        // Build CoM rows
        let comRows = '';
        cats.forEach(cat => {
            const info = axis.categories[cat];
            const tCoM = com(info.timing_curve);
            const eCoM = com(info.error_curve);
            const fmtT = tCoM !== null ? tCoM.toFixed(2) : '—';
            const fmtE = eCoM !== null ? eCoM.toFixed(2) : '—';
            const tColor = tCoM !== null ? (tCoM < 1.5 ? '#27ae60' : '#e74c3c') : 'inherit';
            const eColor = eCoM !== null ? (eCoM < 1.5 ? '#27ae60' : '#e74c3c') : 'inherit';
            comRows += `<tr><td>${cat}</td><td style="text-align:center;">${info.n}</td>
                <td style="text-align:center;color:${tColor};font-weight:600;">${fmtT}</td>
                <td style="text-align:center;color:${eColor};font-weight:600;">${fmtE}</td></tr>`;
        });

        container.innerHTML += `<div style="margin-bottom:25px;">
            <h4 style="color:var(--text);margin-bottom:8px;">${axis.label}</h4>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
                <div class="chart-container" style="height:200px;"><canvas id="vi-tc-${fi}"></canvas></div>
                <div class="chart-container" style="height:200px;"><canvas id="vi-ec-${fi}"></canvas></div>
            </div>
            <table style="margin-top:10px;font-size:13px;max-width:500px;">
                <thead><tr><th>Category</th><th style="text-align:center;">n</th><th style="text-align:center;">Timing CoM</th><th style="text-align:center;">Error CoM</th></tr></thead>
                <tbody>${comRows}</tbody>
            </table>
        </div>`;
    });

    // Render charts
    features.forEach((feat, fi) => {
        const axis = ct[feat];
        const cats = Object.keys(axis.categories);

        const tcEl = document.getElementById(`vi-tc-${fi}`);
        if (tcEl) {
            const datasets = cats.map((cat, ci) => {
                const info = axis.categories[cat];
                const curve = info.timing_curve || [null, null, null, null];
                const color = CURVE_COLORS[ci % CURVE_COLORS.length];
                return { label: `${cat} (n=${info.n})`, data: curve, borderColor: color,
                          borderWidth: 2, pointRadius: 4, tension: 0.3, fill: false, spanGaps: true };
            });
            new Chart(tcEl.getContext('2d'), {
                type: 'line',
                data: { labels: timingLabels, datasets },
                options: {
                    plugins: {
                        title: { display: true, text: 'Timing (seconds)', color: '#636e72', font: { size: 12 } },
                        legend: { display: true, position: 'top', labels: { boxWidth: 12, font: { size: 11 } } },
                        tooltip: { callbacks: { footer: (items) => {
                            const cat = cats[items[0].datasetIndex];
                            const info = axis.categories[cat];
                            return `Puzzles: ${info.puzzles.join(', ')}`;
                        } } }
                    },
                    scales: { y: { title: { display: true, text: 'Median seconds' }, beginAtZero: true } }
                }
            });
        }

        const ecEl = document.getElementById(`vi-ec-${fi}`);
        if (ecEl) {
            const datasets = cats.map((cat, ci) => {
                const info = axis.categories[cat];
                const curve = info.error_curve || [null, null, null, null];
                const color = CURVE_COLORS[ci % CURVE_COLORS.length];
                return { label: `${cat} (n=${info.n})`, data: curve, borderColor: color,
                          borderWidth: 2, pointRadius: 4, tension: 0.3, fill: false, spanGaps: true };
            });
            new Chart(ecEl.getContext('2d'), {
                type: 'line',
                data: { labels: errorLabels, datasets },
                options: {
                    plugins: {
                        title: { display: true, text: 'Errors (wrong guesses)', color: '#636e72', font: { size: 12 } },
                        legend: { display: true, position: 'top', labels: { boxWidth: 12, font: { size: 11 } } },
                        tooltip: { callbacks: { footer: (items) => {
                            const cat = cats[items[0].datasetIndex];
                            const info = axis.categories[cat];
                            return `Puzzles: ${info.puzzles.join(', ')}`;
                        } } }
                    },
                    scales: { y: { title: { display: true, text: 'Mean wrong guesses' }, beginAtZero: true } }
                }
            });
        }
    });

    // Per-puzzle detail table with dual sparklines
    const tbody = document.querySelector('#vi-puzzle-table tbody');
    const sorted = [...viData.puzzles].sort((a, b) => (a.error_auc ?? 99) - (b.error_auc ?? 99));
    let si = 0;
    sorted.forEach(p => {
        const tauc = p.timing_auc !== null ? p.timing_auc.toFixed(2) : '—';
        const tColor = p.timing_auc !== null ? (p.timing_auc < 1.5 ? 'color:#27ae60' : 'color:#e74c3c') : '';
        const eauc = p.error_auc !== null ? p.error_auc.toFixed(2) : '—';
        const eColor = p.error_auc !== null ? (p.error_auc < 1.5 ? 'color:#27ae60' : 'color:#e74c3c') : '';
        const tsId = `sp-t-${si}`, esId = `sp-e-${si}`;
        si++;
        tbody.innerHTML += `<tr>
            <td>${p.name}</td><td>${p.label}</td>
            <td><canvas id="${tsId}" width="120" height="32" style="vertical-align:middle;"></canvas></td>
            <td style="${tColor};font-weight:600;">${tauc}</td>
            <td><canvas id="${esId}" width="120" height="32" style="vertical-align:middle;"></canvas></td>
            <td style="${eColor};font-weight:600;">${eauc}</td>
            <td>${p.solve_rate}%</td></tr>`;
    });
    // Render sparklines
    si = 0;
    sorted.forEach(p => {
        drawSparkline(`sp-t-${si}`, p.timing_curve || [], 4, (p.timing_auc ?? 99) < 1.5);
        drawSparkline(`sp-e-${si}`, p.error_curve || [], 4, (p.error_auc ?? 99) < 1.5);
        si++;
    });
}
