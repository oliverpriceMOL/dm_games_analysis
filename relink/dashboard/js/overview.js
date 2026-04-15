/**
 * Key Findings / Overview section.
 */

export function render(overview, regression, simulator) {
    const el = document.getElementById('subtitle');
    el.textContent = `${overview.n_puzzles} puzzles analysed · ${overview.n_dated} with player data · ${overview.total_completions} total completions`;

    const grid = document.getElementById('stats-grid');
    const rowCoefs = regression.row;
    let maxCoef = '', maxVal = 0;
    for (let i = 1; i < rowCoefs.names.length; i++) {
        if (Math.abs(rowCoefs.coefs[i]) > Math.abs(maxVal)) {
            maxVal = rowCoefs.coefs[i];
            maxCoef = rowCoefs.names[i];
        }
    }

    const findings = [
        { value: simulator.validation.r.toFixed(2), label: 'Simulator Correlation (r)' },
        { value: simulator.validation.mae + 'pp', label: 'Simulator MAE' },
        { value: regression.row.r2, label: 'Row Regression R²' },
        { value: maxCoef.replace('manip:','').replace('abstr:','').replace('know:',''),
           label: 'Strongest Predictor' },
        { value: (maxVal > 0 ? '+' : '') + (maxVal * 100).toFixed(0) + 'pp',
           label: 'Its Effect on First-Try %' },
        { value: regression.puzzle.loo_mae + 'pp', label: 'Puzzle LOO-CV MAE' },
    ];
    findings.forEach(f => {
        grid.innerHTML += `<div class="stat-card"><div class="value">${f.value}</div><div class="label">${f.label}</div></div>`;
    });
}
