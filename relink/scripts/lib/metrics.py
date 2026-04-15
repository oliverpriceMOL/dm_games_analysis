"""Analysis computations. Each function takes loaded data, returns JSON-serialisable dicts."""

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
            'relink_manipulation': pf['relink_manipulation'],
            'relink_abstraction': pf['relink_abstraction'],
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
            'relink_manipulation': pf['relink_manipulation'],
            'relink_abstraction': pf['relink_abstraction'],
            'hasSpecialist': pf['hasSpecialist'],
        })

    # Cross-tabs by PDL features
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

    return {
        'by_manip': relink_manip_stats,
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
