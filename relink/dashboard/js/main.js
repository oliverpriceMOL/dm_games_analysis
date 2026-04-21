/**
 * Dashboard router. Hash-based navigation with lazy JSON loading.
 * 7 pages: Overview, Published, Upcoming, Difficulty, Relink, Validation, Glossary.
 */

import * as overview from './overview.js';
import * as published from './published.js';
import * as upcoming from './upcoming.js';
import * as difficultyDrivers from './difficulty-drivers.js';
import * as relinkPhase from './relink.js';
import * as validation from './validation.js';
import * as glossary from './glossary.js';

const DATA_DIR = '../outputs/data';

/* ── Page configuration ─────────────────────────────────────────── */

const PAGE_CONFIG = {
    overview: {
        files: ['overview'],
        render(d) { overview.render(d.overview); }
    },
    published: {
        files: ['puzzle-explorer', 'difficulty'],
        render(d) { published.render(d.puzzleExplorer, d.difficulty); }
    },
    upcoming: {
        files: ['puzzle-explorer', 'difficulty', 'simulator'],
        render(d) { upcoming.render(d.puzzleExplorer, d.difficulty, d.simulator); }
    },
    difficulty: {
        files: ['crosstabs', 'heatmap', 'impostor-domain', 'correlations', 'regression', 'vertical', 'decoys'],
        render(d) { difficultyDrivers.render(d); }
    },
    relink: {
        files: ['relink'],
        render(d) { relinkPhase.render(d.relink); }
    },
    validation: {
        files: ['simulator', 'transitions', 'failures', 'clustering'],
        render(d) { validation.render(d); }
    },
    glossary: {
        files: [],
        render() { glossary.render(document.getElementById('glossary-content')); }
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
