# 04 — The Monte Carlo Simulator

> **File:** `relink/scripts/lib/model.py` (functions: `build_per_puzzle_dists`, `_sample_wrong_guesses`, `_apply_ratio_shift`, `_compute_feature_ratios`, `_compute_position_ratios`, `predict_row_dist`, `_apply_decoy_shift`, `simulate_puzzle`)
> **Called by:** `pdl_analysis.py` as step 14
> **Output:** `simulator.json`

## What It Does

The simulator plays 10,000 games of Relink for each puzzle and counts how many end in wins. This produces a predicted solve rate that can be compared to the actual solve rate (for puzzles with player data) or used as a forecast (for puzzles without player data).

There are two modes:

| Mode | When Used | Data Source | Accuracy |
|------|-----------|-------------|----------|
| **Empirical** | 7 puzzles with player data | Per-puzzle observed distributions + pooled fallback | r = 0.993, MAE = 8.1pp |
| **Feature-only** | 41 puzzles without player data | PDL feature-based distributions only | Used for predictions |

---

## How One Simulated Game Works

```
START: 4 lives

For each row (sorted easiest-first for undated puzzles):
  ┌─────────────────────────────────┐
  │ Sample wrong_guesses from       │
  │ the row's distribution          │
  │ (0, 1, 2, or 3 wrongs)         │
  └────────────────┬────────────────┘
                   │
                   ▼
            lives -= wrong_guesses
                   │
          ┌────────┴────────┐
          │                 │
     lives > 0         lives ≤ 0
     ─── next row ──     ─── LOST ──


After solving all 4 rows:
  ┌─────────────────────────────────┐
  │ RELINK PHASE                    │
  │ Sample wrong_guesses from       │
  │ the relink distribution         │
  └────────────────┬────────────────┘
                   │
            lives -= wrong_guesses
                   │
          ┌────────┴────────┐
          │                 │
     lives > 0         lives ≤ 0
     ─── WON ──       ─── LOST ──
```

Repeat 10,000 times. Solve rate = wins / 10,000.

---

## The Distribution Selection Algorithm

The most important question is: **what distribution do we sample from for each row?** The answer depends on what data is available.

### For Dated Puzzles (Empirical Mode)

```
For each row at position pos:

Try 1: per_puzzle_obs[pos]
       ↓ (empirical distribution observed for this specific puzzle at this position)
       
Try 2: predict_row_dist(row_pdl, has_decoy, transition_probs)
       ↓ (feature-based prediction — fallback if per_puzzle_obs is missing)
       
Try 3: by_position_lives[pos, lives]
       ↓ (pooled distribution for this position and life count)
       
Try 4: Hard-coded default {0: 0.65, 1: 0.20, 2: 0.10, 3: 0.05}
```

### For Undated Puzzles (Feature-Only Mode)

```
For each row:

Step 1: predict_row_dist(row_pdl, has_decoy, transition_probs)
        ↓ (feature-based prediction — the main path)
        
Step 2: Sort all 4 rows by predicted difficulty (easiest first)
        ↓ (models player strategy of solving easy rows first)
        
Step 3: Re-apply position ratio shifts based on solve order
        ↓ (position 0 is easier than position 3 due to life pressure)
```

---

## `predict_row_dist()` — The Feature-Based Distribution Model

This is the heart of the feature-only prediction. It builds a wrong-guess distribution for a row using multiple PDL features, stacking adjustments multiplicatively.

### Step-by-step

```
┌───────────────────────────────────────────────────────────┐
│ Step 1: BASE DISTRIBUTION                                 │
│                                                           │
│ Look up (manipulation, has_decoy) in by_feature_combo     │
│                                                           │
│   e.g. "Hidden word|True" → {0: 0.42, 1: 0.28, 2: 0.19} │
│                                                           │
│ Fallback chain if not found:                              │
│   → manipulation only (from by_pdl_feature)               │
│     + decoy shift if applicable                           │
│   → global baseline                                       │
│     + decoy shift if applicable                           │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────┐
│ Step 2: RATIO-SHIFT ADJUSTMENTS                           │
│                                                           │
│ For each feature, compute how much harder/easier the      │
│ row's category is vs the global average. Apply that       │
│ ratio as an exponential reweighting.                      │
│                                                           │
│ Features applied in order:                                │
│   1. Abstraction (e.g. Shared property = 1.3× harder)    │
│   2. Knowledge (e.g. Specialist cultural = 1.4× harder)  │
│   3. Same domain (e.g. True = 1.2× harder)               │
│   4. Position (e.g. position 3 = 1.15× harder)           │
└───────────────────────────────────────────────────────────┘
```

