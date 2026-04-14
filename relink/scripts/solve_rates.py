import csv
import ast
import sys
import os
import glob
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RELINK_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.dirname(RELINK_DIR)
RAW_DIR = os.path.join(DATA_DIR, 'raw')
EVENT_FILES = sorted(glob.glob(os.path.join(RAW_DIR, 'daily-mail-events*.csv')))
OUTPUT_FILE = os.path.join(RELINK_DIR, 'outputs', 'solve-rates.txt')

def parse_props(raw):
    try:
        return ast.literal_eval(raw)
    except:
        return {}

# ========== LOAD DATA ==========

# Track level_started by calendar date (no puzzle_date in those events)
starts_by_date = defaultdict(int)
# Track level_completed by puzzle_date
wins_by_date = defaultdict(int)
losses_by_date = defaultdict(int)

# Load from all event files; later files overwrite earlier ones (dedup by id)
seen_ids = set()
all_events = {}  # id -> row
for ef in EVENT_FILES:
    with open(ef) as f:
        for row in csv.DictReader(f):
            all_events[row['id']] = row  # last file wins

for row in all_events.values():
    props = parse_props(row.get('properties', '{}'))
    if props.get('game_id') != 'relink':
        continue
    if row.get('city', '') == 'Västerås' and row.get('country', '') == 'SE':
        continue

    if row['name'] == 'level_started':
        cal_date = row['created_at'][:10]
        starts_by_date[cal_date] += 1

    elif row['name'] == 'level_completed':
        puzzle_date = props.get('puzzle_date', '')
        if not puzzle_date:
            continue
        if props.get('is_won') == 'true':
            wins_by_date[puzzle_date] += 1
        else:
            losses_by_date[puzzle_date] += 1

# ========== OUTPUT ==========

all_dates = sorted(set(wins_by_date) | set(losses_by_date))

with open(OUTPUT_FILE, 'w') as out:
    sys.stdout = out

    print("RELINK — SOLVE RATES BY PUZZLE DATE")
    print("=" * 65)
    print(f"Data sources: {', '.join(os.path.basename(f) for f in EVENT_FILES)}")
    print()

    print(f"  {'Puzzle date':<15} {'Wins':<8} {'Losses':<8} {'Total':<8} {'Solve rate':<12} {'Starts*':<8}")
    print(f"  {'-' * 62}")

    total_wins = 0
    total_losses = 0
    total_starts = 0

    for d in all_dates:
        w = wins_by_date[d]
        l = losses_by_date[d]
        t = w + l
        rate = f"{w/t*100:.0f}%" if t else "n/a"
        s = starts_by_date.get(d, '-')
        print(f"  {d:<15} {w:<8} {l:<8} {t:<8} {rate:<12} {s:<8}")
        total_wins += w
        total_losses += l
        total_starts += starts_by_date.get(d, 0)

    total_completed = total_wins + total_losses
    overall_rate = f"{total_wins/total_completed*100:.0f}%" if total_completed else "n/a"
    print(f"  {'-' * 62}")
    print(f"  {'TOTAL':<15} {total_wins:<8} {total_losses:<8} {total_completed:<8} {overall_rate:<12} {total_starts:<8}")

    print()
    print("  * Starts = level_started events by calendar date (not puzzle date).")
    print("    Archive plays may cause slight mismatches between starts and completions.")

    sys.stdout = sys.__stdout__

print(f"Output written to {OUTPUT_FILE}")
with open(OUTPUT_FILE) as f:
    print(f.read())
