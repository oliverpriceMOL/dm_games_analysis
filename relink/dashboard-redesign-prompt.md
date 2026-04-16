# Dashboard Redesign — Prompt for New Chat

Paste this into a fresh Copilot chat session:

---

## Task

Redesign the Relink analysis dashboard (`relink/dashboard/`) from a single long scrolling page into a properly structured multi-page dashboard with logical groupings, dynamic navigation, and a glossary.

## Current State

The dashboard is a single `index.html` with 13 sections stacked vertically. It's an absurdly long scroll. All 13 JSON data files are loaded at once. Each section has its own JS renderer module in `dashboard/js/`. Chart.js v4 is loaded via CDN.

**Current 13 sections (in order):**
1. Key Findings (overview stats grid)
2. PDL Cross-tabs (4 bar charts by PDL axis)  
3. Difficulty Heatmap (manipulation × abstraction grid)
4. Impostor Domain (same vs different domain comparison)
5. Puzzle Correlations (6 scatter plots)
6. Regression Models (OLS coefficients + forest plot)
7. Vertical Inference (learning curves by position)
8. Decoy Analysis (decoy vs no-decoy comparison + hit rates)
9. Relink Phase (phase 2 by identification, construction, tiles)
10. Clustering (puzzle + row archetypes)
11. Transition Model (position×lives heatmap + PDL distributions)
12. Correlated Failures (phi coefficient matrices)
13. Game Simulator (predicted vs actual + undated predictions)

## Requirements

### Multi-Page Structure

Replace the single scroll with a **tabbed or routed page system** (hash routing is fine — no build tools). Suggested page grouping:

- **Overview** — Key Findings + headline simulator validation. The landing page.
- **Difficulty Drivers** — Cross-tabs, Heatmap, Impostor Domain, Correlations, Regression. All the "what makes puzzles hard?" analyses.
- **Player Behaviour** — Vertical Inference, Decoy Analysis. How players learn and get tricked.
- **Relink Phase** — Relink Phase analysis (phase 2 specific).
- **Statistical Model** — Transition Model, Correlated Failures. The IPW-weighted probability model.
- **Simulator** — Game Simulator results, predictions for undated puzzles.
- **Clustering** — Puzzle and row archetypes.
- **Glossary** — Definitions of all key terms (see below).

These groupings can be adjusted if you think a different arrangement makes more sense — the key constraint is that related analyses should be together and it should be easy to navigate.

### Navigation

- Persistent sidebar or top nav with page links
- Current page highlighted
- Each page should have a brief intro paragraph explaining what the section covers and why it matters
- Breadcrumb or back-to-top for long pages

### Dynamic & Interactive

- Only load JSON files needed for the current page (lazy loading)
- Smooth transitions between pages
- Charts should resize properly when page changes
- Consider collapsible sections within pages for dense content (e.g., the per-puzzle detail table in Vertical Inference)

### Glossary Page

Create a glossary page with simple, non-technical explanations of all key terms used across the dashboard. At minimum:

**Game Terms:**
- Impostor, Relink phase, Row, Tile, Lives, Solve rate, First-try rate
- Wrong guess, Phase 1 / Phase 2

**PDL Terms:**
- PDL (Puzzle Design Language), Manipulation, Abstraction, Knowledge, Knowledge Domain
- Connection Identification, Answer Construction
- Same-domain impostor, Decoy grouping

**Statistical Terms:**
- IPW (Inverse Probability Weighting), Survivorship bias
- Transition probability, Wrong-guess distribution
- Pearson r, Spearman ρ, Phi coefficient (φ)
- OLS regression, R², LOO (leave-one-out) cross-validation, MAE
- Ratio-shift model, Monte Carlo simulation

**Analysis Terms:**
- Vertical inference, Transparency score, Centre of mass (CoM)
- Cluster / archetype, Feature combo
- Pairwise ordering accuracy

Each term should have a 1-2 sentence plain-English explanation. Use analogies where helpful. Link to the relevant dashboard page where the term appears.

### Design

- Keep the existing dark theme and card-based layout
- Improve visual hierarchy within pages (section headers, spacing, dividers)
- The current CSS file is `dashboard/css/styles.css` — extend it rather than replacing
- Keep Chart.js v4 via CDN (no build step)
- Keep ES modules for all JS

### Constraints

- **No build tools** — this is a static site served via `python3 -m http.server`
- **No external JS dependencies** beyond Chart.js v4 CDN
- Keep all existing renderer modules working (they export `render(data)` functions)
- The 13 JSON files in `outputs/data/` are the data source — don't modify the Python pipeline
- Read the full documentation in `relink/docs/` (6 files: 00-overview.md through 05-dashboard.md) before starting — they explain every analysis in detail

### Files to Modify/Create

- `dashboard/index.html` — restructure into multi-page layout
- `dashboard/js/main.js` — add routing, lazy loading, page dispatch
- `dashboard/js/glossary.js` — new renderer for glossary page
- `dashboard/css/styles.css` — extend with page/nav styles
- Existing `dashboard/js/*.js` renderers should need minimal changes (just ensure they work when called on page navigation)

---
