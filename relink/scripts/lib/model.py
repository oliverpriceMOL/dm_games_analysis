"""Model layer — IPW weights, transition probabilities, game simulator."""

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
