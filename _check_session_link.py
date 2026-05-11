"""Check if there's any link between session IDs and events."""
import csv

# Find sessions from Dalkeith on May 10
print('=== SESSIONS from Dalkeith, May 10 ===')
sessions = []
with open('raw/daily-mail-sessions-2026-04-19_to_2026-05-11.csv') as f:
    for row in csv.DictReader(f):
        if row['city'] == 'Dalkeith' and row['created_at'].startswith('2026-05-10') and 'relink' in row.get('properties', ''):
            sessions.append(row)
            print(f"Session ID: {row['id']}")
            print(f"  Created: {row['created_at']}")
            print(f"  Ended: {row['ended_at']}")
            print(f"  Duration: {row['duration']}ms")
            print(f"  Event count: {row['event_count']}")
            print(f"  Properties: {row['properties'][:300]}")
            print()

# Event IDs from same location/time
print('=== EVENT IDs from Dalkeith, May 10 ===')
events = []
with open('raw/daily-mail-events-2026-04-19_to_2026-05-11.csv') as f:
    for row in csv.DictReader(f):
        if row['city'] == 'Dalkeith' and row['created_at'].startswith('2026-05-10') and 'relink' in row.get('properties', ''):
            events.append(row)
            print(f"  {row['id']}  {row['name']}  {row['created_at']}")

# Check: does the session event_count match the number of events we found?
print(f"\n=== COMPARISON ===")
print(f"Events found: {len(events)}")
for s in sessions:
    print(f"Session {s['id']}: event_count={s['event_count']}")

# Check: do event IDs share any prefix/pattern with session IDs?
print(f"\n=== ID PATTERN CHECK ===")
for s in sessions:
    sid = s['id']
    print(f"Session ID: {sid}")
    for e in events[:3]:
        eid = e['id']
        # Check common prefix
        common = 0
        for a, b in zip(sid, eid):
            if a == b:
                common += 1
            else:
                break
        print(f"  Event ID: {eid}  (common prefix: {common} chars)")

# Check: does grep for session ID appear anywhere in events file?
print(f"\n=== SEARCHING FOR SESSION ID IN EVENT PROPERTIES ===")
if sessions:
    sid = sessions[0]['id']
    print(f"Looking for session ID '{sid}' in event properties...")
    found = False
    with open('raw/daily-mail-events-2026-04-19_to_2026-05-11.csv') as f:
        for i, line in enumerate(f):
            if sid in line:
                print(f"  FOUND at line {i}: {line[:200]}")
                found = True
                break
            if i > 100000:
                break
    if not found:
        # Try just part of it
        print(f"  Not found in first 100K lines")
        # Maybe search the whole file
        with open('raw/daily-mail-events-2026-04-19_to_2026-05-11.csv') as f:
            for line in f:
                if sid in line:
                    print(f"  FOUND: {line[:200]}")
                    found = True
                    break
        if not found:
            print(f"  NOT FOUND anywhere in events file")