### The Ratio-Shift Mechanism (`_apply_ratio_shift`)

This is how adjustments work without replacing the base distribution:

```
For a distribution {0: 0.65, 1: 0.20, 2: 0.10, 3: 0.05}
with ratio = 1.3 (harder):

  P(0) = 0.65 × 1.3⁰ = 0.65 × 1.000 = 0.650
  P(1) = 0.20 × 1.3¹ = 0.20 × 1.300 = 0.260
  P(2) = 0.10 × 1.3² = 0.10 × 1.690 = 0.169
  P(3) = 0.05 × 1.3³ = 0.05 × 2.197 = 0.110

  Renormalise (total = 1.189):
  P(0) = 0.547, P(1) = 0.219, P(2) = 0.142, P(3) = 0.092
```

Higher wrong counts get amplified exponentially, shifting the distribution toward more errors. Ratio < 1.0 does the opposite — shifts toward fewer errors.

**Clamping:** Ratios are clamped to [0.5, 2.0] to prevent extreme adjustments when sample sizes are small. Ratios within 2% of 1.0 are ignored (no meaningful adjustment).

### How Feature Ratios Are Computed (`_compute_feature_ratios`)

For each feature axis (abstraction, knowledge, same_domain):

```
global_mean_wrong = weighted mean across ALL observations (e.g. 0.42)

For each category in the axis:
  category_mean_wrong = weighted mean for observations in this category
  ratio = category_mean_wrong / global_mean_wrong
```

Example:
```
global_mean_wrong = 0.42

abstraction:
  Direct membership:  mean_wrong = 0.35  → ratio = 0.83 (easier)
  Shared property:    mean_wrong = 0.58  → ratio = 1.38 (harder)
  Conceptual link:    mean_wrong = 0.49  → ratio = 1.17 (slightly harder)
```

### How Position Ratios Are Computed (`_compute_position_ratios`)

Aggregates across all life states for each position:

```
Position 0: mean_wrong = 0.36  → ratio = 0.86
Position 1: mean_wrong = 0.41  → ratio = 0.98
Position 2: mean_wrong = 0.48  → ratio = 1.14
Position 3: mean_wrong = 0.55  → ratio = 1.31
```

This captures the empirical observation that later positions are harder (fewer lives, more pressure, harder rows left).

### Stacking

All adjustments are applied multiplicatively. For a row that is:
- "Hidden word" manipulation (captured in base distribution)
- "Shared property" abstraction (ratio = 1.38)
- "General vocabulary" knowledge (ratio = 0.95)
- Same domain impostor (ratio = 1.20)
- Position 2 (ratio = 1.14)

The base distribution gets shifted by 1.38, then by 0.95, then by 1.20, then by 1.14. The total effective shift ≈ 1.38 × 0.95 × 1.20 × 1.14 ≈ 1.80×, making this row substantially harder than the base.

---

## The Decoy Shift (`_apply_decoy_shift`)

A special case of ratio-shifting used when the base distribution doesn't include decoy information:

```
no_decoy_mean = 0.38
yes_decoy_mean = 0.56
ratio = 0.56 / 0.38 = 1.47

Apply _apply_ratio_shift(dist, 1.47) → shifts distribution harder
```

This is only used as a fallback when the (manipulation, has_decoy) combo lookup fails and we fall back to manipulation-only data.

---

## Building Per-Puzzle Empirical Distributions (`build_per_puzzle_dists`)

For dated puzzles, we don't need the feature model — we have real data.

