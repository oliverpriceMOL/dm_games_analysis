# Relink — Analysis

## The Game

Relink is a word puzzle with two phases:

1. **Imposters phase** — A 4×4 grid of words, grouped into 4 rows. Each row contains one "imposter" word that doesn't belong. Players tap one tile per guess to identify the imposter. 4 lives total across all rows.
2. **Relink phase** — After finding all imposters, players select tiles that spell out the hidden *link* connecting the four imposters.

Players can attempt rows in any order. The game ends when all imposters are found (proceed to relink) or all lives are lost.

## Data

- **Period**: Mar 25 – Apr 13, 2026 (20 puzzle dates)
- **Player counts**: Grew from ~40/day early on to ~100/day by Apr 10
- **Total completions**: ~496
- **Puzzle design files**: 39 puzzles in `save-data/` (PDL JSON format), 20 of which have matching player data

### Filters Applied

| Filter | Rule | Purpose |
|--------|------|---------|
| Bot | `(country in NL/IE and duration ≤ 10s) or duration ≤ 2s` | Remove automated traffic |
| Tutorial | `attempts_remaining > 4` | Tutorial events have 999 lives |
| Tester | `INCOMPLETE outcome with 0 wrong guesses` | Remove passive testers |

### Event Types

| Event | Phase | Key Properties |
|-------|-------|---------------|
| `relink_guess_submitted` | Imposters | `row_index`, `selected_word`, `is_correct`, `attempts_remaining`, `phase: 'imposters'` |
| `relink_guess_submitted` | Relink | `selected_tile_ids`, `is_correct`, `phase: 'relink'` |
| `level_completed` | End | `is_won`, `puzzle_date` |

## Scripts

| Script | Output | Description |
|--------|--------|-------------|
| `relink_analysis.py` | `relink-analysis.txt` | Comprehensive per-puzzle breakdown: solve rates, wrong guesses, row metrics, timing |
| `compare_dates.py` | `compare-all-dates.txt` | Side-by-side table of all puzzle dates |
| `failure_analysis.py` | `failure-analysis.txt` | Deep-dive into what causes losses — which rows, which wrong words |
| `abandonment_analysis.py` | `abandonment-analysis.txt` | Players who started but didn't finish |
| `cross_date_failures.py` | `cross-date-failures.txt` | Track players across dates — do early players improve? |
| `solve_rates.py` | `solve-rates.txt` | Simple solve rate summary by date |
| `pdl_analysis.py` | `pdl-analysis.html` | **Interactive HTML report** — cross-references puzzle design (PDL) with player behaviour |

### PDL Analysis (`pdl_analysis.py`)

The main analysis script. Joins puzzle design parameters (manipulation type, abstraction, knowledge level, decoys, etc.) with behavioural data to answer: *which design choices make puzzles harder or easier?*

**Sections in the HTML report:**

1. **Key Findings** — Top-line stats (prediction correlation, MAE, strongest predictor)
2. **PDL Cross-tabs** — First-try % and avg wrong guesses grouped by each PDL axis (manipulation, abstraction, knowledge, domain)
3. **Difficulty Heatmap** — Manipulation × abstraction 2D grid
4. **Impostor Domain** — Same vs different domain between impostor and group
5. **Puzzle-Level Correlations** — 6 scatter plots of design features vs solve rate (Pearson + Spearman)
6. **Regression Models** — Puzzle-level (with LOO-CV), row-level, and position-controlled (adding mean attempt position as covariate for vertical inference)
7. **Vertical Inference** — Which PDL features promote or inhibit players deducing the theme mid-game. Cross-tabs acceleration and transparency against all 8 PDL axes
8. **Decoy Analysis** — Puzzles with vs without designed decoy groupings; decoy hit rates
9. **Cross-Row Confusion** — When players guess wrong, which row did their pick actually belong to?
10. **Relink Phase** — Phase 2 performance grouped by meta-connection manipulation type and tile count
11. **Clustering** — K-means archetypes for puzzles (k=3) and rows (k=4)
12. **Difficulty Predictions** — Predicted solve rate for all 39 puzzles using row-level regression; validation scatter + sortable table

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
| `phase2TileCount` | Number of tiles in the relink phase |
| `decoyCount` | Number of designed decoy groupings |

## Key Findings

- **Solve rates vary widely**: 17%–83% across 20 puzzle dates
- **PDL features show modest individual effects** but combine meaningfully in regression (row R² = 0.25, position-controlled R² = 0.27)
- **Vertical inference is real**: median inter-correct interval drops 24% from 1st→2nd to 3rd→4th correct guess (14.0s → 10.6s). 10/14 puzzles show acceleration
- **Position effect**: +1.3pp first-try rate per later attempt position (quantified via position-controlled regression)
- **Manipulation complexity inhibits vertical inference**: 0 complexity = 0.64x acceleration, 2 complexity = 1.10x (no speed-up)
- **Prediction**: Row-level PDL regression predicts solve rates with r = 0.48, MAE = 16pp
- **Tutorial usage declined** from 67% → 4% as the player base matured
