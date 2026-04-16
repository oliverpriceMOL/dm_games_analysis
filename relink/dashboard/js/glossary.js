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
            { name: 'Transparency Score', page: 'behaviour', definition: 'How much a row\'s connection "gives itself away" — measured by how quickly and accurately players solve it. High transparency means the connection is obvious.' },
            { name: 'Centre of Mass (CoM)', page: 'behaviour', definition: 'A single number summarising where activity concentrates across 4 positions. CoM = 0.5 means front-loaded (most action early); CoM = 2.5 means back-loaded (most action late).' },
            { name: 'Cluster / Archetype', page: 'clustering', definition: 'A group of puzzles or rows that share similar characteristics, identified by k-means clustering. An archetype represents a "typical" member of the group.' },
            { name: 'Feature Combo', page: 'difficulty', definition: 'A specific combination of PDL values (e.g., Association + Concept-level + General knowledge). The unique fingerprint of a row\'s design.' },
            { name: 'Pairwise Ordering Accuracy', page: 'simulator', definition: 'The percentage of puzzle pairs where the simulator correctly predicts which one is harder. 91% means for 91 out of 100 random pairs, the simulator gets the relative ordering right.' },
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
        clustering: 'Clustering'
    };
    return names[page] || page;
}
