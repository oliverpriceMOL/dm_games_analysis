# 05 — The Dashboard

> **Directory:** `relink/dashboard/`
> **Entry point:** `dashboard/index.html`
> **Data source:** 15 JSON files in `relink/outputs/data/`
> **Technology:** Chart.js v4 (CDN), vanilla JS ES modules

## Architecture

```
Browser loads index.html
       │
       ├── Chart.js v4 (via CDN, global <script>)
       │
       └── js/main.js (ES module entry point)
              │
              ├── Hash-based routing (#overview, #difficulty, etc.)
              │
              ├── Lazy-loads JSON files per page on first visit
              │
              └── Calls render functions for the active page
                  (each page groups 1-5 analysis sections)
```

### Why Two Script Loading Strategies?

- **Chart.js** is loaded as a traditional `<script>` tag from CDN. It attaches itself to the global `Chart` object.
- **Dashboard code** uses ES modules (`import`/`export`). Each section has its own `.js` file that exports a `render()` function.

This hybrid approach means Chart.js is available globally to all renderer modules without needing to pass it around.

---

## Data Loading (`main.js`)

The dashboard uses hash-based routing with lazy JSON loading. Each page only fetches the JSON files it needs on first visit. A `PAGE_CONFIG` object maps page names to their required files and render functions:

```javascript
const PAGE_CONFIG = {
    overview:   { files: ['overview'], ... },
    published:  { files: ['puzzle-explorer', 'difficulty'], ... },
    upcoming:   { files: ['puzzle-explorer', 'difficulty', 'simulator'], ... },
    difficulty: { files: ['crosstabs', 'heatmap', 'impostor-domain', 'correlations', 'regression', 'vertical', 'decoys'], ... },
    relink:     { files: ['relink'], ... },
    validation: { files: ['simulator', 'transitions', 'failures', 'clustering'], ... },
    glossary:   { files: [], ... }
};
```

File names are normalised to camelCase keys (e.g. `impostor-domain` → `impostorDomain`, `puzzle-explorer` → `puzzleExplorer`) so renderers can access them cleanly. Previously-loaded data is cached in memory — navigating back to an already-visited page reuses the cached data without re-fetching.

---

## The 7 Pages

Each page is rendered by one or more dedicated JS modules and groups related analyses together.

### 1. Overview (`overview.js`)
**Page:** `#overview`
**Data:** `overview.json`

Renders headline stat cards (total puzzles, completions, solve rate range) and a per-date summary table with solve rates. This is the landing page.

### 2. Published Puzzles (`published.js`)
**Page:** `#published`
**Data:** `puzzle-explorer.json`, `difficulty.json`

A sortable table of all dated (published) puzzles showing:
- Date, name, player count, solve rate, difficulty stars
- Row-click opens a modal detail panel with per-row wrong-guess distributions (compound key bars: solved/lost split), timing curves, PDL feature summary, and simulator predictions
- Toggle between Actual and Predicted (simulator) distributions

### 3. Upcoming Puzzles (`upcoming.js`)
**Page:** `#upcoming`
**Data:** `puzzle-explorer.json`, `difficulty.json`, `simulator.json`

A sortable table of undated (unpublished) puzzles showing:
- Name, publish date, predicted solve rate, difficulty stars
- Row-click opens the same modal detail panel as Published (but only predicted distributions available)

### 4. Difficulty Drivers (`difficulty-drivers.js`)
**Page:** `#difficulty`
**Data:** `crosstabs.json`, `heatmap.json`, `impostor-domain.json`, `correlations.json`, `regression.json`, `vertical.json`, `decoys.json`

Multi-section page combining all difficulty-related analyses:
- **Cross-tabs:** Four horizontal bar charts (one per PDL axis) showing first-try % by category
- **Heatmap:** Manipulation × abstraction 2D grid (green=easy, red=hard)
- **Impostor Domain:** Same vs different domain comparison
- **Correlations:** Six scatter plots (feature vs solve rate with Pearson r)
- **Regression:** OLS coefficient tables + forest plot
- **Vertical Inference:** Position timing/error curves showing learning within a game
- **Decoys:** Decoy presence effect on solve rate

### 5. Relink Phase (`relink.js`)
**Page:** `#relink`
**Data:** `relink.json`

Three bar charts analysing Phase 2 (the relink phase):
- First-try % by connection identification manipulation
- First-try % by answer construction manipulation
- First-try % and solve rate by phase 2 tile count

### 6. Validation (`validation.js`)
**Page:** `#validation`
**Data:** `simulator.json`, `transitions.json`, `failures.json`, `clustering.json`

