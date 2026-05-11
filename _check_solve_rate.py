"""Check whether event multi-matching is creating phantom losses.

Key question: if the same events get matched to multiple sessions,
do some sessions get partial event streams that look like LOST
when the full stream would be WON?
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'relink', 'scripts'))
from lib.data import load_behaviour, match_events, _parse_ts
from collections import defaultdict, Counter
from datetime import timedelta

RAW_DIR = os.path.join(os.path.dirname(__file__), 'raw')

# Only load May 7-11 data
target_dates = {'2026-05-07', '2026-05-08', '2026-05-09', '2026-05-10', '2026-05-11'}

print("Loading data...")
sessions_by_date, events_by_date, ALL_DATES = load_behaviour(RAW_DIR, target_dates)

# Flatten into single dicts for matching
sessions = {}
for d, sd in sessions_by_date.items():
    sessions.update(sd)
events = []
for d, el in events_by_date.items():
    events.extend(el)
print(f"  {len(sessions)} sessions, {len(events)} events")

print("\nMatching events to sessions...")
event_sessions = match_events(sessions, events)
print(f"  {len(event_sessions)} sessions with matched events")

# CHECK 1: How many events are matched to MULTIPLE sessions?
print("\n" + "="*60)
print("CHECK 1: Events matched to multiple sessions")
print("="*60)

# Build reverse map: event_id -> list of session IDs
event_to_sessions = defaultdict(list)
for sid, evts in event_sessions.items():
    for ev in evts:
        event_to_sessions[ev['id']].append(sid)

multi_matched = {eid: sids for eid, sids in event_to_sessions.items() if len(sids) > 1}
print(f"  Total events matched: {len(event_to_sessions)}")
print(f"  Events matched to >1 session: {len(multi_matched)} ({100*len(multi_matched)/max(1,len(event_to_sessions)):.1f}%)")

if multi_matched:
    # How many sessions are affected?
    affected_sids = set()
    for sids in multi_matched.values():
        affected_sids.update(sids)
    print(f"  Sessions affected by multi-matching: {len(affected_sids)}")

# CHECK 2: For sessions sharing events, compare event counts
print("\n" + "="*60)
print("CHECK 2: Sessions sharing events — do they get the same set?")
print("="*60)

# Group sessions that share at least one event
session_groups = defaultdict(set)  # canonical_group_id -> set of sids
eid_to_group = {}
group_counter = 0

for eid, sids in multi_matched.items():
    existing_groups = set()
    for sid in sids:
        for gid, members in session_groups.items():
            if sid in members:
                existing_groups.add(gid)
                break
    if existing_groups:
        # Merge groups
        merge_into = min(existing_groups)
        for gid in existing_groups:
            if gid != merge_into:
                session_groups[merge_into].update(session_groups[gid])
                del session_groups[gid]
        for sid in sids:
            session_groups[merge_into].add(sid)
    else:
        group_counter += 1
        for sid in sids:
            session_groups[group_counter].add(sid)

print(f"  Session groups (sets of sessions sharing events): {len(session_groups)}")
sizes = [len(v) for v in session_groups.values()]
print(f"  Group sizes: min={min(sizes)}, max={max(sizes)}, mean={sum(sizes)/len(sizes):.1f}")

# For each group, compare how many events each session got
partial_groups = 0
groups_with_outcome_mismatch = 0
outcome_details = []

for gid, sids in session_groups.items():
    event_counts = {}
    guess_counts = {}
    has_completion = {}
    completion_outcome = {}
    
    for sid in sids:
        evts = event_sessions[sid]
        event_counts[sid] = len(evts)
        guess_counts[sid] = sum(1 for e in evts if e['name'] == 'relink_guess_submitted')
        completions = [e for e in evts if e['name'] == 'level_completed']
        has_completion[sid] = len(completions) > 0
        if completions:
            # Quick check of is_won
            raw = completions[-1].get('_raw_props', completions[-1].get('properties', ''))
            if "'is_won':'true'" in raw or "'is_won': 'true'" in raw:
                completion_outcome[sid] = 'WON'
            elif "'is_won':'false'" in raw or "'is_won': 'false'" in raw:
                completion_outcome[sid] = 'LOST'
            else:
                completion_outcome[sid] = 'UNKNOWN'
    
    counts = list(event_counts.values())
    if max(counts) != min(counts):
        partial_groups += 1
    
    outcomes = set(completion_outcome.values())
    completions_present = set(has_completion.values())
    if len(outcomes) > 1 or (True in completions_present and False in completions_present):
        groups_with_outcome_mismatch += 1
        outcome_details.append({
            'sids': list(sids),
            'event_counts': event_counts,
            'guess_counts': guess_counts,
            'has_completion': has_completion,
            'completion_outcome': completion_outcome,
        })

print(f"\n  Groups where sessions got different event counts: {partial_groups}/{len(session_groups)}")
print(f"  Groups with outcome mismatch (one has completion, other doesn't, or different outcomes): {groups_with_outcome_mismatch}")

# CHECK 3: Show examples of problematic groups
print("\n" + "="*60)
print("CHECK 3: Outcome mismatch examples (first 10)")
print("="*60)

for i, det in enumerate(outcome_details[:10]):
    print(f"\n  Group {i+1}:")
    for sid in det['sids']:
        ec = det['event_counts'][sid]
        gc = det['guess_counts'][sid]
        hc = det['has_completion'][sid]
        oc = det['completion_outcome'].get(sid, 'NO_COMPLETION')
        sess = sessions[sid]
        print(f"    Session {sid[:8]}...: {ec} events, {gc} guesses, completion={hc}, outcome={oc}")
        print(f"      Country={sess['country']}, City={sess['city']}, Duration={sess.get('duration','?')}s")
        print(f"      Start={sess['created_at']}, End={sess['ended_at']}")

# CHECK 4: Overall impact on solve rates
print("\n" + "="*60)
print("CHECK 4: Impact on solve rates")
print("="*60)

# For each affected group, if one session shows WON and another shows LOST or NO_COMPLETION,
# that's a potential underestimation
phantom_losses = 0
phantom_incompletes = 0
for det in outcome_details:
    outcomes_in_group = set(det['completion_outcome'].values())
    has_no_completion = any(not v for v in det['has_completion'].values())
    if 'WON' in outcomes_in_group:
        # Count sessions in this group that don't show WON
        for sid in det['sids']:
            oc = det['completion_outcome'].get(sid, 'NO_COMPLETION')
            if oc == 'LOST':
                phantom_losses += 1
            elif oc == 'NO_COMPLETION':
                phantom_incompletes += 1
    elif 'LOST' in outcomes_in_group and has_no_completion:
        for sid in det['sids']:
            if not det['has_completion'][sid]:
                phantom_incompletes += 1

print(f"  Potential phantom LOST (WON group but shows LOST): {phantom_losses}")
print(f"  Potential phantom INCOMPLETE (group has outcome but session doesn't): {phantom_incompletes}")
print(f"  Note: INCOMPLETE players are excluded from solve rate denominator")
print(f"        Phantom LOST players would DIRECTLY reduce reported solve rate")

# CHECK 5: What fraction of all LOST players might be phantoms?
print("\n" + "="*60)
print("CHECK 5: Scale check — all players by outcome")
print("="*60)

from lib.data import build_players
all_players = build_players(sessions, event_sessions)
outcome_counts = Counter(p['outcome'] for p in all_players)
print(f"  WON:        {outcome_counts['WON']}")
print(f"  LOST:       {outcome_counts['LOST']}")
print(f"  INCOMPLETE: {outcome_counts['INCOMPLETE']}")
total_completed = outcome_counts['WON'] + outcome_counts['LOST']
if total_completed > 0:
    print(f"  Solve rate: {outcome_counts['WON']}/{total_completed} = {100*outcome_counts['WON']/total_completed:.1f}%")
    if phantom_losses > 0:
        corrected_wins = outcome_counts['WON']
        corrected_losses = outcome_counts['LOST'] - phantom_losses
        corrected_total = corrected_wins + corrected_losses
        print(f"  If phantom losses removed: {corrected_wins}/{corrected_total} = {100*corrected_wins/corrected_total:.1f}%")
        print(f"  Impact: +{100*corrected_wins/corrected_total - 100*outcome_counts['WON']/total_completed:.2f}pp")
