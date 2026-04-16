"""Model layer — IPW weights, transition probabilities, game simulator."""

import math
from collections import defaultdict


def compute_ipw_weights(players_by_date, max_weight=20):
    """Compute Inverse Probability Weighting for survivorship bias correction.

    For each (position, lives_before) cell, compute the empirical probability of
    surviving to that state. A player's weight at position k = 1 / P(reaching position k).

    Pools across all puzzle dates for stable estimates.

    Returns:
        ipw_data: dict with 'survival_table', 'player_weights', 'diagnostics'
    """
    # Count transitions: how many players were at each (position, lives) state,
    # and how many survived to the next position.
    # state_counts[(pos, lives)] = number of players who attempted a row at this state
    # state_survived[(pos, lives)] = number who survived (solved the row without dying)
    state_counts = defaultdict(int)
    state_survived = defaultdict(int)

    all_trajectories = []
    for d, pp in players_by_date.items():
        for p in pp:
            traj = p.get('trajectory', [])
            if not traj:
                continue
            all_trajectories.append(traj)
            for step in traj:
                pos = step['position']
                lives = step['lives_before']
                state_counts[(pos, lives)] += 1
                if step['survived']:
                    state_survived[(pos, lives)] += 1
            # Include relink as position 4
            rt = p.get('relink_trajectory')
            if rt:
                state_counts[(4, rt['lives_before'])] += 1
                if rt['survived']:
                    state_survived[(4, rt['lives_before'])] += 1

    # Compute survival rates per state
    survival_table = {}
    for state, count in state_counts.items():
        survived = state_survived.get(state, 0)
        survival_table[state] = {
            'count': count,
            'survived': survived,
            'rate': survived / count if count > 0 else 0,
        }

    # Compute player weights: weight = 1 / P(reaching current state)
    # P(reaching state at position k) = product of survival rates at each prior step
    player_weights = {}  # keyed by (date, player_sid)
    weight_values = []

    for d, pp in players_by_date.items():
        for p in pp:
            traj = p.get('trajectory', [])
            if not traj:
                continue

            # Compute cumulative survival probability for each step
            step_weights = []
            cumulative_prob = 1.0
            for step in traj:
                pos = step['position']
                lives = step['lives_before']
                state = (pos, lives)
                # Weight = 1 / probability of reaching this state
                weight = 1.0 / cumulative_prob if cumulative_prob > 0 else max_weight
                weight = min(weight, max_weight)
                step_weights.append({
                    'position': pos,
                    'lives_before': lives,
                    'row': step['row'],
                    'weight': round(weight, 4),
                })
                # Update cumulative probability for next step
                sr = survival_table.get(state, {}).get('rate', 0)
                if sr > 0:
                    cumulative_prob *= sr
                else:
                    cumulative_prob = 0

            player_weights[(d, p['sid'])] = step_weights
            # Include relink step weight
            rt = p.get('relink_trajectory')
            if rt:
                weight = 1.0 / cumulative_prob if cumulative_prob > 0 else max_weight
                weight = min(weight, max_weight)
                step_weights.append({
                    'position': 4,
                    'lives_before': rt['lives_before'],
                    'row': 'relink',
                    'weight': round(weight, 4),
                })
            weight_values.extend(sw['weight'] for sw in step_weights)

    # Diagnostics
    from .stats import safe_mean, safe_median, percentile
    diagnostics = {}
    if weight_values:
        diagnostics = {
            'n_trajectories': len(all_trajectories),
            'n_steps': len(weight_values),
            'mean_weight': round(safe_mean(weight_values), 3),
            'median_weight': round(safe_median(weight_values), 3),
            'p95_weight': round(percentile(weight_values, 95), 3),
            'max_weight': round(max(weight_values), 3),
            'n_capped': sum(1 for w in weight_values if w >= max_weight),
        }

    return {
        'survival_table': {f'{pos},{lives}': v for (pos, lives), v in survival_table.items()},
        'player_weights': player_weights,
        'diagnostics': diagnostics,
    }


# ══════════════════════════════════════════════════════════════════════
#  B1: Transition Probability Model
# ══════════════════════════════════════════════════════════════════════

