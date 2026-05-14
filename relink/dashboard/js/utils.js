/**
 * Shared utilities — toggle controls, pattern generators, KDE,
 * radar chart factory, sort helpers, badge/star renderers, constants.
 */

import { hsl, hsla, nearestInteraction } from './charts.js';

/* ── Dimension colours (difficulty rating axes) ───────────────── */

export const DIM_COLORS = {
    manipulation:      hsl(0, 70, 50),
    abstraction:       hsl(35, 90, 55),
    domain_mismatch:   hsl(145, 60, 45),
    knowledge:         hsl(210, 70, 50),
    relink_challenge:  hsl(270, 60, 55),
};
export const DIM_COLORS_A = {
    manipulation:      hsla(0, 70, 50, 0.25),
    abstraction:       hsla(35, 90, 55, 0.25),
    domain_mismatch:   hsla(145, 60, 45, 0.25),
    knowledge:         hsla(210, 70, 50, 0.25),
    relink_challenge:  hsla(270, 60, 55, 0.25),
};
export const TIER_COLORS = ['#27ae60', '#2ecc71', '#f39c12', '#e74c3c', '#c0392b'];

/* ── Wrong-dist constants ─────────────────────────────────────── */

// Wrong-count palette (project standard). Order: 0 → 4 → no_attempt.
// orange → green → blue → purple → lighter red → darker red.
export const BASE_COLORS = {
    '0': '#f39c12', '1': '#27ae60', '2': '#2980b9',
    '3': '#8e44ad', '4': '#e74c3c', 'no_attempt': '#641e16',
};

export const WRONG_KEYS = [
    '0_solved', '0_lost', '0_incomplete',
    '1_solved', '1_lost', '1_incomplete',
    '2_solved', '2_lost', '2_incomplete',
    '3_solved', '3_lost', '3_incomplete',
    '4_solved', '4_lost', '4_incomplete',
    'no_attempt_lost', 'no_attempt_incomplete',
];

export const PRED_KEYS = [
    '0_solved', '0_lost', '1_solved', '1_lost',
    '2_solved', '2_lost', '3_solved', '3_lost',
    '4_solved', '4_lost', 'no_attempt_lost',
];

export const WRONG_LABELS = {
    '0_solved': '0 wrong (solved)', '0_lost': '0 wrong (lost)', '0_incomplete': '0 wrong (abandoned)',
    '1_solved': '1 wrong (solved)', '1_lost': '1 wrong (lost)', '1_incomplete': '1 wrong (abandoned)',
    '2_solved': '2 wrong (solved)', '2_lost': '2 wrong (lost)', '2_incomplete': '2 wrong (abandoned)',
    '3_solved': '3 wrong (solved)', '3_lost': '3 wrong (lost)', '3_incomplete': '3 wrong (abandoned)',
    '4_solved': '4 wrong (solved)', '4_lost': '4 wrong (lost)',
    'no_attempt_lost': 'No attempt (lost)', 'no_attempt_incomplete': 'No attempt (abandoned)',
};

export function baseColorForKey(key) {
    if (key.startsWith('no_attempt')) return BASE_COLORS['no_attempt'];
    return BASE_COLORS[key.charAt(0)] || BASE_COLORS['4'];
}

export function outcomeForKey(key) {
    if (key.includes('_solved')) return 'solved';
    if (key.includes('_lost') || key === 'no_attempt_lost') return 'lost';
    return 'incomplete';
}

/* ── Toggle controls ──────────────────────────────────────────── */

export function initToggle(containerId, onChange) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.addEventListener('click', (e) => {
        const btn = e.target.closest('.toggle-btn');
        if (!btn) return;
        el.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        onChange(btn.dataset.mode);
    });
}

export function syncToggle(containerId, mode) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.querySelectorAll('.toggle-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.mode === mode);
    });
}

/* ── Pattern generators for chart fills ───────────────────────── */

