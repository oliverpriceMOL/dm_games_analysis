# 03 — Statistical Modelling

> **File:** `relink/scripts/lib/model.py` (first three functions)
> **Called by:** `pdl_analysis.py` as steps 11–13
> **Output:** `transitions.json`, `failures.json`

## What This Layer Does

The analysis phases in `metrics.py` (document 02) are *descriptive* — they measure what happened. The statistical modelling in `model.py` is *predictive* — it builds probabilistic models from the observed data that can be used to simulate outcomes for puzzles that haven't been played yet.

The modelling layer has three components:

```
┌──────────────────────────────────────────────────────────────────┐
│                    STATISTICAL MODELLING                        │
│                                                                  │
│  ┌────────────────┐   ┌──────────────────┐   ┌──────────────┐  │
│  │  IPW Weights   │──▶│  Transition      │   │  Correlated  │  │
│  │  (survivorship │   │  Probabilities   │   │  Failures    │  │
│  │   correction)  │   │  (difficulty     │   │  (row pairs) │  │
│  └────────────────┘   │   model)         │   └──────────────┘  │
│                       └──────────────────┘                      │
│                              │                                   │
│                              ▼                                   │
│                       Used by simulator                          │
│                       (document 04)                              │
└──────────────────────────────────────────────────────────────────┘
```

---

## Component 1: Inverse Probability Weighting (IPW)

### The Problem: Survivorship Bias

In Relink, players who lose all 4 lives are eliminated. This means later positions in the game (positions 2, 3, and especially the relink phase) are only observed for players who survived the earlier positions. These survivors are a *biased sample* — they're better-than-average players, because the worse players already died.

If we naively count error rates at position 3, we'd underestimate the true difficulty because we're only seeing the survivors' performance.

```
Position 0: All ~9,000 players attempt this  → unbiased
Position 1: ~8,300 players survived to here  → slightly biased
Position 2: ~7,200 players survived          → moderately biased
Position 3: ~6,100 players survived          → heavily biased
Relink:     ~5,200 players survived          → most biased
```

### The Solution: IPW

Inverse Probability Weighting corrects this by giving more weight to observations at later positions. The idea: if only 60% of players survive to position 2, then each observation at position 2 should count as 1/0.6 ≈ 1.67 observations, because each surviving player "represents" the ~40% who didn't make it.

### How It Works

```
For each (position, lives_before) state:
  1. Count how many players were in this state
  2. Count how many survived to the next state
  3. Survival rate = survived / total

For each player's trajectory:
  1. Start with cumulative probability = 1.0
  2. At each step, weight = 1 / cumulative_probability
  3. Update: cumulative *= survival_rate_at_this_state
```

**Example:**

| Position | Lives | Survival Rate | Cumulative P | Weight |
|----------|-------|---------------|-------------|--------|
| 0 | 4 | 0.92 | 1.00 | 1.00 |
| 1 | 3 | 0.85 | 0.92 | 1.09 |
| 2 | 3 | 0.88 | 0.78 | 1.28 |
| 3 | 2 | 0.75 | 0.69 | 1.45 |

**Safety cap:** Weights are capped at 20× to prevent extreme observations (players who barely survived through many unlikely states) from dominating the estimates.

**Pooling:** IPW is computed by pooling trajectories across all 7 dated puzzles (~65K total). This gives stable survival estimates even for rare states (e.g., position 3 with 1 life).

### Output

```python
ipw_data = {
    'survival_table': {
        '0,4': {'count': 64892, 'survived': 59718, 'rate': 0.920},
        '1,4': {'count': 41230, 'survived': 38102, 'rate': 0.924},
        '1,3': {'count': 18488, 'survived': 15140, 'rate': 0.819},
        ...
    },
    'player_weights': {
        ('2026-05-07', 'device_abc'): [
            {'position': 0, 'lives_before': 4, 'weight': 1.0},
            {'position': 1, 'lives_before': 3, 'weight': 1.09},
            ...
        ],
        ...
    },
    'diagnostics': {
        'n_trajectories': 71712,
        'mean_weight': 1.193,
        'p95_weight': 1.963,
        'n_capped': 0,
    }
}
```

