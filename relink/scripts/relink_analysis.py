"""
Relink Puzzle Analysis — Comprehensive per-puzzle breakdown.

Usage:
    python3 relink_analysis.py [--pdl metadata.json]

Reads data from all raw/daily-mail-events*.csv and raw/daily-mail-sessions*.csv files.
Later files take priority for dedup (by event/session ID).
Outputs to relink/outputs/relink-analysis.txt.
"""

import csv, ast, sys, os, json, argparse, glob
from datetime import datetime, timedelta
from collections import Counter, defaultdict

# ── Paths ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RELINK_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.dirname(RELINK_DIR)
RAW_DIR = os.path.join(DATA_DIR, 'raw')
SESSION_FILES = sorted(glob.glob(os.path.join(RAW_DIR, 'daily-mail-sessions*.csv')))
EVENT_FILES = sorted(glob.glob(os.path.join(RAW_DIR, 'daily-mail-events*.csv')))
OUTPUT_FILE = os.path.join(RELINK_DIR, 'outputs', 'relink-analysis.txt')

# DATES and DATE_LABELS will be discovered dynamically from data

# ── CLI ──
parser = argparse.ArgumentParser()
parser.add_argument('--pdl', help='Path to PDL metadata JSON file', default=None)
args = parser.parse_args()

# ── Helpers ──
def parse_ts(s):
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S.%f'):
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

def median(vals):
    if not vals:
        return 0
    s = sorted(vals)
    n = len(s)
    return (s[n // 2] + s[(n - 1) // 2]) / 2

def pct(num, den):
    return f"{num}/{den} ({num/den*100:.0f}%)" if den else "n/a"

# ── Load sessions from all files (later files win on dedup) ──
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

# ── Load events from all files (later files win on dedup) ──
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

# ── Match events to sessions ──
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

# ── Build player data ──
def build_players(sessions, event_sessions, date_prefix):
    players = []
    for sid, events in event_sessions.items():
        sess = sessions[sid]
        sess_props = parse_props(sess.get('properties', '{}'))

        real_guesses = []
        relink_guesses = []
        played_tutorial = False
        first_real_ts = None

        sorted_events = sorted(events, key=lambda e: e['created_at'])

        for ev in sorted_events:
            ep = ev['_props']
            if ev['name'] in ('tutorial_started', 'tutorial_completed', 'tutorial_skipped'):
                played_tutorial = True

            if ev['name'] == 'relink_guess_submitted':
                att = ep.get('attempts_remaining', '')
                try:
                    is_tutorial = int(att) > 4
                except (ValueError, TypeError):
                    is_tutorial = False
                if is_tutorial:
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
                if not first_real_ts:
                    first_real_ts = ev['_ts']
                if g['phase'] == 'relink':
                    relink_guesses.append(g)
                else:
                    real_guesses.append(g)

        if not real_guesses and not relink_guesses:
            continue

        outcome = None
        puzzle_date = None
        for ev in sorted_events:
            if ev['name'] == 'level_completed':
                ep = ev['_props']
                pd = ep.get('puzzle_date', '')
                if pd.startswith(date_prefix):
                    outcome = 'WON' if ep.get('is_won') == 'true' else 'LOST'
                    puzzle_date = pd

        if not outcome:
            outcome = 'INCOMPLETE'

        wrong_imposters = [g for g in real_guesses if not g['is_correct']]

        row_order = []
        for g in real_guesses:
            if g['row'] not in row_order:
                row_order.append(g['row'])

        all_real = sorted(real_guesses + relink_guesses, key=lambda g: g['ts'])
        solve_time = (all_real[-1]['ts'] - all_real[0]['ts']).total_seconds() if len(all_real) > 1 else 0

        # Rows completed
        rows_completed = set()
        for g in real_guesses:
            if g['is_correct']:
                rows_completed.add(g['row'])

        # Last guess info (for abandonment)
        last_guess = all_real[-1] if all_real else None

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
            'real_guesses': real_guesses,
            'relink_guesses': relink_guesses,
            'wrong_imposters': wrong_imposters,
            'row_order': row_order,
            'solve_time': solve_time,
            'total_guesses': len(real_guesses) + len(relink_guesses),
            'num_wrong': len(wrong_imposters),
            'rows_completed': rows_completed,
            'last_guess': last_guess,
            'days_since': sess_props.get('days_since_first_visit', '?'),
            'streak': sess_props.get('current_streak', '?'),
        })

    players.sort(key=lambda p: parse_ts(sessions[p['sid']]['created_at']))
    return players

