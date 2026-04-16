# 05 — The Dashboard

> **Directory:** `relink/dashboard/`
> **Entry point:** `dashboard/index.html`
> **Data source:** 13 JSON files in `relink/outputs/data/`
> **Technology:** Chart.js v4 (CDN), vanilla JS ES modules

## Architecture

```
Browser loads index.html
       │
       ├── Chart.js v4 (via CDN, global <script>)
       │
       └── js/main.js (ES module entry point)
              │
              ├── Fetches 13 JSON files in parallel
              │
              └── Calls 13 render functions
                  (one per dashboard section)
```

### Why Two Script Loading Strategies?

- **Chart.js** is loaded as a traditional `<script>` tag from CDN. It attaches itself to the global `Chart` object.
- **Dashboard code** uses ES modules (`import`/`export`). Each section has its own `.js` file that exports a `render()` function.

This hybrid approach means Chart.js is available globally to all renderer modules without needing to pass it around.

---

## Data Loading (`main.js`)

On page load, `main.js` fetches all 13 JSON files in parallel:

```javascript
const FILES = [
    'overview', 'crosstabs', 'heatmap', 'impostor-domain',
    'correlations', 'regression', 'vertical', 'decoys',
    'relink', 'clustering',
    'transitions', 'failures', 'simulator'
];

// All fetched simultaneously via Promise.all
const results = await Promise.all(
    FILES.map(f => fetch(`../outputs/data/${f}.json`).then(r => r.json()))
);
```

File names are normalised to camelCase keys (e.g. `impostor-domain` → `impostorDomain`) so renderers can access `data.impostorDomain`.

Once all data is loaded, the loading spinner is hidden and each section renderer is called with its slice of the data.

---

## The 13 Sections

Each section corresponds to one or more JSON files and is rendered by a dedicated JS module.

### 1. Key Findings (`overview.js`)
**Canvas/Elements:** `#stats-grid`, `#subtitle`
**Data:** `overview.json`, `regression.json`, `simulator.json`

Renders a grid of headline stat cards:
- Total puzzles, dated puzzles, total completions
- Overall solve rate range (min–max)
- Simulator validation metrics (r, MAE)
- OLS R² from regression
- Per-date table with sparkline solve rates

### 2. PDL Cross-tabs (`crosstabs.js`)
**Canvas IDs:** `#chart-manip`, `#chart-abstr`, `#chart-know`, `#chart-domain`
**Data:** `crosstabs.json`

Four horizontal bar charts, one per PDL axis. Each bar shows mean first-try % with sample size labels. Bars are sorted by difficulty.

### 3. Difficulty Heatmap (`heatmap.js` — `renderHeatmap`)
**Element:** `#heatmap-container`
**Data:** `heatmap.json`

A HTML table styled as a heatmap — manipulation on x-axis, abstraction on y-axis. Cell colour goes from green (easy) to red (hard). Each cell shows percentage and sample size.

### 4. Impostor Domain (`heatmap.js` — `renderImpostorDomain`)
**Canvas IDs:** `#chart-domain-dist`, `#chart-imp-domain`
**Data:** `impostor-domain.json`

Two charts:
- Grouped bar comparing same-domain vs different-domain impostor performance
- Bar chart breaking down by specific impostor domain

### 5. Puzzle Correlations (`correlations.js`)
**Container:** `#scatter-container`
**Data:** `correlations.json`

Six scatter plots (one per feature), each showing puzzle feature value on x-axis and solve rate on y-axis. Includes Pearson r annotation. Each point represents one dated puzzle.

### 6. Regression Models (`regression.js`)
**Elements:** `#regression-tables`, `#regression-pos`, `#chart-forest`
**Data:** `regression.json`

- Coefficient tables for puzzle-level and row-level OLS models
- Position-controlled model comparison
- Forest plot: horizontal bar chart of row-level coefficients with 0-line reference
- R² and LOO MAE annotations

### 7. Vertical Inference (`vertical.js`)
**Elements:** `#vi-summary`, `#vi-curve-charts`, `#vi-puzzle-table`
**Data:** `vertical.json`

- Summary statistics (mean CoM, proportion that speed up/get more accurate)
- Per-feature crosstab charts: pairs of line charts (timing curve + error curve) for each PDL feature category
- Per-puzzle detail table with inline curve sparklines

### 8. Decoy Analysis (`decoys.js`)
**Canvas IDs:** `#chart-decoy-compare`, `#chart-decoy-hits`
**Data:** `decoys.json`

- Grouped bar: puzzles with decoys vs without (solve rate and avg wrong)
- Per-puzzle decoy hit rate bars with tooltip descriptions

