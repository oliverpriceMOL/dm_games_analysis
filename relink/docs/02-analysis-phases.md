# 02 — Analysis Phases

> **File:** `relink/scripts/lib/metrics.py`
> **Called by:** `pdl_analysis.py` as steps 1–9
> **Output:** 8 JSON data files consumed by the dashboard

## What Happens

After data loading produces joined structures (PDL features + player behaviour), the pipeline runs 8 independent analyses. Each takes a slice of the joined data and produces a JSON file that answers a specific question about puzzle difficulty.

```
                        Joined Data
                            │
            ┌───────────────┼───────────────┐
            │               │               │
    ┌───────┴────┐  ┌───────┴───────┐  ┌────┴────────┐
    │ row_joined │  │ puzzle_data   │  │ players_by  │
    │ ~56 rows   │  │ 14 puzzles    │  │ _date       │
    │ (row PDL   │  │ (puzzle PDL   │  │ (raw player │
    │ + row      │  │ + puzzle-     │  │ trajectories│
    │ behaviour) │  │  level stats) │  │ per date)   │
    └───┬────────┘  └──┬────────────┘  └────┬────────┘
        │              │                    │
        ▼              ▼                    ▼
  ┌──────────┐   ┌───────────┐    ┌──────────────┐
  │Crosstabs │   │Correlation│    │   Vertical   │
  │Heatmap   │   │Regression │    │  Inference   │
  │Imp Domain│   │           │    │   Decoys     │
  │Relink    │   │           │    │              │
  │Clustering│   │           │    │              │
  └──────────┘   └───────────┘    └──────────────┘
        │              │                    │
        ▼              ▼                    ▼
  5 JSON files    2 JSON files        2 JSON files
```

---

## Analysis 1: Cross-Tabs (`crosstabs.json`)

**Question:** How does each PDL tag relate to row difficulty?

**Method:** Groups the ~56 row observations by each of 4 PDL axes — manipulation, abstraction, knowledge, knowledge domain — and computes mean first-try %, mean wrong guesses, and mean "never correct" % for each category.

**Example result:**
```
Manipulation:
  None           → 82% first-try (n=36 rows)
  Hidden word    → 64% first-try (n=8 rows)
  Compound       → 71% first-try (n=12 rows)
```

This tells you that rows with no word manipulation are easiest (82% of players get them first try), while hidden words are the hardest manipulation type.

**How it works:**
1. For each PDL axis, group rows by category label
2. For each group, compute `mean(first_try_pct)`, `mean(avg_wrong)`, `mean(never_correct_pct)`
3. Format as bar chart data: labels, values, sample sizes

**JSON structure:**
```json
{
  "Manipulation": {
    "labels": ["Compound", "Hidden word", "None"],
    "first_try": [71.2, 63.8, 81.5],
    "avg_wrong": [0.34, 0.52, 0.21],
    "n": [12, 8, 36]
  },
  "Abstraction": { ... },
  "Knowledge": { ... },
  "Knowledge Domain": { ... }
}
```

---

## Analysis 2: Heatmap (`heatmap.json`)

**Question:** Do manipulation and abstraction interact — is a row with BOTH manipulation AND abstract connections harder than either alone would predict?

**Method:** Creates a 2D grid of manipulation × abstraction categories. Each cell shows the mean first-try % for rows with that specific combination.

**How it works:**
1. Group rows by (manipulation, abstraction) pairs
2. For each cell that has data, compute mean first-try %
3. Format as a matrix with row/column labels

**Example:** A row that is "Hidden word" manipulation AND "Shared property" abstraction might have 45% first-try, even though "Hidden word" alone averages 64% and "Shared property" alone averages 70%. This would reveal a multiplicative (not additive) difficulty interaction.

---

## Analysis 3: Impostor Domain (`impostor-domain.json`)

**Question:** Is it harder to find the impostor when it comes from the same knowledge domain as the legitimate tiles?

**Hypothesis:** An impostor tile from the same domain (e.g., a wrong "newspaper section" in a row about newspaper sections) should be harder to spot than one from a completely different domain.

