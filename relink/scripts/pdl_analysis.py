"""
Relink PDL Analysis — Orchestrator.

Loads puzzle + behaviour data, runs all analysis phases, and writes
JSON data files for the dashboard to consume.

Usage:
    python3 pdl_analysis.py          # generate data + print serve instructions
    python3 pdl_analysis.py --serve  # generate data + start local HTTP server
"""

import os
import sys
import json

# ── Paths ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RELINK_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR   = os.path.dirname(RELINK_DIR)
RAW_DIR    = os.path.join(DATA_DIR, 'raw')
SAVE_DIR   = os.path.join(RELINK_DIR, 'save-data')
OUT_DIR    = os.path.join(RELINK_DIR, 'outputs', 'data')
DASH_DIR   = os.path.join(RELINK_DIR, 'dashboard')

os.makedirs(OUT_DIR, exist_ok=True)

# ── Load ──
from lib.data import load_all
from lib.stats import safe_mean
from lib import metrics
from lib import model

data = load_all(SAVE_DIR, RAW_DIR)

# Convenience aliases
pdl_puzzles = data['pdl_puzzles']
pdl_rows = data['pdl_rows']
pdl_puzzle_features = data['pdl_puzzle_features']
level_to_date = data['level_to_date']
date_to_level = data['date_to_level']
players_by_date = data['players_by_date']
overlap_dates = data['overlap_dates']
date_summaries = data['date_summaries']
aggregate_timing = data['aggregate_timing']

# ── Join rows with behaviour ──
row_joined = []
for pr in pdl_rows:
    if not pr['date'] or pr['date'] not in date_summaries:
        continue
    ds = date_summaries[pr['date']]
    rm = ds['row_metrics'].get(pr['row_position'], {})
    if not rm or rm['attempts'] == 0:
        continue
    row_joined.append({**pr, **rm})

print(f"  Joined rows with behaviour: {len(row_joined)}")

# ── Build puzzle_data for correlations/regression ──
puzzle_data = []
for d in overlap_dates:
    ds = date_summaries[d]
    pf = pdl_puzzle_features[ds['lid']]
    puzzle_data.append({**pf, **ds})

# ══════════════════════════════════════════════════════════════════════
#  Run all analysis phases
# ══════════════════════════════════════════════════════════════════════
print("Running analysis phases...")

# 1. Cross-tabs
ct_result = metrics.compute_crosstabs(row_joined)

# 2. Correlations
scatter_data = metrics.compute_correlations(puzzle_data, overlap_dates, date_summaries)

# 3. Regression
regression_data, row_coefs, manip_cats, abstr_cats, know_cats = \
    metrics.compute_regression(puzzle_data, row_joined, overlap_dates, date_summaries)

# 4. Vertical inference
vi_chart_data, transparency_scores = metrics.compute_vertical_inference(
    overlap_dates, date_summaries, players_by_date, pdl_puzzle_features, aggregate_timing)

# 5. Decoys
decoy_chart = metrics.compute_decoys(
    overlap_dates, date_summaries, pdl_puzzle_features, pdl_puzzles, players_by_date)

# 6. Relink phase
relink_chart_data = metrics.compute_relink(overlap_dates, date_summaries, pdl_puzzle_features)

# 8. Clustering
cluster_chart_data, cluster_assignments = metrics.compute_clustering(
    pdl_puzzles, pdl_rows, pdl_puzzle_features, level_to_date, date_summaries, row_joined)

# 9. Predictions
pred_chart_data = metrics.compute_predictions(
    pdl_puzzles, pdl_rows, pdl_puzzle_features, level_to_date, date_summaries,
    row_coefs, manip_cats, abstr_cats, know_cats, cluster_assignments)

# 10. Overview
overview_data = metrics.compute_overview(
    date_summaries, pdl_puzzle_features, pdl_puzzles, overlap_dates, aggregate_timing)

