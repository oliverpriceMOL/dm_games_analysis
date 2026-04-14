import csv, ast, sys, os
from collections import Counter, defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRACE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.dirname(TRACE_DIR)
EVENTS_FILES = [
    os.path.join(DATA_DIR, 'raw', 'daily-mail-events.csv'),
    os.path.join(DATA_DIR, 'raw', 'daily-mail-events-2.csv'),
]
OUTPUT_FILE = os.path.join(TRACE_DIR, 'outputs', 'retention-analysis.txt')

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

# ========== LOAD DATA ==========
# We have no explicit user ID, but we can use current_streak on level_completed
# events as a retention proxy. We also have days_since_first_visit on session_started.
#
# Strategy: Use the streak distribution per puzzle_date to understand:
# 1. What % of completers on each day are returning players (streak >= 2)?
# 2. After a hard/easy puzzle, does the next day's returning player count change?
# 3. Use session_started events with days_since_first_visit for cohort analysis.

# Load all trace events, deduplicating
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

# Exclude pre-launch
events_by_date.pop('2026-03-25', None)

# ========== OUTPUT ==========
out = open(OUTPUT_FILE, 'w')
sys.stdout = out

print("=" * 90)
print("TRACE — RETENTION & STREAK ANALYSIS")
print("=" * 90)

# ========== 1. STREAK DISTRIBUTION PER PUZZLE ==========
print("\n\n" + "=" * 90)
print("1. STREAK DISTRIBUTION PER PUZZLE DATE")
print("=" * 90)
print("\n  Shows current_streak on level_completed events. Streak 1 = first/only play,")
print("  streak 2+ = consecutive-day returnees.\n")

streak_data = {}  # date -> {streak: count}
for date in ALL_DATES:
    evts = events_by_date.get(date, [])
    streaks = Counter()
    for e in evts:
        if e['name'] == 'level_completed':
            s = e['_props'].get('current_streak', '0')
            try:
                streaks[int(s)] += 1
            except:
                pass
    streak_data[date] = streaks

print(f"  {'Date':<14} {'Word':<10} {'Total':<8} {'Streak=1':<14} {'Str 2+':<14} "
      f"{'Str 3+':<14} {'Str 5+':<14} {'Str 7+':<14}")
print(f"  {'-'*88}")

for date in ALL_DATES:
    dist = streak_data[date]
    total = sum(dist.values())
    if total == 0:
        continue
    s1 = dist.get(1, 0)
    s2p = sum(c for s, c in dist.items() if s >= 2)
    s3p = sum(c for s, c in dist.items() if s >= 3)
    s5p = sum(c for s, c in dist.items() if s >= 5)
    s7p = sum(c for s, c in dist.items() if s >= 7)
    word = PUZZLE_WORDS.get(date, '?')
    print(f"  {date:<14} {word:<10} {total:<8} {pct(s1, total):<14} {pct(s2p, total):<14} "
          f"{pct(s3p, total):<14} {pct(s5p, total):<14} {pct(s7p, total):<14}")


# ========== 2. DAY-OVER-DAY RETENTION FLOW ==========
print("\n\n" + "=" * 90)
print("2. DAY-OVER-DAY COMPLETION FLOW")
print("=" * 90)
print("\n  Compares completions on consecutive days. 'Streak 2+' on day N+1 tells us")
print("  how many day-N+1 completers also played the previous day.\n")

print(f"  {'Day N':<14} {'Word':<10} {'Med(s)':<8} {'D(N) comps':<12} {'D(N+1) comps':<14} "
      f"{'D(N+1) str2+':<14} {'Return %':<10}")
print(f"  {'-'*82}")

for i in range(len(ALL_DATES) - 1):
    d0 = ALL_DATES[i]
    d1 = ALL_DATES[i + 1]
    dist0 = streak_data[d0]
    dist1 = streak_data[d1]
    total0 = sum(dist0.values())
    total1 = sum(dist1.values())
    s2p_1 = sum(c for s, c in dist1.items() if s >= 2)

    # Median solve time for d0
    times0 = []
    for e in events_by_date.get(d0, []):
        if e['name'] == 'level_completed':
            try:
                t = int(e['_props'].get('time_seconds', ''))
                if t <= 3600:
                    times0.append(t)
            except:
                pass
    med0 = median(times0)

    word0 = PUZZLE_WORDS.get(d0, '?')
    # Return % = streak2+ on D(N+1) / completions on D(N)
    ret_pct = f"{s2p_1/total0*100:.0f}%" if total0 else '-'
    print(f"  {d0:<14} {word0:<10} {med0:<8} {total0:<12} {total1:<14} "
          f"{pct(s2p_1, total1):<14} {ret_pct:<10}")


