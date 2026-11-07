# 🎵 Music Recommender Simulation — VibeMatch 1.0

## Project Summary

VibeMatch is a small, **content-based** music recommender that runs in the terminal.
It reads a 20-song catalog from a CSV file and takes a listener's taste profile
(favourite genre, favourite mood, target energy, and optionally whether they like
acoustic sound). It gives every song a score and prints the top 5 matches,
**with a written reason for every point it awarded**.

It is an educational simulation. It shows how "turn data into a ranked list"
works in principle. It does **not** reproduce Spotify's (or anyone else's)
proprietary recommendation algorithm.

### Quick start

```bash
git clone https://github.com/NagaSekhar23/ai110-module3show-musicrecommendersimulation-starter.git
cd ai110-module3show-musicrecommendersimulation-starter
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.main --profile chill_lofi   # recommendations for one listener
python -m src.evaluate                    # every profile + the weight experiment
python -m pytest                          # run the test suite
```

### Problem statement

Streaming services have far more songs than anyone can browse. A recommender
has to answer: *"Of everything in the catalog, which few songs is this person
most likely to enjoy right now?"* This project answers that with a transparent,
explainable scoring rule, then tests where that rule works and where it fails.

---

## How Recommendation Systems Work

### Collaborative filtering vs. content-based filtering

| | Collaborative filtering | Content-based filtering (this project) |
|---|---|---|
| Core idea | "People who liked what you liked also liked X" | "X has the attributes you like" |
| Data needed | Behaviour of **many users** (plays, likes, skips) | **Attributes of each song** + one user's preferences |
| Strength | Finds surprising matches across genres | Works for a single user; easy to explain |
| Weakness | Cold start: new songs/users have no history | Only recommends "more of the same"; limited by the features you have |

### Signals real systems use

Real platforms usually **combine** both approaches and many signals:

- **Explicit feedback:** likes, saves, thumbs-down, adding a song to a playlist.
- **Implicit feedback:** listening history, skips (a skip in the first few seconds is a strong negative signal), replays, listening time.
- **Playlists:** songs that appear together in many users' playlists are probably related.
- **Song attributes:** genre, mood, energy, tempo, acousticness, danceability, valence (musical positivity), and audio features extracted from the sound itself.
- **Context:** time of day, device, activity.