---

## Component 2: Transition Probabilities

### What These Are

The transition model estimates: "For a row with these PDL features, what's the probability of getting 0, 1, 2, or 3 wrong guesses before finding the impostor?"

These distributions are the core input to the Monte Carlo simulator (document 04).

### How It's Built

```
For every row attempt in every player's trajectory:
  1. Look up the row's PDL features (manipulation, abstraction, knowledge, same_domain)
  2. Look up whether the row contains decoy tiles
  3. Record the observation: (wrong_count, IPW_weight, features)

Then aggregate into tables at multiple granularities.
```

### The Tables

**1. `by_position_lives`** — Empirical wrong-guess distributions for each (position, lives) state:
```
Position 0, Lives 4:  {0: 0.65, 1: 0.20, 2: 0.10, 3: 0.05}  (n=64892)
Position 1, Lives 3:  {0: 0.58, 1: 0.24, 2: 0.12, 3: 0.06}  (n=18488)
Position 2, Lives 2:  {0: 0.52, 1: 0.28, 2: 0.15, 3: 0.05}  (n=8920)
...
```
Each distribution is IPW-weighted (using the weights from Component 1).

**2. `by_pdl_feature`** — Wrong-guess distributions grouped by each PDL axis:
```
manipulation:
  None:          {0: 0.72, 1: 0.18, 2: 0.07, 3: 0.03}  (n=38K)
  Hidden word:   {0: 0.48, 1: 0.28, 2: 0.16, 3: 0.08}  (n=9.5K)
  Compound:      {0: 0.61, 1: 0.22, 2: 0.12, 3: 0.05}  (n=12K)

abstraction:
  Direct membership: {0: 0.70, 1: 0.19, 2: 0.08, 3: 0.03}
  Shared property:   {0: 0.55, 1: 0.26, 2: 0.13, 3: 0.06}

knowledge:
  General vocabulary: {0: 0.68, 1: 0.20, 2: 0.08, 3: 0.04}
  Common cultural:    {0: 0.60, 1: 0.23, 2: 0.11, 3: 0.06}

same_domain:
  True:  {0: 0.58, 1: 0.24, 2: 0.12, 3: 0.06}
  False: {0: 0.72, 1: 0.17, 2: 0.08, 3: 0.03}
```

**3. `by_feature_combo`** — Distributions for (manipulation, has_decoy) combinations:
```
None|False:        {0: 0.74, ...}  (n=28K)  ← easiest
Hidden word|True:  {0: 0.42, ...}  (n=3.5K) ← hardest
```
This table powers the simulator's *base distribution* for each row.

**4. `by_decoy`** — Aggregate decoy effect:
```
False (no decoy): mean_wrong=0.38
True (has decoy): mean_wrong=0.56
Ratio: 0.56/0.38 = 1.47 (decoy rows are ~47% harder)
```

**5. `global_baseline`** — Overall distribution pooled across everything. Used as a denominator for ratio calculations and as a last-resort fallback.

**6. `intrinsic_difficulty`** — Position-0, lives-4 only (removes confounds from later positions). Shows "clean" difficulty by PDL feature.

---

## Component 3: Correlated Failures

### What This Measures

Do certain pairs of rows tend to trip up the same players? If rows A and B both use "Hidden word" manipulation, a player who fails row A might also fail row B — the failures are *correlated*.

### Why It Matters

The simulator needs to decide: are a puzzle's 4 rows independent coin-flips, or is there positive correlation between failures? If failures correlate, the puzzle is harder than independent rows would suggest (a player who gets one wrong is likely to get others wrong too).

### How It Works

**Phi coefficient** — a measure of association between two binary variables (like a correlation coefficient for 0/1 data).