**Method:** Splits rows into two groups: same-domain impostors vs different-domain impostors. Compares mean first-try % and mean wrong guesses.

**Typical finding:** Same-domain impostors have lower first-try rates — they're better disguised.

---

## Analysis 4: Correlations (`correlations.json`)

**Question:** Which board-level features predict overall puzzle solve rate?

**Method:** For each of 6 computed puzzle features, calculates both Pearson (linear) and Spearman (rank) correlation with solve rate across the 14 dated puzzles.

**The 6 features tested:**

| Feature | What It Counts |
|---------|----------------|
| `manipulationComplexity` | Rows with manipulation ≠ 'None' |
| `abstractionComplexity` | Rows with abstraction ≠ 'Direct membership' |
| `knowledgeBreadth` | Distinct knowledge domains across rows |
| `phase2TileCount` | Tiles needed for the relink answer |
| `decoyCount` | Number of designed decoy groupings |
| `specialistGroupCount` | Rows requiring specialist cultural knowledge |

**How it works:**
1. Extract feature values for all 14 dated puzzles
2. Extract corresponding solve rates
3. Compute Pearson r (assumes linear relationship) and Spearman ρ (rank-based, handles non-linear)
4. Package as scatter plot data: x-values, y-values, labels, correlation coefficients

---

## Analysis 5: Regression (`regression.json`)

**Question:** Can we build a formula that predicts solve rate from multiple features simultaneously?

**Method:** Ordinary Least Squares (OLS) regression — finds the best-fit linear combination of features, with leave-one-out cross-validation.

**Three models are fitted:**

### Puzzle-Level Model
```
solve_rate = β₀ + β₁·manipulationComplexity + β₂·abstractionComplexity
           + β₃·phase2TileCount + β₄·playerCount
```
- 14 observations (one per dated puzzle)
- Player count included as a covariate (controls for growing player base)
- Reports R², coefficients, and LOO MAE

### Row-Level Model
```
first_try_pct = β₀ + Σ(manipulation one-hot) + Σ(abstraction one-hot)
              + Σ(knowledge one-hot) + β·same_domain
```
- ~56 observations (one per row)
- Uses one-hot encoding for categorical PDL tags (drops first category as baseline)

### Position-Controlled Row Model
Same as row-level but adds `mean_attempt_position` — the average solve-order position that row was attempted at — to control for the fact that later-attempted rows are harder because players have fewer lives.

**LOO Cross-Validation:** For each puzzle, trains on the other 13 and predicts the held-out one. MAE across all 14 folds gives an unbiased error estimate.

---

## Analysis 6: Vertical Inference (`vertical.json`)

**Question:** Do players get better as they progress through a puzzle? And does this learning rate differ across puzzle types?

**Terminology:** "Vertical" because it looks at improvement *within* a single game session, down the solve sequence (positions 0→3).

**What it measures:**

Two curves per puzzle:
1. **Error curve:** Mean wrong guesses at each solve position (0, 1, 2, 3)
2. **Timing curve:** Median seconds between consecutive solves at each position

**How it works:**
1. For each player, reconstruct their solve order (which row they solved 1st, 2nd, 3rd, 4th)
2. Count wrong guesses at each position in the solve sequence
3. Measure timing gaps between consecutive solves
4. Aggregate across all players for that puzzle
5. Compute a "transparency" score — a weighted centroid that summarises whether errors are front-loaded (good: player improves) or back-loaded (bad: puzzle gets confusing)

**Transparency score:** Sum(position × mean_wrong) / Sum(mean_wrong). Low = errors mostly at position 0 (early), meaning players learn quickly. High = errors still happening at positions 2-3.

**Per-feature breakdown:** Groups puzzles by each PDL axis (manipulation complexity, abstraction complexity, etc.) and averages the error and timing curves. This shows whether, say, high-manipulation puzzles have steeper or flatter learning curves.

