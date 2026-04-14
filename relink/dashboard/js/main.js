/**
 * Dashboard entry point. Fetches JSON data files and dispatches to section renderers.
 */

import * as overview from './overview.js';
import * as crosstabs from './crosstabs.js';
import { renderHeatmap, renderImpostorDomain } from './heatmap.js';
import * as correlations from './correlations.js';
import * as regression from './regression.js';
import * as vertical from './vertical.js';
import * as decoys from './decoys.js';
import * as relinkPhase from './relink.js';
import * as clustering from './clustering.js';
import * as predictions from './predictions.js';
import * as transitions from './transitions.js';
import * as failures from './failures.js';
import * as simulator from './simulator.js';

const DATA_DIR = '../outputs/data';

const FILES = [
    'overview', 'crosstabs', 'heatmap', 'impostor-domain',
    'correlations', 'regression', 'vertical', 'decoys',
    'relink', 'clustering', 'predictions',
    'transitions', 'failures', 'simulator'
];

async function loadData() {
    const data = {};
    const results = await Promise.all(
        FILES.map(f => fetch(`${DATA_DIR}/${f}.json`).then(r => {
            if (!r.ok) throw new Error(`Failed to load ${f}.json: ${r.status}`);
            return r.json();
        }))
    );
    FILES.forEach((f, i) => {
        // Normalise key: 'impostor-domain' → 'impostorDomain'
        const key = f.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
        data[key] = results[i];
    });
    return data;
}

async function main() {
    const loadingEl = document.getElementById('loading');
    const contentEl = document.getElementById('content');

    try {
        const data = await loadData();

        // Hide loading, show content
        loadingEl.style.display = 'none';
        contentEl.style.display = 'block';

        // Render each section
        overview.render(data.overview, data.regression, data.predictions);
        crosstabs.render(data.crosstabs);
        renderHeatmap(data.heatmap);
        renderImpostorDomain(data.impostorDomain);
        correlations.render(data.correlations);
        regression.render(data.regression);
        vertical.render(data.vertical);
        decoys.render(data.decoys);
        relinkPhase.render(data.relink);
        clustering.render(data.clustering);
        predictions.render(data.predictions, data.clustering);
        transitions.render(data.transitions);
        failures.render(data.failures);
        simulator.render(data.simulator);

        // Nav highlighting
        document.querySelectorAll('nav a').forEach(link => {
            link.addEventListener('click', () => {
                document.querySelectorAll('nav a').forEach(l => l.classList.remove('active'));
                link.classList.add('active');
            });
        });

    } catch (err) {
        loadingEl.textContent = `Error loading data: ${err.message}`;
        loadingEl.classList.add('error');
        console.error(err);
    }
}

main();
