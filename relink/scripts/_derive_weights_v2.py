"""
Derive optimal difficulty dimension weights for the new 5-dimension system.
Grid search over all weight combinations (5% increments, sum=1) on 14 dated puzzles.
Also runs LOO cross-validation to check stability.
"""
import json, os, math

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'outputs', 'data')

with open(os.path.join(DATA_DIR, 'difficulty.json')) as f:
    data = json.load(f)

DIMS = data['dimensions']
DIM_LABELS = data['dimension_labels']
CURRENT = data['weights']

# Extract dated puzzles
puzzles = []
for date, p in data['puzzles'].items():
    puzzles.append({
        'name': p['name'],
        'profile': p['profile'],
        'predicted_profile': p.get('predicted_profile', p['profile']),
        'solve_rate': p['solve_rate'],
    })

n = len(puzzles)
print(f"=== Deriving Weights from {n} Dated Puzzles ===\n")
print(f"Dimensions: {', '.join(DIM_LABELS[d] for d in DIMS)}\n")


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return cov / (sx * sy) if sx > 0 and sy > 0 else 0


def spearman(xs, ys):
    def rank(arr):
        indexed = sorted(range(len(arr)), key=lambda i: arr[i])
        ranks = [0.0] * len(arr)
        for r, i in enumerate(indexed):
            ranks[i] = r + 1
        return ranks
    return pearson(rank(xs), rank(ys))


def composite(profile, w):
    return sum(profile[d] * w[d] for d in DIMS)


# ── 1. Per-dimension correlations ──
print("── Per-Dimension Correlations with Solve Rate ──\n")
print(f"  {'Dimension':<20s} {'Pearson r':>10s} {'Spearman ρ':>10s}    (actual profile)")
print("  " + "-" * 44)
for d in DIMS:
    xs = [p['profile'][d] for p in puzzles]
    ys = [p['solve_rate'] for p in puzzles]
    print(f"  {DIM_LABELS[d]:<20s} {pearson(xs, ys):>10.3f} {spearman(xs, ys):>10.3f}")

print()
print(f"  {'Dimension':<20s} {'Pearson r':>10s} {'Spearman ρ':>10s}    (predicted profile)")
print("  " + "-" * 44)
for d in DIMS:
    xs = [p['predicted_profile'][d] for p in puzzles]
    ys = [p['solve_rate'] for p in puzzles]
    print(f"  {DIM_LABELS[d]:<20s} {pearson(xs, ys):>10.3f} {spearman(xs, ys):>10.3f}")
print()

# ── 2. Current weights ──
cs = [composite(p['profile'], CURRENT) for p in puzzles]
srs = [p['solve_rate'] for p in puzzles]
print(f"── Current Weights ──\n")
for d in DIMS:
    print(f"  {DIM_LABELS[d]:<20s}  {CURRENT[d]:.0%}")
print(f"\n  Pearson r  = {pearson(cs, srs):.3f}")
print(f"  Spearman ρ = {spearman(cs, srs):.3f}\n")

# ── 3. Grid search (5% increments) ──
print("── Grid Search (5% increments, Σw=1, 10% floor) ──\n")

STEP = 5
FLOOR = 10
best_r = 0
best_w = None
count = 0

# Generate all 5-tuples that sum to 100, in steps of STEP, min FLOOR each
for a in range(FLOOR, 101, STEP):
    for b in range(FLOOR, 101 - a, STEP):
        for c in range(FLOOR, 101 - a - b, STEP):
            for d_val in range(FLOOR, 101 - a - b - c, STEP):
                e = 100 - a - b - c - d_val
                if e < FLOOR:
                    continue
                count += 1
                w = {DIMS[0]: a/100, DIMS[1]: b/100, DIMS[2]: c/100,
                     DIMS[3]: d_val/100, DIMS[4]: e/100}
                cs = [composite(p['profile'], w) for p in puzzles]
                r = abs(pearson(cs, srs))
                if r > best_r:
                    best_r = r
                    best_w = w.copy()

print(f"  Tested {count:,} combinations")
print(f"  Best |Pearson r| = {best_r:.4f}\n")
print(f"  Optimal weights:")
for d in DIMS:
    tag = " ←" if best_w[d] > 0 else ""
    print(f"    {DIM_LABELS[d]:<20s}  {best_w[d]:.0%}{tag}")

