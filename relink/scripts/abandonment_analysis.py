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
OUTPUT_FILE = os.path.join(RELINK_DIR, 'outputs', 'abandonment-analysis.txt')

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

# Load data - collect all dates dynamically, from all CSV files (later files win on dedup)
raw_sessions = {}
for sf in SESSION_FILES:
    with open(sf) as f:
        for row in csv.DictReader(f):
            raw_sessions[row['id']] = row  # last file wins

all_sessions = defaultdict(dict)  # date -> {sid: row}
for sid, row in raw_sessions.items():
    dur = int(row['duration'])
    country = row['country']
    city = row.get('city', '')
    is_bot = (country in ('NL', 'IE') and dur <= 10) or dur <= 2
    is_dev = city == 'Västerås' and country == 'SE'
    if is_bot or is_dev:
        continue
    d = row['created_at'][:10]
    all_sessions[d][row['id']] = row

raw_events = {}
for ef in EVENT_FILES:
    with open(ef) as f:
        for row in csv.DictReader(f):
            raw_events[row['id']] = row  # last file wins

all_events = defaultdict(list)  # date -> [events]
for row in raw_events.values():
    props = parse_props(row.get('properties', '{}'))
    if props.get('game_id') != 'relink':
        continue
    row['_ts'] = parse_ts(row['created_at'])
    row['_props'] = props
    d = row['created_at'][:10]
    all_events[d].append(row)

DATES = sorted(all_sessions.keys() | all_events.keys())

# Match events to sessions (optimised: group events by country)
def match_events(sessions, events):
    events_by_country = defaultdict(list)
    for ev in events:
        events_by_country[ev['country']].append(ev)
    result = {}
    for sid, sess in sessions.items():
        s_start = parse_ts(sess['created_at'])
        s_end = parse_ts(sess['ended_at'])
        if not s_start or not s_end:
            continue
        margin = timedelta(milliseconds=200)
        bucket = events_by_country.get(sess['country'], [])
        matched = [ev for ev in bucket
                   if ev['_ts'] and (s_start - margin) <= ev['_ts'] <= (s_end + margin)
                   and (ev['city'] == sess['city'] or not ev['city'] or not sess['city'])]
        if matched:
            result[sid] = matched
    return result

event_sessions_by_date = {}
for d in DATES:
    event_sessions_by_date[d] = match_events(all_sessions[d], all_events[d])

# Build player data for both dates
def build_players(sessions, event_sessions):
    players = []
    for sid, evts in event_sessions.items():
        sess = sessions[sid]

        real_guesses = []
        relink_guesses = []
        played_tutorial = False
        all_events_list = []

        for ev in sorted(evts, key=lambda e: e['created_at']):
            ep = ev['_props']
            all_events_list.append(ev)

            if ev['name'] == 'tutorial_started':
                played_tutorial = True

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

        if not real_guesses and not relink_guesses:
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

        # Compute active play time (first guess to last guess)
        all_real = sorted(real_guesses + relink_guesses, key=lambda g: g['ts'])
        play_time = (all_real[-1]['ts'] - all_real[0]['ts']).total_seconds() if len(all_real) > 1 else 0

        # Rows completed
        correct_rows = set()
        for g in real_guesses:
            if g['is_correct']:
                correct_rows.add(g['row'])

        # Tester filter: abandon with 0 wrong guesses = not a real player
        if outcome not in ('WON', 'LOST') and len(wrong_guesses) == 0:
            continue

        players.append({
            'date': date,
            'puzzle_date': puzzle_date or date,
            'city': sess['city'],
            'country': sess['country'],
            'device': sess['device'],
            'outcome': outcome or 'INCOMPLETE',
            'played_tutorial': played_tutorial,
            'real_guesses': real_guesses,
            'relink_guesses': relink_guesses,
            'wrong_guesses': wrong_guesses,
            'num_wrong': len(wrong_guesses),
            'total_guesses': len(real_guesses) + len(relink_guesses),
            'play_time': play_time,
            'rows_completed': len(correct_rows),
            'correct_rows': correct_rows,
            'all_events': all_events_list,
        })

    return players

all_players = []
for d in DATES:
    all_players.extend(build_players(all_sessions[d], event_sessions_by_date[d]))

# ========== OUTPUT ==========
out = open(OUTPUT_FILE, 'w')
sys.stdout = out