```
For each player in the puzzle:
  Replay their guess sequence chronologically:
    - Between two consecutive solves, count total wrong guesses
      (including wrongs on abandoned rows from row-switching)
    - Record: [position] → wrong_count

  If player died:
    - Record their remaining wrongs as a partial observation

  For relink phase:
    - Record wrong_count from relink_trajectory

Result: 5 distributions (positions 0-3 + relink)
  Each: {wrong_count: probability}
  Minimum 5 observations per position to use
```

**Important nuance:** This counts lives consumed between solves, not per-row wrongs. If a player guesses wrong on row 2, switches to row 1 to solve it, those wrongs count against position 0 (the first solve). This matches what the simulator needs — it doesn't model row-switching, just total wrongs per solve.

**Note:** Although these input distributions use plain integer keys (`{0: 0.65, 1: 0.20, ...}`), the simulator's *output* uses compound keys that split by outcome (`0_solved`, `1_lost`, etc.) — see the Output Structure section below.

---

## Relink Phase Prediction

The relink phase has its own distribution selection:

### For Dated Puzzles
```
Try 1: per_puzzle_obs[4]  (empirical relink distribution)
Try 2: Feature-based prediction (see below)
Try 3: Pooled by_position_lives[4, current_lives]
Try 4: Scan lives 4→1 for any relink data
Try 5: Hard-coded {0: 0.85, 1: 0.10, 2: 0.05}
```

### Feature-Based Relink Prediction
Uses the same ratio-shift approach but with relink-specific features:

```
Base: by_con_manip[construction_manipulation]
  e.g. "Word split" → {0: 0.70, 1: 0.20, 2: 0.10}

Ratio adjustments:
  1. id_manipulation ratio  (mean_wrong of id category / global relink mean)
  2. con_knowledge ratio    (mean_wrong of knowledge category / global relink mean)
  3. phase2TileCount ratio  (mean_wrong of tile count / global relink mean)
```

The `relink_feature_dists` structure is built in `pdl_analysis.py` by pooling relink outcomes across all dated puzzles, grouped by 4 axes:

```python
relink_feature_dists = {
    'global': {'mean_wrong': 0.28, 'n': 380},
    'by_con_manip': {
        'None': {'dist': {0: 0.80, 1: 0.15, 2: 0.05}, 'mean_wrong': 0.25},
        'Word split': {'dist': {0: 0.65, 1: 0.25, 2: 0.10}, 'mean_wrong': 0.45},
        ...
    },
    'by_id_manip': { ... },
    'by_con_knowledge': { ... },
    'by_tiles': { ... },
}
```

---

## Row Ordering for Undated Puzzles

Players tend to solve easier rows first (because easy rows are recognisable as easy). The simulator models this:

1. Compute `predict_row_dist()` for each row **without** position adjustment
2. Calculate expected wrong guesses: Σ(k × P(k)) for each row
3. Sort rows by expected wrongs (ascending = easiest first)
4. Re-apply position ratio shifts based on the new solve order

This means the easiest row gets the position-0 ratio (slightly easier) and the hardest row gets the position-3 ratio (slightly harder), widening the gap.

---

## Random Number Generator

The simulator uses a deterministic Linear Congruential Generator (LCG) with seed=42:

```python
rng_state[0] = (rng_state[0] * 1103515245 + 12345) & 0x7fffffff
r = (rng_state[0] >> 16) / 32768.0  # uniform [0, 1)
```

This ensures reproducible results — running the simulator twice with the same input always produces the same output. The RNG state is shared across all 10,000 simulations for a puzzle, giving a different sequence of random draws for each simulated player.

### Sampling from a Distribution

```python
Given dist = {0: 0.65, 1: 0.20, 2: 0.10, 3: 0.05}
and a random draw r = 0.73:

  cumulative = 0.65 → r > 0.65, continue
  cumulative = 0.85 → r ≤ 0.85 → sample 1 wrong guess
```

---

## Simulator Validation

