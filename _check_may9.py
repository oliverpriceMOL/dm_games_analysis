"""Deep dive into May 9 completions - why is solve rate so low?"""
import csv
from datetime import datetime
from collections import defaultdict, Counter

target_date = '2026-05-09'

def parse_ts(s):
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None

# Load all relink events for May 9
print("Loading May 9 events...")
events = []
with open('raw/daily-mail-events-2026-04-19_to_2026-05-11.csv') as f:
    for row in csv.DictReader(f):
        if not row['created_at'].startswith(target_date):
            continue
        props = row.get('properties', '')
        if "'game_id':'relink'" not in props and "'game_id': 'relink'" not in props:
            continue
        if "'attempts_remaining':'999'" in props:
            continue
        events.append(row)

print(f"Total non-tutorial relink events on May 9: {len(events)}")

# Check level_ids present
level_ids = Counter()
for ev in events:
    props = ev['properties']
    lid = ''
    for pattern in ["'level_id':'", "'level_id': '"]:
        idx = props.find(pattern)
        if idx >= 0:
            start = idx + len(pattern)
            end = props.find("'", start)
            lid = props[start:end]
            break
    if lid:
        level_ids[lid] += 1

print(f"\n{'='*60}")
print("LEVEL IDS ON MAY 9")
print(f"{'='*60}")
for lid, count in level_ids.most_common():
    print(f"  {lid}: {count} events")

# Check completions by level_id
print(f"\n{'='*60}")
print("COMPLETIONS BY LEVEL_ID")
print(f"{'='*60}")
completions_by_lid = defaultdict(lambda: {'won': 0, 'lost': 0})
for ev in events:
    if ev['name'] != 'level_completed':
        continue
    props = ev['properties']
    lid = ''
    for pattern in ["'level_id':'", "'level_id': '"]:
        idx = props.find(pattern)
        if idx >= 0:
            start = idx + len(pattern)
            end = props.find("'", start)
            lid = props[start:end]
            break
    is_won = "'is_won':'true'" in props or "'is_won': 'true'" in props
    is_lost = "'is_won':'false'" in props or "'is_won': 'false'" in props
    if is_won:
        completions_by_lid[lid]['won'] += 1
    elif is_lost:
        completions_by_lid[lid]['lost'] += 1

for lid, counts in sorted(completions_by_lid.items(), key=lambda x: -(x[1]['won']+x[1]['lost'])):
    w = counts['won']
    l = counts['lost']
    t = w + l
    pct = 100 * w / t if t else 0
    print(f"  {lid}: {w} won, {l} lost, total={t}, solve={pct:.1f}%")

# Check: hourly breakdown of completions for the main level_id
main_lid = level_ids.most_common(1)[0][0] if level_ids else ''
print(f"\n{'='*60}")
print(f"HOURLY COMPLETIONS FOR {main_lid}")
print(f"{'='*60}")
hourly = defaultdict(lambda: {'won': 0, 'lost': 0})
for ev in events:
    if ev['name'] != 'level_completed':
        continue
    props = ev['properties']
    if main_lid not in props:
        continue
    is_won = "'is_won':'true'" in props or "'is_won': 'true'" in props
    hour = ev['created_at'][11:13]
    if is_won:
        hourly[hour]['won'] += 1
    else:
        hourly[hour]['lost'] += 1

print(f"{'Hour':<6} {'Won':>5} {'Lost':>5} {'Total':>6} {'Solve%':>7}")
for h in sorted(hourly.keys()):
    w = hourly[h]['won']
    l = hourly[h]['lost']
    t = w + l
    pct = 100 * w / t if t else 0
    print(f"{h}:00  {w:>5} {l:>5} {t:>6} {pct:>6.1f}%")

# Check guess patterns for the losses - are they realistic?
print(f"\n{'='*60}")
print(f"WRONG GUESS COUNT DISTRIBUTION (for completions with {main_lid})")
print(f"{'='*60}")

# Group events by (city, country) to approximate individual games
# Sort by time and look for level_started -> guesses -> level_completed patterns
by_location = defaultdict(list)
for ev in events:
    if main_lid in ev.get('properties', ''):
        key = (ev['country'], ev['city'])
        by_location[key].append(ev)

# For each location, sort by time and extract game sequences
wrong_counts_won = Counter()
wrong_counts_lost = Counter()
games_analyzed = 0

for key, loc_events in by_location.items():
    loc_events.sort(key=lambda e: e['created_at'])
    
    # Simple approach: count guesses between each level_started and level_completed
    current_wrongs = 0
    in_game = False
    
    for ev in loc_events:
        if ev['name'] == 'level_started':
            in_game = True
            current_wrongs = 0
        elif ev['name'] == 'relink_guess_submitted' and in_game:
            props = ev['properties']
            if "'is_correct':'false'" in props or "'is_correct': 'false'" in props:
                current_wrongs += 1
        elif ev['name'] == 'level_completed' and in_game:
            props = ev['properties']
            is_won = "'is_won':'true'" in props or "'is_won': 'true'" in props
            if is_won:
                wrong_counts_won[current_wrongs] += 1
            else:
                wrong_counts_lost[current_wrongs] += 1
            in_game = False
            games_analyzed += 1

print(f"Games analyzed: {games_analyzed}")
print(f"\nWrong guesses for WINS:")
for w in sorted(wrong_counts_won.keys()):
    print(f"  {w} wrongs: {wrong_counts_won[w]}")
print(f"\nWrong guesses for LOSSES:")
for w in sorted(wrong_counts_lost.keys()):
    print(f"  {w} wrongs: {wrong_counts_lost[w]}")

# For losses: with 4 lives, you need exactly 4 wrong guesses to lose in imposters.
# Unless they reach relink phase and lose there.
print(f"\n{'='*60}")
print(f"SANITY CHECK: Losses with <4 wrong guesses should be relink-phase losses")
print(f"{'='*60}")
sus_losses = wrong_counts_lost.get(0, 0) + wrong_counts_lost.get(1, 0) + wrong_counts_lost.get(2, 0) + wrong_counts_lost.get(3, 0)
print(f"Losses with 0-3 wrongs (reached relink but lost there): {sus_losses}")
normal_losses = sum(v for k, v in wrong_counts_lost.items() if k >= 4)
print(f"Losses with 4+ wrongs (died in imposters): {normal_losses}")
