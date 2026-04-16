# Prompt: Split Relink Phase PDL into Connection Identification vs Answer Construction

## Background

In Relink, Phase 2 (the "relink" phase) requires players to do **two distinct cognitive tasks**:

1. **Connection Identification** — Look at the 4 impostor words and figure out what they have in common. *"What do Silent, Alpha, Z, and Greatest share?"* → They're all types of **generations**.

2. **Answer Construction** — Take the available tiles from the solved grid and combine them to express that connection. *"How do I spell GENERATIONS from these tiles?"* → Select **GENE** + **RATIONS** and smash them together.

These are **independent sources of difficulty**. A player might identify the connection quickly but struggle to see that GENE + RATIONS = GENERATIONS. Or they might immediately spot the word-smash opportunity but not know what "generations" refers to.

Currently, both tasks are conflated into a single `pdl.metaConnection` block on each puzzle's relink object. This makes it impossible to separately model the difficulty of each task. The existing tags sometimes describe the identification (e.g. `"manipulation": "Hidden word"` in "End in imperial units" describes how the connection is encoded in the impostors) and sometimes describe the construction (e.g. `"manipulation": "Word split"` in "Generations" describes how tiles combine into the answer).

## Task

Split the relink phase PDL into two separate tag sets, then re-tag all 39 puzzles.

### New Structure

Replace the current:

```json
"relink": {
  "tiles": [...],
  "answer": "...",
  "pdl": {
    "metaConnection": {
      "knowledge": [...],
      "manipulation": [...],
      "abstraction": [...],
      "knowledgeDomain": [...]
    }
  }
}
```

With:

```json
"relink": {
  "tiles": [...],
  "answer": "...",
  "pdl": {
    "connectionIdentification": {
      "manipulation": [...],
      "knowledge": [...],
      "abstraction": [...],
      "knowledgeDomain": [...]
    },
    "answerConstruction": {
      "manipulation": [...]
    }
  }
}
```

### Field Definitions

#### `connectionIdentification` — *"What connects these 4 impostors?"*

Tags describe the cognitive task of recognising the shared link between the 4 impostor words, **independent of how the answer is constructed from tiles**.

- **`manipulation`** — Does the player need to transform or decode the impostor words to see the connection, or is the connection visible at face value?
  - `"None"` — The connection is visible from the impostor words as-is, no linguistic transformation needed. (e.g. "Video game mascots" — the impostors ARE mascots: Mario, Sonic, etc.)
  - `"Hidden word"` — The connection involves spotting words/patterns embedded inside the impostor tiles. (e.g. "End in imperial units" — each impostor contains a hidden unit like FOOT, YARD at the end; "Start with shades of blue" — each impostor starts with a hidden colour)
  - `"Compound"` — The connection involves recognising that each impostor forms a compound word/phrase with a shared word. (e.g. "_ _ _ Ray" — each impostor combines with "Ray": Sting→Stingray, X→X-ray, Gamma→Gamma ray)
  - `"Letter add-delete"` — The connection involves adding, removing, or rearranging letters in the impostor words. (e.g. anagrams, or words that become something else with a letter change)
  - `"Homophone"` — The connection involves how the impostor words sound rather than how they're spelled.

- **`knowledge`** — What background knowledge does the player need to identify the connection?
  - `"General vocabulary"` — Everyday English words/concepts (e.g. "Cleaning products", "Dramatic pause")
  - `"Common cultural"` — Widely known pop culture, traditions, or facts (e.g. "Video game mascots", "Something old, new, borrowed and blue")
  - `"Specialist cultural"` — Niche/specialist knowledge (e.g. "Batman rogues gallery")