def compute_transition_probs(players_by_date, pdl_rows, pdl_puzzle_features,
                             date_to_level, ipw_data):
    """Estimate P(wrong_guesses=k | position, lives, row_PDL, decoy_context).

    Uses IPW weights so later-position estimates aren't biased toward survivors.

    Returns dict with:
      - 'by_position_lives': empirical IPW-weighted wrong-guess distributions
      - 'by_pdl_feature': error rates grouped by PDL axis
      - 'by_decoy': error rates with/without decoy exposure
      - 'intrinsic_difficulty': position-0, 4-lives baseline for each PDL combo
    """
    from .stats import safe_mean, safe_median

    # Build row lookup: (date, row_index) -> row PDL features
    row_pdl_lookup = {}
    for pr in pdl_rows:
        if pr['date']:
            row_pdl_lookup[(pr['date'], str(pr['row_position']))] = pr

    # Build decoy set per puzzle: which row positions contain decoy tiles
    decoy_rows_by_date = {}
    for pr in pdl_rows:
        d = pr['date']
        if not d or d not in date_to_level:
            continue
        lid = date_to_level[d]
        pf = pdl_puzzle_features.get(lid, {})
        decoys = pf.get('decoys', [])
        if not decoys:
            continue
        decoy_tile_ids = set()
        for dec in decoys:
            for tid in dec.get('tileIds', []):
                decoy_tile_ids.add(tid)
        # Mark which row positions have decoy tiles
        if d not in decoy_rows_by_date:
            decoy_rows_by_date[d] = set()
        for row_rec in pdl_rows:
            if row_rec['lid'] == lid:
                if any(tid in decoy_tile_ids for tid in row_rec.get('tile_ids', [])):
                    decoy_rows_by_date[d].add(str(row_rec['row_position']))

    player_weights = ipw_data['player_weights']

    # Collect observations: each row attempt in each trajectory
    observations = []
    for d, pp in players_by_date.items():
        for p in pp:
            traj = p.get('trajectory', [])
            if not traj:
                continue
            pw = player_weights.get((d, p['sid']), [])
            pw_by_pos = {sw['position']: sw['weight'] for sw in pw}

            for step in traj:
                pos = step['position']
                lives = step['lives_before']
                row = step['row']
                wrong = step['wrong_count']
                survived = step['survived']
                weight = pw_by_pos.get(pos, 1.0)

                row_pdl = row_pdl_lookup.get((d, row))
                if not row_pdl:
                    continue

                has_decoy = row in decoy_rows_by_date.get(d, set())

                observations.append({
                    'date': d,
                    'position': pos,
                    'lives': lives,
                    'wrong': wrong,
                    'survived': survived,
                    'weight': weight,
                    'manipulation': row_pdl['manipulation'],
                    'abstraction': row_pdl['abstraction'],
                    'knowledge': row_pdl['knowledge'],
                    'same_domain': row_pdl['same_domain'],
                    'has_decoy': has_decoy,
                })

    # ── By (position, lives) ──
    by_pos_lives = defaultdict(lambda: {'wrongs': [], 'weights': [], 'n': 0})
    for obs in observations:
        key = (obs['position'], obs['lives'])
        by_pos_lives[key]['wrongs'].append(obs['wrong'])
        by_pos_lives[key]['weights'].append(obs['weight'])
        by_pos_lives[key]['n'] += 1

    pos_lives_table = {}
    for (pos, lives), data in sorted(by_pos_lives.items()):
        ww = data['wrongs']
        wts = data['weights']
        w_sum = sum(wts)
        w_mean = sum(wts[i] * ww[i] for i in range(len(ww))) / w_sum if w_sum else 0
        # Weighted first-try rate
        w_first_try = sum(wts[i] for i in range(len(ww)) if ww[i] == 0) / w_sum if w_sum else 0
        # Distribution of wrong counts
        wrong_dist = defaultdict(float)
        for i in range(len(ww)):
            wrong_dist[ww[i]] += wts[i]
        for k in wrong_dist:
            wrong_dist[k] /= w_sum
        pos_lives_table[f'{pos},{lives}'] = {
            'n': data['n'],
            'weighted_mean_wrong': round(w_mean, 3),
            'weighted_first_try': round(w_first_try, 3),
            'wrong_dist': {str(k): round(v, 3) for k, v in sorted(wrong_dist.items())},
        }

    # ── By PDL feature (IPW-weighted) — with full wrong_dist ──
    by_pdl = {}
    for axis in ['manipulation', 'abstraction', 'knowledge']:
        groups = defaultdict(lambda: {'wrongs': [], 'weights': []})
        for obs in observations:
            groups[obs[axis]]['wrongs'].append(obs['wrong'])
            groups[obs[axis]]['weights'].append(obs['weight'])
        result = {}
        for label, data in sorted(groups.items()):
            ww, wts = data['wrongs'], data['weights']
            w_sum = sum(wts)
            w_mean = sum(wts[i] * ww[i] for i in range(len(ww))) / w_sum if w_sum else 0
            w_ft = sum(wts[i] for i in range(len(ww)) if ww[i] == 0) / w_sum if w_sum else 0
            wrong_dist = defaultdict(float)
            for i in range(len(ww)):
                wrong_dist[ww[i]] += wts[i]
            for k in wrong_dist:
                wrong_dist[k] /= w_sum
            result[label] = {
                'n': len(ww),
                'weighted_mean_wrong': round(w_mean, 3),
                'weighted_first_try': round(w_ft, 3),
                'wrong_dist': {str(k): round(v, 3) for k, v in sorted(wrong_dist.items())},
            }
        by_pdl[axis] = result

    # Same domain
    sd_groups = defaultdict(lambda: {'wrongs': [], 'weights': []})
    for obs in observations:
        sd_groups[obs['same_domain']]['wrongs'].append(obs['wrong'])
        sd_groups[obs['same_domain']]['weights'].append(obs['weight'])
    sd_result = {}
    for label, data in sd_groups.items():
        ww, wts = data['wrongs'], data['weights']
        w_sum = sum(wts)
        w_mean = sum(wts[i] * ww[i] for i in range(len(ww))) / w_sum if w_sum else 0
        w_ft = sum(wts[i] for i in range(len(ww)) if ww[i] == 0) / w_sum if w_sum else 0
        wrong_dist = defaultdict(float)
        for i in range(len(ww)):
            wrong_dist[ww[i]] += wts[i]
        for k in wrong_dist:
            wrong_dist[k] /= w_sum
        sd_result[str(label)] = {
            'n': len(ww),
            'weighted_mean_wrong': round(w_mean, 3),
            'weighted_first_try': round(w_ft, 3),
            'wrong_dist': {str(k): round(v, 3) for k, v in sorted(wrong_dist.items())},
        }
    by_pdl['same_domain'] = sd_result

    # ── By decoy exposure ──
    decoy_groups = defaultdict(lambda: {'wrongs': [], 'weights': []})
    for obs in observations:
        decoy_groups[obs['has_decoy']]['wrongs'].append(obs['wrong'])
        decoy_groups[obs['has_decoy']]['weights'].append(obs['weight'])
    by_decoy = {}
    for label, data in decoy_groups.items():
        ww, wts = data['wrongs'], data['weights']
        w_sum = sum(wts)
        w_mean = sum(wts[i] * ww[i] for i in range(len(ww))) / w_sum if w_sum else 0
        w_ft = sum(wts[i] for i in range(len(ww)) if ww[i] == 0) / w_sum if w_sum else 0
        wrong_dist = defaultdict(float)
        for i in range(len(ww)):
            wrong_dist[ww[i]] += wts[i]
        for k in wrong_dist:
            wrong_dist[k] /= w_sum
        by_decoy[str(label)] = {
            'n': len(ww),
            'weighted_mean_wrong': round(w_mean, 3),
            'weighted_first_try': round(w_ft, 3),
            'wrong_dist': {str(k): round(v, 3) for k, v in sorted(wrong_dist.items())},
        }

    # ── By feature combo: (manipulation, has_decoy) — full distributions ──
    # This powers the feature-based simulator for undated puzzles.
    combo_groups = defaultdict(lambda: {'wrongs': [], 'weights': []})
    for obs in observations:
        key = (obs['manipulation'], obs['has_decoy'])
        combo_groups[key]['wrongs'].append(obs['wrong'])
        combo_groups[key]['weights'].append(obs['weight'])
    by_feature_combo = {}
    for (manip, decoy), data in sorted(combo_groups.items()):
        ww, wts = data['wrongs'], data['weights']
        w_sum = sum(wts)
        w_mean = sum(wts[i] * ww[i] for i in range(len(ww))) / w_sum if w_sum else 0
        w_ft = sum(wts[i] for i in range(len(ww)) if ww[i] == 0) / w_sum if w_sum else 0
        wrong_dist = defaultdict(float)
        for i in range(len(ww)):
            wrong_dist[ww[i]] += wts[i]
        for k in wrong_dist:
            wrong_dist[k] /= w_sum
        by_feature_combo[f'{manip}|{decoy}'] = {
            'n': len(ww),
            'weighted_mean_wrong': round(w_mean, 3),
            'weighted_first_try': round(w_ft, 3),
            'wrong_dist': {str(k): round(v, 3) for k, v in sorted(wrong_dist.items())},
        }

    # ── Intrinsic difficulty: position=0, lives=4 only ──
    baseline_obs = [o for o in observations if o['position'] == 0 and o['lives'] == 4]
    intrinsic = {}
    for axis in ['manipulation', 'abstraction', 'knowledge']:
        groups = defaultdict(lambda: {'wrongs': [], 'weights': []})
        for obs in baseline_obs:
            groups[obs[axis]]['wrongs'].append(obs['wrong'])
            groups[obs[axis]]['weights'].append(obs['weight'])
        result = {}
        for label, data in sorted(groups.items()):
            ww, wts = data['wrongs'], data['weights']
            w_sum = sum(wts)
            w_mean = sum(wts[i] * ww[i] for i in range(len(ww))) / w_sum if w_sum else 0
            w_ft = sum(wts[i] for i in range(len(ww)) if ww[i] == 0) / w_sum if w_sum else 0
            result[label] = {
                'n': len(ww),
                'weighted_mean_wrong': round(w_mean, 3),
                'weighted_first_try': round(w_ft, 3),
            }
        intrinsic[axis] = result

    # ── Global baseline (all rows, all positions) ──
    all_wrongs = [obs['wrong'] for obs in observations]
    all_weights = [obs['weight'] for obs in observations]
    global_w_sum = sum(all_weights)
    global_dist = defaultdict(float)
    for i in range(len(all_wrongs)):
        global_dist[all_wrongs[i]] += all_weights[i]
    for k in global_dist:
        global_dist[k] /= global_w_sum
    global_baseline = {
        'n': len(observations),
        'weighted_mean_wrong': round(sum(all_weights[i] * all_wrongs[i] for i in range(len(all_wrongs))) / global_w_sum, 3) if global_w_sum else 0,
        'wrong_dist': {str(k): round(v, 3) for k, v in sorted(global_dist.items())},
    }

    return {
        'by_position_lives': pos_lives_table,
        'by_pdl_feature': by_pdl,
        'by_decoy': by_decoy,
        'by_feature_combo': by_feature_combo,
        'global_baseline': global_baseline,
        'intrinsic_difficulty': intrinsic,
        'n_observations': len(observations),
    }


