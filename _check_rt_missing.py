"""Why don't WON players get a relink_trajectory?"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'relink', 'scripts'))
from lib.data import load_behaviour, match_events, build_players
from collections import Counter

RAW_DIR = os.path.join(os.path.dirname(__file__), 'raw')
target_dates = {'2026-05-09'}
sessions_by_date, events_by_date, ALL_DATES = load_behaviour(RAW_DIR, target_dates)
sessions = {}
for d, sd in sessions_by_date.items():
    sessions.update(sd)
events = []
for d, el in events_by_date.items():
    events.extend(el)
event_sessions = match_events(sessions, events)
players = build_players(sessions, event_sessions)
may9 = [p for p in players if p['level_id'] == 'mouaw3d1-g9ugg95']
won_no_rt = [p for p in may9 if p['outcome'] == 'WON' and not p.get('relink_trajectory')]

# Check lives remaining (4 - num_wrong)
lives_dist = Counter()
for p in won_no_rt:
    lives_remaining = 4 - p['num_wrong']
    lives_dist[lives_remaining] += 1

print("Lives remaining after imposters (WON, no relink_trajectory):")
for k, v in sorted(lives_dist.items()):
    print(f"  {k} lives: {v}")

# The relink_trajectory code builds 'lives' from the trajectory loop,
# not from num_wrong. Let me check what 'lives' would be after trajectory.
# In build_players, the trajectory loop decrements lives for each wrong guess.
# If the trajectory loop breaks early (len(solved_so_far) >= 4), lives is correct.
# But if the trajectory doesn't process all wrongs...

# Actually - re-read the code: relink_trajectory is built if 'relink_guesses and lives > 0'
# where 'lives' is the variable after the trajectory loop. If a wrong guess in imposters
# sets lives to 0 AND the row is resolved, the loop breaks. But for WON players lives
# should never reach 0.

# Let me check: are there WON players with >4 wrong guesses? (session cross-contamination!)
print("\nWrong guesses distribution (WON, no relink_trajectory):")
wrong_dist = Counter()
for p in won_no_rt:
    wrong_dist[p['num_wrong']] += 1
for k, v in sorted(wrong_dist.items()):
    print(f"  {k} wrongs: {v}")

# Sample a player with many wrong guesses
high_wrong = [p for p in won_no_rt if p['num_wrong'] >= 4]
print(f"\nWON players with >=4 wrong imposters guesses (no rt): {len(high_wrong)}")
if high_wrong:
    p = high_wrong[0]
    print(f"\n  Sample: {p['num_wrong']} wrongs, {len(p['relink_guesses'])} relink guesses")
    print(f"  Trajectory:")
    for t in p['trajectory']:
        print(f"    pos={t['position']} row={t['row']} wrongs={t['wrong_count']} survived={t['survived']}")

# Sample a "normal" player (0-3 wrongs) without rt
normal_no_rt = [p for p in won_no_rt if p['num_wrong'] <= 3]
if normal_no_rt:
    p = normal_no_rt[0]
    print(f"\n  Normal sample: {p['num_wrong']} wrongs, {len(p['relink_guesses'])} relink guesses")
    print(f"  rows_completed: {p['rows_completed']}")
    print(f"  Trajectory ({len(p['trajectory'])} entries):")
    for t in p['trajectory']:
        print(f"    pos={t['position']} row={t['row']} wrongs={t['wrong_count']} survived={t['survived']}")
    # Check: what does the relink_trajectory code see?
    # It checks 'relink_guesses and lives > 0'
    # Let's simulate:
    lives = 4
    solved = set()
    for g in sorted(p['real_guesses'], key=lambda g: g['ts']):
        if len(solved) >= 4:
            break
        if g['is_correct']:
            solved.add(g['row'])
        else:
            lives -= 1
            if lives <= 0:
                break
    print(f"  Simulated lives after imposters: {lives}")
    print(f"  Simulated solved rows: {len(solved)}")
    print(f"  Would build relink_trajectory: {bool(p['relink_guesses'] and lives > 0)}")
