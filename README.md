# Daily Mail Puzzles — Analytics

Analysis of player behaviour data from internal tests of Daily Mail puzzle games. The data comes from the [Puzzlr](https://puzzlr.com) analytics platform, covering session and event data from early 2026.

## Games

| Game | Internal ID | Data Period | Completions |
|------|------------|-------------|-------------|
| [Relink](relink/) | `relink` | Mar 31 – Apr 13, 2026 | ~496 |
| [Trace](trace/) | `word-flow` | Mar 26 – Apr 6, 2026 | ~74,000 |

## Project Structure

```
├── raw/                        # Source CSVs (gitignored)
├── relink/
│   ├── scripts/
│   │   ├── lib/                # Shared library (data, metrics, model, stats)
│   │   └── pdl_analysis.py     # Main pipeline → 13 JSON files
│   ├── dashboard/              # Interactive Chart.js dashboard
│   ├── docs/                   # 6 documentation files (architecture, data, analysis, model, simulator, dashboard)
│   ├── outputs/
│   │   ├── data/               # 13 JSON files (generated)
│   │   └── *.txt               # Legacy text reports
│   └── save-data/              # 39 puzzle design files (PDL JSON)
├── trace/
│   ├── scripts/                # 6 analysis scripts
│   └── outputs/                # Text reports + interactive HTML
└── .github/
    └── copilot-instructions.md # AI assistant context
```

## Data Sources

All scripts read from `raw/` which contains:

- `daily-mail-sessions*.csv` (3 files) — Session-level data: duration, device, browser, entry/exit paths, UTM fields, etc.
- `daily-mail-events*.csv` (3 files) — Event-level data: event name, timestamp, properties (stringified Python dicts).

The numbered suffixes (`-2`, `-3`) are successive exports with overlapping date ranges. Scripts use `glob.glob()` to discover all matching CSVs, load in sorted order, and deduplicate by row ID (last file wins).

The `raw/` directory is gitignored as it contains potentially sensitive player data. Scripts will not run without it.

## Conventions

- **Python 3 stdlib only** — no numpy, pandas, or external packages. Uses `csv`, `ast`, `json`, `glob`, `math`, `collections`.
- All analysis is in `.py` script files run from the terminal — no notebooks or inline execution.
- Scripts use relative path chains (`SCRIPT_DIR → GAME_DIR → DATA_DIR`) so they work from any working directory.
- Output goes to each game's `outputs/` folder.
- Raw figures shown alongside percentages: `28/34 (82%)`.
- The `properties` column in CSVs contains stringified Python dicts — parsed with `ast.literal_eval()`.

## Running

```bash
# From the data/ directory:

# Relink — generate 13 JSON data files (~5-8 min):
python3 relink/scripts/pdl_analysis.py

# Relink — serve interactive dashboard (http://localhost:8000):
python3 -m http.server 8000 -d relink

# Trace — generate text analysis:
python3 trace/scripts/trace_analysis.py
```

Each script is self-contained and can be run independently.

## Key Findings

- **Relink**: Solve rates vary 17–83% across 14 dated puzzles. Manipulation type is the strongest difficulty driver. Full-feature Monte Carlo simulator achieves r=0.934 (empirical) / r=0.655 (feature-only) with Spearman ρ=0.938 rank correlation. Predicts solve rates for 25 puzzles without player data. See [relink/README.md](relink/README.md) for full details.
- **Trace**: Median solve times range from 18s to 164s across 12 puzzles. 7-letter words take ~3× longer than 5-letter words. Hard puzzles reduce next-day retention by ~12pp. See [trace/README.md](trace/README.md) for full details.

## See Also

- [Relink documentation](relink/README.md) — Game rules, PDL system, analysis pipeline, 13 dashboard sections, key findings
- [Relink detailed docs](relink/docs/) — 6-document architecture guide
- [Trace documentation](trace/README.md) — Game rules, scripts, difficulty & retention findings