players_by_date = {}
for d in DATES:
    players_by_date[d] = build_players(sessions_by_date[d], event_sessions_by_date[d], d)

# ── Load PDL metadata if provided ──
pdl_data = None
if args.pdl and os.path.exists(args.pdl):
    with open(args.pdl) as f:
        pdl_data = json.load(f)

# ══════════════════════════════════════════════════════════════════════
#  OUTPUT
# ══════════════════════════════════════════════════════════════════════

with open(OUTPUT_FILE, 'w') as out:
    sys.stdout = out

    SEP = "=" * 80

    print(SEP)
    print("RELINK COMPREHENSIVE ANALYSIS")
    print("Bots removed | Devs (Västerås, SE) removed | Tutorial-only sessions removed | Testers (abandon w/ 0 wrong) removed")
    print(f"Dates: {DATE_LABELS[DATES[0]]} – {DATE_LABELS[DATES[-1]]}")
    print(SEP)

    # ═══════════════════════════════════════════════════════════════════
    # 1. SOLVE RATES BY PUZZLE DATE
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n\n{SEP}")
    print("1. SOLVE RATES BY PUZZLE DATE")
    print(SEP)

    print(f"\n  {'Date':<10} {'Players':>8} {'Won':>8} {'Lost':>8} {'Incmpl':>8} {'Solve%':>12}")
    print("  " + "-" * 58)
    for d in DATES:
        pp = players_by_date[d]
        w = sum(1 for p in pp if p['outcome'] == 'WON')
        l = sum(1 for p in pp if p['outcome'] == 'LOST')
        inc = sum(1 for p in pp if p['outcome'] == 'INCOMPLETE')
        comp = w + l
        print(f"  {DATE_LABELS[d]:<10} {len(pp):>8} {w:>8} {l:>8} {inc:>8} {pct(w, comp):>12}")

    # ═══════════════════════════════════════════════════════════════════
    # 2. ROW-LEVEL DIFFICULTY
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n\n{SEP}")
    print("2. ROW-LEVEL DIFFICULTY")
    print(SEP)

    for d in DATES:
        pp = players_by_date[d]
        label = DATE_LABELS[d]
        print(f"\n  ── {label} ({len(pp)} players) {'─' * 50}")

        for row in ['0', '1', '2', '3']:
            first_try = 0
            eventually = 0
            never = 0
            wrong_words = Counter()
            wrong_counts = []

            for p in pp:
                seq = [g for g in p['real_guesses'] if g['row'] == row]
                if not seq:
                    continue
                wrongs = sum(1 for g in seq if not g['is_correct'])
                wrong_counts.append(wrongs)
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
            total_wrong = sum(wrong_counts)
            correct_words = set(g['word'] for p in pp for g in p['real_guesses']
                                if g['row'] == row and g['is_correct'])

            print(f"\n    Row {row} (answer: {', '.join(sorted(correct_words))})")
            print(f"      Attempted by:        {attempted}")
            print(f"      First try correct:   {pct(first_try, attempted)}")
            print(f"      Eventually correct:  {eventually}")
            print(f"      Never correct:       {never}")
            print(f"      Total wrong guesses: {total_wrong}")
            print(f"      Avg wrong/player:    {total_wrong/attempted:.1f}" if attempted else "      Avg wrong/player:    n/a")
            if wrong_words:
                top = ', '.join(f"{w}({c})" for w, c in wrong_words.most_common(5))
                print(f"      Top wrong tiles:     {top}")

    # ═══════════════════════════════════════════════════════════════════
    # 3. ROW ATTEMPT ORDER ANALYSIS
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n\n{SEP}")
    print("3. ROW ATTEMPT ORDER ANALYSIS")
    print(SEP)

    for d in DATES:
        pp = players_by_date[d]
        label = DATE_LABELS[d]
        print(f"\n  ── {label} ({len(pp)} players) {'─' * 50}")

        # Position counts: how often each row was attempted at each position
        pos_counts = {r: Counter() for r in ['0', '1', '2', '3']}
        never_attempted = Counter()
        # First-try correct by position (early = 1st/2nd, late = 3rd/4th)
        early_first_try = {r: [0, 0] for r in ['0', '1', '2', '3']}  # [correct, total]
        late_first_try = {r: [0, 0] for r in ['0', '1', '2', '3']}

        for p in pp:
            order = p['row_order']
            attempted_rows = set(order)
            for r in ['0', '1', '2', '3']:
                if r in attempted_rows:
                    pos = order.index(r)
                    pos_counts[r][pos + 1] += 1  # 1-indexed
                else:
                    never_attempted[r] += 1

            # First-try correct by attempt position
            for pos_idx, r in enumerate(order):
                seq = [g for g in p['real_guesses'] if g['row'] == r]
                if not seq:
                    continue
                is_early = pos_idx < 2  # 0 or 1 = early
                if is_early:
                    early_first_try[r][1] += 1
                    if seq[0]['is_correct']:
                        early_first_try[r][0] += 1
                else:
                    late_first_try[r][1] += 1
                    if seq[0]['is_correct']:
                        late_first_try[r][0] += 1

        # Position frequency table
        print(f"\n    How often each row was attempted at each position:")
        print(f"      {'Row':<6} {'1st':>8} {'2nd':>8} {'3rd':>8} {'4th':>8} {'Never':>8}")
        print(f"      {'─' * 46}")
        for r in ['0', '1', '2', '3']:
            vals = [str(pos_counts[r].get(i, 0)) for i in range(1, 5)]
            nv = str(never_attempted.get(r, 0))
            print(f"      Row {r}  {vals[0]:>8} {vals[1]:>8} {vals[2]:>8} {vals[3]:>8} {nv:>8}")

        # Early vs late first-try rates
        print(f"\n    First-try correct rate by attempt position (early=1st/2nd, late=3rd/4th):")
        print(f"      {'Row':<6} {'Early':>14} {'Late':>14} {'Delta':>8}")
        print(f"      {'─' * 44}")
        for r in ['0', '1', '2', '3']:
            ec, et = early_first_try[r]
            lc, lt = late_first_try[r]
            e_pct = ec / et * 100 if et else 0
            l_pct = lc / lt * 100 if lt else 0
            delta = l_pct - e_pct
            e_str = pct(ec, et) if et else "n/a"
            l_str = pct(lc, lt) if lt else "n/a"
            d_str = f"{delta:+.0f}pp" if et and lt else "n/a"
            print(f"      Row {r}  {e_str:>14} {l_str:>14} {d_str:>8}")

        print(f"\n    (Positive delta = vertical inference is helping; negative = row is harder late)")

    # ═══════════════════════════════════════════════════════════════════
    # 4. FAILURE ANALYSIS
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n\n{SEP}")
    print("4. FAILURE ANALYSIS")
    print(SEP)

    for d in DATES:
        pp = players_by_date[d]
        label = DATE_LABELS[d]
        winners = [p for p in pp if p['outcome'] == 'WON']
        losers = [p for p in pp if p['outcome'] == 'LOST']

        if not losers:
            continue

        print(f"\n  ── {label}: {len(losers)} losers, {len(winners)} winners {'─' * 30}")

        # 4a. Killing blow
        killing_row = Counter()
        killing_word = Counter()
        for p in losers:
            if p['wrong_imposters']:
                last = p['wrong_imposters'][-1]
                killing_row[f"Row {last['row']}"] += 1
                killing_word[f"R{last['row']}:'{last['word']}'"] += 1

        print(f"\n    Killing blow (final wrong guess):")
        for k, v in killing_row.most_common():
            print(f"      {k}: {v}/{len(losers)} ({v/len(losers)*100:.0f}%)")

        print(f"\n    Top killing tiles:")
        for k, v in killing_word.most_common(5):
            print(f"      {k}: {v}")

        # 4b. Where losers vs winners spent wrong guesses
        loser_row_wrongs = Counter()
        winner_row_wrongs = Counter()
        for p in losers:
            for g in p['wrong_imposters']:
                loser_row_wrongs[g['row']] += 1
        for p in winners:
            for g in p['wrong_imposters']:
                winner_row_wrongs[g['row']] += 1

        loser_total = sum(loser_row_wrongs.values())
        winner_total = sum(winner_row_wrongs.values())

        print(f"\n    Wrong guesses by row (losers vs winners):")
        print(f"      {'Row':<6} {'Losers':>16} {'Winners':>16}")
        print(f"      {'─' * 38}")
        for r in ['0', '1', '2', '3']:
            lv = loser_row_wrongs.get(r, 0)
            wv = winner_row_wrongs.get(r, 0)
            l_pct = f"{lv} ({lv/loser_total*100:.0f}%)" if loser_total else "0"
            w_pct = f"{wv} ({wv/winner_total*100:.0f}%)" if winner_total else "0"
            print(f"      Row {r} {l_pct:>16} {w_pct:>16}")

        # 4c. Cascading failures (longest streak of consecutive wrong guesses)
        streaks = []
        for p in losers:
            max_streak = 0
            current = 0
            for g in p['real_guesses']:
                if not g['is_correct']:
                    current += 1
                    max_streak = max(max_streak, current)
                else:
                    current = 0
            streaks.append(max_streak)

        streak_dist = Counter(streaks)
        print(f"\n    Longest consecutive wrong guess streak (losers):")
        for s in sorted(streak_dist):
            print(f"      {s} in a row: {streak_dist[s]} players")

        # 4d. Started with wrong first guess?
        started_wrong = sum(1 for p in losers if p['real_guesses'] and not p['real_guesses'][0]['is_correct'])
        print(f"\n    Started with wrong first guess: {pct(started_wrong, len(losers))}")

        # 4e. Rows completed before losing
        rows_done = Counter()
        for p in losers:
            rows_done[len(p['rows_completed'])] += 1
        print(f"\n    Rows completed before losing:")
        for n in sorted(rows_done):
            print(f"      {n} rows: {rows_done[n]} players")

    # ═══════════════════════════════════════════════════════════════════
    # 5. ABANDONMENT ANALYSIS
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n\n{SEP}")
    print("5. ABANDONMENT ANALYSIS")
    print(SEP)

    for d in DATES:
        pp = players_by_date[d]
        label = DATE_LABELS[d]
        abandoners = [p for p in pp if p['outcome'] == 'INCOMPLETE']
        completers = [p for p in pp if p['outcome'] in ('WON', 'LOST')]

        if not abandoners:
            continue

        print(f"\n  ── {label}: {len(abandoners)} abandoners, {len(completers)} completers {'─' * 20}")

        # 5a. Rows completed
        rows_done = Counter()
        for p in abandoners:
            rows_done[len(p['rows_completed'])] += 1
        print(f"\n    Rows completed before abandoning:")
        for n in sorted(rows_done):
            print(f"      {n} rows: {rows_done[n]} players")

        # 5b. Quit after wrong or correct?
        quit_after_wrong = 0
        quit_after_correct = 0
        for p in abandoners:
            if p['last_guess']:
                if p['last_guess'].get('is_correct', p['last_guess'].get('phase') == 'relink'):
                    quit_after_correct += 1
                else:
                    quit_after_wrong += 1
        print(f"\n    Quit after wrong guess:   {pct(quit_after_wrong, len(abandoners))}")
        print(f"    Quit after correct guess: {pct(quit_after_correct, len(abandoners))}")

        # 5c. Tutorial completion
        aband_tut = sum(1 for p in abandoners if p['played_tutorial'])
        comp_tut = sum(1 for p in completers if p['played_tutorial'])
        print(f"\n    Tutorial played — abandoners: {pct(aband_tut, len(abandoners))}")
        print(f"    Tutorial played — completers: {pct(comp_tut, len(completers))}" if completers else "")

        # 5d. Device breakdown
        a_mobile = sum(1 for p in abandoners if p['device'] == 'mobile')
        a_desktop = sum(1 for p in abandoners if p['device'] == 'desktop')
        a_tablet = sum(1 for p in abandoners if p['device'] == 'tablet')
        c_mobile = sum(1 for p in completers if p['device'] == 'mobile')
        c_desktop = sum(1 for p in completers if p['device'] == 'desktop')
        c_tablet = sum(1 for p in completers if p['device'] == 'tablet')
        print(f"\n    Device — abandoners: mobile {a_mobile}, desktop {a_desktop}, tablet {a_tablet}")
        print(f"    Device — completers: mobile {c_mobile}, desktop {c_desktop}, tablet {c_tablet}")

        # 5e. Play time
        a_times = [p['solve_time'] for p in abandoners if p['solve_time'] > 0]
        c_times = [p['solve_time'] for p in completers if p['solve_time'] > 0]
        if a_times:
            print(f"\n    Play time — abandoners: avg {sum(a_times)/len(a_times):.0f}s, median {median(a_times):.0f}s")
        if c_times:
            print(f"    Play time — completers: avg {sum(c_times)/len(c_times):.0f}s, median {median(c_times):.0f}s")

    # ═══════════════════════════════════════════════════════════════════
    # 6. PHASE 2 (RELINK) ANALYSIS
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n\n{SEP}")
    print("6. PHASE 2 (RELINK) ANALYSIS")
    print(SEP)

    for d in DATES:
        pp = players_by_date[d]
        label = DATE_LABELS[d]
        relinkers = [p for p in pp if p['relink_guesses']]

        if not relinkers:
            continue

        print(f"\n  ── {label}: {len(relinkers)}/{len(pp)} players reached Phase 2 {'─' * 20}")

        total_guesses = sum(len(p['relink_guesses']) for p in relinkers)
        correct = sum(sum(1 for g in p['relink_guesses'] if g['is_correct']) for p in relinkers)
        wrong = total_guesses - correct
        print(f"    Total relink guesses: {total_guesses} (correct: {correct}, wrong: {wrong})")
        print(f"    Success rate: {pct(correct, total_guesses)}")

        # Wrong tile combos
        wrong_combos = Counter()
        for p in relinkers:
            for g in p['relink_guesses']:
                if not g['is_correct']:
                    wrong_combos[g['tiles']] += 1
        if wrong_combos:
            print(f"    Wrong tile combinations:")
            for combo, cnt in wrong_combos.most_common(5):
                print(f"      {combo}: {cnt}x")

        # Attempts per player
        attempt_counts = Counter()
        for p in relinkers:
            n = len(p['relink_guesses'])
            attempt_counts[n] += 1
        print(f"    Attempts per player:")
        for n in sorted(attempt_counts):
            print(f"      {n} attempt{'s' if n > 1 else ''}: {attempt_counts[n]} players")

    # ═══════════════════════════════════════════════════════════════════
    # 7. TIMING PATTERNS
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n\n{SEP}")
    print("7. TIMING PATTERNS")
    print(SEP)

    print(f"\n  {'Metric':<35}", end='')
    for d in DATES:
        print(f" {DATE_LABELS[d]:>10}", end='')
    print()
    print("  " + "-" * (35 + 11 * len(DATES)))

    all_correct_gaps = {}
    all_wrong_gaps = {}
    all_recovery = {}
    all_post_wrong_gaps = {}

    for d in DATES:
        pp = players_by_date[d]
        cg, wg = [], []
        rec_correct, rec_wrong = 0, 0
        pwg = []
        for p in pp:
            prev = None
            for g in p['real_guesses']:
                if prev:
                    gap = (g['ts'] - prev['ts']).total_seconds()
                    if g['is_correct']:
                        cg.append(gap)
                    else:
                        wg.append(gap)
                    if not prev['is_correct']:
                        pwg.append(gap)
                        if g['is_correct']:
                            rec_correct += 1
                        else:
                            rec_wrong += 1
                prev = g
        all_correct_gaps[d] = cg
        all_wrong_gaps[d] = wg
        rec_total = rec_correct + rec_wrong
        all_recovery[d] = (rec_correct, rec_total)
        all_post_wrong_gaps[d] = pwg

    def row_metric(label, fn):
        print(f"  {label:<35}", end='')
        for d in DATES:
            val = fn(d)
            print(f" {val:>10}", end='')
        print()

    row_metric("Correct gap (median)", lambda d: f"{median(all_correct_gaps[d]):.1f}s" if all_correct_gaps[d] else "n/a")
    row_metric("Correct gap (avg)", lambda d: f"{sum(all_correct_gaps[d])/len(all_correct_gaps[d]):.1f}s" if all_correct_gaps[d] else "n/a")
    row_metric("Wrong gap (median)", lambda d: f"{median(all_wrong_gaps[d]):.1f}s" if all_wrong_gaps[d] else "n/a")
    row_metric("Wrong gap (avg)", lambda d: f"{sum(all_wrong_gaps[d])/len(all_wrong_gaps[d]):.1f}s" if all_wrong_gaps[d] else "n/a")
    row_metric("Recovery rate", lambda d: pct(all_recovery[d][0], all_recovery[d][1]))
    row_metric("Avg time after wrong", lambda d: f"{sum(all_post_wrong_gaps[d])/len(all_post_wrong_gaps[d]):.1f}s" if all_post_wrong_gaps[d] else "n/a")
    row_metric("Median time after wrong", lambda d: f"{median(all_post_wrong_gaps[d]):.1f}s" if all_post_wrong_gaps[d] else "n/a")

    # Solve time: winners vs losers
    print(f"\n  Solve time distribution:")
    print(f"  {'':>35}", end='')
    for d in DATES:
        print(f" {DATE_LABELS[d]:>10}", end='')
    print()
    print("  " + "-" * (35 + 11 * len(DATES)))

    row_metric("Winner avg solve time", lambda d: f"{sum(p['solve_time'] for p in players_by_date[d] if p['outcome']=='WON' and p['solve_time']>0) / max(1, sum(1 for p in players_by_date[d] if p['outcome']=='WON' and p['solve_time']>0)):.0f}s")
    row_metric("Winner median solve time", lambda d: f"{median([p['solve_time'] for p in players_by_date[d] if p['outcome']=='WON' and p['solve_time']>0]):.0f}s")
    row_metric("Loser avg solve time", lambda d: f"{sum(p['solve_time'] for p in players_by_date[d] if p['outcome']=='LOST' and p['solve_time']>0) / max(1, sum(1 for p in players_by_date[d] if p['outcome']=='LOST' and p['solve_time']>0)):.0f}s")
    row_metric("Loser median solve time", lambda d: f"{median([p['solve_time'] for p in players_by_date[d] if p['outcome']=='LOST' and p['solve_time']>0]):.0f}s")

    # ═══════════════════════════════════════════════════════════════════
    # 8. CONFUSION CLUSTERS
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n\n{SEP}")
    print("8. CONFUSION CLUSTERS (2+ wrong guesses)")
    print(SEP)

    for d in DATES:
        pp = players_by_date[d]
        label = DATE_LABELS[d]
        confused = [p for p in pp if p['num_wrong'] >= 2]

        if not confused:
            continue

        print(f"\n  ── {label} ({len(confused)} players with 2+ wrong) {'─' * 30}")
        for p in confused:
            outcome = p['outcome']
            city = p['city'] or ''
            seq = ' -> '.join(f"R{g['row']}:'{g['word']}'" for g in p['wrong_imposters'])
            print(f"    {city}, {p['country']} ({outcome}): {seq}")

    # ═══════════════════════════════════════════════════════════════════
    # 9. PLAYER JOURNEYS
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n\n{SEP}")
    print("9. PLAYER JOURNEYS (STEP-BY-STEP)")
    print(SEP)

    for d in DATES:
        pp = players_by_date[d]
        label = DATE_LABELS[d]

        print(f"\n  {'=' * 70}")
        print(f"  {label} ({len(pp)} players)")
        print(f"  {'=' * 70}")

        for i, p in enumerate(pp, 1):
            print(f"\n  {'─' * 60}")
            print(f"  Player {i}: {p['city']}, {p['country']} | {p['device']} ({p['browser']})")
            print(f"    Outcome: {p['outcome']} | Wrong: {p['num_wrong']} | Total guesses: {p['total_guesses']}")
            extras = []
            if p['streak'] != '?':
                extras.append(f"Streak: {p['streak']}")
            if p['days_since'] != '?':
                extras.append(f"Days since first visit: {p['days_since']}")
            if extras:
                print(f"    {' | '.join(extras)}")

            all_g = sorted(p['real_guesses'] + p['relink_guesses'], key=lambda g: g['ts'])
            prev_ts = None
            for g in all_g:
                gap = f"(+{(g['ts'] - prev_ts).total_seconds():.1f}s) " if prev_ts else ""
                ts_str = g['ts'].strftime('%H:%M:%S')
                if g['phase'] == 'relink':
                    mark = '+' if g['is_correct'] else 'X'
                    print(f"      [{ts_str}] {gap}RELINK: {g['tiles']} -> {mark}")
                else:
                    mark = '+' if g['is_correct'] else 'X'
                    lives_str = f"(lives: {g['attempts']})" if g['attempts'] else ''
                    print(f"      [{ts_str}] {gap}Row {g['row']}: '{g['word']}' {lives_str} -> {mark}")
                prev_ts = g['ts']

            if p['solve_time'] > 0:
                print(f"    Solve time: {p['solve_time']:.0f}s")

    # ═══════════════════════════════════════════════════════════════════
    # PDL ANALYSIS (if metadata provided)
    # ═══════════════════════════════════════════════════════════════════
    if pdl_data:
        print(f"\n\n{SEP}")
        print("10. PDL ANALYSIS (Puzzle Design Language)")
        print(SEP)

        # Aggregate by axis values
        axes = ['connection_type', 'knowledge_axis', 'manipulation_axis', 'abstraction_axis']

        for axis_name in axes:
            print(f"\n  ── By {axis_name} {'─' * 50}")
            agg = defaultdict(lambda: [0, 0, 0])  # [first_try, never_correct, total]

            for d in DATES:
                if d not in pdl_data:
                    continue
                pp = players_by_date[d]
                for row_str, meta in pdl_data[d].items():
                    row = row_str
                    val = meta.get(axis_name, 'Unknown')
                    for p in pp:
                        seq = [g for g in p['real_guesses'] if g['row'] == row]
                        if not seq:
                            continue
                        agg[val][2] += 1
                        if seq[0]['is_correct']:
                            agg[val][0] += 1
                        elif not any(g['is_correct'] for g in seq):
                            agg[val][1] += 1

            print(f"      {'Value':<30} {'1st-try%':>10} {'Never%':>10} {'n':>6}")
            print(f"      {'─' * 58}")
            for val, (ft, nc, tot) in sorted(agg.items(), key=lambda x: -x[1][0]/max(1, x[1][2])):
                ft_pct = f"{ft/tot*100:.0f}%" if tot else "n/a"
                nc_pct = f"{nc/tot*100:.0f}%" if tot else "n/a"
                print(f"      {val:<30} {ft_pct:>10} {nc_pct:>10} {tot:>6}")

        # Cross-tabulation: manipulation x abstraction
        print(f"\n  ── Cross-tab: manipulation × abstraction (first-try %) {'─' * 20}")
        cross = defaultdict(lambda: [0, 0])  # [first_try, total]
        for d in DATES:
            if d not in pdl_data:
                continue
            pp = players_by_date[d]
            for row_str, meta in pdl_data[d].items():
                row = row_str
                m = meta.get('manipulation_axis', 'Unknown')
                a = meta.get('abstraction_axis', 'Unknown')
                for p in pp:
                    seq = [g for g in p['real_guesses'] if g['row'] == row]
                    if not seq:
                        continue
                    cross[(m, a)][1] += 1
                    if seq[0]['is_correct']:
                        cross[(m, a)][0] += 1

        all_m = sorted(set(k[0] for k in cross))
        all_a = sorted(set(k[1] for k in cross))
        header = f"      {'':20}" + ''.join(f" {a[:12]:>12}" for a in all_a)
        print(header)
        for m in all_m:
            row_str = f"      {m[:20]:20}"
            for a in all_a:
                ft, tot = cross.get((m, a), [0, 0])
                cell = f"{ft/tot*100:.0f}%" if tot else "-"
                row_str += f" {cell:>12}"
            print(row_str)

        # Vertical inference by connection type
        print(f"\n  ── Vertical inference benefit by connection type {'─' * 25}")
        vi = defaultdict(lambda: [0, 0, 0, 0])  # early_correct, early_total, late_correct, late_total
        for d in DATES:
            if d not in pdl_data:
                continue
            pp = players_by_date[d]
            for row_str, meta in pdl_data[d].items():
                row = row_str
                ct = meta.get('connection_type', 'Unknown')
                for p in pp:
                    order = p['row_order']
                    if row not in order:
                        continue
                    pos = order.index(row)
                    seq = [g for g in p['real_guesses'] if g['row'] == row]
                    if not seq:
                        continue
                    is_early = pos < 2
                    if is_early:
                        vi[ct][1] += 1
                        if seq[0]['is_correct']:
                            vi[ct][0] += 1
                    else:
                        vi[ct][3] += 1
                        if seq[0]['is_correct']:
                            vi[ct][2] += 1

        print(f"      {'Type':<30} {'Early%':>10} {'Late%':>10} {'Delta':>8}")
        print(f"      {'─' * 60}")
        for ct, (ec, et, lc, lt) in sorted(vi.items()):
            e_pct = ec / et * 100 if et else 0
            l_pct = lc / lt * 100 if lt else 0
            delta = l_pct - e_pct
            print(f"      {ct:<30} {e_pct:>9.0f}% {l_pct:>9.0f}% {delta:>+7.0f}pp")

    print(f"\n\n{SEP}")
    print("END OF ANALYSIS")
    print(SEP)

sys.stdout = sys.__stdout__
print(f"Output written to {OUTPUT_FILE}")