- **`abstraction`** — How directly do the impostor words relate to the connection?
  - `"Direct membership"` — Impostors are literal members/examples of the category (e.g. impostors are literal video game mascots)
  - `"Shared property"` — Impostors share a linguistic or structural property (e.g. all end in imperial units, all start with shades of blue)
  - `"Association"` — Impostors are associated with the connection, not direct members (e.g. impostors are associated with "Monopoly" — they're board game concepts)
  - `"Loose thematic"` — Connection is thematic/lateral rather than categorical (e.g. "This puzzle is hard")

- **`knowledgeDomain`** — Subject area(s) of the connection itself: `"General"`, `"Language"`, `"Music"`, `"Film-TV"`, `"Geography"`, `"Science"`, `"Food"`, `"Technology"`, `"History"`, `"Religion"`, `"Maths"`, `"Sport"`

#### `answerConstruction` — *"How do I build the answer from the available tiles?"*

Tags describe the mechanical/linguistic task of combining grid tiles to express the answer, **assuming the player already knows what the answer is**.

- **`manipulation`** — What does the player need to do with the tiles to form the answer?
  - `"None"` — Tiles are literal whole words of the answer. No transformation needed. Player just selects them in order. (e.g. "Video game mascots" → tiles: Video, Game, Mascots)
  - `"Compound"` — Tiles are word fragments that combine to form compound words or multi-word phrases. The fragments are sub-word pieces that don't individually represent the answer. (e.g. "Cleaning products" → tiles: Clean, Ing, Products; "Renewable energy" → Re, New, Able, Energy)
  - `"Word split"` — Tiles smash together (no space) to form a single word that isn't obviously composed of those parts. The key difficulty is recognising the tiles AS fragments of a single word. (e.g. "Generations" → tiles: Gene, Rations — both are real words individually, but GENE+RATIONS = GENERATIONS)
  - `"Hidden word"` — Tiles need to be read with awareness that some contain embedded/hidden words as part of the construction. (e.g. "Friends characters" → tiles: Fri, Ends, Characters — FRI+ENDS = FRIENDS)

## Worked Examples

### "Generations" (l17)
- Impostors: Silent, Alpha, Z, Greatest
- Answer: Generations (tiles: Gene, Rations)
- **connectionIdentification**: The impostors are all types of generations (Silent Generation, Gen Alpha, Gen Z, Greatest Generation). The connection is visible from the impostor words at face value — no linguistic decoding needed — but you need cultural knowledge of generational labels.
  - `manipulation`: `["None"]` — impostors directly name generation types, no transformation to see the link
  - `knowledge`: `["Common cultural"]` — generational labels are widely known
  - `abstraction`: `["Direct membership"]` — each impostor directly names a generation type
  - `knowledgeDomain`: `["General"]`
- **answerConstruction**: GENE + RATIONS must be mentally smashed into GENERATIONS. Both tiles are normal English words, so recognising them as fragments of "Generations" is the hard part.
  - `manipulation`: `["Word split"]`

### "End in imperial units" (l12)
- Impostors: (words that end in hidden imperial units like FOOT, YARD, etc.)
- Answer: End in imperial units (tiles: Imperial, Units)
- **connectionIdentification**: Player must notice the impostors all CONTAIN hidden imperial units at the end. This requires actively looking inside each word for embedded patterns — a linguistic decoding step.
  - `manipulation`: `["Hidden word"]` — you have to spot words hidden inside each impostor
  - `knowledge`: `["General vocabulary"]`
  - `abstraction`: `["Shared property"]` — the link is a hidden structural property
  - `knowledgeDomain`: `["Science"]`
- **answerConstruction**: tiles "Imperial" + "Units" are two literal words that form the phrase. Straightforward.
  - `manipulation`: `["None"]`

### "_ _ _ Ray" (row from l17, hypothetical as relink example)
- Impostors: Sting, X, Gamma, Manta (each forms ___ray)
- Answer: _ _ _ Ray
- **connectionIdentification**: Player must recognise that each impostor forms a compound with "Ray". You have to mentally append "Ray" to each word to see the connection.
  - `manipulation`: `["Compound"]` — comprehension requires mentally forming compound words
  - `knowledge`: `["General vocabulary"]`
  - `abstraction`: `["Shared property"]`
  - `knowledgeDomain`: `["General"]`

### "Friends characters" (l35)
- Impostors: (characters from Friends)
- Answer: Friends characters (tiles: Fri, Ends, Characters)
- **connectionIdentification**: Player must know the TV show Friends and its characters. The impostors are straightforwardly character names — no decoding needed.
  - `manipulation`: `["None"]` — impostors are literal character names
  - `knowledge`: `["Common cultural"]`
  - `abstraction`: `["Direct membership"]`
  - `knowledgeDomain`: `["Film-TV"]`
- **answerConstruction**: FRI + ENDS + CHARACTERS — the first two tiles smash into FRIENDS, then CHARACTERS is literal.
  - `manipulation`: `["Word split"]`

### "Video game mascots" (l18)
- Answer: Video game mascots (tiles: Video, Game, Mascots)
- **connectionIdentification**: Impostors are literal video game mascots. No transformation required.
  - `manipulation`: `["None"]`
  - `knowledge`: `["Common cultural"]`
  - `abstraction`: `["Direct membership"]`
  - `knowledgeDomain`: `["Technology"]`
- **answerConstruction**: Three tiles that are just the three words of the answer. Trivial once you know the answer.
  - `manipulation`: `["None"]`

### "Renewable energy" (l26)
- Answer: Renewable energy (tiles: Re, New, Able, Energy)
- **connectionIdentification**: Impostors are types/sources of renewable energy. No decoding needed — they're literally energy sources.
  - `manipulation`: `["None"]`
  - `knowledge`: `["Common cultural"]`
  - `abstraction`: `["Direct membership"]`
  - `knowledgeDomain`: `["Science"]`
- **answerConstruction**: RE + NEW + ABLE + ENERGY — three fragments form RENEWABLE, plus the literal word ENERGY. Requires recognising RE/NEW/ABLE as fragments of a single word.
  - `manipulation`: `["Word split"]`

### Hypothetical: "Starts with US states" 
- Impostors: (words that start with hidden US state names, e.g. COLORADO → COLOUR + ADO?)
- Answer: Starts with US states (tiles: U, S, States)
- **connectionIdentification**: Player must notice each impostor starts with a hidden US state name embedded in the word. Requires linguistic decoding.
  - `manipulation`: `["Hidden word"]` — must spot state names hidden inside each impostor
  - `knowledge`: `["Common cultural"]`
  - `abstraction`: `["Shared property"]`
  - `knowledgeDomain`: `["Geography"]`
- **answerConstruction**: U + S + STATES — fragments must be combined to form "US States". 
  - `manipulation`: `["Compound"]`

## Important Notes

- When re-tagging, **think about each concern independently**. Both sides now have their own `manipulation` field — they describe completely different things:
  - `connectionIdentification.manipulation`: *"Do I need to decode/transform the impostor words to see what they have in common?"* (Hidden word, Compound, etc.)
  - `answerConstruction.manipulation`: *"Do I need to decode/transform the tiles to spell out the answer?"* (Word split, Compound, etc.)
- These are **independent**. A puzzle can have `"Hidden word"` identification manipulation (spotting patterns in impostors) but `"None"` construction manipulation (tiles are literal words). Or vice versa: `"None"` identification (impostors are obvious members) but `"Word split"` construction (tiles smash together non-obviously).
- The old `metaConnection.manipulation` was conflating both concerns into one tag. When migrating:
  - If the old tag described how you **read the impostors** (e.g. "Hidden word" in l12 "End in imperial units"), it belongs in `connectionIdentification.manipulation`.
  - If the old tag described how you **combine the tiles** (e.g. "Word split" in l17 "Generations"), it belongs in `answerConstruction.manipulation`.
  - Some puzzles may need tags on **both** sides that the old single tag couldn't capture.
- Some puzzles may need new values or refinements — use your best judgement but keep the taxonomy consistent.

## Puzzles to Tag

Apply the new split PDL to all 39 puzzles (l1–l39). Here is the current data for reference:

| Puzzle | Answer | Tiles | Old manipulation | Old abstraction | Old knowledge | Old domain |
|--------|--------|-------|------------------|-----------------|---------------|------------|
| l1 | Something old, new, borrowed and blue | Old, New, Borrowed, Blue | None | Direct membership | Common cultural | General |
| l2 | London Underground stations | London, Underground, Stations | None | Direct membership | Common cultural | Geography |
| l3 | Daily ____ | Daily | Compound | Direct membership | Common cultural | General |
| l4 | Squid | Squid | None | Association | General vocabulary | General |
| l5 | Monopoly | Monopoly | None | Association | Common cultural | General |
| l6 | Dictionaries | Dictionaries | None | Association | General vocabulary | Language |
| l7 | Comes in second | Second | None | Association | General vocabulary | General |
| l8 | ____graph | Graph | Compound | Direct membership | General vocabulary | Language |
| l9 | Silent letter | Silent, Letter | Compound | Shared property | General vocabulary | Language |
| l10 | Taylor Swift records | Taylor Swift, Records | None | Association | Common cultural | Music, General |
| l11 | Newspaper sections | Newspaper, Sections | Compound | Direct membership | General vocabulary | General |
| l12 | End in imperial units | Imperial, Units | Hidden word | Shared property | General vocabulary | Science |
| l13 | Start with shades of blue | Blue, Shades | Hidden word | Shared property | General vocabulary | General |
| l14 | Associated with volcanic eruptions | Volcanic, Eruption | None | Association | General vocabulary | Geography, Science |
| l15 | Collective animals nouns | Collective, Animal, Nouns | None | Direct membership | General vocabulary | General |
| l16 | To con | Con | None | Association | General vocabulary | Language |
| l17 | Generations | Gene, Rations | Word split | Direct membership | General vocabulary | General |
| l18 | Video game mascots | Video, Game, Mascots | None | Direct membership | Common cultural | Technology |
| l19 | Estate planning | Estate, planning | Compound | Direct membership | General vocabulary | General |
| l20 | Cleaning products | Clean, Ing, Products | Compound | Direct membership | General vocabulary | General |
| l21 | Spaceships | Space, Ships | Compound | Direct membership | General vocabulary | General |
| l22 | Named after US Presidents | Named, After, Us, Presidents | None | Association | Common cultural | History, Geography |
| l23 | Strings section | Strings, Section | None | Direct membership | Common cultural | Music |
| l24 | Preparing for battle | Preparing for battle | None | Association | General vocabulary | General |
| l25 | Royal flush | Royal, Flush | Compound | Direct membership | Common cultural | General |
| l26 | Renewable energy | Re, New, Able, Energy | Compound | Direct membership | Common cultural | Science |
| l27 | Types of bean | Bean | Compound | Direct membership | General vocabulary | Food |
| l28 | Nicknames for English Monarchs | Nicknames, English, Monarchs | None | Direct membership | Common cultural | History |
| l29 | Precious metals | Precious, Metals | Compound | Direct membership | General vocabulary | General |
| l30 | Dramatic pause | Dramatic, Pause | Compound | Direct membership | Common cultural | General |
| l31 | PlayStation buttons | Play, Station, Buttons | None | Direct membership | Common cultural | Technology |
| l32 | This puzzle is hard | This, Puzzle, Is, Hard | None | Loose thematic | General vocabulary | General |
| l33 | The Beatles members | Beatles, Members | None | Direct membership | Common cultural | Music |
| l34 | 21ˢᵗ Century Popes | 21ˢᵗ Century, Popes | None | Direct membership | Common cultural | Religion |
| l35 | Friends characters | Fri, Ends, Characters | Hidden word | Direct membership | Common cultural | Film-TV |
| l36 | Batman rogues gallery | Bat, Man, Rogues, Gallery | Compound | Direct membership | Specialist cultural | Film-TV |
| l37 | Chocolate bars | Chocolate, Bars | Compound | Direct membership | Common cultural | Food |
| l38 | Songbirds | Song, Birds | Compound | Direct membership | General vocabulary | General |
| l39 | Evergreen trees | Evergreen, Trees | Compound | Direct membership | General vocabulary | General |

For each puzzle, output the new `connectionIdentification` and `answerConstruction` objects. Pay careful attention to the distinction — especially for puzzles where the old `manipulation` was really describing the identification mechanism (Hidden word in l12, l13) rather than the tile construction.
