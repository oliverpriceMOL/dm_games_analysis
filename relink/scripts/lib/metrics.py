"""Analysis computations. Each function takes loaded data, returns JSON-serialisable dicts."""

import math
from collections import defaultdict, Counter

from .stats import (safe_mean, safe_median, pearson, spearman, ols_multi,
                    one_hot, kmeans)
from .data import date_label


# ══════════════════════════════════════════════════════════════════════
#  CROSS-TABS
# ══════════════════════════════════════════════════════════════════════

def _cross_tab(rows, field):
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


def compute_crosstabs(row_joined):
    """Compute cross-tab breakdowns + heatmap data.
    Returns dict with keys: chart_data, heatmap, impostor_domain.
    """
    ct_manipulation = _cross_tab(row_joined, 'manipulation')
    ct_abstraction = _cross_tab(row_joined, 'abstraction')
    ct_knowledge = _cross_tab(row_joined, 'knowledge')
    ct_domain = _cross_tab(row_joined, 'knowledgeDomain')
    ct_imp_domain = _cross_tab(row_joined, 'impostor_domain')
    ct_same_domain = _cross_tab(row_joined, 'same_domain')

    # Chart data for bar charts
    chart_data = {}
    for axis_name, ct in [('Manipulation', ct_manipulation), ('Abstraction', ct_abstraction),
                           ('Knowledge', ct_knowledge), ('Knowledge Domain', ct_domain)]:
        chart_data[axis_name] = {
            'labels': list(ct.keys()),
            'first_try': [ct[k]['mean_first_try'] * 100 for k in ct],
            'avg_wrong': [ct[k]['mean_avg_wrong'] for k in ct],
            'never_correct': [ct[k]['mean_never_correct'] * 100 for k in ct],
            'n': [ct[k]['n'] for k in ct],
        }

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

    # Impostor domain
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

    return {
        'chart_data': chart_data,
        'heatmap': {
            'manips': all_manips_hm,
            'abstrs': all_abstrs_hm,
            'values': hm_values,
            'annotations': hm_annotations,
        },
        'impostor_domain': imp_domain_chart,
        # Pass through raw cross-tabs for internal use
        '_ct_manipulation': ct_manipulation,
        '_ct_abstraction': ct_abstraction,
        '_ct_knowledge': ct_knowledge,
        '_ct_domain': ct_domain,
    }


# ══════════════════════════════════════════════════════════════════════
#  CORRELATIONS & REGRESSION
# ══════════════════════════════════════════════════════════════════════

CORR_FEATURES = [
    ('phase2TileCount', 'Phase 2 Tile Count'),
    ('decoyCount', 'Decoy Count'),
    ('manipulationComplexity', 'Manipulation Complexity'),
    ('abstractionComplexity', 'Abstraction Complexity'),
    ('knowledgeBreadth', 'Knowledge Breadth'),
    ('specialistGroupCount', 'Specialist Group Count'),
]


def compute_correlations(puzzle_data, overlap_dates, date_summaries):
    """Compute feature correlations with solve rate. Returns scatter_data dict."""
    scatter_data = {}
    for feat, label in CORR_FEATURES:
        xs = [p[feat] for p in puzzle_data]
        ys = [p['solve_rate'] for p in puzzle_data]
        r, p_val = pearson(xs, ys)
        rs, ps = spearman(xs, ys)
        scatter_data[feat] = {
            'label': label,
            'xs': xs,
            'ys': [round(y * 100, 1) for y in ys],
            'pearson_r': round(r, 3),
            'spearman_r': round(rs, 3),
            'labels': [date_summaries[d]['name'] for d in overlap_dates],
        }
    return scatter_data


def compute_regression(puzzle_data, row_joined, overlap_dates, date_summaries):
    """Compute puzzle-level and row-level regressions. Returns regression_data dict."""
    # Puzzle-level
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
        pred = c[0] + sum(c[k + 1] * X_multi[i][k] for k in range(len(X_multi[i])))
        loo_errors.append(abs(y_multi[i] - pred))
    loo_mae = safe_mean(loo_errors)

    # Row-level
    manip_cats = sorted(set(r['manipulation'] for r in row_joined))
    abstr_cats = sorted(set(r['abstraction'] for r in row_joined))
    know_cats = sorted(set(r['knowledge'] for r in row_joined))

    row_feature_names = ['Intercept']
    for c in manip_cats[1:]:
        row_feature_names.append(f'manip:{c}')
    for c in abstr_cats[1:]:
        row_feature_names.append(f'abstr:{c}')
    for c in know_cats[1:]:
        row_feature_names.append(f'know:{c}')
    row_feature_names.append('same_domain')

    row_X = []
    row_y = []
    for r in row_joined:
        features = one_hot(r['manipulation'], manip_cats) + \
                   one_hot(r['abstraction'], abstr_cats) + \
                   one_hot(r['knowledge'], know_cats) + \
                   [1 if r['same_domain'] else 0]
        row_X.append(features)
        row_y.append(r['first_try_pct'])

    row_coefs, row_r2, row_resid = ols_multi(row_X, row_y)

    # Position-controlled
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

    return regression_data


