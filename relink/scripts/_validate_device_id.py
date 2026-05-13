"""Validate device_id and client_id coverage for relink events."""

import csv
import os
import glob
from collections import defaultdict, Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.dirname(GAME_DIR)
RAW_DIR = os.path.join(DATA_DIR, 'raw')


def _strip_nuls(f):
    for line in f:
        if '\x00' in line:
            line = line.replace('\x00', '')
        yield line


def main():
    event_files = sorted(glob.glob(os.path.join(RAW_DIR, 'daily-mail-events*.csv')))
    print(f"Found {len(event_files)} event file(s)")

    total_relink = 0
    has_device_id = 0
    no_device_id = 0
    has_client_dm = 0
    has_both = 0

    # Per-date breakdown
    per_date_total = Counter()
    per_date_has_device = Counter()
    per_date_has_both = Counter()

    # Events-per-device distribution (for events that have both device_id + client_id:dailymail)
    events_per_device_date = Counter()  # (device_id, date) -> count

    seen_ids = set()

    for ef in event_files:
        print(f"  Scanning: {os.path.basename(ef)}")
        with open(ef) as f:
            for row in csv.DictReader(_strip_nuls(f)):
                raw_props = row.get('properties', '')
                # Gate: relink only
                if 'relink' not in raw_props:
                    continue
                if "'game_id':'relink'" not in raw_props and "'game_id': 'relink'" not in raw_props:
                    continue

                eid = row['id']
                if eid in seen_ids:
                    continue
                seen_ids.add(eid)

                date = row['created_at'][:10]
                total_relink += 1
                per_date_total[date] += 1

                device_id = row.get('device_id', '').strip()
                has_dm = "'client_id':'dailymail'" in raw_props or "'client_id': 'dailymail'" in raw_props

                if device_id:
                    has_device_id += 1
                    per_date_has_device[date] += 1
                else:
                    no_device_id += 1

                if has_dm:
                    has_client_dm += 1

                if device_id and has_dm:
                    has_both += 1
                    per_date_has_both[date] += 1
                    events_per_device_date[(device_id, date)] += 1

    # Print results
    print(f"\n{'='*60}")
    print(f"RELINK EVENT COVERAGE REPORT")
    print(f"{'='*60}")

    print(f"\n── Headline ──")
    pct_missing = (no_device_id / total_relink * 100) if total_relink else 0
    pct_has = (has_device_id / total_relink * 100) if total_relink else 0
    print(f"  Total relink events:          {total_relink:,}")
    print(f"  With device_id:               {has_device_id:,} ({pct_has:.1f}%)")
    print(f"  WITHOUT device_id:            {no_device_id:,} ({pct_missing:.1f}%) ← excluded from new pipeline")

    print(f"\n── client_id:'dailymail' ──")
    pct_dm = (has_client_dm / total_relink * 100) if total_relink else 0
    print(f"  With client_id:'dailymail':   {has_client_dm:,} ({pct_dm:.1f}%)")
    pct_both = (has_both / total_relink * 100) if total_relink else 0
    print(f"  With BOTH device_id + DM:     {has_both:,} ({pct_both:.1f}%) ← usable for pipeline")

    print(f"\n── Per-date breakdown ──")
    for date in sorted(per_date_total.keys()):
        t = per_date_total[date]
        d = per_date_has_device.get(date, 0)
        b = per_date_has_both.get(date, 0)
        pct_d = d / t * 100 if t else 0
        pct_b = b / t * 100 if t else 0
        print(f"  {date}: {t:>6,} total | {d:>6,} w/device ({pct_d:5.1f}%) | {b:>6,} w/both ({pct_b:5.1f}%)")

    # Events-per-device distribution (only for usable events: both device_id + dailymail)
    print(f"\n── Events per device+date (usable only) ──")
    counts = list(events_per_device_date.values())
    dist = Counter()
    for c in counts:
        if c == 1:
            dist['1 event'] += 1
        elif c <= 4:
            dist['2-4 events'] += 1
        elif c <= 8:
            dist['5-8 events'] += 1
        elif c <= 12:
            dist['9-12 events'] += 1
        else:
            dist[f'13+ events'] += 1
    total_devices = len(counts)
    print(f"  Total unique (device_id, date) pairs: {total_devices:,}")
    for bucket in ['1 event', '2-4 events', '5-8 events', '9-12 events', '13+ events']:
        n = dist.get(bucket, 0)
        pct = n / total_devices * 100 if total_devices else 0
        print(f"    {bucket:>12}: {n:>7,} ({pct:5.1f}%)")

    # Unique devices per date (usable)
    devices_by_date = defaultdict(set)
    for (dev, date), _ in events_per_device_date.items():
        devices_by_date[date].add(dev)
    print(f"\n── Unique devices per date (usable) ──")
    for date in sorted(devices_by_date.keys()):
        print(f"  {date}: {len(devices_by_date[date]):,} players")


if __name__ == '__main__':
    main()