### 9. Relink Phase (`relink.js`)
**Canvas IDs:** `#chart-relink-id-manip`, `#chart-relink-con-manip`, `#chart-relink-tiles`
**Data:** `relink.json`

Three bar charts:
- Relink first-try % by connection identification manipulation
- Relink first-try % by answer construction manipulation
- Relink first-try % and solve rate by phase 2 tile count

### 10. Clustering (`clustering.js`)
**Canvas IDs:** `#chart-puzzle-cluster`, `#chart-row-cluster`
**Elements:** `#cluster-members`
**Data:** `clustering.json`

- Puzzle archetype bar chart (k=3) showing mean solve rate per cluster
- Cluster member lists
- Row archetype bar chart (k=4) showing mean first-try %

### 11. Transition Model (`transitions.js`)
**Elements:** `#pos-lives-grid`, `#trans-pdl-charts`, `#trans-chart-decoy`, `#trans-n`
**Data:** `transitions.json`

- Position × Lives heatmap grid (HTML table with colour-coded cells)
- Per-PDL-axis bar charts showing IPW-weighted first-try rates
- Decoy effect comparison chart
- Observation count annotation

### 12. Correlated Failures (`failures.js`)
**Elements:** `#failure-aggregate`, `#failure-puzzles`, `#failures-n`
**Data:** `failures.json`

- Aggregate table: mean phi by feature similarity (same/different manipulation, abstraction, domain)
- Per-puzzle phi matrices displayed as small 4×4 coloured grids
- Row category labels and failure rates

### 13. Game Simulator (`simulator.js`)
**Canvas IDs:** `#chart-sim-scatter`, `#chart-sim-dist`
**Elements:** `#sim-table`, `#sim-undated`, `#sim-validation`
**Data:** `simulator.json`

- Scatter plot: simulated vs actual solve rate (with y=x reference line)
- Stacked bar chart: simulated row completion distribution per puzzle
- Per-puzzle comparison table with deltas
- Undated puzzle predictions table (sorted by predicted difficulty)
- Validation metrics (r, MAE) for both empirical and feature-only modes

---

## Page Layout

```
┌──────────┬───────────────────────────────────────────┐
│          │                                           │
│   NAV    │            MAIN CONTENT                   │
│          │                                           │
│  Fixed   │   Scrollable                              │
│  sidebar │                                           │
│          │   ┌─────────────────────────────────────┐ │
│  Links   │   │ Section 1: Key Findings             │ │
│  to all  │   │ (stats grid)                        │ │
│  13      │   └─────────────────────────────────────┘ │
│  sections│                                           │
│          │   ┌─────────────────────────────────────┐ │
│          │   │ Section 2: PDL Cross-tabs           │ │
│          │   │ (4 horizontal bar charts)           │ │
│          │   └─────────────────────────────────────┘ │
│          │                                           │
│          │   ... (11 more sections) ...              │
│          │                                           │
└──────────┴───────────────────────────────────────────┘
```

Sections use a `.two-col` CSS grid layout for side-by-side cards, with `.card` containers wrapping each chart or table.

---

## Shared Chart Utilities (`charts.js`)

Common Chart.js configuration shared across renderers:

| Export | Purpose |
|--------|---------|
| `COLOURS` | Consistent palette across all charts |
| `defaultBarOpts()` | Standard horizontal bar chart options |
| `tooltipFormat()` | Standard tooltip formatting |

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
├── index.html          ← Page structure + Canvas elements
├── css/
│   └── styles.css      ← Layout, cards, heatmap colours
└── js/
    ├── main.js          ← Entry point: load data, dispatch to renderers
    ├── charts.js        ← Shared Chart.js config / colours
    ├── overview.js      ← Section 1: Key Findings
    ├── crosstabs.js     ← Section 2: PDL Cross-tabs
    ├── heatmap.js       ← Sections 3+4: Heatmap + Impostor Domain
    ├── correlations.js  ← Section 5: Scatter plots
    ├── regression.js    ← Section 6: OLS models + forest plot
    ├── vertical.js      ← Section 7: VI curves
    ├── decoys.js        ← Section 8: Decoy comparison
    ├── relink.js        ← Section 9: Relink phase charts
    ├── clustering.js    ← Section 10: k-means archetypes
    ├── transitions.js   ← Section 11: Transition model
    ├── failures.js      ← Section 12: Phi matrices
    └── simulator.js     ← Section 13: Monte Carlo results
```

Each `.js` renderer module follows the same pattern:
```javascript
export function render(data) {
    // 1. Extract relevant fields from data
    // 2. Create Chart.js instance(s)
    // 3. Populate any HTML tables or text elements
}
```
