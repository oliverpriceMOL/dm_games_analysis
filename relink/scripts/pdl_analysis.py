"""
Relink PDL Analysis — Cross-reference puzzle design language with player behaviour.

Loads all 39 puzzle PDL files from save-data/ and joins with player behaviour data
from raw CSVs.  Outputs an interactive HTML report with charts (Chart.js v4).

Usage:
    python3 pdl_analysis.py
"""

import csv, ast, sys, os, json, glob, math
from datetime import datetime, timedelta
from collections import Counter, defaultdict

# ── Paths ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RELINK_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR   = os.path.dirname(RELINK_DIR)
RAW_DIR    = os.path.join(DATA_DIR, 'raw')
SAVE_DIR   = os.path.join(RELINK_DIR, 'save-data')
OUTPUT_FILE = os.path.join(RELINK_DIR, 'outputs', 'pdl-analysis.html')

SESSION_FILES = sorted(glob.glob(os.path.join(RAW_DIR, 'daily-mail-sessions*.csv')))
EVENT_FILES   = sorted(glob.glob(os.path.join(RAW_DIR, 'daily-mail-events*.csv')))

# ── Helpers ──
def parse_ts(s):
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S.%f'):
        try:
            return datetime.strptime(s.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None

def parse_props(s):
    try:
        return ast.literal_eval(s)
    except:
        return {}

def safe_median(vals):
    if not vals: return 0
    s = sorted(vals); n = len(s)
    return (s[n // 2] + s[(n - 1) // 2]) / 2

def percentile(vals, p):
    """Linear interpolation percentile (p in 0-100)."""
    if not vals: return 0
    s = sorted(vals)
    k = (len(s) - 1) * p / 100
    f = int(k); c = min(f + 1, len(s) - 1)
    return s[f] + (k - f) * (s[c] - s[f])

def safe_mean(vals):
    return sum(vals) / len(vals) if vals else 0

def safe_stdev(vals):
    if len(vals) < 2: return 0
    m = safe_mean(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))

def pct_str(num, den):
    return f"{num}/{den} ({num*100/den:.0f}%)" if den else "n/a"

def pearson(xs, ys):
    n = len(xs)
    if n < 3: return 0, 1.0
    mx, my = safe_mean(xs), safe_mean(ys)
    sx = math.sqrt(sum((x - mx)**2 for x in xs))
    sy = math.sqrt(sum((y - my)**2 for y in ys))
    if sx == 0 or sy == 0: return 0, 1.0
    r = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)
    # t-test for significance
    if abs(r) >= 1: return r, 0
    t = r * math.sqrt((n - 2) / (1 - r * r))
    # approximate p-value using t distribution (two-tailed)
    p = _t_pvalue(t, n - 2)
    return r, p

def _t_pvalue(t, df):
    """Approximate two-tailed p-value for t distribution."""
    x = df / (df + t * t)
    if df <= 0: return 1.0
    # Use regularised incomplete beta function approximation
    p = _betai(0.5 * df, 0.5, x)
    return p

def _betai(a, b, x):
    """Incomplete beta function (rough approximation via continued fraction)."""
    if x < 0 or x > 1: return 0
    if x == 0 or x == 1: return x
    if x < (a + 1) / (a + b + 2):
        return _betacf(a, b, x) * math.exp(
            math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) +
            a * math.log(x) + b * math.log(1 - x)) / a
    else:
        return 1 - _betacf(b, a, 1 - x) * math.exp(
            math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) +
            a * math.log(x) + b * math.log(1 - x)) / b

def _betacf(a, b, x):
    """Continued fraction for incomplete beta."""
    MAXIT = 200; EPS = 3e-7
    qab = a + b; qap = a + 1; qam = a - 1
    c = 1; d = max(1 - qab * x / qap, 1e-30); d = 1 / d; h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = max(1 + aa * d, 1e-30); c = max(1 + aa / c, 1e-30)
        d = 1 / d; h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = max(1 + aa * d, 1e-30); c = max(1 + aa / c, 1e-30)
        d = 1 / d; dl = d * c; h *= dl
        if abs(dl - 1) < EPS: break
    return h

def spearman(xs, ys):
    n = len(xs)
    if n < 3: return 0, 1.0
    def rank(v):
        s = sorted(range(n), key=lambda i: v[i])
        r = [0] * n
        for i, idx in enumerate(s): r[idx] = i + 1
        return r
    rx, ry = rank(xs), rank(ys)
    d2 = sum((a - b) ** 2 for a, b in zip(rx, ry))
    rs = 1 - 6 * d2 / (n * (n * n - 1))
    if abs(rs) >= 1: return rs, 0
    t = rs * math.sqrt((n - 2) / (1 - rs * rs))
    p = _t_pvalue(t, n - 2)
    return rs, p

def ols_simple(xs, ys):
    """Simple OLS: y = a + b*x.  Returns (a, b, r2)."""
    n = len(xs)
    if n < 2: return 0, 0, 0
    mx, my = safe_mean(xs), safe_mean(ys)
    ss_xy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    ss_xx = sum((x - mx) ** 2 for x in xs)
    if ss_xx == 0: return my, 0, 0
    b = ss_xy / ss_xx
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    return a, b, r2

def ols_multi(X, y):
    """Multiple OLS via normal equations.  X is list of lists (each row is one obs).
    Returns (coefficients_list, r2, residuals)."""
    n = len(y)
    k = len(X[0]) if X else 0
    if n <= k + 1: return [0] * (k + 1), 0, [0] * n
    # Add intercept
    A = [[1] + list(row) for row in X]
    # A^T A
    AtA = [[sum(A[i][r] * A[i][c] for i in range(n)) for c in range(k + 1)] for r in range(k + 1)]
    # A^T y
    Aty = [sum(A[i][r] * y[i] for i in range(n)) for r in range(k + 1)]
    # Solve via Gauss elimination
    aug = [AtA[r][:] + [Aty[r]] for r in range(k + 1)]
    for col in range(k + 1):
        # Pivot
        max_row = max(range(col, k + 1), key=lambda r: abs(aug[r][col]))
        aug[col], aug[max_row] = aug[max_row], aug[col]
        if abs(aug[col][col]) < 1e-12:
            return [0] * (k + 1), 0, [0] * n
        for row in range(col + 1, k + 1):
            f = aug[row][col] / aug[col][col]
            for j in range(col, k + 2):
                aug[row][j] -= f * aug[col][j]
    # Back-substitute
    coefs = [0] * (k + 1)
    for i in range(k, -1, -1):
        coefs[i] = aug[i][k + 1]
        for j in range(i + 1, k + 1):
            coefs[i] -= aug[i][j] * coefs[j]
        coefs[i] /= aug[i][i]
    # R2
    my = safe_mean(y)
    ss_tot = sum((yi - my) ** 2 for yi in y)
    preds = [sum(coefs[j] * A[i][j] for j in range(k + 1)) for i in range(n)]
    ss_res = sum((y[i] - preds[i]) ** 2 for i in range(n))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    resid = [y[i] - preds[i] for i in range(n)]
    return coefs, r2, resid

print("Loading PDL data from save-data/...")

# ══════════════════════════════════════════════════════════════════════
#  PHASE 1: LOAD PDL DATA
# ══════════════════════════════════════════════════════════════════════
with open(os.path.join(SAVE_DIR, 'puzzles-index.json')) as f:
    puzzles_index = json.load(f)

# Map level IDs to dates, and load each level file
pdl_puzzles = {}   # keyed by level id
level_to_date = {}
date_to_level = {}

for entry in puzzles_index['puzzles']:
    lid = entry['id']
    date = entry.get('date', '')
    level_file = os.path.join(SAVE_DIR, f'{lid}.json')
    if not os.path.exists(level_file):
        continue
    with open(level_file) as f:
        pdata = json.load(f)
    pdl_puzzles[lid] = pdata
    pdl_puzzles[lid]['_index'] = entry
    if date:
        level_to_date[lid] = date
        date_to_level[date] = lid

print(f"  Loaded {len(pdl_puzzles)} puzzle PDL files")
print(f"  Dated puzzles: {len(level_to_date)}")

# Extract per-row PDL features
pdl_rows = []  # flat list of all rows across all puzzles
pdl_puzzle_features = {}  # keyed by level id

for lid, pdata in pdl_puzzles.items():
    rows = pdata.get('rows', [])
    relink = pdata.get('relink', {})
    decoys = pdata.get('decoys', [])
    board = pdata.get('board', {})
    date = level_to_date.get(lid, '')

    # Puzzle-level features
    manip_count = 0
    abstr_count = 0
    domains = set()
    knowledge_types = set()
    for row in rows:
        rpdl = row.get('pdl', {}).get('group', {})
        manip = rpdl.get('manipulation', ['None'])[0] if rpdl.get('manipulation') else 'None'
        abstr = rpdl.get('abstraction', ['Direct membership'])[0] if rpdl.get('abstraction') else 'Direct membership'
        know = rpdl.get('knowledge', ['General vocabulary'])[0] if rpdl.get('knowledge') else 'General vocabulary'
        kdoms = rpdl.get('knowledgeDomain', ['General'])
        if manip != 'None':
            manip_count += 1
        if abstr != 'Direct membership':
            abstr_count += 1
        for kd in kdoms:
            domains.add(kd)
        knowledge_types.add(know)

    rpdl_meta = relink.get('pdl', {}).get('metaConnection', {})
    relink_manipulation = rpdl_meta.get('manipulation', ['None'])[0] if rpdl_meta.get('manipulation') else 'None'
    relink_abstraction = rpdl_meta.get('abstraction', ['Direct membership'])[0] if rpdl_meta.get('abstraction') else 'Direct membership'
    relink_knowledge = rpdl_meta.get('knowledge', ['General vocabulary'])[0] if rpdl_meta.get('knowledge') else 'General vocabulary'
    relink_domain = rpdl_meta.get('knowledgeDomain', ['General'])[0] if rpdl_meta.get('knowledgeDomain') else 'General'

    pf = {
        'lid': lid,
        'date': date,
        'name': pdata.get('name', lid),
        'phase2TileCount': board.get('phase2TileCount', 1),
        'decoyCount': len(decoys),
        'specialistGroupCount': board.get('specialistGroupCount', 0),
        'isThemed': board.get('isThemed', False),
        'manipulationComplexity': manip_count,
        'abstractionComplexity': abstr_count,
        'knowledgeBreadth': len(domains),
        'hasSpecialist': 'Specialist cultural' in knowledge_types,
        'relink_manipulation': relink_manipulation,
        'relink_abstraction': relink_abstraction,
        'relink_knowledge': relink_knowledge,
        'relink_domain': relink_domain,
        'relink_answer': relink.get('answer', ''),
        'decoys': decoys,
    }
    pdl_puzzle_features[lid] = pf

    # Per-row features
    for row in rows:
        rpdl = row.get('pdl', {})
        group = rpdl.get('group', {})
        impostor_pdl = rpdl.get('impostor', {})

        manip = group.get('manipulation', ['None'])[0] if group.get('manipulation') else 'None'
        abstr = group.get('abstraction', ['Direct membership'])[0] if group.get('abstraction') else 'Direct membership'
        know = group.get('knowledge', ['General vocabulary'])[0] if group.get('knowledge') else 'General vocabulary'
        kdom = group.get('knowledgeDomain', ['General'])[0] if group.get('knowledgeDomain') else 'General'
        imp_dom = impostor_pdl.get('realIdentityDomain', ['General'])[0] if impostor_pdl.get('realIdentityDomain') else 'General'

        # Find the impostor tile and relink tiles
        impostor_word = ''
        relink_words = []
        non_impostor_words = []
        for tile in row.get('tiles', []):
            if tile.get('isImpostor'):
                impostor_word = tile['text']
            else:
                non_impostor_words.append(tile['text'])
            if tile.get('isRelink'):
                relink_words.append(tile['text'])

        same_domain = (kdom == imp_dom)

        pdl_rows.append({
            'lid': lid,
            'date': date,
            'puzzle_name': pdata.get('name', lid),
            'row_position': row.get('position', 0),
            'row_id': row.get('id', ''),
            'category': row.get('category', ''),
            'manipulation': manip,
            'abstraction': abstr,
            'knowledge': know,
            'knowledgeDomain': kdom,
            'impostor_domain': imp_dom,
            'same_domain': same_domain,
            'impostor_word': impostor_word,
            'non_impostor_words': non_impostor_words,
            'relink_words': relink_words,
            'tile_ids': [t['id'] for t in row.get('tiles', [])],
        })

