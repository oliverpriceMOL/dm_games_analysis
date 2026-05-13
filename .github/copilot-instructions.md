# Daily Mail Puzzles - Analytics Project

## Overview

This project analyses player behaviour data from internal tests of Daily Mail puzzle games. The data comes from multiple CSV files (with numbered suffixes for successive exports) containing session and event data from the Puzzlr analytics platform.

## Data Sources

### Raw CSVs

- `raw/daily-mail-events*.csv` — Event-level data. Columns: id, device_id, name, created_at, country, city, region, properties.
- `raw/daily-mail-sessions*.csv` — Session-level data (legacy, not used by current pipeline).
- The `properties` column contains stringified Python dicts (single quotes, **no spaces around colons** e.g. `'game_id':'relink'`). Parse with `ast.literal_eval()` but only after filtering — prefer string-based checks for pre-filtering.
- **Multi-file loading**: Scripts use `glob.glob()` to discover all matching CSVs, load them in sorted order (alphabetical), and deduplicate by row ID (last file wins). This ensures full date coverage without duplicates.
- **File sizes**: Event CSVs can be 900MB+ (5M rows). Performance-critical code must avoid full `ast.literal_eval()` during scanning.
- **Player grouping**: Players are identified by `device_id` column (not sessions). Events without a device_id are used for broad completion counts but excluded from trajectory analysis.

### PDL Save-Data (Relink only)

- `relink/save-data/puzzles-index.json` — Lists all 49 puzzles with `id`, `date`, `phase2TileCount`, `pdlComplete`, and a `searchFields` block for explorer search.
- `relink/save-data/pdl-schema.json` — Enum vocabulary for the PDL fields (knowledge levels, manipulation types, abstraction levels, knowledge domains, plus the smaller relink-specific manipulation enums).
- `relink/save-data/l{id}.json` — Per-puzzle design file. Schema **v2** (top-level `schemaVersion: 2`). Contains `canonicalId` (the level_id string used in analytics events to identify this puzzle), 4 rows (each with tiles, impostor flags, and a nested `pdl.group.{manipulation, abstraction, knowledge, knowledgeDomain}` block plus `pdl.impostor.realIdentityDomain` — every PDL leaf is now an array, multi-valued allowed). Relink phase has split PDL (`connectionIdentification` with manipulation/knowledge/abstraction/knowledgeDomain + `answerConstruction` with manipulation/knowledge), decoy groupings (with `pdl.knowledge/manipulation/abstraction` arrays plus reserved `completeness` and `groupsSpanned` fields — currently unpopulated on all puzzles), and board metadata (`phase2TileCount`, `specialistGroupCount`, `isThemed`, `themeDomain`).
- 7 of the 49 puzzles have both dates and matching player behaviour data (May 7–13); a further 3 are dated in the future (May 14–16); the remaining 39 are undated design-only puzzles.

**PDL schema v2 notes**: Loader (`lib/data.py`) reads the full arrays and exposes both scalar (`manipulation`, `knowledgeDomain`, …) and list (`manipulations`, `knowledgeDomains`, `realIdentityDomains`, …) keys on each `pdl_rows` entry. The `same_domain` flag is computed via set intersection between the row's `knowledgeDomain` and the impostor's `realIdentityDomain` (any overlap = same), and an explicit `cross_domain_impostor` boolean is emitted alongside. `decoys[].pdl.completeness`, `decoys[].pdl.groupsSpanned`, and `board.themeDomain` are reserved schema-v2 fields with no analytical signal yet — analyses that rely on them should warn rather than silently treat empties as zero.

**Canonical ID system**: Each puzzle JSON has a `"canonicalId"` field (e.g. `"mov6vke9-yv61qq8"`) matching the `level_id` property in analytics events. All 7 dated puzzles with player data have canonical IDs. After building player trajectories, `load_all()` filters out players whose `level_id` doesn't match the canonical for their date. This removes glitch data (e.g. wrong puzzle served during server switches).

## Games

### Relink (`game_id: 'relink'`)

A word puzzle played on a 4×4 grid with two phases:

**Phase 1 — Imposters:** The grid has 4 colour-coded rows of 4 tiles each. Three tiles in each row share a hidden connection; the fourth is an impostor (wrong word). Players start with 4 lives.

