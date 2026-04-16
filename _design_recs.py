"""Extract actionable design recommendations from analysis data."""
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'relink', 'outputs', 'data')

def load(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)

ct = load('crosstabs.json')
hm = load('heatmap.json')
imp = load('impostor-domain.json')
corr = load('correlations.json')
reg = load('regression.json')
rl = load('relink.json')
sim = load('simulator.json')
dec = load('decoys.json')
trans = load('transitions.json')

print("=" * 70)
print("DESIGN RECOMMENDATIONS — Evidence Base")
print("=" * 70)

# 1. Cross-tabs: what first-try rates come from each PDL category?
print("\n### ROW-LEVEL DIFFICULTY BY PDL TAG ###\n")
for axis_name in ['Manipulation', 'Abstraction', 'Knowledge']:
    data = ct[axis_name]
    print(f"  {axis_name}:")
    for i, label in enumerate(data['labels']):
        ft = data['first_try'][i]
        aw = data['avg_wrong'][i]
        n = data['n'][i]
        print(f"    {label:<30} {ft:>5.1f}% first-try, {aw:.2f} avg wrong  (n={n})")
    print()

# 2. Impostor domain effect
print("### IMPOSTOR DOMAIN EFFECT ###\n")
sd = imp['same_domain']
dd = imp['diff_domain']
print(f"  Same domain:      {sd['mean_first_try']}% first-try, {sd['mean_avg_wrong']} avg wrong  (n={sd['n']})")
print(f"  Different domain:  {dd['mean_first_try']}% first-try, {dd['mean_avg_wrong']} avg wrong  (n={dd['n']})")
print(f"  Delta:             {dd['mean_first_try'] - sd['mean_first_try']:+.1f}pp easier with different domain")

# 3. Decoy effect
print("\n### DECOY EFFECT ###\n")
nd = dec['no_decoys']
hd = dec['has_decoys']
print(f"  No decoys:   {nd['mean_solve_rate']*100:.1f}% solve rate, {nd['mean_avg_wrong']:.2f} avg wrong  (n={nd['n']} puzzles)")
print(f"  Has decoys:  {hd['mean_solve_rate']*100:.1f}% solve rate, {hd['mean_avg_wrong']:.2f} avg wrong  (n={hd['n']} puzzles)")

# 4. Relink phase
print("\n### RELINK PHASE — BY CONSTRUCTION TYPE ###\n")
for manip, stats in sorted(rl.get('by_con_manip', {}).items()):
    print(f"  {manip:<25} {stats['mean_first_try']*100:>5.1f}% first-try, {stats['mean_attempts']:.2f} avg attempts  (n={stats['n']})")

print("\n### RELINK PHASE — BY IDENTIFICATION TYPE ###\n")
for manip, stats in sorted(rl.get('by_id_manip', {}).items()):
    print(f"  {manip:<25} {stats['mean_first_try']*100:>5.1f}% first-try, {stats['mean_attempts']:.2f} avg attempts  (n={stats['n']})")

print("\n### RELINK PHASE — BY TILE COUNT ###\n")
for tc, stats in sorted(rl.get('by_tiles', {}).items()):
    print(f"  {tc} tiles:  {stats['mean_first_try']*100:>5.1f}% first-try, {stats['mean_attempts']:.2f} avg attempts, {stats['mean_solve_rate']*100:.1f}% solve rate  (n={stats['n']})")

# 5. Correlations
print("\n### PUZZLE-LEVEL FEATURE CORRELATIONS WITH SOLVE RATE ###\n")
for feat, data in corr.items():
    print(f"  {data['label']:<30} Pearson r={data['pearson_r']:+.3f}  Spearman={data['spearman_r']:+.3f}")

# 6. Regression coefficients
print("\n### PUZZLE-LEVEL REGRESSION ###\n")
preg = reg['puzzle']
for name, coef in zip(preg['names'], preg['coefs']):
    print(f"  {name:<35} coef={coef:+.4f}")
print(f"  R² = {preg['r2']}, LOO MAE = {preg['loo_mae']}pp")

# 7. Heatmap: manipulation x abstraction combos
print("\n### MANIPULATION × ABSTRACTION COMBINATIONS ###\n")
print(f"  {'Combination':<45} {'First-try %':>12}")
print("  " + "-" * 60)
for ai, abstr in enumerate(hm['abstrs']):
    for mi, manip in enumerate(hm['manips']):
        val = hm['values'][ai][mi]
        ann = hm['annotations'][ai][mi]
        if val is not None:
            print(f"  {manip + ' / ' + abstr:<45} {ann:>12}")

# 8. Simulator: dated puzzles in target range (65-95%)
print("\n### DATED PUZZLES IN TARGET RANGE (65-95% actual) ###\n")
for d, r in sorted(sim['puzzles'].items()):
    actual = r['actual_solve_rate']
    if 65 <= actual <= 95:
        print(f"  {r['name']:<35} actual={actual:.1f}%  sim={r['solve_rate']*100:.1f}%  "
              f"manip={r['manipulationComplexity']} abstr={r['abstractionComplexity']} tiles={r['phase2TileCount']}")

print("\n### DATED PUZZLES OUTSIDE TARGET (too hard) ###\n")
for d, r in sorted(sim['puzzles'].items()):
    actual = r['actual_solve_rate']
    if actual < 65:
        print(f"  {r['name']:<35} actual={actual:.1f}%  "
              f"manip={r['manipulationComplexity']} abstr={r['abstractionComplexity']} tiles={r['phase2TileCount']}")

# 9. Undated predictions in target range
print("\n### UNDATED PUZZLE PREDICTIONS — SORTED ###\n")
undated = [(lid, r) for lid, r in sim.get('undated', {}).items()]
undated.sort(key=lambda x: x[1]['solve_rate'], reverse=True)
for lid, r in undated:
    pred = r['solve_rate'] * 100
    marker = " <<<" if 65 <= pred <= 95 else (" (too easy)" if pred > 95 else " (too hard)")
    print(f"  {r['name']:<40} pred={pred:>5.1f}%  "
          f"manip={r['manipulationComplexity']} abstr={r['abstractionComplexity']} tiles={r['phase2TileCount']}{marker}")

# 10. Transition model: feature combo distributions
print("\n### FEATURE COMBO ERROR RATES (manipulation × decoy) ###\n")
combos = trans.get('by_feature_combo', {})
for key in sorted(combos.keys()):
    data = combos[key]
    print(f"  {key:<30} first-try={data['weighted_first_try']*100:>5.1f}%, mean_wrong={data['weighted_mean_wrong']:.3f}  (n={data['n']})")
