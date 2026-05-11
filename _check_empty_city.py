"""Check empty-city prevalence and its impact on matching."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'relink', 'scripts'))
from lib.data import load_behaviour
from collections import Counter

RAW_DIR = os.path.join(os.path.dirname(__file__), 'raw')
target_dates = {'2026-05-07','2026-05-08','2026-05-09','2026-05-10','2026-05-11'}
sessions_by_date, events_by_date, ALL_DATES = load_behaviour(RAW_DIR, target_dates)

sessions = {}
for d, sd in sessions_by_date.items():
    sessions.update(sd)
events = []
for d, el in events_by_date.items():
    events.extend(el)

empty_city_events = sum(1 for e in events if not e.get('city', ''))
empty_city_sessions = sum(1 for s in sessions.values() if not s.get('city', ''))
pct_ev = 100 * empty_city_events / len(events)
pct_sess = 100 * empty_city_sessions / len(sessions)
print(f"Events with empty city: {empty_city_events}/{len(events)} ({pct_ev:.1f}%)")
print(f"Sessions with empty city: {empty_city_sessions}/{len(sessions)} ({pct_sess:.1f}%)")

ev_country = Counter(e['country'] for e in events if not e.get('city', ''))
sess_country = Counter(s['country'] for s in sessions.values() if not s.get('city', ''))
print(f"\nEmpty-city events by country (top 5): {ev_country.most_common(5)}")
print(f"Empty-city sessions by country (top 5): {sess_country.most_common(5)}")

gb_events = sum(1 for e in events if e['country'] == 'GB')
print(f"\nTotal GB events: {gb_events}")
print(f"Total GB sessions: {sum(1 for s in sessions.values() if s['country'] == 'GB')}")
