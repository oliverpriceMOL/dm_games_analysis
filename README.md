# Daily Mail Puzzles — Analytics

Analysis of player behaviour data from internal tests of Daily Mail puzzle games. The data comes from the [Puzzlr](https://puzzlr.com) analytics platform, covering session and event data from early 2026.

## Games

| Game | Internal ID | Data Period | Completions |
|------|------------|-------------|-------------|
| [Relink](relink/) | `relink` | Mar 25 – Apr 13, 2026 | ~496 |
| [Trace](trace/) | `word-flow` | Mar 26 – Apr 6, 2026 | ~74,000 |

## Project Structure

```
├── raw/                        # Source CSVs (gitignored)
├── relink/
│   ├── scripts/                # 7 analysis scripts
│   ├── outputs/                # Text reports + interactive HTML
│   └── save-data/              # Puzzle design files (PDL JSON)
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
python3 relink/scripts/pdl_analysis.py      # Generates interactive HTML report
python3 trace/scripts/trace_analysis.py      # Generates text analysis
```

Each script is self-contained and can be run independently.

## See Also

- [Relink documentation](relink/README.md) — Game rules, scripts, key findings
- [Trace documentation](trace/README.md) — Game rules, scripts, key findings
