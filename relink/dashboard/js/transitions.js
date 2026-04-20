/**
 * Transition Probability section — IPW-weighted error rates by position/lives, PDL features, and decoy context.
 */
import { COLORS, hsla, hsl } from './charts.js';

export function render(data) {
    renderPositionLives(data.by_position_lives);
    renderPdlFeatures(data.by_pdl_feature);
    renderDecoyEffect(data.by_decoy);
    document.getElementById('trans-n').textContent = `Based on ${data.n_observations.toLocaleString()} IPW-weighted observations across all trajectories.`;
}

/* ── Position × Lives heatmap ── */
function renderPositionLives(byPosLives) {
    const container = document.getElementById('pos-lives-grid');
    const positions = [0, 1, 2, 3];
    const livesVals = [1, 2, 3, 4];
    const posLabels = ['1st row', '2nd row', '3rd row', '4th row'];

    // Build grid: rows = lives (4 down to 1), cols = position (0-3)
    const cols = positions.length + 1;
    container.style.gridTemplateColumns = `80px repeat(${positions.length}, 1fr)`;

    // Header row
    container.innerHTML = '<div class="hm-header"></div>';
    positions.forEach((_, i) => {
        container.innerHTML += `<div class="hm-header">${posLabels[i]}</div>`;
    });

    // Data rows
    for (const lives of livesVals.slice().reverse()) {
        container.innerHTML += `<div class="hm-header">${lives} ${lives === 1 ? 'life' : 'lives'}</div>`;
        for (const pos of positions) {
            const key = `${pos},${lives}`;
            const cell = byPosLives[key];
            if (cell && cell.n >= 5) {
                const pct = (cell.weighted_first_try * 100).toFixed(0);
                const bg = difficultyColor(cell.weighted_first_try);
                container.innerHTML += `<div class="hm-cell" style="background:${bg}" title="n=${cell.n}, mean wrong=${cell.weighted_mean_wrong.toFixed(2)}">${pct}%<br><span style="font-size:10px;opacity:0.8">n=${cell.n}</span></div>`;
            } else {
                container.innerHTML += `<div class="hm-cell" style="background:#dfe6e9;color:var(--muted)">${cell ? 'n=' + cell.n : '—'}</div>`;
            }
        }
    }
}

/* ── PDL feature breakdown ── */
function renderPdlFeatures(byFeature) {
    const container = document.getElementById('trans-pdl-charts');
    const featureLabels = {
        manipulation: 'By Manipulation Type',
        abstraction: 'By Abstraction Type',
        knowledge: 'By Knowledge Level',
        same_domain: 'By Same Domain'
    };

    for (const [feat, label] of Object.entries(featureLabels)) {
        const vals = byFeature[feat];
        if (!vals) continue;
        const keys = Object.keys(vals);
        const labels = keys.map(k => k === 'True' ? 'Same domain' : k === 'False' ? 'Different domain' : k);
        const firstTry = keys.map(k => (vals[k].weighted_first_try * 100));
        const meanWrong = keys.map(k => vals[k].weighted_mean_wrong);
        const ns = keys.map(k => vals[k].n);

        const canvasId = `trans-chart-${feat}`;
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `<h3>${label} (IPW-weighted)</h3><div class="chart-container"><canvas id="${canvasId}"></canvas></div>`;
        container.appendChild(card);

        const ctx = document.getElementById(canvasId).getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    { label: 'First-try correct %', data: firstTry.map(v => v.toFixed(1)),
                      backgroundColor: hsla(210, 70, 50, 0.7), yAxisID: 'y' },
                    { label: 'Avg wrong guesses', data: meanWrong.map(v => v.toFixed(2)),
                      backgroundColor: hsla(0, 70, 55, 0.7), yAxisID: 'y1' },
                ]
            },
            options: {
                plugins: {
                    tooltip: {
                        callbacks: {
                            footer: (items) => `n = ${ns[items[0].dataIndex]} observations`
                        }
                    }
                },
                scales: {
                    y: { beginAtZero: true, position: 'left', title: { display: true, text: 'First-try %' } },
                    y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false },
                          title: { display: true, text: 'Avg wrong' } },
                }
            }
        });
    }
}

/* ── Decoy effect ── */
function renderDecoyEffect(byDecoy) {
    const noDecoy = byDecoy['False'];
    const hasDecoy = byDecoy['True'];
    if (!noDecoy || !hasDecoy) return;

    const ctx = document.getElementById('trans-chart-decoy').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['No decoy involvement', 'In decoy group'],
            datasets: [
                { label: 'First-try correct %',
                  data: [(noDecoy.weighted_first_try * 100).toFixed(1), (hasDecoy.weighted_first_try * 100).toFixed(1)],
                  backgroundColor: [hsla(145, 60, 45, 0.7), hsla(0, 70, 55, 0.7)] },
            ]
        },
        options: {
            plugins: {
                tooltip: {
                    callbacks: {
                        footer: (items) => {
                            const d = items[0].dataIndex === 0 ? noDecoy : hasDecoy;
                            return `n = ${d.n} obs · mean wrong = ${d.weighted_mean_wrong.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: { y: { beginAtZero: true, max: 100, title: { display: true, text: 'First-try correct %' } } }
        }
    });
}

/* ── Difficulty colour: green (easy) → red (hard) ── */
function difficultyColor(firstTryRate) {
    // 0.0 = hardest (red), 1.0 = easiest (green)
    const h = firstTryRate * 120; // 0=red, 120=green
    return `hsla(${h}, 70%, 45%, 0.85)`;
}
