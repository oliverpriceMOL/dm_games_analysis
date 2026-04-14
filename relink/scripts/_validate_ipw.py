"""Quick IPW validation script — run from data/ root."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.data import load_all
from lib.model import compute_ipw_weights
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RELINK_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.dirname(RELINK_DIR)

data = load_all(os.path.join(RELINK_DIR, 'save-data'), os.path.join(DATA_DIR, 'raw'))
ipw = compute_ipw_weights(data['players_by_date'])

print("=== Survival Table ===")
print(f"{'State (pos,lives)':<20} {'Count':>6} {'Survived':>9} {'Rate':>8}")
for state_key in sorted(ipw['survival_table'].keys()):
    v = ipw['survival_table'][state_key]
    print(f"  {state_key:<18} {v['count']:>6} {v['survived']:>9} {v['rate']:>8.1%}")

print(f"\n=== Diagnostics ===")
for k, v in ipw['diagnostics'].items():
    print(f"  {k}: {v}")

# Check bias correction: raw vs IPW-weighted first-try rates at different positions
pos_raw = defaultdict(list)
pos_weighted = defaultdict(list)
for (d, sid), steps in ipw['player_weights'].items():
    pp = [p for p in data['players_by_date'][d] if p['sid'] == sid]
    if not pp:
        continue
    p = pp[0]
    traj = p.get('trajectory', [])
    for step, sw in zip(traj, steps):
        first_try = 1 if step['wrong_count'] == 0 else 0
        pos_raw[step['position']].append(first_try)
        pos_weighted[step['position']].append((first_try, sw['weight']))

print(f"\n=== Position Bias Check ===")
print(f"{'Position':<10} {'Raw 1st-try %':>15} {'IPW-weighted':>15} {'N':>6}")
for pos in range(4):
    raw_vals = pos_raw.get(pos, [])
    wt_vals = pos_weighted.get(pos, [])
    raw_mean = sum(raw_vals) / len(raw_vals) * 100 if raw_vals else 0
    wt_sum = sum(v * w for v, w in wt_vals)
    w_total = sum(w for _, w in wt_vals)
    wt_mean = wt_sum / w_total * 100 if w_total else 0
    print(f"  pos {pos:<6} {raw_mean:>14.1f}% {wt_mean:>14.1f}% {len(raw_vals):>6}")
