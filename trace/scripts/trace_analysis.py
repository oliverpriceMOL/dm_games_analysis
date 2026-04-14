import csv, ast, sys
from collections import Counter, defaultdict
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRACE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.dirname(TRACE_DIR)
SESSIONS_FILES = [
    os.path.join(DATA_DIR, 'raw', 'daily-mail-sessions.csv'),
    os.path.join(DATA_DIR, 'raw', 'daily-mail-sessions-2.csv'),
]
EVENTS_FILES = [
    os.path.join(DATA_DIR, 'raw', 'daily-mail-events.csv'),
    os.path.join(DATA_DIR, 'raw', 'daily-mail-events-2.csv'),
]
OUTPUT_FILE = os.path.join(TRACE_DIR, 'outputs', 'trace-analysis.txt')

def parse_props(s):
    try:
        return ast.literal_eval(s)
    except:
        return {}

def median(lst):
    if not lst:
        return 0
    s = sorted(lst)
    return s[len(s) // 2]

def pct(n, total):
    if not total:
        return "n/a"
    return f"{n}/{total} ({n/total*100:.0f}%)"

# ========== LOAD DATA ==========

# Load all trace events from both files, deduplicating by event ID
events_by_date = defaultdict(list)
seen_ids = set()
for events_file in EVENTS_FILES:
    if not os.path.exists(events_file):
        continue
    with open(events_file) as f:
        for row in csv.DictReader(f):
            if row['id'] in seen_ids:
                continue
            seen_ids.add(row['id'])
            props = parse_props(row.get('properties', '{}'))
            if props.get('game_id') != 'word-flow':
                continue
            row['_props'] = props
            date = row['created_at'][:10]
            events_by_date[date].append(row)

# Exclude 2026-03-25 (pre-launch test data)
events_by_date.pop('2026-03-25', None)

# Puzzle words (not in the data, manually provided)
PUZZLE_WORDS = {
    '2026-03-26': 'TRACE',
    '2026-03-27': 'LEANING',
    '2026-03-28': 'WHEEL',
    '2026-03-29': 'PARTIAL',
    '2026-03-30': 'UNIQUE',
    '2026-03-31': 'WEEPING',
    '2026-04-01': 'FOOLS',
    '2026-04-02': 'CONQUER',
    '2026-04-03': 'BASKET',
    '2026-04-04': 'CROSS',
    '2026-04-05': 'EASTER',
    '2026-04-06': 'BUNNY',
}

# ========== OUTPUT ==========
out = open(OUTPUT_FILE, 'w')
sys.stdout = out

print("=" * 80)
print("TRACE (WORD-FLOW) ANALYSIS")
print("=" * 80)

all_dates = sorted(events_by_date.keys())
print(f"\nDates covered: {all_dates[0]} to {all_dates[-1]} ({len(all_dates)} days)")

# ========== 1. OVERVIEW PER DAY ==========
print("\n\n" + "=" * 80)
print("1. DAILY OVERVIEW")
print("=" * 80)

print(f"\n  {'Date':<14} {'Events':<10} {'Started':<10} {'Completed':<12} "
      f"{'Completion%':<14} {'Med time':<10} {'Avg time':<10} {'Shared':<8}")
print(f"  {'-'*88}")

daily_completions = {}
for date in all_dates:
    evts = events_by_date[date]
    started = sum(1 for e in evts if e['name'] == 'level_started')
    completed_evts = [e for e in evts if e['name'] == 'level_completed']
    completed = len(completed_evts)
    shared = sum(1 for e in evts if e['name'] == 'level_result_shared')

    times = []
    for e in completed_evts:
        t = e['_props'].get('time_seconds', '')
        try:
            times.append(int(t))
        except:
            pass

    # Filter out extreme outliers (> 1 hour) for stats
    clean_times = [t for t in times if t <= 3600]

    med_t = f"{median(clean_times)}s" if clean_times else "-"
    avg_t = f"{sum(clean_times)//len(clean_times)}s" if clean_times else "-"
    comp_pct = f"{completed}/{started} ({completed/started*100:.0f}%)" if started else "-"

    daily_completions[date] = {
        'started': started,
        'completed': completed,
        'times': clean_times,
        'shared': shared,
    }

    print(f"  {date:<14} {len(evts):<10} {started:<10} {completed:<12} "
          f"{comp_pct:<14} {med_t:<10} {avg_t:<10} {shared:<8}")

# ========== 2. SOLVE TIME DISTRIBUTION ==========
print("\n\n" + "=" * 80)
print("2. SOLVE TIME DISTRIBUTION (per puzzle date)")
print("=" * 80)

# Gather level_completed by puzzle_date
completions_by_puzzle = defaultdict(list)
for date in all_dates:
    for e in events_by_date[date]:
        if e['name'] == 'level_completed':
            pd = e['_props'].get('puzzle_date', date)
            t = e['_props'].get('time_seconds', '')
            try:
                t = int(t)
            except:
                continue
            if t <= 3600:  # exclude outliers
                completions_by_puzzle[pd].append({
                    'time': t,
                    'streak': e['_props'].get('current_streak', '0'),
                    'country': e['country'],
                    'city': e['city'],
                })

for pd in sorted(completions_by_puzzle.keys()):
    comps = completions_by_puzzle[pd]
    times = [c['time'] for c in comps]
    times.sort()
    n = len(times)
    p10 = times[n // 10] if n >= 10 else times[0]
    p25 = times[n // 4] if n >= 4 else times[0]
    p50 = times[n // 2]
    p75 = times[3 * n // 4] if n >= 4 else times[-1]
    p90 = times[9 * n // 10] if n >= 10 else times[-1]

    buckets = Counter()
    for t in times:
        if t <= 15:
            buckets['0-15s'] += 1
        elif t <= 30:
            buckets['16-30s'] += 1
        elif t <= 60:
            buckets['31-60s'] += 1
        elif t <= 120:
            buckets['1-2min'] += 1
        elif t <= 300:
            buckets['2-5min'] += 1
        else:
            buckets['5min+'] += 1

    word = PUZZLE_WORDS.get(pd, '?')
    print(f"\n  Puzzle: {pd} — {word} ({len(word)} letters, n={n})")
    print(f"    Percentiles: 10th={p10}s, 25th={p25}s, 50th={p50}s, 75th={p75}s, 90th={p90}s")
    print(f"    Distribution:")
    for bucket in ['0-15s', '16-30s', '31-60s', '1-2min', '2-5min', '5min+']:
        bc = buckets.get(bucket, 0)
        bar = '#' * (bc * 40 // n) if n else ''
        print(f"      {bucket:<8} {pct(bc, n):<16} {bar}")

# ========== 3. PLAYER RETENTION / STREAKS ==========
print("\n\n" + "=" * 80)
print("3. PLAYER STREAKS")
print("=" * 80)

all_streaks = []
for date in all_dates:
    for e in events_by_date[date]:
        if e['name'] == 'level_completed':
            s = e['_props'].get('current_streak', '0')
            try:
                all_streaks.append(int(s))
            except:
                pass

streak_dist = Counter(all_streaks)
print(f"\n  Streak distribution across all completions (n={len(all_streaks)}):")
for s in sorted(streak_dist.keys()):
    count = streak_dist[s]
    bar = '#' * (count * 40 // len(all_streaks)) if all_streaks else ''
    print(f"    Streak {s}: {pct(count, len(all_streaks))} {bar}")

# ========== 4. TUTORIAL BEHAVIOUR ==========
print("\n\n" + "=" * 80)
print("4. TUTORIAL BEHAVIOUR")
print("=" * 80)

for date in all_dates:
    evts = events_by_date[date]
    tut_started = sum(1 for e in evts if e['name'] == 'tutorial_started')
    tut_completed = sum(1 for e in evts if e['name'] == 'tutorial_completed')
    tut_skipped = sum(1 for e in evts if e['name'] == 'tutorial_skipped')
    sess_started = sum(1 for e in evts if e['name'] == 'session_started')

    print(f"  {date}: {tut_started} started tutorial | "
          f"{tut_completed} completed ({pct(tut_completed, tut_started)}) | "
          f"{tut_skipped} skipped ({pct(tut_skipped, tut_started)}) | "
          f"{sess_started} sessions")

# ========== 5. ABANDONMENT (level_started vs level_completed) ==========
print("\n\n" + "=" * 80)
print("5. ABANDONMENT RATE (event-level)")
print("=" * 80)

print(f"\n  {'Date':<14} {'Sessions':<10} {'Started':<10} {'Completed':<12} {'Drop-off':<14}")
print(f"  {'-'*60}")
for date in all_dates:
    evts = events_by_date[date]
    sessions = sum(1 for e in evts if e['name'] == 'session_started')
    started = sum(1 for e in evts if e['name'] == 'level_started')
    completed = sum(1 for e in evts if e['name'] == 'level_completed')
    dropoff = started - completed
    print(f"  {date:<14} {sessions:<10} {started:<10} {completed:<12} "
          f"{pct(dropoff, started):<14}")

print(f"\n  Note: Drop-off = level_started minus level_completed events.")
print(f"  Some players may start multiple times (refresh), so this is approximate.")

# ========== 6. GEOGRAPHY ==========
print("\n\n" + "=" * 80)
print("6. TOP COUNTRIES & CITIES")
print("=" * 80)

country_completions = Counter()
city_completions = Counter()
country_times = defaultdict(list)

for pd, comps in completions_by_puzzle.items():
    for c in comps:
        country_completions[c['country']] += 1
        city_completions[f"{c['city']}, {c['country']}"] += 1
        country_times[c['country']].append(c['time'])

print(f"\n  Top 20 countries by completions:")
for country, count in country_completions.most_common(20):
    times = country_times[country]
    med = median(times)
    print(f"    {country:<6} {count:>6} completions | median solve: {med}s")

print(f"\n  Top 20 cities by completions:")
for city, count in city_completions.most_common(20):
    print(f"    {city:<35} {count:>5} completions")

# ========== 7. PUZZLE DIFFICULTY COMPARISON ==========
print("\n\n" + "=" * 80)
print("7. PUZZLE DIFFICULTY COMPARISON (by solve time)")
print("=" * 80)

print(f"\n  {'Puzzle date':<14} {'Word':<10} {'Len':<5} {'Players':<10} {'Median':<10} {'Avg':<10} "
      f"{'Under 30s':<14} {'Under 60s':<14} {'Over 2min':<14}")
print(f"  {'-'*101}")
for pd in sorted(completions_by_puzzle.keys()):
    comps = completions_by_puzzle[pd]
    times = sorted([c['time'] for c in comps])
    n = len(times)
    med = median(times)
    avg = sum(times) // n
    under30 = sum(1 for t in times if t <= 30)
    under60 = sum(1 for t in times if t <= 60)
    over2m = sum(1 for t in times if t > 120)
    word = PUZZLE_WORDS.get(pd, '?')
    print(f"  {pd:<14} {word:<10} {len(word):<5} {n:<10} {med:<10} {avg:<10} "
          f"{pct(under30, n):<14} {pct(under60, n):<14} {pct(over2m, n):<14}")

# ========== 8. SOCIAL SHARING ==========
print("\n\n" + "=" * 80)
print("8. SOCIAL SHARING")
print("=" * 80)

total_completions = sum(len(comps) for comps in completions_by_puzzle.values())
total_shares = sum(1 for date in all_dates
                   for e in events_by_date[date]
                   if e['name'] == 'level_result_shared')

print(f"\n  Total shares: {total_shares}")
print(f"  Total completions: {total_completions}")
print(f"  Share rate: {pct(total_shares, total_completions)}")

print(f"\n  Shares by date:")
for date in all_dates:
    shares = sum(1 for e in events_by_date[date] if e['name'] == 'level_result_shared')
    comps = sum(1 for e in events_by_date[date] if e['name'] == 'level_completed')
    print(f"    {date}: {shares} shares / {comps} completions ({pct(shares, comps)})")

# ========== 9. FINAL BOARD VIEWS ==========
print("\n\n" + "=" * 80)
print("9. FINAL BOARD VIEWS (post-solve engagement)")
print("=" * 80)

for date in all_dates:
    evts = events_by_date[date]
    completed = sum(1 for e in evts if e['name'] == 'level_completed')
    board_views = sum(1 for e in evts if e['name'] == 'final_board_viewed')
    print(f"  {date}: {board_views} board views / {completed} completions "
          f"({pct(board_views, completed)})")

# ========== 10. SPEED TIERS ==========
print("\n\n" + "=" * 80)
print("10. SPEED TIERS (across all puzzles)")
print("=" * 80)

all_times = []
for comps in completions_by_puzzle.values():
    all_times.extend(c['time'] for c in comps)

tiers = [
    ('Speed demons', 0, 15),
    ('Fast', 16, 30),
    ('Average', 31, 60),
    ('Steady', 61, 120),
    ('Careful', 121, 300),
    ('Slow', 301, 3600),
]

total = len(all_times)
for label, lo, hi in tiers:
    count = sum(1 for t in all_times if lo <= t <= hi)
    print(f"  {label:<16} ({lo}-{hi}s): {pct(count, total)}")


# ========== 11. WORD LENGTH vs METRICS ==========
print("\n\n" + "=" * 80)
print("11. WORD LENGTH vs METRICS")
print("=" * 80)

print(f"\n  {'Word':<10} {'Letters':<8} {'Median(s)':<10} {'Avg(s)':<8} "
      f"{'Players':<10} {'Drop-off%':<10} {'Share%':<10} {'Board%':<10}")
print(f"  {'-'*76}")

# Gather per-puzzle metrics
word_rows = []
for pd in sorted(PUZZLE_WORDS.keys()):
    word = PUZZLE_WORDS[pd]
    wlen = len(word)
    comps = completions_by_puzzle.get(pd, [])
    times = sorted([c['time'] for c in comps])
    n = len(times)
    if n == 0:
        continue
    med = median(times)
    avg = sum(times) // n

    # Abandonment from events on the puzzle's event date
    started = sum(1 for e in events_by_date.get(pd, []) if e['name'] == 'level_started')
    completed = sum(1 for e in events_by_date.get(pd, []) if e['name'] == 'level_completed')
    dropoff_pct = f"{(started - completed) / started * 100:.0f}%" if started else '-'

    # Shares
    shares = sum(1 for e in events_by_date.get(pd, []) if e['name'] == 'level_result_shared')
    share_pct = f"{shares / completed * 100:.0f}%" if completed else '-'

    # Board views
    boards = sum(1 for e in events_by_date.get(pd, []) if e['name'] == 'final_board_viewed')
    board_pct = f"{boards / completed * 100:.0f}%" if completed else '-'

    word_rows.append((word, wlen, med, avg, n, dropoff_pct, share_pct, board_pct))
    print(f"  {word:<10} {wlen:<8} {med:<10} {avg:<8} "
          f"{n:<10} {dropoff_pct:<10} {share_pct:<10} {board_pct:<10}")

# Sort by word length and show correlation
word_rows.sort(key=lambda r: r[1])  # sort by length
print(f"\n  Sorted by word length:")
print(f"  {'Word':<10} {'Letters':<8} {'Median(s)':<10} {'Avg(s)':<8} "
      f"{'Players':<10} {'Drop-off%':<10} {'Share%':<10} {'Board%':<10}")
print(f"  {'-'*76}")
for word, wlen, med, avg, n, dp, sp, bp in word_rows:
    print(f"  {word:<10} {wlen:<8} {med:<10} {avg:<8} "
          f"{n:<10} {dp:<10} {sp:<10} {bp:<10}")

# Group by length
length_groups = defaultdict(list)
for word, wlen, med, avg, n, dp, sp, bp in word_rows:
    length_groups[wlen].append((word, med, avg, n))

print(f"\n  Summary by word length:")
print(f"  {'Length':<8} {'Words':<20} {'Avg median(s)':<14} {'Total players':<14}")
print(f"  {'-'*56}")
for length in sorted(length_groups.keys()):
    group = length_groups[length]
    words = ', '.join(g[0] for g in group)
    avg_med = sum(g[1] for g in group) // len(group)
    total_players = sum(g[3] for g in group)
    print(f"  {length:<8} {words:<20} {avg_med:<14} {total_players:<14}")


sys.stdout = sys.__stdout__
out.close()
print(f"Output written to {OUTPUT_FILE}")