print("Loading behaviour data from CSVs...")

# ══════════════════════════════════════════════════════════════════════
#  PHASE 1b: LOAD BEHAVIOUR DATA
# ══════════════════════════════════════════════════════════════════════
raw_sessions = {}
for sf in SESSION_FILES:
    with open(sf) as f:
        for row in csv.DictReader(f):
            raw_sessions[row['id']] = row

sessions_by_date = defaultdict(dict)
for sid, row in raw_sessions.items():
    dur = int(row['duration'])
    country = row['country']
    city = row.get('city', '')
    is_bot = (country in ('NL', 'IE') and dur <= 10) or dur <= 2
    is_dev = city == 'Västerås' and country == 'SE'
    if is_bot or is_dev:
        continue
    d = row['created_at'][:10]
    sessions_by_date[d][sid] = row

raw_events = {}
for ef in EVENT_FILES:
    with open(ef) as f:
        for row in csv.DictReader(f):
            raw_events[row['id']] = row

events_by_date = defaultdict(list)
for row in raw_events.values():
    props = parse_props(row.get('properties', '{}'))
    if props.get('game_id') != 'relink':
        continue
    row['_ts'] = parse_ts(row['created_at'])
    row['_props'] = props
    d = row['created_at'][:10]
    events_by_date[d].append(row)

ALL_DATES = sorted(sessions_by_date.keys() | events_by_date.keys())

for d in ALL_DATES:
    events_by_date[d].sort(key=lambda e: e['created_at'])

MONTH_NAMES = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',
               7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
def date_label(d):
    parts = d.split('-')
    return f"{MONTH_NAMES[int(parts[1])]} {int(parts[2])}"

# Match events to sessions
def match_events(sessions, events):
    events_by_country = defaultdict(list)
    for ev in events:
        events_by_country[ev['country']].append(ev)
    result = {}
    for sid, sess in sessions.items():
        s_start = parse_ts(sess['created_at'])
        s_end = parse_ts(sess['ended_at'])
        if not s_start or not s_end:
            continue
        margin = timedelta(milliseconds=200)
        bucket = events_by_country.get(sess['country'], [])
        matched = [ev for ev in bucket
                   if ev['_ts'] and (s_start - margin) <= ev['_ts'] <= (s_end + margin)
                   and (ev['city'] == sess['city'] or not ev['city'] or not sess['city'])]
        if matched:
            result[sid] = matched
    return result

# Build player data per date
def build_players(sessions, event_sessions):
    players = []
    for sid, events in event_sessions.items():
        sess = sessions[sid]
        real_guesses = []
        relink_guesses = []

        sorted_events = sorted(events, key=lambda e: e['created_at'])
        for ev in sorted_events:
            ep = ev['_props']
            if ev['name'] == 'relink_guess_submitted':
                att = ep.get('attempts_remaining', '')
                try:
                    if int(att) > 4: continue  # tutorial
                except (ValueError, TypeError):
                    continue
                g = {
                    'ts': ev['_ts'],
                    'phase': ep.get('phase', ''),
                    'is_correct': ep.get('is_correct') == 'true',
                    'word': ep.get('selected_word', ''),
                    'row': ep.get('row_index', ''),
                    'tiles': ep.get('selected_tile_ids', ''),
                    'attempts': att,
                }
                if g['phase'] == 'relink':
                    relink_guesses.append(g)
                else:
                    real_guesses.append(g)

        if not real_guesses and not relink_guesses:
            continue

        outcome = None
        puzzle_date = None
        for ev in sorted_events:
            if ev['name'] == 'level_completed':
                ep = ev['_props']
                is_won = ep.get('is_won', ep.get('outcome', ''))
                if is_won in ('true', 'WON'):
                    outcome = 'WON'
                elif is_won in ('false', 'LOST'):
                    outcome = 'LOST'
                puzzle_date = ep.get('puzzle_date', '')

        if not outcome:
            outcome = 'INCOMPLETE'

        wrong_imposters = [g for g in real_guesses if not g['is_correct']]

        # Tester filter
        if outcome not in ('WON', 'LOST') and len(wrong_imposters) == 0:
            continue

        # Row order (order of first attempt per row)
        row_order = []
        for g in real_guesses:
            if g['row'] not in row_order:
                row_order.append(g['row'])

        all_guesses_sorted = sorted(real_guesses + relink_guesses, key=lambda g: g['ts'])
        solve_time = (all_guesses_sorted[-1]['ts'] - all_guesses_sorted[0]['ts']).total_seconds() if len(all_guesses_sorted) > 1 else 0

        rows_completed = set()
        for g in real_guesses:
            if g['is_correct']:
                rows_completed.add(g['row'])

        players.append({
            'sid': sid,
            'outcome': outcome,
            'puzzle_date': puzzle_date or '',
            'real_guesses': real_guesses,
            'relink_guesses': relink_guesses,
            'wrong_imposters': wrong_imposters,
            'row_order': row_order,
            'solve_time': solve_time,
            'num_wrong': len(wrong_imposters),
            'rows_completed': rows_completed,
        })
    return players

# Build players for each date
players_by_date = {}
for d in ALL_DATES:
    es = match_events(sessions_by_date[d], events_by_date[d])
    players_by_date[d] = build_players(sessions_by_date[d], es)

print("  Loaded behaviour data")

# ══════════════════════════════════════════════════════════════════════
#  PHASE 1c: JOIN PDL ↔ BEHAVIOUR
# ══════════════════════════════════════════════════════════════════════
# Find overlap: dates that exist in both PDL and behaviour
overlap_dates = sorted(set(date_to_level.keys()) & set(d for d in ALL_DATES if players_by_date.get(d)))
print(f"  Overlapping dates (PDL + behaviour): {len(overlap_dates)}")

# Per-date summary
date_summaries = {}
for d in overlap_dates:
    pp = players_by_date[d]
    lid = date_to_level[d]
    wins = sum(1 for p in pp if p['outcome'] == 'WON')
    losses = sum(1 for p in pp if p['outcome'] == 'LOST')
    incomplete = sum(1 for p in pp if p['outcome'] == 'INCOMPLETE')
    completions = wins + losses
    solve_rate = wins / completions if completions else 0
    times = [p['solve_time'] for p in pp if p['outcome'] == 'WON' and p['solve_time'] > 0]

    # Row-level metrics
    row_metrics = {}
    for row_pos in range(4):
        rp = str(row_pos)
        attempts = 0
        first_try = 0
        never_correct = 0
        wrong_count = 0
        wrong_words = Counter()
        correct_words = Counter()

        # Track attempt position for this row (was it attempted 1st, 2nd, 3rd, 4th?)
        attempt_positions = []
        first_try_by_position = defaultdict(lambda: [0, 0])  # [correct, total]

        for p in pp:
            # Check if this player attempted this row
            row_guesses = [g for g in p['real_guesses'] if g['row'] == rp]
            if not row_guesses:
                continue
            attempts += 1

            # What position was this row attempted in?
            if rp in p['row_order']:
                pos = p['row_order'].index(rp)
                attempt_positions.append(pos)
            else:
                pos = -1

            first_guess_correct = row_guesses[0]['is_correct']
            if first_guess_correct:
                first_try += 1
                correct_words[row_guesses[0]['word']] += 1
            else:
                wrong_words[row_guesses[0]['word']] += 1

            if pos >= 0:
                first_try_by_position[pos][1] += 1
                if first_guess_correct:
                    first_try_by_position[pos][0] += 1

            row_wrongs = [g for g in row_guesses if not g['is_correct']]
            wrong_count += len(row_wrongs)

            any_correct = any(g['is_correct'] for g in row_guesses)
            if not any_correct:
                never_correct += 1

            for g in row_wrongs:
                wrong_words[g['word']] += 1

        row_metrics[row_pos] = {
            'attempts': attempts,
            'first_try': first_try,
            'first_try_pct': first_try / attempts if attempts else 0,
            'never_correct': never_correct,
            'never_correct_pct': never_correct / attempts if attempts else 0,
            'wrong_count': wrong_count,
            'avg_wrong': wrong_count / attempts if attempts else 0,
            'top_wrong': wrong_words.most_common(5),
            'attempt_positions': attempt_positions,
            'first_try_by_position': dict(first_try_by_position),
        }

    # Relink metrics
    relink_attempts_list = []
    relink_first_try = 0
    relink_total = 0
    for p in pp:
        if p['relink_guesses']:
            relink_total += 1
            relink_attempts_list.append(len(p['relink_guesses']))
            if p['relink_guesses'][0]['is_correct']:
                relink_first_try += 1

    # Inter-correct timing analysis
    inter_correct_intervals = []  # list of (position, interval_seconds) across all players
    speed_up_ratios = []

    for p in pp:
        if p['outcome'] not in ('WON', 'LOST'):
            continue
        # Get correct impostor guesses in order (one per unique row)
        correct_guesses = []
        seen_rows = set()
        for g in sorted(p['real_guesses'], key=lambda g: g['ts']):
            if g['is_correct'] and g['row'] not in seen_rows:
                correct_guesses.append(g)
                seen_rows.add(g['row'])

        if len(correct_guesses) < 2:
            continue

        # Compute inter-correct intervals (positions 1, 2, 3 for a 4-row game)
        intervals = []
        for i in range(1, len(correct_guesses)):
            dt = (correct_guesses[i]['ts'] - correct_guesses[i-1]['ts']).total_seconds()
            intervals.append(dt)
            inter_correct_intervals.append((i, dt))

        if not intervals:
            continue

        # Speed-up ratio
        if intervals[0] > 0:
            ratio = intervals[-1] / intervals[0]
            speed_up_ratios.append(ratio)

    date_summaries[d] = {
        'lid': lid,
        'date': d,
        'label': date_label(d),
        'name': pdl_puzzle_features[lid]['name'],
        'players': len(pp),
        'wins': wins,
        'losses': losses,
        'incomplete': incomplete,
        'completions': completions,
        'solve_rate': solve_rate,
        'median_time': safe_median(times),
        'row_metrics': row_metrics,
        'relink_first_try': relink_first_try,
        'relink_total': relink_total,
        'relink_first_try_pct': relink_first_try / relink_total if relink_total else 0,
        'relink_avg_attempts': safe_mean(relink_attempts_list),
        'inter_correct_intervals': inter_correct_intervals,
        'speed_up_ratios': speed_up_ratios,
    }

print(f"  Built summaries for {len(date_summaries)} puzzle dates")

# Aggregate inter-correct timing across all dates (positions 1-3 only)
all_intervals_by_pos = defaultdict(list)
for d in date_summaries:
    for pos, iv in date_summaries[d]['inter_correct_intervals']:
        if pos <= 3:  # 4 rows → max 3 transitions
            all_intervals_by_pos[pos].append(iv)

aggregate_timing = {}
for pos in sorted(all_intervals_by_pos):
    vals = all_intervals_by_pos[pos]
    aggregate_timing[pos] = {
        'p10': round(percentile(vals, 10), 2),
        'p25': round(percentile(vals, 25), 2),
        'median': round(percentile(vals, 50), 2),
        'p75': round(percentile(vals, 75), 2),
        'p90': round(percentile(vals, 90), 2),
        'mean': round(safe_mean(vals), 2),
        'n': len(vals),
    }

_agg_parts = [f"pos {p}: median {aggregate_timing[p]['median']}s (n={aggregate_timing[p]['n']})" for p in sorted(aggregate_timing)]
print(f"  Aggregate timing: {', '.join(_agg_parts)}")

# ══════════════════════════════════════════════════════════════════════
#  PHASE 2: PDL CROSS-TABS
# ══════════════════════════════════════════════════════════════════════
print("Running PDL cross-tab analysis...")

# Join row-level PDL with behavioural metrics
row_joined = []
for pr in pdl_rows:
    if not pr['date'] or pr['date'] not in date_summaries:
        continue
    ds = date_summaries[pr['date']]
    rm = ds['row_metrics'].get(pr['row_position'], {})
    if not rm or rm['attempts'] == 0:
        continue
    row_joined.append({**pr, **rm})

print(f"  Joined rows with behaviour: {len(row_joined)}")