# ══════════════════════════════════════════════════════════════════════
#  B2: Correlated Failure Analysis
# ══════════════════════════════════════════════════════════════════════

def compute_correlated_failures(players_by_date, date_to_level, pdl_puzzle_features, pdl_rows):
    """Compute phi coefficients between row-pair failures per puzzle.

    For each puzzle date, build a binary matrix (player × row) where 1 = failed
    (either wrong guess in row or never attempted). Compute phi coefficient for
    all 6 row pairs (0-1, 0-2, 0-3, 1-2, 1-3, 2-3).

    Returns dict with:
      - 'per_puzzle': phi coefficients per puzzle
      - 'aggregate': mean phi by PDL similarity group
    """
    per_puzzle = {}
    all_pair_features = []  # for aggregation

    for d, pp in players_by_date.items():
        if d not in date_to_level:
            continue
        lid = date_to_level[d]
        if lid not in pdl_puzzle_features:
            continue

        # Build binary failure matrix: 1 = failed row (≥1 wrong guess or never attempted)
        rows_data = [pr for pr in pdl_rows if pr['lid'] == lid]
        if len(rows_data) < 4:
            continue

        row_positions = sorted(set(str(pr['row_position']) for pr in rows_data))[:4]
        row_pdl = {}
        for pr in rows_data:
            rp = str(pr['row_position'])
            if rp in row_positions:
                row_pdl[rp] = pr

        # Binary vectors per player
        failure_vectors = []
        for p in pp:
            if p['outcome'] not in ('WON', 'LOST'):
                continue
            vec = {}
            for rp in row_positions:
                row_guesses = [g for g in p['real_guesses'] if g['row'] == rp]
                if not row_guesses:
                    vec[rp] = 1  # never attempted = failed
                else:
                    had_wrong = any(not g['is_correct'] for g in row_guesses)
                    vec[rp] = 1 if had_wrong else 0
            failure_vectors.append(vec)

        if len(failure_vectors) < 10:
            continue

        # Compute phi coefficient for each row pair
        phi_matrix = {}
        for i in range(len(row_positions)):
            for j in range(i + 1, len(row_positions)):
                ri, rj = row_positions[i], row_positions[j]
                # 2x2 contingency table
                a = sum(1 for v in failure_vectors if v[ri] == 1 and v[rj] == 1)
                b = sum(1 for v in failure_vectors if v[ri] == 1 and v[rj] == 0)
                c = sum(1 for v in failure_vectors if v[ri] == 0 and v[rj] == 1)
                d_val = sum(1 for v in failure_vectors if v[ri] == 0 and v[rj] == 0)
                denom = math.sqrt((a+b) * (c+d_val) * (a+c) * (b+d_val))
                phi = (a * d_val - b * c) / denom if denom > 0 else 0
                pair_key = f'{ri}-{rj}'
                phi_matrix[pair_key] = round(phi, 3)

                # Feature similarity for this pair
                pri = row_pdl.get(ri, {})
                prj = row_pdl.get(rj, {})
                if pri and prj:
                    same_manip = pri.get('manipulation') == prj.get('manipulation')
                    same_abstr = pri.get('abstraction') == prj.get('abstraction')
                    same_know_dom = pri.get('knowledgeDomain') == prj.get('knowledgeDomain')
                    all_pair_features.append({
                        'phi': phi,
                        'same_manipulation': same_manip,
                        'same_abstraction': same_abstr,
                        'same_domain': same_know_dom,
                    })

        per_puzzle[d] = {
            'name': pdl_puzzle_features[lid]['name'],
            'phi_matrix': phi_matrix,
            'n_players': len(failure_vectors),
            'row_failure_rates': {
                rp: round(sum(v[rp] for v in failure_vectors) / len(failure_vectors), 3)
                for rp in row_positions
            },
            'row_categories': {
                rp: row_pdl[rp].get('category', f'Row {rp}')
                for rp in row_positions if rp in row_pdl
            },
        }

    # Aggregate: mean phi by feature similarity
    from .stats import safe_mean
    aggregate = {}
    for feature in ['same_manipulation', 'same_abstraction', 'same_domain']:
        yes_phis = [pf['phi'] for pf in all_pair_features if pf[feature]]
        no_phis = [pf['phi'] for pf in all_pair_features if not pf[feature]]
        aggregate[feature] = {
            'same': {'mean_phi': round(safe_mean(yes_phis), 3), 'n': len(yes_phis)},
            'different': {'mean_phi': round(safe_mean(no_phis), 3), 'n': len(no_phis)},
        }

    return {
        'per_puzzle': per_puzzle,
        'aggregate': aggregate,
        'n_pairs': len(all_pair_features),
    }


