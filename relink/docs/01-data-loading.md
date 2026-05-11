# 01 — Data Loading

> **File:** `relink/scripts/lib/data.py`
> **Called by:** `pdl_analysis.py` as the first step
> **Time:** ~1–2 minutes (CSV I/O dominates; parsing is deferred)

## What Happens

Data loading takes raw files (puzzle designs + player logs) and produces clean, analysis-ready data structures. There are two independent input streams that get joined together.

```
┌──────────────┐     ┌──────────────────────────────────────────────┐
│  save-data/  │     │  raw/                                        │
│  49 JSON     │     │  CSV files (sessions + events, 933MB+174MB)  │
│  puzzle      │     │                                              │
│  designs     │     │                                              │
└──────┬───────┘     └────────────────────┬────────────────────────┘
       │                                  │
       ▼                                  ▼
  load_pdl()                    load_behaviour(target_dates)
       │                                  │
       │  ┌───────────────────────────────┘
       │  │  3-gate filter:                   
       │  │    1. Date slice ∈ target_dates   
       │  │    2. 'relink' substring check    
       │  │    3. "'game_id':'relink'" check   
       │  │  Deferred: ast.literal_eval        
       │  │  Extracted: _ts, _level_id (string)
       │  │                                  
       │  ├── match_events()  [binary search]
       │  ├── build_players() [lazy parse here]
       │  ├── canonical ID filter             
       │  ├── build_date_summaries()
       │  └── build_aggregate_timing()
       │                      │
       ▼                      ▼
  PDL structures         Behaviour structures
       │                      │
       └──────────┬───────────┘
                  │
                  ▼
            Joined data
         (PDL + behaviour)
```

---

## Stream 1: Puzzle Design (PDL)

### Source Files

- `save-data/puzzles-index.json` — master list of all 39 puzzles with `id`, `date`, `name`
- `save-data/l{id}.json` — one file per puzzle with the full design

### What `load_pdl()` Produces

**Six return values:**

| Structure | Shape | Description |
|-----------|-------|-------------|
| `pdl_puzzles` | dict of 49 entries | Raw puzzle data keyed by level ID (`l1`, `l2`, etc.) |
| `pdl_rows` | list of ~196 dicts | One entry per row across all puzzles (49 puzzles × 4 rows) |
| `pdl_puzzle_features` | dict of 49 entries | Computed board-level features per puzzle |
| `level_to_date` | dict | Maps level ID → puzzle date (e.g. `l11` → `2026-05-07`) |
| `date_to_level` | dict | Reverse mapping: date → level ID |
| `canonical_ids` | dict | Maps date → canonical level_id string (for filtering glitch data) |

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

Three pairs of CSVs (original + three subsequent exports covering overlapping date ranges):

- `daily-mail-sessions.csv`, `-2.csv`, `-3.csv`, `-4.csv` — session-level data
- `daily-mail-events.csv`, `-2.csv`, `-3.csv`, `-4.csv` — event-level data

### Performance-Optimised Loading

The raw CSVs can be very large (933MB events, 174MB sessions, 4M+ rows total). Loading uses a three-gate filter pipeline that avoids expensive `ast.literal_eval()` parsing during the scan:

```
For events:
  1. glob.glob() finds all matching CSV files
  2. For each row (via csv.DictReader):
     Gate 1: row['created_at'][:10] ∈ target_dates?     ← string slice + set lookup
     Gate 2: 'relink' in row['properties']?             ← substring check
     Gate 3: "'game_id':'relink'" in row['properties']? ← exact string match
  3. If all gates pass: extract _ts (timestamp) and _level_id (string slicing)
  4. Store raw properties string — NO ast.literal_eval() yet
  5. Deduplicate by event ID (last file wins)

For sessions:
  1. Only scan dates that had relink events (from step above)
  2. Same 'relink' substring gate on properties
  3. Apply bot/dev filters on duration and city
```

**Key insight — deferred parsing:** The expensive `ast.literal_eval()` call is deferred to `build_players()` and only runs on the subset of events that were successfully matched to sessions (~thousands, not millions). The `_level_id` field is extracted via string find + slice on the raw properties string, avoiding full parsing.

**`target_dates` parameter:** Passed from `load_all()` as `set(date_to_level.keys())` — the set of all dated puzzle dates from save-data. This excludes pre-launch test data and non-puzzle dates, typically eliminating 50-60% of rows at Gate 1.

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
Clean events (~900+ completions across 17 dated puzzles)
```

### Event-Session Matching (`match_events`)

Events and sessions are separate tables. Matching links each event to its session:

```
Problem: events have (country, timestamp) but no session_id
         sessions have (country, created_at, ended_at)

Solution (binary search):
  1. Group events by country, sort each bucket by timestamp
  2. Build parallel timestamp list per country (for bisect)
  3. For each session:
     a. bisect_left(ts_list, session_start - 200ms) → lo
     b. bisect_right(ts_list, session_end + 200ms) → hi
     c. Only check city match on events[lo:hi]
  4. Complexity: O(sessions × log(events_per_country) + matches)
     vs. previous O(sessions × events_per_country)
```

With 59K sessions and 1.3M events across 5 dates, binary search reduces matching from minutes to seconds.

### Building Player Trajectories (`build_players`)

This is the most complex step. For each puzzle date, it constructs a per-player game state history.

**Lazy property parsing:** At the start of processing each player's events, `ast.literal_eval()` is called on any events that still have raw (unparsed) properties. This deferred approach means only matched events (~thousands) get the expensive parse, not all 1.3M loaded events.

```
For each player (identified by session ID):
  1. Lazy-parse event properties (deferred from loading)
  2. Collect all their guess events, sorted by timestamp
  3. Walk through guesses chronologically:
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

### Canonical ID Filtering

After `build_players()`, an optional filter removes players who played the wrong puzzle on a given date (e.g. glitch data from early-morning server switches):

```
For each date with a canonical_id (from puzzle JSON's "canonicalId" field):
  Keep only players whose level_id matches the expected canonical
  Log how many were removed
```

The `level_id` is extracted from event properties during loading (via string slicing, not full parsing) and stored on each player record. The `canonical_ids` mapping comes from `load_pdl()` which reads the `"canonicalId"` field from each puzzle JSON.

---

## Summary

The data loading step transforms:

- **49 JSON puzzle files** → 196 rows with PDL tags + 49 puzzle feature vectors + canonical IDs
- **CSV files (933MB+174MB, 4M+ rows)** → ~50K filtered player sessions → per-player trajectories → per-puzzle summaries
- **Join** → rows and puzzles with both design features and observed difficulty metrics

### Performance

| Phase | Time | What Dominates |
|-------|------|----------------|
| CSV scan (events) | ~30s | Raw I/O of 933MB, string comparisons |
| CSV scan (sessions) | ~5s | Smaller file, date+relink gates |
| Event-session matching | ~10s | Binary search per session |
| build_players (incl. lazy parse) | ~15s | ast.literal_eval on matched events |
| Analysis phases | ~15s | Simulator Monte Carlo |
| **Total** | **~75s** | |

The three-gate filter eliminates ~97% of event rows before any expensive processing. The date gate alone skips ~50% by string slice, the 'relink' gate skips ~65% of the remainder, and deferred parsing means `ast.literal_eval` only runs on ~0.1% of original rows.

Everything downstream — the 15 analyses, the statistical models, and the simulator — operates on these joined structures.
