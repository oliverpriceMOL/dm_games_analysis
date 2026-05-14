# Relink Analysis Pipeline — Overview

## What This Is

This is a data analysis pipeline that measures how hard each Relink puzzle is and predicts the difficulty of puzzles that haven't been played yet. It works by combining two sources of information:

1. **Puzzle Design Language (PDL)** — structured tags that describe how each puzzle is designed (what kind of word manipulation is used, how abstract the connections are, what knowledge is required)
2. **Player Behaviour Data** — event logs from real players showing exactly what they guessed, when, and whether they won or lost

The pipeline cross-references these two sources to answer: *which design features make puzzles harder, and can we predict a new puzzle's difficulty from its design alone?*

## The Big Picture

```
┌─────────────────────────────────────────────────────────────┐
│                     INPUT DATA                              │
│                                                             │
│  save-data/           raw/                                  │
│  49 puzzle PDL files  Event CSVs (900MB+, 5M rows)          │
│  (design tags)        (player behaviour logs)               │
└──────────┬─────────────────────────┬────────────────────────┘
           │                         │
           ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA LOADING                             │
│                    lib/data.py                              │
│                                                             │
│  • Parse 49 puzzle design files → PDL features              │
│  • Parse CSV logs → filter bots/devs/tutorials              │
│  • Parse CSV logs → filter by date/game/device_id           │
│  • Group events by (device_id, date) — no sessions needed   │
│  • Build per-player game trajectories                       │
│  • Collect broad completion stats (all users)               │
│  • Compute per-puzzle summary statistics                    │
│  • Join PDL features with behaviour metrics                 │
└──────────┬─────────────────────────┬────────────────────────┘
           │                         │
     PDL features            Player trajectories
     196 rows                + date summaries
     49 puzzles              for 7 dated puzzles
           │                         │
           ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  ANALYSIS PHASES                            │
│                                                             │
│  ┌──────────────────┐  ┌──────────────────────────────┐    │
│  │  lib/metrics.py   │  │  lib/model.py                │    │
│  │  10 analyses      │  │  Statistical modelling       │    │
│  │                   │  │                              │    │
│  │  • Crosstabs      │  │  • IPW survivorship          │    │
│  │  • Heatmap        │  │    correction                │    │
│  │  • Correlations   │  │  • Transition probability    │    │
│  │  • Regression     │  │    distributions             │    │
│  │  • Vertical       │  │  • Correlated failure        │    │
│  │    inference       │  │    analysis                  │    │
│  │  • Decoys         │  │  • Monte Carlo game          │    │
│  │  • Relink phase   │  │    simulator                 │    │
│  │  • Clustering     │  │  • Monte Carlo game          │    │
│  │  • Difficulty     │  │    simulator                 │    │
│  │    ratings        │  │                              │    │
│  └────────┬─────────┘  └──────────────┬───────────────┘    │
│           │                            │                    │
│           ▼                            ▼                    │
│  10 JSON data files           5 JSON data files             │
└──────────┬─────────────────────────────┬────────────────────┘
           │                             │
           ▼                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    DASHBOARD                                │
│                    dashboard/                               │
│                                                             │
│  15 JSON files loaded lazily per page                       │
│  → 7 navigable pages with interactive charts                │
│  → Served as static HTML at localhost:8000                  │
└─────────────────────────────────────────────────────────────┘
```

## How To Run

```bash
# Generate all data files (~75s with optimized loading):
python3 relink/scripts/pdl_analysis.py

# Serve the dashboard:
python3 -m http.server 8000 -d relink
# Then open http://localhost:8000
```

## Files Changed By The Pipeline

The pipeline reads from `save-data/` and `raw/` (never modifies them) and writes 15 JSON files to `relink/outputs/data/`. The dashboard reads these JSON files.

## Document Index

| Document | What It Covers |
|----------|---------------|
| [01-data-loading.md](01-data-loading.md) | How raw data is parsed, filtered, grouped by device_id, and shaped into analysis-ready structures |
| [02-analysis-phases.md](02-analysis-phases.md) | The 10 feature analyses (overview through difficulty ratings) — what each measures and why |
| [03-statistical-modelling.md](03-statistical-modelling.md) | IPW correction, transition probabilities, correlated failures |
| [04-simulator.md](04-simulator.md) | The Monte Carlo game simulator — how it predicts puzzle difficulty |
| [05-dashboard.md](05-dashboard.md) | How the interactive dashboard works and what each section shows |

## Key Numbers (Latest Run)

| Metric | Value |
|--------|-------|
| Puzzles with design data | 49 |
| Puzzles with player data | 7 |
| Puzzles without player data (predicted) | 41 |
| Total completions (all users) | ~102K |
| Total device-ID trajectories | ~65K |
| Simulator accuracy (empirical mode) | r = 0.993, MAE = 8.1pp |
| Difficulty rating correlation | Spearman ρ = −0.893 |