def run_analysis(players, label):
    incomplete = [p for p in players if p['outcome'] == 'INCOMPLETE']
    completed = [p for p in players if p['outcome'] in ('WON', 'LOST')]
    winners = [p for p in players if p['outcome'] == 'WON']
    losers = [p for p in players if p['outcome'] == 'LOST']

    print("=" * 80)
    print(f"ABANDONMENT ANALYSIS: {label}")
    print(f"Total players: {len(players)} | Completed: {len(completed)} "
          f"({len(winners)}W/{len(losers)}L) | Incomplete: {len(incomplete)}")
    print("=" * 80)

    if not incomplete:
        print("\n  No incomplete sessions — everyone finished.\n")
        return

    abandonment_rate = len(incomplete) / len(players) * 100
    print(f"\n  Abandonment rate: {len(incomplete)}/{len(players)} ({abandonment_rate:.0f}%)")

    # 1. Player-by-player breakdown
    print("\n\n--- 1. INDIVIDUAL ABANDONMENT DETAILS ---")
    for p in incomplete:
        loc = f"{p['city']}, {p['country']}"
        last_action = "no guesses"
        if p['real_guesses']:
            last = p['real_guesses'][-1]
            last_action = f"Row {last['row']} ({'correct' if last['is_correct'] else 'WRONG'})"
        elif p['relink_guesses']:
            last_action = "relink phase"

        print(f"  {loc:<30} {p['device']:<8} | "
              f"{p['total_guesses']} guesses ({p['num_wrong']} wrong) | "
              f"Rows: {p['rows_completed']}/4 | "
              f"Last: {last_action} | "
              f"Play time: {p['play_time']:.0f}s")

        # Show their guess journey
        all_real = sorted(p['real_guesses'] + p['relink_guesses'], key=lambda g: g['ts'])
        prev_ts = None
        for g in all_real:
            gap = f" (+{(g['ts'] - prev_ts).total_seconds():.1f}s)" if prev_ts else ""
            result = "correct" if g['is_correct'] else "WRONG"
            if g['phase'] == 'relink':
                print(f"      RELINK: {g['tiles']} -> {result}{gap}")
            else:
                print(f"      Row {g['row']}: '{g['word']}' -> {result}{gap}")
            prev_ts = g['ts']

    # 2. How far did they get?
    print("\n\n--- 2. WHERE THEY STOPPED ---")
    rows_completed = Counter()
    for p in incomplete:
        rows_completed[p['rows_completed']] += 1
    for rc in sorted(rows_completed.keys()):
        pct = rows_completed[rc] / len(incomplete) * 100
        print(f"  {rc}/4 rows completed: {rows_completed[rc]}/{len(incomplete)} ({pct:.0f}%)")

    # Compare with completed players
    comp_by_rows = Counter()
    for p in completed:
        comp_by_rows[p['rows_completed']] += 1

    # 3. Last action before quitting
    print("\n\n--- 3. LAST ACTION BEFORE QUITTING ---")
    after_wrong = []
    after_correct = []
    for p in incomplete:
        if p['real_guesses']:
            if p['real_guesses'][-1]['is_correct']:
                after_correct.append(p)
            else:
                after_wrong.append(p)
    print(f"  Quit after a WRONG guess:   {len(after_wrong)}/{len(incomplete)} "
          f"({len(after_wrong)/len(incomplete)*100:.0f}%)")
    print(f"  Quit after a correct guess: {len(after_correct)}/{len(incomplete)} "
          f"({len(after_correct)/len(incomplete)*100:.0f}%)")

    if after_wrong:
        print(f"\n  Players who quit after wrong guess:")
        for p in after_wrong:
            last = p['real_guesses'][-1]
            loc = f"{p['city']}, {p['country']}"
            print(f"    {loc:<30} Row {last['row']}: '{last['word']}' | "
                  f"Lives remaining: {last['attempts']} | "
                  f"Rows done: {p['rows_completed']}/4")

    # 4. Tutorial correlation
    print("\n\n--- 4. TUTORIAL AND ABANDONMENT ---")
    inc_tut = sum(1 for p in incomplete if p['played_tutorial'])
    comp_tut = sum(1 for p in completed if p['played_tutorial'])
    print(f"  Incomplete players who played tutorial: {inc_tut}/{len(incomplete)} "
          f"({inc_tut/len(incomplete)*100:.0f}%)")
    if completed:
        print(f"  Completed players who played tutorial: {comp_tut}/{len(completed)} "
              f"({comp_tut/len(completed)*100:.0f}%)")

    # 5. Device breakdown
    print("\n\n--- 5. DEVICE BREAKDOWN ---")
    all_devices = sorted(set(p['device'] for p in players))
    for dev in all_devices:
        inc_dev = sum(1 for p in incomplete if p['device'] == dev)
        comp_dev = sum(1 for p in completed if p['device'] == dev)
        total = inc_dev + comp_dev
        if total:
            print(f"  {dev:<12} {inc_dev}/{total} abandoned ({inc_dev/total*100:.0f}%) | "
                  f"{comp_dev}/{total} completed ({comp_dev/total*100:.0f}%)")

    # 6. Play time comparison
    print("\n\n--- 6. PLAY TIME (first guess to last guess) ---")
    inc_times = sorted([p['play_time'] for p in incomplete if p['play_time'] > 0])
    comp_times = sorted([p['play_time'] for p in completed if p['play_time'] > 0])
    if inc_times:
        print(f"  Incomplete: median {inc_times[len(inc_times)//2]:.0f}s, "
              f"avg {sum(inc_times)/len(inc_times):.0f}s (n={len(inc_times)})")
    else:
        print(f"  Incomplete: insufficient data (most had <=1 guess)")
    if comp_times:
        print(f"  Completed:  median {comp_times[len(comp_times)//2]:.0f}s, "
              f"avg {sum(comp_times)/len(comp_times):.0f}s (n={len(comp_times)})")

    # 7. Wrong guesses comparison
    print("\n\n--- 7. WRONG GUESS COUNT ---")
    inc_wrongs = [p['num_wrong'] for p in incomplete]
    comp_wrongs = [p['num_wrong'] for p in completed]
    win_wrongs = [p['num_wrong'] for p in winners]
    lose_wrongs = [p['num_wrong'] for p in losers]
    print(f"  Incomplete: avg {sum(inc_wrongs)/len(inc_wrongs):.1f} wrong guesses")
    if comp_wrongs:
        print(f"  Completed:  avg {sum(comp_wrongs)/len(comp_wrongs):.1f} wrong guesses")
    if win_wrongs:
        print(f"    Winners:  avg {sum(win_wrongs)/len(win_wrongs):.1f} wrong guesses")
    if lose_wrongs:
        print(f"    Losers:   avg {sum(lose_wrongs)/len(lose_wrongs):.1f} wrong guesses")

    # 8. Which rows were they stuck on?
    print("\n\n--- 8. WHICH ROWS CAUSED ABANDONMENT? ---")
    wrong_by_row = Counter()
    for p in incomplete:
        for g in p['wrong_guesses']:
            wrong_by_row[f"Row {g['row']}"] += 1
    total_inc_wrongs = sum(wrong_by_row.values())
    if total_inc_wrongs:
        for row in ['Row 0', 'Row 1', 'Row 2', 'Row 3']:
            wc = wrong_by_row.get(row, 0)
            pct = wc / total_inc_wrongs * 100 if total_inc_wrongs else 0
            print(f"  {row}: {wc}/{total_inc_wrongs} wrong guesses ({pct:.0f}%)")
    else:
        print("  No wrong guesses from incomplete players")

    # Also show: which row were they ON when they quit?
    print(f"\n  Row they were working on when they quit:")
    last_row = Counter()
    for p in incomplete:
        if p['real_guesses']:
            lr = f"Row {p['real_guesses'][-1]['row']}"
            last_row[lr] += 1
    for row, count in last_row.most_common():
        print(f"    {row}: {count} players")

    # 9. Specific wrong words from abandoners
    print("\n\n--- 9. WRONG WORDS THAT PRECEDED ABANDONMENT ---")
    all_wrong_words = Counter()
    for p in incomplete:
        for g in p['wrong_guesses']:
            all_wrong_words[f"R{g['row']}:'{g['word']}'"] += 1
    if all_wrong_words:
        for word, count in all_wrong_words.most_common(10):
            print(f"  {word}: {count}")
    else:
        print("  No wrong guesses from abandoners")

    # 10. Events before and after guesses — did they do anything else?
    print("\n\n--- 10. OTHER EVENTS FROM ABANDONERS ---")
    event_types = Counter()
    for p in incomplete:
        for ev in p['all_events']:
            if ev['name'] != 'relink_guess_submitted':
                event_types[ev['name']] += 1
    if event_types:
        for ename, count in event_types.most_common():
            print(f"  {ename}: {count}")
    else:
        print("  No other events")


# Group by puzzle date
puzzle_dates = sorted(set(p['puzzle_date'] for p in all_players))

print("=" * 80)
print("ABANDONMENT ANALYSIS: WHO QUITS AND WHY?")
print("=" * 80)
print(f"\nPuzzles found: {len(puzzle_dates)}")
for pd in puzzle_dates:
    pd_players = [p for p in all_players if p['puzzle_date'] == pd]
    inc = sum(1 for p in pd_players if p['outcome'] == 'INCOMPLETE')
    comp = sum(1 for p in pd_players if p['outcome'] in ('WON', 'LOST'))
    print(f"  {pd}: {len(pd_players)} players ({comp} completed, {inc} incomplete)")

for pd in puzzle_dates:
    pd_players = [p for p in all_players if p['puzzle_date'] == pd]
    print("\n\n")
    run_analysis(pd_players, f"PUZZLE: {pd}")


sys.stdout = sys.__stdout__
out.close()
print(f"Output written to {OUTPUT_FILE}")
