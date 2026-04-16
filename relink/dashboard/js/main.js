/**
 * Dashboard router. Hash-based navigation with lazy JSON loading.
 * Each page only fetches the JSON files it needs on first visit.
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
import * as transitions from './transitions.js';
import * as failures from './failures.js';
import * as simulator from './simulator.js';
import * as glossary from './glossary.js';
import * as explorer from './explorer.js';

const DATA_DIR = '../outputs/data';

/* ── Page configuration ─────────────────────────────────────────── */

const PAGE_CONFIG = {
    overview: {
        files: ['overview', 'regression', 'simulator'],
        render(d) {
            overview.render(d.overview, d.regression, d.simulator);
        }
    },
    difficulty: {
        files: ['crosstabs', 'heatmap', 'impostor-domain', 'correlations', 'regression'],
        render(d) {
            crosstabs.render(d.crosstabs);
            renderHeatmap(d.heatmap);
            renderImpostorDomain(d.impostorDomain);
            correlations.render(d.correlations);
            regression.render(d.regression);
        }
    },
    behaviour: {
        files: ['vertical', 'decoys'],
        render(d) {
            vertical.render(d.vertical);
            decoys.render(d.decoys);
        }
    },
    relink: {
        files: ['relink'],
        render(d) { relinkPhase.render(d.relink); }
    },
    model: {
        files: ['transitions', 'failures'],
        render(d) {
            transitions.render(d.transitions);
            failures.render(d.failures);
        }
    },
    simulator: {
        files: ['simulator'],
        render(d) { simulator.render(d.simulator); }
    },
    clustering: {
        files: ['clustering'],
        render(d) { clustering.render(d.clustering); }
    },
    explorer: {
        files: ['puzzle-explorer'],
        render(d) { explorer.render(d); }
    },
    glossary: {
        files: [],
        render() {
            glossary.render(document.getElementById('glossary-content'));
        }
    }
};

const DEFAULT_PAGE = 'overview';

/* ── Data cache ─────────────────────────────────────────────────── */

const dataCache = {};          // filename → parsed JSON
const renderedPages = new Set(); // pages already rendered

function toCamelCase(name) {
    return name.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
}

async function fetchFiles(fileNames) {
    const missing = fileNames.filter(f => !(toCamelCase(f) in dataCache));
    if (missing.length) {
        const results = await Promise.all(
            missing.map(f => fetch(`${DATA_DIR}/${f}.json`).then(r => {
                if (!r.ok) throw new Error(`Failed to load ${f}.json: ${r.status}`);
                return r.json();
            }))
        );
        missing.forEach((f, i) => { dataCache[toCamelCase(f)] = results[i]; });
    }
    return dataCache;
}

/* ── Navigation ─────────────────────────────────────────────────── */

function getPageFromHash() {
    const hash = location.hash.replace('#', '');
    return (hash && hash in PAGE_CONFIG) ? hash : DEFAULT_PAGE;
}

async function navigate(pageName) {
    const config = PAGE_CONFIG[pageName];
    if (!config) { pageName = DEFAULT_PAGE; }

    const loadingEl = document.getElementById('loading');

    // Hide all pages
    document.querySelectorAll('.page').forEach(p => { p.style.display = 'none'; });

    // Highlight active nav link
    document.querySelectorAll('nav a').forEach(a => {
        a.classList.toggle('active', a.dataset.page === pageName);
    });

    // Close mobile nav if open
    document.body.classList.remove('nav-open');

    // Show target page
    const pageEl = document.getElementById(`page-${pageName}`);
    if (!pageEl) return;

    // Fetch data & render if first visit
    if (!renderedPages.has(pageName)) {
        const cfg = PAGE_CONFIG[pageName];
        try {
            if (cfg.files.length) {
                loadingEl.style.display = 'block';
            }
            const data = await fetchFiles(cfg.files);
            cfg.render(data);
            renderedPages.add(pageName);
        } catch (err) {
            loadingEl.textContent = `Error loading data: ${err.message}`;
            loadingEl.classList.add('error');
            console.error(err);
            return;
        }
    }

    loadingEl.style.display = 'none';
    pageEl.style.display = 'block';

    // Scroll to top of page
    window.scrollTo(0, 0);

    // Trigger resize so Chart.js canvases recalculate dimensions
    window.dispatchEvent(new Event('resize'));
}

/* ── Back-to-top button ─────────────────────────────────────────── */

function initBackToTop() {
    const btn = document.getElementById('back-to-top');
    if (!btn) return;
    window.addEventListener('scroll', () => {
        btn.style.display = window.scrollY > 200 ? 'block' : 'none';
    });
    btn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
}

/* ── Hamburger menu ─────────────────────────────────────────────── */

function initHamburger() {
    const btn = document.getElementById('hamburger');
    const overlay = document.getElementById('nav-overlay');
    if (!btn) return;
    btn.addEventListener('click', () => {
        document.body.classList.toggle('nav-open');
    });
    if (overlay) {
        overlay.addEventListener('click', () => {
            document.body.classList.remove('nav-open');
        });
    }
    // Close nav when a link is clicked (mobile)
    document.querySelectorAll('nav a').forEach(a => {
        a.addEventListener('click', () => {
            document.body.classList.remove('nav-open');
        });
    });
}

/* ── Init ────────────────────────────────────────────────────────── */

window.addEventListener('hashchange', () => navigate(getPageFromHash()));

initBackToTop();
initHamburger();
navigate(getPageFromHash());