# Cross-tab computations for each axis
def cross_tab(rows, field):
    groups = defaultdict(list)
    for r in rows:
        groups[r[field]].append(r)
    result = {}
    for label, group_rows in sorted(groups.items()):
        result[label] = {
            'n': len(group_rows),
            'mean_first_try': safe_mean([r['first_try_pct'] for r in group_rows]),
            'mean_avg_wrong': safe_mean([r['avg_wrong'] for r in group_rows]),
            'mean_never_correct': safe_mean([r['never_correct_pct'] for r in group_rows]),
        }
    return result

ct_manipulation = cross_tab(row_joined, 'manipulation')
ct_abstraction = cross_tab(row_joined, 'abstraction')
ct_knowledge = cross_tab(row_joined, 'knowledge')
ct_domain = cross_tab(row_joined, 'knowledgeDomain')
ct_imp_domain = cross_tab(row_joined, 'impostor_domain')
ct_same_domain = cross_tab(row_joined, 'same_domain')

# 2D heatmap: manipulation x abstraction
heatmap_data = defaultdict(lambda: {'first_try_vals': [], 'n': 0})
for r in row_joined:
    key = (r['manipulation'], r['abstraction'])
    heatmap_data[key]['first_try_vals'].append(r['first_try_pct'])
    heatmap_data[key]['n'] += 1

heatmap_results = {}
for (manip, abstr), data in heatmap_data.items():
    heatmap_results[(manip, abstr)] = {
        'mean_first_try': safe_mean(data['first_try_vals']),
        'n': data['n']
    }

# ══════════════════════════════════════════════════════════════════════
#  PHASE 3: PUZZLE-LEVEL CORRELATIONS & REGRESSION
# ══════════════════════════════════════════════════════════════════════
print("Running puzzle-level correlations...")

# Build feature/outcome vectors for dated puzzles
puzzle_data = []
for d in overlap_dates:
    ds = date_summaries[d]
    pf = pdl_puzzle_features[ds['lid']]
    puzzle_data.append({**pf, **ds})

# Correlation targets
corr_features = [
    ('phase2TileCount', 'Phase 2 Tile Count'),
    ('decoyCount', 'Decoy Count'),
    ('manipulationComplexity', 'Manipulation Complexity'),
    ('abstractionComplexity', 'Abstraction Complexity'),
    ('knowledgeBreadth', 'Knowledge Breadth'),
    ('specialistGroupCount', 'Specialist Group Count'),
]

correlations = {}
for feat, label in corr_features:
    xs = [p[feat] for p in puzzle_data]
    ys = [p['solve_rate'] for p in puzzle_data]
    r, p_val = pearson(xs, ys)
    rs, ps = spearman(xs, ys)
    correlations[feat] = {'label': label, 'pearson_r': r, 'pearson_p': p_val,
                          'spearman_r': rs, 'spearman_p': ps,
                          'xs': xs, 'ys': ys}

# Multiple regression: solve_rate ~ manipComplexity + abstrComplexity + phase2TileCount + players (covariate)
X_multi = [[p['manipulationComplexity'], p['abstractionComplexity'],
            p['phase2TileCount'], p['players']] for p in puzzle_data]
y_multi = [p['solve_rate'] for p in puzzle_data]
multi_labels = ['Intercept', 'Manipulation Complexity', 'Abstraction Complexity',
                'Phase2 Tile Count', 'Player Count (covariate)']
multi_coefs, multi_r2, multi_resid = ols_multi(X_multi, y_multi)

# LOO cross-validation
loo_errors = []
for i in range(len(puzzle_data)):
    X_loo = [X_multi[j] for j in range(len(puzzle_data)) if j != i]
    y_loo = [y_multi[j] for j in range(len(puzzle_data)) if j != i]
    c, _, _ = ols_multi(X_loo, y_loo)
    pred = c[0] + sum(c[k+1] * X_multi[i][k] for k in range(len(X_multi[i])))
    loo_errors.append(abs(y_multi[i] - pred))
loo_mae = safe_mean(loo_errors)

# ══════════════════════════════════════════════════════════════════════
#  PHASE 4: ROW-LEVEL REGRESSION
# ══════════════════════════════════════════════════════════════════════
print("Running row-level regression...")

# Encode categorical features
manip_cats = sorted(set(r['manipulation'] for r in row_joined))
abstr_cats = sorted(set(r['abstraction'] for r in row_joined))
know_cats = sorted(set(r['knowledge'] for r in row_joined))

# One-hot encode (drop first category as reference)
def one_hot(value, categories):
    return [1 if value == c else 0 for c in categories[1:]]

row_X = []
row_y = []
row_feature_names = ['Intercept']
for c in manip_cats[1:]:
    row_feature_names.append(f'manip:{c}')
for c in abstr_cats[1:]:
    row_feature_names.append(f'abstr:{c}')
for c in know_cats[1:]:
    row_feature_names.append(f'know:{c}')
row_feature_names.append('same_domain')

for r in row_joined:
    features = one_hot(r['manipulation'], manip_cats) + \
               one_hot(r['abstraction'], abstr_cats) + \
               one_hot(r['knowledge'], know_cats) + \
               [1 if r['same_domain'] else 0]
    row_X.append(features)
    row_y.append(r['first_try_pct'])

row_coefs, row_r2, row_resid = ols_multi(row_X, row_y)

# Position-controlled regression: same as row regression but with mean attempt position as covariate
# This controls for vertical inference rather than filtering to position 0 only
pos_controlled_feature_names = row_feature_names + ['mean_attempt_position']
pos_X = []
pos_y = []
for r in row_joined:
    mean_pos = safe_mean(r['attempt_positions']) if r['attempt_positions'] else 0
    features = one_hot(r['manipulation'], manip_cats) + \
               one_hot(r['abstraction'], abstr_cats) + \
               one_hot(r['knowledge'], know_cats) + \
               [1 if r['same_domain'] else 0, mean_pos]
    pos_X.append(features)
    pos_y.append(r['first_try_pct'])

pos_coefs, pos_r2, _ = ols_multi(pos_X, pos_y) if pos_X else ([0], 0, [])

# ══════════════════════════════════════════════════════════════════════
#  PHASE 4b: VERTICAL INFERENCE
# ══════════════════════════════════════════════════════════════════════
print("Running vertical inference analysis...")

# Theme transparency: per puzzle, after 2 correct, what % get 3rd first-try?
transparency_scores = {}
for d in overlap_dates:
    ds = date_summaries[d]
    pf = pdl_puzzle_features[ds['lid']]
    pp = players_by_date[d]

    after_2_correct_first_try = 0
    after_2_total = 0

    for p in pp:
        if p['outcome'] not in ('WON', 'LOST'):
            continue
        correct_order = []
        for g in sorted(p['real_guesses'], key=lambda g: g['ts']):
            if g['is_correct'] and g['row'] not in [c['row'] for c in correct_order]:
                correct_order.append(g)

        if len(correct_order) >= 3:
            after_2_total += 1
            # Was the 3rd correct guess first-try for that row?
            third_row = correct_order[2]['row']
            row_guesses_before_3rd = [g for g in sorted(p['real_guesses'], key=lambda g: g['ts'])
                                       if g['row'] == third_row]
            if row_guesses_before_3rd and row_guesses_before_3rd[0]['is_correct']:
                after_2_correct_first_try += 1

    transparency_scores[d] = {
        'n': after_2_total,
        'first_try_after_2': after_2_correct_first_try / after_2_total if after_2_total else 0,
        'relink_manipulation': pf['relink_manipulation'],
        'relink_abstraction': pf['relink_abstraction'],
    }

# ══════════════════════════════════════════════════════════════════════
#  PHASE 5: DECOY & CONFUSION ANALYSIS
# ══════════════════════════════════════════════════════════════════════
print("Running decoy & confusion analysis...")

# Compare puzzles with 0 decoys vs 1+ decoys
decoy0 = [ds for ds in date_summaries.values()
          if pdl_puzzle_features[ds['lid']]['decoyCount'] == 0]
decoy1plus = [ds for ds in date_summaries.values()
              if pdl_puzzle_features[ds['lid']]['decoyCount'] > 0]

decoy_comparison = {
    'no_decoys': {
        'n': len(decoy0),
        'mean_solve_rate': safe_mean([ds['solve_rate'] for ds in decoy0]),
        'mean_avg_wrong': safe_mean([safe_mean([ds['row_metrics'][r]['avg_wrong']
                                                 for r in ds['row_metrics']]) for ds in decoy0]) if decoy0 else 0,
    },
    'has_decoys': {
        'n': len(decoy1plus),
        'mean_solve_rate': safe_mean([ds['solve_rate'] for ds in decoy1plus]),
        'mean_avg_wrong': safe_mean([safe_mean([ds['row_metrics'][r]['avg_wrong']
                                                 for r in ds['row_metrics']]) for ds in decoy1plus]) if decoy1plus else 0,
    }
}

# Decoy hit rate: do wrong guesses match decoy-designed tiles?
decoy_hit_analysis = []
for d in overlap_dates:
    ds = date_summaries[d]
    lid = ds['lid']
    pdata = pdl_puzzles[lid]
    decoys = pdata.get('decoys', [])
    if not decoys:
        continue

    # Collect all decoy tile IDs
    decoy_tile_ids = set()
    for dec in decoys:
        for tid in dec.get('tileIds', []):
            decoy_tile_ids.add(tid)

    # Find impostor words that are in decoy tiles
    decoy_impostor_words = set()
    for row in pdata.get('rows', []):
        for tile in row.get('tiles', []):
            if tile['id'] in decoy_tile_ids and not tile.get('isImpostor', False):
                decoy_impostor_words.add(tile['text'].lower())

    # Count wrong guesses that match decoy tiles
    total_wrong = 0
    decoy_wrong = 0
    pp = players_by_date[d]
    for p in pp:
        for g in p.get('wrong_imposters', []):
            total_wrong += 1
            if g['word'].lower() in decoy_impostor_words:
                decoy_wrong += 1

    decoy_hit_analysis.append({
        'date': d,
        'label': date_label(d),
        'name': pdl_puzzle_features[lid]['name'],
        'decoy_count': len(decoys),
        'total_wrong': total_wrong,
        'decoy_wrong': decoy_wrong,
        'hit_rate': decoy_wrong / total_wrong if total_wrong else 0,
        'descriptions': [dec.get('pdl', {}).get('description', '') for dec in decoys],
    })

# Cross-row confusion: when wrong, which row's tiles did they pick?
confusion_data = {}
for d in overlap_dates:
    ds = date_summaries[d]
    lid = ds['lid']
    pdata = pdl_puzzles[lid]

    # Build tile->row mapping
    tile_to_row = {}
    word_to_row = {}
    for row in pdata.get('rows', []):
        rpos = row['position']
        for tile in row.get('tiles', []):
            tile_to_row[tile['id']] = rpos
            word_to_row[tile['text'].lower()] = rpos

    # For each wrong guess, find which row's tile was picked
    confusion_matrix = [[0]*4 for _ in range(4)]  # [guessed_in_row][tile_from_row]
    pp = players_by_date[d]
    for p in pp:
        for g in p.get('wrong_imposters', []):
            guessed_row = int(g['row']) if g['row'].isdigit() else -1
            tile_row = word_to_row.get(g['word'].lower(), -1)
            if 0 <= guessed_row < 4 and 0 <= tile_row < 4:
                confusion_matrix[guessed_row][tile_row] += 1

    confusion_data[d] = {
        'matrix': confusion_matrix,
        'label': date_label(d),
        'name': pdl_puzzle_features[lid]['name'],
    }

# ══════════════════════════════════════════════════════════════════════
#  PHASE 6: RELINK PHASE PDL
# ══════════════════════════════════════════════════════════════════════
print("Running relink phase analysis...")

relink_by_manip = defaultdict(list)
relink_by_tiles = defaultdict(list)
for d in overlap_dates:
    ds = date_summaries[d]
    pf = pdl_puzzle_features[ds['lid']]
    relink_by_manip[pf['relink_manipulation']].append(ds)
    relink_by_tiles[pf['phase2TileCount']].append(ds)

relink_manip_stats = {}
for manip, dss in sorted(relink_by_manip.items()):
    relink_manip_stats[manip] = {
        'n': len(dss),
        'mean_first_try': safe_mean([ds['relink_first_try_pct'] for ds in dss]),
        'mean_attempts': safe_mean([ds['relink_avg_attempts'] for ds in dss]),
    }