const _patternCache = {};
export function stripePattern(hexColor) {
    if (_patternCache[hexColor]) return _patternCache[hexColor];
    const c = document.createElement('canvas');
    c.width = 10; c.height = 10;
    const ctx = c.getContext('2d');
    ctx.fillStyle = hexColor;
    ctx.fillRect(0, 0, 10, 10);
    ctx.strokeStyle = 'rgba(255,255,255,0.55)';
    ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(-2, 12); ctx.lineTo(12, -2); ctx.stroke();
    const pat = ctx.createPattern(c, 'repeat');
    _patternCache[hexColor] = pat;
    return pat;
}

const _hollowCache = {};
export function hollowPattern(hexColor) {
    if (_hollowCache[hexColor]) return _hollowCache[hexColor];
    const c = document.createElement('canvas');
    c.width = 10; c.height = 10;
    const ctx = c.getContext('2d');
    ctx.fillStyle = hexColor;
    ctx.globalAlpha = 0.18;
    ctx.fillRect(0, 0, 10, 10);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = hexColor;
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 2]);
    ctx.beginPath(); ctx.moveTo(0, 5); ctx.lineTo(10, 5); ctx.stroke();
    const pat = ctx.createPattern(c, 'repeat');
    _hollowCache[hexColor] = pat;
    return pat;
}

export function fillForOutcome(hexColor, outcome) {
    if (outcome === 'solved') return hexColor;
    if (outcome === 'lost') return stripePattern(hexColor);
    return hollowPattern(hexColor);
}

/* ── Gaussian KDE ─────────────────────────────────────────────── */

export function gaussianKDE(values, bandwidth, xMin, xMax, nPoints) {
    const xs = [], ys = [];
    const step = (xMax - xMin) / (nPoints - 1);
    const n = values.length;
    if (n === 0) return { xs, ys };
    const bw = bandwidth || Math.max(
        1.06 * Math.sqrt(values.reduce((s, v) => s + (v - values.reduce((a, b) => a + b, 0) / n) ** 2, 0) / n) * Math.pow(n, -0.2),
        3
    );
    for (let i = 0; i < nPoints; i++) {
        const x = xMin + i * step;
        let density = 0;
        for (const v of values) {
            const z = (x - v) / bw;
            density += Math.exp(-0.5 * z * z) / (bw * Math.sqrt(2 * Math.PI));
        }
        density /= n;
        xs.push(x);
        ys.push(density);
    }
    return { xs, ys };
}

/* ── Radar chart helpers ──────────────────────────────────────── */

export function createConicGradient(ctx2d, cx, cy, dims) {
    const n = dims.length;
    const startAngle = -Math.PI / 2;
    const grad = ctx2d.createConicGradient(startAngle, cx, cy);
    for (let i = 0; i < n; i++) {
        grad.addColorStop(i / n, DIM_COLORS_A[dims[i]] || 'rgba(99,110,114,0.25)');
    }
    grad.addColorStop(1, DIM_COLORS_A[dims[0]] || 'rgba(99,110,114,0.25)');
    return grad;
}

export function createRadarChart(canvasId, dims, dimLabels, profile, options = {}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;
    const ctx2d = canvas.getContext('2d');
    const w = canvas.width || 140, h = canvas.height || 140;
    const cx = w / 2, cy = h / 2;
    const grad = createConicGradient(ctx2d, cx, cy, dims);
    const ptColors = dims.map(d => DIM_COLORS[d] || '#636e72');

    const labels = options.shortLabels
        ? dims.map(d => (dimLabels[d] || d).split(' ').map(w => w[0].toUpperCase()).join(''))
        : dims.map(d => {
            const words = (dimLabels[d] || d).split(' ');
            if (options.showValues) words.push(`${Math.round(profile[d] * 100)}%`);
            return words;
        });

    const chart = new Chart(ctx2d, {
        type: 'radar',
        data: {
            labels,
            datasets: [{
                data: dims.map(d => profile[d]),
                backgroundColor: grad,
                borderWidth: options.large ? 2 : 1.5,
                segment: { borderColor: (ctx) => ptColors[ctx.p0DataIndex] },
                pointBackgroundColor: ptColors,
                pointBorderColor: ptColors,
                pointRadius: options.large ? 5 : 3,
                pointHoverRadius: options.large ? 7 : undefined,
            }]
        },
        options: {
            responsive: false,
            animation: false,
            interaction: nearestInteraction,
            scales: {
                r: {
                    min: 0, max: 1, beginAtZero: true,
                    ticks: { display: false, stepSize: options.large ? 0.1 : 0.2 },
                    pointLabels: {
                        display: true,
                        font: { size: options.large ? 12 : 9, weight: options.large ? 'bold' : undefined },
                        color: ptColors,
                    },
                    grid: { color: options.large ? '#b2bec3' : '#b2bec399' },
                    angleLines: { display: true, color: options.large ? '#b2bec3' : '#b2bec399' },
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => dimLabels[dims[items[0].dataIndex]] || dims[items[0].dataIndex],
                        label: (ctx) => `${(ctx.raw * 100).toFixed(0)}%`,
                    }
                }
            }
        }
    });
    return chart;
}

