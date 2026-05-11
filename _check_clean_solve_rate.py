"""Compute solve rates directly from level_completed events (no session matching).
Also detect and deduplicate potential duplicate completions."""
import csv
import ast
from collections import defaultdict

RAW_DIR = 'raw'
target_dates = {'2026-05-07', '2026-05-08', '2026-05-09', '2026-05-10', '2026-05-11'}

# Collect all level_completed events for relink
completions = []
with open('raw/daily-mail-events-2026-04-19_to_2026-05-11.csv') as f:
    for row in csv.DictReader(f):
        if row['name'] != 'level_completed':
            continue
        d = row['created_at'][:10]
        if d not in target_dates:
            continue
        props = row.get('properties', '')
        if "'game_id':'relink'" not in props and "'game_id': 'relink'" not in props:
            continue
        # Extract is_won and puzzle_date from properties string
        is_won = None
        puzzle_date = None
        level_id = None
        if "'is_won':'true'" in props or "'is_won': 'true'" in props:
            is_won = True
        elif "'is_won':'false'" in props or "'is_won': 'false'" in props:
            is_won = False
        # Extract puzzle_date
        for pattern in ["'puzzle_date':'", "'puzzle_date': '"]:
            idx = props.find(pattern)
            if idx >= 0:
                start = idx + len(pattern)
                end = props.find("'", start)
                puzzle_date = props[start:end]
                break
        # Extract level_id
        for pattern in ["'level_id':'", "'level_id': '"]:
            idx = props.find(pattern)
            if idx >= 0:
                start = idx + len(pattern)
                end = props.find("'", start)
                level_id = props[start:end]
                break
        # Skip tutorial (attempts_remaining > 4)
        if "'attempts_remaining':'999'" in props or "'attempts_remaining': '999'" in props:
            continue
            
        if is_won is None:
            continue
            
        completions.append({
            'id': row['id'],
            'ts': row['created_at'],
            'date': d,
            'puzzle_date': puzzle_date or d,
            'city': row['city'],
            'country': row['country'],
            'region': row.get('region', ''),
            'is_won': is_won,
            'level_id': level_id,
        })

print(f"Total level_completed events (non-tutorial): {len(completions)}")

# Group by puzzle_date
by_date = defaultdict(list)
for c in completions:
    by_date[c['puzzle_date']].append(c)

print(f"\n{'='*60}")
print("RAW COUNTS (no deduplication)")
print(f"{'='*60}")
print(f"{'Date':<12} {'Won':>6} {'Lost':>6} {'Total':>7} {'Solve%':>7}")
for d in sorted(by_date.keys()):
    evts = by_date[d]
    won = sum(1 for e in evts if e['is_won'])
    lost = sum(1 for e in evts if not e['is_won'])
    total = won + lost
    pct = 100 * won / total if total else 0
    print(f"{d:<12} {won:>6} {lost:>6} {total:>7} {pct:>6.1f}%")

# Now deduplicate: look for events from same city+country within 5 seconds
# with same outcome - these are likely the same player's event fired twice
print(f"\n{'='*60}")
print("DEDUPLICATION ANALYSIS")
print(f"{'='*60}")

from datetime import datetime

def parse_ts(s):
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None

for d in sorted(by_date.keys()):
    evts = sorted(by_date[d], key=lambda e: e['ts'])
    dupes = 0
    kept = []
    for e in evts:
        ts = parse_ts(e['ts'])
        is_dupe = False
        # Check against recent kept events
        for k in kept[-50:]:  # only check last 50
            kts = parse_ts(k['ts'])
            if not ts or not kts:
                continue
            delta = abs((ts - kts).total_seconds())
            if (delta < 5 and 
                e['city'] == k['city'] and 
                e['country'] == k['country'] and
                e['is_won'] == k['is_won']):
                dupes += 1
                is_dupe = True
                break
        if not is_dupe:
            kept.append(e)
    print(f"  {d}: {dupes} duplicates removed ({len(evts)} -> {len(kept)})")
    by_date[d] = kept  # replace with deduped

print(f"\n{'='*60}")
print("DEDUPED COUNTS")
print(f"{'='*60}")
print(f"{'Date':<12} {'Won':>6} {'Lost':>6} {'Total':>7} {'Solve%':>7}")
total_won = 0
total_lost = 0
for d in sorted(by_date.keys()):
    evts = by_date[d]
    won = sum(1 for e in evts if e['is_won'])
    lost = sum(1 for e in evts if not e['is_won'])
    total = won + lost
    pct = 100 * won / total if total else 0
    total_won += won
    total_lost += lost
    print(f"{d:<12} {won:>6} {lost:>6} {total:>7} {pct:>6.1f}%")

print(f"{'TOTAL':<12} {total_won:>6} {total_lost:>6} {total_won+total_lost:>7} {100*total_won/(total_won+total_lost):>6.1f}%")

# Compare with pipeline
print(f"\n{'='*60}")
print("COMPARISON WITH PIPELINE (from overview.json)")
print(f"{'='*60}")
import json, os
overview_path = os.path.join('relink', 'outputs', 'data', 'overview.json')
if os.path.exists(overview_path):
    with open(overview_path) as f:
        overview = json.load(f)
    print(f"{'Date':<12} {'Pipeline%':>10} {'Events%':>10} {'Diff':>7}")
    for entry in overview.get('per_date', []):
        d = entry['date']
        pipeline_pct = entry.get('solve_rate', 0) * 100
        if d in by_date:
            evts = by_date[d]
            won = sum(1 for e in evts if e['is_won'])
            lost = sum(1 for e in evts if not e['is_won'])
            events_pct = 100 * won / (won + lost) if (won + lost) else 0
            diff = events_pct - pipeline_pct
            print(f"{d:<12} {pipeline_pct:>9.1f}% {events_pct:>9.1f}% {diff:>+6.1f}pp")
