"""Data loading, parsing, filtering, joining. No analysis, no HTML."""

import csv
import ast
import os
import json
import glob
from datetime import datetime
from collections import defaultdict, Counter

from .stats import safe_mean, safe_median


# ── Constants ──

MONTH_NAMES = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
               7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}

_ORDINAL_LABELS = {1: '1st', 2: '2nd', 3: '3rd', 4: '4th'}
# '5th' covers the Relink phase (post-imposters); always 0 on imposters rows.
SOLVE_ORDER_BUCKETS = ('1st', '2nd', '3rd', '4th', '5th', 'never')


# ── Internal helpers ──

def _parse_ts(s):
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S.%f'):
        try:
            return datetime.strptime(s.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def _parse_props(s):
    try:
        return ast.literal_eval(s)
    except Exception:
        return {}


def _strip_nuls(f):
    for line in f:
        if '\x00' in line:
            line = line.replace('\x00', '')
        yield line


def date_label(d):
    parts = d.split('-')
    return f"{MONTH_NAMES[int(parts[1])]} {int(parts[2])}"


# ── PDL loading ──

def load_pdl(save_dir):
    """Load puzzle PDL data from save-data/.
    Returns (pdl_puzzles, pdl_rows, pdl_puzzle_features, level_to_date, date_to_level, canonical_ids).
    """
    with open(os.path.join(save_dir, 'puzzles-index.json')) as f:
        puzzles_index = json.load(f)

    pdl_puzzles = {}
    level_to_date = {}
    date_to_level = {}
    canonical_ids = {}  # date -> canonicalId (for puzzles that have one)

    for entry in puzzles_index['puzzles']:
        lid = entry['id']
        date = entry.get('date', '')
        level_file = os.path.join(save_dir, f'{lid}.json')
        if not os.path.exists(level_file):
            continue
        with open(level_file) as f:
            pdata = json.load(f)
        if pdata.get('schemaVersion') != 2:
            print(f"  WARN: {lid} has schemaVersion={pdata.get('schemaVersion')!r}, expected 2")
        pdl_puzzles[lid] = pdata
        pdl_puzzles[lid]['_index'] = entry
        if date:
            level_to_date[lid] = date
            date_to_level[date] = lid
        canon = pdata.get('canonicalId', '')
        if canon and date:
            canonical_ids[date] = canon

    pdl_rows = []
    pdl_puzzle_features = {}

    for lid, pdata in pdl_puzzles.items():
        rows = pdata.get('rows', [])
        relink = pdata.get('relink', {})
        decoys = pdata.get('decoys', [])
        board = pdata.get('board', {})
        date = level_to_date.get(lid, '')

        manip_count = 0
        abstr_count = 0
        domains = set()
        knowledge_types = set()
        for row in rows:
            rpdl = row.get('pdl', {}).get('group', {})
            manip = rpdl.get('manipulation', ['None'])[0] if rpdl.get('manipulation') else 'None'
            abstr = rpdl.get('abstraction', ['Direct membership'])[0] if rpdl.get('abstraction') else 'Direct membership'
            know = rpdl.get('knowledge', ['General vocabulary'])[0] if rpdl.get('knowledge') else 'General vocabulary'
            kdoms = rpdl.get('knowledgeDomain', ['General']) or ['General']
            if manip != 'None':
                manip_count += 1
            if abstr != 'Direct membership':
                abstr_count += 1
            for kd in kdoms:
                domains.add(kd)
            knowledge_types.add(know)

        rpdl = relink.get('pdl', {})
        conn_id = rpdl.get('connectionIdentification', {})
        ans_con = rpdl.get('answerConstruction', {})

        relink_id_manipulation = conn_id.get('manipulation', ['None'])[0] if conn_id.get('manipulation') else 'None'
        relink_id_knowledge = conn_id.get('knowledge', ['General vocabulary'])[0] if conn_id.get('knowledge') else 'General vocabulary'
        relink_id_abstraction = conn_id.get('abstraction', ['Direct membership'])[0] if conn_id.get('abstraction') else 'Direct membership'
        relink_id_domain = conn_id.get('knowledgeDomain', ['General'])[0] if conn_id.get('knowledgeDomain') else 'General'
        relink_con_manipulation = ans_con.get('manipulation', ['None'])[0] if ans_con.get('manipulation') else 'None'
        relink_con_knowledge = ans_con.get('knowledge', ['None'])[0] if ans_con.get('knowledge') else 'None'

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
            'relink_id_manipulation': relink_id_manipulation,
            'relink_id_knowledge': relink_id_knowledge,
            'relink_id_abstraction': relink_id_abstraction,
            'relink_id_domain': relink_id_domain,
            'relink_con_manipulation': relink_con_manipulation,
            'relink_con_knowledge': relink_con_knowledge,
            'relink_answer': relink.get('answer', ''),
            'decoys': decoys,
        }
        pdl_puzzle_features[lid] = pf

        for row in rows:
            rpdl = row.get('pdl', {})
            group = rpdl.get('group', {})
            impostor_pdl = rpdl.get('impostor', {})

            manips = list(group.get('manipulation') or ['None'])
            abstrs = list(group.get('abstraction') or ['Direct membership'])
            knows = list(group.get('knowledge') or ['General vocabulary'])
            kdoms = list(group.get('knowledgeDomain') or ['General'])
            imp_doms = list(impostor_pdl.get('realIdentityDomain') or ['General'])

            manip = manips[0]
            abstr = abstrs[0]
            know = knows[0]
            kdom = kdoms[0]
            imp_dom = imp_doms[0]

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

            same_domain = bool(set(kdoms) & set(imp_doms))
            cross_domain_impostor = not same_domain

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
                'knowledgeDomains': kdoms,
                'manipulations': manips,
                'abstractions': abstrs,
                'knowledges': knows,
                'realIdentityDomains': imp_doms,
                'row_domain_breadth': len(set(kdoms)),
                'impostor_domain': imp_dom,
                'same_domain': same_domain,
                'cross_domain_impostor': cross_domain_impostor,
                'impostor_word': impostor_word,
                'non_impostor_words': non_impostor_words,
                'relink_words': relink_words,
                'tile_ids': [t['id'] for t in row.get('tiles', [])],
            })

    return pdl_puzzles, pdl_rows, pdl_puzzle_features, level_to_date, date_to_level, canonical_ids


