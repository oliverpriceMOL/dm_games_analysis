# Daily Mail Puzzles - Analytics Project

## Overview

This project analyses player behaviour data from internal tests of Daily Mail puzzle games. The data comes from multiple CSV files (with numbered suffixes for successive exports) containing session and event data from the Puzzlr analytics platform.

## Data Sources

### Raw CSVs

- `raw/daily-mail-sessions*.csv` — Session-level data. Four files: original, `-2`, `-3`, `-4` covering overlapping date ranges. Columns: id, created_at, ended_at, is_bounce, duration, screen_view_count, event_count, entry_path, exit_path, referrer, country, city, region, device, browser, browser_version, os, os_version, utm fields, properties.
- `raw/daily-mail-events*.csv` — Event-level data. Four files: original, `-2`, `-3`, `-4` covering overlapping date ranges. Columns: id, name, created_at, country, city, region, properties.
- The `properties` column in both files contains stringified Python dicts (single quotes). Parse with `ast.literal_eval()`.
- **Multi-file loading**: Scripts use `glob.glob()` to discover all matching CSVs, load them in sorted order (alphabetical), and deduplicate by row ID (last file wins). This ensures full date coverage without duplicates.

### PDL Save-Data (Relink only)

- `relink/save-data/puzzles-index.json` — Lists all 39 puzzles with `id` and `date`.
- `relink/save-data/l{id}.json` — Per-puzzle design file. Contains 4 rows (each with tiles, impostor flags, PDL metadata: manipulation, abstraction, knowledge, knowledgeDomain), relink answer with split PDL (connectionIdentification + answerConstruction), decoy groupings, board metadata (`phase2TileCount`, `specialistGroupCount`, `isThemed`).
- 17 of the 39 puzzles have matching player behaviour data (Mar 31 – Apr 16); the remaining 22 are undated design-only puzzles without player data.

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
- `relink_guess_submitted` (imposters phase): `row_index`, `selected_word`, `is_correct`, `attempts_remaining`, `phase: 'imposters'`
- `relink_guess_submitted` (relink phase): `selected_tile_ids` (e.g. `r3w0,r0w1`), `is_correct`, `phase: 'relink'`
- `level_completed`: `is_won`, `puzzle_date`
- Data covers Mar 31 – Apr 16, 2026 (17 puzzle dates with player data). Player counts grew from ~40/day to ~100/day over the period. ~900+ total completions.

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
- **Trace**: Mar 25 data excluded (pre-launch test).

## Project Structure

```
data/
├── raw/                              # Source CSVs (gitignored, do not modify)
│   ├── daily-mail-events.csv
│   ├── daily-mail-events-2.csv
│   ├── daily-mail-events-3.csv
│   ├── daily-mail-events-4.csv
│   ├── daily-mail-sessions.csv
│   ├── daily-mail-sessions-2.csv
│   ├── daily-mail-sessions-3.csv
│   └── daily-mail-sessions-4.csv
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
│   │   └── solve_rates.py            # Simple solve rate summary by date
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
│   │   ├── data/                     # 15 JSON files (generated by pdl_analysis.py)
│   │   ├── pdl-analysis.html         # Standalone HTML report (legacy)
│   │   ├── relink-analysis.txt
│   │   ├── compare-all-dates.txt
│   │   ├── failure-analysis.txt
│   │   ├── abandonment-analysis.txt
│   │   ├── cross-date-failures.txt
│   │   └── solve-rates.txt
│   ├── save-data/                    # 39 puzzle design files (PDL JSON)
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

### Key Derived Structures (from lib/data.py)

- **`players_by_date`**: Per-player trajectory (position, lives_before, row, wrong_count, survived), guess events, relink trajectory, outcome.
- **`pdl_puzzle_features`**: Computed board-level features (manipulationComplexity, abstractionComplexity, knowledgeBreadth, phase2TileCount, decoyCount, etc.).
- **`pdl_rows`**: Row-level PDL joined across all puzzles (manipulation, abstraction, knowledge, domain, same_domain flag, plus relink split PDL fields).
- **`date_summaries`**: Per-date aggregated stats, row metrics, timing curves.

### Running

```bash
# Generate all 15 JSON data files (~5-8 min, CSV loading dominates):
python3 relink/scripts/pdl_analysis.py

# Serve dashboard (then visit http://localhost:8000):
python3 -m http.server 8000 -d relink
```

## Conventions

- **Always create .py script files** — never run inline Python in the terminal.
- **Python 3 stdlib only** — no numpy, pandas, or external packages. Uses `csv`, `ast`, `json`, `glob`, `math`, `collections`, `os`, `sys`.
- Scripts use `os.path.dirname` chains for relative paths: `SCRIPT_DIR → GAME_DIR → DATA_DIR`.
- Older scripts write output to their game's `outputs/` folder and redirect stdout via `sys.stdout = out`.
- Use `csv.DictReader` and `ast.literal_eval()` for parsing.
- Use `glob.glob()` to discover all CSV files matching a pattern, load in sorted order, deduplicate by ID (dict keyed by ID, last file wins).
- Show raw figures alongside percentages (e.g. `28/34 (82%)`).
- Separate analysis by puzzle date where applicable.
- Dates and labels are derived dynamically from the data — no hardcoded date lists.
- Event-session matching is optimized by bucketing events by `(country, date)` before matching, to avoid O(n*m) performance.
- Dashboard uses Chart.js v4 via CDN (non-module global) and ES modules for all JS renderers.

## Key Findings

- **Relink**: Solve rates vary widely across 17 dated puzzles (17%–83%). Mar 31 was easiest (83%); Apr 13 hardest (17%). Player counts grew from ~40/day to ~100/day by Apr 10. The full-feature Monte Carlo simulator uses a ratio-shift model stacking adjustments for manipulation, abstraction, knowledge, same_domain, position (imposters phase) and identification manipulation, construction knowledge, tile count (relink phase). Empirical mode: r=0.929, MAE=11.1pp. Spearman rank ρ = −0.782. Predicts solve rates for 22 puzzles without player data. A 5-axis difficulty rating system (manipulation 10%, abstraction 30%, domain mismatch 10%, knowledge 10%, relink challenge 40%) produces 1–5 star ratings with severity-based scoring (avg_wrong/3) and a vertical inference discount.
- **Trace**: Puzzle difficulty varies hugely — median solve times range from 18s to 164s. 7-letter words take ~3× longer than 5-letter words but completion rates are similar (~80% vs ~88%). Sharing rate is flat at 1%. Hard puzzles reduce next-day retention by ~12pp.