relink_tile_stats = {}
for tc, dss in sorted(relink_by_tiles.items()):
    relink_tile_stats[tc] = {
        'n': len(dss),
        'mean_first_try': safe_mean([ds['relink_first_try_pct'] for ds in dss]),
        'mean_attempts': safe_mean([ds['relink_avg_attempts'] for ds in dss]),
        'mean_solve_rate': safe_mean([ds['solve_rate'] for ds in dss]),
    }

# ══════════════════════════════════════════════════════════════════════
#  PHASE 7: CLUSTERING
# ══════════════════════════════════════════════════════════════════════
print("Running clustering analysis...")

# Feature vector per puzzle: counts of each PDL category
all_manips = sorted(set(r['manipulation'] for r in pdl_rows))
all_abstrs = sorted(set(r['abstraction'] for r in pdl_rows))
all_knows = sorted(set(r['knowledge'] for r in pdl_rows))

def puzzle_feature_vec(lid):
    rows = [r for r in pdl_rows if r['lid'] == lid]
    pf = pdl_puzzle_features[lid]
    vec = []
    # Manipulation type counts
    for m in all_manips:
        vec.append(sum(1 for r in rows if r['manipulation'] == m))
    # Abstraction type counts
    for a in all_abstrs:
        vec.append(sum(1 for r in rows if r['abstraction'] == a))
    # Knowledge type counts
    for k in all_knows:
        vec.append(sum(1 for r in rows if r['knowledge'] == k))
    # Board features
    vec.append(pf['phase2TileCount'])
    vec.append(pf['decoyCount'])
    vec.append(pf['specialistGroupCount'])
    return vec

puzzle_vecs = {}
for lid in pdl_puzzles:
    puzzle_vecs[lid] = puzzle_feature_vec(lid)