# ── Behaviour loading ──

def _extract_level_id(raw_props):
    """Extract level_id from raw properties string without full parsing."""
    for marker in ("'level_id':'", "'level_id': '"):
        idx = raw_props.find(marker)
        if idx != -1:
            start = idx + len(marker)
            end = raw_props.find("'", start)
            return raw_props[start:end] if end != -1 else ''
    return ''


def load_behaviour(raw_dir, target_dates=None):
    """Load events from CSVs, grouped by (device_id, date).
    Trajectory events require non-empty device_id and client_id:'dailymail'.
    Also collects broad completion stats from ALL level_completed events (no device_id needed).
    target_dates: optional set of date strings to restrict loading to.
    Returns (events_by_device_date, ALL_DATES, completions_all).
      events_by_device_date: {date: {device_id: [events]}}
      completions_all: {date: {level_id: {'wins': int, 'losses': int}}}
    """
    event_files = sorted(glob.glob(os.path.join(raw_dir, 'daily-mail-events*.csv')))

    events_by_device_date = defaultdict(lambda: defaultdict(list))
    completions_all = defaultdict(lambda: defaultdict(lambda: {'wins': 0, 'losses': 0}))
    seen_event_ids = set()
    _ev_total = 0
    _ev_skipped_date = 0
    _ev_no_device = 0
    for ef in event_files:
        with open(ef) as f:
            for row in csv.DictReader(_strip_nuls(f)):
                _ev_total += 1
                # Gate 1: date filter (cheapest — string slice + set lookup)
                d = row['created_at'][:10]
                if target_dates and d not in target_dates:
                    _ev_skipped_date += 1
                    continue
                # Gate 2: relink substring check
                raw_props = row.get('properties', '')
                if 'relink' not in raw_props:
                    continue
                # Gate 3: game_id string check (avoids ast.literal_eval)
                if "'game_id':'relink'" not in raw_props and "'game_id': 'relink'" not in raw_props:
                    continue
                eid = row['id']
                if eid in seen_event_ids:
                    continue
                seen_event_ids.add(eid)

                # Broad completion stats — ALL level_completed events (no device_id needed)
                if row['name'] == 'level_completed':
                    lid = _extract_level_id(raw_props)
                    if "'is_won':'true'" in raw_props or "'is_won': 'true'" in raw_props:
                        completions_all[d][lid]['wins'] += 1
                    elif "'is_won':'false'" in raw_props or "'is_won': 'false'" in raw_props:
                        completions_all[d][lid]['losses'] += 1

                # Gate 4: device_id must be non-empty (for trajectory grouping)
                device_id = row.get('device_id', '').strip()
                if not device_id:
                    _ev_no_device += 1
                    continue
                # Gate 5: client_id:'dailymail' verification
                if "'client_id':'dailymail'" not in raw_props and "'client_id': 'dailymail'" not in raw_props:
                    continue
                # Deferred parsing — only store raw props + extracted fields
                row['_ts'] = _parse_ts(row['created_at'])
                row['_raw_props'] = raw_props
                row['_level_id'] = _extract_level_id(raw_props)
                row['_device_id'] = device_id
                events_by_device_date[d][device_id].append(row)

    ev_kept = sum(len(evs) for devs in events_by_device_date.values() for evs in devs.values())
    n_devices = sum(len(devs) for devs in events_by_device_date.values())
    n_completions = sum(v['wins'] + v['losses'] for dd in completions_all.values() for v in dd.values())
    print(f"  Events: {ev_kept:,} relink events across {len(events_by_device_date)} dates, "
          f"{n_devices:,} unique device+date pairs "
          f"(scanned {_ev_total:,} rows, {_ev_skipped_date:,} skipped by date, "
          f"{_ev_no_device:,} skipped no device_id)")
    print(f"  Broad completions (all users): {n_completions:,} across {len(completions_all)} dates")

    ALL_DATES = sorted(events_by_device_date.keys() | completions_all.keys())
    # Sort events within each device group by timestamp
    for d in events_by_device_date:
        for dev_events in events_by_device_date[d].values():
            dev_events.sort(key=lambda e: e['created_at'])

    return dict(events_by_device_date), ALL_DATES, dict(completions_all)


