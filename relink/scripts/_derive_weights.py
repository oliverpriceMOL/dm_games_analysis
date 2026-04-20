"""
Derive optimal difficulty dimension weights from the 14 dated puzzles.
Compares hand-tuned vs data-derived weights using constrained grid search
and unconstrained OLS regression.
"""
import json, os, sys, math, itertools

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'outputs', 'data')

with open(os.path.join(DATA_DIR, 'difficulty.json')) as f:
    data = json.load(f)

DIMS = ['impostor_deception', 'punishment_risk', 'connection_challenge',
        'knowledge_demand', 'volatility']
DIM_LABELS = {
    'impostor_deception': 'Impostor Deception',
    'punishment_risk': 'Punishment Risk',
    'connection_challenge': 'Connection Challenge',
    'knowledge_demand': 'Knowledge Demand',
    'volatility': 'Volatility',
}

# Extract dated puzzles: dimension scores + solve rates
puzzles = []
for date, p in data['puzzles'].items():
    row = {d: p['profile'][d] for d in DIMS}
    row['solve_rate'] = p['solve_rate']
    row['name'] = p['name']
    row['label'] = p.get('label', date)
    puzzles.append(row)

n = len(puzzles)
print(f"=== Deriving Difficulty Weights from {n} Dated Puzzles ===\n")

# ── Current hand-tuned weights ──
CURRENT = {'impostor_deception': 0.30, 'punishment_risk': 0.25,
           'connection_challenge': 0.20, 'knowledge_demand': 0.15,
           'volatility': 0.10}

def composite(p, w):
    return sum(p[d] * w[d] for d in DIMS)

def pearson(xs, ys):
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
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

def mae(xs, ys):
    return sum(abs(x - y) for x, y in zip(xs, ys)) / len(xs)

# ── 1. Per-dimension correlations with solve rate ──
print("── Per-Dimension Correlations with Solve Rate ──\n")
print(f"{'Dimension':<25s} {'Pearson r':>10s} {'Spearman ρ':>10s}")
print("-" * 47)
for d in DIMS:
    xs = [p[d] for p in puzzles]
    ys = [p['solve_rate'] for p in puzzles]
    r = pearson(xs, ys)
    rho = spearman(xs, ys)
    print(f"{DIM_LABELS[d]:<25s} {r:>10.3f} {rho:>10.3f}")

print()

# ── 2. Unconstrained OLS: solve_rate = a + b1*d1 + ... + b5*d5 ──
# Solve via normal equations: β = (X'X)^-1 X'y
print("── Unconstrained OLS Regression ──\n")
print("  solve_rate = a + b₁·deception + b₂·punishment + b₃·connection + b₄·knowledge + b₅·volatility\n")

# Build X matrix (n×6) with intercept column
X = []
y = []
for p in puzzles:
    X.append([1.0] + [p[d] for d in DIMS])
    y.append(p['solve_rate'])

def mat_mul(A, B):
    """Multiply two matrices (lists of lists)."""
    ra, ca = len(A), len(A[0])
    rb, cb = len(B), len(B[0])
    assert ca == rb
    return [[sum(A[i][k] * B[k][j] for k in range(ca)) for j in range(cb)] for i in range(ra)]

def mat_T(A):
    return [[A[i][j] for i in range(len(A))] for j in range(len(A[0]))]

def mat_inv(M):
    """Invert a small matrix via Gauss-Jordan."""
    n = len(M)
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(M)]
    for col in range(n):
        # Partial pivot
        max_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
        aug[col], aug[max_row] = aug[max_row], aug[col]
        pivot = aug[col][col]
        if abs(pivot) < 1e-12:
            return None
        for j in range(2 * n):
            aug[col][j] /= pivot
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            for j in range(2 * n):
                aug[row][j] -= factor * aug[col][j]
    return [row[n:] for row in aug]

XT = mat_T(X)
XTX = mat_mul(XT, [list(row) for row in X])
XTy = mat_mul(XT, [[yi] for yi in y])
XTX_inv = mat_inv(XTX)

if XTX_inv:
    beta = [sum(XTX_inv[i][j] * XTy[j][0] for j in range(len(XTy))) for i in range(len(XTX_inv))]
    
    print(f"  {'Intercept':<25s} {beta[0]:>8.4f}")
    for i, d in enumerate(DIMS):
        print(f"  {DIM_LABELS[d]:<25s} {beta[i+1]:>8.4f}")
    
    # Goodness of fit
    y_pred = [sum(X[i][j] * beta[j] for j in range(6)) for i in range(n)]
    ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
    y_mean = sum(y) / n
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    r_sq = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    adj_r_sq = 1 - (1 - r_sq) * (n - 1) / (n - 6) if n > 6 else r_sq
    
    print(f"\n  R² = {r_sq:.3f},  Adjusted R² = {adj_r_sq:.3f}")
    print(f"  Residual SE = {math.sqrt(ss_res / (n - 6)):.4f}")
    
    # Derive relative weights from absolute coefficients (negative = higher difficulty → lower solve rate)
    abs_betas = {d: abs(beta[i+1]) for i, d in enumerate(DIMS)}
    total_abs = sum(abs_betas.values())
    if total_abs > 0:
        ols_weights = {d: abs_betas[d] / total_abs for d in DIMS}
        print(f"\n  Implied weights (|coefficient| normalised):")
        for d in DIMS:
            sign = "−" if beta[DIMS.index(d)+1] < 0 else "+"
            print(f"    {DIM_LABELS[d]:<25s} {ols_weights[d]*100:>5.1f}%  (coeff {sign}{abs_betas[d]:.4f})")
