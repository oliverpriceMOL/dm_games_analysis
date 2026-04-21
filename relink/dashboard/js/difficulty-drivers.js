/**
 * Difficulty Drivers page — orchestrates 7 sub-sections:
 * 1. PDL Cross-Tabs (crosstabs)
 * 2. Manipulation × Abstraction Heatmap
 * 3. Impostor Domain Analysis
 * 4. Puzzle-Level Correlations
 * 5. Regression Models
 * 6. Vertical Inference
 * 7. Decoy Analysis
 *
 * Reuses the existing renderer modules directly.
 */

import * as crosstabs from './crosstabs.js';
import { renderHeatmap, renderImpostorDomain } from './heatmap.js';
import * as correlations from './correlations.js';
import * as regression from './regression.js';
import * as vertical from './vertical.js';
import * as decoys from './decoys.js';

export function render(data) {
    crosstabs.render(data.crosstabs);
    renderHeatmap(data.heatmap);
    renderImpostorDomain(data.impostorDomain);
    correlations.render(data.correlations);
    regression.render(data.regression);
    vertical.render(data.vertical);
    decoys.render(data.decoys);
}
