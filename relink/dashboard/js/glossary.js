/**
 * Glossary page renderer. Builds a categorised term list with cross-links to dashboard pages.
 */

const TERMS = [
    {
        category: 'Game Terms',
        terms: [
            { name: 'Impostor', page: 'difficulty', definition: 'The one wrong word in each row. Three tiles share a hidden connection; the fourth is the impostor that doesn\'t belong. Players must identify it.' },
            { name: 'Relink Phase', page: 'relink', definition: 'Phase 2 of the game. After finding all four impostors, players discover the impostors share their own hidden connection and must spell it out by selecting tiles from the resolved grid.' },
            { name: 'Row', page: 'difficulty', definition: 'One of the four colour-coded groups of 4 tiles on the board. Each row has 3 connected tiles and 1 impostor.' },
            { name: 'Tile', page: 'difficulty', definition: 'A single word on the 4\u00d74 grid. Players select tiles to make guesses.' },
            { name: 'Lives', page: 'model', definition: 'Players start with 4 lives. A wrong guess costs one life. Losing all lives ends the game.' },
            { name: 'Solve Rate', page: 'overview', definition: 'The percentage of players who complete the entire puzzle (both phases) successfully.' },
            { name: 'First-Try Rate', page: 'difficulty', definition: 'The percentage of rows where the player identifies the impostor on their first guess — no wrong answers.' },
            { name: 'Wrong Guess', page: 'difficulty', definition: 'Selecting a non-impostor tile. Costs a life and eliminates that tile from future guesses in the row.' },
            { name: 'Phase 1 (Imposters)', page: 'difficulty', definition: 'The first part of the game where players identify the impostor in each of the four rows.' },
            { name: 'Phase 2 (Relink)', page: 'relink', definition: 'The second part of the game where players spell out the hidden connection linking the four impostors.' },
        ]
    },
    {
        category: 'PDL Terms',
        terms: [
            { name: 'PDL (Puzzle Design Language)', page: 'difficulty', definition: 'A structured framework for describing puzzle difficulty. Each row and the relink answer are tagged with PDL parameters that capture how the connection works.' },
            { name: 'Manipulation', page: 'difficulty', definition: 'How words in a row relate to their connection. Types include Synonym, Association, Category Member, Property, etc. More abstract manipulation types tend to be harder.' },
            { name: 'Abstraction', page: 'difficulty', definition: 'How concrete or abstract the connection concept is. "Word-level" connections are about the words themselves; "Concept-level" are about what the words represent.' },
            { name: 'Knowledge', page: 'difficulty', definition: 'How much external knowledge is needed. "General" knowledge is everyday; "Specialist" requires domain-specific expertise.' },
            { name: 'Knowledge Domain', page: 'difficulty', definition: 'The subject area a row draws from — e.g., Music, Sport, Science, Food. Rows from specialist domains tend to be harder.' },
            { name: 'Connection Identification', page: 'relink', definition: 'A PDL tag for the relink answer describing how players must identify the connection between the four impostors.' },
            { name: 'Answer Construction', page: 'relink', definition: 'A PDL tag for the relink answer describing how players must construct the answer (e.g., selecting whole words vs. combining parts).' },
            { name: 'Same-Domain Impostor', page: 'difficulty', definition: 'An impostor whose knowledge domain matches the row\'s connection domain. These tend to be more deceptive because they "look like they belong".' },
            { name: 'Decoy Grouping', page: 'behaviour', definition: 'A deliberately designed false connection across rows — tiles from different rows that could plausibly form a group, tricking players into wrong guesses.' },
        ]
    },
    {
        category: 'Statistical Terms',
        terms: [
            { name: 'IPW (Inverse Probability Weighting)', page: 'model', definition: 'A technique that corrects for survivorship bias. Players who reach later rows are better-than-average, so their results are weighted to represent what a random player would experience.' },
            { name: 'Survivorship Bias', page: 'model', definition: 'The distortion that occurs when we only observe players who survived to a given point. Later rows appear easier than they are because only skilled players reach them.' },
            { name: 'Transition Probability', page: 'model', definition: 'The chance of a specific outcome (correct or wrong) at a given position and lives count. Like a probability map of the game state space.' },
            { name: 'Wrong-Guess Distribution', page: 'model', definition: 'How wrong guesses are spread across 0, 1, 2, or 3 attempts before finding the impostor. Captures the full shape of difficulty, not just the average.' },
            { name: 'Pearson r', page: 'difficulty', definition: 'A measure of linear correlation between two variables, ranging from \u22121 (perfect inverse) to +1 (perfect positive). Used here to check if design features predict solve rates.' },
            { name: 'Spearman \u03c1', page: 'difficulty', definition: 'A rank-based correlation. Instead of raw values, it checks whether the rank ordering of puzzles by one measure matches another. More robust to outliers than Pearson.' },
            { name: 'Phi Coefficient (\u03c6)', page: 'model', definition: 'A correlation measure for binary outcomes — specifically, whether failing row A is associated with failing row B. Ranges from \u22121 to +1; higher values mean failures are correlated.' },
            { name: 'OLS Regression', page: 'difficulty', definition: 'Ordinary Least Squares regression — a standard method for finding which features best predict an outcome. Fits a linear equation to the data.' },
            { name: 'R\u00b2', page: 'difficulty', definition: 'The fraction of variation in the outcome explained by the model. R\u00b2 = 0.80 means the model explains 80% of the variation in solve rates.' },
            { name: 'LOO Cross-Validation', page: 'difficulty', definition: 'Leave-One-Out cross-validation. Tests the model by removing one puzzle, predicting it from the rest, and repeating for all puzzles. Measures how well the model generalises.' },
            { name: 'MAE', page: 'simulator', definition: 'Mean Absolute Error — the average gap between predicted and actual values. MAE = 12.7pp means predictions are off by about 12.7 percentage points on average.' },
            { name: 'Ratio-Shift Model', page: 'simulator', definition: 'The simulator\'s approach to adjusting base transition probabilities. Instead of adding a fixed amount, it shifts the odds ratio — preserving valid probability ranges and respecting floor/ceiling effects.' },
            { name: 'Monte Carlo Simulation', page: 'simulator', definition: 'Running thousands of simulated games using random sampling. Each simulated player plays through the game using the learned transition probabilities, building up a distribution of outcomes.' },
        ]
    },
    {
        category: 'Analysis Terms',
        terms: [
            { name: 'Vertical Inference', page: 'behaviour', definition: 'Tracking how player performance changes across row positions (1st, 2nd, 3rd, 4th row solved). "Vertical" because it looks down the sequence of rows a player solves.' },
            { name: 'Centre of Mass (CoM)', page: 'behaviour', definition: 'Weighted average of position (0–3) using timing or error values as weights. Formula: Sum(position × value) / Sum(value). Ranges from 0 (all weight at position 0) to 3 (all weight at position 3), with 1.5 as the midpoint. Error CoM < 1.5 means errors are front-loaded — players make more mistakes early and improve, suggesting they\'re learning. Timing CoM < 1.5 means players are slower early and speed up. Formerly called "transparency score".' },
            { name: 'Cluster / Archetype', page: 'clustering', definition: 'A group of puzzles or rows that share similar characteristics, identified by k-means clustering. An archetype represents a "typical" member of the group.' },
            { name: 'Feature Combo', page: 'difficulty', definition: 'A specific combination of PDL values (e.g., Association + Concept-level + General knowledge). The unique fingerprint of a row\'s design.' },
            { name: 'Pairwise Ordering Accuracy', page: 'simulator', definition: 'The percentage of puzzle pairs where the simulator correctly predicts which one is harder. 91% means for 91 out of 100 random pairs, the simulator gets the relative ordering right.' },
        ]
    },
    {
        category: 'Difficulty Rating Terms',
        terms: [
            { name: 'Difficulty Rating (1–5)', page: 'ratings', definition: 'A star rating from 1 (easiest) to 5 (hardest), derived from a weighted blend of five difficulty dimensions. Rated for all 39 puzzles — empirical for dated puzzles, simulator-predicted for undated.' },
            { name: 'Composite Score', page: 'ratings', definition: 'The weighted sum of the five difficulty dimensions (each 0–1), producing a single 0–1 number. Mapped to star ratings via calibrated thresholds. Correlates with actual solve rates at |ρ| ≈ 0.89.' },
            { name: 'Impostor Deception', page: 'ratings', definition: 'Difficulty dimension measuring how hard it is to spot the impostor in each row. Computed as mean (1 − first-try rate) across all 4 rows. High deception = players frequently guess wrong before finding the impostor. Weight: 30%.' },
            { name: 'Knowledge Demand', page: 'ratings', definition: 'Difficulty dimension measuring how much specialist or broad knowledge the puzzle requires. Derived from PDL: knowledge breadth (how many distinct domains) and specialist group count. Pure design metric — same for dated and undated puzzles. Weight: 15%.' },
            { name: 'Punishment Risk', page: 'ratings', definition: 'Difficulty dimension capturing life pressure and tail risk. Blends expected total wrong guesses with the probability of ≥3 wrongs (the "danger zone" where game-over is likely). High punishment = the puzzle drains lives even if individual rows aren\'t terrible. Weight: 25%.' },
            { name: 'Connection Challenge', page: 'ratings', definition: 'Difficulty dimension for Phase 2 (Relink). Blends (1 − relink first-try rate) with the phase 2 tile count. More tiles and a harder connection both increase this score. Weight: 20%.' },
            { name: 'Volatility', page: 'ratings', definition: 'Difficulty dimension measuring whether difficulty is concentrated in one killer row or spread evenly. Computed as the coefficient of variation of per-row wrong rates. High volatility = one row is dramatically harder than the others, creating a bottleneck. Weight: 10%.' },
            { name: 'Difficulty Profile', page: 'ratings', definition: 'The radar chart showing a puzzle\'s scores across all five difficulty dimensions. Different profile shapes indicate different types of difficulty — a puzzle can be hard because of deceptive impostors, specialist knowledge, or a tough relink connection.' },
        ]
    }
];

export function render(container) {
    if (!container) return;
    let html = '';
    for (const group of TERMS) {
        html += `<div class="glossary-category">`;
        html += `<h2>${group.category}</h2>`;
        html += `<div class="glossary-grid">`;
        for (const t of group.terms) {
            html += `<div class="glossary-term">`;
            html += `<dt>${t.name}</dt>`;
            html += `<dd>${t.definition} <a href="#${t.page}" class="glossary-link">${formatPageName(t.page)}</a></dd>`;
            html += `</div>`;
        }
        html += `</div></div>`;
    }
    container.innerHTML = html;
}

function formatPageName(page) {
    const names = {
        overview: 'Overview',
        difficulty: 'Difficulty Drivers',
        behaviour: 'Player Behaviour',
        relink: 'Relink Phase',
        model: 'Statistical Model',
        simulator: 'Simulator',
        clustering: 'Clustering',
        ratings: 'Difficulty Ratings'
    };
    return names[page] || page;
}