**Aggregate finding:** Across all 14 puzzles, mean wrong guesses increase from ~0.45 at position 0 to ~0.65 at position 3. This is counterintuitive — players get *worse* as they solve more rows. The reason: later positions have fewer lives, so there's more pressure, and the easiest rows tend to be solved first.

---

## Analysis 7: Decoys (`decoys.json`)

**Question:** Do designed decoy groupings actually trick players? And how much harder do they make puzzles?

**Background:** Puzzle designers can add "decoy groupings" — tiles that look like they form a valid group but don't. These are meant to mislead players into wrong guesses.

**Two sub-analyses:**

### Comparison: Decoy vs No-Decoy Puzzles
Splits the 14 dated puzzles into those with decoys and those without. Compares mean solve rate and mean wrong guesses.

### Hit-Rate Analysis
For puzzles with decoys, traces individual wrong guesses to see if the wrongly-selected tile was in a decoy grouping. The "hit rate" = what fraction of wrong guesses fell on decoy tiles.

**How the hit rate works:**
1. From the puzzle design, identify which tiles are in decoy groupings
2. From player events, identify which tiles players wrongly selected as impostors
3. Count how many wrong selections targeted decoy tiles
4. Hit rate = decoy-targeted wrongs / total wrongs

A high hit rate means the decoy is effective — it's drawing players toward the wrong answer.

---

## Analysis 8: Relink Phase (`relink.json`)

**Question:** What makes the relink phase (phase 2) harder or easier?

**Background:** After finding all 4 impostors, players enter the relink phase: the 4 impostors share a hidden connection, and players must spell it out using tiles from the grid.

**Method:** Groups puzzles by three relink features and compares first-try rates and mean attempts:

1. **By identification manipulation** — how the connection between impostors is encoded (e.g., hidden word, compound)
2. **By construction manipulation** — how tiles combine to form the answer (e.g., word split, phrase)
3. **By tile count** — how many tiles are needed to spell the answer (1, 2, 3, or 4)

---

## Analysis 9: Clustering (`clustering.json`)

**Question:** Can we group puzzles (and individual rows) into natural archetypes based on their design features?

**Method:** k-means clustering applied at two levels.

### Puzzle Clustering (k=3)
Creates a feature vector per puzzle: counts of each PDL category across its 4 rows, plus numeric features (tile count, decoy count, specialist count). Runs k-means with k=3 to find 3 puzzle archetypes.

**Auto-naming logic:** Each cluster is named based on its centroid:
- If many non-None manipulation categories → "Complex Manipulation"
- If many non-Direct abstraction categories → "Abstract Reasoning"
- Otherwise → "Straightforward"
- If specialist count > 0.5 → appends "+ Specialist"

### Row Clustering (k=4)
Creates a one-hot feature vector per row (manipulation, abstraction, knowledge, same_domain). Runs k-means with k=4 to find 4 row archetypes. Each cluster is labelled by its dominant manipulation / abstraction combination.

**Why this matters:** Clustering reveals natural puzzle families. If all the hardest puzzles land in one cluster, that tells you which combination of design features produces difficulty.

---

## Analysis 10: Overview (`overview.json`)

**Question:** What are the headline numbers?

A lightweight summary providing:
- Total puzzle and completion counts
- Per-date table: date, name, player count, wins, losses, solve rate, median time
- Aggregate timing by solve position

This data populates the dashboard's "Key Findings" section.

---

## How Analyses Feed Together

The 8 analyses are mostly independent — they each take a slice of the joined data and produce their own JSON file. But there are two connections:

1. **Clustering → Simulator:** The cluster assignment for each puzzle is included in the simulator results, so the dashboard can colour-code predicted solve rates by archetype.

2. **Regression → Cross-validation:** The regression coefficients aren't used by the simulator. They're a separate linear model for comparison; the simulator uses a non-parametric approach (transition probabilities) instead.

The analyses in `metrics.py` are purely descriptive — they measure what happened. The statistical modelling in `model.py` (next document) is predictive — it builds a model that can simulate what *would* happen for unseen puzzles.