- Each turn: select one tile from any row, then submit.
- If the selected tile is the impostor → row resolves (no life lost). The row's connection is revealed.
- If wrong → lose a life. The selected tile is eliminated (can't pick it again). Player can retry the same row or switch to a different one.
- Players can freely switch between rows at any time — they don't have to solve one row before trying another.
- Max 3 wrong guesses per row (4 tiles, 1 impostor — after 3 wrongs the impostor is the only tile left).
- Phase ends when all 4 impostors found (proceed to relink) or all lives lost (game over).

**Phase 2 — Relink:** The 4 impostors share a hidden connection. Players select tiles from the resolved grid to spell it out (1–4 slots to fill).

- Each guess = select a set of tiles to fill the remaining slots.
- Wrong guess → told "X of Y correct" + lose a life.
- Game ends when the link is correctly spelled or lives run out.

**Analytics events:**
- `relink_guess_submitted` (imposters phase): `row_index`, `selected_word`, `is_correct`, `attempts_remaining`, `phase: 'imposters'`, `level_id`
- `relink_guess_submitted` (relink phase): `selected_tile_ids` (e.g. `r3w0,r0w1`), `is_correct`, `phase: 'relink'`, `level_id`
- `level_completed`: `is_won`, `puzzle_date`, `level_id`
- Data covers May 7–13, 2026 (7 puzzle dates with player data, post-launch). ~8K–17.5K completions per day (all users).

### Trace (`game_id: 'word-flow'`)
- A word-tracing puzzle. No guess-level events — only `level_started`, `level_completed`, `tutorial_started/completed/skipped`, `level_result_shared`, `final_board_viewed`, `session_started`.
- `level_completed` properties: `time_seconds`, `current_streak`, `puzzle_date`, `is_archive`, `next_puzzle_available`.
- No win/loss — all completions are wins. Key metric is solve time.
- Data covers Mar 26 – Apr 6, 2026 (ignore Mar 25, pre-launch test). ~74K completions across 12 days.
- Puzzle words (not in data): TRACE (Mar 26), LEANING (27), WHEEL (28), PARTIAL (29), UNIQUE (30), WEEPING (31), FOOLS (Apr 1), BUNNY (Apr 2), REFRESH (3), BREEZE (4), RIPPLE (5), ECLIPSE (6).

## Filters

- **Relink bot filter**: `(country in ('NL','IE') and duration <= 10) or duration <= 2`
- **Relink dev filter**: sessions from Västerås, SE excluded.
- **Relink tutorial detection**: `int(attempts_remaining) > 4` — tutorial events have lives starting at 999.
- **Relink tester filter**: INCOMPLETE outcomes with 0 wrong guesses.
- **Relink canonical filter**: Players whose `level_id` doesn't match the puzzle's `canonicalId` for that date are excluded (removes glitch/wrong-puzzle data).
- **Relink date filter**: Only dates with a puzzle design in save-data (i.e. May 7+) are loaded; pre-launch test data is excluded by absence of matching dates.
- **Trace**: Mar 25 data excluded (pre-launch test).

## Project Structure

```
data/
├── raw/                              # Source CSVs (gitignored, do not modify)
│   ├── daily-mail-events-*.csv        # Event-level (900MB+, 4M rows)
│   └── daily-mail-sessions-*.csv      # Session-level (170MB+, 300K rows)
├── relink/
│   ├── scripts/
│   │   ├── lib/                      # Shared library modules
│   │   │   ├── data.py               # Data loading, trajectory building
│   │   │   ├── metrics.py            # 10 analysis compute functions (incl. difficulty ratings)
│   │   │   ├── model.py              # IPW, transitions, full-feature simulator
│   │   │   └── stats.py              # Stats utilities (OLS, k-means, correlations)
│   │   ├── pdl_analysis.py           # Main pipeline → 15 JSON files + HTML dashboard
│   │   ├── relink_analysis.py        # Comprehensive per-puzzle text analysis
│   │   ├── compare_dates.py          # Side-by-side comparison of all puzzle dates
│   │   ├── failure_analysis.py       # Deep-dive into what causes losses
│   │   ├── abandonment_analysis.py   # Players who started but didn't finish
│   │   ├── cross_date_failures.py    # Track players across dates
│   │   ├── solve_rates.py            # Simple solve rate summary by date
│   │   └── fix_leverage.py           # Per-row fix-leverage punch list (reads pipeline outputs, no CSV reload)
│   ├── dashboard/                    # Static HTML dashboard (served via http.server)
│   │   ├── index.html
│   │   ├── css/
│   │   └── js/                       # ES modules: main.js + charts.js + 15 section renderers
│   ├── docs/                         # 6 comprehensive documentation files
│   │   ├── 00-overview.md
│   │   ├── 01-data-loading.md
│   │   ├── 02-analysis-phases.md
│   │   ├── 03-statistical-modelling.md
│   │   ├── 04-simulator.md
│   │   └── 05-dashboard.md
│   ├── outputs/
│   │   ├── data/                     # 15 JSON files (pdl_analysis.py) + fix-leverage.json (fix_leverage.py)
│   │   ├── pdl-analysis.html         # Standalone HTML report (legacy)
│   │   ├── relink-analysis.txt
│   │   ├── compare-all-dates.txt
│   │   ├── failure-analysis.txt
│   │   ├── abandonment-analysis.txt
│   │   ├── cross-date-failures.txt
│   │   ├── solve-rates.txt
│   │   └── fix-leverage.txt
│   ├── save-data/                    # 49 puzzle design files (PDL JSON, schema v2) + puzzles-index.json + pdl-schema.json
│   ├── index.html                    # Redirects to dashboard/
│   └── README.md
├── trace/
│   ├── scripts/
│   │   ├── trace_analysis.py         # 11-section trace analysis
│   │   ├── plot_solve_time.py        # HTML chart of solve time distributions
│   │   ├── retention_analysis.py     # Player retention across dates
│   │   ├── solve_rate_by_length.py   # Solve rates by word length
│   │   ├── engagement_vs_difficulty.py
│   │   └── _check_fingerprint.py     # Utility for fingerprint inspection
│   ├── outputs/
│   │   ├── trace-analysis.txt
│   │   ├── solve-time-by-length.html
│   │   └── retention-analysis.txt
│   └── README.md
├── README.md
└── .github/
    └── copilot-instructions.md       # This file
```

## Relink PDL Analysis Pipeline

The main analysis is `relink/scripts/pdl_analysis.py`, which cross-references puzzle design parameters (PDL) with player behaviour data. It produces 15 JSON data files consumed by an interactive dashboard.

### Architecture

```
pdl_analysis.py (orchestrator)
├── lib/data.py     → load CSVs + PDL, build player trajectories
├── lib/metrics.py  → 10 analysis functions (crosstabs, regression, VI, clustering, difficulty, etc.)
├── lib/model.py    → IPW weights, transition probs, correlated failures, full-feature simulator
└── lib/stats.py    → mean, median, percentile, pearson, spearman, ols_multi, kmeans

Outputs: 15 JSON files → relink/outputs/data/
Dashboard: relink/dashboard/ (Chart.js v4 + ES modules)
```

### 15 JSON Outputs

Plus a 16th JSON `fix-leverage.json` produced by the standalone `fix_leverage.py` script (re-reads pipeline outputs, no CSV reload).

| File | Analysis | What It Answers |
|------|----------|-----------------|
| `overview.json` | Summary stats | Headline numbers, per-date solve rates, timing percentiles |
| `crosstabs.json` | PDL cross-tabs | First-try % by manipulation, abstraction, knowledge, domain |
| `heatmap.json` | 2D difficulty grid | Manipulation × abstraction interaction |
| `impostor-domain.json` | Domain analysis | Same vs different domain impostor deception |
| `correlations.json` | Scatter plots | 6 board features vs solve rate (Pearson + Spearman) |
| `regression.json` | OLS regression | Feature coefficients, LOO cross-validation |
| `vertical.json` | Vertical inference | Speed/accuracy improvement across positions 0→3 |
| `decoys.json` | Decoy analysis | Decoy presence effect on solve rate; hit rates |
| `relink.json` | Relink phase | Phase 2 by connection identification, answer construction, and tile count |
| `clustering.json` | k-means | Puzzle archetypes (k=3) and row archetypes (k=4) |
| `puzzle-explorer.json` | Puzzle Explorer | Per-puzzle deep-dive with outcome-split wrong distributions, timing curves, PDL features, simulator predictions |
| `transitions.json` | Transition model | IPW-weighted wrong-guess distributions by features |
| `failures.json` | Correlated failures | Row-pair phi coefficients; PDL similarity effects |
| `simulator.json` | Monte Carlo | Simulated solve rates; undated puzzle predictions |
| `difficulty.json` | Difficulty ratings | 5-axis profiles, composites, star ratings, validation |

### Two-Tier Analysis

The pipeline uses two levels of data:

1. **All-user completions (`completions_all`)**: Every `level_completed` event regardless of whether the player has a `device_id`. Used for headline stats in the Overview page and Published Puzzles table (solve rate, player count, wins/losses). ~98K total completions across 7 dates.

2. **Device-ID trajectories (`players_by_date`)**: Only players with a `device_id` whose full guess sequence can be reconstructed. Used for per-row analysis, wrong-guess distributions, timing curves, simulator training, and all detailed behavioural modelling. ~65K trajectories across 7 dates.

The two levels agree within ~1pp on solve rate (no selection bias from device_id availability).

### Key Derived Structures (from lib/data.py)

- **`completions_all`**: `{date: {level_id: {'wins': int, 'losses': int}}}` — broad completion counts from ALL events.
- **`players_by_date`**: Per-player trajectory (position, lives_before, row, wrong_count, survived), guess events, relink trajectory, outcome. Device-ID grouped.
- **`pdl_puzzle_features`**: Computed board-level features (manipulationComplexity, abstractionComplexity, knowledgeBreadth, phase2TileCount, decoyCount, etc.).
- **`pdl_rows`**: Row-level PDL joined across all puzzles (manipulation, abstraction, knowledge, domain, same_domain flag, plus relink split PDL fields).
- **`date_summaries`**: Per-date aggregated stats from trajectory data — row metrics, timing curves.
- **`canonical_ids`**: `{date: canonicalId}` — maps dates to their puzzle's canonical level_id.

### Running

```bash
# Generate all 15 JSON data files (~75s with optimized loading):
python3 relink/scripts/pdl_analysis.py

# Serve dashboard (then visit http://localhost:8000):
python3 -m http.server 8000 -d relink
```

## Conventions

- **Always create .py script files** — never run inline Python in the terminal.
- **Python 3 stdlib only** — no numpy, pandas, or external packages. Uses `csv`, `ast`, `json`, `glob`, `math`, `collections`, `os`, `sys`, `bisect`.
- Scripts use `os.path.dirname` chains for relative paths: `SCRIPT_DIR → GAME_DIR → DATA_DIR`.
- Older scripts write output to their game's `outputs/` folder and redirect stdout via `sys.stdout = out`.
- Use `csv.DictReader` and `ast.literal_eval()` for parsing — but **defer** `ast.literal_eval()` to after filtering/matching for performance. Use string-based checks (`'relink' in props`, `"'game_id':'relink'" in props`) for pre-filtering.
- Use `glob.glob()` to discover all CSV files matching a pattern, load in sorted order, deduplicate by ID (dict keyed by ID, last file wins).
- Show raw figures alongside percentages (e.g. `28/34 (82%)`).
- Separate analysis by puzzle date where applicable.
- Dates and labels are derived dynamically from the data — no hardcoded date lists.
- Dashboard uses Chart.js v4 via CDN (non-module global) and ES modules for all JS renderers.

## Key Findings

- **Relink**: Solve rates vary across 7 puzzles (May 7–13, 22–68%). ~98K total completions (all users), ~65K device-ID trajectories. The full-feature Monte Carlo simulator uses a ratio-shift model stacking adjustments for manipulation, abstraction, knowledge, same_domain, position (imposters phase) and identification manipulation, construction knowledge, tile count (relink phase). Empirical mode: r=0.993, MAE=8.2pp. Predicts solve rates for 42 puzzles without player data. A 5-axis difficulty rating system (manipulation 10%, abstraction 30%, domain mismatch 10%, knowledge 10%, relink challenge 40%) produces 1–5 star ratings with severity-based scoring (avg_wrong/3) and a vertical inference discount.
- **Trace**: Puzzle difficulty varies hugely — median solve times range from 18s to 164s. 7-letter words take ~3× longer than 5-letter words but completion rates are similar (~80% vs ~88%). Sharing rate is flat at 1%. Hard puzzles reduce next-day retention by ~12pp.