# Check Spearman too
cs_best = [composite(p['profile'], best_w) for p in puzzles]
print(f"\n  Spearman ρ = {spearman(cs_best, srs):.3f}")

# ── 4. Also optimise on predicted profiles ──
print("\n── Grid Search on Predicted Profiles (10% floor) ──\n")

best_r_pred = 0
best_w_pred = None

for a in range(FLOOR, 101, STEP):
    for b in range(FLOOR, 101 - a, STEP):
        for c in range(FLOOR, 101 - a - b, STEP):
            for d_val in range(FLOOR, 101 - a - b - c, STEP):
                e = 100 - a - b - c - d_val
                if e < FLOOR:
                    continue
                w = {DIMS[0]: a/100, DIMS[1]: b/100, DIMS[2]: c/100,
                     DIMS[3]: d_val/100, DIMS[4]: e/100}
                cs = [composite(p['predicted_profile'], w) for p in puzzles]
                r = abs(pearson(cs, srs))
                if r > best_r_pred:
                    best_r_pred = r
                    best_w_pred = w.copy()

print(f"  Best |Pearson r| = {best_r_pred:.4f}\n")
print(f"  Optimal weights (predicted):")
for d in DIMS:
    tag = " ←" if best_w_pred[d] > 0 else ""
    print(f"    {DIM_LABELS[d]:<20s}  {best_w_pred[d]:.0%}{tag}")

cs_pred = [composite(p['predicted_profile'], best_w_pred) for p in puzzles]
print(f"\n  Spearman ρ = {spearman(cs_pred, srs):.3f}")

# ── 5. LOO cross-validation for best actual weights ──
print("\n── LOO Cross-Validation (actual, 5% grid) ──\n")

loo_errors = []
for leave_out in range(n):
    train = [p for i, p in enumerate(puzzles) if i != leave_out]
    test_p = puzzles[leave_out]
    train_srs = [p['solve_rate'] for p in train]

    best_loo_r = 0
    best_loo_w = None
    for a in range(FLOOR, 101, STEP):
        for b in range(FLOOR, 101 - a, STEP):
            for c in range(FLOOR, 101 - a - b, STEP):
                for d_val in range(FLOOR, 101 - a - b - c, STEP):
                    e = 100 - a - b - c - d_val
                    if e < FLOOR:
                        continue
                    w = {DIMS[0]: a/100, DIMS[1]: b/100, DIMS[2]: c/100,
                         DIMS[3]: d_val/100, DIMS[4]: e/100}
                    cs = [composite(p['profile'], w) for p in train]
                    r = abs(pearson(cs, train_srs))
                    if r > best_loo_r:
                        best_loo_r = r
                        best_loo_w = w.copy()

    # Show which weights were picked
    active = [f"{DIM_LABELS[d]}={best_loo_w[d]:.0%}" for d in DIMS if best_loo_w[d] > 0]
    print(f"  Leave out {test_p['name']:<25s}  "
          f"|r|={best_loo_r:.3f}  weights: {', '.join(active)}")

# ── 6. Top 10 weight combinations ──
print("\n── Top 10 Weight Combinations (actual) ──\n")

results = []
for a in range(0, 101, STEP):
    for b in range(0, 101 - a, STEP):
        for c in range(0, 101 - a - b, STEP):
            for d_val in range(0, 101 - a - b - c, STEP):
                e = 100 - a - b - c - d_val
                if e < 0:
                    continue
                w = {DIMS[0]: a/100, DIMS[1]: b/100, DIMS[2]: c/100,
                     DIMS[3]: d_val/100, DIMS[4]: e/100}
                cs_vals = [composite(p['profile'], w) for p in puzzles]
                r = abs(pearson(cs_vals, srs))
                rho = abs(spearman(cs_vals, srs))
                results.append((r, rho, w))

results.sort(key=lambda x: -x[0])
abbrevs = [DIM_LABELS[d][:4] for d in DIMS]
header = "  " + "  ".join(f"{a:>5s}" for a in abbrevs) + "   |r|     |ρ|"
print(header)
print("  " + "-" * len(header))
for r, rho, w in results[:10]:
    vals = "  ".join(f"{w[d]*100:>4.0f}%" for d in DIMS)
    print(f"  {vals}  {r:.4f}  {rho:.4f}")