# Simple k-means (k=3)
def euclidean(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

def kmeans(vecs, k=3, max_iter=100):
    items = list(vecs.keys())
    n = len(items)
    dim = len(next(iter(vecs.values())))

    # Initialise centroids by picking spread-out items
    centroids = [list(vecs[items[i * n // k]]) for i in range(k)]
    assignments = {}

    for _ in range(max_iter):
        # Assign
        new_assignments = {}
        for item in items:
            dists = [euclidean(vecs[item], c) for c in centroids]
            new_assignments[item] = dists.index(min(dists))
        if new_assignments == assignments:
            break
        assignments = new_assignments

        # Update centroids
        for ci in range(k):
            members = [vecs[item] for item in items if assignments[item] == ci]
            if members:
                centroids[ci] = [sum(m[d] for m in members) / len(members) for d in range(dim)]

    return assignments, centroids

cluster_assignments, cluster_centroids = kmeans(puzzle_vecs, k=3)

# Name clusters by their dominant features
cluster_profiles = {}
for ci in range(3):
    members = [lid for lid, c in cluster_assignments.items() if c == ci]
    centroid = cluster_centroids[ci]

    # Parse centroid back into feature names
    idx = 0
    profile = {}
    for m in all_manips:
        profile[f'manip_{m}'] = centroid[idx]; idx += 1
    for a in all_abstrs:
        profile[f'abstr_{a}'] = centroid[idx]; idx += 1
    for k in all_knows:
        profile[f'know_{k}'] = centroid[idx]; idx += 1
    profile['phase2TileCount'] = centroid[idx]; idx += 1
    profile['decoyCount'] = centroid[idx]; idx += 1
    profile['specialistGroupCount'] = centroid[idx]; idx += 1

    # Solve rates for dated members
    dated_members = [lid for lid in members if lid in level_to_date and level_to_date[lid] in date_summaries]
    solve_rates = [date_summaries[level_to_date[lid]]['solve_rate'] for lid in dated_members]

    cluster_profiles[ci] = {
        'members': members,
        'dated_members': dated_members,
        'centroid': profile,
        'mean_solve_rate': safe_mean(solve_rates) if solve_rates else None,
        'n_total': len(members),
        'n_dated': len(dated_members),
    }

# Auto-name clusters
for ci, cp in cluster_profiles.items():
    c = cp['centroid']
    # Find dominant manipulation
    manip_vals = {m: c.get(f'manip_{m}', 0) for m in all_manips}
    dom_manip = max(manip_vals, key=manip_vals.get)
    non_none_manip = sum(v for k, v in manip_vals.items() if 'None' not in k)

    abstr_vals = {a: c.get(f'abstr_{a}', 0) for a in all_abstrs}
    non_direct = sum(v for k, v in abstr_vals.items() if 'Direct' not in k)

    if non_none_manip > 1.5:
        name = "Complex Manipulation"
    elif non_direct > 0.8:
        name = "Abstract Reasoning"
    else:
        name = "Straightforward"

    # Refine with knowledge
    know_spec = c.get('know_Specialist cultural', 0)
    if know_spec > 0.5:
        name += " + Specialist"

    cp['name'] = name

# Row-level clustering: cluster the 56 joined rows
def row_feature_vec(r):
    vec = [1 if r['manipulation'] == m else 0 for m in all_manips]
    vec += [1 if r['abstraction'] == a else 0 for a in all_abstrs]
    vec += [1 if r['knowledge'] == k else 0 for k in all_knows]
    vec += [1 if r['same_domain'] else 0]
    return vec

row_vecs_map = {}
for i, r in enumerate(row_joined):
    row_vecs_map[i] = row_feature_vec(r)

row_cluster_assignments, row_cluster_centroids = kmeans(row_vecs_map, k=4)

row_cluster_stats = {}
for ci in range(4):
    members = [i for i, c in row_cluster_assignments.items() if c == ci]
    if not members:
        continue
    member_rows = [row_joined[i] for i in members]

    # Find dominant features
    manip_counts = Counter(r['manipulation'] for r in member_rows)
    abstr_counts = Counter(r['abstraction'] for r in member_rows)
    know_counts = Counter(r['knowledge'] for r in member_rows)

    row_cluster_stats[ci] = {
        'n': len(members),
        'mean_first_try': safe_mean([r['first_try_pct'] for r in member_rows]),
        'mean_avg_wrong': safe_mean([r['avg_wrong'] for r in member_rows]),
        'dom_manipulation': manip_counts.most_common(1)[0][0] if manip_counts else 'None',
        'dom_abstraction': abstr_counts.most_common(1)[0][0] if abstr_counts else 'Direct membership',
        'dom_knowledge': know_counts.most_common(1)[0][0] if know_counts else 'General vocabulary',
        'manip_dist': dict(manip_counts),
        'abstr_dist': dict(abstr_counts),
    }

# ══════════════════════════════════════════════════════════════════════
#  PHASE 8: PREDICTIONS
# ══════════════════════════════════════════════════════════════════════
print("Computing difficulty predictions...")

# Use row-level regression coefficients to score every row, then aggregate
def predict_row_difficulty(r):
    features = one_hot(r['manipulation'], manip_cats) + \
               one_hot(r['abstraction'], abstr_cats) + \
               one_hot(r['knowledge'], know_cats) + \
               [1 if r.get('same_domain', False) else 0]
    if len(row_coefs) != len(features) + 1:
        return 0.5  # fallback
    return row_coefs[0] + sum(row_coefs[i+1] * features[i] for i in range(len(features)))

def predict_puzzle_solve_rate(lid):
    rows = [r for r in pdl_rows if r['lid'] == lid]
    if not rows:
        return 0.5
    row_diffs = [predict_row_difficulty(r) for r in rows]
    # Puzzle solve rate approximation: average row difficulty
    avg_row = safe_mean(row_diffs)
    return max(0, min(1, avg_row))

predictions = []
for lid, pdata in pdl_puzzles.items():
    pf = pdl_puzzle_features[lid]
    pred = predict_puzzle_solve_rate(lid)
    actual = None
    if lid in level_to_date and level_to_date[lid] in date_summaries:
        actual = date_summaries[level_to_date[lid]]['solve_rate']
    predictions.append({
        'lid': lid,
        'name': pf['name'],
        'date': pf['date'],
        'predicted': pred,
        'actual': actual,
        'phase2TileCount': pf['phase2TileCount'],
        'manipulationComplexity': pf['manipulationComplexity'],
        'abstractionComplexity': pf['abstractionComplexity'],
        'cluster': cluster_assignments.get(lid, -1),
    })

predictions.sort(key=lambda p: p['predicted'])

# Validation: actual vs predicted for dated puzzles
dated_preds = [p for p in predictions if p['actual'] is not None]
pred_vs_actual_r, _ = pearson([p['predicted'] for p in dated_preds],
                               [p['actual'] for p in dated_preds]) if dated_preds else (0, 1)
pred_mae = safe_mean([abs(p['predicted'] - p['actual']) for p in dated_preds]) if dated_preds else 0

# ══════════════════════════════════════════════════════════════════════
#  PHASE 9: GENERATE HTML REPORT
# ══════════════════════════════════════════════════════════════════════
print("Generating HTML report...")

# Prepare JSON data for charts
def to_json(obj):
    return json.dumps(obj)

# Chart data preparation
chart_data = {}

# Cross-tab bar charts
for axis_name, ct in [('Manipulation', ct_manipulation), ('Abstraction', ct_abstraction),
                       ('Knowledge', ct_knowledge), ('Knowledge Domain', ct_domain)]:
    chart_data[axis_name] = {
        'labels': list(ct.keys()),
        'first_try': [ct[k]['mean_first_try'] * 100 for k in ct],
        'avg_wrong': [ct[k]['mean_avg_wrong'] for k in ct],
        'never_correct': [ct[k]['mean_never_correct'] * 100 for k in ct],
        'n': [ct[k]['n'] for k in ct],
    }

# Heatmap data
all_manips_hm = sorted(set(k[0] for k in heatmap_results))
all_abstrs_hm = sorted(set(k[1] for k in heatmap_results))
hm_values = []
hm_annotations = []
for a in all_abstrs_hm:
    row_vals = []
    row_anns = []
    for m in all_manips_hm:
        data = heatmap_results.get((m, a), {'mean_first_try': None, 'n': 0})
        if data['n'] > 0:
            row_vals.append(round(data['mean_first_try'] * 100, 1))
            row_anns.append(f"{data['mean_first_try']*100:.0f}% (n={data['n']})")
        else:
            row_vals.append(None)
            row_anns.append('')
    hm_values.append(row_vals)
    hm_annotations.append(row_anns)

# Scatter data
scatter_data = {}
for feat, label in corr_features:
    c = correlations[feat]
    scatter_data[feat] = {
        'label': label,
        'xs': c['xs'],
        'ys': [round(y * 100, 1) for y in c['ys']],
        'pearson_r': round(c['pearson_r'], 3),
        'spearman_r': round(c['spearman_r'], 3),
        'labels': [date_summaries[d]['name'] for d in overlap_dates],
    }

# Regression data
regression_data = {
    'puzzle': {
        'names': multi_labels,
        'coefs': [round(c, 4) for c in multi_coefs],
        'r2': round(multi_r2, 3),
        'loo_mae': round(loo_mae * 100, 1),
        'residuals': [round(r * 100, 1) for r in multi_resid],
        'puzzle_labels': [date_summaries[d]['name'] for d in overlap_dates],
    },
    'row': {
        'names': row_feature_names,
        'coefs': [round(c, 4) for c in row_coefs],
        'r2': round(row_r2, 3),
        'n': len(row_joined),
    },
    'pos_controlled': {
        'names': pos_controlled_feature_names,
        'coefs': [round(c, 4) for c in pos_coefs] if pos_coefs else [],
        'r2': round(pos_r2, 3),
        'n': len(pos_X),
    }
}

# Timing curve data (replaces click-point data)
# Vertical inference data: per-puzzle acceleration and transparency, cross-tabbed by all PDL features
vi_puzzle_data = []  # one entry per dated puzzle with acceleration + transparency + all PDL features

for d in overlap_dates:
    ds = date_summaries[d]
    pf = pdl_puzzle_features[ds['lid']]
    ts = transparency_scores[d]

    # Compute acceleration
    intervals_by_pos = defaultdict(list)
    for pos, iv in ds['inter_correct_intervals']:
        intervals_by_pos[pos].append(iv)
    medians = [safe_median(intervals_by_pos.get(p, [])) for p in [1, 2, 3]]
    accel_factor = medians[2] / medians[0] if (medians[0] > 0 and medians[2] > 0) else None

    vi_puzzle_data.append({
        'label': ds['label'],
        'name': ds['name'],
        'accel_factor': round(accel_factor, 3) if accel_factor is not None else None,
        'transparency': round(ts['first_try_after_2'] * 100, 1),
        'solve_rate': round(ds['solve_rate'] * 100, 1),
        # Puzzle-level PDL features for grouping
        'manipulationComplexity': pf['manipulationComplexity'],
        'abstractionComplexity': pf['abstractionComplexity'],
        'knowledgeBreadth': pf['knowledgeBreadth'],
        'phase2TileCount': pf['phase2TileCount'],
        'decoyCount': pf['decoyCount'],
        'relink_manipulation': pf['relink_manipulation'],
        'relink_abstraction': pf['relink_abstraction'],
        'hasSpecialist': pf['hasSpecialist'],
    })

# Cross-tab acceleration and transparency by each PDL feature
vi_feature_axes = [
    ('manipulationComplexity', 'Manipulation Complexity'),
    ('abstractionComplexity', 'Abstraction Complexity'),
    ('knowledgeBreadth', 'Knowledge Breadth'),
    ('phase2TileCount', 'Phase 2 Tile Count'),
    ('decoyCount', 'Decoy Count'),
    ('relink_manipulation', 'Relink Manipulation'),
    ('relink_abstraction', 'Relink Abstraction'),
    ('hasSpecialist', 'Has Specialist Knowledge'),
]

vi_crosstabs = {}
for feat_key, feat_label in vi_feature_axes:
    groups = defaultdict(list)
    for p in vi_puzzle_data:
        val = p[feat_key]
        if isinstance(val, bool):
            val = 'Yes' if val else 'No'
        groups[str(val)].append(p)

    tab = {}
    for cat in sorted(groups.keys()):
        items = groups[cat]
        accels = [p['accel_factor'] for p in items if p['accel_factor'] is not None]
        transparencies = [p['transparency'] for p in items]
        tab[cat] = {
            'n': len(items),
            'mean_accel': round(safe_mean(accels), 3) if accels else None,
            'mean_transparency': round(safe_mean(transparencies), 1),
            'mean_solve_rate': round(safe_mean([p['solve_rate'] for p in items]), 1),
            'puzzles': [p['name'] for p in items],
        }
    vi_crosstabs[feat_key] = {'label': feat_label, 'categories': tab}

# Aggregate summary
all_accels = [p['accel_factor'] for p in vi_puzzle_data if p['accel_factor'] is not None]
all_transp = [p['transparency'] for p in vi_puzzle_data]

vi_summary = {
    'median_intervals': [round(aggregate_timing.get(p, {}).get('median', 0), 1) for p in [1, 2, 3]],
    'interval_ns': [aggregate_timing.get(p, {}).get('n', 0) for p in [1, 2, 3]],
    'mean_accel': round(safe_mean(all_accels), 3) if all_accels else None,
    'n_accelerated': sum(1 for a in all_accels if a < 1),
    'n_total': len(all_accels),
    'mean_transparency': round(safe_mean(all_transp), 1),
}

vi_chart_data = {
    'puzzles': vi_puzzle_data,
    'crosstabs': {k: v for k, v in vi_crosstabs.items()},
    'summary': vi_summary,
}

# Transparency scores (kept for backward compat)
transparency_data = []
for d in overlap_dates:
    ts = transparency_scores[d]
    ds = date_summaries[d]
    transparency_data.append({
        'label': ds['label'],
        'name': ds['name'],
        'score': round(ts['first_try_after_2'] * 100, 1),
        'n': ts['n'],
        'relink_manip': ts['relink_manipulation'],
        'solve_rate': round(ds['solve_rate'] * 100, 1),
    })

# Decoy data
decoy_chart = {
    'no_decoys': decoy_comparison['no_decoys'],
    'has_decoys': decoy_comparison['has_decoys'],
    'hit_analysis': decoy_hit_analysis,
}

# Relink phase data
relink_chart_data = {
    'by_manip': relink_manip_stats,
    'by_tiles': {str(k): v for k, v in relink_tile_stats.items()},
}

# Cluster data
cluster_chart_data = {
    'puzzles': {},
    'rows': {},
}
for ci, cp in cluster_profiles.items():
    member_names = [pdl_puzzle_features[lid]['name'] for lid in cp['members']]
    cluster_chart_data['puzzles'][cp['name']] = {
        'n_total': cp['n_total'],
        'n_dated': cp['n_dated'],
        'mean_solve_rate': round(cp['mean_solve_rate'] * 100, 1) if cp['mean_solve_rate'] is not None else None,
        'members': member_names,
        'centroid': {k: round(v, 2) for k, v in cp['centroid'].items()},
    }

for ci, rcs in row_cluster_stats.items():
    label = f"{rcs['dom_manipulation']} / {rcs['dom_abstraction']}"
    cluster_chart_data['rows'][label] = {
        'n': rcs['n'],
        'mean_first_try': round(rcs['mean_first_try'] * 100, 1),
        'mean_avg_wrong': round(rcs['mean_avg_wrong'], 2),
        'manip_dist': rcs['manip_dist'],
        'abstr_dist': rcs['abstr_dist'],
    }

# Prediction data
pred_chart_data = {
    'all': [{
        'name': p['name'],
        'date': p['date'],
        'predicted': round(p['predicted'] * 100, 1),
        'actual': round(p['actual'] * 100, 1) if p['actual'] is not None else None,
        'cluster': p['cluster'],
        'manipComplexity': p['manipulationComplexity'],
        'abstrComplexity': p['abstractionComplexity'],
        'phase2Tiles': p['phase2TileCount'],
    } for p in predictions],
    'validation': {
        'r': round(pred_vs_actual_r, 3),
        'mae': round(pred_mae * 100, 1),
    }
}

# Impostor domain analysis
imp_domain_chart = {
    'same_domain': {
        'n': ct_same_domain.get(True, {'n': 0})['n'],
        'mean_first_try': round(ct_same_domain.get(True, {'mean_first_try': 0})['mean_first_try'] * 100, 1),
        'mean_avg_wrong': round(ct_same_domain.get(True, {'mean_avg_wrong': 0})['mean_avg_wrong'], 2),
    },
    'diff_domain': {
        'n': ct_same_domain.get(False, {'n': 0})['n'],
        'mean_first_try': round(ct_same_domain.get(False, {'mean_first_try': 0})['mean_first_try'] * 100, 1),
        'mean_avg_wrong': round(ct_same_domain.get(False, {'mean_avg_wrong': 0})['mean_avg_wrong'], 2),
    },
    'by_imp_domain': {k: {'n': v['n'], 'mean_first_try': round(v['mean_first_try'] * 100, 1),
                           'mean_avg_wrong': round(v['mean_avg_wrong'], 2)} for k, v in ct_imp_domain.items()},
}

# Confusion data for JSON
confusion_chart = {}
for d, cd in confusion_data.items():
    confusion_chart[date_label(d)] = {
        'name': cd['name'],
        'matrix': cd['matrix'],
    }

# ── Build HTML ──
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Relink PDL Analysis</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
:root {{
    --bg: #f5f6fa; --card: #fff; --text: #2d3436; --muted: #636e72;
    --accent: #6c5ce7; --accent2: #00b894; --danger: #d63031; --warn: #fdcb6e;
    --border: #dfe6e9;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: var(--bg); color: var(--text); line-height: 1.6; }}
.layout {{ display: flex; min-height: 100vh; }}
nav {{ width: 240px; background: #2d3436; color: #fff; padding: 20px 0;
      position: fixed; height: 100vh; overflow-y: auto; }}
nav h2 {{ padding: 0 20px 15px; font-size: 14px; color: #b2bec3; text-transform: uppercase;
          letter-spacing: 1px; }}
nav a {{ display: block; padding: 8px 20px; color: #dfe6e9; text-decoration: none;
         font-size: 13px; border-left: 3px solid transparent; }}
nav a:hover, nav a.active {{ background: rgba(255,255,255,0.05); color: #fff;
                              border-left-color: var(--accent); }}
main {{ margin-left: 240px; padding: 30px; max-width: 1200px; width: 100%; }}
h1 {{ font-size: 28px; margin-bottom: 5px; }}
.subtitle {{ color: var(--muted); margin-bottom: 30px; }}
.section {{ margin-bottom: 40px; scroll-margin-top: 20px; }}
.section h2 {{ font-size: 20px; margin-bottom: 15px; padding-bottom: 8px;
               border-bottom: 2px solid var(--accent); }}
.card {{ background: var(--card); border-radius: 12px; padding: 20px;
         box-shadow: 0 2px 10px rgba(0,0,0,0.06); margin-bottom: 20px; }}
.card h3 {{ font-size: 16px; margin-bottom: 10px; color: var(--muted); }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
               gap: 15px; margin-bottom: 20px; }}
.stat-card {{ background: var(--card); border-radius: 10px; padding: 18px;
              box-shadow: 0 2px 8px rgba(0,0,0,0.05); text-align: center; }}
.stat-card .value {{ font-size: 32px; font-weight: 700; color: var(--accent); }}
.stat-card .label {{ font-size: 12px; color: var(--muted); text-transform: uppercase;
                     letter-spacing: 0.5px; margin-top: 4px; }}
.chart-container {{ position: relative; height: 350px; margin: 10px 0; }}
.chart-container.tall {{ height: 450px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
th {{ background: #f8f9fa; font-weight: 600; position: sticky; top: 0; }}
.heatmap-grid {{ display: grid; gap: 2px; margin: 10px 0; }}
.hm-cell {{ padding: 12px 8px; text-align: center; border-radius: 6px; font-size: 12px;
            font-weight: 600; color: #fff; }}
.hm-header {{ padding: 8px; text-align: center; font-size: 11px; font-weight: 600;
              color: var(--muted); }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px;
          font-weight: 600; }}
.badge-green {{ background: #00b89420; color: #00b894; }}
.badge-amber {{ background: #fdcb6e30; color: #e17055; }}
.badge-red {{ background: #d6303120; color: #d63031; }}
.collapsible {{ cursor: pointer; user-select: none; }}
.collapsible::before {{ content: '▸ '; color: var(--muted); }}
.collapsible.open::before {{ content: '▾ '; }}
.collapse-content {{ display: none; padding-top: 10px; }}
.collapse-content.show {{ display: block; }}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
@media (max-width: 900px) {{
    nav {{ display: none; }}
    main {{ margin-left: 0; }}
    .two-col {{ grid-template-columns: 1fr; }}
}}
.confusion-grid {{ display: inline-grid; gap: 1px; background: var(--border); border-radius: 8px;
                    overflow: hidden; margin: 10px 0; }}
.confusion-cell {{ padding: 10px; text-align: center; background: var(--card); min-width: 60px; font-size: 13px; }}
.confusion-header {{ background: #f8f9fa; font-weight: 600; font-size: 11px; }}
</style>
</head>
<body>
<div class="layout">
<nav>
    <h2>PDL Analysis</h2>
    <a href="#findings">Key Findings</a>
    <a href="#crosstabs">PDL Cross-tabs</a>
    <a href="#heatmap">Difficulty Heatmap</a>
    <a href="#impostor">Impostor Domain</a>
    <a href="#correlations">Puzzle Correlations</a>
    <a href="#regression">Regression Models</a>
    <a href="#vertical">Vertical Inference</a>
    <a href="#decoys">Decoy Analysis</a>
    <a href="#confusion">Confusion Maps</a>
    <a href="#relink">Relink Phase</a>
    <a href="#clusters">Clustering</a>
    <a href="#predictions">Predictions</a>
</nav>
<main>

<h1>Relink PDL &times; Behaviour Analysis</h1>
<p class="subtitle">{len(pdl_puzzles)} puzzles analysed &middot; {len(overlap_dates)} with player data &middot;
{sum(ds['completions'] for ds in date_summaries.values())} total completions</p>

<!-- KEY FINDINGS -->
<div class="section" id="findings">
<h2>Key Findings</h2>
<div class="stats-grid" id="stats-grid"></div>
</div>

<!-- CROSS-TABS -->
<div class="section" id="crosstabs">
<h2>PDL Axis Breakdown</h2>
<p style="color:var(--muted);margin-bottom:15px;">Mean first-try correct % and average wrong guesses per row, grouped by each PDL axis. Shows which design labels correlate with harder or easier rows.</p>
<div class="two-col">
    <div class="card"><h3>By Manipulation Type</h3><div class="chart-container"><canvas id="chart-manip"></canvas></div></div>
    <div class="card"><h3>By Abstraction Type</h3><div class="chart-container"><canvas id="chart-abstr"></canvas></div></div>
    <div class="card"><h3>By Knowledge Level</h3><div class="chart-container"><canvas id="chart-know"></canvas></div></div>
    <div class="card"><h3>By Knowledge Domain</h3><div class="chart-container tall"><canvas id="chart-domain"></canvas></div></div>
</div>
</div>

<!-- HEATMAP -->
<div class="section" id="heatmap">
<h2>Manipulation &times; Abstraction Heatmap</h2>
<p style="color:var(--muted);margin-bottom:15px;">Mean first-try correct % for each combination. Darker red = harder.</p>
<div class="card" id="heatmap-container"></div>
</div>

<!-- IMPOSTOR DOMAIN -->
<div class="section" id="impostor">
<h2>Impostor Domain Analysis</h2>
<p style="color:var(--muted);margin-bottom:15px;">Do impostors from the same knowledge domain as the group fool players more?</p>
<div class="two-col">
    <div class="card"><h3>Same vs Different Domain</h3><div class="chart-container"><canvas id="chart-domain-dist"></canvas></div></div>
    <div class="card"><h3>By Impostor Domain</h3><div class="chart-container"><canvas id="chart-imp-domain"></canvas></div></div>
</div>
</div>

<!-- CORRELATIONS -->
<div class="section" id="correlations">
<h2>Puzzle-Level Correlations</h2>
<p style="color:var(--muted);margin-bottom:15px;">Board-level design parameters vs solve rate. Each point is one puzzle date.</p>
<div class="two-col" id="scatter-container"></div>
</div>

<!-- REGRESSION -->
<div class="section" id="regression">
<h2>Regression Models</h2>
<div class="two-col">
    <div class="card">
        <h3>Puzzle-Level (n={len(puzzle_data)})</h3>
        <table id="reg-puzzle-table"></table>
        <p style="margin-top:10px;color:var(--muted);font-size:13px;">
            R&sup2; = {regression_data['puzzle']['r2']} &middot; LOO-CV MAE = {regression_data['puzzle']['loo_mae']}pp
        </p>
    </div>
    <div class="card">
        <h3>Row-Level: All Rows (n={regression_data['row']['n']})</h3>
        <table id="reg-row-table"></table>
        <p style="margin-top:10px;color:var(--muted);font-size:13px;">R&sup2; = {regression_data['row']['r2']}</p>
    </div>
</div>
<div class="card" style="margin-top:20px;">
    <h3>Row-Level: Position-Controlled (n={regression_data['pos_controlled']['n']})</h3>
    <table id="reg-intrinsic-table"></table>
    <p style="margin-top:10px;color:var(--muted);font-size:13px;">
        R&sup2; = {regression_data['pos_controlled']['r2']} — Same features + mean attempt position as covariate to control for vertical inference
    </p>
</div>
<div class="card" style="margin-top:20px;">
    <h3>Regression Coefficients (Row-Level Forest Plot)</h3>
    <div class="chart-container tall"><canvas id="chart-forest"></canvas></div>
</div>
</div>

<!-- VERTICAL INFERENCE -->
<div class="section" id="vertical">
<h2>Vertical Inference &amp; Theme Transparency</h2>
<p style="color:var(--muted);margin-bottom:15px;">Which PDL features promote or inhibit vertical inference? Acceleration = ratio of last to first inter-correct interval (&lt;1 means players sped up). Transparency = % of players who got their 3rd row first-try after solving 2.</p>
<div class="card" style="margin-bottom:20px;">
    <h3>Summary</h3>
    <div id="vi-summary"></div>
</div>
<div class="card" style="margin-bottom:20px;">
    <h3>Acceleration by PDL Feature</h3>
    <p style="color:var(--muted);font-size:13px;margin-bottom:10px;">
        Mean acceleration factor per category. Lower = players sped up more (stronger vertical inference). The dashed line marks 1.0 (no change).
    </p>
    <div id="vi-accel-charts"></div>
</div>
<div class="card" style="margin-bottom:20px;">
    <h3>Transparency by PDL Feature</h3>
    <p style="color:var(--muted);font-size:13px;margin-bottom:10px;">
        Mean theme transparency (% first-try on 3rd row after 2 correct) per category. Higher = theme is more deducible.
    </p>
    <div id="vi-transp-charts"></div>
</div>
<div class="card">
    <h3>Per-Puzzle Detail</h3>
    <table id="vi-puzzle-table">
        <thead><tr><th>Puzzle</th><th>Date</th><th>Acceleration</th><th>Transparency</th><th>Solve Rate</th></tr></thead>
        <tbody></tbody>
    </table>
</div>
</div>

<!-- DECOYS -->
<div class="section" id="decoys">
<h2>Decoy Analysis</h2>
<div class="two-col">
    <div class="card">
        <h3>Puzzles With vs Without Decoys</h3>
        <div class="chart-container"><canvas id="chart-decoy-compare"></canvas></div>
    </div>
    <div class="card">
        <h3>Decoy Hit Rate</h3>
        <p style="color:var(--muted);font-size:13px;margin-bottom:10px;">What fraction of wrong guesses match tiles from designed decoy groupings?</p>
        <div class="chart-container"><canvas id="chart-decoy-hits"></canvas></div>
    </div>
</div>
</div>

<!-- CONFUSION -->
<div class="section" id="confusion">
<h2>Cross-Row Confusion</h2>
<p style="color:var(--muted);margin-bottom:15px;">When a player guesses wrong in a row, which row did the tile they picked actually belong to? High off-diagonal values indicate cross-row interference.</p>
<div id="confusion-container"></div>
</div>

<!-- RELINK PHASE -->
<div class="section" id="relink">
<h2>Relink Phase PDL</h2>
<div class="two-col">
    <div class="card">
        <h3>By Meta-Connection Manipulation</h3>
        <div class="chart-container"><canvas id="chart-relink-manip"></canvas></div>
    </div>
    <div class="card">
        <h3>By Phase 2 Tile Count</h3>
        <div class="chart-container"><canvas id="chart-relink-tiles"></canvas></div>
    </div>
</div>
</div>

<!-- CLUSTERING -->
<div class="section" id="clusters">
<h2>Puzzle &amp; Row Archetypes</h2>
<div class="two-col">
    <div class="card">
        <h3>Puzzle Clusters (k=3)</h3>
        <div class="chart-container"><canvas id="chart-puzzle-cluster"></canvas></div>
        <div id="cluster-members" style="margin-top:15px;"></div>
    </div>
    <div class="card">
        <h3>Row Archetypes (k=4)</h3>
        <div class="chart-container"><canvas id="chart-row-cluster"></canvas></div>
    </div>
</div>
</div>

<!-- PREDICTIONS -->
<div class="section" id="predictions">
<h2>Difficulty Predictions</h2>
<p style="color:var(--muted);margin-bottom:15px;">
    Predicted solve rate for all {len(predictions)} puzzles based on row-level PDL regression.
    Validation: r = {pred_chart_data['validation']['r']}, MAE = {pred_chart_data['validation']['mae']}pp
</p>
<div class="card" style="margin-bottom:20px;">
    <h3>Predicted vs Actual (Dated Puzzles)</h3>
    <div class="chart-container"><canvas id="chart-pred-scatter"></canvas></div>
</div>
<div class="card">
    <h3>All Puzzles — Predicted Difficulty</h3>
    <table id="pred-table">
        <thead><tr><th>Puzzle</th><th>Date</th><th>Predicted</th><th>Actual</th><th>Delta</th>
                   <th>Manip. Complexity</th><th>Cluster</th></tr></thead>
        <tbody></tbody>
    </table>
</div>
</div>

</main>
</div>

<script>
// ── Data ──
const chartData = {to_json(chart_data)};
const heatmapManips = {to_json(all_manips_hm)};
const heatmapAbstrs = {to_json(all_abstrs_hm)};
const heatmapValues = {to_json(hm_values)};
const heatmapAnnotations = {to_json(hm_annotations)};
const scatterData = {to_json(scatter_data)};
const regressionData = {to_json(regression_data)};
const viData = {to_json(vi_chart_data)};
const transparencyData = {to_json(transparency_data)};
const decoyData = {to_json(decoy_chart)};
const confusionData = {to_json(confusion_chart)};
const relinkData = {to_json(relink_chart_data)};
const clusterData = {to_json(cluster_chart_data)};
const predData = {to_json(pred_chart_data)};
const impDomainData = {to_json(imp_domain_chart)};

// ── Colours ──
const COLORS = ['#6c5ce7','#00b894','#e17055','#0984e3','#fdcb6e','#a29bfe',
                '#55efc4','#fab1a0','#74b9ff','#ffeaa7','#dfe6e9','#636e72','#d63031'];
function hsl(h, s, l) {{ return `hsl(${{h}}, ${{s}}%, ${{l}}%)`; }}
function hsla(h, s, l, a) {{ return `hsla(${{h}}, ${{s}}%, ${{l}}%, ${{a}})`; }}

// ── Key Findings ──
(function() {{
    const grid = document.getElementById('stats-grid');
    // Find most impactful features
    const rowCoefs = regressionData.row;
    let maxCoef = '', maxVal = 0;
    for (let i = 1; i < rowCoefs.names.length; i++) {{
        if (Math.abs(rowCoefs.coefs[i]) > Math.abs(maxVal)) {{
            maxVal = rowCoefs.coefs[i];
            maxCoef = rowCoefs.names[i];
        }}
    }}

    const findings = [
        {{ value: predData.validation.r.toFixed(2), label: 'Prediction Correlation (r)' }},
        {{ value: predData.validation.mae + 'pp', label: 'Prediction MAE' }},
        {{ value: regressionData.row.r2, label: 'Row Regression R²' }},
        {{ value: maxCoef.replace('manip:','').replace('abstr:','').replace('know:',''),
           label: 'Strongest Predictor' }},
        {{ value: (maxVal > 0 ? '+' : '') + (maxVal * 100).toFixed(0) + 'pp',
           label: 'Its Effect on First-Try %' }},
        {{ value: regressionData.puzzle.loo_mae + 'pp', label: 'Puzzle LOO-CV MAE' }},
    ];
    findings.forEach(f => {{
        grid.innerHTML += `<div class="stat-card"><div class="value">${{f.value}}</div><div class="label">${{f.label}}</div></div>`;
    }});
}})();

// ── Cross-tab charts ──
function makeBarChart(canvasId, data, horizontal) {{
    const ctx = document.getElementById(canvasId).getContext('2d');
    const indexAxis = horizontal ? 'y' : 'x';
    const valAxis = horizontal ? 'xAxisID' : 'yAxisID';
    const ds1 = {{ label: 'First-try correct %', data: data.first_try.map(v => v.toFixed(1)),
                   backgroundColor: hsla(260, 70, 55, 0.7), borderColor: hsl(260, 70, 55),
                   borderWidth: 1 }};
    const ds2 = {{ label: 'Avg wrong guesses', data: data.avg_wrong.map(v => v.toFixed(2)),
                   backgroundColor: hsla(15, 70, 55, 0.7), borderColor: hsl(15, 70, 55),
                   borderWidth: 1 }};
    ds1[valAxis] = horizontal ? 'x' : 'y';
    ds2[valAxis] = horizontal ? 'x1' : 'y1';
    const scales = horizontal ? {{
        x: {{ beginAtZero: true, position: 'bottom',
              title: {{ display: true, text: 'First-try %' }} }},
        x1: {{ beginAtZero: true, position: 'top', grid: {{ drawOnChartArea: false }},
               title: {{ display: true, text: 'Avg wrong' }} }},
    }} : {{
        y: {{ beginAtZero: true, position: 'left',
              title: {{ display: true, text: 'First-try %' }} }},
        y1: {{ beginAtZero: true, position: 'right', grid: {{ drawOnChartArea: false }},
               title: {{ display: true, text: 'Avg wrong' }} }},
    }};
    new Chart(ctx, {{
        type: 'bar',
        data: {{ labels: data.labels, datasets: [ds1, ds2] }},
        options: {{
            indexAxis,
            responsive: true, maintainAspectRatio: false,
            plugins: {{
                tooltip: {{
                    callbacks: {{
                        afterBody: (items) => {{
                            const i = items[0].dataIndex;
                            return `n = ${{data.n[i]}} rows`;
                        }}
                    }}
                }}
            }},
            scales,
        }}
    }});
}}

makeBarChart('chart-manip', chartData['Manipulation'], false);
makeBarChart('chart-abstr', chartData['Abstraction'], false);
makeBarChart('chart-know', chartData['Knowledge'], false);
makeBarChart('chart-domain', chartData['Knowledge Domain'], true);

// ── Heatmap ──
(function() {{
    const container = document.getElementById('heatmap-container');
    const cols = heatmapManips.length + 1;
    let html = `<div class="heatmap-grid" style="grid-template-columns: 120px repeat(${{heatmapManips.length}}, 1fr);">`;
    html += '<div class="hm-header"></div>';
    heatmapManips.forEach(m => {{ html += `<div class="hm-header">${{m}}</div>`; }});
    heatmapAbstrs.forEach((a, ai) => {{
        html += `<div class="hm-header" style="text-align:right;padding-right:8px;">${{a}}</div>`;
        heatmapValues[ai].forEach((v, mi) => {{
            if (v === null) {{
                html += '<div class="hm-cell" style="background:#eee;color:#999;">—</div>';
            }} else {{
                const pct = v;
                const h = pct < 40 ? 0 : pct < 55 ? 30 : pct < 70 ? 120 : 150;
                const s = 65; const l = 42;
                html += `<div class="hm-cell" style="background:${{hsl(h,s,l)}};">${{heatmapAnnotations[ai][mi]}}</div>`;
            }}
        }});
    }});
    html += '</div>';
    container.innerHTML += html;
}})();

// ── Impostor Domain ──
(function() {{
    const ctx1 = document.getElementById('chart-domain-dist').getContext('2d');
    new Chart(ctx1, {{
        type: 'bar',
        data: {{
            labels: ['Same Domain', 'Different Domain'],
            datasets: [
                {{ label: 'First-try %', data: [impDomainData.same_domain.mean_first_try,
                   impDomainData.diff_domain.mean_first_try],
                   backgroundColor: [hsla(260,70,55,0.7), hsla(170,70,45,0.7)] }},
            ]
        }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            plugins: {{
                tooltip: {{
                    callbacks: {{
                        afterBody: (items) => {{
                            const d = items[0].dataIndex === 0 ? impDomainData.same_domain : impDomainData.diff_domain;
                            return `n = ${{d.n}} rows\\nAvg wrong: ${{d.mean_avg_wrong}}`;
                        }}
                    }}
                }}
            }},
            scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: 'First-try correct %' }} }} }}
        }}
    }});

    const bd = impDomainData.by_imp_domain;
    const labels = Object.keys(bd);
    const ctx2 = document.getElementById('chart-imp-domain').getContext('2d');
    new Chart(ctx2, {{
        type: 'bar',
        data: {{
            labels,
            datasets: [{{ label: 'First-try %', data: labels.map(l => bd[l].mean_first_try),
                          backgroundColor: labels.map((_, i) => COLORS[i % COLORS.length]) }}]
        }},
        options: {{
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: {{
                tooltip: {{
                    callbacks: {{
                        afterBody: (items) => {{
                            const l = items[0].label;
                            return `n = ${{bd[l].n}} rows\\nAvg wrong: ${{bd[l].mean_avg_wrong}}`;
                        }}
                    }}
                }}
            }},
            scales: {{ x: {{ beginAtZero: true, title: {{ display: true, text: 'First-try %' }} }} }}
        }}
    }});
}})();

// ── Scatter Plots ──
(function() {{
    const container = document.getElementById('scatter-container');
    const feats = Object.keys(scatterData);
    feats.forEach((feat, fi) => {{
        const d = scatterData[feat];
        const cardId = `scatter-${{fi}}`;
        container.innerHTML += `<div class="card"><h3>${{d.label}} vs Solve Rate</h3>
            <p style="color:var(--muted);font-size:12px;">Pearson r=${{d.pearson_r}} · Spearman ρ=${{d.spearman_r}}</p>
            <div class="chart-container"><canvas id="${{cardId}}"></canvas></div></div>`;
    }});

    feats.forEach((feat, fi) => {{
        const d = scatterData[feat];
        const ctx = document.getElementById(`scatter-${{fi}}`).getContext('2d');
        const pts = d.xs.map((x, i) => ({{ x, y: d.ys[i] }}));
        // Trendline
        const n = d.xs.length;
        const mx = d.xs.reduce((a,b) => a+b, 0) / n;
        const my = d.ys.reduce((a,b) => a+b, 0) / n;
        const ssxy = d.xs.reduce((s, x, i) => s + (x - mx) * (d.ys[i] - my), 0);
        const ssxx = d.xs.reduce((s, x) => s + (x - mx) ** 2, 0);
        const slope = ssxx ? ssxy / ssxx : 0;
        const intercept = my - slope * mx;
        const xMin = Math.min(...d.xs) - 0.5;
        const xMax = Math.max(...d.xs) + 0.5;

        // Detect integer-only x values and force integer ticks
        const allInt = d.xs.every(x => Number.isInteger(x));
        const xScale = allInt ? {{
            title: {{ display: true, text: d.label }},
            min: Math.min(...d.xs) - 0.3,
            max: Math.max(...d.xs) + 0.3,
            ticks: {{ stepSize: 1, callback: (v) => Number.isInteger(v) ? v : '' }}
        }} : {{
            title: {{ display: true, text: d.label }},
        }};

        new Chart(ctx, {{
            type: 'scatter',
            data: {{
                datasets: [
                    {{ label: 'Puzzles', data: pts, backgroundColor: hsla(260,70,55,0.8),
                       pointRadius: 6, pointHoverRadius: 8 }},
                    {{ label: 'Trend', data: [{{x: xMin, y: intercept + slope * xMin}},
                                               {{x: xMax, y: intercept + slope * xMax}}],
                       type: 'line', borderColor: hsla(0,70,55,0.5), borderDash: [6,3],
                       pointRadius: 0, borderWidth: 2 }},
                ]
            }},
            options: {{
                responsive: true, maintainAspectRatio: false,
                plugins: {{
                    tooltip: {{
                        callbacks: {{
                            label: (ctx) => {{
                                if (ctx.datasetIndex === 0) {{
                                    const i = ctx.dataIndex;
                                    return `${{d.labels[i]}}: ${{d.ys[i]}}% solve rate`;
                                }}
                                return '';
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: xScale,
                    y: {{ title: {{ display: true, text: 'Solve Rate %' }} }},
                }}
            }}
        }});
    }});
}})();

// ── Regression Tables ──
function makeRegTable(tableId, data) {{
    const table = document.getElementById(tableId);
    let html = '<thead><tr><th>Feature</th><th>Coefficient</th><th>Effect</th></tr></thead><tbody>';
    data.names.forEach((name, i) => {{
        const c = data.coefs[i];
        const effect = i === 0 ? 'baseline' : (c > 0 ? '+' : '') + (c * 100).toFixed(1) + 'pp';
        const cls = i === 0 ? '' : (Math.abs(c) > 0.1 ? ' style="font-weight:600;"' : '');
        html += `<tr${{cls}}><td>${{name}}</td><td>${{c.toFixed(4)}}</td><td>${{effect}}</td></tr>`;
    }});
    html += '</tbody>';
    table.innerHTML = html;
}}
makeRegTable('reg-puzzle-table', regressionData.puzzle);
makeRegTable('reg-row-table', regressionData.row);
if (regressionData.pos_controlled.coefs.length > 0) makeRegTable('reg-intrinsic-table', regressionData.pos_controlled);

// Forest plot
(function() {{
    const rd = regressionData.row;
    const labels = rd.names.slice(1);
    const coefs = rd.coefs.slice(1).map(c => c * 100);
    const ctx = document.getElementById('chart-forest').getContext('2d');
    new Chart(ctx, {{
        type: 'bar',
        data: {{
            labels,
            datasets: [{{ label: 'Effect on first-try % (pp)', data: coefs,
                          backgroundColor: coefs.map(c => c >= 0 ? hsla(150,60,45,0.7) : hsla(0,65,50,0.7)),
                          borderColor: coefs.map(c => c >= 0 ? hsl(150,60,45) : hsl(0,65,50)),
                          borderWidth: 1 }}]
        }},
        options: {{
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
                x: {{ title: {{ display: true, text: 'Effect on first-try correct % (pp)' }},
                      grid: {{ color: (ctx) => ctx.tick.value === 0 ? '#2d3436' : '#eee' }} }}
            }}
        }}
    }});
}})();

// ── Vertical Inference ──
(function() {{
    const ct = viData.crosstabs;
    const summ = viData.summary;

    // Summary
    const summDiv = document.getElementById('vi-summary');
    const meds = summ.median_intervals;
    const drop = meds[0] > 0 ? ((meds[0] - meds[2]) / meds[0] * 100).toFixed(0) : '?';
    let sh = `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:15px;">`;
    sh += `<div class="stat-card"><div class="value">${{meds[0]}}s \u2192 ${{meds[2]}}s</div><div class="label">Median interval: 1st\u21922nd \u2192 3rd\u21924th</div></div>`;
    sh += `<div class="stat-card"><div class="value">${{drop}}%</div><div class="label">Median time drop</div></div>`;
    sh += `<div class="stat-card"><div class="value">${{summ.mean_accel}}x</div><div class="label">Mean acceleration factor</div></div>`;
    sh += `<div class="stat-card"><div class="value">${{summ.n_accelerated}}/${{summ.n_total}}</div><div class="label">Puzzles that accelerated (&lt;1x)</div></div>`;
    sh += `<div class="stat-card"><div class="value">${{summ.mean_transparency}}%</div><div class="label">Mean theme transparency</div></div>`;
    sh += `</div>`;
    summDiv.innerHTML = sh;

    // Helper: create a grouped bar chart for a metric across all PDL feature axes
    function makeViCrosstabs(containerId, metric, metricLabel, refLine) {{
        const container = document.getElementById(containerId);
        const features = Object.keys(ct);
        features.forEach((feat, fi) => {{
            const axis = ct[feat];
            const cats = Object.keys(axis.categories);
            const vals = cats.map(c => axis.categories[c]['mean_' + metric]);
            const ns = cats.map(c => axis.categories[c].n);

            // Skip if all null
            if (vals.every(v => v === null)) return;

            const chartId = `vi-${{metric}}-${{fi}}`;
            container.innerHTML += `<div style="margin-bottom:20px;">
                <h4 style="color:var(--text);margin-bottom:8px;">${{axis.label}}</h4>
                <div class="chart-container" style="height:200px;"><canvas id="${{chartId}}"></canvas></div>
            </div>`;
        }});

        // Render charts after DOM update
        features.forEach((feat, fi) => {{
            const axis = ct[feat];
            const cats = Object.keys(axis.categories);
            const vals = cats.map(c => axis.categories[c]['mean_' + metric]);
            const ns = cats.map(c => axis.categories[c].n);
            if (vals.every(v => v === null)) return;

            const chartId = `vi-${{metric}}-${{fi}}`;
            const el = document.getElementById(chartId);
            if (!el) return;
            const ctx = el.getContext('2d');

            const barColors = vals.map(v => {{
                if (v === null) return '#dfe6e9';
                if (metric === 'accel') return v < 1 ? hsla(150,60,45,0.7) : hsla(0,65,50,0.7);
                return hsla(260,70,55,0.7);
            }});

            const annotation = refLine !== null ? {{
                annotations: {{
                    refLine: {{ type: 'line', yMin: refLine, yMax: refLine,
                               borderColor: '#636e72', borderDash: [4,4], borderWidth: 1 }}
                }}
            }} : {{}};

            new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: cats.map((c, i) => `${{c}} (n=${{ns[i]}})`),
                    datasets: [{{ label: metricLabel, data: vals.map(v => v !== null ? v : 0),
                                  backgroundColor: barColors, borderWidth: 0 }}]
                }},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }},
                        annotation,
                        tooltip: {{
                            callbacks: {{
                                afterBody: (items) => {{
                                    const i = items[0].dataIndex;
                                    const cat = cats[i];
                                    const info = axis.categories[cat];
                                    return `Puzzles: ${{info.puzzles.join(', ')}}\\nSolve rate: ${{info.mean_solve_rate}}%`;
                                }}
                            }}
                        }}
                    }},
                    scales: {{ y: {{ title: {{ display: true, text: metricLabel }} }} }}
                }}
            }});
        }});
    }}

    makeViCrosstabs('vi-accel-charts', 'accel', 'Acceleration factor (< 1 = sped up)', 1.0);
    makeViCrosstabs('vi-transp-charts', 'transparency', 'Theme transparency %', null);

    // Per-puzzle detail table
    const tbody = document.querySelector('#vi-puzzle-table tbody');
    const sorted = [...viData.puzzles].sort((a, b) => (a.accel_factor || 99) - (b.accel_factor || 99));
    sorted.forEach(p => {{
        const accelStr = p.accel_factor !== null ? p.accel_factor.toFixed(3) + 'x' : '\u2014';
        const accelColor = p.accel_factor !== null ? (p.accel_factor < 1 ? 'color:#00b894' : 'color:#d63031') : '';
        tbody.innerHTML += `<tr>
            <td>${{p.name}}</td><td>${{p.label}}</td>
            <td style="${{accelColor}};font-weight:600;">${{accelStr}}</td>
            <td>${{p.transparency}}%</td>
            <td>${{p.solve_rate}}%</td></tr>`;
    }});
}})();

// ── Decoy Analysis ──
(function() {{
    const ctx = document.getElementById('chart-decoy-compare').getContext('2d');
    new Chart(ctx, {{
        type: 'bar',
        data: {{
            labels: ['No Decoys', 'Has Decoys'],
            datasets: [
                {{ label: 'Mean Solve Rate %', data: [
                    (decoyData.no_decoys.mean_solve_rate * 100).toFixed(1),
                    (decoyData.has_decoys.mean_solve_rate * 100).toFixed(1)],
                   backgroundColor: [hsla(260,70,55,0.7), hsla(170,70,45,0.7)] }},
            ]
        }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            plugins: {{
                tooltip: {{
                    callbacks: {{
                        afterBody: (items) => {{
                            const i = items[0].dataIndex;
                            const d = i === 0 ? decoyData.no_decoys : decoyData.has_decoys;
                            return `n = ${{d.n}} puzzles\\nAvg wrong/row: ${{d.mean_avg_wrong.toFixed(2)}}`;
                        }}
                    }}
                }}
            }},
            scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: 'Solve Rate %' }} }} }}
        }}
    }});

    const hits = decoyData.hit_analysis;
    if (hits.length > 0) {{
        const ctx2 = document.getElementById('chart-decoy-hits').getContext('2d');
        new Chart(ctx2, {{
            type: 'bar',
            data: {{
                labels: hits.map(h => h.label + ' ' + h.name.substring(0, 15)),
                datasets: [
                    {{ label: 'Decoy-matching wrong guesses', data: hits.map(h => h.decoy_wrong),
                       backgroundColor: hsla(0,65,50,0.7) }},
                    {{ label: 'Other wrong guesses', data: hits.map(h => h.total_wrong - h.decoy_wrong),
                       backgroundColor: hsla(220,30,70,0.5) }},
                ]
            }},
            options: {{
                responsive: true, maintainAspectRatio: false,
                scales: {{ x: {{ stacked: true }}, y: {{ stacked: true,
                    title: {{ display: true, text: 'Wrong guesses' }} }} }},
                plugins: {{
                    tooltip: {{
                        callbacks: {{
                            afterBody: (items) => {{
                                const i = items[0].dataIndex;
                                return `Hit rate: ${{(hits[i].hit_rate * 100).toFixed(0)}}%\\nDecoys: ${{hits[i].descriptions.join('; ')}}`;
                            }}
                        }}
                    }}
                }}
            }}
        }});
    }}
}})();

