import csv
import ast
import sys
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import glob

import os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RELINK_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.dirname(RELINK_DIR)
RAW_DIR = os.path.join(DATA_DIR, 'raw')
EVENT_FILES = sorted(glob.glob(os.path.join(RAW_DIR, 'daily-mail-events*.csv')))
SESSION_FILES = sorted(glob.glob(os.path.join(RAW_DIR, 'daily-mail-sessions*.csv')))
OUTPUT_FILE = os.path.join(RELINK_DIR, 'outputs', 'compare-all-dates.txt')

# Dates and labels will be discovered dynamically from data

def parse_props(raw):
    try:
        return ast.literal_eval(raw)
    except:
        return {}

def parse_ts(ts_str):
    for fmt in ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S']:
        try:
            return datetime.strptime(ts_str, fmt)
        except:
            continue
    return None

# ========== LOAD DATA ==========

# Load all sessions from all files; later files overwrite (dedup by id)
raw_sessions = {}
for sf in SESSION_FILES:
    with open(sf) as f:
        for row in csv.DictReader(f):
            raw_sessions[row['id']] = row  # last file wins

sessions_by_date = defaultdict(dict)
for sid, row in raw_sessions.items():
    dur = int(row['duration'])
    country = row['country']
    city = row.get('city', '')
    is_bot = (country in ('NL', 'IE') and dur <= 10) or dur <= 2
    is_dev = city == 'Västerås' and country == 'SE'
    if is_bot or is_dev:
        continue
    d = row['created_at'][:10]
    sessions_by_date[d][sid] = row

# Load all events from all files; later files overwrite (dedup by id)
raw_events = {}
for ef in EVENT_FILES:
    with open(ef) as f:
        for row in csv.DictReader(f):
            raw_events[row['id']] = row  # last file wins

events_by_date = defaultdict(list)
for row in raw_events.values():
    props = parse_props(row.get('properties', '{}'))
    if props.get('game_id') != 'relink':
        continue
    row['_ts'] = parse_ts(row['created_at'])
    row['_props'] = props
    d = row['created_at'][:10]
    events_by_date[d].append(row)

DATES = sorted(sessions_by_date.keys() | events_by_date.keys())

# Generate labels from dates (e.g. '2026-04-01' -> 'Apr 1')
MONTH_NAMES = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',
               7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
DATE_LABELS = {}
for d in DATES:
    parts = d.split('-')
    DATE_LABELS[d] = f"{MONTH_NAMES[int(parts[1])]} {int(parts[2])}"

for d in DATES:
    events_by_date[d].sort(key=lambda e: e['created_at'])

# ========== MATCH EVENTS TO SESSIONS ==========

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
    event_sessions_by_date[d] = match_events(sessions_by_date[d], events_by_date[d])

# ========== BUILD PLAYER DATA ==========