# ══════════════════════════════════════════════════════════════════════
#  VERTICAL INFERENCE
# ══════════════════════════════════════════════════════════════════════

def compute_vertical_inference(overlap_dates, date_summaries, players_by_date,
                               pdl_puzzle_features, aggregate_timing):
    """Compute transparency scores and VI curves. Returns (vi_chart_data, transparency_scores)."""
    transparency_scores = {}
    for d in overlap_dates:
        ds = date_summaries[d]
        pf = pdl_puzzle_features[ds['lid']]
        pp = players_by_date[d]

        errors_by_pos = defaultdict(list)
        for p in pp:
            if p['outcome'] not in ('WON', 'LOST'):
                continue
            sorted_guesses = sorted(p['real_guesses'], key=lambda g: g['ts'])
            seen_rows = set()
            correct_order = []
            for g in sorted_guesses:
                if g['is_correct'] and g['row'] not in seen_rows:
                    seen_rows.add(g['row'])
                    correct_order.append(g['row'])

            for pos, row in enumerate(correct_order):
                wrong_count = 0
                for g in sorted_guesses:
                    if g['row'] == row:
                        if g['is_correct']:
                            break
                        wrong_count += 1
                errors_by_pos[pos].append(wrong_count)

        pos_means = {}
        pos_ns = {}
        for pos in range(4):
            vals = errors_by_pos.get(pos, [])
            pos_means[pos] = safe_mean(vals) if vals else None
            pos_ns[pos] = len(vals)

        curve_vals = [(p, pos_means[p]) for p in range(4) if pos_means[p] is not None]
        total_weight = sum(v for _, v in curve_vals)
        if len(curve_vals) >= 2 and total_weight > 0:
            transp = sum(i * v for i, v in curve_vals) / total_weight
        else:
            transp = None

        transparency_scores[d] = {
            'pos_means': {p: round(pos_means[p], 3) if pos_means[p] is not None else None for p in range(4)},
            'pos_ns': pos_ns,
            'transparency': round(transp, 3) if transp is not None else None,
            'relink_id_manipulation': pf['relink_id_manipulation'],
            'relink_con_manipulation': pf['relink_con_manipulation'],
        }

    # Per-puzzle VI data
    vi_puzzle_data = []
    for d in overlap_dates:
        ds = date_summaries[d]
        pf = pdl_puzzle_features[ds['lid']]
        ts = transparency_scores[d]

        intervals_by_pos = defaultdict(list)
        for pos, iv in ds['inter_correct_intervals']:
            intervals_by_pos[pos].append(iv)
        timing_curve = [round(safe_median(intervals_by_pos.get(p, [])), 2)
                        if intervals_by_pos.get(p) else None for p in range(4)]

        tc_indexed = [(i, v) for i, v in enumerate(timing_curve) if v is not None]
        tc_total = sum(v for _, v in tc_indexed)
        if len(tc_indexed) >= 2 and tc_total > 0:
            timing_auc = sum(i * v for i, v in tc_indexed) / tc_total
        else:
            timing_auc = None

        vi_puzzle_data.append({
            'label': ds['label'],
            'name': ds['name'],
            'timing_curve': timing_curve,
            'timing_auc': round(timing_auc, 3) if timing_auc is not None else None,
            'error_curve': [ts['pos_means'].get(p) for p in range(4)],
            'error_auc': ts['transparency'],
            'solve_rate': round(ds['solve_rate'] * 100, 1),
            'manipulationComplexity': pf['manipulationComplexity'],
            'abstractionComplexity': pf['abstractionComplexity'],
            'knowledgeBreadth': pf['knowledgeBreadth'],
            'phase2TileCount': pf['phase2TileCount'],
            'decoyCount': pf['decoyCount'],
            'relink_id_manipulation': pf['relink_id_manipulation'],
            'relink_con_manipulation': pf['relink_con_manipulation'],
            'hasSpecialist': pf['hasSpecialist'],
        })

    # Cross-tabs by PDL features
    vi_feature_axes = [
        ('manipulationComplexity', 'Manipulation Complexity'),
        ('abstractionComplexity', 'Abstraction Complexity'),
        ('knowledgeBreadth', 'Knowledge Breadth'),
        ('phase2TileCount', 'Phase 2 Tile Count'),
        ('decoyCount', 'Decoy Count'),
        ('relink_id_manipulation', 'Relink Identification'),
        ('relink_con_manipulation', 'Relink Construction'),
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
            cat_tcurves = [p['timing_curve'] for p in items if p.get('timing_curve')]
            avg_tcurve = []
            for pos in range(4):
                vals = [c[pos] for c in cat_tcurves if c[pos] is not None]
                avg_tcurve.append(round(safe_mean(vals), 2) if vals else None)
            cat_ecurves = [p['error_curve'] for p in items if p.get('error_curve')]
            avg_ecurve = []
            for pos in range(4):
                vals = [c[pos] for c in cat_ecurves if c[pos] is not None]
                avg_ecurve.append(round(safe_mean(vals), 3) if vals else None)
            tab[cat] = {
                'n': len(items),
                'timing_curve': avg_tcurve,
                'error_curve': avg_ecurve,
                'mean_solve_rate': round(safe_mean([p['solve_rate'] for p in items]), 1),
                'puzzles': [p['name'] for p in items],
            }
        vi_crosstabs[feat_key] = {'label': feat_label, 'categories': tab}

    # Aggregate summary
    all_timing_aucs = [p['timing_auc'] for p in vi_puzzle_data if p['timing_auc'] is not None]
    all_error_aucs = [p['error_auc'] for p in vi_puzzle_data if p['error_auc'] is not None]

    agg_errors_by_pos = defaultdict(list)
    for d in overlap_dates:
        ts = transparency_scores[d]
        for pos in range(4):
            if ts['pos_means'][pos] is not None:
                agg_errors_by_pos[pos].append(ts['pos_means'][pos])

    vi_summary = {
        'timing_curve': [round(aggregate_timing.get(p, {}).get('median', 0), 1) for p in range(4)],
        'timing_ns': [aggregate_timing.get(p, {}).get('n', 0) for p in range(4)],
        'mean_timing_auc': round(safe_mean(all_timing_aucs), 3) if all_timing_aucs else None,
        'n_sped_up': sum(1 for a in all_timing_aucs if a < 1.5),
        'error_curve': [round(safe_mean(agg_errors_by_pos.get(p, [])), 3) if agg_errors_by_pos.get(p) else None for p in range(4)],
        'error_ns': [len(agg_errors_by_pos.get(p, [])) for p in range(4)],
        'mean_error_auc': round(safe_mean(all_error_aucs), 3) if all_error_aucs else None,
        'n_more_accurate': sum(1 for t in all_error_aucs if t < 1.5),
        'n_total': len(vi_puzzle_data),
    }

    vi_chart_data = {
        'puzzles': vi_puzzle_data,
        'crosstabs': dict(vi_crosstabs),
        'summary': vi_summary,
    }

    return vi_chart_data, transparency_scores


# ══════════════════════════════════════════════════════════════════════
#  DECOYS & CONFUSION
# ══════════════════════════════════════════════════════════════════════

def compute_decoys(overlap_dates, date_summaries, pdl_puzzle_features, pdl_puzzles, players_by_date):
    """Compute decoy comparison and hit analysis. Returns decoy_chart dict."""
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

    decoy_hit_analysis = []
    for d in overlap_dates:
        ds = date_summaries[d]
        lid = ds['lid']
        pdata = pdl_puzzles[lid]
        decoys = pdata.get('decoys', [])
        if not decoys:
            continue

        decoy_tile_ids = set()
        for dec in decoys:
            for tid in dec.get('tileIds', []):
                decoy_tile_ids.add(tid)

        decoy_impostor_words = set()
        for row in pdata.get('rows', []):
            for tile in row.get('tiles', []):
                if tile['id'] in decoy_tile_ids and not tile.get('isImpostor', False):
                    decoy_impostor_words.add(tile['text'].lower())

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

    return {
        'no_decoys': decoy_comparison['no_decoys'],
        'has_decoys': decoy_comparison['has_decoys'],
        'hit_analysis': decoy_hit_analysis,
    }


# ══════════════════════════════════════════════════════════════════════
#  RELINK PHASE
# ══════════════════════════════════════════════════════════════════════

def compute_relink(overlap_dates, date_summaries, pdl_puzzle_features):
    """Compute relink phase analysis. Returns relink_chart_data dict."""
    relink_by_id_manip = defaultdict(list)
    relink_by_con_manip = defaultdict(list)
    relink_by_tiles = defaultdict(list)
    for d in overlap_dates:
        ds = date_summaries[d]
        pf = pdl_puzzle_features[ds['lid']]
        relink_by_id_manip[pf['relink_id_manipulation']].append(ds)
        relink_by_con_manip[pf['relink_con_manipulation']].append(ds)
        relink_by_tiles[pf['phase2TileCount']].append(ds)

    def _manip_stats(groups):
        out = {}
        for manip, dss in sorted(groups.items()):
            out[manip] = {
                'n': len(dss),
                'mean_first_try': safe_mean([ds['relink_first_try_pct'] for ds in dss]),
                'mean_attempts': safe_mean([ds['relink_avg_attempts'] for ds in dss]),
            }
        return out

    relink_tile_stats = {}
    for tc, dss in sorted(relink_by_tiles.items()):
        relink_tile_stats[tc] = {
            'n': len(dss),
            'mean_first_try': safe_mean([ds['relink_first_try_pct'] for ds in dss]),
            'mean_attempts': safe_mean([ds['relink_avg_attempts'] for ds in dss]),
            'mean_solve_rate': safe_mean([ds['solve_rate'] for ds in dss]),
        }

    return {
        'by_id_manip': _manip_stats(relink_by_id_manip),
        'by_con_manip': _manip_stats(relink_by_con_manip),
        'by_tiles': {str(k): v for k, v in relink_tile_stats.items()},
    }


# ══════════════════════════════════════════════════════════════════════
#  CLUSTERING
# ══════════════════════════════════════════════════════════════════════

def compute_clustering(pdl_puzzles, pdl_rows, pdl_puzzle_features, level_to_date,
                       date_summaries, row_joined):
    """Compute puzzle and row clustering. Returns (cluster_chart_data, cluster_assignments)."""
    all_manips = sorted(set(r['manipulation'] for r in pdl_rows))
    all_abstrs = sorted(set(r['abstraction'] for r in pdl_rows))
    all_knows = sorted(set(r['knowledge'] for r in pdl_rows))

    def puzzle_feature_vec(lid):
        rows = [r for r in pdl_rows if r['lid'] == lid]
        pf = pdl_puzzle_features[lid]
        vec = []
        for m in all_manips:
            vec.append(sum(1 for r in rows if r['manipulation'] == m))
        for a in all_abstrs:
            vec.append(sum(1 for r in rows if r['abstraction'] == a))
        for k in all_knows:
            vec.append(sum(1 for r in rows if r['knowledge'] == k))
        vec.append(pf['phase2TileCount'])
        vec.append(pf['decoyCount'])
        vec.append(pf['specialistGroupCount'])
        return vec

    puzzle_vecs = {}
    for lid in pdl_puzzles:
        puzzle_vecs[lid] = puzzle_feature_vec(lid)

    cluster_assignments, cluster_centroids = kmeans(puzzle_vecs, k=3)

    cluster_profiles = {}
    for ci in range(3):
        members = [lid for lid, c in cluster_assignments.items() if c == ci]
        centroid = cluster_centroids[ci]

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
        manip_vals = {m: c.get(f'manip_{m}', 0) for m in all_manips}
        non_none_manip = sum(v for k, v in manip_vals.items() if 'None' not in k)
        abstr_vals = {a: c.get(f'abstr_{a}', 0) for a in all_abstrs}
        non_direct = sum(v for k, v in abstr_vals.items() if 'Direct' not in k)

        if non_none_manip > 1.5:
            name = "Complex Manipulation"
        elif non_direct > 0.8:
            name = "Abstract Reasoning"
        else:
            name = "Straightforward"

        know_spec = c.get('know_Specialist cultural', 0)
        if know_spec > 0.5:
            name += " + Specialist"
        cp['name'] = name

    # Row-level clustering
    def row_feature_vec(r):
        vec = [1 if r['manipulation'] == m else 0 for m in all_manips]
        vec += [1 if r['abstraction'] == a else 0 for a in all_abstrs]
        vec += [1 if r['knowledge'] == k else 0 for k in all_knows]
        vec += [1 if r['same_domain'] else 0]
        return vec

    row_vecs_map = {}
    for i, r in enumerate(row_joined):
        row_vecs_map[i] = row_feature_vec(r)

    row_cluster_assignments, _ = kmeans(row_vecs_map, k=4)

    row_cluster_stats = {}
    for ci in range(4):
        members = [i for i, c in row_cluster_assignments.items() if c == ci]
        if not members:
            continue
        member_rows = [row_joined[i] for i in members]
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

    # Build chart data
    cluster_chart_data = {'puzzles': {}, 'rows': {}}
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

    return cluster_chart_data, cluster_assignments


# ══════════════════════════════════════════════════════════════════════
#  OVERVIEW (Key Findings summary data)
# ══════════════════════════════════════════════════════════════════════

def compute_overview(date_summaries, pdl_puzzle_features, pdl_puzzles, overlap_dates, aggregate_timing):
    """Compute overview/summary data for the Key Findings section."""
    return {
        'n_puzzles': len(pdl_puzzles),
        'n_dated': len(overlap_dates),
        'total_completions': sum(ds['completions'] for ds in date_summaries.values()),
        'dates': [{
            'date': ds['date'],
            'label': ds['label'],
            'name': ds['name'],
            'players': ds['players'],
            'wins': ds['wins'],
            'losses': ds['losses'],
            'completions': ds['completions'],
            'solve_rate': round(ds['solve_rate'] * 100, 1),
            'median_time': round(ds['median_time'], 1),
        } for ds in (date_summaries[d] for d in overlap_dates)],
        'aggregate_timing': aggregate_timing,
    }


# ══════════════════════════════════════════════════════════════════════
#  PUZZLE EXPLORER
# ══════════════════════════════════════════════════════════════════════

def compute_puzzle_explorer(overlap_dates, date_summaries, players_by_date,
                            pdl_puzzle_features, pdl_rows, transparency_scores,
                            sim_results, failure_data,
                            feat_sim_results=None, sim_undated=None,
                            transition_data=None, relink_feature_dists=None,
                            pdl_puzzles=None, level_to_date=None,
                            date_to_level=None, row_joined=None):
    """Build per-puzzle deep-dive data for the Puzzle Explorer page.

    Returns dict with:
      - puzzles: keyed by date, with actual + predicted distributions
      - undated_puzzles: keyed by lid, with predicted-only distributions
      - pdl_aggregates: average dist shapes grouped by PDL category
    """
    puzzles = {}

    for d in overlap_dates:
        ds = date_summaries[d]
        lid = ds['lid']
        pf = pdl_puzzle_features[lid]
        pp = players_by_date[d]
        ts = transparency_scores.get(d, {})

        # --- Row-level data ---
        rows_data = {}
        puzzle_pdl_rows = {str(pr['row_position']): pr
                          for pr in pdl_rows if pr['lid'] == lid}

        for row_pos in range(4):
            rp = str(row_pos)
            pr = puzzle_pdl_rows.get(rp, {})
            rm = ds['row_metrics'].get(row_pos, {})

            # Build wrong-guess distribution from player trajectories
            # Split by row outcome: solved (got it right), lost (died elsewhere),
            # incomplete (abandoned). Each key is e.g. '1_solved', '2_lost'.
            solved_dist = Counter()
            lost_dist = Counter()
            incomplete_dist = Counter()
            no_attempt_lost = 0
            no_attempt_incomplete = 0

            for p in pp:
                row_guesses = [g for g in p['real_guesses'] if g['row'] == rp]
                if not row_guesses:
                    # Player has no guess events for this row.
                    # WON players with missing events are a data gap (events
                    # not logged), not evidence of 0 wrongs — skip them.
                    if p['outcome'] == 'LOST':
                        no_attempt_lost += 1
                    elif p['outcome'] == 'INCOMPLETE':
                        no_attempt_incomplete += 1
                    continue
                row_wrongs = sum(1 for g in row_guesses if not g['is_correct'])
                # Cap at 3 (mechanical max per row; extras are duplicate events)
                row_wrongs = min(row_wrongs, 3)
                row_solved = any(g['is_correct'] for g in row_guesses)
                if row_solved:
                    solved_dist[row_wrongs] += 1
                elif p['outcome'] == 'LOST':
                    lost_dist[row_wrongs] += 1
                else:  # INCOMPLETE
                    incomplete_dist[row_wrongs] += 1

            # Attempt order distribution
            attempt_order_dist = Counter()
            if rm.get('attempt_positions'):
                for pos in rm['attempt_positions']:
                    attempt_order_dist[pos] += 1

            rows_data[rp] = {
                'category': pr.get('category', f'Row {rp}'),
                'manipulation': pr.get('manipulation', 'None'),
                'abstraction': pr.get('abstraction', 'Direct membership'),
                'knowledge': pr.get('knowledge', 'General vocabulary'),
                'knowledgeDomain': pr.get('knowledgeDomain', 'General'),
                'impostor_word': pr.get('impostor_word', ''),
                'non_impostor_words': pr.get('non_impostor_words', []),
                'same_domain': pr.get('same_domain', False),
                'attempts': rm.get('attempts', 0),
                'first_try_pct': round(rm.get('first_try_pct', 0), 3),
                'avg_wrong': round(rm.get('avg_wrong', 0), 2),
                'never_correct_pct': round(rm.get('never_correct_pct', 0), 3),
                'wrong_dist': {
                    '0_solved': solved_dist.get(0, 0),
                    '1_solved': solved_dist.get(1, 0),
                    '1_lost': lost_dist.get(1, 0),
                    '1_incomplete': incomplete_dist.get(1, 0),
                    '2_solved': solved_dist.get(2, 0),
                    '2_lost': lost_dist.get(2, 0),
                    '2_incomplete': incomplete_dist.get(2, 0),
                    '3_solved': solved_dist.get(3, 0),
                    '3_lost': lost_dist.get(3, 0),
                    '3_incomplete': incomplete_dist.get(3, 0),
                    'no_attempt_lost': no_attempt_lost,
                    'no_attempt_incomplete': no_attempt_incomplete,
                },
                'wrong_dist_completed': {
                    '0_solved': solved_dist.get(0, 0),
                    '1_solved': solved_dist.get(1, 0),
                    '1_lost': lost_dist.get(1, 0),
                    '2_solved': solved_dist.get(2, 0),
                    '2_lost': lost_dist.get(2, 0),
                    '3_solved': solved_dist.get(3, 0),
                    '3_lost': lost_dist.get(3, 0),
                    'no_attempt_lost': no_attempt_lost,
                },
                'top_wrong': rm.get('top_wrong', [])[:5],
                'attempt_order_dist': {str(k): v for k, v in sorted(attempt_order_dist.items())},
            }

        # --- Relink wrong-guess distribution ---
        # Relink phase: if you won you solved all rows + relink. If you lost at relink,
        # you had all impostors but failed the connection. Split by outcome.
        relink_solved_dist = Counter()      # WON at relink
        relink_lost_dist = Counter()        # LOST at relink
        relink_incomplete_dist = Counter()  # Abandoned at relink
        relink_no_attempt_lost = 0
        relink_no_attempt_incomplete = 0
        relink_total = 0
        relink_total_completed = 0

        for p in pp:
            is_completed = p['outcome'] in ('WON', 'LOST')
            rt = p.get('relink_trajectory')
            if rt:
                relink_total += 1
                wc = rt['wrong_count']
                if p['outcome'] == 'WON':
                    relink_solved_dist[wc] += 1
                elif p['outcome'] == 'LOST':
                    relink_lost_dist[wc] += 1
                else:
                    relink_incomplete_dist[wc] += 1
                if is_completed:
                    relink_total_completed += 1
            else:
                # No relink trajectory — WON players with missing events
                # are a data gap, not 0-wrong evidence; skip them.
                if p['outcome'] == 'LOST':
                    relink_no_attempt_lost += 1
                elif p['outcome'] == 'INCOMPLETE':
                    relink_no_attempt_incomplete += 1

        relink_data = {
            'first_try_pct': round(ds['relink_first_try_pct'], 3),
            'avg_attempts': round(ds['relink_avg_attempts'], 2),
            'total': relink_total,
            'wrong_dist': {
                '0_solved': relink_solved_dist.get(0, 0),
                '0_lost': relink_lost_dist.get(0, 0),
                '0_incomplete': relink_incomplete_dist.get(0, 0),
                '1_solved': relink_solved_dist.get(1, 0),
                '1_lost': relink_lost_dist.get(1, 0),
                '1_incomplete': relink_incomplete_dist.get(1, 0),
                '2_solved': relink_solved_dist.get(2, 0),
                '2_lost': relink_lost_dist.get(2, 0),
                '2_incomplete': relink_incomplete_dist.get(2, 0),
                '3_solved': relink_solved_dist.get(3, 0),
                '3_lost': relink_lost_dist.get(3, 0),
                '3_incomplete': relink_incomplete_dist.get(3, 0),
                '4_solved': relink_solved_dist.get(4, 0),
                '4_lost': relink_lost_dist.get(4, 0),
                '4_incomplete': relink_incomplete_dist.get(4, 0),
                'no_attempt_lost': relink_no_attempt_lost,
                'no_attempt_incomplete': relink_no_attempt_incomplete,
            },
            'wrong_dist_completed': {
                '0_solved': relink_solved_dist.get(0, 0),
                '0_lost': relink_lost_dist.get(0, 0),
                '1_solved': relink_solved_dist.get(1, 0),
                '1_lost': relink_lost_dist.get(1, 0),
                '2_solved': relink_solved_dist.get(2, 0),
                '2_lost': relink_lost_dist.get(2, 0),
                '3_solved': relink_solved_dist.get(3, 0),
                '3_lost': relink_lost_dist.get(3, 0),
                '4_solved': relink_solved_dist.get(4, 0),
                '4_lost': relink_lost_dist.get(4, 0),
                'no_attempt_lost': relink_no_attempt_lost,
            },
            'answer': pf.get('relink_answer', ''),
        }

        # --- Timing & error curves ---
        intervals_by_pos = defaultdict(list)
        for pos, iv in ds['inter_correct_intervals']:
            intervals_by_pos[pos].append(iv)
        timing_curve = [round(safe_median(intervals_by_pos.get(p, [])), 2)
                        if intervals_by_pos.get(p) else None for p in range(4)]
        error_curve = [ts.get('pos_means', {}).get(p) for p in range(4)]

        def _com(curve):
            indexed = [(i, v) for i, v in enumerate(curve) if v is not None]
            total = sum(v for _, v in indexed)
            if len(indexed) >= 2 and total > 0:
                return round(sum(i * v for i, v in indexed) / total, 3)
            return None

        timing_data = {
            'timing_curve': timing_curve,
            'error_curve': error_curve,
            'timing_com': _com(timing_curve),
            'error_com': _com(error_curve),
        }

        # --- Whole-puzzle mistake distribution ---
        # Total wrong guesses across both imposters + relink phases.
        # LOST = 4 wrongs by definition (all lives consumed).
        # WON: use relink_trajectory.lives_before to derive imposters wrongs,
        #       falling back to trajectory step sums if relink data is missing.
        #       Capped at 3 since winners must have ≥1 life remaining.
        # INCOMPLETE: best-effort from available trajectory data.
        mistake_dist = Counter()
        mistake_dist_completed = Counter()
        for p in pp:
            is_completed = p['outcome'] in ('WON', 'LOST')
            if p['outcome'] == 'LOST':
                total_wrongs = 4
            elif p['outcome'] == 'WON':
                rt = p.get('relink_trajectory')
                if rt:
                    total_wrongs = (4 - rt['lives_before']) + rt['wrong_count']
                else:
                    traj = p.get('trajectory', [])
                    total_wrongs = sum(step['wrong_count'] for step in traj)
                total_wrongs = min(total_wrongs, 3)  # winners always have ≥1 life
            else:
                rt = p.get('relink_trajectory')
                if rt:
                    total_wrongs = (4 - rt['lives_before']) + rt['wrong_count']
                else:
                    traj = p.get('trajectory', [])
                    total_wrongs = sum(step['wrong_count'] for step in traj)
            mistake_dist[total_wrongs] += 1
            if is_completed:
                mistake_dist_completed[total_wrongs] += 1

        # --- Failure correlations (from pre-computed failure_data) ---
        fd_puzzle = failure_data.get('per_puzzle', {}).get(d, {})
        failure_corr = {
            'phi_matrix': fd_puzzle.get('phi_matrix', {}),
            'row_failure_rates': fd_puzzle.get('row_failure_rates', {}),
        }

        # --- Simulator (from pre-computed sim_results) ---
        sr = sim_results.get(d, {})
        simulator_data = {
            'simulated_solve_rate': round(sr['solve_rate'] * 100, 1) if 'solve_rate' in sr else None,
            'actual_solve_rate': round(ds['solve_rate'] * 100, 1),
        }

        puzzles[d] = {
            'name': ds['name'],
            'label': ds['label'],
            'date': d,
            'lid': lid,
            'players': ds['players'],
            'wins': ds['wins'],
            'losses': ds['losses'],
            'incomplete': ds['incomplete'],
            'solve_rate': round(ds['solve_rate'], 3),
            'median_time': round(ds['median_time'], 1),
            'has_player_data': True,
            'pdl': {
                'manipulationComplexity': pf['manipulationComplexity'],
                'abstractionComplexity': pf['abstractionComplexity'],
                'knowledgeBreadth': pf['knowledgeBreadth'],
                'phase2TileCount': pf['phase2TileCount'],
                'decoyCount': pf['decoyCount'],
                'relink_id_manipulation': pf['relink_id_manipulation'],
                'relink_con_manipulation': pf['relink_con_manipulation'],
            },
            'rows': rows_data,
            'relink': relink_data,
            'mistake_dist': {str(k): v for k, v in sorted(mistake_dist.items())},
            'mistake_dist_completed': {str(k): v for k, v in sorted(mistake_dist_completed.items())},
            'timing': timing_data,
            'failure_correlations': failure_corr,
            'simulator': simulator_data,
            'mean_lives_at_win': round(sr.get('mean_lives_at_win', 0), 2) if sr else None,
            'rows_completed_pct': sr.get('rows_completed_pct', []) if sr else [],
        }

    # --- Attach predicted distributions to dated puzzles ---
    if feat_sim_results:
        for d, fsr in feat_sim_results.items():
            if d not in puzzles:
                continue
            puzzles[d]['predicted_wrong_dist'] = fsr.get('sim_row_dists', {})
            puzzles[d]['predicted_mistake_dist'] = fsr.get('sim_mistake_dist', {})
            puzzles[d]['predicted_row_labels'] = fsr.get('row_labels', [])
            puzzles[d]['predicted_solve_rate'] = round(fsr.get('solve_rate', 0) * 100, 1)

    # --- Build undated puzzle entries (predicted-only) ---
    undated_puzzles = {}
    if sim_undated and pdl_puzzle_features:
        for lid, sr in sim_undated.items():
            pf = pdl_puzzle_features.get(lid, {})
            if not pf:
                continue
            puzzle_pdl_rows = {str(pr['row_position']): pr
                               for pr in pdl_rows if pr['lid'] == lid}

            # Build row metadata from PDL (no actual distributions)
            rows_meta = {}
            for rp in range(4):
                pr = puzzle_pdl_rows.get(str(rp), {})
                rows_meta[str(rp)] = {
                    'category': pr.get('category', f'Row {rp}'),
                    'manipulation': pr.get('manipulation', 'None'),
                    'abstraction': pr.get('abstraction', 'Direct membership'),
                    'knowledge': pr.get('knowledge', 'General vocabulary'),
                    'knowledgeDomain': pr.get('knowledgeDomain', 'General'),
                    'impostor_word': pr.get('impostor_word', ''),
                    'same_domain': pr.get('same_domain', False),
                }

            d = sr.get('date')
            undated_puzzles[lid] = {
                'name': pf.get('name', lid),
                'label': sr.get('label', pf.get('name', lid)),
                'date': d,
                'lid': lid,
                'has_player_data': False,
                'pdl': {
                    'manipulationComplexity': pf.get('manipulationComplexity', 0),
                    'abstractionComplexity': pf.get('abstractionComplexity', 0),
                    'knowledgeBreadth': pf.get('knowledgeBreadth', 0),
                    'phase2TileCount': pf.get('phase2TileCount', 1),
                    'decoyCount': pf.get('decoyCount', 0),
                    'relink_id_manipulation': pf.get('relink_id_manipulation', 'None'),
                    'relink_con_manipulation': pf.get('relink_con_manipulation', 'None'),
                },
                'rows': rows_meta,
                'relink': {
                    'answer': pf.get('relink_answer', ''),
                },
                'predicted_wrong_dist': sr.get('sim_row_dists', {}),
                'predicted_mistake_dist': sr.get('sim_mistake_dist', {}),
                'predicted_row_labels': sr.get('row_labels', []),
                'predicted_solve_rate': round(sr.get('solve_rate', 0) * 100, 1),
                'simulator': {
                    'simulated_solve_rate': round(sr['solve_rate'] * 100, 1),
                    'actual_solve_rate': None,
                },
                'mean_lives_at_win': round(sr.get('mean_lives_at_win', 0), 2),
                'rows_completed_pct': sr.get('rows_completed_pct', []),
            }

    # --- Aggregate PDL distributions ---
    # For each PDL axis, group rows by category and compute average
    # actual wrong-dist shape (from dated puzzles) and a count.
    pdl_aggregates = {}
    if row_joined:
        from collections import defaultdict as _dd
        axes = {
            'manipulation': 'manipulation',
            'abstraction': 'abstraction',
            'knowledge': 'knowledge',
        }
        for axis_name, field in axes.items():
            buckets = _dd(lambda: {'dists': [], 'n': 0})
            for rj in row_joined:
                cat = rj.get(field, 'Unknown')
                # Row wrong-dist from per-puzzle data: first-try, 1-wrong, etc.
                ft = rj.get('first_try_pct', 0)
                avg_wrong = rj.get('avg_wrong', 0)
                buckets[cat]['dists'].append({
                    'first_try_pct': ft,
                    'avg_wrong': avg_wrong,
                })
                buckets[cat]['n'] += 1

            axis_data = {}
            for cat, bkt in sorted(buckets.items()):
                n = bkt['n']
                if n == 0:
                    continue
                avg_ft = sum(d['first_try_pct'] for d in bkt['dists']) / n
                avg_aw = sum(d['avg_wrong'] for d in bkt['dists']) / n
                axis_data[cat] = {
                    'avg_first_try_pct': round(avg_ft, 3),
                    'avg_wrong': round(avg_aw, 3),
                    'n_rows': n,
                }
            pdl_aggregates[axis_name] = axis_data

        # Same-domain aggregate
        sd_buckets = _dd(lambda: {'dists': [], 'n': 0})
        for rj in row_joined:
            sd = 'Same' if rj.get('same_domain', False) else 'Different'
            sd_buckets[sd]['dists'].append({
                'first_try_pct': rj.get('first_try_pct', 0),
                'avg_wrong': rj.get('avg_wrong', 0),
            })
            sd_buckets[sd]['n'] += 1
        sd_data = {}
        for cat, bkt in sorted(sd_buckets.items()):
            n = bkt['n']
            if n == 0:
                continue
            sd_data[cat] = {
                'avg_first_try_pct': round(sum(d['first_try_pct'] for d in bkt['dists']) / n, 3),
                'avg_wrong': round(sum(d['avg_wrong'] for d in bkt['dists']) / n, 3),
                'n_rows': n,
            }
        pdl_aggregates['same_domain'] = sd_data

    # Build actual aggregate wrong-dist from all dated puzzle row data
    # For each PDL axis × category, average the row-level wrong-dist counts
    # (across all dated puzzles) into a probability distribution.
    if puzzles:
        from collections import defaultdict as _dd
        for axis_name in ['manipulation', 'abstraction', 'knowledge', 'same_domain']:
            if axis_name not in pdl_aggregates:
                pdl_aggregates[axis_name] = {}
            cat_totals = _dd(lambda: _dd(int))
            cat_n = _dd(int)
            for d, puz in puzzles.items():
                for rp_str, rdata in puz['rows'].items():
                    if axis_name == 'same_domain':
                        cat = 'Same' if rdata.get('same_domain', False) else 'Different'
                    else:
                        cat = rdata.get(axis_name, 'Unknown')
                    wd = rdata.get('wrong_dist', {})
                    # Sum solved+lost+incomplete into single wrong-count buckets
                    for n in range(4):
                        total_n = sum(wd.get(f'{n}_{s}', 0) for s in ('solved', 'lost', 'incomplete'))
                        cat_totals[cat][str(n)] += total_n
                    cat_totals[cat]['no_attempt_lost'] += wd.get('no_attempt_lost', 0)
                    cat_totals[cat]['no_attempt_incomplete'] += wd.get('no_attempt_incomplete', 0)
                    cat_n[cat] += 1
            for cat in cat_totals:
                total = sum(cat_totals[cat].values())
                if total > 0 and cat in pdl_aggregates.get(axis_name, {}):
                    pdl_aggregates[axis_name][cat]['actual_wrong_dist'] = {
                        k: round(v / total, 4) for k, v in sorted(cat_totals[cat].items())
                    }

    return {
        'puzzles': puzzles,
        'undated_puzzles': undated_puzzles,
        'pdl_aggregates': pdl_aggregates,
    }