This simulator uses only the **song attributes** part, because we have no real
listening data. That keeps it fully explainable, but it is also its biggest
limitation (see [Limitations](#limitations-and-bias)).

---

## How The System Works

### Features used

**Each `Song`** (one row of [data/songs.csv](data/songs.csv)):

| Field | Type | Used in scoring? |
|---|---|---|
| `id`, `title`, `artist` | int / text | No (identification, tie-breaking, diversity) |
| `genre` | text | **Yes**: exact match |
| `mood` | text | **Yes**: exact match |
| `energy` | 0.0–1.0 | **Yes**: similarity to target |
| `acousticness` | 0.0–1.0 | **Yes**, only if the user states `likes_acoustic` |
| `tempo_bpm`, `valence`, `danceability` | numbers | Loaded and validated, not scored (future work) |

**Each user profile** (a dictionary, or the `UserProfile` dataclass):

| Key | Meaning |
|---|---|
| `genre` | favourite genre, e.g. `"pop"` |
| `mood` | favourite mood, e.g. `"happy"` |
| `energy` | target energy, 0.0 (calm) to 1.0 (intense) |
| `likes_acoustic` | optional `True`/`False` |

Any preference can be left out; missing preferences are simply not scored.
Invalid ones (e.g. `energy=8`) raise a clear error instead of silently giving
bad results.

### Algorithm recipe (default "balanced" strategy)

| Component | Points |
|---|---|
| Genre match | **+2.0** if `song.genre == user.genre` (case-insensitive) |
| Mood match | **+1.0** if `song.mood == user.mood` |
| Energy similarity | **+1.0 × (1 − \|target − song.energy\|)**, from 0.0 to 1.0 |
| Acoustic fit (optional) | **+0.5 × acousticness** if the user likes acoustic, **+0.5 × (1 − acousticness)** if not |

Maximum possible score: **4.5**. Because energy and acousticness are both on a
0–1 scale, `1 − |difference|` is always between 0 and 1: identical energy earns
the full point and opposite energy earns nothing.

### Worked example

Happy Pop Lover (`genre=pop, mood=happy, energy=0.80, likes_acoustic=False`) vs.
*Sunrise City* (`pop, happy, energy 0.82, acousticness 0.18`):

```
genre match        pop == pop                         +2.00
mood match         happy == happy                     +1.00
energy similarity  1.0 × (1 − |0.80 − 0.82|) = 0.98   +0.98
acoustic fit       0.5 × (1 − 0.18)          = 0.41   +0.41
                                              total =  4.39
```

### Scoring vs. ranking: two separate steps

1. **`score_song(user, song)`** judges **one** song. It knows nothing about
   other songs, so it is easy to test and explain.
2. **`recommend_songs(user, songs, k)`** runs `score_song` on **every** song,
   sorts them highest first, and keeps the top `k`.

Keeping them separate means you can change *how a song is judged* (the weights)
without touching *how the list is built* (sorting, tie-breaking, diversity), and
the reverse. Ranking also needs whole-catalog decisions that a single score
can't make, such as "don't show the same artist twice in a row".

**Ties** are broken alphabetically by title, then artist, then id, so the same
input always gives the same output. This happens for real: *Broken Amplifier*
and *Storm Runner* both score exactly 4.44 for the rock profile.

### Architecture

```
data/songs.csv
      │  load_songs()      csv module → list of dicts, numbers converted,
      ▼                    bad rows skipped with a warning
 list of song dicts ──────────────────────────────┐
      │                                           │
user profile (src/profiles.py)                    │
      │                                           ▼
      └──► score_song(prefs, song, weights) ──► (score, reasons)   ← one song
                       ▲
                       │ called for every song
           rank_songs() → sort by (-score, title, artist, id)
                       │
           [optional] diversify() → penalise repeat artists/genres
                       │
           recommend_songs() → top k (song, score, explanation)
                       │
           src/main.py (CLI table)   src/evaluate.py (experiments)
```

### Repository structure

```
├── data/songs.csv              20-song catalog
├── src/
│   ├── recommender.py          loading, scoring, ranking, strategies, diversity, OOP wrapper
│   ├── profiles.py             3 core + 4 adversarial user profiles
│   ├── main.py                 CLI  (python -m src.main)
│   └── evaluate.py             evaluation + experiment report (python -m src.evaluate)
├── tests/                      96 pytest tests
├── docs/evaluation_output.txt  saved output of python -m src.evaluate
├── model_card.md               model card
├── ai_interactions.md          how AI was used in this project
├── pytest.ini                  test configuration
└── requirements.txt            pytest (the only dependency)
```

---

## Dataset

[data/songs.csv](data/songs.csv) holds **20 songs**: the 10 starter songs plus
10 added for this project. All titles and artists are **fictional**, written in
the same style as the starter rows. The numbers are hand-assigned to be plausible
for each style (e.g. metal ≈ 0.97 energy, classical ≈ 0.97 acousticness); they
are **not** measured from real audio.

The 10 additions were picked to fill gaps: a second rock song (so the rock
profile has more than one real match), plus r&b, hip hop, folk, edm, country,
classical, metal and reggae, and moods the starter lacked (sad, romantic,
confident, euphoric, nostalgic, melancholy, angry). One deliberately tricky song,
*Static Tears* (high-energy **sad** pop), tests whether the system can tell mood
from energy.

| | Counts |
|---|---|
| Genres (15) | pop 3, lofi 3, rock 2, and 1 each: ambient, jazz, synthwave, indie pop, r&b, hip hop, folk, edm, country, classical, metal, reggae |
| Moods (13) | chill 3, intense 3, happy 2, relaxed 2, sad 2, and 1 each: moody, focused, romantic, confident, euphoric, nostalgic, melancholy, angry |
| Repeat artists | Neon Echo 3, LoRoom 2 |

`load_songs()` validates every row: the right number of columns, integer id, non-empty title/genre/mood,
energy present, 0–1 features within range, positive tempo, no duplicate ids.
A test checks that every row of the real file passes.

---

## User Profiles

Defined in [src/profiles.py](src/profiles.py):

| Key | Name | Preferences |
|---|---|---|
| `happy_pop` | Happy Pop Lover (default) | genre=pop, mood=happy, energy=0.8, likes_acoustic=False |
| `chill_lofi` | Chill Lofi Listener | genre=lofi, mood=chill, energy=0.38, likes_acoustic=True |
| `intense_rock` | Intense Rock Listener | genre=rock, mood=intense, energy=0.9, likes_acoustic=False |
| `high_energy_sad` | *Adversarial:* High Energy + Sad | genre=pop, mood=sad, energy=0.9 |
| `low_energy_rock` | *Adversarial:* Low Energy + Intense Rock | genre=rock, mood=intense, energy=0.15 |
| `unknown_genre` | *Adversarial:* Genre not in dataset | genre=k-pop, mood=happy, energy=0.7 |
| `conflicting` | *Adversarial:* Classical but euphoric, max energy | genre=classical, mood=euphoric, energy=1.0, likes_acoustic=True |

---

## Getting Started

### Setup (macOS)

```bash
cd ai110-module3show-musicrecommendersimulation-starter
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate` instead. The program itself
uses only the Python standard library (developed and tested on Python 3.12);
`pytest` is only needed for the tests.

### Run the app

```bash
python -m src.main                                  # interactive menu (Enter = Happy Pop Lover)
python -m src.main --profile chill_lofi             # skip the menu
python -m src.main --profile intense_rock --k 3     # top 3 instead of top 5
python -m src.main --strategy mood_first --diverse  # optional extensions
python -m src.main --list-profiles
python -m src.evaluate                              # full evaluation + experiment report
```

When no terminal is attached (e.g. input is piped), the menu is skipped and the
default profile is used. Invalid menu input is rejected and re-asked; after three
bad tries the default is used. Ctrl+C at the menu exits cleanly.

### Run the tests

```bash
python -m pytest        # or simply: pytest
```

96 tests cover CSV loading and validation, numeric conversion, each scoring
component, combined scores, ranking order, top-k, empty catalogs, invalid k and
preferences, missing preferences, deterministic ties, dataset integrity, the
three profiles, the CLI menu (including Ctrl+C), strategies and diversity.

Latest run:

```
$ python -m pytest
============================== 96 passed in 0.06s ==============================
```

---

## Sample Recommendation Output

Actual output of `python -m src.main --profile happy_pop`:

```
Loaded 20 songs from data/songs.csv

=========================================================================================
Profile: Happy Pop Lover  (top 5, strategy=balanced)
Preferences: genre=pop, mood=happy, energy=0.8, likes_acoustic=False
=========================================================================================
#   Title                       Artist             Genre       Mood         Energy  Score
-----------------------------------------------------------------------------------------
1   Sunrise City                Neon Echo          pop         happy          0.82   4.39
      - genre match: pop (+2.00)
      - mood match: happy (+1.00)
      - energy similarity: 0.82 vs target 0.80 (+0.98)
      - produced/electronic sound fit: acousticness 0.18 (+0.41)
2   Static Tears                Neon Echo          pop         sad            0.86   3.37
      - genre match: pop (+2.00)
      - energy similarity: 0.86 vs target 0.80 (+0.94)
      - produced/electronic sound fit: acousticness 0.15 (+0.42)
3   Gym Hero                    Max Pulse          pop         intense        0.93   3.35
      - genre match: pop (+2.00)
      - energy similarity: 0.93 vs target 0.80 (+0.87)
      - produced/electronic sound fit: acousticness 0.05 (+0.47)
4   Rooftop Lights              Indigo Parade      indie pop   happy          0.76   2.29
      - mood match: happy (+1.00)
      - energy similarity: 0.76 vs target 0.80 (+0.96)
      - produced/electronic sound fit: acousticness 0.35 (+0.33)
5   Concrete Crown              Kilo Verse         hip hop     confident      0.78   1.42
      - energy similarity: 0.78 vs target 0.80 (+0.98)
      - produced/electronic sound fit: acousticness 0.12 (+0.44)
```

The full output for every profile is in
[docs/evaluation_output.txt](docs/evaluation_output.txt).

---

## Evaluation Results

All results below come from `python -m src.evaluate` using the balanced
strategy, with scores in brackets.

**Happy Pop Lover:** Sunrise City (4.39), Static Tears (3.37), Gym Hero (3.35), Rooftop Lights (2.29), Concrete Crown (1.42)
*#1 is a perfect fit. But #2 is a **sad** song and #3 an **intense** one: both
beat the genuinely happy *Rooftop Lights*, because "pop" (+2) is worth twice as
much as "happy" (+1) and "indie pop" is not counted as "pop".*

**Chill Lofi Listener:** Library Rain (4.40), Midnight Coding (4.32), Focus Flow (3.37), Spacewalk Thoughts (2.36), Coffee Shop Stories (1.44)
*Very sensible: two chill lofi songs, then focused lofi, then chill ambient and
relaxed jazz, all low energy and acoustic. This is the best-behaved profile
because the catalog has three lofi songs.*

**Intense Rock Listener:** Broken Amplifier (4.44), Storm Runner (4.44), Gym Hero (2.44), Laser Garden (1.44), Iron Tide (1.41)
*Both rock songs on top (an exact tie, broken alphabetically). After that the
catalog runs out of rock, so #3–5 are filled by energy alone. Metal, arguably the
closest genre, only reaches #5.*

### Adversarial profiles

| Profile | Top 3 | What it reveals |
|---|---|---|
| High Energy + Sad | Static Tears (3.96), Gym Hero (2.97), Sunrise City (2.92) | Works for #1. Then a *happy* song (#3) beats the sad folk song (#4, 1.34) because genre + energy outweigh mood. |
| Low Energy + Intense Rock | Broken Amplifier (3.27), Storm Runner (3.24), Gym Hero (1.22) | The listener asked for energy 0.15 and got 0.88–0.93 energy songs. Genre + mood (3 pts) overwhelm energy (≤1 pt). |
| Genre not in dataset (k-pop) | Rooftop Lights (1.94), Sunrise City (1.88), Night Drive Loop (0.95) | It degrades gracefully to mood + energy, and the CLI now prints a warning that no k-pop exists. |
| Conflicting (classical, euphoric, energy 1.0) | Nocturne for Empty Rooms (2.67), Laser Garden (1.97), Iron Tide (0.99) | The genre match wins even though the song's energy (0.18) is the opposite of what was asked. |

---

## Experiments

### Controlled experiment: halve genre weight, double energy weight

Same dataset, same 7 profiles. Only the weights change:

| | Genre | Mood | Energy | Acoustic |
|---|---|---|---|---|
| Original (`DEFAULT_WEIGHTS`) | 2.0 | 1.0 | 1.0 | 0.5 |
| Experimental (`EXPERIMENT_WEIGHTS`) | 1.0 | 1.0 | 2.0 | 0.5 |

The original weights stay the default; the experimental ones live in a
separate constant.

| Profile | What changed in the top 5 | More relevant or just different? |
|---|---|---|
| Happy Pop Lover | Rooftop Lights (happy) #4 → #3; Gym Hero (intense) #3 → #4 | **More relevant**: the happy song now beats the intense one. Static Tears (sad) still holds #2. |
| Chill Lofi | No change | The profile is internally consistent, so all weights agree. |
| Intense Rock | Storm Runner and Broken Amplifier swap #1/#2; Iron Tide (metal) **out**, Static Tears (sad pop) **in** at #5 | **Just different, arguably worse**: a sad pop song replaced the metal song. |
| High Energy + Sad | Paper Boats in March (sad folk, low energy) **out**; Broken Amplifier **in** | Different. Energy now beats mood. |
| Low Energy + Rock | Gym Hero **out**; calm songs Nocturne, Paper Boats and Spacewalk Thoughts fill #3–5 | More relevant *to the energy request*, but #1–2 are still high-energy rock. |
| k-pop | No change in order (scores roughly double) | Without a genre match, both versions rank by mood + energy. |
| Conflicting | Laser Garden (euphoric edm, 0.95 energy) **#2 → #1**; Nocturne **#1 → #5** | Depends what the user meant. Shows the weights decide which half of a contradiction wins. |

**Conclusion:** shifting weight from genre to energy made some lists more
relevant and others just different. No single set of weights is "correct"; the
weights encode an assumption about what listeners care about most. That is why
the project offers selectable strategies instead of one hidden formula.

### Optional extensions tried

- **Scoring strategies** (`--strategy`): `balanced` (default), `genre_first`
  (3.0/1.0/0.5/0.25), `mood_first` (1.0/2.5/1.0/0.5), `energy_focused`
  (0.5/0.5/3.0/0.5). With `mood_first`, the Happy Pop Lover's #2 becomes
  *Rooftop Lights* instead of the sad *Static Tears*.
- **Diversity re-ranking** (`--diverse`): songs are picked one at a time, and
  each remaining candidate loses 0.75 for every already-picked song by the same
  artist and 0.35 for every one in the same genre. For Happy Pop Lover this drops
  the second Neon Echo song from #2 to #4. The penalty is printed as a reason
  (e.g. `diversity: artist already listed x1 (-0.75)`).
- **Unknown preference warning:** the CLI says when a requested genre or mood
  doesn't exist in the catalog.
- Extra attributes (popularity, release decade) were **not** added: inventing
  values for them would make the data less trustworthy, not more.

---

## Limitations and Bias

- **Genre dominates.** Genre (+2) outweighs mood (+1) and energy (≤1). The
  low-energy rock listener was recommended 0.88-energy songs, and the Happy Pop
  Lover's #2 pick is a sad song. *This is the main concrete limitation found in
  evaluation.*
- **Exact string matching.** "indie pop" ≠ "pop" and "metal" ≠ "rock", so
  closely related songs get no genre credit at all.
- **Genre imbalance.** 12 of 15 genres have exactly one song. A country fan can
  get at most one genre match, while pop and lofi fans get three. Users with
  well-represented tastes systematically get better lists.
- **Tiny catalog.** 20 songs means the top 5 quickly fills with weak matches
  (scores near 1.0 that matched only on energy).
- **Filter bubble.** A content-based system only recommends more of what you
  already said you like; it never suggests a surprising genre the way
  collaborative filtering could.
- **No real behaviour.** No plays, skips or likes, so the system cannot learn or
  notice that a user's taste has changed.
- **Cold start.** Users must state their preferences up front. And with no
  user history, there is no collaborative signal for new songs or new users.
- **Hand-assigned numbers.** Energy and acousticness values are plausible
  estimates, not measurements.

See [model_card.md](model_card.md) for the full analysis.

---

## Future Improvements

- Genre similarity groups (pop ≈ indie pop, rock ≈ metal) for partial credit.
- Score tempo, valence and danceability, which are already loaded and validated.
- Let users list several genres/moods or weight their own preferences.
- Learn weights from simulated feedback (likes/skips) instead of hand-tuning.
- Add a collaborative component once there is multi-user listening data.
- A larger, more balanced catalog with measured audio features.

---

## Reflection

My full personal reflection is in the [Model Card, section 11](model_card.md#11-personal-reflection).
Two key takeaways from it:

> One of my biggest learning moments was implementing the scoring and ranking
> logic separately. [...] I also learned how small changes to scoring weights
> can significantly affect the final recommendations.

> During evaluation, I discovered that the algorithm could recommend a sad song
> to someone who preferred happy pop simply because genre matching had a higher
> weight than mood matching. This showed me why testing and evaluating an AI
> system is just as important as implementing it.

See also [**AI Interactions**](ai_interactions.md) for how AI tools were used
and verified in this project.
