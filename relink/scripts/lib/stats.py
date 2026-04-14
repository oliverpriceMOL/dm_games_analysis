"""Pure math / statistics functions. No I/O, no side effects."""

import math
import json


def safe_mean(vals):
    return sum(vals) / len(vals) if vals else 0


def safe_median(vals):
    if not vals:
        return 0
    s = sorted(vals)
    n = len(s)
    return (s[n // 2] + s[(n - 1) // 2]) / 2


def safe_stdev(vals):
    if len(vals) < 2:
        return 0
    m = safe_mean(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))


def percentile(vals, p):
    """Linear interpolation percentile (p in 0-100)."""
    if not vals:
        return 0
    s = sorted(vals)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (k - f) * (s[c] - s[f])


def pct_str(num, den):
    return f"{num}/{den} ({num*100/den:.0f}%)" if den else "n/a"


# ── Correlation ──

def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return 0, 1.0
    mx, my = safe_mean(xs), safe_mean(ys)
    sx = math.sqrt(sum((x - mx)**2 for x in xs))
    sy = math.sqrt(sum((y - my)**2 for y in ys))
    if sx == 0 or sy == 0:
        return 0, 1.0
    r = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)
    if abs(r) >= 1:
        return r, 0
    t = r * math.sqrt((n - 2) / (1 - r * r))
    p = _t_pvalue(t, n - 2)
    return r, p


def spearman(xs, ys):
    n = len(xs)
    if n < 3:
        return 0, 1.0

    def rank(v):
        s = sorted(range(n), key=lambda i: v[i])
        r = [0] * n
        for i, idx in enumerate(s):
            r[idx] = i + 1
        return r

    rx, ry = rank(xs), rank(ys)
    d2 = sum((a - b) ** 2 for a, b in zip(rx, ry))
    rs = 1 - 6 * d2 / (n * (n * n - 1))
    if abs(rs) >= 1:
        return rs, 0
    t = rs * math.sqrt((n - 2) / (1 - rs * rs))
    p = _t_pvalue(t, n - 2)
    return rs, p


def _t_pvalue(t, df):
    """Approximate two-tailed p-value for t distribution."""
    x = df / (df + t * t)
    if df <= 0:
        return 1.0
    return _betai(0.5 * df, 0.5, x)


def _betai(a, b, x):
    """Incomplete beta function (rough approximation via continued fraction)."""
    if x < 0 or x > 1:
        return 0
    if x == 0 or x == 1:
        return x
    if x < (a + 1) / (a + b + 2):
        return _betacf(a, b, x) * math.exp(
            math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) +
            a * math.log(x) + b * math.log(1 - x)) / a
    else:
        return 1 - _betacf(b, a, 1 - x) * math.exp(
            math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) +
            a * math.log(x) + b * math.log(1 - x)) / b


def _betacf(a, b, x):
    """Continued fraction for incomplete beta."""
    MAXIT = 200
    EPS = 3e-7
    qab = a + b
    qap = a + 1
    qam = a - 1
    c = 1
    d = max(1 - qab * x / qap, 1e-30)
    d = 1 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = max(1 + aa * d, 1e-30)
        c = max(1 + aa / c, 1e-30)
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = max(1 + aa * d, 1e-30)
        c = max(1 + aa / c, 1e-30)
        d = 1 / d
        dl = d * c
        h *= dl
        if abs(dl - 1) < EPS:
            break
    return h


# ── Regression ──

def ols_simple(xs, ys):
    """Simple OLS: y = a + b*x.  Returns (a, b, r2)."""
    n = len(xs)
    if n < 2:
        return 0, 0, 0
    mx, my = safe_mean(xs), safe_mean(ys)
    ss_xy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    ss_xx = sum((x - mx) ** 2 for x in xs)
    if ss_xx == 0:
        return my, 0, 0
    b = ss_xy / ss_xx
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    return a, b, r2