# ══════════════════════════════════════════════════════════════════════
#  C: Monte Carlo Simulator
# ══════════════════════════════════════════════════════════════════════

def build_per_puzzle_dists(players):
    """Build empirical wrong-guess distributions per solve position for one puzzle.

    Returns list of 5 dicts: [{wrong_count_str: probability}, ...]
      positions 0-3 (imposters) + position 4 (relink).

    Counts total lives consumed between consecutive row solves (not per-row
    wrongs), so that abandoned-row wrongs (from row switching) are captured.
    Also builds a per-puzzle relink wrong-guess distribution.
    """
    from collections import Counter
    pos_counts = [Counter() for _ in range(5)]  # 0-3 imposters, 4 relink
    pos_totals = [0] * 5

    for p in players:
        # -- Imposters phase: count wrongs between consecutive solves --
        sorted_rg = sorted(p.get('real_guesses', []), key=lambda g: g['ts'])
        wrongs_since_last_solve = 0
        solve_position = 0

        for g in sorted_rg:
            if solve_position >= 4:
                break  # all 4 rows solved
            if g['is_correct']:
                pos_counts[solve_position][wrongs_since_last_solve] += 1
                pos_totals[solve_position] += 1
                solve_position += 1
                wrongs_since_last_solve = 0
            else:
                wrongs_since_last_solve += 1

        # Death case: player died trying to solve position `solve_position`
        if solve_position < 4 and wrongs_since_last_solve > 0:
            pos_counts[solve_position][wrongs_since_last_solve] += 1
            pos_totals[solve_position] += 1

        # -- Relink phase --
        rt = p.get('relink_trajectory')
        if rt:
            pos_counts[4][rt['wrong_count']] += 1
            pos_totals[4] += 1

    dists = []
    for pos in range(5):
        total = pos_totals[pos]
        if total >= 5:  # minimum observations
            dist = {str(k): round(v / total, 4) for k, v in sorted(pos_counts[pos].items())}
            dists.append(dist)
        else:
            dists.append(None)
    return dists

