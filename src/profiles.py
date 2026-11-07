"""
User taste profiles used by the CLI, the evaluation script, and the tests.

Each profile is a plain dictionary so it can be passed straight into
``score_song`` / ``recommend_songs``. Supported keys:

- ``genre``          (str)   favourite genre, e.g. "pop"
- ``mood``           (str)   favourite mood, e.g. "happy"
- ``energy``         (float) target energy between 0.0 (calm) and 1.0 (intense)
- ``likes_acoustic`` (bool)  optional; True favours acoustic songs,
                             False favours produced/electronic songs

Any key may be left out. Missing preferences are simply not scored.
"""

from typing import Dict

# The three core profiles required by the assignment.
CORE_PROFILES: Dict[str, Dict] = {
    "happy_pop": {
        "name": "Happy Pop Lover",
        "prefs": {"genre": "pop", "mood": "happy", "energy": 0.80, "likes_acoustic": False},
    },
    "chill_lofi": {
        "name": "Chill Lofi Listener",
        "prefs": {"genre": "lofi", "mood": "chill", "energy": 0.38, "likes_acoustic": True},
    },
    "intense_rock": {
        "name": "Intense Rock Listener",
        "prefs": {"genre": "rock", "mood": "intense", "energy": 0.90, "likes_acoustic": False},
    },
}

# "Edge case" profiles designed to stress-test the scoring rule.
ADVERSARIAL_PROFILES: Dict[str, Dict] = {
    "high_energy_sad": {
        "name": "High Energy + Sad Mood",
        "prefs": {"genre": "pop", "mood": "sad", "energy": 0.90},
    },
    "low_energy_rock": {
        "name": "Low Energy + Intense Rock",
        "prefs": {"genre": "rock", "mood": "intense", "energy": 0.15},
    },
    "unknown_genre": {
        "name": "Genre Not In Dataset (k-pop)",
        "prefs": {"genre": "k-pop", "mood": "happy", "energy": 0.70},
    },
    "conflicting": {
        "name": "Conflicting: Calm Classical but Euphoric + Max Energy",
        "prefs": {"genre": "classical", "mood": "euphoric", "energy": 1.0, "likes_acoustic": True},
    },
}

ALL_PROFILES: Dict[str, Dict] = {**CORE_PROFILES, **ADVERSARIAL_PROFILES}

DEFAULT_PROFILE_KEY = "happy_pop"