### Empirical Mode (dated puzzles)
Each of the 7 dated puzzles is simulated using its own observed distributions, with the feature model as fallback. Comparing simulated vs actual solve rate:
- **Pearson r = 0.993** — near-perfect correlation
- **MAE = 8.1 percentage points** — average prediction error

### Feature-Only Mode (cross-validation on dated puzzles)
Each dated puzzle is simulated using ONLY the feature model (no per-puzzle observations). This tests how well the model generalises.

### Improvement History
| Version | Feature-Only r | Feature-Only MAE |
|---------|---------------|-----------------|
| Manipulation + decoy only | 0.493 | 19.1pp |
| + abstraction, knowledge, same_domain, position | 0.655 | 15.1pp |

---

## Output Structure (`simulator.json`)

```json
{
  "puzzles": {
    "2026-05-07": {
      "solve_rate": 0.5180,
      "actual_solve_rate": 51.8,
      "name": "Newspaper sections",
      "date": "2026-05-07",
      "won": 7892,
      "lost": 2108,
      "relink_reached": 8450,
      "rows_completed_pct": [0.5, 2.1, 5.8, 6.6, 85.0],
      "mean_lives_at_win": 2.34,
      "sim_row_dists": {
        "0": {"0_solved": 7200, "1_solved": 1800, "1_lost": 50, "2_solved": 600, ...},
        "1": {"0_solved": 6800, "1_solved": 2000, ...},
        "2": {"0_solved": 6500, ...},
        "3": {"0_solved": 6000, "no_attempt_lost": 400, ...},
        "4": {"0_solved": 5500, "1_solved": 1200, "1_lost": 300, "4_lost": 50, ...}
      },
      "manipulationComplexity": 1,
      "abstractionComplexity": 0,
      "phase2TileCount": 2,
      "cluster": 0
    },
    ...
  },
  "undated": {
    "l1": { ... same structure but actual_solve_rate: null ... },
    ...
  },
  "validation": { "r": 0.993, "mae": 8.1 },
  "feature_validation": { "r": 0.655, "mae": 15.1 }
}
```

### Compound Wrong-Distribution Keys

The `sim_row_dists` field uses **compound keys** that encode both the number of wrong guesses and the outcome for that row:

| Key Format | Meaning |
|------------|---------|
| `0_solved` | Row solved with 0 wrong guesses |
| `1_solved` | Row solved with 1 wrong guess |
| `1_lost` | Player died on this row after 1 wrong guess |
| `2_solved`, `2_lost` | 2 wrongs, solved or lost |
| `3_solved`, `3_lost` | 3 wrongs, solved or lost |
| `4_lost` | Player lost on relink phase after 4 wrong guesses (arrived with all 4 lives) |
| `no_attempt_lost` | Player never reached this row (died earlier) |

**Key details:**
- Positions 0–3 are impostor rows (max 3 wrongs per row). Wrongs are counted between consecutive solves, not per-row.
- Position 4 is the relink phase (max 4 wrongs — a player can arrive with all 4 lives and lose them all).
- Values are raw simulation counts (out of 10,000).
- This format matches the actual player data compound keys produced by `lib/metrics.py`, enabling direct visual comparison in the dashboard's Puzzle Explorer.

---

## Summary: The Full Prediction Pipeline

```
PDL puzzle design
       │
       ├── Row PDL features ──────────────────────┐
       │                                          │
       ├── Relink PDL features ──────────────┐    │
       │                                     │    │
       ▼                                     ▼    ▼
┌─────────────┐  ┌───────────────┐  ┌─────────────────────┐
│ Row ordering│  │ Relink dist   │  │ Per-row distribution │
│ (easiest    │  │ (con_manip    │  │ (manip+decoy base    │
│  first)     │  │  base + 3     │  │  + 4 ratio shifts)   │
│             │  │  ratio shifts)│  │                      │
└──────┬──────┘  └──────┬────────┘  └──────────┬───────────┘
       │                │                       │
       └────────────────┼───────────────────────┘
                        │
                        ▼
               Monte Carlo: 10,000 games
                        │
                        ▼
               Predicted solve rate
```
