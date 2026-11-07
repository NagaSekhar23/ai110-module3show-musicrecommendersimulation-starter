# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name

**VibeMatch 1.0**, a transparent, rule-based, content-based music recommender.

---

## 2. Goal / Task

Given a listener's stated taste (favourite genre, favourite mood, how energetic
they want the music, and optionally whether they like acoustic sound),
VibeMatch picks the **5 songs** from its catalog that best match and explains
**why** each one was chosen.

It doesn't predict whether someone will actually enjoy a song; it measures how
closely each song's labels match what the listener said they want.

---

## 3. Data Used

- **Catalog:** `data/songs.csv`, **20 songs** (10 from the starter project and
  10 added for this project). Song titles and artists are fictional.
- **Attributes per song:** genre, mood, energy (0–1), tempo (BPM), valence
  (0–1, musical positivity), danceability (0–1) and acousticness (0–1).
- **Coverage:** 15 genres and 13 moods. Pop and lofi have 3 songs each, rock
  has 2, and the other 12 genres have just 1 each. One artist (Neon Echo)
  has 3 songs.
- **Where the numbers come from:** they were assigned by hand to be plausible
  for each style. They were **not** measured from real recordings.
- **No user data.** There are no listening histories, likes or skips. The
  "users" are 7 hand-written profiles (3 normal, 4 deliberately tricky).
- **Missing parts of musical taste:** lyrics, language, artist familiarity,
  release era, popularity, and the listening context (working out, studying,
  a party).

---

## 4. Algorithm Summary

Think of it as a judge awarding points to each song:

- **Same genre as the listener's favourite:** 2 points.
- **Same mood as the listener's favourite:** 1 point.
- **Energy closeness:** up to 1 point. A song with exactly the energy the
  listener wants gets the full point; one at the opposite extreme gets 0.
  (Formula: 1 − the gap between the two energy values.)
- **Acoustic fit** (only if the listener said whether they like acoustic
  music): up to 0.5 points, more for songs that lean the way they prefer.

The judge scores every song separately. Then the songs are sorted from most to
fewest points, and the top 5 are shown with a list of exactly which points they
earned. If two songs tie, they are listed alphabetically, so the result never
changes between runs.

**Changes from the starter logic:** the starter returned the first 5 songs
unscored. VibeMatch adds the scoring above, input validation, deterministic
tie-breaking and explanations. Optional add-ons: four selectable weightings
("balanced", "genre first", "mood first", "energy focused") and a
"diversity" option that docks points for repeating an artist or genre already
in the list.

---

## 5. Observed Behavior / Biases

- **Genre outweighs everything else.** Because genre is worth twice as much as
  mood, the *Happy Pop Lover's* #2 recommendation is *Static Tears*, a **sad**
  pop song, ranked above the genuinely happy (but "indie pop") *Rooftop Lights*.
- **Stated energy can be ignored.** A listener who wants *low-energy* (0.15)
  intense rock is recommended rock songs with energy 0.88 and 0.91. Genre +
  mood (3 points) easily beat the at most 1 point for energy.
- **Near-miss genres get nothing.** "indie pop" isn't "pop" and "metal" isn't
  "rock". The rock fan sees the metal song only at #5.
- **Better service for well-represented tastes.** Pop and lofi fans have 3
  songs that can match their genre; fans of country, jazz, reggae, metal, etc.
  have only 1. Nothing in the code favours anyone, but the data does.
- **Artist repetition.** Neon Echo appears twice in the Happy Pop Lover's top
  3. The optional diversity mode fixes this, but it's off by default.
- **Graceful but quiet failure (now warned).** A listener asking for "k-pop"
  (not in the catalog) silently got a mood + energy list. The CLI now prints a
  note when a requested genre or mood doesn't exist.

---

## 6. Evaluation Process

1. **Three core profiles** (Happy Pop, Chill Lofi, Intense Rock). I checked that
   the top picks share the requested genre and mood, and that energy is close.
   Results: Chill Lofi was ideal; Intense Rock was good for #1–2 and then ran
   out of rock; Happy Pop had the sad-song problem above.
2. **Four adversarial profiles:** high energy + sad, low energy + intense rock,
   a genre that doesn't exist (k-pop), and contradictory classical + euphoric +
   max energy. These exposed the genre-dominance and exact-match problems.
3. **Controlled experiment:** the same 7 profiles and the same data were run
   with genre weight halved (2.0 → 1.0) and energy weight doubled (1.0 → 2.0).
   - Happy Pop: the happy *Rooftop Lights* rose above the intense *Gym Hero*
     (**more relevant**).
   - Intense Rock: the metal song dropped out and a sad pop song came in
     (**different, arguably worse**).
   - Chill Lofi and k-pop: order unchanged.
   - Conclusion: no weighting is best for everyone.
4. **Automated tests:** 94 pytest tests, including checks that every
   score matches the recipe by hand-calculation, that the top results for each
   core profile have the expected genre, that ties are always broken the same
   way, and that the catalog itself has valid, unique rows.

The full, reproducible output is in `docs/evaluation_output.txt`
(`python -m src.evaluate`).

**Strengths observed:** coherent profiles with several catalog matches (Chill
Lofi) get excellent lists; every recommendation can be explained exactly; bad
input is rejected instead of producing nonsense.

---

## 7. Intended Use

- Classroom exploration of how recommender systems turn data into ranked lists.
- Demonstrating trade-offs in feature weighting, and how bias can come from
  data and design choices.
- A small, readable codebase for practising testing and evaluation.

---

## 8. Non-Intended Use

- **Not** for real users or production music apps: the catalog is tiny and
  fictional, and the numbers are hand-assigned.
- **Not** a model of how Spotify, Apple Music or any real service works.
- **Not** for drawing conclusions about real artists, genres or listener
  groups.
- **Not** for any decision about people (e.g. profiling users by taste).

---

## 9. Limitations

- Only 20 songs; most genres have one example.
- Exact text matching for genre and mood, with no notion of "similar" genres.
- Fixed, hand-chosen weights that encode one assumption about what matters.
- Tempo, valence and danceability are loaded but not scored.
- One genre and one mood per user; real taste is broader.
- No feedback loop: it never learns from likes, skips or repeat plays.
- Cold start: users must describe their taste up front, and there's no
  collaborative signal from other listeners.
- Filter bubble: it only recommends more of what the user already named.

---

## 10. Ideas for Improvement

- Partial credit for related genres and moods (pop ≈ indie pop, sad ≈
  melancholy).
- Include tempo, valence and danceability in the score.
- Allow multiple favourite genres/moods and user-adjustable weights.
- Learn weights from (simulated) feedback instead of hand-tuning them.
- Turn diversity on by default once the catalog is larger.
- A bigger, more balanced catalog with real measured audio features.
- Add collaborative filtering once multi-user listening data exists.

---

## 11. Personal Reflection

> *Draft written with AI assistance from the observed results. Edit it into
> your own words before submitting.*

The biggest surprise was how much a single number decides. With genre worth
2 points, a "happy pop" listener gets a sad song at #2. Halving that weight
fixed it for them but made the rock listener's list worse. Before this project
I assumed recommendation apps "understand" music; now I see that they rank by
rules or learned weights, and every choice of weight is a judgment about what
listeners care about. I also learned that bias doesn't need biased code: the
pop and lofi profiles got better results simply because the catalog had more of
those songs.
