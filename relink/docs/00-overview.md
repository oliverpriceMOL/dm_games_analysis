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
│  39 puzzle PDL files  3 session CSVs + 3 event CSVs         │
│  (design tags)        (player behaviour logs)               │
└──────────┬─────────────────────────┬────────────────────────┘
           │                         │
           ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA LOADING                             │
│                    lib/data.py                              │
│                                                             │
│  • Parse 39 puzzle design files → PDL features              │
│  • Parse CSV logs → filter bots/devs/tutorials              │
│  • Match events to sessions                                 │
│  • Build per-player game trajectories                       │
│  • Compute per-puzzle summary statistics                    │
│  • Join PDL features with behaviour metrics                 │
└──────────┬─────────────────────────┬────────────────────────┘
           │                         │
     PDL features            Player trajectories
     156 rows                + date summaries
     39 puzzles              for 14 dated puzzles
           │                         │
           ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  ANALYSIS PHASES                            │
│                                                             │
│  ┌──────────────────┐  ┌──────────────────────────────┐    │
│  │  lib/metrics.py   │  │  lib/model.py                │    │
│  │  9 analyses       │  │  Statistical modelling       │    │
│  │                   │  │                              │    │
│  │  • Crosstabs      │  │  • IPW survivorship          │    │
│  │  • Heatmap        │  │    correction                │    │
│  │  • Correlations   │  │  • Transition probability    │    │
│  │  • Regression     │  │    distributions             │    │
│  │  • Vertical       │  │  • Correlated failure        │    │
│  │    inference       │  │    analysis                  │    │
│  │  • Decoys         │  │  • Monte Carlo game          │    │
│  │  • Relink phase   │  │    simulator                 │    │
│  │  • Clustering     │  │                              │    │
│  └────────┬─────────┘  └──────────────┬───────────────┘    │
│           │                            │                    │
│           ▼                            ▼                    │
│  9 JSON data files            5 JSON data files             │
└──────────┬─────────────────────────────┬────────────────────┘
           │                             │
           ▼                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    DASHBOARD                                │
│                    dashboard/                               │
│                                                             │
│  14 JSON files loaded in parallel                           │
│  → 15 interactive chart sections                            │
│  → Served as static HTML at localhost:8000                  │
└─────────────────────────────────────────────────────────────┘
```

## How To Run

```bash
# Generate all data files (~5-8 minutes, CSV parsing dominates):
python3 relink/scripts/pdl_analysis.py

# Serve the dashboard:
python3 -m http.server 8000 -d relink
# Then open http://localhost:8000
```

## Files Changed By The Pipeline

The pipeline reads from `save-data/` and `raw/` (never modifies them) and writes 13 JSON files to `relink/outputs/data/`. The dashboard reads these JSON files.

## Document Index

| Document | What It Covers |
|----------|---------------|
| [01-data-loading.md](01-data-loading.md) | How raw data is parsed, filtered, matched, and shaped into analysis-ready structures |
| [02-analysis-phases.md](02-analysis-phases.md) | The 8 feature analyses (crosstabs through clustering) — what each measures and why |
| [03-statistical-modelling.md](03-statistical-modelling.md) | IPW correction, transition probabilities, correlated failures |
| [04-simulator.md](04-simulator.md) | The Monte Carlo game simulator — how it predicts puzzle difficulty |
| [05-dashboard.md](05-dashboard.md) | How the interactive dashboard works and what each section shows |

## Key Numbers (Latest Run)

| Metric | Value |
|--------|-------|
| Puzzles with design data | 39 |
| Puzzles with player data | 14 |
| Puzzles without player data | 25 |
| Total player completions analysed | ~496 |
| Simulator accuracy (with player data) | r = 0.934, MAE = 12.7pp |
| Simulator accuracy (design features only) | r = 0.655, MAE = 15.1pp |