# ========== 3. HARD PUZZLE IMPACT ON NEXT-DAY RETURNS ==========
print("\n\n" + "=" * 90)
print("3. DOES A HARD PUZZLE REDUCE NEXT-DAY RETURNS?")
print("=" * 90)
print("\n  We compare: after an easy day (median <= 40s) vs after a hard day (median >= 80s),")
print("  what fraction of next-day completers are returning (streak >= 2)?\n")

easy_next = []
hard_next = []
for i in range(len(ALL_DATES) - 1):
    d0 = ALL_DATES[i]
    d1 = ALL_DATES[i + 1]
    times0 = []
    for e in events_by_date.get(d0, []):
        if e['name'] == 'level_completed':
            try:
                t = int(e['_props'].get('time_seconds', ''))
                if t <= 3600:
                    times0.append(t)
            except:
                pass
    med0 = median(times0)
    dist1 = streak_data[d1]
    total1 = sum(dist1.values())
    s2p_1 = sum(c for s, c in dist1.items() if s >= 2)
    ret_rate = s2p_1 / total1 if total1 else 0

    word0 = PUZZLE_WORDS.get(d0, '?')
    if med0 <= 40:
        easy_next.append((d0, word0, med0, total1, s2p_1, ret_rate))
    elif med0 >= 80:
        hard_next.append((d0, word0, med0, total1, s2p_1, ret_rate))

print(f"  After EASY puzzles (median <= 40s):")
for d, w, med, tot, ret, rate in easy_next:
    print(f"    {d} {w:<10} (med {med}s) -> next day: {pct(ret, tot)} returning ({rate*100:.0f}%)")
if easy_next:
    avg_easy = sum(r[5] for r in easy_next) / len(easy_next)
    print(f"    Average next-day return rate: {avg_easy*100:.0f}%")

print(f"\n  After HARD puzzles (median >= 80s):")
for d, w, med, tot, ret, rate in hard_next:
    print(f"    {d} {w:<10} (med {med}s) -> next day: {pct(ret, tot)} returning ({rate*100:.0f}%)")
if hard_next:
    avg_hard = sum(r[5] for r in hard_next) / len(hard_next)
    print(f"    Average next-day return rate: {avg_hard*100:.0f}%")

if easy_next and hard_next:
    diff = avg_easy - avg_hard
    print(f"\n  Difference: {diff*100:+.0f}pp (easy - hard)")


# ========== 4. ABANDONMENT IMPACT ON NEXT-DAY ==========
print("\n\n" + "=" * 90)
print("4. DOES ABANDONMENT ON DAY N PREDICT LOWER DAY N+1 VOLUME?")
print("=" * 90)
print("\n  'Drop-off %' = (started - completed) / started on day N.")
print("  We check if high drop-off days are followed by lower player counts.\n")

print(f"  {'Day N':<14} {'Word':<10} {'Drop-off%':<12} {'D(N) starts':<14} {'D(N+1) starts':<14} {'Change':<10}")
print(f"  {'-'*74}")

for i in range(len(ALL_DATES) - 1):
    d0 = ALL_DATES[i]
    d1 = ALL_DATES[i + 1]
    started0 = sum(1 for e in events_by_date.get(d0, []) if e['name'] == 'level_started')
    completed0 = sum(1 for e in events_by_date.get(d0, []) if e['name'] == 'level_completed')
    started1 = sum(1 for e in events_by_date.get(d1, []) if e['name'] == 'level_started')
    dropoff = (started0 - completed0) / started0 * 100 if started0 else 0
    change = (started1 - started0) / started0 * 100 if started0 else 0
    word0 = PUZZLE_WORDS.get(d0, '?')
    print(f"  {d0:<14} {word0:<10} {dropoff:>6.0f}%      {started0:<14} {started1:<14} {change:>+6.0f}%")


