"""Check for 'orphan' level_completed events that have no nearby guess events.
These would be revisits where the page re-fires the completion event."""
import csv
from datetime import datetime, timedelta
from collections import defaultdict

target_dates = {'2026-05-07', '2026-05-08', '2026-05-09', '2026-05-10', '2026-05-11'}

def parse_ts(s):
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None

# Load ALL relink events, grouped by (city, country, date)
print("Loading events...")
events_by_location = defaultdict(list)
total = 0
with open('raw/daily-mail-events-2026-04-19_to_2026-05-11.csv') as f:
    for row in csv.DictReader(f):
        d = row['created_at'][:10]
        if d not in target_dates:
            continue
        props = row.get('properties', '')
        if "'game_id':'relink'" not in props and "'game_id': 'relink'" not in props:
            continue
        # Skip tutorial
        if "'attempts_remaining':'999'" in props:
            continue
        key = (row['country'], row['city'], d)
        events_by_location[key].append({
            'name': row['name'],
            'ts': row['created_at'],
            'props': props,
        })
        total += 1

print(f"Loaded {total} non-tutorial relink events in {len(events_by_location)} location-date buckets")

# For each bucket, sort by time and check each level_completed:
# Does it have guess events within 5 minutes before it?
print("\nAnalysing level_completed events...")

orphan_completions = 0
normal_completions = 0
orphan_by_date = defaultdict(lambda: {'won': 0, 'lost': 0})
normal_by_date = defaultdict(lambda: {'won': 0, 'lost': 0})

for key, events in events_by_location.items():
    country, city, date = key
    events.sort(key=lambda e: e['ts'])
    
    for i, ev in enumerate(events):
        if ev['name'] != 'level_completed':
            continue
        
        is_won = "'is_won':'true'" in ev['props'] or "'is_won': 'true'" in ev['props']
        is_lost = "'is_won':'false'" in ev['props'] or "'is_won': 'false'" in ev['props']
        if not is_won and not is_lost:
            continue
        
        ev_ts = parse_ts(ev['ts'])
        if not ev_ts:
            continue
        
        # Look back up to 10 minutes for any guess events
        has_nearby_guess = False
        for j in range(i - 1, max(i - 200, -1), -1):
            prev = events[j]
            prev_ts = parse_ts(prev['ts'])
            if not prev_ts:
                continue
            if (ev_ts - prev_ts).total_seconds() > 600:  # 10 min window
                break
            if prev['name'] == 'relink_guess_submitted':
                has_nearby_guess = True
                break
        
        # Also check: is there a level_started within 10 min before?
        has_nearby_start = False
        for j in range(i - 1, max(i - 200, -1), -1):
            prev = events[j]
            prev_ts = parse_ts(prev['ts'])
            if not prev_ts:
                continue
            if (ev_ts - prev_ts).total_seconds() > 600:
                break
            if prev['name'] == 'level_started':
                has_nearby_start = True
                break
        
        outcome = 'won' if is_won else 'lost'
        if has_nearby_guess:
            normal_completions += 1
            normal_by_date[date][outcome] += 1
        else:
            orphan_completions += 1
            orphan_by_date[date][outcome] += 1

print(f"\n{'='*60}")
print(f"RESULTS")
print(f"{'='*60}")
print(f"Normal completions (guess events within 10min before): {normal_completions}")
print(f"Orphan completions (NO guess events within 10min): {orphan_completions}")
print(f"Orphan rate: {100*orphan_completions/(orphan_completions+normal_completions):.1f}%")

print(f"\n{'='*60}")
print(f"ORPHAN BREAKDOWN BY DATE")
print(f"{'='*60}")
print(f"{'Date':<12} {'Orphan Won':>10} {'Orphan Lost':>11} {'Orphan%':>8} {'Normal Won':>10} {'Normal Lost':>11}")
for d in sorted(set(list(orphan_by_date.keys()) + list(normal_by_date.keys()))):
    ow = orphan_by_date[d]['won']
    ol = orphan_by_date[d]['lost']
    nw = normal_by_date[d]['won']
    nl = normal_by_date[d]['lost']
    total_d = ow + ol + nw + nl
    orphan_pct = 100 * (ow + ol) / total_d if total_d else 0
    print(f"{d:<12} {ow:>10} {ol:>11} {orphan_pct:>7.1f}% {nw:>10} {nl:>11}")

print(f"\n{'='*60}")
print(f"SOLVE RATE COMPARISON")
print(f"{'='*60}")
print(f"{'Date':<12} {'All events':>11} {'Normal only':>12} {'Diff':>7}")
for d in sorted(normal_by_date.keys()):
    ow = orphan_by_date[d]['won']
    ol = orphan_by_date[d]['lost']
    nw = normal_by_date[d]['won']
    nl = normal_by_date[d]['lost']
    all_rate = 100 * (ow + nw) / (ow + ol + nw + nl) if (ow + ol + nw + nl) else 0
    normal_rate = 100 * nw / (nw + nl) if (nw + nl) else 0
    diff = normal_rate - all_rate
    print(f"{d:<12} {all_rate:>10.1f}% {normal_rate:>11.1f}% {diff:>+6.1f}pp")