// ── Confusion Maps ──
(function() {{
    const container = document.getElementById('confusion-container');
    for (const [label, cd] of Object.entries(confusionData)) {{
        let html = `<div class="card"><h3>${{label}} — ${{cd.name}}</h3>`;
        html += `<div class="confusion-grid" style="grid-template-columns: 80px repeat(4, 60px);">`;
        html += '<div class="confusion-cell confusion-header"></div>';
        for (let c = 0; c < 4; c++) html += `<div class="confusion-cell confusion-header">From R${{c}}</div>`;
        for (let r = 0; r < 4; r++) {{
            html += `<div class="confusion-cell confusion-header">Guessed R${{r}}</div>`;
            const rowTotal = cd.matrix[r].reduce((a,b) => a+b, 0);
            for (let c = 0; c < 4; c++) {{
                const v = cd.matrix[r][c];
                const intensity = rowTotal > 0 ? Math.min(v / Math.max(rowTotal, 1), 1) : 0;
                const bg = r === c ? `hsla(260, 70%, 55%, ${{0.1 + intensity * 0.6}})` :
                                     `hsla(0, 65%, 50%, ${{intensity * 0.8}})`;
                html += `<div class="confusion-cell" style="background:${{bg}};${{intensity > 0.4 ? 'color:#fff;' : ''}}">${{v || ''}}</div>`;
            }}
        }}
        html += '</div></div>';
        container.innerHTML += html;
    }}
}})();

