/**
 * Shared Chart.js helpers and colour palette.
 */

export const COLORS = ['#6c5ce7','#00b894','#e17055','#0984e3','#fdcb6e','#a29bfe',
                        '#55efc4','#fab1a0','#74b9ff','#ffeaa7','#dfe6e9','#636e72','#d63031'];

export function hsl(h, s, l) { return `hsl(${h}, ${s}%, ${l}%)`; }
export function hsla(h, s, l, a) { return `hsla(${h}, ${s}%, ${l}%, ${a})`; }

export function makeBarChart(canvasId, data, horizontal) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    const indexAxis = horizontal ? 'y' : 'x';
    const valAxis = horizontal ? 'xAxisID' : 'yAxisID';
    const ds1 = { label: 'First-try correct %', data: data.first_try.map(v => v.toFixed(1)),
                   backgroundColor: hsla(260, 70, 55, 0.7), borderColor: hsl(260, 70, 55),
                   borderWidth: 1 };
    const ds2 = { label: 'Avg wrong guesses', data: data.avg_wrong.map(v => v.toFixed(2)),
                   backgroundColor: hsla(15, 70, 55, 0.7), borderColor: hsl(15, 70, 55),
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
            responsive: true, maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        afterBody: (items) => {
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
    const lineColor = isDown ? '#00b894' : '#d63031';
    const fillColor = isDown ? 'rgba(0,184,148,0.15)' : 'rgba(214,48,49,0.15)';
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
