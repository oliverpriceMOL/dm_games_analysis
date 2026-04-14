# Trace — Analysis

## The Game

Trace is a word-tracing puzzle. Players trace a path through a grid of letters to spell a hidden word. There is no win/lose — all completions are wins. The key metric is **solve time**.

A new puzzle is available each day with a single target word.

## Data

- **Period**: Mar 26 – Apr 6, 2026 (12 puzzle dates; Mar 25 excluded as pre-launch test)
- **Total completions**: ~74,000
- **Daily volume**: ~3,000–10,000 completions/day
- **Player base**: 76% GB; City of London leads individual cities

### Puzzle Words

| Date | Word | Letters |
|------|------|---------|
| Mar 26 | TRACE | 5 |
| Mar 27 | LEANING | 7 |
| Mar 28 | WHEEL | 5 |
| Mar 29 | PARTIAL | 7 |
| Mar 30 | UNIQUE | 6 |
| Mar 31 | WEEPING | 7 |
| Apr 1 | FOOLS | 5 |
| Apr 2 | BUNNY | 5 |
| Apr 3 | REFRESH | 7 |
| Apr 4 | BREEZE | 6 |
| Apr 5 | RIPPLE | 6 |
| Apr 6 | ECLIPSE | 7 |

### Event Types

| Event | Key Properties |
|-------|---------------|
| `level_completed` | `time_seconds`, `current_streak`, `puzzle_date`, `is_archive`, `next_puzzle_available` |
| `level_started` | `puzzle_date` |
| `tutorial_started` / `tutorial_completed` / `tutorial_skipped` | — |
| `level_result_shared` | — |
| `final_board_viewed` | — |
| `session_started` | — |

## Scripts

| Script | Output | Description |
|--------|--------|-------------|
| `trace_analysis.py` | `trace-analysis.txt` | Comprehensive 11-section analysis: daily overview, solve times, streaks, tutorials, abandonment, geography, difficulty, sharing, engagement |
| `retention_analysis.py` | `retention-analysis.txt` | Player retention across dates: streak cohorts, day-over-day return rates, hard vs easy puzzle impact |
| `plot_solve_time.py` | `solve-time-by-length.html` | Interactive HTML chart of solve time distributions grouped by word length |
| `solve_rate_by_length.py` | stdout | Simple solve rate summary table by puzzle and word length |
| `engagement_vs_difficulty.py` | stdout | Solve time patterns by player experience (streak level) |
| `_check_fingerprint.py` | — | Utility for inspecting player fingerprint/identity fields |

## Key Findings

### Difficulty

- **Word length is the dominant difficulty factor**: 7-letter words take ~3× longer than 5-letter (median 104s vs 35s)
- Solve rates remain high across all lengths: 5-letter ~88%, 6-letter ~88%, 7-letter ~80%
- Easiest puzzle: **BUNNY** (5 letters) — 18s median, 91% solved under 60s
- Hardest puzzle: **LEANING** (7 letters) — 164s median, 67% took over 2 minutes

### Player Speed Tiers

| Tier | Time Range | % of Players |
|------|-----------|-------------|
| Speed demons | 0–15s | 11% |
| Fast | 16–30s | 24% |
| Average | 31–60s | 25% |
| Steady | 1–2 min | 21% |
| Careful | 2–5 min | 17% |
| Slow | 5+ min | 3% |

### Retention

- **Player base matures quickly**: Day 1 was 100% new players; by day 12 only 49% new
- **Hard puzzles hurt retention**: 41% next-day return after hard puzzles vs 53% after easy (+12pp difference)
- **New → returning conversion is low** (~30%), but returning players are sticky (60%+ multi-day survival)
- Day-of drop-off does **not** predict next-day volume loss

### Engagement

- **Sharing rate**: flat at ~1% across all days and difficulties
- **Final board views**: declined from 52% (day 1) to 31% (day 12) — post-solve engagement fading
- **Tutorial**: ~50–60% completion rate, ~35–40% skip rate
- **Abandonment**: ranges 6–29% depending on puzzle difficulty