# ── Build player dicts ──

def build_players(device_events):
    """Build one dict per player from device-grouped events.
    device_events: {device_id: [events]}
    """
    players = []
    for device_id, events in device_events.items():
        real_guesses = []
        relink_guesses = []

        sorted_events = sorted(events, key=lambda e: e['created_at'])
        # Lazy-parse properties (deferred from loading for performance)
        for ev in sorted_events:
            if '_props' not in ev:
                ev['_props'] = _parse_props(ev.get('_raw_props', ev.get('properties', '{}')))
        for ev in sorted_events:
            ep = ev['_props']
            if ev['name'] == 'relink_guess_submitted':
                att = ep.get('attempts_remaining', '')
                try:
                    if int(att) > 4:
                        continue  # tutorial
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
        level_started_ts = None
        for ev in sorted_events:
            if ev['name'] == 'level_started' and level_started_ts is None:
                level_started_ts = ev['_ts']
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

        if outcome not in ('WON', 'LOST') and len(wrong_imposters) == 0:
            continue

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

        # ── Build state trajectory ──
        # Track position (which solve this is: 0th, 1st, 2nd, 3rd row solved),
        # lives before each row attempt, wrong guesses per row, survival.
        # wrongs_by_row persists across row switches so that if a player
        # fails row 0, tries row 1, then comes back to row 0, the earlier
        # miss is still counted.
        trajectory = []
        sorted_rg = sorted(real_guesses, key=lambda g: g['ts'])
        lives = 4
        solved_so_far = set()
        wrongs_by_row = {}          # row_index -> total wrong guesses
        lives_at_row_start = {}     # row_index -> lives when first attempted

        for g in sorted_rg:
            if len(solved_so_far) >= 4:
                break  # All 4 rows solved — rest is relink phase
            row = g['row']
            if row not in wrongs_by_row:
                wrongs_by_row[row] = 0
            if row not in lives_at_row_start:
                lives_at_row_start[row] = lives

            if g['is_correct']:
                pos = len(solved_so_far)
                trajectory.append({
                    'position': pos,
                    'lives_before': lives_at_row_start[row],
                    'row': row,
                    'wrong_count': wrongs_by_row[row],
                    'survived': True,
                })
                solved_so_far.add(row)
            else:
                wrongs_by_row[row] += 1
                lives -= 1
                if lives <= 0:
                    pos = len(solved_so_far)
                    trajectory.append({
                        'position': pos,
                        'lives_before': lives_at_row_start[row],
                        'row': row,
                        'wrong_count': wrongs_by_row[row],
                        'survived': False,
                    })
                    break

        # Relink trajectory (for players who reached phase 2)
        # Process guesses sequentially — each wrong guess costs a life,
        # stop when correct or lives run out.
        relink_trajectory = None
        if relink_guesses and lives > 0:
            sorted_rl = sorted(relink_guesses, key=lambda g: g['ts'])
            # Deduplicate events with same tiles and timestamp within 5s
            deduped = []
            for g in sorted_rl:
                if deduped and g['tiles'] == deduped[-1]['tiles'] and g['is_correct'] == deduped[-1]['is_correct']:
                    continue
                deduped.append(g)
            rl_lives = lives
            rl_wrong = 0
            rl_survived = False
            tile_count = len(deduped[0]['tiles'].split(',')) if deduped[0]['tiles'] else 1
            for g in deduped:
                if g['is_correct']:
                    rl_survived = True
                    break
                rl_wrong += 1
                rl_lives -= 1
                if rl_lives <= 0:
                    break
            relink_trajectory = {
                'lives_before': lives,
                'wrong_count': rl_wrong,
                'survived': rl_survived,
                'tile_count': tile_count,
            }

        # Extract level_id from events (first non-empty)
        level_id = ''
        for ev in sorted_events:
            lid_val = ev.get('_level_id', '')
            if lid_val:
                level_id = lid_val
                break

        players.append({
            'sid': device_id,
            'outcome': outcome,
            'level_id': level_id,
            'puzzle_date': puzzle_date or '',
            'real_guesses': real_guesses,
            'relink_guesses': relink_guesses,
            'wrong_imposters': wrong_imposters,
            'row_order': row_order,
            'solve_time': solve_time,
            'num_wrong': len(wrong_imposters),
            'rows_completed': rows_completed,
            'level_started_ts': level_started_ts,
            'trajectory': trajectory,
            'relink_trajectory': relink_trajectory,
        })
    return players


