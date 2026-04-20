"""Quick validation of difficulty.json output."""
import json, os, sys
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'outputs', 'data')

with open(os.path.join(OUT_DIR, 'difficulty.json')) as f:
    d = json.load(f)

print('Keys:', list(d.keys()))
print('Dimensions:', d['dimensions'])
print('Weights:', d['weights'])
print('Thresholds:', d['thresholds'])
print()

v = d['validation']
print(f"Validation: rho={v['spearman_rho']}, p={v['spearman_p']}, r={v['pearson_r']}")
print()

print('=== DATED PUZZLES (sorted by composite) ===')
items = sorted(d['puzzles'].items(), key=lambda x: x[1]['composite'])
for date, p in items:
    sr = p['solve_rate']
    prof = p['profile']
    print(f"  {p['label']:20s}  SR={sr*100:5.1f}%  "
          f"rating={p['rating']}  comp={p['composite']:.3f}  "
          f"dec={prof['impostor_deception']:.2f} kno={prof['knowledge_demand']:.2f} "
          f"pun={prof['punishment_risk']:.2f} con={prof['connection_challenge']:.2f} "
          f"vol={prof['volatility']:.2f}")
print()

print('=== UNDATED (top 5 hardest) ===')
items2 = sorted(d['undated'].items(), key=lambda x: x[1]['composite'], reverse=True)
for lid, p in items2[:5]:
    print(f"  {p['name']:25s}  pred_SR={p['predicted_solve_rate']:5.1f}%  "
          f"rating={p['rating']}  comp={p['composite']:.3f}")
print()

print('=== RATING DISTRIBUTION ===')
all_ratings = [p['rating'] for p in d['puzzles'].values()] + \
              [p['rating'] for p in d['undated'].values()]
for r, n in sorted(Counter(all_ratings).items()):
    print(f'  {r} stars: {n} puzzles')
print()

# Sanity: all scores in [0,1]
errors = []
for key, puzzles in [('puzzles', d['puzzles']), ('undated', d['undated'])]:
    for pid, p in puzzles.items():
        for dim, val in p['profile'].items():
            if val < 0 or val > 1:
                errors.append(f"{key}/{pid}/{dim}={val}")
        if p['composite'] < 0 or p['composite'] > 1:
            errors.append(f"{key}/{pid}/composite={p['composite']}")
if errors:
    print("ERRORS (out of range):", errors)
else:
    print("All scores in [0, 1] range ✓")

# Check explorer injection
with open(os.path.join(OUT_DIR, 'puzzle-explorer.json')) as f:
    ex = json.load(f)
dated_with_diff = sum(1 for p in ex['puzzles'].values() if 'difficulty' in p)
undated_with_diff = sum(1 for p in ex.get('undated_puzzles', {}).values() if 'difficulty' in p)
print(f"Explorer injection: {dated_with_diff} dated, {undated_with_diff} undated have 'difficulty' key ✓")
