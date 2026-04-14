import csv, ast
from collections import defaultdict, Counter

DATA_DIR = '/Users/oliver.price/Library/CloudStorage/OneDrive-DMGTCloud/Documents/Daily Mail Puzzles/Puzzles/Relink/Relink internal test/data'

# Try fingerprinting: city + device + browser + browser_version + os + os_version
fp_dates = defaultdict(set)
fp_sessions = defaultdict(list)

for fname in [f'{DATA_DIR}/raw/daily-mail-sessions.csv', f'{DATA_DIR}/raw/daily-mail-sessions-2.csv']:
    with open(fname) as f:
        for row in csv.DictReader(f):
            try:
                props = ast.literal_eval(row['properties'])
            except:
                continue
            if props.get('game_id') != 'word-flow':
                continue
            date = row['created_at'][:10]
            fp = (row['city'], row['device'], row['browser'],
                  row['browser_version'], row['os'], row['os_version'])
            fp_dates[fp].add(date)
            fp_sessions[fp].append(date)

multi = {k: v for k, v in fp_dates.items() if len(v) > 1}
total = len(fp_dates)
print(f'Total unique fingerprints: {total}')
print(f'Appearing on 2+ dates: {len(multi)} ({len(multi)*100//total}%)')

day_counts = Counter(len(v) for v in fp_dates.values())
for n in sorted(day_counts):
    print(f'  On {n} dates: {day_counts[n]} fingerprints')

# Check for collisions on the same day
same_day_dupes = 0
for fp, sessions in fp_sessions.items():
    date_counts = Counter(sessions)
    if any(c > 1 for c in date_counts.values()):
        same_day_dupes += 1
print(f'\nFingerprints with multiple sessions on SAME day: {same_day_dupes}')
print('(These are ambiguous - could be different people)')
