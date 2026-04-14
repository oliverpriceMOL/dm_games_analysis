# Daily Mail Puzzles - Analytics Project

## Overview

This project analyses player behaviour data from internal tests of Daily Mail puzzle games. The data comes from multiple CSV files (with numbered suffixes for successive exports) containing session and event data from the Puzzlr analytics platform.

## Data Sources

- `raw/daily-mail-sessions*.csv` — Session-level data. Three files: original, `-2`, `-3` covering overlapping date ranges. Columns: id, created_at, ended_at, is_bounce, duration, screen_view_count, event_count, entry_path, exit_path, referrer, country, city, region, device, browser, browser_version, os, os_version, utm fields, properties.
- `raw/daily-mail-events*.csv` — Event-level data. Three files: original, `-2`, `-3` covering overlapping date ranges. Columns: id, name, created_at, country, city, region, properties.
- The `properties` column in both files contains stringified Python dicts (single quotes). Parse with `ast.literal_eval()`.
- **Multi-file loading**: Scripts use `glob.glob()` to discover all matching CSVs, load them in sorted order (alphabetical), and deduplicate by row ID (last file wins). This ensures full date coverage without duplicates.

## Games

### Relink (`game_id: 'relink'`)
- A word puzzle with two phases: **imposters** (identify wrong words in rows, one tile per guess) and **relink** (select tiles that spell out the link between the imposters).
- 4 rows, 4 lives. Event names: `guess_made` (imposters phase), `relink_guess_submitted` (relink phase), `level_completed` (has `is_won`).
- Imposters phase properties: `row_index`, `selected_word`, `is_correct`, `attempts_remaining`, `phase: 'imposters'`.
- Relink phase properties: `selected_tile_ids` (e.g. `r3w0,r0w1`), `is_correct`, `phase: 'relink'`. Players select tiles to form the link answer.
- Data covers Mar 25 – Apr 13, 2026 (20 puzzle dates). Player counts grew from ~40/day to ~100/day over the period. ~496 total completions.

### Trace (`game_id: 'word-flow'`)
- A word-tracing puzzle. No guess-level events — only `level_started`, `level_completed`, `tutorial_started/completed/skipped`, `level_result_shared`, `final_board_viewed`, `session_started`.
- `level_completed` properties: `time_seconds`, `current_streak`, `puzzle_date`, `is_archive`, `next_puzzle_available`.
- No win/loss — all completions are wins. Key metric is solve time.
- Data covers Mar 26 – Apr 1, 2026 (ignore Mar 25, pre-launch test). ~36K completions across 7 days.
- Puzzle words (not in data): TRACE (Mar 26), LEANING (27), WHEEL (28), PARTIAL (29), UNIQUE (30), WEEPING (31), FOOLS (Apr 1).

## Filters

- **Relink bot filter**: `(country in ('NL','IE') and duration <= 10) or duration <= 2`
- **Relink tutorial detection**: `int(attempts_remaining) > 4` — tutorial events have lives starting at 999.
- **Trace**: Mar 25 data excluded (pre-launch test).

## Project Structure

```
data/
├── raw/                              # Source CSVs (do not modify)
│   ├── daily-mail-events.csv         # Original export
│   ├── daily-mail-events-2.csv       # Second export (overlapping dates)
│   ├── daily-mail-events-3.csv       # Third export (overlapping dates)
│   ├── daily-mail-sessions.csv
│   ├── daily-mail-sessions-2.csv
│   └── daily-mail-sessions-3.csv
├── relink/
│   ├── scripts/
│   │   ├── relink_analysis.py        # Comprehensive multi-section analysis
│   │   ├── compare_dates.py          # Side-by-side comparison of all puzzle dates
│   │   ├── failure_analysis.py       # Deep-dive into what causes losses, per puzzle
│   │   ├── abandonment_analysis.py   # Standalone abandonment analysis
│   │   ├── cross_date_failures.py    # Track players across dates (early vs late)
│   │   └── solve_rates.py            # Simple solve rate summary by date
│   └── outputs/
│       ├── relink-analysis.txt
│       ├── compare-all-dates.txt
│       ├── failure-analysis.txt
│       ├── abandonment-analysis.txt
│       ├── cross-date-failures.txt
│       └── solve-rates.txt
├── trace/
│   ├── scripts/
│   │   ├── trace_analysis.py         # 11-section trace analysis
│   │   ├── plot_solve_time.py        # HTML chart of solve time distributions
│   │   ├── retention_analysis.py     # Player retention across dates
│   │   ├── solve_rate_by_length.py   # Solve rates by word length
│   │   ├── engagement_vs_difficulty.py
│   │   └── _check_fingerprint.py     # Utility for fingerprint inspection
│   └── outputs/
│       ├── trace-analysis.txt
│       ├── solve-time-by-length.html
│       └── retention-analysis.txt
└── .github/
    └── copilot-instructions.md
```

## Conventions

- **Always create .py script files** — never run inline Python in the terminal.
- Scripts use `os.path.dirname` chains for relative paths: `SCRIPT_DIR → GAME_DIR → DATA_DIR`.
- Scripts write output to their game's `outputs/` folder and redirect stdout via `sys.stdout = out`.
- Use `csv.DictReader` and `ast.literal_eval()` for parsing.
- Use `glob.glob()` to discover all CSV files matching a pattern, load in sorted order, deduplicate by ID (dict keyed by ID, last file wins).
- Show raw figures alongside percentages (e.g. `28/34 (82%)`).
- Separate analysis by puzzle date where applicable.
- Dates and labels are derived dynamically from the data — no hardcoded date lists.
- Event-session matching is optimized by bucketing events by `(country, date)` before matching, to avoid O(n*m) performance.

## Key Findings

- **Relink**: Solve rates vary widely across 20 puzzle dates (17%–82%). Mar 31 had the highest solve rate (82%); Apr 9 (21%) and Apr 13 (17%) were the hardest. Player counts grew from ~40/day early on to ~100/day by Apr 10, then tapered. Tutorial usage declined over time (67% → 4%), indicating a maturing player base.
- **Trace**: Puzzle difficulty varies hugely — median solve times range from 32s to 164s. 7-letter words take ~2.5x longer than 5-letter words but completion rates are similar (~80% vs ~88%). Sharing rate is flat at 1%.
