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
OUTPUT_FILE = os.path.join(RELINK_DIR, 'outputs', 'cross-date-failures.txt')

# DATES, EARLY, LATE will be discovered dynamically from data

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

# ── Load sessions from all files (later files win on dedup) ──
raw_sessions = {}
for sf in SESSION_FILES:
    with open(sf) as f:
        for row in csv.DictReader(f):
            raw_sessions[row['id']] = row  # last file wins

all_sessions = {}
session_dates = set()
for sid, row in raw_sessions.items():
    dur = int(row['duration'])
    country = row['country']
    city = row.get('city', '')
    is_bot = (country in ('NL', 'IE') and dur <= 10) or dur <= 2
    is_dev = city == 'Västerås' and country == 'SE'
    if is_bot or is_dev:
        continue
    d = row['created_at'][:10]
    session_dates.add(d)
    all_sessions[sid] = row

# ── Load relink events from all files (later files win on dedup) ──
raw_events = {}
for ef in EVENT_FILES:
    with open(ef) as f:
        for row in csv.DictReader(f):
            raw_events[row['id']] = row  # last file wins

all_relink_events = []
event_dates = set()
for row in raw_events.values():
    props = parse_props(row.get('properties', '{}'))
    if props.get('game_id') != 'relink':
        continue
    row['_ts'] = parse_ts(row['created_at'])
    row['_props'] = props
    d = row['created_at'][:10]
    event_dates.add(d)
    all_relink_events.append(row)

DATES = sorted(session_dates | event_dates)
# First 3 dates = EARLY, rest = LATE (consistent with original 3/4 split)
EARLY = DATES[:3]
LATE  = DATES[3:]

# Generate labels from dates
MONTH_NAMES = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',
               7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
def make_label(d):
    parts = d.split('-')
    return f"{MONTH_NAMES[int(parts[1])]} {int(parts[2])}"

# ── Match events to sessions (optimised) ──
# Group events by (country, date) for fast lookup
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

# ── Build player outcomes per puzzle_date ──
# player_key = (city, country, device)
# outcomes[player_key][puzzle_date] = 'WON' | 'LOST' | 'ABANDONED'

outcomes = defaultdict(dict)  # player_key -> {puzzle_date: outcome}

for sid, evts in all_event_sessions.items():
    sess = all_sessions[sid]
    dur = int(sess['duration'])
    country = sess['country']
    if (country in ('NL', 'IE') and dur <= 10) or dur <= 2:
        continue

    # Check for tutorial events only
    has_real = False
    for ev in evts:
        if ev['name'] == 'relink_guess_submitted':
            att = ev['_props'].get('attempts_remaining', '')
            try:
                if int(att) <= 4:
                    has_real = True
                    break
            except (ValueError, TypeError):
                continue
    if not has_real:
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

    if not puzzle_date:
        puzzle_date = sess['created_at'][:10]
    if not outcome:
        outcome = 'ABANDONED'

    # Tester filter: abandon with 0 wrong guesses = not a real player
    num_wrong = sum(1 for ev in evts if ev['name'] == 'relink_guess_submitted'
                    and ev['_props'].get('is_correct') == 'false'
                    and int(ev['_props'].get('attempts_remaining', '999')) <= 4)
    if outcome == 'ABANDONED' and num_wrong == 0:
        continue

    player_key = (sess['city'], sess['country'], sess['device'])
    # If a player has multiple sessions for same puzzle, take the best outcome
    existing = outcomes[player_key].get(puzzle_date)
    if existing == 'WON':
        pass  # already won, keep it
    else:
        outcomes[player_key][puzzle_date] = outcome

