/**
 * Shared Chart.js helpers, colour palette, and global defaults.
 */

export const COLORS = ['#e74c3c','#f39c12','#27ae60','#2980b9','#8e44ad',
                        '#c0392b','#e67e22','#2ecc71','#3498db','#9b59b6','#dfe6e9','#636e72','#1abc9c'];

export function hsl(h, s, l) { return `hsl(${h}, ${s}%, ${l}%)`; }
export function hsla(h, s, l, a) { return `hsla(${h}, ${s}%, ${l}%, ${a})`; }

/* ── Global Chart.js defaults ─────────────────────────────────────── */

Chart.defaults.responsive = true;
Chart.defaults.maintainAspectRatio = false;

// White tooltip styling
Chart.defaults.plugins.tooltip.backgroundColor = '#fff';
Chart.defaults.plugins.tooltip.titleColor = '#2d3436';
Chart.defaults.plugins.tooltip.bodyColor = '#636e72';
Chart.defaults.plugins.tooltip.footerColor = '#b2bec3';
Chart.defaults.plugins.tooltip.borderColor = '#dfe6e9';
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.cornerRadius = 6;
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.plugins.tooltip.titleFont = { weight: 'bold', size: 13 };
Chart.defaults.plugins.tooltip.bodyFont = { size: 12 };
Chart.defaults.plugins.tooltip.footerFont = { size: 11, weight: 'normal' };
Chart.defaults.plugins.tooltip.displayColors = true;
Chart.defaults.plugins.tooltip.boxPadding = 4;
Chart.defaults.plugins.tooltip.usePointStyle = true;
Chart.defaults.plugins.tooltip.multiKeyBackground = 'transparent';

// Default interaction: index mode (show all datasets at same x), no need to aim
Chart.defaults.interaction.mode = 'index';
Chart.defaults.interaction.intersect = false;

/* ── Crosshair plugin — dashed vertical line at hover position ──── */

Chart.register({
    id: 'crosshair',
    afterDraw(chart) {
        const tt = chart.tooltip;
        if (!tt || tt.opacity === 0) return;
        // Skip crosshair for radar charts
        if (chart.config.type === 'radar') return;
        const { ctx, chartArea: { top, bottom, left, right } } = chart;
        const isHorizontal = chart.options.indexAxis === 'y';
        ctx.save();
        ctx.strokeStyle = '#b2bec3';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        if (isHorizontal && tt.caretY) {
            ctx.moveTo(left, tt.caretY);
            ctx.lineTo(right, tt.caretY);
        } else if (tt.caretX) {
            ctx.moveTo(tt.caretX, top);
            ctx.lineTo(tt.caretX, bottom);
        }
        ctx.stroke();
        ctx.restore();
    }
});

/** Interaction config for scatter/radar charts that need point-level targeting. */
export const nearestInteraction = { mode: 'nearest', intersect: true };

/** Interaction config for horizontal bar charts — trigger by row. */
export const horizontalInteraction = { mode: 'index', axis: 'y', intersect: false };

/* ── Shared chart factories ───────────────────────────────────────── */

export function makeBarChart(canvasId, data, horizontal) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    const indexAxis = horizontal ? 'y' : 'x';
    const valAxis = horizontal ? 'xAxisID' : 'yAxisID';
    const ds1 = { label: 'First-try correct %', data: data.first_try.map(v => v.toFixed(1)),
                   backgroundColor: hsla(210, 70, 50, 0.7), borderColor: hsl(210, 70, 50),
                   borderWidth: 1 };
    const ds2 = { label: 'Avg wrong guesses', data: data.avg_wrong.map(v => v.toFixed(2)),
                   backgroundColor: hsla(0, 70, 55, 0.7), borderColor: hsl(0, 70, 55),
                   borderWidth: 1 };
    ds1[valAxis] = horizontal ? 'x' : 'y';
    ds2[valAxis] = horizontal ? 'x1' : 'y1';
    const scales = horizontal ? {
        x: { beginAtZero: true, position: 'bottom',
              title: { display: true, text: 'First-try %' } },
        x1: { beginAtZero: true, position: 'top', grid: { drawOnChartArea: false },
               title: { display: true, text: 'Avg wrong' } },
    } : {
        y: { beginAtZero: true, position: 'left',
              title: { display: true, text: 'First-try %' } },
        y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false },
               title: { display: true, text: 'Avg wrong' } },
    };
    new Chart(ctx, {
        type: 'bar',
        data: { labels: data.labels, datasets: [ds1, ds2] },
        options: {
            indexAxis,
            interaction: horizontal ? horizontalInteraction : undefined,
            plugins: {
                tooltip: {
                    callbacks: {
                        footer: (items) => {
                            const i = items[0].dataIndex;
                            return `n = ${data.n[i]} rows`;
                        }
                    }
                }
            },
            scales,
        }
    });
}

export function drawSparkline(canvasId, vals, nPoints, isDown) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || vals.every(v => v === null)) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height, pad = 4;
    const data = vals.map(v => v ?? 0);
    const maxV = Math.max(...data, 0.01);
    const lineColor = isDown ? '#27ae60' : '#e74c3c';
    const fillColor = isDown ? 'rgba(39,174,96,0.15)' : 'rgba(231,76,60,0.15)';
    const step = (w - 2 * pad) / (nPoints - 1);

    ctx.beginPath();
    data.forEach((v, i) => {
        const x = pad + i * step;
        const y = h - pad - (v / maxV) * (h - 2 * pad);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = lineColor; ctx.lineWidth = 2; ctx.stroke();
    ctx.lineTo(pad + (nPoints - 1) * step, h - pad);
    ctx.lineTo(pad, h - pad); ctx.closePath();
    ctx.fillStyle = fillColor; ctx.fill();
    data.forEach((v, i) => {
        const x = pad + i * step;
        const y = h - pad - (v / maxV) * (h - 2 * pad);
        ctx.beginPath(); ctx.arc(x, y, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = lineColor; ctx.fill();
    });
}
