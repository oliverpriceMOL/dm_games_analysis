"""Check IPW survival table including relink step."""
import sys, os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RELINK_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.dirname(RELINK_DIR)
sys.path.insert(0, SCRIPT_DIR)
from lib.data import load_all
from lib import model

data = load_all(os.path.join(RELINK_DIR, 'save-data'), os.path.join(DATA_DIR, 'raw'))
players_by_date = data['players_by_date']
ipw = model.compute_ipw_weights(players_by_date)
st = ipw['survival_table']

print("=== SURVIVAL TABLE (pos,lives) ===")
for key in sorted(st.keys()):
    v = st[key]
    pos_label = 'relink' if key.startswith('4,') else f'row {key.split(",")[0]}'
    print(f'  {pos_label} (lives={key.split(",")[1]}): n={v["count"]:3d}, survived={v["survived"]:3d}, rate={v["rate"]:.1%}')

print(f'\nDiagnostics: {ipw["diagnostics"]}')

# Relink trajectory summary
rl_total = 0
rl_survived = 0
rl_lost = 0
for pp in players_by_date.values():
    for p in pp:
        rt = p.get('relink_trajectory')
        if rt:
            rl_total += 1
            if rt['survived']:
                rl_survived += 1
            else:
                rl_lost += 1

print(f'\nRelink trajectories: {rl_total} total, {rl_survived} survived, {rl_lost} lost')
