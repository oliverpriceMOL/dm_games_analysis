import csv, ast, sys
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import glob

import os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RELINK_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.dirname(RELINK_DIR)
RAW_DIR = os.path.join(DATA_DIR, 'raw')
SESSION_FILES = sorted(glob.glob(os.path.join(RAW_DIR, 'daily-mail-sessions*.csv')))
EVENT_FILES = sorted(glob.glob(os.path.join(RAW_DIR, 'daily-mail-events*.csv')))
OUTPUT_FILE = os.path.join(RELINK_DIR, 'outputs', 'failure-analysis.txt')

# Dates will be discovered dynamically from data

def parse_ts(s):
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S.%f'):
        try:
            return datetime.strptime(s.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None

def parse_props(s):
    try:
        return ast.literal_eval(s)
    except:
        return {}

# Load data - all dates dynamically, from all CSV files (later files win on dedup)
all_sessions = {}
session_dates = set()
for sf in SESSION_FILES:
    with open(sf) as f:
        for row in csv.DictReader(f):
            all_sessions[row['id']] = row  # last file wins

# Apply filters after dedup
filtered_sessions = {}
for sid, row in all_sessions.items():
    dur = int(row['duration'])
    country = row['country']
    city = row.get('city', '')
    is_bot = (country in ('NL', 'IE') and dur <= 10) or dur <= 2
    is_dev = city == 'Västerås' and country == 'SE'
    if is_bot or is_dev:
        continue
    d = row['created_at'][:10]
    session_dates.add(d)
    filtered_sessions[sid] = row
all_sessions = filtered_sessions

all_events_raw = {}
for ef in EVENT_FILES:
    with open(ef) as f:
        for row in csv.DictReader(f):
            all_events_raw[row['id']] = row  # last file wins

all_relink_events = []
event_dates = set()
for row in all_events_raw.values():
    props = parse_props(row.get('properties', '{}'))
    if props.get('game_id') != 'relink':
        continue
    row['_ts'] = parse_ts(row['created_at'])
    row['_props'] = props
    d = row['created_at'][:10]
    event_dates.add(d)
    all_relink_events.append(row)

DATES = sorted(session_dates | event_dates)

# Match events to sessions (optimised: group events by country+date)
events_by_key = defaultdict(list)
for ev in all_relink_events:
    d = ev['created_at'][:10]
    events_by_key[(ev['country'], d)].append(ev)

all_event_sessions = {}
for sid, sess in all_sessions.items():
    s_start = parse_ts(sess['created_at'])
    s_end = parse_ts(sess['ended_at'])
    if not s_start or not s_end:
        continue
    margin = timedelta(milliseconds=200)
    d = sess['created_at'][:10]
    bucket = events_by_key.get((sess['country'], d), [])
    matched = [ev for ev in bucket
               if ev['_ts'] and (s_start - margin) <= ev['_ts'] <= (s_end + margin)
               and (ev['city'] == sess['city'] or not ev['city'] or not sess['city'])]
    if matched:
        all_event_sessions[sid] = matched

# Build player data
all_losers = []
all_winners = []

for sid, evts in all_event_sessions.items():
    sess = all_sessions[sid]
    dur = int(sess['duration'])
    country = sess['country']
    if (country in ('NL', 'IE') and dur <= 10) or dur <= 2:
        continue

    real_guesses = []
    relink_guesses = []
    for ev in sorted(evts, key=lambda e: e['created_at']):
        ep = ev['_props']
        if ev['name'] == 'relink_guess_submitted':
            att = ep.get('attempts_remaining', '')
            try:
                if int(att) > 4:
                    continue
            except (ValueError, TypeError):
                continue
            g = {
                'ts': ev['_ts'],
                'phase': ep.get('phase', ''),
                'is_correct': ep.get('is_correct') == 'true',
                'word': ep.get('selected_word', ''),
                'row': ep.get('row_index', ''),
                'tiles': ep.get('selected_tile_ids', ''),
                'attempts': att,
            }
            if g['phase'] == 'relink':
                relink_guesses.append(g)
            else:
                real_guesses.append(g)

    if not real_guesses:
        continue

    outcome = None
    puzzle_date = None
    for ev in sorted(evts, key=lambda e: e['created_at']):
        if ev['name'] == 'level_completed':
            ep = ev['_props']
            is_won = ep.get('is_won', ep.get('outcome', ''))
            if is_won in ('true', 'WON'):
                outcome = 'WON'
            elif is_won in ('false', 'LOST'):
                outcome = 'LOST'
            puzzle_date = ep.get('puzzle_date', '')

    date = sess['created_at'][:10]
    wrong_guesses = [g for g in real_guesses if not g['is_correct']]

    # Tester filter: abandon with 0 wrong guesses = not a real player
    if outcome not in ('WON', 'LOST') and len(wrong_guesses) == 0:
        continue

    player = {
        'date': date,
        'puzzle_date': puzzle_date or date,
        'city': sess['city'],
        'country': sess['country'],
        'device': sess['device'],
        'outcome': outcome,
        'real_guesses': real_guesses,
        'relink_guesses': relink_guesses,
        'wrong_guesses': wrong_guesses,
        'num_wrong': len(wrong_guesses),
    }

    if outcome == 'LOST':
        all_losers.append(player)
    elif outcome == 'WON':
        all_winners.append(player)

def run_analysis(losers, winners, label):
    print("=" * 80)
    print(f"FAILURE ANALYSIS: {label}")
    print(f"Losers: {len(losers)}  |  Winners: {len(winners)}")
    print("=" * 80)

    if not losers:
        print("\n  No losers for this puzzle — skipping.\n")
        return

    # 1. Which row killed them?
    print("\n\n--- 1. KILLING BLOW: Which row was the final wrong guess on? ---")
    killing_row = Counter()
    killing_word = Counter()
    for p in losers:
        last_wrong = [g for g in p['real_guesses'] if not g['is_correct']]
        if last_wrong:
            final = last_wrong[-1]
            killing_row[f"Row {final['row']}"] += 1
            killing_word[final['word']] += 1
    for row, count in killing_row.most_common():
        print(f"  {row}: {count}/{len(losers)} losers' final mistake")
    print("  Final wrong word picked:")
    for word, count in killing_word.most_common():
        print(f"    '{word}': {count}")

    # 2. Where did losers spend their lives?
    print("\n\n--- 2. WHERE LOSERS SPENT THEIR LIVES ---")
    loser_wrongs_by_row = Counter()
    winner_wrongs_by_row = Counter()
    for p in losers:
        for g in p['wrong_guesses']:
            loser_wrongs_by_row[f"Row {g['row']}"] += 1
    for p in winners:
        for g in p['wrong_guesses']:
            winner_wrongs_by_row[f"Row {g['row']}"] += 1
    total_loser_wrongs = sum(loser_wrongs_by_row.values())
    total_winner_wrongs = sum(winner_wrongs_by_row.values())
    print(f"\n  {'Row':<10} {'Loser wrongs':<20} {'Winner wrongs':<20}")
    print(f"  {'-'*50}")
    for row in ['Row 0', 'Row 1', 'Row 2', 'Row 3']:
        lw = loser_wrongs_by_row.get(row, 0)
        ww = winner_wrongs_by_row.get(row, 0)
        lp = f"{lw}/{total_loser_wrongs} ({lw/total_loser_wrongs*100:.0f}%)" if total_loser_wrongs else "0"
        wp = f"{ww}/{total_winner_wrongs} ({ww/total_winner_wrongs*100:.0f}%)" if total_winner_wrongs else "0"
        print(f"  {row:<10} {lp:<20} {wp:<20}")

    # 2b. Exact wrong tiles and order per loser
    print(f"\n  Per-player wrong guess sequence:")
    for p in losers:
        if not p['wrong_guesses']:
            continue
        loc = f"{p['city']}, {p['country']}"
        seq = [f"R{g['row']}:'{g['word']}'" for g in p['wrong_guesses']]
        print(f"    {loc:<30} {' -> '.join(seq)}")

    # 2c. Most common wrong words overall
    all_wrong_words = Counter()
    for p in losers:
        for g in p['wrong_guesses']:
            all_wrong_words[f"R{g['row']}:'{g['word']}'"] += 1
    print(f"\n  Most picked wrong tiles (losers):")
    for tile, count in all_wrong_words.most_common(10):
        print(f"    {tile}: {count}")

    # 3. Did losers get stuck on one row or spread mistakes?
    print("\n\n--- 3. MISTAKE CONCENTRATION: One row or spread? ---")
    for p in losers:
        row_wrongs = Counter()
        for g in p['wrong_guesses']:
            row_wrongs[f"R{g['row']}"] += 1
        spread = ', '.join(f"{r}:{c}" for r, c in row_wrongs.most_common())
        loc = f"{p['city']}, {p['country']}"
        print(f"  {p['date']} {loc:<30} {p['num_wrong']} wrong | {spread}")

    # 4. Did losers try the same wrong word twice?
    print("\n\n--- 4. REPEAT MISTAKES: Same wrong word picked multiple times ---")
    any_repeats = False
    for p in losers:
        word_counts = Counter(g['word'] for g in p['wrong_guesses'])
        repeats = {w: c for w, c in word_counts.items() if c > 1}
        if repeats:
            any_repeats = True
            loc = f"{p['city']}, {p['country']}"
            rep_str = ', '.join(f"'{w}' x{c}" for w, c in repeats.items())
            print(f"  {p['date']} {loc}: {rep_str}")
    if not any_repeats:
        print("  (none)")

    # 5. How many rows did losers complete before failing?
    print("\n\n--- 5. PROGRESS BEFORE FAILURE: How many rows completed? ---")
    for p in losers:
        correct_rows = set()
        for g in p['real_guesses']:
            if g['is_correct']:
                correct_rows.add(g['row'])
        reached_relink = len(p['relink_guesses']) > 0
        loc = f"{p['city']}, {p['country']}"
        print(f"  {p['date']} {loc:<30} Completed {len(correct_rows)}/4 rows | "
              f"Reached relink: {'Yes' if reached_relink else 'No'} | "
              f"Wrong: {p['num_wrong']}")

    # 6. Timing: did losers guess faster than winners?
    print("\n\n--- 6. TIMING: Losers vs Winners ---")
    loser_gaps = []
    winner_gaps = []
    for p in losers:
        for i, g in enumerate(p['real_guesses'][1:], 1):
            gap = (g['ts'] - p['real_guesses'][i-1]['ts']).total_seconds()
            loser_gaps.append(gap)
    for p in winners:
        for i, g in enumerate(p['real_guesses'][1:], 1):
            gap = (g['ts'] - p['real_guesses'][i-1]['ts']).total_seconds()
            winner_gaps.append(gap)
    if loser_gaps and winner_gaps:
        loser_gaps.sort()
        winner_gaps.sort()
        print(f"  Losers:  median gap {loser_gaps[len(loser_gaps)//2]:.1f}s, "
              f"avg {sum(loser_gaps)/len(loser_gaps):.1f}s (n={len(loser_gaps)})")
        print(f"  Winners: median gap {winner_gaps[len(winner_gaps)//2]:.1f}s, "
              f"avg {sum(winner_gaps)/len(winner_gaps):.1f}s (n={len(winner_gaps)})")
    elif loser_gaps:
        loser_gaps.sort()
        print(f"  Losers:  median gap {loser_gaps[len(loser_gaps)//2]:.1f}s, "
              f"avg {sum(loser_gaps)/len(loser_gaps):.1f}s (n={len(loser_gaps)})")
        print("  Winners: no data")
    else:
        print("  Insufficient timing data")

    # 7. First guess: did losers start wrong more often?
    print("\n\n--- 7. FIRST GUESS: Right or wrong? ---")
    loser_first_wrong = sum(1 for p in losers if not p['real_guesses'][0]['is_correct'])
    print(f"  Losers starting with wrong guess:  {loser_first_wrong}/{len(losers)} "
          f"({loser_first_wrong/len(losers)*100:.0f}%)")
    if winners:
        winner_first_wrong = sum(1 for p in winners if not p['real_guesses'][0]['is_correct'])
        print(f"  Winners starting with wrong guess: {winner_first_wrong}/{len(winners)} "
              f"({winner_first_wrong/len(winners)*100:.0f}%)")

    # 8. Cascading failures: wrong streaks
    print("\n\n--- 8. CASCADING FAILURES: Longest wrong streaks ---")
    for p in losers:
        max_streak = 0
        current_streak = 0
        streak_words = []
        max_streak_words = []
        for g in p['real_guesses']:
            if not g['is_correct']:
                current_streak += 1
                streak_words.append(f"R{g['row']}:'{g['word']}'")
            else:
                if current_streak > max_streak:
                    max_streak = current_streak
                    max_streak_words = streak_words[:]
                current_streak = 0
                streak_words = []
        if current_streak > max_streak:
            max_streak = current_streak
            max_streak_words = streak_words[:]
        loc = f"{p['city']}, {p['country']}"
        print(f"  {p['date']} {loc:<30} longest streak: {max_streak} wrong in a row")
        if max_streak_words:
            print(f"    {' -> '.join(max_streak_words)}")


# Group by puzzle date and run analysis for each
all_players = all_losers + all_winners
puzzle_dates = sorted(set(p['puzzle_date'] for p in all_players if p['puzzle_date'] in DATES))

out = open(OUTPUT_FILE, 'w')
sys.stdout = out

print("=" * 80)
print("FAILURE ANALYSIS: WHAT CAUSES PLAYERS TO LOSE?")
print(f"Data: {DATES[0]} to {DATES[-1]}")
print("=" * 80)
print(f"\nPuzzles found: {len(puzzle_dates)}")
for pd in puzzle_dates:
    losers_pd = [p for p in all_losers if p['puzzle_date'] == pd]
    winners_pd = [p for p in all_winners if p['puzzle_date'] == pd]
    print(f"  {pd}: {len(losers_pd) + len(winners_pd)} players ({len(winners_pd)} won, {len(losers_pd)} lost)")

for pd in puzzle_dates:
    losers_pd = [p for p in all_losers if p['puzzle_date'] == pd]
    winners_pd = [p for p in all_winners if p['puzzle_date'] == pd]
    print("\n\n")
    run_analysis(losers_pd, winners_pd, f"PUZZLE: {pd}")

sys.stdout = sys.__stdout__
out.close()

print(f"Output written to {OUTPUT_FILE}")