# ── Build per-date summaries ──

def build_date_summaries(overlap_dates, players_by_date, date_to_level, pdl_puzzle_features):
    """Compute per-date aggregates: row metrics, relink stats, timing curves."""
    from .stats import percentile as _percentile

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

        engaged_players = [p for p in pp if p['real_guesses']]

        row_metrics = {}
        for row_pos in range(4):
            rp = str(row_pos)
            attempts = 0
            first_try = 0
            never_correct = 0
            wrong_count = 0
            wrong_words = Counter()
            attempt_positions = []
            first_try_by_position = defaultdict(lambda: [0, 0])

            for p in pp:
                row_guesses = [g for g in p['real_guesses'] if g['row'] == rp]
                if not row_guesses:
                    continue
                attempts += 1
                if rp in p['row_order']:
                    pos = p['row_order'].index(rp)
                    attempt_positions.append(pos)
                else:
                    pos = -1

                first_guess_correct = row_guesses[0]['is_correct']
                if first_guess_correct:
                    first_try += 1
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

            # Solve-order distribution: across all engaged players (made any
            # guess), which solve position (1st/2nd/3rd/4th) did this row land
            # in for the puzzle, or was it never resolved? Players who never
            # reached this row contribute to 'never'.
            solve_order_counts = Counter()
            solve_order_counts_completed = Counter()
            for p in engaged_players:
                solve_pos = None
                for t in p['trajectory']:
                    if t['row'] == rp and t['survived']:
                        solve_pos = t['position'] + 1
                        break
                if solve_pos is None:
                    solve_order_counts['never'] += 1
                    if p['outcome'] in ('WON', 'LOST'):
                        solve_order_counts_completed['never'] += 1
                else:
                    solve_order_counts[_ORDINAL_LABELS[solve_pos]] += 1
                    if p['outcome'] in ('WON', 'LOST'):
                        solve_order_counts_completed[_ORDINAL_LABELS[solve_pos]] += 1

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
                'solve_order_counts': dict(solve_order_counts),
                'solve_order_counts_completed': dict(solve_order_counts_completed),
            }

        relink_attempts_list = []
        relink_first_try = 0
        relink_total = 0
        for p in pp:
            if p['relink_guesses']:
                relink_total += 1
                relink_attempts_list.append(len(p['relink_guesses']))
                if p['relink_guesses'][0]['is_correct']:
                    relink_first_try += 1

        inter_correct_intervals = []
        speed_up_ratios = []

        for p in pp:
            if p['outcome'] not in ('WON', 'LOST'):
                continue
            correct_guesses = []
            seen_rows = set()
            all_sorted = sorted(p['real_guesses'], key=lambda g: g['ts'])
            for g in all_sorted:
                if g['is_correct'] and g['row'] not in seen_rows:
                    correct_guesses.append(g)
                    seen_rows.add(g['row'])

            if len(correct_guesses) < 1:
                continue

            start_ts = p.get('level_started_ts') or (all_sorted[0]['ts'] if all_sorted else None)
            if start_ts:
                dt0 = (correct_guesses[0]['ts'] - start_ts).total_seconds()
                if dt0 >= 0:
                    inter_correct_intervals.append((0, dt0))

            if len(correct_guesses) < 2:
                continue

            intervals = []
            for i in range(1, len(correct_guesses)):
                dt = (correct_guesses[i]['ts'] - correct_guesses[i - 1]['ts']).total_seconds()
                intervals.append(dt)
                inter_correct_intervals.append((i, dt))

            if not intervals:
                continue

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

    return date_summaries


