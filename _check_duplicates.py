"""Check for duplicate/overlap issues in the data pipeline."""
import csv
import glob
import os
from collections import defaultdict, Counter

def strip_nuls(f):
    for line in f:
        yield line.replace('\x00', '') if '\x00' in line else line

target_dates = {'2026-05-07','2026-05-08','2026-05-09','2026-05-10','2026-05-11'}

# ── Check 1: Overlapping sessions (same country+city+date) ──
print("=" * 60)
print("CHECK 1: Overlapping sessions (same country+city+date)")
print("=" * 60)

session_files = sorted(glob.glob('raw/daily-mail-sessions*.csv'))
sessions_by_bucket = defaultdict(list)

for sf in session_files:
    with open(sf) as f:
        for row in csv.DictReader(strip_nuls(f)):
            d = row['created_at'][:10]
            if d not in target_dates:
                continue
            if 'relink' not in row.get('properties', ''):
                continue
            key = (row['country'], row.get('city', ''), d)
            sessions_by_bucket[key].append((row['created_at'], row['ended_at'], row['id']))

overlap_count = 0
for key, sessions in sessions_by_bucket.items():
    if len(sessions) < 2:
        continue
    sessions.sort()
    for i in range(len(sessions) - 1):
        _, end_i, sid_i = sessions[i]
        start_j, _, sid_j = sessions[i + 1]
        if end_i > start_j:
            overlap_count += 1
            if overlap_count <= 5:
                print(f"  Overlap: {key[0]}/{key[1]}/{key[2]}")
                print(f"    Session A: {sid_i[:12]}.. ({sessions[i][0]} to {end_i})")
                print(f"    Session B: {sid_j[:12]}.. ({start_j} to {sessions[i+1][1]})")

print(f"\n  Total overlapping session pairs: {overlap_count}")
print(f"  Total buckets (country+city+date): {len(sessions_by_bucket)}")

# ── Check 2: Multiple level_completed per session ──
print("\n" + "=" * 60)
print("CHECK 2: Multiple level_completed events per session-worth of events")
print("=" * 60)

# Load events for target dates
event_files = sorted(glob.glob('raw/daily-mail-events*.csv'))
events_by_date = defaultdict(list)

for ef in event_files:
    with open(ef) as f:
        for row in csv.DictReader(strip_nuls(f)):
            d = row['created_at'][:10]
            if d not in target_dates:
                continue
            raw_props = row.get('properties', '')
            if 'relink' not in raw_props:
                continue
            if "'game_id':'relink'" not in raw_props:
                continue
            events_by_date[d].append(row)

# Count level_completed and level_started events per date
for d in sorted(events_by_date.keys()):
    evs = events_by_date[d]
    completed = [e for e in evs if e['name'] == 'level_completed']
    started = [e for e in evs if e['name'] == 'level_started']
    guesses = [e for e in evs if e['name'] == 'relink_guess_submitted']
    print(f"\n  {d}: {len(started)} level_started, {len(completed)} level_completed, {len(guesses)} guesses")
    print(f"    Ratio completed/started: {len(completed)/len(started):.2f}" if started else "")

# ── Check 3: Same level_id appearing in multiple events for same apparent player ──
print("\n" + "=" * 60)
print("CHECK 3: Duplicate level_completed per (country, city, level_id) within short window")
print("=" * 60)

from datetime import datetime, timedelta

def parse_ts(s):
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f'):
        try:
            return datetime.strptime(s.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None

for d in sorted(events_by_date.keys()):
    completed = [e for e in events_by_date[d] if e['name'] == 'level_completed']
    # Group by (country, city) as proxy for "same player"
    by_location = defaultdict(list)
    for e in completed:
        key = (e['country'], e.get('city', ''))
        by_location[key].append(e)
    
    dupe_count = 0
    for key, evs in by_location.items():
        if len(evs) < 2:
            continue
        evs.sort(key=lambda e: e['created_at'])
        for i in range(len(evs) - 1):
            ts1 = parse_ts(evs[i]['created_at'])
            ts2 = parse_ts(evs[i+1]['created_at'])
            if ts1 and ts2 and (ts2 - ts1).total_seconds() < 5:
                dupe_count += 1
                if dupe_count <= 3:
                    print(f"  Near-duplicate level_completed in {key}: {evs[i]['created_at']} vs {evs[i+1]['created_at']}")
    print(f"  {d}: {dupe_count} near-duplicate level_completed pairs (<5s apart, same location)")

# ── Check 4: How many players have INCOMPLETE outcome (no level_completed) ──
print("\n" + "=" * 60)
print("CHECK 4: Player outcome breakdown (from pipeline output)")
print("=" * 60)

import json
overview = json.load(open('relink/outputs/data/overview.json'))
for x in overview['dates']:
    incomplete = x['players'] - x['completions']
    print(f"  {x['date']}: {x['players']} players, {x['completions']} completions, {incomplete} INCOMPLETE ({100*incomplete/x['players']:.1f}%)")