def build_players(sessions, event_sessions, date_prefix):
    players = []
    for sid, events in event_sessions.items():
        sess = sessions[sid]
        props = parse_props(sess.get('properties', '{}'))

        real_guesses = []
        relink_guesses = []
        played_tutorial = False
        did_tutorial_first = False
        first_real_guess_ts = None

        sorted_events = sorted(events, key=lambda e: e['created_at'])

        for ev in sorted_events:
            ep = ev['_props']
            if ev['name'] == 'tutorial_started':
                played_tutorial = True
                if not first_real_guess_ts:
                    did_tutorial_first = True

            if ev['name'] == 'relink_guess_submitted':
                attempts = ep.get('attempts_remaining', '')
                try:
                    is_tutorial = int(attempts) > 4
                except (ValueError, TypeError):
                    is_tutorial = False
                g = {
                    'ts': ev['_ts'],
                    'phase': ep.get('phase', ''),
                    'is_correct': ep.get('is_correct') == 'true',
                    'word': ep.get('selected_word', ''),
                    'row': ep.get('row_index', ''),
                    'tiles': ep.get('selected_tile_ids', ''),
                    'attempts': attempts,
                }
                if not is_tutorial:
                    if not first_real_guess_ts:
                        first_real_guess_ts = ev['_ts']
                    if g['phase'] == 'relink':
                        relink_guesses.append(g)
                    else:
                        real_guesses.append(g)

        if not real_guesses and not relink_guesses:
            continue

        outcome = None
        for ev in sorted_events:
            if ev['name'] == 'level_completed':
                ep = ev['_props']
                pd = ep.get('puzzle_date', '')
                if pd.startswith(date_prefix):
                    outcome = 'WON' if ep.get('is_won') == 'true' else 'LOST'
        if not outcome:
            outcome = 'WON' if props.get('is_won') == 'true' else ('LOST' if props.get('is_won') == 'false' else 'UNKNOWN')

        wrong_imposters = [g for g in real_guesses if not g['is_correct']]

        row_order = []
        for g in real_guesses:
            if g['row'] not in row_order:
                row_order.append(g['row'])

        sess_start = parse_ts(sess['created_at'])
        time_to_first = (first_real_guess_ts - sess_start).total_seconds() if first_real_guess_ts and sess_start else None

        all_real = sorted(real_guesses + relink_guesses, key=lambda g: g['ts'])
        solve_time = (all_real[-1]['ts'] - all_real[0]['ts']).total_seconds() if len(all_real) > 1 else 0

        row_wrong_before_right = {}
        row_sequence = defaultdict(list)
        for g in real_guesses:
            row_sequence[g['row']].append(g['is_correct'])
        for row, seq in row_sequence.items():
            wrongs = 0
            for v in seq:
                if v:
                    row_wrong_before_right[row] = wrongs
                    break
                wrongs += 1
            else:
                row_wrong_before_right[row] = wrongs

        # Tester filter: abandon with 0 wrong guesses = not a real player
        if outcome not in ('WON', 'LOST') and len(wrong_imposters) == 0:
            continue

        players.append({
            'sid': sid,
            'city': sess['city'],
            'country': sess['country'],
            'device': sess['device'],
            'browser': sess['browser'],
            'duration': int(sess['duration']),
            'outcome': outcome,
            'played_tutorial': played_tutorial,
            'did_tutorial_first': did_tutorial_first,
            'real_guesses': real_guesses,
            'relink_guesses': relink_guesses,
            'wrong_imposters': wrong_imposters,
            'row_order': row_order,
            'time_to_first': time_to_first,
            'solve_time': solve_time,
            'row_wrong_before_right': row_wrong_before_right,
            'total_guesses': len(real_guesses) + len(relink_guesses),
            'num_wrong': len(wrong_imposters),
            'days_since': props.get('days_since_first_visit', '?'),
            'streak': props.get('current_streak', '?'),
        })

    players.sort(key=lambda p: parse_ts(sessions[p['sid']]['created_at']))
    return players

players_by_date = {}
for d in DATES:
    players_by_date[d] = build_players(sessions_by_date[d], event_sessions_by_date[d], d)

# ========== HELPER FUNCTIONS ==========