def _sample_wrong_guesses(wrong_dist, rng_state):
    """Sample wrong guess count from weighted distribution using LCG RNG."""
    # Simple deterministic sampling using LCG
    rng_state[0] = (rng_state[0] * 1103515245 + 12345) & 0x7fffffff
    r = (rng_state[0] >> 16) / 32768.0
    cumulative = 0.0
    for k_str, prob in sorted(wrong_dist.items(), key=lambda x: int(x[0])):
        cumulative += prob
        if r <= cumulative:
            return int(k_str)
    # Fallback: return max k
    return max(int(k) for k in wrong_dist) if wrong_dist else 0


def _apply_ratio_shift(dist, ratio):
    """Shift a wrong_dist by a difficulty ratio using exponential reweighting.

    P(k) -> P(k) * ratio^k, then renormalize.
    ratio > 1.0 = harder (more wrongs), ratio < 1.0 = easier.
    Clamped to [0.5, 2.0] to prevent runaway adjustments.
    """
    ratio = max(0.5, min(2.0, ratio))
    if abs(ratio - 1.0) < 0.02:
        return dist  # negligible adjustment
    new_dist = {}
    total = 0
    for k_str, prob in dist.items():
        k = int(k_str)
        w = prob * (ratio ** k)
        new_dist[k_str] = w
        total += w
    if total > 0:
        for k_str in new_dist:
            new_dist[k_str] = round(new_dist[k_str] / total, 4)
    return new_dist


def _compute_feature_ratios(transition_probs):
    """Compute mean_wrong ratios per feature category relative to global baseline.

    Returns dict: {axis: {category: ratio}} for axes with sufficient data.
    ratio > 1.0 means harder than average, < 1.0 means easier.
    """
    MIN_N = 20
    global_mean = transition_probs.get('global_baseline', {}).get('weighted_mean_wrong', 0)
    if global_mean <= 0:
        return {}
    pdl_table = transition_probs.get('by_pdl_feature', {})
    ratios = {}
    for axis in ('abstraction', 'knowledge', 'same_domain'):
        axis_data = pdl_table.get(axis, {})
        axis_ratios = {}
        for cat, data in axis_data.items():
            if data.get('n', 0) >= MIN_N and data.get('weighted_mean_wrong') is not None:
                axis_ratios[cat] = data['weighted_mean_wrong'] / global_mean
        if axis_ratios:
            ratios[axis] = axis_ratios
    return ratios


def _compute_position_ratios(transition_probs):
    """Compute mean_wrong ratio per solve-position relative to global baseline.

    Aggregates across all lives states for each position, weighted by count.
    Returns dict: {position_int: ratio}.
    """
    global_mean = transition_probs.get('global_baseline', {}).get('weighted_mean_wrong', 0)
    if global_mean <= 0:
        return {}
    pos_lives = transition_probs.get('by_position_lives', {})
    pos_totals = defaultdict(float)  # weighted sum of mean_wrong
    pos_counts = defaultdict(int)
    for key, data in pos_lives.items():
        parts = key.split(',')
        if len(parts) != 2:
            continue
        pos = int(parts[0])
        if pos > 3:  # only imposters positions
            continue
        n = data.get('n', 0)
        if n > 0:
            pos_totals[pos] += data.get('weighted_mean_wrong', 0) * n
            pos_counts[pos] += n
    ratios = {}
    for pos in range(4):
        if pos_counts[pos] > 0:
            pos_mean = pos_totals[pos] / pos_counts[pos]
            ratios[pos] = pos_mean / global_mean
    return ratios


