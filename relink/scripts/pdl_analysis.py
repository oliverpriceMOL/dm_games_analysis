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
regression_data = metrics.compute_regression(puzzle_data, row_joined, overlap_dates, date_summaries)

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

# 9. Overview
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
# Build enriched relink feature distributions from pooled player data.
# Groups relink outcomes by multiple feature axes for ratio-shift adjustments.
from collections import Counter, defaultdict as _dd

_rl_axis_counts = {
    'con_manip': _dd(Counter), 'id_manip': _dd(Counter),
    'con_knowledge': _dd(Counter), 'tiles': _dd(Counter),
}
_rl_axis_totals = {k: _dd(int) for k in _rl_axis_counts}
_rl_all_wrongs = []

for d in overlap_dates:
    lid = date_to_level[d]
    pf = pdl_puzzle_features[lid]
    pp = players_by_date[d]
    for p in pp:
        rt = p.get('relink_trajectory')
        if rt:
            wc = rt['wrong_count']
            _rl_all_wrongs.append(wc)
            mappings = {
                'con_manip': pf['relink_con_manipulation'],
                'id_manip': pf['relink_id_manipulation'],
                'con_knowledge': pf['relink_con_knowledge'],
                'tiles': str(pf['phase2TileCount']),
            }
            for axis, cat in mappings.items():
                _rl_axis_counts[axis][cat][wc] += 1
                _rl_axis_totals[axis][cat] += 1

# Global relink baseline
_rl_global_total = len(_rl_all_wrongs)
_rl_global_mean = sum(_rl_all_wrongs) / _rl_global_total if _rl_global_total else 0

# Build per-axis distributions + mean_wrong for ratio computation
MIN_RL_N = 5
relink_feature_dists = {'global': {'mean_wrong': round(_rl_global_mean, 4), 'n': _rl_global_total}}
_axis_to_key = {'con_manip': 'by_con_manip', 'id_manip': 'by_id_manip',
                'con_knowledge': 'by_con_knowledge', 'tiles': 'by_tiles'}
for axis, out_key in _axis_to_key.items():
    dists = {}
    for cat, counts in _rl_axis_counts[axis].items():
        total = _rl_axis_totals[axis][cat]
        if total >= MIN_RL_N:
            cat_wrongs = []
            for wc, n in counts.items():
                cat_wrongs.extend([wc] * n)
            dists[cat] = {
                'dist': {str(k): round(v / total, 4) for k, v in sorted(counts.items())},
                'mean_wrong': round(sum(cat_wrongs) / len(cat_wrongs), 4) if cat_wrongs else 0,
            }
    relink_feature_dists[out_key] = dists

# Log
_cm = relink_feature_dists.get('by_con_manip', {})
_cm_axis = _rl_axis_totals['con_manip']
_cm_summary = ', '.join(f'{k}(n={_cm_axis[k]})' for k in sorted(_cm))
print(f"  Relink feature dists: con_manip={_cm_summary}"
      f", id_manip={len(relink_feature_dists.get('by_id_manip', {}))} types"
      f", con_know={len(relink_feature_dists.get('by_con_knowledge', {}))} types"
      f", tiles={len(relink_feature_dists.get('by_tiles', {}))} types"
      f", global n={_rl_global_total}")

# Run simulation on dated puzzles (per-puzzle empirical distributions + pooled fallback)
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
        n_sims=10000, per_puzzle_obs=per_puzzle_dists,
        relink_feature_dists=relink_feature_dists)
    result['actual_solve_rate'] = round(ds['solve_rate'] * 100, 1)
    result['name'] = ds['name']
    result['date'] = d
    result['label'] = ds['label']
    result['manipulationComplexity'] = pf['manipulationComplexity']
    result['abstractionComplexity'] = pf['abstractionComplexity']
    result['phase2TileCount'] = pf['phase2TileCount']
    result['cluster'] = cluster_assignments.get(lid, -1)
    sim_results[d] = result

# Simulation validation (dated only)
sim_preds = [sim_results[d]['solve_rate'] * 100 for d in overlap_dates]
actual_rates = [date_summaries[d]['solve_rate'] * 100 for d in overlap_dates]
from lib.stats import pearson as _pearson
sim_r, _ = _pearson(sim_preds, actual_rates) if len(sim_preds) >= 3 else (0, 1)
sim_mae = safe_mean([abs(sim_preds[i] - actual_rates[i]) for i in range(len(sim_preds))])
print(f"  Simulator (dated, empirical): r={sim_r:.3f}, MAE={sim_mae:.1f}pp")

# Cross-validation: run feature-based model on dated puzzles (no per_puzzle_obs)
# This measures how well the feature model alone predicts known puzzles.
feat_preds = []
for d in overlap_dates:
    lid = date_to_level[d]
    rows_for_puzzle = [pr for pr in pdl_rows if pr['lid'] == lid]
    pf = pdl_puzzle_features[lid]
    result = model.simulate_puzzle(
        transition_data, rows_for_puzzle, pf, n_sims=10000,
        relink_feature_dists=relink_feature_dists)
    feat_preds.append(result['solve_rate'] * 100)
feat_r, _ = _pearson(feat_preds, actual_rates) if len(feat_preds) >= 3 else (0, 1)
feat_mae = safe_mean([abs(feat_preds[i] - actual_rates[i]) for i in range(len(feat_preds))])
print(f"  Simulator (dated, feature-only): r={feat_r:.3f}, MAE={feat_mae:.1f}pp")

# Run simulation on ALL puzzles without player data (pooled model only)
sim_undated = {}
for lid, pdata in pdl_puzzles.items():
    if lid not in pdl_puzzle_features:
        continue
    pf = pdl_puzzle_features[lid]
    d = level_to_date.get(lid)
    if d and d in overlap_dates:
        continue  # already simulated above
    rows_for_puzzle = [pr for pr in pdl_rows if pr['lid'] == lid]
    if len(rows_for_puzzle) < 4:
        continue
    result = model.simulate_puzzle(
        transition_data, rows_for_puzzle, pf, n_sims=10000,
        relink_feature_dists=relink_feature_dists)
    result['actual_solve_rate'] = None
    result['name'] = pf['name']
    result['date'] = d  # may be None for undated, or a date without player data
    result['label'] = pf['name']  # use puzzle name as label for undated
    result['manipulationComplexity'] = pf['manipulationComplexity']
    result['abstractionComplexity'] = pf['abstractionComplexity']
    result['phase2TileCount'] = pf['phase2TileCount']
    result['cluster'] = cluster_assignments.get(lid, -1)
    sim_undated[lid] = result

print(f"  Simulator (undated/no-data): {len(sim_undated)} puzzles simulated")


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
    'transitions.json': transition_data,
    'failures.json': failure_data,
    'simulator.json': {
        'puzzles': {d: {k: v for k, v in r.items()} for d, r in sim_results.items()},
        'undated': {lid: {k: v for k, v in r.items()} for lid, r in sim_undated.items()},
        'validation': {'r': round(sim_r, 3), 'mae': round(sim_mae, 1)},
        'feature_validation': {'r': round(feat_r, 3), 'mae': round(feat_mae, 1)},
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
