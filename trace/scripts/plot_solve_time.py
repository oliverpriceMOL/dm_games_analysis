import csv, ast, json, os
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRACE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.dirname(TRACE_DIR)
EVENTS_FILES = [
    os.path.join(DATA_DIR, 'raw', 'daily-mail-events.csv'),
    os.path.join(DATA_DIR, 'raw', 'daily-mail-events-2.csv'),
]
OUTPUT_FILE = os.path.join(TRACE_DIR, 'outputs', 'solve-time-by-length.html')

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

# Collect solve times by puzzle from both files, deduplicating by event ID
times_by_puzzle = defaultdict(list)
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
            if row['name'] != 'level_completed':
                continue
            pd = props.get('puzzle_date', row['created_at'][:10])
            if pd not in PUZZLE_WORDS:
                continue
            try:
                t = int(props.get('time_seconds', ''))
            except:
                continue
            if t <= 600:  # cap at 10 min for chart clarity
                times_by_puzzle[pd].append(t)

# Build histogram data: 5-second buckets, grouped by word length
bucket_size = 5
max_time = 300  # show up to 5 min
buckets = list(range(0, max_time + bucket_size, bucket_size))
bucket_labels = [f"{b}s" for b in buckets[:-1]]

# Group by word length
length_groups = defaultdict(list)  # length -> list of all times
for pd, times in times_by_puzzle.items():
    word = PUZZLE_WORDS[pd]
    length_groups[len(word)].extend(times)