def ols_multi(X, y):
    """Multiple OLS via normal equations.  X is list of lists (each row = one obs).
    Returns (coefficients_list, r2, residuals). Intercept is prepended automatically."""
    n = len(y)
    k = len(X[0]) if X else 0
    if n <= k + 1:
        return [0] * (k + 1), 0, [0] * n
    A = [[1] + list(row) for row in X]
    AtA = [[sum(A[i][r] * A[i][c] for i in range(n)) for c in range(k + 1)] for r in range(k + 1)]
    Aty = [sum(A[i][r] * y[i] for i in range(n)) for r in range(k + 1)]
    aug = [AtA[r][:] + [Aty[r]] for r in range(k + 1)]
    for col in range(k + 1):
        max_row = max(range(col, k + 1), key=lambda r: abs(aug[r][col]))
        aug[col], aug[max_row] = aug[max_row], aug[col]
        if abs(aug[col][col]) < 1e-12:
            return [0] * (k + 1), 0, [0] * n
        for row in range(col + 1, k + 1):
            f = aug[row][col] / aug[col][col]
            for j in range(col, k + 2):
                aug[row][j] -= f * aug[col][j]
    coefs = [0] * (k + 1)
    for i in range(k, -1, -1):
        coefs[i] = aug[i][k + 1]
        for j in range(i + 1, k + 1):
            coefs[i] -= aug[i][j] * coefs[j]
        coefs[i] /= aug[i][i]
    my = safe_mean(y)
    ss_tot = sum((yi - my) ** 2 for yi in y)
    preds = [sum(coefs[j] * A[i][j] for j in range(k + 1)) for i in range(n)]
    ss_res = sum((y[i] - preds[i]) ** 2 for i in range(n))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    resid = [y[i] - preds[i] for i in range(n)]
    return coefs, r2, resid


def wls_multi(X, y, w):
    """Weighted least squares via normal equations.
    X: list of lists (each row = one obs), y: response, w: weights.
    Returns (coefficients_list, r2, residuals). Intercept prepended."""
    n = len(y)
    k = len(X[0]) if X else 0
    if n <= k + 1:
        return [0] * (k + 1), 0, [0] * n
    A = [[1] + list(row) for row in X]
    # Weighted normal equations: (A^T W A) c = (A^T W y)
    AtWA = [[sum(w[i] * A[i][r] * A[i][c] for i in range(n)) for c in range(k + 1)] for r in range(k + 1)]
    AtWy = [sum(w[i] * A[i][r] * y[i] for i in range(n)) for r in range(k + 1)]
    aug = [AtWA[r][:] + [AtWy[r]] for r in range(k + 1)]
    for col in range(k + 1):
        max_row = max(range(col, k + 1), key=lambda r: abs(aug[r][col]))
        aug[col], aug[max_row] = aug[max_row], aug[col]
        if abs(aug[col][col]) < 1e-12:
            return [0] * (k + 1), 0, [0] * n
        for row in range(col + 1, k + 1):
            f = aug[row][col] / aug[col][col]
            for j in range(col, k + 2):
                aug[row][j] -= f * aug[col][j]
    coefs = [0] * (k + 1)
    for i in range(k, -1, -1):
        coefs[i] = aug[i][k + 1]
        for j in range(i + 1, k + 1):
            coefs[i] -= aug[i][j] * coefs[j]
        coefs[i] /= aug[i][i]
    # Weighted R²
    w_sum = sum(w)
    w_mean_y = sum(w[i] * y[i] for i in range(n)) / w_sum if w_sum else 0
    preds = [sum(coefs[j] * A[i][j] for j in range(k + 1)) for i in range(n)]
    ss_tot = sum(w[i] * (y[i] - w_mean_y) ** 2 for i in range(n))
    ss_res = sum(w[i] * (y[i] - preds[i]) ** 2 for i in range(n))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    resid = [y[i] - preds[i] for i in range(n)]
    return coefs, r2, resid


# ── Clustering ──

def euclidean(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def kmeans(vecs, k=3, max_iter=100):
    """Simple k-means. vecs is dict {key: [floats]}. Returns (assignments, centroids)."""
    items = list(vecs.keys())
    n = len(items)
    dim = len(next(iter(vecs.values())))
    centroids = [list(vecs[items[i * n // k]]) for i in range(k)]
    assignments = {}
    for _ in range(max_iter):
        new_assignments = {}
        for item in items:
            dists = [euclidean(vecs[item], c) for c in centroids]
            new_assignments[item] = dists.index(min(dists))
        if new_assignments == assignments:
            break
        assignments = new_assignments
        for ci in range(k):
            members = [vecs[item] for item in items if assignments[item] == ci]
            if members:
                centroids[ci] = [sum(m[d] for m in members) / len(members) for d in range(dim)]
    return assignments, centroids


# ── Encoding ──

def one_hot(value, categories):
    """One-hot encode value against sorted categories, dropping first as reference."""
    return [1 if value == c else 0 for c in categories[1:]]


# ── JSON helpers ──

def to_json(obj):
    return json.dumps(obj)
