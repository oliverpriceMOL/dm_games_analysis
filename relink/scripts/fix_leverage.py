"""Per-row fix-leverage punch list for Relink.

Reads existing pipeline outputs (overview.json, puzzle-explorer.json, simulator.json)
and emits a ranked punch-list of which row to target in each below-threshold puzzle:
- Dated puzzles use empirical deaths-at-row from real player events (upper-bound projected SR).
- Undated puzzles use simulator-predicted mean wrongs per row (bottleneck identification only).

Usage: python3 relink/scripts/fix_leverage.py [--threshold 60] [--data-dir <path>]
Outputs: relink/outputs/fix-leverage.txt + relink/outputs/data/fix-leverage.json
"""
import argparse
import json
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RELINK_DIR = os.path.dirname(SCRIPT_DIR)
DEFAULT_DATA_DIR = os.path.join(RELINK_DIR, 'outputs', 'data')
TXT_OUT = os.path.join(RELINK_DIR, 'outputs', 'fix-leverage.txt')
JSON_OUT_NAME = 'fix-leverage.json'

MONTH_NAMES = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
               7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}


def date_label(d):
    parts = d.split('-')
    return f"{MONTH_NAMES[int(parts[1])]} {int(parts[2])}"


def deaths_at_row(wrong_dist):
    return sum(v for k, v in wrong_dist.items()
               if k.endswith('_lost') and not k.startswith('no_attempt'))


def mean_wrongs(dist):
    return sum(int(k) * v for k, v in dist.items())


def analyse_dated(overview, explorer, threshold_pct):
    out = []
    for d in overview['dates']:
        if d['solve_rate'] >= threshold_pct:
            continue
        ex = explorer['puzzles'][d['date']]
        rows = ex['rows']
        deaths = {pos: deaths_at_row(rows[pos]['wrong_dist']) for pos in rows}
        ranked = sorted(deaths.keys(), key=lambda p: -deaths[p])

        def row_payload(pos):
            r = rows[pos]
            return {
                'row_position': int(pos),
                'row_label': r['category'],
                'deaths_at_row': deaths[pos],
                'first_try_pct': round(r['first_try_pct'] * 100, 1),
                'avg_wrong': round(r['avg_wrong'], 2),
                'impostor_word': r['impostor_word'],
                'top_wrong_picks': r.get('top_wrong', []),
                'row_pdl': {
                    'manipulation': r['manipulation'],
                    'abstraction': r['abstraction'],
                    'knowledge': r['knowledge'],
                    'knowledgeDomain': r['knowledgeDomain'],
                    'same_domain': r.get('same_domain'),
                },
            }

        single_pos = ranked[0]
        single_proj = round(100 * (d['wins'] + deaths[single_pos]) / d['completions'], 1)
        single = row_payload(single_pos)
        single['projected_sr_upper_bound'] = single_proj

        two_row = None
        if single_proj < threshold_pct:
            pos2 = ranked[1]
            two_proj = round(100 * (d['wins'] + deaths[single_pos] + deaths[pos2]) / d['completions'], 1)
            two_row = {
                'rows': [int(single_pos), int(pos2)],
                'deaths_total': deaths[single_pos] + deaths[pos2],
                'projected_sr_upper_bound': two_proj,
                'second_row_label': rows[pos2]['category'],
            }

        out.append({
            'lid': ex['lid'],
            'date': d['date'],
            'date_label': d['label'],
            'name': d['name'],
            'current_sr': d['solve_rate'],
            'wins': d['wins'],
            'losses': d['losses'],
            'completions': d['completions'],
            'single_row_fix': single,
            'two_row_fix': two_row,
        })
    out.sort(key=lambda x: x['current_sr'])
    return out


def analyse_undated(simulator, explorer, threshold_pct):
    out = []
    for lid, sim in simulator['undated'].items():
        pred_sr_pct = sim['solve_rate'] * 100
        if pred_sr_pct >= threshold_pct:
            continue
        means = [mean_wrongs(d) for d in sim['predicted_row_dists']]
        target = max(range(4), key=lambda i: means[i])
        puzzle_avg = sum(means) / 4 if means else 0
        rel_burden = round(means[target] / puzzle_avg, 2) if puzzle_avg > 0 else None

        ex = explorer['undated_puzzles'].get(lid, {})
        ex_rows = ex.get('rows', {}) if ex else {}
        ex_row = ex_rows.get(str(target), {})

        out.append({
            'lid': lid,
            'name': sim['name'],
            'predicted_sr': round(pred_sr_pct, 1),
            'bottleneck_row': {
                'row_position': target,
                'row_label': sim['row_labels'][target],
                'mean_predicted_wrongs': round(means[target], 2),
                'puzzle_mean_wrongs': round(puzzle_avg, 2),
                'relative_burden': rel_burden,
                'predicted_first_try_pct': round(ex_row.get('first_try_pct', 0) * 100, 1) if ex_row else None,
                'impostor_word': ex_row.get('impostor_word'),
                'row_pdl': {
                    'manipulation': ex_row.get('manipulation'),
                    'abstraction': ex_row.get('abstraction'),
                    'knowledge': ex_row.get('knowledge'),
                    'knowledgeDomain': ex_row.get('knowledgeDomain'),
                    'same_domain': ex_row.get('same_domain'),
                },
            },
        })
    out.sort(key=lambda x: x['predicted_sr'])
    return out