// ── Relink Phase ──
(function() {{
    const byM = relinkData.by_manip;
    const mLabels = Object.keys(byM);
    const ctx1 = document.getElementById('chart-relink-manip').getContext('2d');
    new Chart(ctx1, {{
        type: 'bar',
        data: {{
            labels: mLabels,
            datasets: [
                {{ label: 'First-try %', data: mLabels.map(l => (byM[l].mean_first_try * 100).toFixed(1)),
                   backgroundColor: hsla(260,70,55,0.7) }},
            ]
        }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            plugins: {{
                tooltip: {{
                    callbacks: {{
                        afterBody: (items) => {{
                            const l = items[0].label;
                            return `n = ${{byM[l].n}} puzzles\\nAvg attempts: ${{byM[l].mean_attempts.toFixed(1)}}`;
                        }}
                    }}
                }}
            }},
            scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: 'Relink first-try %' }} }} }}
        }}
    }});

    const byT = relinkData.by_tiles;
    const tLabels = Object.keys(byT).sort();
    const ctx2 = document.getElementById('chart-relink-tiles').getContext('2d');
    new Chart(ctx2, {{
        type: 'bar',
        data: {{
            labels: tLabels.map(t => t + ' tile' + (t === '1' ? '' : 's')),
            datasets: [
                {{ label: 'Relink first-try %', data: tLabels.map(t => (byT[t].mean_first_try * 100).toFixed(1)),
                   backgroundColor: hsla(260, 70, 55, 0.7), yAxisID: 'y' }},
                {{ label: 'Puzzle solve rate %', data: tLabels.map(t => (byT[t].mean_solve_rate * 100).toFixed(1)),
                   backgroundColor: hsla(170, 70, 45, 0.7), yAxisID: 'y' }},
            ]
        }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: '%' }} }} }},
            plugins: {{
                tooltip: {{
                    callbacks: {{
                        afterBody: (items) => {{
                            const t = tLabels[items[0].dataIndex];
                            return `n = ${{byT[t].n}} puzzles\\nAvg attempts: ${{byT[t].mean_attempts.toFixed(1)}}`;
                        }}
                    }}
                }}
            }}
        }}
    }});
}})();