# ── Analysis ──
with open(OUTPUT_FILE, 'w') as out:
    sys.stdout = out

    print("=" * 80)
    print("CROSS-DATE FAILURE ANALYSIS")
    print(f"Were {make_label(LATE[0])}-{make_label(LATE[-1])} losers more likely to have failed on {make_label(EARLY[0])} - {make_label(EARLY[-1])}?")
    print("=" * 80)
    print(f"\nPlayer fingerprint: (city, country, device)")
    print(f"Total unique players across all dates: {len(outcomes)}")

    # ── 1. Overview: outcomes per date ──
    print("\n\n--- 1. OUTCOMES PER PUZZLE DATE ---\n")
    labels = {d: make_label(d) for d in DATES}
    print(f"  {'Date':<10} {'Players':>8} {'Won':>8} {'Lost':>8} {'Aband.':>8} {'Solve%':>8}")
    for d in DATES:
        players_on_d = [(k, v[d]) for k, v in outcomes.items() if d in v]
        total = len(players_on_d)
        won = sum(1 for _, o in players_on_d if o == 'WON')
        lost = sum(1 for _, o in players_on_d if o == 'LOST')
        aband = sum(1 for _, o in players_on_d if o == 'ABANDONED')
        pct = f"{won/total*100:.0f}%" if total else "-"
        print(f"  {labels[d]:<10} {total:>8} {won:>8} {lost:>8} {aband:>8} {pct:>8}")

    # ── 2. Late losers: did they play early? ──
    early_label = f"{make_label(EARLY[0])}-{make_label(EARLY[-1])}"
    late_label = f"{make_label(LATE[0])}-{make_label(LATE[-1])}"
    print(f"\n\n--- 2. LATE LOSERS ({late_label}): DID THEY PLAY {early_label}? ---\n")

    late_losers = set()
    for key, puzzle_outcomes in outcomes.items():
        for d in LATE:
            if puzzle_outcomes.get(d) == 'LOST':
                late_losers.add(key)
                break

    late_winners = set()
    for key, puzzle_outcomes in outcomes.items():
        lost_late = any(puzzle_outcomes.get(d) == 'LOST' for d in LATE)
        won_late = any(puzzle_outcomes.get(d) == 'WON' for d in LATE)
        if won_late and not lost_late:
            late_winners.add(key)

    print(f"  Players who LOST at least once on {late_label}: {len(late_losers)}")
    print(f"  Players who only WON on {late_label} (never lost): {len(late_winners)}")

    # For late losers, check early history
    def early_history(player_set, label):
        played_early = 0
        early_outcomes = Counter()
        early_detail = Counter()  # (date, outcome) combos
        for key in player_set:
            po = outcomes[key]
            played_any_early = False
            for d in EARLY:
                if d in po:
                    played_any_early = True
                    early_detail[(labels[d], po[d])] += 1
            if played_any_early:
                played_early += 1
                # Summarise their early record
                wins = sum(1 for d in EARLY if po.get(d) == 'WON')
                losses = sum(1 for d in EARLY if po.get(d) == 'LOST')
                abandons = sum(1 for d in EARLY if po.get(d) == 'ABANDONED')
                if losses > 0:
                    early_outcomes['Had early loss'] += 1
                if wins > 0 and losses == 0:
                    early_outcomes['Only early wins'] += 1
                if wins == 0 and losses == 0 and abandons > 0:
                    early_outcomes['Only early abandons'] += 1
        return played_early, early_outcomes, early_detail

    print(f"\n  --- Late LOSERS ({late_label}) early history ---")
    pe, eo, ed = early_history(late_losers, "Late losers")
    not_played = len(late_losers) - pe
    print(f"  Played {early_label}:       {pe}/{len(late_losers)} ({pe/len(late_losers)*100:.0f}%)")
    print(f"  Did NOT play {early_label}:  {not_played}/{len(late_losers)} ({not_played/len(late_losers)*100:.0f}%)")
    for k, v in eo.most_common():
        print(f"    {k}: {v}/{pe} ({v/pe*100:.0f}%)" if pe else f"    {k}: {v}")

    print(f"\n  --- Late WINNERS ({late_label}) early history ---")
    pe2, eo2, ed2 = early_history(late_winners, "Late winners")
    not_played2 = len(late_winners) - pe2
    if late_winners:
        print(f"  Played {early_label}:       {pe2}/{len(late_winners)} ({pe2/len(late_winners)*100:.0f}%)")
        print(f"  Did NOT play {early_label}:  {not_played2}/{len(late_winners)} ({not_played2/len(late_winners)*100:.0f}%)")
        for k, v in eo2.most_common():
            print(f"    {k}: {v}/{pe2} ({v/pe2*100:.0f}%)" if pe2 else f"    {k}: {v}")

    # ── 3. Comparison: early failure rates ──
    print("\n\n--- 3. EARLY FAILURE RATE COMPARISON ---\n")
    print(f"  Among players who played BOTH early ({early_label}) AND late ({late_label}):")

    # Players who played both periods
    both_losers_early = 0
    both_losers_total = 0
    both_winners_early = 0
    both_winners_total = 0

    for key in late_losers:
        po = outcomes[key]
        if any(d in po for d in EARLY):
            both_losers_total += 1
            if any(po.get(d) == 'LOST' for d in EARLY):
                both_losers_early += 1

    for key in late_winners:
        po = outcomes[key]
        if any(d in po for d in EARLY):
            both_winners_total += 1
            if any(po.get(d) == 'LOST' for d in EARLY):
                both_winners_early += 1

    if both_losers_total:
        print(f"\n  Late LOSERS who also LOST early:  {both_losers_early}/{both_losers_total} ({both_losers_early/both_losers_total*100:.0f}%)")
    if both_winners_total:
        print(f"  Late WINNERS who also LOST early: {both_winners_early}/{both_winners_total} ({both_winners_early/both_winners_total*100:.0f}%)")

    if both_losers_total and both_winners_total:
        loser_pct = both_losers_early / both_losers_total * 100
        winner_pct = both_winners_early / both_winners_total * 100
        print(f"\n  => Late losers were {loser_pct:.0f}% likely to have lost early")
        print(f"  => Late winners were {winner_pct:.0f}% likely to have lost early")
        if loser_pct > winner_pct:
            print(f"  => Late losers were {loser_pct/winner_pct:.1f}x more likely to have also lost early")
        elif winner_pct > loser_pct:
            print(f"  => Late winners were actually MORE likely to have lost early")

    # ── 4. Per-date breakdown for late losers ──
    print("\n\n--- 4. LATE LOSERS: DETAILED EARLY HISTORY ---\n")
    print(f"  For each of the {len(late_losers)} late losers, what happened on each early date:\n")
    early_hdrs = ''.join(f" {make_label(d):>8}" for d in EARLY)
    late_hdrs = ''.join(f" {make_label(d):>8}" for d in LATE)
    print(f"  {'Player (city, country, device)':<45}{early_hdrs} |{late_hdrs}")
    print("  " + "-" * (45 + 9 * len(DATES) + 2))

    # Sort by number of early losses descending
    sorted_losers = sorted(late_losers,
                           key=lambda k: sum(1 for d in EARLY if outcomes[k].get(d) == 'LOST'),
                           reverse=True)

    for key in sorted_losers:
        po = outcomes[key]
        city, country, device = key
        name = f"{city}, {country} ({device})"
        if len(name) > 43:
            name = name[:40] + "..."
        cols = []
        for d in DATES:
            o = po.get(d, '-')
            if o == 'WON':
                cols.append('W')
            elif o == 'LOST':
                cols.append('L')
            elif o == 'ABANDONED':
                cols.append('A')
            else:
                cols.append('-')
        early_cols = ''.join(f"{c:>8}" for c in cols[:len(EARLY)])
        late_cols = ''.join(f"{c:>8}" for c in cols[len(EARLY):])
        print(f"  {name:<45} {early_cols} | {late_cols}")

    # ── 5. Streak analysis ──
    print("\n\n--- 5. LOSING STREAKS ---\n")
    streak_counts = Counter()
    for key, po in outcomes.items():
        max_streak = 0
        current = 0
        for d in DATES:
            if po.get(d) == 'LOST':
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        if max_streak > 0:
            streak_counts[max_streak] += 1

    print(f"  {'Max consecutive losses':>25} {'Players':>10}")
    for streak in sorted(streak_counts.keys()):
        print(f"  {streak:>25} {streak_counts[streak]:>10}")

    # ── 6. Retention: did early losers come back? ──
    print("\n\n--- 6. RETENTION: DID EARLY LOSERS COME BACK? ---\n")
    early_losers = set()
    for key, po in outcomes.items():
        if any(po.get(d) == 'LOST' for d in EARLY):
            early_losers.add(key)

    early_only_winners = set()
    for key, po in outcomes.items():
        if any(po.get(d) == 'WON' for d in EARLY) and not any(po.get(d) == 'LOST' for d in EARLY):
            early_only_winners.add(key)

    came_back_losers = sum(1 for k in early_losers if any(d in outcomes[k] for d in LATE))
    came_back_winners = sum(1 for k in early_only_winners if any(d in outcomes[k] for d in LATE))

    if early_losers:
        print(f"  Early losers (lost {early_label}): {len(early_losers)}")
        print(f"    Came back {late_label}:   {came_back_losers}/{len(early_losers)} ({came_back_losers/len(early_losers)*100:.0f}%)")
    if early_only_winners:
        print(f"  Early-only winners (won {early_label}, never lost): {len(early_only_winners)}")
        print(f"    Came back {late_label}:   {came_back_winners}/{len(early_only_winners)} ({came_back_winners/len(early_only_winners)*100:.0f}%)")

    if early_losers and early_only_winners and came_back_losers and came_back_winners:
        l_pct = came_back_losers / len(early_losers) * 100
        w_pct = came_back_winners / len(early_only_winners) * 100
        print(f"\n  => Early losers returned at {l_pct:.0f}% vs early winners at {w_pct:.0f}%")

    print("\n" + "=" * 80)
    print("END OF CROSS-DATE FAILURE ANALYSIS")
    print("=" * 80)

sys.stdout = sys.__stdout__
print(f"Output written to {OUTPUT_FILE}")
