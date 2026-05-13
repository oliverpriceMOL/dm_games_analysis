"""Compare all-user solve rates vs trajectory-only (device_id) solve rates."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'relink', 'scripts'))
from lib.data import load_all

data = load_all('relink/save-data', 'raw')
ca = data['completions_all']

# Build canonical ID lookup
canonical = {}
for d, lid in data['date_to_level'].items():
    pf = data['pdl_puzzles'].get(lid, {})
    canonical[d] = pf.get('canonicalId', '')

print()
print("Date         | All-user solve rate      | Trajectory solve rate    | Diff")
print("-------------|--------------------------|--------------------------|------")
for d in sorted(ca.keys()):
    # All-user: filter to canonical level_id only
    canon = canonical.get(d, '')
    if canon and canon in ca[d]:
        w = ca[d][canon]['wins']
        l = ca[d][canon]['losses']
    else:
        w = sum(v['wins'] for v in ca[d].values())
        l = sum(v['losses'] for v in ca[d].values())
    comp = w + l
    sr_all = w / comp * 100 if comp else 0

    # Trajectory (device_id players only)
    pp = data['players_by_date'].get(d, [])
    tw = sum(1 for p in pp if p['outcome'] == 'WON')
    tl = sum(1 for p in pp if p['outcome'] == 'LOST')
    tc = tw + tl
    sr_traj = tw / tc * 100 if tc else 0

    diff = sr_all - sr_traj
    print(f"  {d} | {w:>6}/{comp:>6} = {sr_all:5.1f}% | {tw:>6}/{tc:>6} = {sr_traj:5.1f}% | {diff:+5.1f}pp")