else:
    print("  [Matrix singular — cannot solve OLS]")
    ols_weights = None

print()

# ── 3. Constrained grid search: weights in [0,1], sum to 1 ──
# We want composite = Σ(w_i * d_i) to maximally anti-correlate with solve_rate
# Grid at 5% increments (21 levels per dimension, 5 dimensions summing to 1)
print("── Constrained Grid Search (5% increments, Σw=1, w≥0) ──\n")

STEP = 5  # percentage points
best_r = 0
best_rho = 0
best_mae_val = 999
best_w_r = None
best_w_rho = None
best_w_mae = None
count = 0

# Generate all 5-tuples of non-negative integers summing to 20 (= 100/5)
TARGET = 100 // STEP
for w0 in range(TARGET + 1):
    for w1 in range(TARGET + 1 - w0):
        for w2 in range(TARGET + 1 - w0 - w1):
            for w3 in range(TARGET + 1 - w0 - w1 - w2):
                w4 = TARGET - w0 - w1 - w2 - w3
                count += 1
                weights = {DIMS[0]: w0/TARGET, DIMS[1]: w1/TARGET,
                          DIMS[2]: w2/TARGET, DIMS[3]: w3/TARGET,
                          DIMS[4]: w4/TARGET}
                comps = [composite(p, weights) for p in puzzles]
                srs = [p['solve_rate'] for p in puzzles]
                
                r = abs(pearson(comps, srs))
                rho = abs(spearman(comps, srs))
                
                if r > best_r:
                    best_r = r
                    best_w_r = dict(weights)
                if rho > best_rho:
                    best_rho = rho
                    best_w_rho = dict(weights)

print(f"  Evaluated {count:,} weight combinations\n")

print(f"  Best by |Pearson r| = {best_r:.4f}:")
for d in DIMS:
    print(f"    {DIM_LABELS[d]:<25s} {best_w_r[d]*100:>5.1f}%")

print(f"\n  Best by |Spearman ρ| = {best_rho:.4f}:")
for d in DIMS:
    print(f"    {DIM_LABELS[d]:<25s} {best_w_rho[d]*100:>5.1f}%")

# ── 4. Compare current vs derived ──
print(f"\n── Comparison: Current vs Derived ──\n")

def eval_weights(w, label):
    comps = [composite(p, w) for p in puzzles]
    srs = [p['solve_rate'] for p in puzzles]
    r = pearson(comps, srs)
    rho = spearman(comps, srs)
    print(f"  {label}:")
    print(f"    Pearson r  = {r:.4f}")
    print(f"    Spearman ρ = {rho:.4f}")
    print(f"    Weights: {', '.join(f'{DIM_LABELS[d]}={w[d]:.0%}' for d in DIMS)}")
    print()
    return r, rho

eval_weights(CURRENT, "Hand-tuned")
eval_weights(best_w_r, "Best Pearson")
eval_weights(best_w_rho, "Best Spearman")

# ── 5. Per-puzzle comparison ──
print("── Per-Puzzle Composite Scores (Hand-tuned vs Best-Pearson) ──\n")
print(f"  {'Puzzle':<35s} {'Solve%':>6s} {'Hand':>6s} {'Derived':>7s} {'Δ':>6s}")
print("  " + "-" * 62)
for p in sorted(puzzles, key=lambda x: x['solve_rate'], reverse=True):
    c_hand = composite(p, CURRENT)
    c_best = composite(p, best_w_r)
    delta = c_best - c_hand
    print(f"  {p['label'] + ': ' + p['name']:<35s} {p['solve_rate']*100:>5.1f}% {c_hand:>6.3f} {c_best:>7.3f} {delta:>+6.3f}")

# ── 6. Stability check: leave-one-out ──
print(f"\n── Leave-One-Out Stability Check ──\n")
print("  For each left-out puzzle, re-derive optimal Pearson weights and report them.\n")

loo_weights = {d: [] for d in DIMS}
for leave_out in range(n):
    subset = [p for i, p in enumerate(puzzles) if i != leave_out]
    best_r_loo = 0
    best_w_loo = None
    for w0 in range(TARGET + 1):
        for w1 in range(TARGET + 1 - w0):
            for w2 in range(TARGET + 1 - w0 - w1):
                for w3 in range(TARGET + 1 - w0 - w1 - w2):
                    w4 = TARGET - w0 - w1 - w2 - w3
                    weights = {DIMS[0]: w0/TARGET, DIMS[1]: w1/TARGET,
                              DIMS[2]: w2/TARGET, DIMS[3]: w3/TARGET,
                              DIMS[4]: w4/TARGET}
                    comps = [composite(p, weights) for p in subset]
                    srs = [p['solve_rate'] for p in subset]
                    r = abs(pearson(comps, srs))
                    if r > best_r_loo:
                        best_r_loo = r
                        best_w_loo = dict(weights)
    
    for d in DIMS:
        loo_weights[d].append(best_w_loo[d])
    left = puzzles[leave_out]
    print(f"  Leave out {left['label']:<12s}: " +
          ', '.join(f'{DIM_LABELS[d][:8]}={best_w_loo[d]:.0%}' for d in DIMS) +
          f"  |r|={best_r_loo:.4f}")

print(f"\n  LOO weight ranges:")
for d in DIMS:
    vals = loo_weights[d]
    lo, hi = min(vals), max(vals)
    avg = sum(vals) / len(vals)
    print(f"    {DIM_LABELS[d]:<25s} {lo:.0%}–{hi:.0%}  (mean {avg:.0%})")

print("\nDone.")