Multi-section page combining model validation analyses:
- **Simulator:** Scatter plot (simulated vs actual), stacked bar distributions, undated predictions table
- **Transitions:** Position × Lives heatmap, per-PDL-axis IPW-weighted distributions
- **Correlated Failures:** Mean phi by feature similarity, per-puzzle phi matrices
- **Clustering:** Puzzle archetypes (k=3) and row archetypes (k=4)

### 7. Glossary (`glossary.js`)
**Page:** `#glossary`
**Data:** None (static content)

Defines key terms used throughout the dashboard (PDL axes, game mechanics, statistical measures). Rendered as a searchable definition list.

---

## Page Layout

```
┌──────────┬───────────────────────────────────────────┐
│          │                                           │
│   NAV    │            MAIN CONTENT                   │
│          │                                           │
│  Fixed   │   Shows one page at a time (hash routing) │
│  sidebar │                                           │
│          │   Pages:                                  │
│  Links   │   #overview   — Headline Stats            │
│  to 7    │   #published  — Published Puzzles table   │
│  pages   │   #upcoming   — Upcoming Puzzles table    │
│          │   #difficulty — Difficulty Drivers         │
│          │   #relink     — Relink Phase              │
│          │   #validation — Model Validation          │
│          │   #glossary   — Glossary                  │
│          │                                           │
└──────────┴───────────────────────────────────────────┘
```

Sections use a `.two-col` CSS grid layout for side-by-side cards, with `.card` containers wrapping each chart or table.

---

## Shared Chart Utilities (`charts.js`)

Common Chart.js configuration shared across renderers:

| Export | Purpose |
|--------|--------|
| `COLORS` | Consistent palette across all charts |
| `hsl()`, `hsla()` | CSS colour helpers |
| `nearestInteraction` | Interaction config for scatter/radar charts (point-level targeting) |
| `horizontalInteraction` | Interaction config for horizontal bar charts (trigger by row, `axis: 'y'`) |
| `makeBarChart()` | Shared dual-axis bar chart factory (used by crosstabs) |

Additionally, `charts.js` registers a **crosshair plugin** that draws a dashed guide line at the hover position — vertical for standard charts, horizontal for charts with `indexAxis: 'y'`. It is automatically skipped for radar charts.

---

## How To Update The Dashboard

1. Modify analysis code in `lib/` or `pdl_analysis.py`
2. Run the pipeline: `python3 relink/scripts/pdl_analysis.py`
3. New JSON files are written to `relink/outputs/data/`
4. Refresh the dashboard in the browser — it re-fetches JSON on each load

No build step is needed. The dashboard is entirely static — it reads JSON files and renders charts client-side.

---

## Serving

```bash
# From the project root:
python3 -m http.server 8000 -d relink

# Or with the built-in serve flag:
python3 relink/scripts/pdl_analysis.py --serve
```

The `--serve` flag both generates data and starts the HTTP server in one command.

Files are served from the `relink/` directory, so the dashboard is at `http://localhost:8000/dashboard/` (with a redirect from `http://localhost:8000/`).

---

## File Map

```
relink/dashboard/
├── index.html              ← Page structure + Canvas elements
├── css/
│   └── styles.css          ← Layout, cards, heatmap colours, modals
└── js/
    ├── main.js              ← Entry point: hash routing, lazy data loading
    ├── charts.js            ← Shared Chart.js config / colours
    ├── overview.js          ← Page 1: Headline Stats
    ├── published.js         ← Page 2: Published Puzzles table + modal
    ├── upcoming.js          ← Page 3: Upcoming Puzzles table + modal
    ├── difficulty-drivers.js← Page 4: Cross-tabs, Heatmap, Correlations, etc.
    ├── crosstabs.js         ← Sub-renderer: PDL cross-tabs charts
    ├── correlations.js      ← Sub-renderer: Scatter plots
    ├── relink.js            ← Page 5: Relink phase charts
    ├── validation.js        ← Page 6: Simulator, Transitions, Failures, Clustering
    ├── clustering.js        ← Sub-renderer: k-means archetypes
    ├── failures.js          ← Sub-renderer: Phi matrices
    ├── explorer.js          ← Shared puzzle detail modal renderer
    └── glossary.js          ← Page 7: Glossary
```

Each `.js` renderer module follows the same pattern:
```javascript
export function render(data) {
    // 1. Extract relevant fields from data
    // 2. Create Chart.js instance(s)
    // 3. Populate any HTML tables or text elements
}
```