def render_text(payload, threshold_pct):
    lines = []
    p = lines.append
    p(f"RELINK FIX-LEVERAGE PUNCH LIST  (threshold: < {threshold_pct}% solve rate)")
    p(f"Generated: {payload['generated_at']}")
    p("Pipeline outputs read from outputs/data/")
    p("")
    p("═" * 72)
    p("SECTION 1 — DATED PUZZLES (real player data)")
    p("═" * 72)

    dated_one = [d for d in payload['dated'] if d['two_row_fix'] is None]
    dated_two = [d for d in payload['dated'] if d['two_row_fix'] is not None]

    if dated_one:
        p("")
        p(f"Single-row fix lifts puzzle to ≥ {threshold_pct}%:")
        p("")
        for d in dated_one:
            s = d['single_row_fix']
            p(f"  {d['date_label']:<7}{d['name'][:38]:<40}{d['current_sr']:>4.0f}% → {s['projected_sr_upper_bound']:>4.0f}%   "
              f"row {s['row_position']} \"{s['row_label']}\" (imp: {s['impostor_word']})")
            tw = s.get('top_wrong_picks') or []
            tw_str = ', '.join(f"{w}({n})" for w, n in tw[:2]) if tw else '—'
            p(f"  {' '*47}{s['deaths_at_row']} deaths · FT {s['first_try_pct']:.0f}% · top wrong: {tw_str}")

    if dated_two:
        p("")
        p(f"Need 2-row fix to reach ≥ {threshold_pct}%:")
        p("")
        for d in dated_two:
            s = d['single_row_fix']
            t = d['two_row_fix']
            p(f"  {d['date_label']:<7}{d['name'][:38]:<40}{d['current_sr']:>4.0f}% → {t['projected_sr_upper_bound']:>4.0f}%   "
              f"rows {t['rows'][0]}+{t['rows'][1]} (\"{s['row_label']}\" + \"{t['second_row_label']}\")")
            p(f"  {' '*47}{t['deaths_total']} deaths combined")

    p("")
    p("═" * 72)
    p("SECTION 2 — UNDATED PUZZLES (simulator-predicted)")
    p("═" * 72)
    p("")
    p(f"Worst predicted solve rates with bottleneck-row identification (pred SR < {threshold_pct}%):")
    p("")
    for u in payload['undated']:
        b = u['bottleneck_row']
        p(f"  {u['lid']:<5}{u['name'][:35]:<37}predSR {u['predicted_sr']:>4.0f}%   "
          f"bottleneck: row {b['row_position']} \"{b['row_label']}\"")
        rel = f"{b['relative_burden']:.1f}× burden" if b['relative_burden'] is not None else "—"
        p(f"  {' '*42}mean wrongs {b['mean_predicted_wrongs']:.2f} (puzzle avg {b['puzzle_mean_wrongs']:.2f}, {rel})")
        pdl = b['row_pdl']
        pdl_str = f"{pdl['manipulation']} / {pdl['abstraction']} / {pdl['knowledge']} / {pdl['knowledgeDomain']}"
        same = "True" if pdl.get('same_domain') else "False"
        imp = b.get('impostor_word') or '?'
        p(f"  {' '*42}PDL: {pdl_str} · same_domain={same} · imp={imp}")
        p("")

    p(f"Counts: {len(payload['dated'])} dated, {len(payload['undated'])} undated below threshold.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--threshold', type=float, default=60.0,
                    help='Solve-rate threshold (percent, default 60).')
    ap.add_argument('--data-dir', default=DEFAULT_DATA_DIR,
                    help='Directory of pipeline JSON outputs (default outputs/data).')
    args = ap.parse_args()

    overview = json.load(open(os.path.join(args.data_dir, 'overview.json')))
    explorer = json.load(open(os.path.join(args.data_dir, 'puzzle-explorer.json')))
    simulator = json.load(open(os.path.join(args.data_dir, 'simulator.json')))

    payload = {
        'threshold_pct': args.threshold,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'dated': analyse_dated(overview, explorer, args.threshold),
        'undated': analyse_undated(simulator, explorer, args.threshold),
    }

    text = render_text(payload, args.threshold)

    json_path = os.path.join(args.data_dir, JSON_OUT_NAME)
    with open(json_path, 'w') as f:
        json.dump(payload, f, indent=2)
    with open(TXT_OUT, 'w') as f:
        f.write(text + "\n")

    print(text)
    print(f"\nWrote {TXT_OUT}")
    print(f"Wrote {json_path}")


if __name__ == '__main__':
    main()
