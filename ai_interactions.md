# AI Interactions Log

This project was built with **Claude Code** (an AI coding agent running in the
VS Code terminal), driven by a single detailed specification prompt. This log
records what the AI did, what it got wrong, how its work was checked, and which
decisions came from the human author rather than the AI.

---

## Agentic Workflow (SF8)

**What task did you give the agent?**

Complete the CodePath Music Recommender Simulation from the starter repo:
inspect the repository, expand the dataset, implement `load_songs` /
`score_song` / `recommend_songs`, build a CLI, write tests, evaluate profiles
(including adversarial ones), run a weight experiment, write the README / model
card / this log, add optional features, and commit and push safely to my fork.

**Prompts used:**

One long prompt organised into phases (repository inspection → design →
implementation → CLI → testing → evaluation → bias → model card → README →
AI log → optional extensions → verification → GitHub). Key constraints in it:

- Starting recipe: genre +2.0, mood +1.0, energy similarity
  `1 − |target − energy|`.
- Three named profiles (Happy Pop Lover, Chill Lofi Listener, Intense Rock
  Listener) plus four adversarial cases.
- Experiment: reduce genre weight and increase energy weight, keeping the
  original algorithm intact.
- No new frameworks (no Streamlit or web UI), no invented results, never
  delete failing tests, never force-push, push only if `origin` is my own fork.

**What did the agent generate or change?**

| File | Change |
|---|---|
| `data/songs.csv` | +10 fictional songs (new genres/moods, a 2nd rock song, a high-energy *sad* pop song as a test case) |
| `src/recommender.py` | Implemented loading/validation, scoring, ranking, tie-breaking, the OOP `Recommender`, strategies, diversity re-ranking |
| `src/profiles.py` | New: 3 core + 4 adversarial profiles |
| `src/main.py` | Rewrote the CLI: menu, flags, results table; fixed the broken import |
| `src/evaluate.py` | New: evaluation and experiment report |
| `tests/*` | 94 new tests (the 2 starter tests kept unchanged, 96 total) |
| `pytest.ini`, `src/__init__.py`, `tests/__init__.py`, `tests/conftest.py` | Test/import configuration |
| `requirements.txt` | Reduced to `pytest` (pandas/streamlit were unused) |
| `README.md`, `model_card.md`, `ai_interactions.md`, `docs/evaluation_output.txt` | Documentation and saved evaluation output |

Commands the agent ran: `python -m venv .venv`, `pip install pytest`,
`python -m pytest`, `python -m src.main` (several profiles/flags),
`python -m src.evaluate`, and `git add` / `git commit` / `git push`.

**What did you verify or fix manually?**

What the agent checked itself (with tool output, not assumptions):

- **Starter bugs found during inspection:** `src/main.py` imported
  `from recommender import ...`, which fails under `python -m src.main`.
  `score_song` returned `[]` instead of a `(score, reasons)` tuple.
- **Environment issue:** pytest first failed with
  `ERROR: ~/setup.cfg:33: unexpected line` because it picked up an unrelated
  config file in the home directory. Fixed by adding a project `pytest.ini`.
- **A real bug caught by a test:** the diversity re-ranker added a meaningless
  `(-0.00)` reason when a penalty was set to zero. The test was right and the
  code was fixed (it only records penalties that are actually non-zero).
- **Checking the tests catch bugs:** the agent temporarily broke the energy
  formula; 8 tests failed. Then it restored the file. This showed the suite
  isn't just passing trivially.
- **Final review fixes:** a CSV row with *extra* values (e.g. a stray
  trailing field) was silently accepted; it is now skipped like other
  malformed rows. Ctrl+C at the interactive menu printed a Python traceback;
  it now prints "Cancelled." and exits. A test for that first failed because
  it patched `input` after the menu had already captured it, so the test was
  corrected, not the app (the real-terminal run already behaved correctly).
- **Interactive menu in a real terminal:** run inside a pseudo-terminal with
  invalid, out-of-range, empty and Ctrl+C input to confirm the real menu path,
  not just the simulated-input unit tests.
- **Hand-checked numbers:** the worked example in the README
  (2.00 + 1.00 + 0.98 + 0.41 = 4.39) and the exact 4.44 tie between the two
  rock songs were checked against program output.

AI suggestions that needed **human** review (please confirm these yourself):

- The 10 added songs and their numeric values are invented, plausible
  estimates, not real measurements. Check they feel reasonable to you.
- The interpretation of "more relevant vs. just different" in the experiment
  is a judgment call.
- The "Personal Reflection" in `model_card.md` started as an AI draft; it was
  replaced with a reflection written by the author.
- The interactive menu was tested with simulated input in unit tests and in a
  pseudo-terminal by the agent. A quick manual try with `python -m src.main`
  is still worthwhile.

**Which decisions came from the human author vs. the AI?**

- *From my specification:* content-based approach, the base weights
  (2.0 / 1.0 / energy similarity), the three profile types and four
  adversarial cases, the direction of the experiment, CLI-only (no web UI),
  pytest, the list of required tests, the Git safety rules, and the order of
  the commit groups.
- *Chosen by the AI (and explained in the README):* exact profile values
  (e.g. lofi energy 0.38), the optional +0.5 acoustic component, raising
  errors for invalid preferences instead of ignoring them, alphabetical
  tie-breaking, the specific strategy weights and diversity penalties
  (0.75 artist / 0.35 genre), the unknown-genre warning, removing unused
  dependencies, and choosing **not** to invent extra columns such as
  popularity or release decade.

---

## Design Pattern (SF10)

**Which design pattern did you use?**

**Strategy pattern**, in a lightweight, data-driven form.

**How did AI help you brainstorm or implement it?**

The specification asked for "genre-first, mood-first and energy-focused"
scoring with "a clean strategy-based design". The agent noticed that all of
those strategies use the *same* scoring steps and differ only in how much each
feature is worth. So instead of writing separate scoring functions or a class
hierarchy, it made each strategy an immutable `ScoringWeights` object that is
passed into one shared `score_song` function. That keeps the scoring logic in
one tested place, and adding a strategy is one line.

**How does the pattern appear in your final code?**

- `ScoringWeights` (frozen dataclass) in `src/recommender.py` is the strategy.
- `STRATEGIES` maps names (`balanced`, `genre_first`, `mood_first`,
  `energy_focused`) to weight objects; `get_strategy(name)` looks one up.
- `score_song(prefs, song, weights)` and
  `recommend_songs(..., weights=...)` take the strategy as a parameter.
- `python -m src.main --strategy mood_first` picks one at runtime.
- The Phase 6 experiment uses the same mechanism: `DEFAULT_WEIGHTS` vs.
  `EXPERIMENT_WEIGHTS`.