# ========== 5. STREAK COHORT SURVIVAL ==========
print("\n\n" + "=" * 90)
print("5. STREAK COHORT SURVIVAL")
print("=" * 90)
print("\n  Of players who had streak=N on a given day, what % reached streak=N+1 the next day?")
print("  (Approximated by comparing streak counts across consecutive days.)\n")

# For each consecutive pair of days, estimate: of those with streak=k on day N,
# how many appear as streak=k+1 on day N+1?
# This is approximate since we can't track individuals, but the streak counter
# should increment if they play the next day.
survival_by_streak = defaultdict(list)  # streak_k -> list of survival rates

for i in range(len(ALL_DATES) - 1):
    d0 = ALL_DATES[i]
    d1 = ALL_DATES[i + 1]
    dist0 = streak_data[d0]
    dist1 = streak_data[d1]
    for k in range(1, 13):
        if dist0.get(k, 0) >= 20:  # need enough sample
            survived = dist1.get(k + 1, 0)
            total = dist0[k]
            rate = survived / total if total else 0
            survival_by_streak[k].append((d0, total, survived, rate))

print(f"  {'Streak':<10} {'Transitions':<14} {'Avg survival':<14} {'Min':<8} {'Max':<8}")
print(f"  {'-'*54}")
for k in sorted(survival_by_streak.keys()):
    entries = survival_by_streak[k]
    rates = [r[3] for r in entries]
    avg = sum(rates) / len(rates)
    mn = min(rates)
    mx = max(rates)
    print(f"  {k:<10} {len(entries):<14} {avg*100:.0f}%            {mn*100:.0f}%      {mx*100:.0f}%")

print(f"\n  Detailed streak-1 -> streak-2 survival (new player to D1 returner):")
for d0, total, survived, rate in survival_by_streak.get(1, []):
    word = PUZZLE_WORDS.get(d0, '?')
    print(f"    {d0} ({word:<10}): {pct(survived, total)} survived ({rate*100:.0f}%)")


# ========== 6. SESSION-LEVEL RETENTION (days_since_first_visit) ==========
print("\n\n" + "=" * 90)
print("6. DAYS SINCE FIRST VISIT (session_started events)")
print("=" * 90)
print("\n  How many days ago did each player first visit? Higher values = longer retained.\n")

dsfv_by_date = defaultdict(Counter)
for date in ALL_DATES:
    for e in events_by_date.get(date, []):
        if e['name'] == 'session_started':
            dsfv = e['_props'].get('days_since_first_visit', '')
            try:
                dsfv_by_date[date][int(dsfv)] += 1
            except:
                pass

print(f"  {'Date':<14} {'Word':<10} {'Sessions':<10} {'New (d=0)':<14} {'d=1':<12} "
      f"{'d=2-3':<12} {'d=4-6':<12} {'d=7+':<12}")
print(f"  {'-'*86}")

for date in ALL_DATES:
    dist = dsfv_by_date[date]
    total = sum(dist.values())
    if total == 0:
        continue
    d0 = dist.get(0, 0)
    d1 = dist.get(1, 0)
    d23 = sum(dist.get(d, 0) for d in range(2, 4))
    d46 = sum(dist.get(d, 0) for d in range(4, 7))
    d7p = sum(c for d, c in dist.items() if d >= 7)
    word = PUZZLE_WORDS.get(date, '?')
    print(f"  {date:<14} {word:<10} {total:<10} {pct(d0, total):<14} {pct(d1, total):<12} "
          f"{pct(d23, total):<12} {pct(d46, total):<12} {pct(d7p, total):<12}")


# ========== 7. SUMMARY ==========
print("\n\n" + "=" * 90)
print("7. KEY RETENTION TAKEAWAYS")
print("=" * 90)
print("""
  Note: Without explicit user IDs, retention is approximated via:
  - current_streak on level_completed (consecutive-day play counter)
  - days_since_first_visit on session_started (total days since first seen)

  These give a strong directional signal even though we can't track individuals
  with certainty.
""")


sys.stdout = sys.__stdout__
out.close()
print(f"Output written to {OUTPUT_FILE}")