def puzzle_stats(players):
    if not players:
        return {}
    winners = [p for p in players if p['outcome'] == 'WON']
    losers = [p for p in players if p['outcome'] == 'LOST']
    incomplete = [p for p in players if p['outcome'] == 'UNKNOWN']
    completed = winners + losers
    avg_wrong = sum(p['num_wrong'] for p in players) / len(players)
    avg_total = sum(p['total_guesses'] for p in players) / len(players)
    solve_times = [p['solve_time'] for p in players if p['solve_time'] > 0]
    avg_solve = sum(solve_times) / len(solve_times) if solve_times else 0
    med_solve = sorted(solve_times)[len(solve_times)//2] if solve_times else 0

    tut_n = sum(1 for p in players if p['played_tutorial'])
    tut_pct = tut_n / len(players) * 100
    solve_rate = f"{len(winners)}/{len(completed)} ({len(winners)/len(completed)*100:.0f}%)" if completed else "n/a"
    return {
        'n': len(players),
        'wins': len(winners),
        'losses': len(losers),
        'incomplete': len(incomplete),
        'solve_rate': solve_rate,
        'avg_wrong': f"{avg_wrong:.1f}",
        'avg_total': f"{avg_total:.1f}",
        'avg_solve': f"{avg_solve:.0f}s",
        'med_solve': f"{med_solve:.0f}s",
        'tut_pct': f"{tut_n}/{len(players)} ({tut_pct:.0f}%)",
    }

def row_difficulty(players):
    rows = {}
    total_wrong_all_rows = sum(1 for p in players for g in p['real_guesses'] if not g['is_correct'])
    for row in ['0', '1', '2', '3']:
        first_try = 0
        eventually = 0
        never = 0
        wrong_words = Counter()
        wrong_per_player = []

        for p in players:
            seq = [g for g in p['real_guesses'] if g['row'] == row]
            if not seq:
                continue
            wrongs_this = sum(1 for g in seq if not g['is_correct'])
            wrong_per_player.append(wrongs_this)
            if seq[0]['is_correct']:
                first_try += 1
            elif any(g['is_correct'] for g in seq):
                eventually += 1
            else:
                never += 1
            for g in seq:
                if not g['is_correct']:
                    wrong_words[g['word']] += 1

        attempted = first_try + eventually + never
        total_wrong = sum(wrong_per_player)
        correct_words = set(g['word'] for p in players for g in p['real_guesses'] if g['row'] == row and g['is_correct'])
        rows[row] = {
            'attempted': attempted,
            'first_try': first_try,
            'first_try_pct': f"{first_try}/{attempted} ({first_try/attempted*100:.0f}%)" if attempted else "n/a",
            'eventually': eventually,
            'never': never,
            'total_wrong': total_wrong,
            'wrong_pct_of_all': f"{total_wrong}/{total_wrong_all_rows} ({total_wrong/total_wrong_all_rows*100:.0f}%)" if total_wrong_all_rows else "n/a",
            'avg_wrong': f"{total_wrong/attempted:.1f}" if attempted else "n/a",
            'wrong_words': wrong_words.most_common(5),
            'correct_words': correct_words,
        }
    return rows

def timing_stats(players):
    correct_gaps = []
    wrong_gaps = []
    for p in players:
        prev_ts = None
        for g in p['real_guesses']:
            if prev_ts:
                gap = (g['ts'] - prev_ts).total_seconds()
                if g['is_correct']:
                    correct_gaps.append(gap)
                else:
                    wrong_gaps.append(gap)
            prev_ts = g['ts']
    return correct_gaps, wrong_gaps

def recovery_stats(players):
    post_wrong_correct = 0
    post_wrong_wrong = 0
    post_wrong_gaps = []
    for p in players:
        for i, g in enumerate(p['real_guesses'][:-1]):
            if not g['is_correct']:
                next_g = p['real_guesses'][i + 1]
                gap = (next_g['ts'] - g['ts']).total_seconds()
                post_wrong_gaps.append(gap)
                if next_g['is_correct']:
                    post_wrong_correct += 1
                else:
                    post_wrong_wrong += 1
    total = post_wrong_correct + post_wrong_wrong
    return {
        'correct_after': post_wrong_correct,
        'wrong_after': post_wrong_wrong,
        'total': total,
        'recovery_rate': f"{post_wrong_correct/total*100:.0f}%" if total else "n/a",
        'avg_gap': f"{sum(post_wrong_gaps)/len(post_wrong_gaps):.1f}s" if post_wrong_gaps else "n/a",
        'med_gap': f"{sorted(post_wrong_gaps)[len(post_wrong_gaps)//2]:.1f}s" if post_wrong_gaps else "n/a",
    }

# Column width for date columns
COL_W = 14

# ========== OUTPUT ==========
out = open(OUTPUT_FILE, 'w')
sys.stdout = out

print("=" * 80)
print(f"COMPARISON: ALL RELINK PUZZLES ({DATE_LABELS[DATES[0]]} - {DATE_LABELS[DATES[-1]]}, 2026)")
print("Bots removed | Devs (Västerås, SE) removed | Tutorial-only sessions removed | Testers (abandon w/ 0 wrong) removed")
print("=" * 80)

# ---- 1. SIDE-BY-SIDE PUZZLE STATS ----
print("\n\n" + "=" * 80)
print("1. SIDE-BY-SIDE PUZZLE STATS")
print("=" * 80)

stats_by_date = {d: puzzle_stats(players_by_date[d]) for d in DATES}

header = f"  {'Metric':<30}" + ''.join(f" {DATE_LABELS[d]:>{COL_W}}" for d in DATES)
print(f"\n{header}")
print(f"  {'-' * (30 + (COL_W + 1) * len(DATES))}")
for key, label in [('n', 'Players'), ('wins', 'Wins'), ('losses', 'Losses'),
                    ('incomplete', 'Incomplete'),
                    ('solve_rate', 'Solve rate'),
                    ('avg_wrong', 'Avg wrong guesses'),
                    ('avg_total', 'Avg total guesses'),
                    ('avg_solve', 'Avg solve time'),
                    ('med_solve', 'Median solve time'),
                    ('tut_pct', 'Tutorial %')]:
    row_str = f"  {label:<30}"
    for d in DATES:
        val = stats_by_date[d].get(key, 'n/a')
        row_str += f" {str(val):>{COL_W}}"
    print(row_str)

# ---- 2. ROW DIFFICULTY PER DATE ----
print("\n\n" + "=" * 80)
print("2. ROW DIFFICULTY BY DATE")
print("=" * 80)

rows_by_date = {d: row_difficulty(players_by_date[d]) for d in DATES}

for row in ['0', '1', '2', '3']:
    print(f"\n  Row {row}:")
    for d in DATES:
        rd = rows_by_date[d].get(row, {})
        correct = ', '.join(rd.get('correct_words', set())) or '?'
        print(f"    {DATE_LABELS[d]} answer: {correct}")

    header = f"    {'Metric':<25}" + ''.join(f" {DATE_LABELS[d]:>{COL_W}}" for d in DATES)
    print(header)
    print(f"    {'-' * (25 + (COL_W + 1) * len(DATES))}")

    for key, label in [('attempted', 'Attempted by'),
                        ('first_try_pct', 'First try correct'),
                        ('eventually', 'Eventually correct'),
                        ('never', 'Never correct'),
                        ('total_wrong', 'Total wrong guesses'),
                        ('avg_wrong', 'Avg wrong/player')]:
        row_str = f"    {label:<25}"
        for d in DATES:
            rd = rows_by_date[d].get(row, {})
            val = rd.get(key, 0)
            row_str += f" {str(val):>{COL_W}}"
        print(row_str)

    print(f"    Top wrong guesses:")
    for d in DATES:
        rd = rows_by_date[d].get(row, {})
        wrongs = rd.get('wrong_words', [])
        words_str = ', '.join(f'{w}({c})' for w, c in wrongs) if wrongs else 'none'
        print(f"      {DATE_LABELS[d]}: {words_str}")

# ---- 3. WIN vs LOSS COMPARISON ----
print("\n\n" + "=" * 80)
print("3. WIN vs LOSS COMPARISON")
print("=" * 80)

for d in DATES:
    players = players_by_date[d]
    label = DATE_LABELS[d]
    winners = [p for p in players if p['outcome'] == 'WON']
    losers = [p for p in players if p['outcome'] == 'LOST']
    if not winners or not losers:
        print(f"\n  {label}: Not enough wins/losses to compare")
        continue

    print(f"\n  {label}:")
    print(f"    {'Metric':<30} {'Winners (n=' + str(len(winners)) + ')':<20} {'Losers (n=' + str(len(losers)) + ')':<20}")
    print(f"    {'-'*70}")

    w_wrong = sum(p['num_wrong'] for p in winners) / len(winners)
    l_wrong = sum(p['num_wrong'] for p in losers) / len(losers)
    print(f"    {'Avg wrong guesses':<30} {w_wrong:<20.1f} {l_wrong:<20.1f}")

    w_total = sum(p['total_guesses'] for p in winners) / len(winners)
    l_total = sum(p['total_guesses'] for p in losers) / len(losers)
    print(f"    {'Avg total guesses':<30} {w_total:<20.1f} {l_total:<20.1f}")

    w_solve = [p['solve_time'] for p in winners if p['solve_time'] > 0]
    l_solve = [p['solve_time'] for p in losers if p['solve_time'] > 0]
    w_avg = f"{sum(w_solve)/len(w_solve):.0f}s" if w_solve else 'n/a'
    l_avg = f"{sum(l_solve)/len(l_solve):.0f}s" if l_solve else 'n/a'
    print(f"    {'Avg solve time':<30} {w_avg:<20} {l_avg:<20}")

# ---- 4. TIMING PATTERNS ----
print("\n\n" + "=" * 80)
print("4. TIMING PATTERNS")
print("=" * 80)

header = f"  {'Metric':<35}" + ''.join(f" {DATE_LABELS[d]:>{COL_W}}" for d in DATES)
print(f"\n{header}")
print(f"  {'-' * (35 + (COL_W + 1) * len(DATES))}")

timing_by_date = {d: timing_stats(players_by_date[d]) for d in DATES}

row_str = f"  {'Correct gap (median)':<35}"
for d in DATES:
    c, _ = timing_by_date[d]
    val = f"{sorted(c)[len(c)//2]:.1f}s" if c else 'n/a'
    row_str += f" {val:>{COL_W}}"
print(row_str)

row_str = f"  {'Correct gap (avg)':<35}"
for d in DATES:
    c, _ = timing_by_date[d]
    val = f"{sum(c)/len(c):.1f}s" if c else 'n/a'
    row_str += f" {val:>{COL_W}}"
print(row_str)

row_str = f"  {'Wrong gap (median)':<35}"
for d in DATES:
    _, w = timing_by_date[d]
    val = f"{sorted(w)[len(w)//2]:.1f}s" if w else 'n/a'
    row_str += f" {val:>{COL_W}}"
print(row_str)

row_str = f"  {'Wrong gap (avg)':<35}"
for d in DATES:
    _, w = timing_by_date[d]
    val = f"{sum(w)/len(w):.1f}s" if w else 'n/a'
    row_str += f" {val:>{COL_W}}"
print(row_str)

# ---- 5. RECOVERY AFTER MISTAKES ----
print("\n\n" + "=" * 80)
print("5. RECOVERY AFTER MISTAKES")
print("=" * 80)

recovery_by_date = {d: recovery_stats(players_by_date[d]) for d in DATES}

header = f"  {'Metric':<35}" + ''.join(f" {DATE_LABELS[d]:>{COL_W}}" for d in DATES)
print(f"\n{header}")
print(f"  {'-' * (35 + (COL_W + 1) * len(DATES))}")

row_str = f"  {'Recovery rate':<35}"
for d in DATES:
    r = recovery_by_date[d]
    val = f"{r['correct_after']}/{r['total']}" if r['total'] else 'n/a'
    row_str += f" {val:>{COL_W}}"
print(row_str)

row_str = f"  {'Recovery %':<35}"
for d in DATES:
    r = recovery_by_date[d]
    row_str += f" {r['recovery_rate']:>{COL_W}}"
print(row_str)

row_str = f"  {'Avg time after wrong':<35}"
for d in DATES:
    r = recovery_by_date[d]
    row_str += f" {r['avg_gap']:>{COL_W}}"
print(row_str)

row_str = f"  {'Median time after wrong':<35}"
for d in DATES:
    r = recovery_by_date[d]
    row_str += f" {r['med_gap']:>{COL_W}}"
print(row_str)

# ---- 6. CONFUSION CLUSTERS ----
print("\n\n" + "=" * 80)
print("6. CONFUSION CLUSTERS (2+ wrong guesses)")
print("=" * 80)

for d in DATES:
    players = players_by_date[d]
    confused = [p for p in players if len(p['wrong_imposters']) >= 2]
    if not confused:
        continue
    print(f"\n  {DATE_LABELS[d]} ({len(confused)} players):")
    for p in confused:
        wrong_words = [f"R{g['row']}:'{g['word']}'" for g in p['wrong_imposters']]
        loc = f"{p['city']}, {p['country']}"
        print(f"    {loc} ({p['outcome']}): {' -> '.join(wrong_words)}")

# ---- 7. ROW ORDER ----
print("\n\n" + "=" * 80)
print("7. ROW ORDER COMPARISON")
print("=" * 80)

for d in DATES:
    players = players_by_date[d]
    order_counts = Counter()
    for p in players:
        order = '->'.join(p['row_order'])
        if order:
            order_counts[order] += 1
    print(f"\n  {DATE_LABELS[d]}:")
    for order, count in order_counts.most_common():
        print(f"    {order}: {count} players")

# ---- 8. RELINK PHASE ----
print("\n\n" + "=" * 80)
print("8. RELINK PHASE (LINK ANSWER)")
print("=" * 80)

for d in DATES:
    players = players_by_date[d]
    label = DATE_LABELS[d]
    rg = [g for p in players for g in p['relink_guesses']]
    players_with_relink = [p for p in players if p['relink_guesses']]
    correct = sum(1 for g in rg if g['is_correct'])
    wrong = sum(1 for g in rg if not g['is_correct'])

    tile_counts = Counter()
    for g in rg:
        tiles = g.get('tiles', '')
        n = len(tiles.split(',')) if tiles else 0
        tile_counts[n] += 1

    answer_counter = Counter()
    answer_results = {}
    for g in rg:
        tiles = g.get('tiles', '')
        answer_counter[tiles] += 1
        if tiles not in answer_results:
            answer_results[tiles] = {'correct': 0, 'wrong': 0}
        if g['is_correct']:
            answer_results[tiles]['correct'] += 1
        else:
            answer_results[tiles]['wrong'] += 1

    print(f"\n  {label}:")
    print(f"    Players reaching relink phase: {len(players_with_relink)}/{len(players)}")
    print(f"    Total relink guesses: {len(rg)} (correct: {correct}, wrong: {wrong})")
    if rg:
        print(f"    Success rate: {correct}/{len(rg)} ({correct/len(rg)*100:.0f}%)")
    if tile_counts:
        print(f"    Tiles per answer: {', '.join(f'{n} tiles: {c}' for n, c in sorted(tile_counts.items()))}")

    wrong_answers = [g for g in rg if not g['is_correct']]
    if wrong_answers:
        print(f"    Wrong answers:")
        for g in wrong_answers:
            for p in players:
                if g in p['relink_guesses']:
                    loc = f"{p['city']}, {p['country']}"
                    print(f"      {loc}: {g['tiles']} (lives: {g['attempts']})")
                    break

    if answer_counter:
        print(f"    Most common answers:")
        for tiles, count in answer_counter.most_common(5):
            r = answer_results[tiles]
            print(f"      {tiles}: {count}x (correct: {r['correct']}, wrong: {r['wrong']})")

# ---- 9. PLAYER JOURNEYS ----
print("\n\n" + "=" * 80)
print("9. PLAYER JOURNEYS (STEP-BY-STEP)")
print("=" * 80)

for d in DATES:
    players = players_by_date[d]
    label = DATE_LABELS[d]
    if not players:
        continue

    print(f"\n  {'=' * 70}")
    print(f"  {label} ({len(players)} players)")
    print(f"  {'=' * 70}")

    for i, p in enumerate(players, 1):
        print(f"\n  {'-' * 60}")
        print(f"  Player {i}: {p['city']}, {p['country']} | {p['device']} ({p['browser']})")
        print(f"    Outcome: {p['outcome']} | Wrong: {p['num_wrong']} | Total guesses: {p['total_guesses']}")
        if p['streak'] != '?':
            print(f"    Streak: {p['streak']} | Days since first visit: {p['days_since']}")

        all_real = sorted(p['real_guesses'] + p['relink_guesses'], key=lambda g: g['ts'])
        prev_ts = None
        for g in all_real:
            gap = f" (+{(g['ts'] - prev_ts).total_seconds():.1f}s)" if prev_ts else ""
            result = "+" if g['is_correct'] else "X"
            ts_str = g['ts'].strftime('%H:%M:%S')
            if g['phase'] == 'relink':
                print(f"      [{ts_str}]{gap} RELINK: {g['tiles']} -> {result}")
            else:
                print(f"      [{ts_str}]{gap} Row {g['row']}: '{g['word']}' (lives: {g['attempts']}) -> {result}")
            prev_ts = g['ts']

        if len(all_real) > 1:
            solve = (all_real[-1]['ts'] - all_real[0]['ts']).total_seconds()
            print(f"    Solve time: {solve:.0f}s")

# ---- CLOSE ----
sys.stdout = sys.__stdout__
out.close()

print(f"Output written to {OUTPUT_FILE}")
with open(OUTPUT_FILE) as f:
    for line in f:
        print(line, end='')
        if 'Tutorial %' in line:
            break
