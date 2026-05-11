"""Check: do WON players without relink_trajectory have zero relink guesses,
or do they have some but the final one is missing?"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'relink', 'scripts'))
from lib.data import load_behaviour, match_events, build_players
from collections import Counter

RAW_DIR = os.path.join(os.path.dirname(__file__), 'raw')
target_dates = {'2026-05-09'}

print("Loading May 9 data...")
sessions_by_date, events_by_date, ALL_DATES = load_behaviour(RAW_DIR, target_dates)

sessions = {}
for d, sd in sessions_by_date.items():
    sessions.update(sd)
events = []
for d, el in events_by_date.items():
    events.extend(el)

event_sessions = match_events(sessions, events)
players = build_players(sessions, event_sessions)

# Filter to May 9's canonical level
may9_players = [p for p in players if p['level_id'] == 'mouaw3d1-g9ugg95']
print(f"May 9 players (canonical): {len(may9_players)}")

won_players = [p for p in may9_players if p['outcome'] == 'WON']
print(f"WON players: {len(won_players)}")

won_with_rt = [p for p in won_players if p.get('relink_trajectory')]
won_without_rt = [p for p in won_players if not p.get('relink_trajectory')]
print(f"  With relink_trajectory: {len(won_with_rt)}")
print(f"  Without relink_trajectory: {len(won_without_rt)}")

# For those without trajectory: do they have any relink guesses at all?
print(f"\nWON without trajectory - relink_guesses count:")
rg_counts = Counter(len(p['relink_guesses']) for p in won_without_rt)
for count, n in sorted(rg_counts.items()):
    print(f"  {count} relink guesses: {n} players")

# For those WITH trajectory: how many relink guesses do they have?
print(f"\nWON with trajectory - relink_guesses count:")
rg_counts2 = Counter(len(p['relink_guesses']) for p in won_with_rt)
for count, n in sorted(rg_counts2.items()):
    print(f"  {count} relink guesses: {n} players")

# Check: do WON-without-rt players have imposters guesses that suggest they solved all 4 rows?
print(f"\nWON without trajectory - rows completed count:")
rc_counts = Counter(len(p['rows_completed']) for p in won_without_rt)
for count, n in sorted(rc_counts.items()):
    print(f"  {count} rows completed: {n} players")

# Check: what about phase2TileCount for this puzzle?
import json
with open('relink/save-data/l44.json') as f:
    puzzle = json.load(f)
print(f"\nPuzzle phase2TileCount: {puzzle.get('board', {}).get('phase2TileCount', 'NOT SET')}")
print(f"Relink tiles marked isRelink:")
for row in puzzle.get('rows', []):
    for tile in row['tiles']:
        if tile.get('isRelink'):
            print(f"  {tile['text']} (row {row['position']})")
