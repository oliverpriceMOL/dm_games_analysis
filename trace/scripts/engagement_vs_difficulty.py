import csv, ast, sys, os
from collections import Counter, defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRACE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.dirname(TRACE_DIR)
EVENTS_FILES = [
    os.path.join(DATA_DIR, 'raw', 'daily-mail-events.csv'),
    os.path.join(DATA_DIR, 'raw', 'daily-mail-events-2.csv'),
]

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

ALL_DATES = sorted(PUZZLE_WORDS.keys())

def median(lst):
    if not lst:
        return 0
    s = sorted(lst)
    return s[len(s) // 2]

def pct(n, total):
    if not total:
        return "n/a"
    return f"{n}/{total} ({n/total*100:.0f}%)"

# Load events
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
            try:
                props = ast.literal_eval(row.get('properties', '{}'))
            except:
                continue
            if props.get('game_id') != 'word-flow':
                continue
            row['_props'] = props
            date = row['created_at'][:10]
            events_by_date[date].append(row)

events_by_date.pop('2026-03-25', None)

# ========== ANALYSIS ==========
print("=" * 90)
print("ENGAGEMENT vs DIFFICULTY — IS EASY = BORING?")
print("=" * 90)

# 1. Solve times by streak level — do experienced players get bored on easy puzzles?
print("\n\n" + "=" * 90)
print("1. SOLVE TIME BY STREAK LEVEL (do veterans blitz easy puzzles?)")
print("=" * 90)
print("\n  Median solve time for players at different streak levels, per puzzle.\n")

# Collect: per puzzle, per streak bucket, list of solve times
streak_buckets = [(1, 1, 'New (str=1)'), (2, 3, 'Str 2-3'), (4, 6, 'Str 4-6'), (7, 99, 'Str 7+')]

print(f"  {'Puzzle':<12} {'Word':<10} {'Med(all)':<10}", end='')
for _, _, label in streak_buckets:
    print(f" {label:<14}", end='')
print()
print(f"  {'-'*70}")

for date in ALL_DATES:
    evts = events_by_date.get(date, [])
    times_by_bucket = defaultdict(list)
    all_times = []
    for e in evts:
        if e['name'] != 'level_completed':
            continue
        try:
            t = int(e['_props'].get('time_seconds', ''))
            s = int(e['_props'].get('current_streak', '0'))
        except:
            continue
        if t > 3600:
            continue
        all_times.append(t)
        for lo, hi, label in streak_buckets:
            if lo <= s <= hi:
                times_by_bucket[label].append(t)
                break

    word = PUZZLE_WORDS.get(date, '?')
    med_all = median(all_times)
    print(f"  {date:<12} {word:<10} {med_all:<10}", end='')
    for _, _, label in streak_buckets:
        bt = times_by_bucket.get(label, [])
        if bt:
            print(f" {median(bt):<4}s (n={len(bt):<4})", end='')
        else:
            print(f" {'—':<14}", end='')
    print()


# 2. Engagement metrics by difficulty tier
print("\n\n" + "=" * 90)
print("2. ENGAGEMENT SIGNALS BY DIFFICULTY")
print("=" * 90)
print("\n  Board view rate and share rate as engagement proxies.\n")

print(f"  {'Puzzle':<12} {'Word':<10} {'Med(s)':<8} {'Tier':<8} {'Board%':<10} {'Share%':<10} "
      f"{'Under15s%':<12} {'Over2min%':<12}")
print(f"  {'-'*82}")

for date in ALL_DATES:
    evts = events_by_date.get(date, [])
    completed = sum(1 for e in evts if e['name'] == 'level_completed')
    boards = sum(1 for e in evts if e['name'] == 'final_board_viewed')
    shares = sum(1 for e in evts if e['name'] == 'level_result_shared')
    times = []
    for e in evts:
        if e['name'] == 'level_completed':
            try:
                t = int(e['_props'].get('time_seconds', ''))
                if t <= 3600:
                    times.append(t)
            except:
                pass
    med = median(times)
    under15 = sum(1 for t in times if t <= 15)
    over2m = sum(1 for t in times if t > 120)
    tier = 'Easy' if med <= 40 else ('Medium' if med <= 70 else 'Hard')
    word = PUZZLE_WORDS.get(date, '?')
    bp = f"{boards/completed*100:.0f}%" if completed else '-'
    sp = f"{shares/completed*100:.1f}%" if completed else '-'
    u15 = f"{under15/len(times)*100:.0f}%" if times else '-'
    o2m = f"{over2m/len(times)*100:.0f}%" if times else '-'
    print(f"  {date:<12} {word:<10} {med:<8} {tier:<8} {bp:<10} {sp:<10} {u15:<12} {o2m:<12}")

# Aggregate by tier
tier_stats = defaultdict(lambda: {'boards': 0, 'shares': 0, 'completed': 0, 'count': 0})
for date in ALL_DATES:
    evts = events_by_date.get(date, [])
    completed = sum(1 for e in evts if e['name'] == 'level_completed')
    boards = sum(1 for e in evts if e['name'] == 'final_board_viewed')
    shares = sum(1 for e in evts if e['name'] == 'level_result_shared')
    times = []
    for e in evts:
        if e['name'] == 'level_completed':
            try:
                t = int(e['_props'].get('time_seconds', ''))
                if t <= 3600:
                    times.append(t)
            except:
                pass
    med = median(times)
    tier = 'Easy' if med <= 40 else ('Medium' if med <= 70 else 'Hard')
    tier_stats[tier]['boards'] += boards
    tier_stats[tier]['shares'] += shares
    tier_stats[tier]['completed'] += completed
    tier_stats[tier]['count'] += 1

print(f"\n  Aggregated by tier:")
print(f"  {'Tier':<10} {'Puzzles':<10} {'Avg board%':<14} {'Avg share%':<14}")
print(f"  {'-'*48}")
for tier in ['Easy', 'Medium', 'Hard']:
    s = tier_stats[tier]
    if s['completed']:
        bp = f"{s['boards']/s['completed']*100:.0f}%"
        sp = f"{s['shares']/s['completed']*100:.1f}%"
    else:
        bp = sp = '-'
    print(f"  {tier:<10} {s['count']:<10} {bp:<14} {sp:<14}")


# 3. The BUNNY problem — is it too easy?
print("\n\n" + "=" * 90)
print("3. THE 'BUNNY PROBLEM' — WHAT HAPPENS WHEN IT'S TOO EASY?")
print("=" * 90)

# BUNNY: 18s median, easiest puzzle. Look at engagement signals.
bunny_evts = events_by_date.get('2026-04-06', [])
bunny_times = []
bunny_streaks = Counter()
for e in bunny_evts:
    if e['name'] == 'level_completed':
        try:
            t = int(e['_props'].get('time_seconds', ''))
            s = int(e['_props'].get('current_streak', '0'))
            if t <= 3600:
                bunny_times.append(t)
                bunny_streaks[s] += 1
        except:
            pass

bunny_completed = len(bunny_times)
bunny_boards = sum(1 for e in bunny_evts if e['name'] == 'final_board_viewed')
bunny_shares = sum(1 for e in bunny_evts if e['name'] == 'level_result_shared')
bunny_under10 = sum(1 for t in bunny_times if t <= 10)
bunny_under15 = sum(1 for t in bunny_times if t <= 15)

print(f"\n  BUNNY (Apr 6): median 18s, easiest puzzle in the dataset")
print(f"  Completions: {bunny_completed}")
print(f"  Under 10s:   {pct(bunny_under10, bunny_completed)}")
print(f"  Under 15s:   {pct(bunny_under15, bunny_completed)}")
print(f"  Board views: {pct(bunny_boards, bunny_completed)}")
print(f"  Shares:      {pct(bunny_shares, bunny_completed)}")

# Veteran solve times on BUNNY
print(f"\n  Veteran players (streak 7+) on BUNNY:")
vet_times = []
for e in bunny_evts:
    if e['name'] == 'level_completed':
        try:
            t = int(e['_props'].get('time_seconds', ''))
            s = int(e['_props'].get('current_streak', '0'))
            if t <= 3600 and s >= 7:
                vet_times.append(t)
        except:
            pass
if vet_times:
    vet_times.sort()
    print(f"    n={len(vet_times)}, median={median(vet_times)}s, "
          f"p10={vet_times[len(vet_times)//10]}s, p90={vet_times[9*len(vet_times)//10]}s")
    vu10 = sum(1 for t in vet_times if t <= 10)
    print(f"    Under 10s: {pct(vu10, len(vet_times))}")


# 4. Consecutive easy days — does engagement trend down?
print("\n\n" + "=" * 90)
print("4. CONSECUTIVE EASY DAYS — ENGAGEMENT TREND")
print("=" * 90)
print("\n  Apr 3-6 had 4 consecutive easy/medium puzzles (BASKET 46s, CROSS 30s, EASTER 33s, BUNNY 18s).")
print("  Is engagement declining across this streak?\n")

run_dates = ['2026-04-03', '2026-04-04', '2026-04-05', '2026-04-06']
print(f"  {'Date':<14} {'Word':<10} {'Med(s)':<8} {'Comps':<8} {'Board%':<10} {'Share%':<10} "
      f"{'Str2+%':<10} {'Str7+%':<10}")
print(f"  {'-'*80}")

for date in run_dates:
    evts = events_by_date.get(date, [])
    completed = sum(1 for e in evts if e['name'] == 'level_completed')
    boards = sum(1 for e in evts if e['name'] == 'final_board_viewed')
    shares = sum(1 for e in evts if e['name'] == 'level_result_shared')
    times = []
    streaks = Counter()
    for e in evts:
        if e['name'] == 'level_completed':
            try:
                t = int(e['_props'].get('time_seconds', ''))
                s = int(e['_props'].get('current_streak', '0'))
                if t <= 3600:
                    times.append(t)
                    streaks[s] += 1
            except:
                pass
    total_s = sum(streaks.values())
    s2p = sum(c for s, c in streaks.items() if s >= 2)
    s7p = sum(c for s, c in streaks.items() if s >= 7)
    word = PUZZLE_WORDS.get(date, '?')
    med = median(times)
    print(f"  {date:<14} {word:<10} {med:<8} {completed:<8} "
          f"{boards/completed*100:.0f}%       {shares/completed*100:.1f}%       "
          f"{s2p/total_s*100:.0f}%       {s7p/total_s*100:.0f}%")

# 5. Does difficulty add "satisfaction" — shares on hard vs easy?
print("\n\n" + "=" * 90)
print("5. SHARE RATE BY SOLVE TIME BRACKET")
print("=" * 90)
print("\n  Do players who took longer share more (pride in solving a hard one)?\n")

# Across all puzzles, bucket completions by solve time, count shares nearby
# We can't directly link a share to a completion, but we can look at per-puzzle
# share rate vs difficulty
print(f"  This is approximated at the puzzle level (not individual).")
print(f"  Puzzle-level correlation between median solve time and share rate:\n")

puzzle_data = []
for date in ALL_DATES:
    evts = events_by_date.get(date, [])
    completed = sum(1 for e in evts if e['name'] == 'level_completed')
    shares = sum(1 for e in evts if e['name'] == 'level_result_shared')
    times = []
    for e in evts:
        if e['name'] == 'level_completed':
            try:
                t = int(e['_props'].get('time_seconds', ''))
                if t <= 3600:
                    times.append(t)
            except:
                pass
    if times and completed:
        med = median(times)
        sr = shares / completed * 100
        word = PUZZLE_WORDS.get(date, '?')
        puzzle_data.append((med, sr, word, shares, completed))

puzzle_data.sort()
for med, sr, word, shares, completed in puzzle_data:
    bar = '#' * int(sr * 20)
    print(f"  {word:<10} med={med:>4}s  share={sr:.1f}% ({shares}/{completed})  {bar}")

# Correlation
meds = [d[0] for d in puzzle_data]
srs = [d[1] for d in puzzle_data]
n = len(meds)
mean_m = sum(meds) / n
mean_s = sum(srs) / n
cov = sum((m - mean_m) * (s - mean_s) for m, s in zip(meds, srs)) / n
std_m = (sum((m - mean_m)**2 for m in meds) / n) ** 0.5
std_s = (sum((s - mean_s)**2 for s in srs) / n) ** 0.5
corr = cov / (std_m * std_s) if std_m * std_s else 0
print(f"\n  Pearson correlation (median time vs share rate): r = {corr:.2f}")