def build_aggregate_timing(date_summaries):
    """Aggregate inter-correct timing across all dates."""
    from .stats import percentile as _percentile

    all_intervals_by_pos = defaultdict(list)
    for d in date_summaries:
        for pos, iv in date_summaries[d]['inter_correct_intervals']:
            if pos <= 3:
                all_intervals_by_pos[pos].append(iv)

    aggregate_timing = {}
    for pos in sorted(all_intervals_by_pos):
        vals = all_intervals_by_pos[pos]
        aggregate_timing[pos] = {
            'p10': round(_percentile(vals, 10), 2),
            'p25': round(_percentile(vals, 25), 2),
            'median': round(_percentile(vals, 50), 2),
            'p75': round(_percentile(vals, 75), 2),
            'p90': round(_percentile(vals, 90), 2),
            'mean': round(safe_mean(vals), 2),
            'n': len(vals),
        }
    return aggregate_timing


# ── Top-level loader ──

def load_all(save_dir, raw_dir):
    """Load and join all data. Returns a dict with all computed data structures."""
    print("Loading PDL data from save-data/...")
    pdl_puzzles, pdl_rows, pdl_puzzle_features, level_to_date, date_to_level, canonical_ids = load_pdl(save_dir)
    print(f"  Loaded {len(pdl_puzzles)} puzzle PDL files")
    print(f"  Dated puzzles: {len(level_to_date)}")
    if canonical_ids:
        print(f"  Canonical IDs: {len(canonical_ids)} puzzles")

    print("Loading behaviour data from CSVs...")
    events_by_device_date, ALL_DATES, completions_all = load_behaviour(raw_dir, set(date_to_level.keys()))

    players_by_date = {}
    event_dates = sorted(d for d in ALL_DATES if events_by_device_date.get(d))
    for d in event_dates:
        players_by_date[d] = build_players(events_by_device_date[d])
    print(f"  Loaded behaviour data ({len(event_dates)} dates with events)")

    # Filter players by canonical ID where available
    for d, canon in canonical_ids.items():
        if d in players_by_date:
            before = len(players_by_date[d])
            players_by_date[d] = [p for p in players_by_date[d] if p['level_id'] == canon]
            after = len(players_by_date[d])
            if before != after:
                print(f"  Canonical filter {d}: {before} -> {after} players ({before - after} removed)")

    overlap_dates = sorted(set(date_to_level.keys()) & set(d for d in ALL_DATES if players_by_date.get(d)))
    print(f"  Overlapping dates (PDL + behaviour): {len(overlap_dates)}")

    date_summaries = build_date_summaries(overlap_dates, players_by_date, date_to_level, pdl_puzzle_features)
    print(f"  Built summaries for {len(date_summaries)} puzzle dates")

    aggregate_timing = build_aggregate_timing(date_summaries)

    return {
        'pdl_puzzles': pdl_puzzles,
        'pdl_rows': pdl_rows,
        'pdl_puzzle_features': pdl_puzzle_features,
        'level_to_date': level_to_date,
        'date_to_level': date_to_level,
        'players_by_date': players_by_date,
        'overlap_dates': overlap_dates,
        'date_summaries': date_summaries,
        'aggregate_timing': aggregate_timing,
        'completions_all': completions_all,
        'canonical_ids': canonical_ids,
    }
