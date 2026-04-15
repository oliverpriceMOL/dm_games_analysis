# Relink — Analysis

## The Game

Relink is a word puzzle played on a 4×4 grid with two phases.

### Phase 1 — Imposters

The grid has 4 colour-coded rows of 4 tiles each. Three tiles in each row share a hidden connection; the fourth is an **impostor** (doesn't belong). Players start with **4 lives**.

- **Each turn:** select one tile from any row, then submit.
- **Correct** (tile is the impostor): the row resolves — the impostor is removed, the connection is revealed. No life lost.
- **Wrong** (tile is not the impostor): lose a life. The selected tile is eliminated (can't pick it again). Player can retry the same row or switch to a different one.
- Players can freely switch between rows at any time — they don't have to solve one row before trying another.
- Max 3 wrong guesses per row (4 tiles, 1 impostor — after 3 wrongs the impostor is the only tile left).
- Phase ends when all 4 impostors found (proceed to Phase 2) or all lives lost (game over).

### Phase 2 — Relink

The 4 impostors share a hidden **meta-connection**. Players select tiles from the resolved grid to spell it out (1–4 slots to fill).

- Each guess = select a set of tiles to fill the remaining slots.
- Wrong guess → told "X of Y correct" + lose a life.
- Game ends when the link is correctly spelled or lives run out.

### Key Game Dynamics

- **Row-switching:** Players often start with the easiest-looking row, switch away after a wrong guess, and return later with more context. This means wrong guesses for a row can be spread across multiple visits.
- **Vertical inference:** As rows resolve, their revealed connections give clues about remaining rows. Later rows are often easier not because they're intrinsically simpler, but because players have accumulated context.
- **Life economy:** Lives are shared across all rows and both phases. A player who uses 3 lives in imposters has only 1 for the relink phase.

## Data

- **Period**: Mar 25 – Apr 13, 2026 (20 puzzle dates)
- **Player counts**: Grew from ~40/day early on to ~100/day by Apr 10
- **Total completions**: ~496
- **Puzzle design files**: 39 puzzles in `save-data/` (PDL JSON format), 20 with matching player data ("dated"), 19 design-only ("undated")

### Filters Applied

| Filter | Rule | Purpose |
|--------|------|---------|
| Bot | `(country in NL/IE and duration ≤ 10s) or duration ≤ 2s` | Remove automated traffic |
| Dev | Sessions from Västerås, SE | Remove developer sessions |
| Tutorial | `attempts_remaining > 4` | Tutorial events have 999 lives |
| Tester | `INCOMPLETE outcome with 0 wrong guesses` | Remove passive testers |

### Event Types

| Event | Phase | Key Properties |
|-------|-------|---------------|
| `relink_guess_submitted` | Imposters | `row_index`, `selected_word`, `is_correct`, `attempts_remaining`, `phase: 'imposters'` |
| `relink_guess_submitted` | Relink | `selected_tile_ids`, `is_correct`, `phase: 'relink'` |
| `level_completed` | End | `is_won`, `puzzle_date` |

## Puzzle Design Language (PDL)

Each puzzle has structured design metadata in `save-data/`:

### Row-Level Tags

| Tag | Values | Meaning |
|-----|--------|---------|
| `manipulation` | None, Compound, Hidden word, Homophone, Word split, Abbreviation | How the connection is encoded |
| `abstraction` | Direct membership, Shared property, Conceptual association | How abstract the grouping is |
| `knowledge` | General vocabulary, General cultural, Specialist cultural | Knowledge required |
| `knowledgeDomain` | Geography, Entertainment, Science, Language, etc. (13 domains) | Topic area |

### Puzzle-Level Features (Computed)

| Feature | Description |
|---------|-------------|
| `manipulationComplexity` | Count of rows with non-default manipulation (0–4) |
| `abstractionComplexity` | Count of rows with non-default abstraction (0–4) |
| `knowledgeBreadth` | Number of distinct knowledge domains across rows (1–4) |
| `phase2TileCount` | Number of tiles in the relink phase (1–4) |
| `decoyCount` | Number of designed decoy groupings |
| `hasSpecialist` | Whether any row requires specialist knowledge |

### Impostor Domain

Each impostor has a `realIdentityDomain` — the domain it actually belongs to. When this matches the row's domain (`same_domain = True`), the impostor is harder to spot because it's semantically close to the group.

### Decoys

Some puzzles include designed **decoy groupings** — sets of tiles across rows that form a plausible (but incorrect) connection. These are traps intended to draw wrong guesses.

## Analysis Pipeline

### Architecture

The main analysis is `scripts/pdl_analysis.py`, which cross-references puzzle design parameters (PDL) with player behaviour data. It produces 14 JSON data files consumed by an interactive dashboard.

```
pdl_analysis.py (orchestrator)
├── lib/data.py     → load CSVs + PDL, build player trajectories
├── lib/metrics.py  → 9 analysis functions (crosstabs, regression, VI, clustering, etc.)
├── lib/model.py    → IPW weights, transition probs, correlated failures, simulator
└── lib/stats.py    → mean, median, percentile, pearson, spearman, ols_multi, kmeans

Outputs: 14 JSON files → outputs/data/
Dashboard: dashboard/ (Chart.js v4 + ES modules)
```

### Library Modules

| Module | Purpose |
|--------|---------|
| `lib/data.py` | Load CSVs (sessions + events), load PDL files, match events to sessions, build per-player trajectories (imposters phase + relink phase), compute date summaries with row metrics and timing |
| `lib/metrics.py` | 9 analysis compute functions: crosstabs, correlations, regression, vertical inference, decoys, relink phase, clustering, predictions, overview |
| `lib/model.py` | IPW weights for survivorship correction, transition probability distributions (by position/lives, PDL features, feature combos), correlated failure analysis (phi coefficients), Monte Carlo game simulator |
| `lib/stats.py` | Utility functions: mean, median, percentile, Pearson/Spearman correlation, OLS regression, k-means clustering, one-hot encoding |

### 14 JSON Outputs

| # | File | Analysis | Question Answered |
|---|------|----------|-------------------|
| 1 | `overview.json` | Summary stats | Headline numbers, per-date solve rates, timing percentiles |
| 2 | `crosstabs.json` | PDL cross-tabs | First-try % by manipulation, abstraction, knowledge, domain |
| 3 | `heatmap.json` | 2D difficulty grid | Manipulation × abstraction interaction |
| 4 | `impostor-domain.json` | Domain analysis | Same vs different domain impostor deception |
| 5 | `correlations.json` | Scatter plots | 6 board features vs solve rate (Pearson + Spearman) |
| 6 | `regression.json` | OLS regression | Feature coefficients on solve rate, LOO cross-validation |
| 7 | `vertical.json` | Vertical inference | Speed/accuracy improvement across positions 0→3 |
| 8 | `decoys.json` | Decoy analysis | Decoy presence effect on solve rate; hit rates |
| 9 | `relink.json` | Relink phase | Phase 2 by meta-connection type and tile count |
| 10 | `clustering.json` | k-means | Puzzle archetypes (k=3) and row archetypes (k=4) |
| 11 | `predictions.json` | Difficulty prediction | Predicted vs actual solve rates for all 39 puzzles |
| 12 | `transitions.json` | Transition model | IPW-weighted wrong-guess distributions by features |
| 13 | `failures.json` | Correlated failures | Row-pair phi coefficients; PDL similarity effects |
| 14 | `simulator.json` | Monte Carlo | Simulated solve rates; undated puzzle predictions |

### Key Derived Structures (from lib/data.py)

- **`players_by_date`**: Per-player trajectory with `position` (chronological solve order 0–3), `lives_before`, `row` (grid row index), `wrong_count`, `survived`. Also: guess events, relink trajectory, outcome (WON/LOST/INCOMPLETE).
- **`date_summaries`**: Per-date aggregated stats — row metrics (first-try %, avg wrong, top wrong words), relink stats, timing curves (inter-correct intervals).
- **`pdl_puzzle_features`**: Computed board-level features from PDL.
- **`pdl_rows`**: Row-level PDL joined across all puzzles.

### Simulator

The Monte Carlo simulator (`lib/model.py`) plays 10,000 trials per puzzle:

- **Dated puzzles** (with player data): uses empirical per-puzzle wrong-guess distributions observed from real players at each position.
- **Undated puzzles** (design-only): uses feature-based distributions from `predict_row_dist()`, which looks up wrong-guess probabilities by `(manipulation, has_decoy)` combination with a fallback chain (combo → manipulation-only with decoy shift → global baseline). Rows are sorted easiest-first to model typical player strategy.

The simulator captures cascading life-loss dynamics that simpler models (like regression) cannot — a hard early row drains lives, making later rows and the relink phase more likely to fail.

Validation: empirical model r=0.84, MAE=18pp; feature-only model r=0.47, MAE=20pp.

### IPW (Inverse Probability Weighting)

Row-level statistics are biased by survivorship — players who reach later rows are those who didn't lose all their lives on earlier ones. IPW corrects this by weighting each observation by 1/P(reaching that state), estimated from observed survival rates at each (position, lives) state.

## Scripts

### PDL Dashboard Pipeline

| Script | Output | Description |
|--------|--------|-------------|
| `pdl_analysis.py` | 14 JSON files in `outputs/data/` | Main pipeline — generates all dashboard data |

### Standalone Text Analyses

| Script | Output | Description |
|--------|--------|-------------|
| `relink_analysis.py` | `relink-analysis.txt` | Comprehensive per-puzzle breakdown: solve rates, wrong guesses, row metrics, timing |
| `compare_dates.py` | `compare-all-dates.txt` | Side-by-side table of all puzzle dates |
| `failure_analysis.py` | `failure-analysis.txt` | Deep-dive into what causes losses — which rows, which wrong words |
| `abandonment_analysis.py` | `abandonment-analysis.txt` | Players who started but didn't finish |
| `cross_date_failures.py` | `cross-date-failures.txt` | Track players across dates — do early players improve? |
| `solve_rates.py` | `solve-rates.txt` | Simple solve rate summary by date |

### Dashboard

The interactive dashboard is served from `dashboard/` as static HTML:

```bash
# From the data/ directory:
python3 -m http.server 8000 -d relink
# Then visit http://localhost:8000
```

Built with Chart.js v4 (CDN) and ES modules. 14 JavaScript renderers in `dashboard/js/` — one per analysis section — orchestrated by `main.js`.

## Key Findings

- **Solve rates vary widely**: 17%–82% across 20 puzzle dates. Mar 31 was easiest (82%); Apr 13 hardest (17%).
- **Player growth**: ~40/day early on → ~100/day by Apr 10, then tapered.
- **Tutorial usage declined**: 67% → 4% as the player base matured.
- **Manipulation is the strongest difficulty driver**: "Hidden word" manipulation rows have ~40% first-try rate vs ~75% for "None".
- **Vertical inference is real**: median inter-correct interval drops 24% from 1st→2nd to 3rd→4th correct guess. Players speed up and make fewer errors as rows resolve.
- **Same-domain impostors are harder**: impostor from the same domain as the row's theme → lower first-try rate.
- **Decoys increase difficulty**: puzzles with decoy groupings have ~10pp lower solve rates.
- **Monte Carlo simulator**: captures cascading life-loss dynamics. r=0.84 on dated puzzles. Predicts 59–77% solve rates for 19 undated puzzles.
- **Feature combos**: (manipulation, has_decoy) pairs show clear differentiation — "Hidden word + decoy" gives 32% first-try; "Word split" gives 100%.