def predict_row_dist(row_pdl, has_decoy, transition_probs, position=None):
    """Predict wrong-guess distribution for a row based on all PDL features.

    Starts from a manipulation+decoy base distribution, then applies
    multiplicative ratio-shift adjustments for abstraction, knowledge,
    same_domain, and position.

    Returns dict {wrong_count_str: probability}.
    """
    MIN_N = 20
    combo_table = transition_probs.get('by_feature_combo', {})
    pdl_table = transition_probs.get('by_pdl_feature', {})
    baseline = transition_probs.get('global_baseline', {})

    manip = row_pdl.get('manipulation', 'None')

    # Step 1: Get base distribution from manipulation+decoy
    dist = None
    combo_key = f'{manip}|{has_decoy}'
    combo = combo_table.get(combo_key)
    if combo and combo.get('n', 0) >= MIN_N:
        dist = dict(combo['wrong_dist'])
    else:
        manip_data = pdl_table.get('manipulation', {}).get(manip)
        if manip_data and manip_data.get('n', 0) >= MIN_N:
            dist = dict(manip_data['wrong_dist'])
            if has_decoy:
                dist = _apply_decoy_shift(dist, transition_probs)
        else:
            dist = dict(baseline.get('wrong_dist', {'0': 0.65, '1': 0.2, '2': 0.1, '3': 0.05}))
            if has_decoy:
                dist = _apply_decoy_shift(dist, transition_probs)

    # Step 2: Apply feature ratio-shift adjustments
    feature_ratios = _compute_feature_ratios(transition_probs)

    # Abstraction adjustment
    abstr = row_pdl.get('abstraction', 'Direct membership')
    abstr_ratios = feature_ratios.get('abstraction', {})
    if abstr in abstr_ratios:
        dist = _apply_ratio_shift(dist, abstr_ratios[abstr])

    # Knowledge adjustment
    know = row_pdl.get('knowledge', 'General vocabulary')
    know_ratios = feature_ratios.get('knowledge', {})
    if know in know_ratios:
        dist = _apply_ratio_shift(dist, know_ratios[know])

    # Same-domain adjustment
    same_dom = str(row_pdl.get('same_domain', False))
    sd_ratios = feature_ratios.get('same_domain', {})
    if same_dom in sd_ratios:
        dist = _apply_ratio_shift(dist, sd_ratios[same_dom])

    # Step 3: Apply position adjustment
    if position is not None:
        pos_ratios = _compute_position_ratios(transition_probs)
        if position in pos_ratios:
            dist = _apply_ratio_shift(dist, pos_ratios[position])

    return dist


def _apply_decoy_shift(dist, transition_probs):
    """Shift a wrong_dist harder based on the decoy effect ratio.

    Uses the ratio of decoy vs non-decoy mean_wrong to redistribute
    probability mass from 0-wrong toward higher wrong counts.
    """
    by_decoy = transition_probs.get('by_decoy', {})
    no_decoy = by_decoy.get('False', {})
    yes_decoy = by_decoy.get('True', {})
    nd_mean = no_decoy.get('weighted_mean_wrong', 0.5)
    yd_mean = yes_decoy.get('weighted_mean_wrong', 0.6)
    if nd_mean <= 0:
        return dist

    # Ratio of how much harder decoy rows are
    ratio = yd_mean / nd_mean  # e.g. 1.48

    # Reweight: multiply P(wrong=k) by ratio^k, then renormalise
    new_dist = {}
    total = 0
    for k_str, prob in dist.items():
        k = int(k_str)
        w = prob * (ratio ** k)
        new_dist[k_str] = w
        total += w
    if total > 0:
        for k_str in new_dist:
            new_dist[k_str] = round(new_dist[k_str] / total, 4)
    return new_dist


