# 01 — Data Loading

> **File:** `relink/scripts/lib/data.py`
> **Called by:** `pdl_analysis.py` as the first step
> **Time:** ~3–5 minutes (CSV parsing with `ast.literal_eval` dominates)

## What Happens

Data loading takes raw files (puzzle designs + player logs) and produces clean, analysis-ready data structures. There are two independent input streams that get joined together.

```
┌──────────────┐     ┌──────────────────┐
│  save-data/  │     │  raw/            │
│  39 JSON     │     │  6 CSV files     │
│  puzzle      │     │  (sessions +     │
│  designs     │     │   events)        │
└──────┬───────┘     └────────┬─────────┘
       │                      │
       ▼                      ▼
  load_pdl()            load_behaviour()
       │                      │
       │                      ├── match_events()
       │                      ├── build_players()
       │                      ├── build_date_summaries()
       │                      └── build_aggregate_timing()
       │                      │
       ▼                      ▼
  PDL structures         Behaviour structures
       │                      │
       └──────────┬───────────┘
                  │
                  ▼
            Joined data
         (PDL + behaviour
          for 14 puzzles)
```

---

## Stream 1: Puzzle Design (PDL)

### Source Files

- `save-data/puzzles-index.json` — master list of all 39 puzzles with `id`, `date`, `name`
- `save-data/l{id}.json` — one file per puzzle with the full design

### What `load_pdl()` Produces

**Five return values:**

| Structure | Shape | Description |
|-----------|-------|-------------|
| `pdl_puzzles` | dict of 39 entries | Raw puzzle data keyed by level ID (`l1`, `l2`, etc.) |
| `pdl_rows` | list of ~156 dicts | One entry per row across all puzzles (39 puzzles × 4 rows) |
| `pdl_puzzle_features` | dict of 39 entries | Computed board-level features per puzzle |
| `level_to_date` | dict | Maps level ID → puzzle date (e.g. `l11` → `2026-03-31`) |
| `date_to_level` | dict | Reverse mapping: date → level ID |

### Row-Level PDL (`pdl_rows`)

Each entry in `pdl_rows` represents one row in one puzzle:

```
{
  'lid': 'l11',                        # which puzzle
  'row_position': 0,                   # grid row (0-3)
  'category': 'Newspaper sections',    # the row's connection name
  'manipulation': 'None',              # how the connection is encoded
  'abstraction': 'Direct membership',  # how abstract the grouping is
  'knowledge': 'General vocabulary',   # knowledge required
  'knowledgeDomain': 'Language',       # topic domain
  'impostor_domain': 'Language',       # the impostor's true domain
  'same_domain': True,                 # does impostor match row domain?
  'tile_ids': ['r0w0','r0w1',...],     # tile identifiers (for decoy matching)
  'date': '2026-03-31',               # puzzle date (empty for undated)
}
```

**How PDL tags are extracted:** Each row in the puzzle JSON has a `pdl.group` object with arrays for `manipulation`, `abstraction`, `knowledge`, and `knowledgeDomain`. The code takes the first element of each array (or a default if missing):

```python
manip = rpdl.get('manipulation', ['None'])[0]
abstr = rpdl.get('abstraction', ['Direct membership'])[0]
know  = rpdl.get('knowledge', ['General vocabulary'])[0]
```

### Puzzle-Level Features (`pdl_puzzle_features`)

These are **computed** from the row-level tags — they summarise the whole puzzle:

| Feature | How It's Computed | Example |
|---------|-------------------|---------|
| `manipulationComplexity` | Count of rows where manipulation ≠ 'None' | 2 (two rows have word tricks) |
| `abstractionComplexity` | Count of rows where abstraction ≠ 'Direct membership' | 1 (one row uses shared property) |
| `knowledgeBreadth` | Count of distinct knowledge domains across all rows | 3 (Language, Science, Entertainment) |
| `phase2TileCount` | From puzzle's `board.phase2TileCount` | 2 (relink answer needs 2 tiles) |
| `decoyCount` | Number of designed decoy groupings | 1 |
| `specialistGroupCount` | From puzzle's `board.specialistGroupCount` | 0 |
| `hasSpecialist` | Is 'Specialist cultural' present in any row? | False |
| `isThemed` | From puzzle's `board.isThemed` | True |

### Relink-Level Features

The relink (phase 2) has its own PDL tags, split into two concerns:

**Connection Identification** — how the hidden link between impostors is encoded:

| Field | Source | Example Values |
|-------|--------|----------------|
| `relink_id_manipulation` | `relink.pdl.connectionIdentification.manipulation` | None, Hidden word |
| `relink_id_knowledge` | `relink.pdl.connectionIdentification.knowledge` | General vocabulary |
| `relink_id_abstraction` | `relink.pdl.connectionIdentification.abstraction` | Direct membership |
| `relink_id_domain` | `relink.pdl.connectionIdentification.knowledgeDomain` | General |

**Answer Construction** — how tiles combine to form the answer:

| Field | Source | Example Values |
|-------|--------|----------------|
| `relink_con_manipulation` | `relink.pdl.answerConstruction.manipulation` | None, Compound, Word split, Phrase |
| `relink_con_knowledge` | `relink.pdl.answerConstruction.knowledge` | None, Common cultural, General vocabulary |

---

## Stream 2: Player Behaviour

### Source Files

Three pairs of CSVs (original + two subsequent exports covering overlapping date ranges):

