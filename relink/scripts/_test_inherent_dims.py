"""
Test inherent-only difficulty dimensions against 14 dated puzzles.
All inputs are pure PDL design properties — no player outcome data.
"""
import json, os, math

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(SCRIPT_DIR, '..', 'save-data')
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'outputs', 'data')

# Load puzzle index and PDL files
with open(os.path.join(SAVE_DIR, 'puzzles-index.json')) as f:
    index = json.load(f)['puzzles']

pdl = {}
for p in index:
    lid = p['id']
    path = os.path.join(SAVE_DIR, f'{lid}.json')
    if os.path.exists(path):
        with open(path) as f:
            pdl[lid] = json.load(f)

# Load difficulty.json for solve rates of dated puzzles
with open(os.path.join(DATA_DIR, 'difficulty.json')) as f:
    diff_data = json.load(f)

# Map date → lid from difficulty.json
dated_puzzles = []
for date, p in diff_data['puzzles'].items():
    dated_puzzles.append({
        'date': date,
        'lid': p['lid'],
        'name': p['name'],
        'label': p.get('label', date),
        'solve_rate': p['solve_rate'],
    })

print(f"=== Inherent-Only Difficulty Dimensions: {len(dated_puzzles)} Dated Puzzles ===\n")

# ── Manipulation type scores (from crosstab empirical effect sizes) ──
# Ranked by how much harder each type makes a row (1 - first_try_pct)
MANIP_SCORE = {
    'None': 0.2,           # 62% first-try → baseline
    'Compound': 0.5,       # 58% first-try → moderate
    'Hidden word': 1.0,    # 36% first-try → hardest
    'Homophone': 0.1,      # 72% first-try → easy
    'Letter add-delete': 0.5,  # similar to compound (limited data)
    'Word split': 0.0,     # 98% first-try → easiest
}

# ── Abstraction scores ──
ABSTR_SCORE = {
    'Direct membership': 0.0,   # 63% first-try → baseline
    'Association': 0.2,         # 65% first-try → similar to direct
    'Shared property': 0.6,     # 52% first-try → harder
}

# ── Relink answer construction manipulation scores ──
RELINK_CON_SCORE = {
    'None': 0.0,
    'Compound': 0.4,
    'Word split': 0.7,
    'Hidden word': 0.8,
}

def clamp01(v):
    return max(0.0, min(1.0, v))

def score_puzzle(lid):
    """Score a puzzle on 5 inherent dimensions using only PDL data."""
    p = pdl[lid]
    rows = p['rows']
    board = p.get('board', {})
    relink = p.get('relink', {})
    
    # 1. Manipulation Load: mean manipulation score across 4 rows
    manip_scores = []
    for row in rows:
        m = row.get('pdl', {}).get('group', {}).get('manipulation', ['None'])[0]
        manip_scores.append(MANIP_SCORE.get(m, 0.3))
    manipulation_load = sum(manip_scores) / 4.0
    
    # 2. Abstraction Load: mean abstraction score across 4 rows
    abstr_scores = []
    for row in rows:
        a = row.get('pdl', {}).get('group', {}).get('abstraction', ['Direct membership'])[0]
        abstr_scores.append(ABSTR_SCORE.get(a, 0.0))
    abstraction_load = sum(abstr_scores) / 4.0
    
    # 3. Domain Mismatch: fraction of rows where impostor domain ≠ group domain
    mismatch_count = 0
    for row in rows:
        group_domain = row.get('pdl', {}).get('group', {}).get('knowledgeDomain', ['General'])[0]
        imp_domain = row.get('pdl', {}).get('impostor', {}).get('realIdentityDomain', ['General'])[0]
        if group_domain != imp_domain:
            mismatch_count += 1
    domain_mismatch = mismatch_count / 4.0
    
    # 4. Knowledge Demand: breadth of knowledge domains + specialist presence
    domains = set()
    specialist_count = 0
    for row in rows:
        kd = row.get('pdl', {}).get('group', {}).get('knowledgeDomain', ['General'])[0]
        domains.add(kd)
        k = row.get('pdl', {}).get('group', {}).get('knowledge', ['General vocabulary'])[0]
        if k == 'Specialist cultural':
            specialist_count += 1
    breadth = len(domains)
    # Normalise: breadth 1→0, 5→1; specialist 0→0, 2→1
    norm_breadth = clamp01((breadth - 1) / 4.0)
    norm_specialist = clamp01(specialist_count / 2.0)
    knowledge_demand = 0.5 * norm_breadth + 0.5 * norm_specialist
    
    # 5. Relink Complexity: tile count + answer construction difficulty
    tile_count = board.get('phase2TileCount', relink.get('tiles', []) and len(relink.get('tiles', [])) or 1)
    tile_factor = clamp01((tile_count - 1) / 3.0)
    
    con_manip = 'None'
    relink_pdl = relink.get('pdl', {})
    if 'answerConstruction' in relink_pdl:
        ac = relink_pdl['answerConstruction']
        con_manip = ac.get('manipulation', ['None'])[0]
    con_score = RELINK_CON_SCORE.get(con_manip, 0.3)
    
    # Also factor in identification manipulation
    id_manip = 'None'
    if 'connectionIdentification' in relink_pdl:
        ci = relink_pdl['connectionIdentification']
        id_manip = ci.get('manipulation', ['None'])[0]
    id_score = MANIP_SCORE.get(id_manip, 0.3)
    
    relink_complexity = clamp01(0.3 * tile_factor + 0.4 * con_score + 0.3 * id_score)
    
    return {
        'manipulation_load': round(manipulation_load, 3),
        'abstraction_load': round(abstraction_load, 3),
        'domain_mismatch': round(domain_mismatch, 3),
        'knowledge_demand': round(knowledge_demand, 3),
        'relink_complexity': round(relink_complexity, 3),
    }