def simulate_puzzle(transition_probs, pdl_rows_for_puzzle, puzzle_features,
                    n_sims=10000, seed=42, per_puzzle_obs=None,
                    relink_feature_dists=None):
    """Monte Carlo simulator for a single Relink puzzle.

    For each simulated player:
    1. Start with 4 lives
    2. Attempt rows sorted easiest-first (modelling player strategy)
    3. For each row, sample wrong_guesses from:
       a. per_puzzle_obs (empirical, for dated puzzles), or
       b. predict_row_dist() (feature-based with all PDL adjustments)
    4. Deduct lives. If lives <= 0: LOST.
    5. Survivors enter relink phase.

    per_puzzle_obs: list of per-position wrong-guess distributions for this puzzle.
      Each is a dict {wrong_count: probability}. If None, uses feature-based model.
    relink_feature_dists: dict with keys 'by_con_manip', 'by_id_manip',
      'by_con_knowledge', 'by_tiles' — each mapping category to wrong_dist.
      Used for feature-based relink prediction when per_puzzle_obs unavailable.
    """
    from .stats import safe_mean

    pos_lives_table = transition_probs['by_position_lives']

    # Build relink distribution from pos=4 data (if available)
    relink_dists = {}
    for key, data in pos_lives_table.items():
        parts = key.split(',')
        if len(parts) == 2 and parts[0] == '4':
            relink_dists[int(parts[1])] = data.get('wrong_dist', {'0': 1.0})

    # Build decoy set for this puzzle
    decoy_tile_ids = set()
    for dec in puzzle_features.get('decoys', []):
        for tid in dec.get('tileIds', []):
            decoy_tile_ids.add(tid)

    # For each row, determine its wrong-guess distribution
    row_dists = []
    for row in pdl_rows_for_puzzle:
        has_decoy = any(tid in decoy_tile_ids for tid in row.get('tile_ids', []))
        if per_puzzle_obs:
            # Use empirical per-position dists (mapped by solve order)
            row_dists.append({
                'row': row,
                'has_decoy': has_decoy,
                'dist': None,  # will use per_puzzle_obs by position
            })
        else:
            # Feature-based prediction (position applied after sorting)
            dist = predict_row_dist(row, has_decoy, transition_probs, position=None)
            row_dists.append({
                'row': row,
                'has_decoy': has_decoy,
                'dist': dist,
            })

    # Sort rows by predicted difficulty (easiest first) for undated puzzles.
    # For dated puzzles with per_puzzle_obs, keep original position order.
    if not per_puzzle_obs:
        def _row_difficulty(rd):
            d = rd['dist']
            return sum(int(k) * v for k, v in d.items())  # expected wrong guesses
        row_dists.sort(key=_row_difficulty)
        # Re-apply position adjustments now that solve order is known
        pos_ratios = _compute_position_ratios(transition_probs)
        for pos, rd in enumerate(row_dists):
            if pos in pos_ratios:
                rd['dist'] = _apply_ratio_shift(rd['dist'], pos_ratios[pos])

    # Capture the feature-based input distributions for each row (pre-sampling)
    predicted_row_dists = []
    for pos, rd in enumerate(row_dists):
        if rd['dist']:
            predicted_row_dists.append({k: round(v, 4) for k, v in rd['dist'].items()})
        else:
            predicted_row_dists.append(None)

    # Build the relink feature-based distribution (same logic as in the sim loop,
    # but captured once before sampling for output)
    predicted_relink_dist = None
    if relink_feature_dists:
        con_manip = puzzle_features.get('relink_con_manipulation', 'None')
        by_cm = relink_feature_dists.get('by_con_manip', {})
        base_entry = by_cm.get(con_manip)
        if base_entry and base_entry.get('dist'):
            predicted_relink_dist = dict(base_entry['dist'])
            gl = relink_feature_dists.get('global', {})
            gl_mean = gl.get('mean_wrong', 0)
            if gl_mean > 0:
                id_manip = puzzle_features.get('relink_id_manipulation', 'None')
                id_entry = relink_feature_dists.get('by_id_manip', {}).get(id_manip)
                if id_entry and id_entry.get('mean_wrong') is not None:
                    predicted_relink_dist = _apply_ratio_shift(predicted_relink_dist, id_entry['mean_wrong'] / gl_mean)
                con_know = puzzle_features.get('relink_con_knowledge', 'None')
                ck_entry = relink_feature_dists.get('by_con_knowledge', {}).get(con_know)
                if ck_entry and ck_entry.get('mean_wrong') is not None:
                    predicted_relink_dist = _apply_ratio_shift(predicted_relink_dist, ck_entry['mean_wrong'] / gl_mean)
                tiles = str(puzzle_features.get('phase2TileCount', 1))
                t_entry = relink_feature_dists.get('by_tiles', {}).get(tiles)
                if t_entry and t_entry.get('mean_wrong') is not None:
                    predicted_relink_dist = _apply_ratio_shift(predicted_relink_dist, t_entry['mean_wrong'] / gl_mean)

    rng = [seed]
    results = {
        'rows_completed': [0] * 5,
        'won': 0,
        'lost': 0,
        'lives_at_end': [],
        'relink_reached': 0,
    }

    # Per-row simulated wrong-guess tallies, split by outcome:
    #   sim_row_solved[pos][wrong_count] = count of sims where row was solved with N wrongs
    #   sim_row_lost[pos][wrong_count] = count of sims where player died on this row
    sim_row_solved = [defaultdict(int) for _ in range(5)]   # 0-3 imposters, 4 relink
    sim_row_lost = [defaultdict(int) for _ in range(5)]
    sim_row_no_attempt = [0] * 5  # count of sims where row was never reached
    # Total mistakes per sim
    sim_mistake_counts = defaultdict(int)

    for _ in range(n_sims):
        lives = 4
        rows_done = 0
        total_wrongs = 0
        death_pos = -1  # track which row killed the player

        for pos, rd in enumerate(row_dists):
            dist = None

            # For dated puzzles, use per-puzzle empirical distributions
            if per_puzzle_obs and pos < len(per_puzzle_obs):
                dist = per_puzzle_obs[pos]

            # For undated (or if per_puzzle_obs missing for this position),
            # use the feature-based distribution
            if not dist:
                dist = rd['dist']

            # Final fallback: pooled (position, lives)
            if not dist:
                key = f'{pos},{lives}'
                dist = pos_lives_table.get(key, {}).get('wrong_dist')
            if not dist:
                dist = {'0': 0.65, '1': 0.2, '2': 0.1, '3': 0.05}

            wrong = _sample_wrong_guesses(dist, rng)
            wrong = min(wrong, lives)  # can't lose more lives than you have
            total_wrongs += wrong
            lives -= wrong
            if lives <= 0:
                # Player died on this row
                death_pos = pos
                sim_row_lost[pos][wrong] += 1
                # Mark remaining rows as not attempted
                for remaining in range(pos + 1, 4):
                    sim_row_no_attempt[remaining] += 1
                sim_row_no_attempt[4] += 1  # relink not reached
                break
            # Survived this row
            sim_row_solved[pos][wrong] += 1
            rows_done += 1

        if rows_done == 4 and lives > 0:
            # Relink phase
            results['relink_reached'] += 1

            # Prefer per-puzzle relink distribution (captures puzzle-specific
            # difficulty); fall back to feature-based prediction, then pooled.
            rl_dist = None
            if per_puzzle_obs and len(per_puzzle_obs) > 4 and per_puzzle_obs[4]:
                rl_dist = per_puzzle_obs[4]
            if not rl_dist and relink_feature_dists:
                con_manip = puzzle_features.get('relink_con_manipulation', 'None')
                by_cm = relink_feature_dists.get('by_con_manip', {})
                base_entry = by_cm.get(con_manip)
                if base_entry and base_entry.get('dist'):
                    rl_dist = dict(base_entry['dist'])
                    gl = relink_feature_dists.get('global', {})
                    gl_mean = gl.get('mean_wrong', 0)
                    if gl_mean > 0:
                        id_manip = puzzle_features.get('relink_id_manipulation', 'None')
                        id_entry = relink_feature_dists.get('by_id_manip', {}).get(id_manip)
                        if id_entry and id_entry.get('mean_wrong') is not None:
                            rl_dist = _apply_ratio_shift(rl_dist, id_entry['mean_wrong'] / gl_mean)
                        con_know = puzzle_features.get('relink_con_knowledge', 'None')
                        ck_entry = relink_feature_dists.get('by_con_knowledge', {}).get(con_know)
                        if ck_entry and ck_entry.get('mean_wrong') is not None:
                            rl_dist = _apply_ratio_shift(rl_dist, ck_entry['mean_wrong'] / gl_mean)
                        tiles = str(puzzle_features.get('phase2TileCount', 1))
                        t_entry = relink_feature_dists.get('by_tiles', {}).get(tiles)
                        if t_entry and t_entry.get('mean_wrong') is not None:
                            rl_dist = _apply_ratio_shift(rl_dist, t_entry['mean_wrong'] / gl_mean)
            if not rl_dist:
                rl_dist = relink_dists.get(lives)
            if not rl_dist:
                for l in range(4, 0, -1):
                    rl_dist = relink_dists.get(l)
                    if rl_dist:
                        break
            if not rl_dist:
                rl_dist = {'0': 0.85, '1': 0.1, '2': 0.05}
            rl_wrong = _sample_wrong_guesses(rl_dist, rng)
            rl_wrong = min(rl_wrong, lives)  # can't lose more lives than you have
            total_wrongs += rl_wrong
            lives -= rl_wrong
            if lives > 0:
                sim_row_solved[4][rl_wrong] += 1
                results['won'] += 1
                results['lives_at_end'].append(lives)
            else:
                sim_row_lost[4][rl_wrong] += 1
                results['lost'] += 1
        else:
            results['lost'] += 1

        sim_mistake_counts[total_wrongs] += 1
        results['rows_completed'][min(rows_done, 4)] += 1

    results['solve_rate'] = round(results['won'] / n_sims, 4)
    results['n_sims'] = n_sims
    results['rows_completed_pct'] = [round(c / n_sims * 100, 1) for c in results['rows_completed']]
    results['mean_lives_at_win'] = round(safe_mean(results['lives_at_end']), 2) if results['lives_at_end'] else 0
    del results['lives_at_end']

    # Per-row simulated wrong-guess distributions with outcome split
    # Uses compound keys matching actual data: '0_solved', '1_lost', etc.
    results['sim_row_dists'] = {}
    for pos in range(5):
        d = {}
        all_wrongs = set(sim_row_solved[pos].keys()) | set(sim_row_lost[pos].keys())
        for w in sorted(all_wrongs):
            if sim_row_solved[pos][w]:
                d[f'{w}_solved'] = sim_row_solved[pos][w]
            if sim_row_lost[pos][w]:
                d[f'{w}_lost'] = sim_row_lost[pos][w]
        d['no_attempt_lost'] = sim_row_no_attempt[pos]
        results['sim_row_dists'][str(pos)] = d

    # Total mistakes distribution (count format)
    results['sim_mistake_dist'] = {str(k): v for k, v in sorted(sim_mistake_counts.items())}

    # Feature-based predicted distributions (probability format)
    results['predicted_row_dists'] = predicted_row_dists
    results['predicted_relink_dist'] = (
        {k: round(v, 4) for k, v in predicted_relink_dist.items()}
        if predicted_relink_dist else None)

    # Row labels (from PDL) to identify which row is which in sorted order
    results['row_labels'] = [rd['row'].get('category', f'Row {i}') for i, rd in enumerate(row_dists)]

    return results