For each puzzle:
1. Build a binary failure matrix: one row per player, one column per grid row
2. Mark 1 = player had ≥1 wrong guess on that row, 0 = got it first try
3. For each of the 6 row pairs (0-1, 0-2, 0-3, 1-2, 1-3, 2-3), compute the phi coefficient from the 2×2 contingency table:

```
             Row B
           Fail  Pass
Row A  Fail  a     b
       Pass  c     d

phi = (ad - bc) / sqrt((a+b)(c+d)(a+c)(b+d))
```

- phi > 0: failures correlate (players who fail one tend to fail the other)
- phi ≈ 0: failures are independent
- phi < 0: failures anti-correlate (failing one makes passing the other more likely)

### Aggregation

To understand *why* rows might correlate, the phi values are grouped by PDL similarity:
- **Same manipulation:** Do row pairs that share a manipulation type correlate more?
- **Same abstraction:** Do row pairs that share an abstraction type correlate more?
- **Same domain:** Do row pairs from the same knowledge domain correlate more?

**Typical finding:** Row pairs that share the same manipulation type have higher mean phi (more correlated failures), suggesting that manipulation-specific skills drive player failures.

### Output

```python
failure_data = {
    'per_puzzle': {
        '2026-05-07': {
            'name': 'Newspaper sections',
            'phi_matrix': {'0-1': 0.15, '0-2': 0.08, ...},
            'n_players': 5884,
            'row_failure_rates': {'0': 0.088, '1': 0.242, ...},
            'row_categories': {'0': 'Newspaper sections', ...},
        },
        ...
    },
    'aggregate': {
        'same_manipulation': {
            'same': {'mean_phi': 0.18, 'n': 22},
            'different': {'mean_phi': 0.09, 'n': 62},
        },
        'same_abstraction': { ... },
        'same_domain': { ... },
    },
    'n_pairs': 42,  # 7 puzzles × 6 pairs
}
```

---

## How These Feed Into The Simulator

```
IPW weights ──────────────▶ Transition probabilities
                                    │
                                    ├── by_feature_combo (base distributions)
                                    ├── by_pdl_feature (ratio-shift adjustments)
                                    ├── by_position_lives (position adjustments)
                                    ├── by_decoy (decoy shift ratio)
                                    └── global_baseline (reference point)
                                    │
                                    ▼
                            Monte Carlo Simulator
                            (document 04)
```

The correlated failures data is currently informational only — it's displayed in the dashboard but not directly used by the simulator (which assumes row-independence within each simulation run, letting the feature-based distributions implicitly capture some correlation).

---

## Pure Statistics Utilities (`lib/stats.py`)

All statistical functions are in `stats.py` — a pure-math module with no I/O or side effects. Everything is implemented from scratch (no numpy/scipy/pandas).

| Function | What It Does |
|----------|-------------|
| `safe_mean(vals)` | Arithmetic mean, returns 0 for empty list |
| `safe_median(vals)` | Median via sort, returns 0 for empty list |
| `safe_stdev(vals)` | Sample standard deviation, returns 0 if n < 2 |
| `percentile(vals, p)` | Linear interpolation percentile (p in 0-100) |
| `pct_str(num, den)` | Format "28/34 (82%)" strings |
| `pearson(xs, ys)` | Pearson r + two-tailed p-value (using Student's t) |
| `spearman(xs, ys)` | Spearman ρ + p-value (via rank transform) |
| `ols_simple(xs, ys)` | Simple linear regression (y = a + bx) |
| `ols_multi(X, y)` | Multiple OLS via normal equations (Gaussian elimination) |
| `wls_multi(X, y, w)` | Weighted least squares |
| `one_hot(value, categories)` | Encode a categorical value (drops first category) |
| `kmeans(items, k)` | k-means clustering (random restarts, max 100 iterations) |

The p-value computation uses the incomplete beta function via continued fraction expansion — a textbook (if complex) algorithm that avoids any dependency on scipy.