- `daily-mail-sessions.csv`, `-2.csv`, `-3.csv` — session-level data
- `daily-mail-events.csv`, `-2.csv`, `-3.csv` — event-level data

### Multi-File Loading

```
For each pattern (sessions, events):
  1. glob.glob() finds all matching files
  2. Sort alphabetically (determines load order)
  3. Load each file with csv.DictReader
  4. Parse the 'properties' column with ast.literal_eval()
  5. Store in dict keyed by row ID
  6. Last file wins (deduplication)
```

This ensures full date coverage without duplicates — if a row appears in both `events.csv` and `events-2.csv`, the version from `-2` is kept.

### Filtering

Four filters remove non-player traffic:

```
Raw events
    │
    ├── Bot filter: (country in NL/IE and duration ≤ 10s) or duration ≤ 2s
    ├── Dev filter: sessions from Västerås, SE
    ├── Tutorial filter: attempts_remaining > 4 (tutorial gives 999 lives)
    └── Tester filter: INCOMPLETE outcomes with 0 wrong guesses
    │
    ▼
Clean events (~496 completions across 14 dated puzzles)
```

### Event-Session Matching (`match_events`)

Events and sessions are separate tables. Matching links each event to its session:

```
Problem: events have (country, timestamp) but no session_id
         sessions have (country, created_at, ended_at)

Solution:
  1. Bucket sessions by (country, date) for O(1) lookup
  2. For each event, find sessions in the same (country, date) bucket
  3. Match if event.timestamp falls within session window (±200ms tolerance)
  4. This avoids O(n×m) comparison across all events × all sessions
```

### Building Player Trajectories (`build_players`)

This is the most complex step. For each puzzle date, it constructs a per-player game state history:

```
For each player (identified by session ID):
  1. Collect all their guess events, sorted by timestamp
  2. Walk through guesses chronologically:
     - Track which row they're guessing on
     - Track lives remaining (start at 4)
     - Record correct guesses (impostor found) and wrong guesses
  3. Build trajectory: list of dictionaries, one per row solved:
     {
       'position': 0,          # which position in solve order (0=first solved)
       'lives_before': 4,      # lives when starting this row
       'row': '2',             # grid row index
       'wrong_count': 1,       # wrongs before finding impostor
       'survived': True,       # did they have lives left after?
     }
  4. Build relink trajectory (if player reached phase 2):
     {
       'lives_before': 3,
       'wrong_count': 0,
       'survived': True,
     }
  5. Determine outcome: WON, LOST, or INCOMPLETE
```

**Key insight — inter-solve counting:** Players can switch between rows freely. If a player guesses wrong on row 2, then switches to row 1 and solves it, then goes back and solves row 2, the trajectory records:

- Position 0 (first solve): row 1, 0 wrongs (they got it first try)
- Position 1 (second solve): row 2, including the earlier wrong guess

This means `wrong_count` captures all wrongs between consecutive solves, not just wrongs on the specific row.

### Date Summaries (`build_date_summaries`)

For each puzzle date, aggregates player-level data into puzzle-level statistics:

```
{
  'date': '2026-03-31',
  'label': 'Mar 31',
  'name': 'Newspaper sections',
  'lid': 'l11',
  'n_players': 34,
  'n_won': 28,
  'n_lost': 6,
  'solve_rate': 0.824,
  'row_stats': {
    '0': {'first_try_pct': 0.912, 'avg_wrong': 0.088, 'n': 34, ...},
    '1': {'first_try_pct': 0.758, 'avg_wrong': 0.242, 'n': 33, ...},
    ...
  },
  'relink_stats': {'first_try_pct': 0.857, 'avg_wrong': 0.143, ...},
  'inter_correct_intervals': [(0, 16.5), (1, 12.3), ...],  # (position, seconds)
  'timing_percentiles': {'p25': 45, 'p50': 62, 'p75': 89},
}
```

### Aggregate Timing (`build_aggregate_timing`)

Pools timing data across all puzzle dates for the vertical inference analysis:

```
{
  0: {'median': 16.6, 'n': 528},  # position 0: median 16.6 seconds
  1: {'median': 14.0, 'n': 482},  # position 1: players speeding up
  2: {'median': 11.7, 'n': 418},
  3: {'median': 10.6, 'n': 338},
}
```

---

## The Join

After loading both streams, `pdl_analysis.py` joins them:

### Row-Level Join (`row_joined`)

Combines PDL row data with observed player behaviour for that row:

```python
row_joined = []
for each pdl_row that has a matching date in date_summaries:
    row_data = pdl_row.copy()
    row_data['first_try_pct'] = date_summaries[date]['row_stats'][row]['first_try_pct']
    row_data['avg_wrong'] = ...
    row_data['never_correct_pct'] = ...
    row_data['solve_rate'] = ...
    row_joined.append(row_data)
```

Result: ~56 rows (14 dated puzzles × 4 rows) with both PDL tags and player metrics.

### Puzzle-Level Data (`puzzle_data`)

Used by correlations and regression — one row per dated puzzle with summary stats.

---

## Summary

The data loading step transforms:

- **39 JSON puzzle files** → 156 rows with PDL tags + 39 puzzle feature vectors
- **6 CSV files** → ~496 filtered player completions → per-player trajectories → per-puzzle summaries
- **Join** → 56 rows and 14 puzzles with both design features and observed difficulty metrics

Everything downstream — the 8 analyses, the statistical models, and the simulator — operates on these joined structures.