# Also per-word data
per_word = {}
for pd in sorted(PUZZLE_WORDS.keys()):
    word = PUZZLE_WORDS[pd]
    times = times_by_puzzle.get(pd, [])
    hist = [0] * (len(buckets) - 1)
    for t in times:
        idx = min(t // bucket_size, len(hist) - 1)
        hist[idx] += 1
    # Convert to percentages
    n = len(times)
    hist_pct = [round(h / n * 100, 2) if n else 0 for h in hist]
    per_word[word] = hist_pct

# Build length-grouped histograms (as percentages)
length_hists = {}
for length in sorted(length_groups.keys()):
    times = length_groups[length]
    hist = [0] * (len(buckets) - 1)
    for t in times:
        idx = min(t // bucket_size, len(hist) - 1)
        hist[idx] += 1
    n = len(times)
    hist_pct = [round(h / n * 100, 2) if n else 0 for h in hist]
    length_hists[length] = {
        'data': hist_pct,
        'count': n,
        'words': [w for pd, w in sorted(PUZZLE_WORDS.items()) if len(w) == length],
    }

# Base colours per word length — shades generated for each word within the group
_length_base = [
    {'h': 217, 's': 91, 'l': 60},   # blue (5-letter)
    {'h': 160, 's': 84, 'l': 39},   # green (6-letter)
    {'h': 0,   's': 84, 'l': 60},   # red (7-letter)
    {'h': 37,  's': 91, 'l': 50},   # amber
    {'h': 263, 's': 70, 'l': 50},   # purple
]

# Line dash patterns to differentiate words within a colour group
_dash_patterns = [
    [],          # solid
    [8, 4],     # dashed
    [2, 3],     # dotted
    [12, 4, 2, 4],  # dash-dot
    [6, 2],     # short dash
]

length_colours = {}
for i, length in enumerate(sorted(length_hists.keys())):
    base = _length_base[i % len(_length_base)]
    h, s, l = base['h'], base['s'], base['l']
    length_colours[length] = {
        'line': f'hsl({h}, {s}%, {l}%)',
        'fill': f'hsla({h}, {s}%, {l}%, 0.15)',
        'h': h, 's': s, 'l': l,
    }

# Build per-word styles: same-length words share a hue, vary in lightness + dash
_date_ordered_words = [PUZZLE_WORDS[pd] for pd in sorted(PUZZLE_WORDS.keys()) if pd in times_by_puzzle]

# Group words by length (preserving date order within each group)
_words_by_length = defaultdict(list)
for w in _date_ordered_words:
    _words_by_length[len(w)].append(w)

# all_words ordered by length group for legend grouping
all_words = []
for length in sorted(_words_by_length.keys()):
    all_words.extend(_words_by_length[length])

word_styles = {}  # word -> {'colour': ..., 'dash': [...]}
for length, words in _words_by_length.items():
    base = length_colours.get(length, {'h': 0, 's': 0, 'l': 50})
    h, s = base['h'], base['s']
    n = len(words)
    for j, w in enumerate(words):
        # Spread lightness from 40% to 65% across words in the group
        l = 40 + (25 * j // max(n - 1, 1)) if n > 1 else 52
        word_styles[w] = {
            'colour': f'hsl({h}, {s}%, {l}%)',
            'dash': _dash_patterns[j % len(_dash_patterns)],
        }

html = f"""<!DOCTYPE html>
<html>
<head>
<title>Trace - Solve Time Distribution by Word Length</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
         margin: 20px; background: #fafafa; }}
  .chart-container {{ background: white; border-radius: 12px; padding: 24px; 
                      margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); 
                      max-width: 1000px; }}
  h1 {{ color: #1a1a1a; font-size: 22px; }}
  h2 {{ color: #333; font-size: 16px; margin-top: 0; }}
  canvas {{ max-height: 400px; }}
</style>
</head>
<body>
<h1>Trace: Solve Time Distribution</h1>

<div class="chart-container">
  <h2>Overlaid by Word Length (% of players)</h2>
  <canvas id="lengthChart"></canvas>
</div>

<div class="chart-container">
  <h2>Individual Words (% of players)</h2>
  <canvas id="wordChart"></canvas>
</div>

<script>
const labels = {json.dumps(bucket_labels)};

// Chart 1: By word length
new Chart(document.getElementById('lengthChart'), {{
  type: 'line',
  data: {{
    labels: labels,
    datasets: [
{','.join(f'''      {{
        label: '{length}-letter ({', '.join(info['words'])}) n={info['count']}',
        data: {json.dumps(info['data'])},
        borderColor: '{length_colours[length]['line']}',
        backgroundColor: '{length_colours[length]['fill']}',
        fill: true,
        tension: 0.3,
        borderWidth: 2,
        pointRadius: 0,
      }}''' for length, info in sorted(length_hists.items()))}
    ]
  }},
  options: {{
    responsive: true,
    interaction: {{ mode: 'index', intersect: false }},
    scales: {{
      x: {{ 
        title: {{ display: true, text: 'Solve Time' }},
        ticks: {{ maxTicksLimit: 20 }}
      }},
      y: {{ 
        title: {{ display: true, text: '% of Players' }},
        beginAtZero: true 
      }}
    }},
    plugins: {{
      tooltip: {{
        callbacks: {{
          label: (ctx) => ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(1) + '%'
        }}
      }}
    }}
  }}
}});

// Chart 2: Individual words
new Chart(document.getElementById('wordChart'), {{
  type: 'line',
  data: {{
    labels: labels,
    datasets: [
{','.join(f'''      {{
        label: '{word} ({len(word)} letters)',
        data: {json.dumps(per_word[word])},
        borderColor: '{word_styles[word]['colour']}',
        borderDash: {json.dumps(word_styles[word]['dash'])},
        fill: false,
        tension: 0.3,
        borderWidth: 2,
        pointRadius: 0,
      }}''' for word in all_words if word in per_word)}
    ]
  }},
  options: {{
    responsive: true,
    interaction: {{ mode: 'index', intersect: false }},
    scales: {{
      x: {{ 
        title: {{ display: true, text: 'Solve Time' }},
        ticks: {{ maxTicksLimit: 20 }}
      }},
      y: {{ 
        title: {{ display: true, text: '% of Players' }},
        beginAtZero: true 
      }}
    }},
    plugins: {{
      tooltip: {{
        callbacks: {{
          label: (ctx) => ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(1) + '%'
        }}
      }}
    }}
  }}
}});
</script>
</body>
</html>
"""

with open(OUTPUT_FILE, 'w') as f:
    f.write(html)

print(f"Chart written to {OUTPUT_FILE}")