# Score all dated puzzles
DIMS = ['manipulation_load', 'abstraction_load', 'domain_mismatch',
        'knowledge_demand', 'relink_complexity']
DIM_LABELS = {
    'manipulation_load': 'Manipulation Load',
    'abstraction_load': 'Abstraction Load',
    'domain_mismatch': 'Domain Mismatch',
    'knowledge_demand': 'Knowledge Demand',
    'relink_complexity': 'Relink Complexity',
}

scored = []
for p in dated_puzzles:
    profile = score_puzzle(p['lid'])
    scored.append({**p, **profile})

# ── Per-dimension correlations ──
def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs)/n, sum(ys)/n
    cov = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x-mx)**2 for x in xs))
    sy = math.sqrt(sum((y-my)**2 for y in ys))
    return cov / (sx * sy) if sx > 0 and sy > 0 else 0

def spearman(xs, ys):
    def rank(arr):
        indexed = sorted(range(len(arr)), key=lambda i: arr[i])
        ranks = [0.0] * len(arr)
        for r, i in enumerate(indexed):
            ranks[i] = r + 1
        return ranks
    return pearson(rank(xs), rank(ys))

print("── Per-Dimension Correlations with Solve Rate ──\n")
print(f"  {'Dimension':<25s} {'Pearson r':>10s} {'Spearman ρ':>10s}")
print("  " + "-" * 47)
for d in DIMS:
    xs = [p[d] for p in scored]
    ys = [p['solve_rate'] for p in scored]
    r = pearson(xs, ys)
    rho = spearman(xs, ys)
    print(f"  {DIM_LABELS[d]:<25s} {r:>10.3f} {rho:>10.3f}")

print()

# ── Per-puzzle scores table ──
print("── Per-Puzzle Inherent Scores ──\n")
print(f"  {'Puzzle':<32s} {'SR%':>5s}  {'Manip':>5s} {'Abstr':>5s} {'DomMM':>5s} {'Know':>5s} {'Relnk':>5s}")
print("  " + "-" * 70)
for p in sorted(scored, key=lambda x: x['solve_rate'], reverse=True):
    print(f"  {p['label'] + ': ' + p['name']:<32s} {p['solve_rate']*100:>4.0f}%  "
          f"{p['manipulation_load']:>5.2f} {p['abstraction_load']:>5.2f} "
          f"{p['domain_mismatch']:>5.2f} {p['knowledge_demand']:>5.2f} "
          f"{p['relink_complexity']:>5.2f}")

print()

# ── Grid search for optimal weights ──
print("── Constrained Grid Search (5% increments, Σw=1, w≥0) ──\n")

STEP = 5
TARGET = 100 // STEP
best_r = 0
best_rho = 0
best_w_r = None
best_w_rho = None
count = 0

def composite(p, w):
    return sum(p[d] * w[d] for d in DIMS)

