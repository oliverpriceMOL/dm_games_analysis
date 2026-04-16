import json, os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'relink', 'outputs', 'data')

with open(os.path.join(DATA_DIR, 'simulator.json')) as f:
    sim = json.load(f)

pairs = []
for d, r in sorted(sim['puzzles'].items()):
    actual = r['actual_solve_rate']
    predicted = round(r['solve_rate'] * 100, 1)
    pairs.append((r.get('name', d), actual, predicted, d))

actuals = [p[1] for p in pairs]
preds = [p[2] for p in pairs]
n = len(actuals)

print("=== DATED PUZZLES: Actual vs Predicted ===\n")
print(f"{'Puzzle':<35} {'Actual':>8} {'Pred':>8} {'Delta':>8}")
print("-" * 63)
for name, act, pred, d in pairs:
    print(f"{name:<35} {act:>7.1f}% {pred:>7.1f}% {pred - act:>+7.1f}")

# Rank correlation
def rank_list(v):
    s = sorted(range(len(v)), key=lambda i: v[i])
    r = [0] * len(v)
    for i, idx in enumerate(s):
        r[idx] = i + 1
    return r

ra = rank_list(actuals)
rp = rank_list(preds)
d2 = sum((a - b) ** 2 for a, b in zip(ra, rp))
spearman = 1 - 6 * d2 / (n * (n * n - 1))

print(f"\nSpearman rank correlation (empirical mode): {spearman:.3f}")
print(f"Pearson r (empirical mode): {sim['validation']['r']}")

# Now do feature-only ranking
# Re-run feature-only predictions from the simulator data
# The feature_validation gives aggregate stats but not per-puzzle
# Let's compute rank from the empirical results since that's what we have

# Show rank comparison
print(f"\n=== RANK ORDERING (easiest -> hardest) ===\n")
actual_order = sorted(range(n), key=lambda i: actuals[i], reverse=True)
pred_order = sorted(range(n), key=lambda i: preds[i], reverse=True)

print(f"{'Rank':>4}  {'Actual (easiest first)':<35} {'Predicted (easiest first)':<35}")
print("-" * 78)
for rank_i in range(n):
    ai = actual_order[rank_i]
    pi = pred_order[rank_i]
    a_name = f"{pairs[ai][0]} ({pairs[ai][1]:.0f}%)"
    p_name = f"{pairs[pi][0]} ({pairs[pi][2]:.0f}%)"
    match = " <-" if ai == pi else ""
    print(f"{rank_i+1:>4}  {a_name:<35} {p_name:<35}{match}")

# Pairwise ordering accuracy (Kendall's tau-like)
correct_pairs = 0
total_pairs = 0
for i in range(n):
    for j in range(i + 1, n):
        total_pairs += 1
        if (actuals[i] - actuals[j]) * (preds[i] - preds[j]) > 0:
            correct_pairs += 1
        elif actuals[i] == actuals[j] or preds[i] == preds[j]:
            correct_pairs += 0.5

print(f"\nPairwise ordering accuracy: {correct_pairs:.0f}/{total_pairs} ({correct_pairs/total_pairs*100:.0f}%)")

# Also show undated predictions for Apr 14/15
print("\n=== UNDATED PUZZLE PREDICTIONS ===\n")
undated = []
for lid, r in sim.get('undated', {}).items():
    pred_sr = round(r['solve_rate'] * 100, 1)
    undated.append((r.get('name', lid), pred_sr, r.get('date', ''), lid))

undated.sort(key=lambda x: x[1], reverse=True)
print(f"{'Puzzle':<40} {'Predicted':>10} {'Date':>12}")
print("-" * 65)
for name, pred_sr, date, lid in undated:
    date_str = date if date else "(undated)"
    print(f"{name:<40} {pred_sr:>9.1f}% {date_str:>12}")
