import csv, ast, os
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRACE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.dirname(TRACE_DIR)
EVENTS_FILES = [
    os.path.join(DATA_DIR, 'raw', 'daily-mail-events.csv'),
    os.path.join(DATA_DIR, 'raw', 'daily-mail-events-2.csv'),
]

PUZZLE_WORDS = {
    '2026-03-26': 'TRACE',
    '2026-03-27': 'LEANING',
    '2026-03-28': 'WHEEL',
    '2026-03-29': 'PARTIAL',
    '2026-03-30': 'UNIQUE',
    '2026-03-31': 'WEEPING',
    '2026-04-01': 'FOOLS',
    '2026-04-02': 'CONQUER',
    '2026-04-03': 'BASKET',
    '2026-04-04': 'CROSS',
    '2026-04-05': 'EASTER',
    '2026-04-06': 'BUNNY',
}

started = defaultdict(int)
completed = defaultdict(int)
times = defaultdict(list)

seen_ids = set()
for events_file in EVENTS_FILES:
    if not os.path.exists(events_file):
        continue
    with open(events_file) as f:
        for row in csv.DictReader(f):
            if row['id'] in seen_ids:
                continue
            seen_ids.add(row['id'])
            props = ast.literal_eval(row.get('properties', '{}'))
            if props.get('game_id') != 'word-flow':
                continue
            date = row['created_at'][:10]
            if date not in PUZZLE_WORDS:
                continue
            if row['name'] == 'level_started':
                started[date] += 1
            elif row['name'] == 'level_completed':
                completed[date] += 1
                try:
                    t = int(props['time_seconds'])
                    if t <= 3600:
                        times[date].append(t)
                except:
                    pass

# Per-word table
print(f"{'Word':<10} {'Letters':<8} {'Started':<10} {'Completed':<10} {'Solve rate':<16} {'Median(s)':<10} {'Avg(s)':<8}")
print('-' * 72)
for pd in sorted(PUZZLE_WORDS.keys()):
    word = PUZZLE_WORDS[pd]
    s = started[pd]
    c = completed[pd]
    tt = sorted(times[pd])
    med = tt[len(tt) // 2] if tt else 0
    avg = sum(tt) // len(tt) if tt else 0
    rate = f"{c}/{s} ({c / s * 100:.0f}%)"
    print(f"{word:<10} {len(word):<8} {s:<10} {c:<10} {rate:<16} {med:<10} {avg:<8}")

# Summary by length
print()
print(f"{'Length':<8} {'Words':<25} {'Started':<10} {'Completed':<10} {'Solve rate':<18} {'Avg median(s)':<14}")
print('-' * 85)
by_len = defaultdict(lambda: {'words': [], 'started': 0, 'completed': 0, 'medians': []})
for pd in sorted(PUZZLE_WORDS.keys()):
    word = PUZZLE_WORDS[pd]
    l = len(word)
    by_len[l]['words'].append(word)
    by_len[l]['started'] += started[pd]
    by_len[l]['completed'] += completed[pd]
    tt = sorted(times[pd])
    if tt:
        by_len[l]['medians'].append(tt[len(tt) // 2])

for l in sorted(by_len.keys()):
    d = by_len[l]
    s, c = d['started'], d['completed']
    avg_med = sum(d['medians']) // len(d['medians'])
    rate = f"{c}/{s} ({c / s * 100:.0f}%)"
    print(f"{l:<8} {', '.join(d['words']):<25} {s:<10} {c:<10} {rate:<18} {avg_med}")