# 11. IPW weights
ipw_data = model.compute_ipw_weights(players_by_date)
print(f"  IPW: {ipw_data['diagnostics'].get('n_trajectories', 0)} trajectories, "
      f"mean weight={ipw_data['diagnostics'].get('mean_weight', 0)}, "
      f"p95={ipw_data['diagnostics'].get('p95_weight', 0)}")

# 12. Transition probabilities (B1)
transition_data = model.compute_transition_probs(
    players_by_date, pdl_rows, pdl_puzzle_features, date_to_level, ipw_data)
print(f"  Transitions: {transition_data['n_observations']} observations")

# 13. Correlated failures (B2)
failure_data = model.compute_correlated_failures(
    players_by_date, date_to_level, pdl_puzzle_features, pdl_rows)
print(f"  Correlated failures: {failure_data['n_pairs']} row pairs across "
      f"{len(failure_data['per_puzzle'])} puzzles")

# 14. Monte Carlo simulator (C)
# Run simulation using per-puzzle empirical distributions + pooled fallback
sim_results = {}
for d in overlap_dates:
    lid = date_to_level[d]
    ds = date_summaries[d]
    rows_for_puzzle = [pr for pr in pdl_rows if pr['lid'] == lid]
    pf = pdl_puzzle_features[lid]
    pp = players_by_date[d]
    per_puzzle_dists = model.build_per_puzzle_dists(pp)
    result = model.simulate_puzzle(
        transition_data, rows_for_puzzle, pf,
        n_sims=10000, per_puzzle_obs=per_puzzle_dists)
    result['actual_solve_rate'] = round(ds['solve_rate'] * 100, 1)
    result['name'] = ds['name']
    result['date'] = d
    result['label'] = ds['label']
    sim_results[d] = result

# Simulation validation
sim_preds = [sim_results[d]['solve_rate'] * 100 for d in overlap_dates]
actual_rates = [date_summaries[d]['solve_rate'] * 100 for d in overlap_dates]
from lib.stats import pearson as _pearson
sim_r, _ = _pearson(sim_preds, actual_rates) if len(sim_preds) >= 3 else (0, 1)
sim_mae = safe_mean([abs(sim_preds[i] - actual_rates[i]) for i in range(len(sim_preds))])
print(f"  Simulator: r={sim_r:.3f}, MAE={sim_mae:.1f}pp")


# ══════════════════════════════════════════════════════════════════════
#  Write JSON files
# ══════════════════════════════════════════════════════════════════════
def write_json(filename, obj):
    path = os.path.join(OUT_DIR, filename)
    with open(path, 'w') as f:
        json.dump(obj, f)
    return path

files = {
    'overview.json': overview_data,
    'crosstabs.json': ct_result['chart_data'],
    'heatmap.json': ct_result['heatmap'],
    'impostor-domain.json': ct_result['impostor_domain'],
    'correlations.json': scatter_data,
    'regression.json': regression_data,
    'vertical.json': vi_chart_data,
    'decoys.json': decoy_chart,
    'relink.json': relink_chart_data,
    'clustering.json': cluster_chart_data,
    'predictions.json': pred_chart_data,
    'transitions.json': transition_data,
    'failures.json': failure_data,
    'simulator.json': {
        'puzzles': {d: {k: v for k, v in r.items()} for d, r in sim_results.items()},
        'validation': {'r': round(sim_r, 3), 'mae': round(sim_mae, 1)},
    },
}

print(f"\nWriting {len(files)} JSON files to {OUT_DIR}/")
for fname, obj in files.items():
    write_json(fname, obj)
    print(f"  ✓ {fname}")

print(f"\nDone! Data files written to outputs/data/")

# ── Serve ──
if '--serve' in sys.argv:
    import subprocess
    port = 8000
    print(f"\nServing dashboard at http://localhost:{port}")
    print("Press Ctrl+C to stop.")
    subprocess.run(
        [sys.executable, '-m', 'http.server', str(port), '-d', RELINK_DIR],
    )
else:
    print(f"\nTo view the dashboard:")
    print(f"  python3 {os.path.relpath(__file__)} --serve")
    print(f"  Then open http://localhost:8000")