/* ── Badge & stars ────────────────────────────────────────────── */

export function badge(val) {
    const n = parseFloat(val);
    const cls = n >= 60 ? 'badge-green' : n >= 40 ? 'badge-amber' : 'badge-red';
    return `<span class="badge ${cls}" style="white-space:nowrap;">${val}</span>`;
}

export function stars(rating) {
    let s = '';
    for (let i = 1; i <= 5; i++) {
        s += `<span class="diff-seg${i <= rating ? ' on' : ''}"></span>`;
    }
    return `<span class="diff-bar" data-tier="${rating}">${s}</span>`;
}

export function tierClass(rating) { return `rating-tier-${rating}`; }

export function dimBar(val, dim) {
    const pct = Math.round(val * 100);
    const color = DIM_COLORS[dim] || '#636e72';
    return `<div class="dim-bar-wrap"><div class="dim-bar" style="width:${pct}%;max-width:60px;background:${color}"></div><span class="dim-bar-label">${pct}%</span></div>`;
}

/* ── Phi matrix renderer ──────────────────────────────────────── */

export function phiColor(phi) {
    const clamped = Math.max(-0.5, Math.min(0.5, phi));
    if (clamped >= 0) {
        const t = clamped / 0.5;
        return `rgb(${Math.round(220 - t * 20)}, ${Math.round(220 - t * 120)}, ${Math.round(220 - t * 170)})`;
    } else {
        const t = -clamped / 0.5;
        return `rgb(${Math.round(220 - t * 170)}, ${Math.round(220 - t * 120)}, ${Math.round(220 - t * 20)})`;
    }
}

export function renderPhiMatrix(fc) {
    const pairs = Object.keys(fc.phi_matrix).sort();
    const failRates = fc.row_failure_rates || {};
    const cats = fc.row_categories || {};
    const rowName = (r) => cats[r] || `Row ${r + 1}`;

    let html = '<div style="display:flex;gap:24px;flex-wrap:wrap;">';
    html += '<div>';
    html += '<table style="font-size:12px;"><thead><tr><th>Pair</th><th>&phi;</th></tr></thead><tbody>';
    for (const pair of pairs) {
        const phi = fc.phi_matrix[pair];
        const color = phi > 0.15 ? 'var(--danger)' : phi < -0.05 ? 'var(--accent2)' : 'var(--muted)';
        html += `<tr><td>Row ${pair}</td><td style="color:${color};font-weight:600;">${phi.toFixed(3)}</td></tr>`;
    }
    html += '</tbody></table></div>';
    if (Object.keys(failRates).length) {
        html += '<div><table style="font-size:12px;"><thead><tr><th>Row</th><th>Failure Rate</th></tr></thead><tbody>';
        for (const [rp, rate] of Object.entries(failRates).sort()) {
            html += `<tr><td>Row ${rp}</td><td>${(rate * 100).toFixed(1)}%</td></tr>`;
        }
        html += '</tbody></table></div>';
    }
    html += '</div>';
    return html;
}

/* ── Difficulty colour helper ─────────────────────────────────── */

export function difficultyColor(firstTryRate) {
    const h = firstTryRate * 120;
    return `hsla(${h}, 70%, 45%, 0.85)`;
}
