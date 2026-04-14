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