for w0 in range(TARGET + 1):
    for w1 in range(TARGET + 1 - w0):
        for w2 in range(TARGET + 1 - w0 - w1):
            for w3 in range(TARGET + 1 - w0 - w1 - w2):
                w4 = TARGET - w0 - w1 - w2 - w3
                count += 1
                weights = {DIMS[0]: w0/TARGET, DIMS[1]: w1/TARGET,
                          DIMS[2]: w2/TARGET, DIMS[3]: w3/TARGET,
                          DIMS[4]: w4/TARGET}
                comps = [composite(p, weights) for p in scored]
                srs = [p['solve_rate'] for p in scored]
                
                r = abs(pearson(comps, srs))
                rho = abs(spearman(comps, srs))
                
                if r > best_r:
                    best_r = r
                    best_w_r = dict(weights)
                if rho > best_rho:
                    best_rho = rho
                    best_w_rho = dict(weights)

print(f"  Evaluated {count:,} weight combinations\n")

def show_weights(w, label, corr_label, corr_val):
    print(f"  {label} (|{corr_label}| = {corr_val:.4f}):")
    for d in DIMS:
        print(f"    {DIM_LABELS[d]:<25s} {w[d]*100:>5.1f}%")
    comps = [composite(p, w) for p in scored]
    srs = [p['solve_rate'] for p in scored]
    r = pearson(comps, srs)
    rho = spearman(comps, srs)
    print(f"    → Pearson r = {r:.4f}, Spearman ρ = {rho:.4f}")
    print()

show_weights(best_w_r, "Best Pearson", "r", best_r)
show_weights(best_w_rho, "Best Spearman", "ρ", best_rho)

# ── LOO stability ──
print("── Leave-One-Out Stability ──\n")
n = len(scored)
loo_weights = {d: [] for d in DIMS}
loo_errors = []
for leave_out in range(n):
    subset = [p for i, p in enumerate(scored) if i != leave_out]
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
    
    # Predict the left-out puzzle
    left = scored[leave_out]
    pred_comp = composite(left, best_w_loo)
    loo_errors.append(pred_comp)
    
    print(f"  Leave out {left['label']:<12s}: " +
          ', '.join(f'{DIM_LABELS[d][:6]}={best_w_loo[d]:.0%}' for d in DIMS) +
          f"  |r|={best_r_loo:.4f}")

print(f"\n  LOO weight ranges:")
for d in DIMS:
    vals = loo_weights[d]
    lo, hi = min(vals), max(vals)
    avg = sum(vals) / len(vals)
    print(f"    {DIM_LABELS[d]:<25s} {lo:.0%}–{hi:.0%}  (mean {avg:.0%})")

# ── OLS regression ──
print(f"\n── OLS Regression: solve_rate ~ dimensions ──\n")

X = []
y = []
for p in scored:
    X.append([1.0] + [p[d] for d in DIMS])
    y.append(p['solve_rate'])

def mat_T(A):
    return [[A[i][j] for i in range(len(A))] for j in range(len(A[0]))]

def mat_mul(A, B):
    ra, ca = len(A), len(A[0])
    rb, cb = len(B), len(B[0])
    return [[sum(A[i][k] * B[k][j] for k in range(ca)) for j in range(cb)] for i in range(ra)]

def mat_inv(M):
    n = len(M)
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(M)]
    for col in range(n):
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
XTX = mat_mul(XT, X)
XTy = mat_mul(XT, [[yi] for yi in y])
XTX_inv = mat_inv(XTX)

if XTX_inv:
    beta = [sum(XTX_inv[i][j] * XTy[j][0] for j in range(len(XTy))) for i in range(len(XTX_inv))]
    y_pred = [sum(X[i][j] * beta[j] for j in range(6)) for i in range(n)]
    ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
    y_mean = sum(y) / n
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    r_sq = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    adj_r_sq = 1 - (1 - r_sq) * (n - 1) / (n - 6) if n > 6 else r_sq
    
    print(f"  {'Intercept':<25s} {beta[0]:>8.4f}")
    for i, d in enumerate(DIMS):
        print(f"  {DIM_LABELS[d]:<25s} {beta[i+1]:>8.4f}")
    print(f"\n  R² = {r_sq:.3f},  Adjusted R² = {adj_r_sq:.3f}")
    
    # Implied weights from |coefficients|
    abs_betas = {d: abs(beta[i+1]) for i, d in enumerate(DIMS)}
    total = sum(abs_betas.values())
    if total > 0:
        print(f"\n  OLS implied weights (|coeff| normalised):")
        for d in DIMS:
            sign = "−" if beta[DIMS.index(d)+1] < 0 else "+"
            print(f"    {DIM_LABELS[d]:<25s} {abs_betas[d]/total*100:>5.1f}%  ({sign}{abs_betas[d]:.4f})")

print("\nDone.")