// ── Clustering ──
(function() {{
    const pc = clusterData.puzzles;
    const cNames = Object.keys(pc);
    const ctx1 = document.getElementById('chart-puzzle-cluster').getContext('2d');
    new Chart(ctx1, {{
        type: 'bar',
        data: {{
            labels: cNames,
            datasets: [
                {{ label: 'Puzzles', data: cNames.map(c => pc[c].n_total),
                   backgroundColor: cNames.map((_, i) => COLORS[i]) }},
                {{ label: 'Mean Solve Rate %', data: cNames.map(c => pc[c].mean_solve_rate),
                   type: 'line', borderColor: '#d63031', backgroundColor: 'transparent',
                   yAxisID: 'y1', pointRadius: 6, borderWidth: 2 }},
            ]
        }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            scales: {{
                y: {{ beginAtZero: true, title: {{ display: true, text: 'Count' }} }},
                y1: {{ beginAtZero: true, position: 'right', grid: {{ drawOnChartArea: false }},
                       title: {{ display: true, text: 'Solve Rate %' }} }},
            }}
        }}
    }});

    // Cluster members list
    const membersDiv = document.getElementById('cluster-members');
    cNames.forEach((c, i) => {{
        membersDiv.innerHTML += `<p style="margin:5px 0;"><span style="display:inline-block;width:12px;height:12px;
            background:${{COLORS[i]}};border-radius:3px;margin-right:6px;vertical-align:middle;"></span>
            <strong>${{c}}</strong> (${{pc[c].n_total}} puzzles, ${{pc[c].n_dated}} dated):
            ${{pc[c].members.slice(0, 8).join(', ')}}${{pc[c].members.length > 8 ? '...' : ''}}</p>`;
    }});

    const rc = clusterData.rows;
    const rNames = Object.keys(rc);
    const ctx2 = document.getElementById('chart-row-cluster').getContext('2d');
    new Chart(ctx2, {{
        type: 'bar',
        data: {{
            labels: rNames,
            datasets: [
                {{ label: 'First-try %', data: rNames.map(r => rc[r].mean_first_try),
                   backgroundColor: rNames.map((_, i) => COLORS[i + 3]) }},
            ]
        }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            plugins: {{
                tooltip: {{
                    callbacks: {{
                        afterBody: (items) => {{
                            const r = rNames[items[0].dataIndex];
                            return `n = ${{rc[r].n}} rows\\nAvg wrong: ${{rc[r].mean_avg_wrong}}`;
                        }}
                    }}
                }}
            }},
            scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: 'First-try correct %' }} }} }}
        }}
    }});
}})();

// ── Predictions ──
(function() {{
    // Scatter: predicted vs actual
    const dated = predData.all.filter(p => p.actual !== null);
    const ctx = document.getElementById('chart-pred-scatter').getContext('2d');
    new Chart(ctx, {{
        type: 'scatter',
        data: {{
            datasets: [
                {{ label: 'Puzzles', data: dated.map(p => ({{ x: p.predicted, y: p.actual }})),
                   backgroundColor: hsla(260, 70, 55, 0.8), pointRadius: 7, pointHoverRadius: 9 }},
                {{ label: 'Perfect prediction', data: [{{x: 0, y: 0}}, {{x: 100, y: 100}}],
                   type: 'line', borderColor: '#b2bec3', borderDash: [6, 3],
                   pointRadius: 0, borderWidth: 1 }},
            ]
        }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            plugins: {{
                tooltip: {{
                    callbacks: {{
                        label: (ctx) => {{
                            if (ctx.datasetIndex === 0) {{
                                const p = dated[ctx.dataIndex];
                                return `${{p.name}}: predicted ${{p.predicted}}%, actual ${{p.actual}}%`;
                            }}
                            return '';
                        }}
                    }}
                }}
            }},
            scales: {{
                x: {{ title: {{ display: true, text: 'Predicted solve rate %' }}, min: 0, max: 100 }},
                y: {{ title: {{ display: true, text: 'Actual solve rate %' }}, min: 0, max: 100 }},
            }}
        }}
    }});

    // Prediction table
    const tbody = document.querySelector('#pred-table tbody');
    const clusterNames = Object.keys(clusterData.puzzles);
    predData.all.sort((a, b) => a.predicted - b.predicted).forEach(p => {{
        const badge = p.predicted < 30 ? 'badge-red' : p.predicted > 70 ? 'badge-green' : 'badge-amber';
        const delta = p.actual !== null ? (p.actual - p.predicted).toFixed(1) + 'pp' : '—';
        const cName = clusterNames[p.cluster] || '?';
        tbody.innerHTML += `<tr>
            <td>${{p.name}}</td>
            <td>${{p.date || '<em>undated</em>'}}</td>
            <td><span class="badge ${{badge}}">${{p.predicted.toFixed(1)}}%</span></td>
            <td>${{p.actual !== null ? p.actual.toFixed(1) + '%' : '—'}}</td>
            <td>${{delta}}</td>
            <td>${{p.manipComplexity}} manip / ${{p.abstrComplexity}} abstr</td>
            <td>${{cName}}</td>
        </tr>`;
    }});
}})();

// ── Nav highlighting ──
document.querySelectorAll('nav a').forEach(link => {{
    link.addEventListener('click', () => {{
        document.querySelectorAll('nav a').forEach(l => l.classList.remove('active'));
        link.classList.add('active');
    }});
}});
</script>
</body>
</html>"""

with open(OUTPUT_FILE, 'w') as f:
    f.write(html)

print(f"\nDone! Report written to {OUTPUT_FILE}")
print(f"Open in a browser to view interactive charts.")
