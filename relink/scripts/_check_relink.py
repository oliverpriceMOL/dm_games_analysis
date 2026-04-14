"""Quick diagnostic: inspect relink guess sequences for tile-swapping pattern."""
import os, sys, csv, ast, glob
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
RAW_DIR = os.path.join(DATA_DIR, 'raw')

# Collect relink-phase events grouped by session (via country+date bucket then matching)
# Simpler: group by event ID proximity — just collect all relink events per unique client session
# Events don't have session ID, but we can group by (country, city, date-ish)
# Actually events DO have an 'id' field which is the event ID, not session.
# Let's group by proximity: same country+city, within 5 minutes

events_by_file = []
for fname in sorted(glob.glob(os.path.join(RAW_DIR, 'daily-mail-events*.csv'))):
    with open(fname) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['name'] != 'relink_guess_submitted':
                continue
            props = ast.literal_eval(row['properties'])
            if props.get('phase') != 'relink':
                continue
            att = props.get('attempts_remaining', '')
            try:
                if int(att) > 4:
                    continue
            except (ValueError, TypeError):
                continue
            events_by_file.append({
                'id': row['id'],
                'ts': row['created_at'],
                'country': row.get('country', ''),
                'city': row.get('city', ''),
                'correct': props.get('is_correct') == 'true',
                'att_rem': int(att),
                'tiles': props.get('selected_tile_ids', ''),
            })

# Group into sessions by looking at att_rem sequences
# A session's relink attempts share same country+city and att_rem decrements
# Simple: group by (country, city, date), then split by att_rem resets
from datetime import datetime

def parse_ts(s):
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except:
        return None

events_by_file.sort(key=lambda e: e['ts'])

# Group by (country, city, date-hour)
buckets = defaultdict(list)
for e in events_by_file:
    ts = parse_ts(e['ts'])
    if not ts:
        continue
    key = (e['country'], e['city'], ts.strftime('%Y-%m-%d %H'))
    buckets[key].append(e)

# Within each bucket, split into sessions by time gaps > 2 min
sessions = []
for key, evts in buckets.items():
    evts.sort(key=lambda e: e['ts'])
    current = [evts[0]]
    for e in evts[1:]:
        t1 = parse_ts(current[-1]['ts'])
        t2 = parse_ts(e['ts'])
        if t2 and t1 and (t2 - t1).total_seconds() < 120:
            current.append(e)
        else:
            sessions.append(current)
            current = [e]
    sessions.append(current)

# Show multi-guess sessions to see tile-swapping
print("=== MULTI-GUESS RELINK SESSIONS (tile swapping analysis) ===\n")
shown = 0
swaps_one = 0
swaps_total = 0
for sess in sessions:
    if len(sess) < 2:
        continue
    print(f"Session ({sess[0]['country']}/{sess[0]['city']}): {len(sess)} guesses")
    prev_tiles = None
    for i, g in enumerate(sess):
        tiles = set(g['tiles'].split(',')) if g['tiles'] else set()
        n = len(tiles)
        overlap = len(tiles & prev_tiles) if prev_tiles else '-'
        changed = len(tiles - prev_tiles) if prev_tiles else '-'
        print(f"  {i}: {g['tiles']} ({n}t) correct={g['correct']} att_rem={g['att_rem']} | overlap={overlap} changed={changed}")
        if prev_tiles and len(tiles) == len(prev_tiles):
            swaps_total += 1
            if changed == 1:
                swaps_one += 1
        prev_tiles = tiles
    print()
    shown += 1
    if shown >= 20:
        break

print(f"\n=== TILE SWAPPING SUMMARY ===")
print(f"Multi-guess transitions: {swaps_total}")
print(f"Swapped exactly 1 tile: {swaps_one} ({100*swaps_one/swaps_total:.0f}%)" if swaps_total else "No multi-guess data")
