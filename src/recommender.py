"""
Content-based music recommender.

The pipeline has three clearly separated steps:

1. ``load_songs``      read the CSV catalog into a list of dictionaries
2. ``score_song``      judge ONE song against ONE user's preferences
3. ``recommend_songs`` score EVERY song, sort them, and return the top ``k``

``Song``, ``UserProfile`` and ``Recommender`` provide an object-oriented
wrapper around the same logic (used by the original starter tests).
"""

import csv
import logging
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

logger = logging.getLogger(__name__)

# Resolve the dataset path relative to this file, so the program works no
# matter which directory it is launched from (and no absolute paths are needed).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "songs.csv"

TEXT_FIELDS = ("title", "artist", "genre", "mood")
UNIT_INTERVAL_FIELDS = ("energy", "valence", "danceability", "acousticness")  # must be 0..1
REQUIRED_COLUMNS = ("id", "title", "genre", "mood", "energy")


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #
@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float


@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool

    def to_prefs(self) -> Dict:
        """Convert to the plain-dictionary format used by ``score_song``."""
        return {
            "genre": self.favorite_genre,
            "mood": self.favorite_mood,
            "energy": self.target_energy,
            "likes_acoustic": self.likes_acoustic,
        }


@dataclass(frozen=True)
class ScoringWeights:
    """
    How many points each feature is worth at most.

    genre    - awarded in full when the song's genre equals the user's genre
    mood     - awarded in full when the song's mood equals the user's mood
    energy   - multiplied by energy similarity (1.0 = identical energy)
    acoustic - multiplied by how well acousticness fits ``likes_acoustic``
    """
    genre: float = 2.0
    mood: float = 1.0
    energy: float = 1.0
    acoustic: float = 0.5


# The original recipe (genre +2.0, mood +1.0, energy up to +1.0).
DEFAULT_WEIGHTS = ScoringWeights()

# Phase 6 experiment: genre matters less, energy matters more.
EXPERIMENT_WEIGHTS = ScoringWeights(genre=1.0, mood=1.0, energy=2.0, acoustic=0.5)

# Strategy pattern: each named strategy is just a different set of weights.
# The scoring code never changes; you swap which weights it uses.
STRATEGIES: Dict[str, ScoringWeights] = {
    "balanced": DEFAULT_WEIGHTS,
    "genre_first": ScoringWeights(genre=3.0, mood=1.0, energy=0.5, acoustic=0.25),
    "mood_first": ScoringWeights(genre=1.0, mood=2.5, energy=1.0, acoustic=0.5),
    "energy_focused": ScoringWeights(genre=0.5, mood=0.5, energy=3.0, acoustic=0.5),
}
DEFAULT_STRATEGY = "balanced"


def get_strategy(name: str) -> ScoringWeights:
    """Look up a scoring strategy by name (raises ValueError if unknown)."""
    try:
        return STRATEGIES[name]
    except KeyError:
        raise ValueError(f"unknown strategy {name!r}; choose from {', '.join(STRATEGIES)}") from None


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def _parse_row(row: Mapping[str, Optional[str]]) -> Dict:
    """Convert one raw CSV row (all strings) into a typed song dictionary.

    Raises ValueError if the row is missing data or has out-of-range values.
    """
    song: Dict = {}

    raw_id = (row.get("id") or "").strip()
    song["id"] = int(raw_id)  # ValueError if blank or not an integer

    for field in TEXT_FIELDS:
        song[field] = (row.get(field) or "").strip()
    for field in ("title", "genre", "mood"):
        if not song[field]:
            raise ValueError(f"missing {field}")
    # Normalise categorical fields so "Pop" and "pop " compare equal.
    song["genre"] = song["genre"].lower()
    song["mood"] = song["mood"].lower()

    for field in UNIT_INTERVAL_FIELDS + ("tempo_bpm",):
        raw = (row.get(field) or "").strip()
        if raw == "":
            if field == "energy":
                raise ValueError("missing energy")
            song[field] = None  # optional feature, simply unknown
            continue
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError(f"{field} is not a finite number")
        if field in UNIT_INTERVAL_FIELDS and not 0.0 <= value <= 1.0:
            raise ValueError(f"{field}={value} is outside 0..1")
        if field == "tempo_bpm" and value <= 0:
            raise ValueError(f"tempo_bpm={value} must be positive")
        song[field] = value

    return song


def load_songs(csv_path=DEFAULT_CSV_PATH) -> List[Dict]:
    """Load songs from a CSV file into a list of dictionaries.

    Numeric columns are converted to ``int`` (id) or ``float`` (energy,
    tempo_bpm, valence, danceability, acousticness). Genre and mood are
    lower-cased. Rows that are malformed (non-numeric values, values outside
    0..1, missing title/genre/mood/energy, or a duplicate id) are skipped with
    a logged warning instead of crashing the program.

    Args:
        csv_path: path to the CSV file. Defaults to ``data/songs.csv``.

    Returns:
        A list of song dictionaries, in file order.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the header is missing required columns.
    """
    path = Path(csv_path)
    songs: List[Dict] = []
    seen_ids = set()

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        missing = [col for col in REQUIRED_COLUMNS if col not in header]
        if missing:
            raise ValueError(f"{path} is missing required column(s): {', '.join(missing)}")

        for line_number, row in enumerate(reader, start=2):  # line 1 is the header
            try:
                song = _parse_row(row)
            except (ValueError, TypeError) as exc:
                logger.warning("Skipping %s line %d: %s", path.name, line_number, exc)
                continue
            if song["id"] in seen_ids:
                logger.warning("Skipping %s line %d: duplicate id %d", path.name, line_number, song["id"])
                continue
            seen_ids.add(song["id"])
            songs.append(song)

    return songs


# --------------------------------------------------------------------------- #
# Scoring a single song
# --------------------------------------------------------------------------- #
def _clean_text(value) -> Optional[str]:
    """Lower-case and strip a text preference; treat blank/None as missing."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"expected text, got {type(value).__name__}")
    value = value.strip().lower()
    return value or None


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _validate_prefs(user_prefs: Mapping) -> Dict:
    """Check user preferences and return a cleaned copy.

    Missing preferences become ``None`` (they are skipped during scoring).
    Invalid ones raise an error, because silently ignoring a typo such as
    ``energy=8`` would produce misleading recommendations.
    """
    if not isinstance(user_prefs, Mapping):
        raise TypeError("user_prefs must be a dictionary")

    energy = user_prefs.get("energy")
    if energy is not None:
        if not _is_number(energy):
            raise ValueError(f"energy preference must be a number, got {energy!r}")
        if not 0.0 <= energy <= 1.0:
            raise ValueError(f"energy preference must be between 0 and 1, got {energy}")

    likes_acoustic = user_prefs.get("likes_acoustic")
    if likes_acoustic is not None and not isinstance(likes_acoustic, bool):
        raise ValueError(f"likes_acoustic must be True or False, got {likes_acoustic!r}")

    return {
        "genre": _clean_text(user_prefs.get("genre")),
        "mood": _clean_text(user_prefs.get("mood")),
        "energy": float(energy) if energy is not None else None,
        "likes_acoustic": likes_acoustic,
    }


def _song_number(song: Mapping, field: str) -> Optional[float]:
    """Read a numeric song attribute, returning None if missing or invalid."""
    value = song.get(field)
    return float(value) if _is_number(value) else None


def _song_text(song: Mapping, field: str) -> Optional[str]:
    """Read a text song attribute, returning None if missing or not text."""
    value = song.get(field)
    return _clean_text(value) if isinstance(value, str) else None


def score_song(user_prefs: Dict, song: Dict, weights: ScoringWeights = DEFAULT_WEIGHTS) -> Tuple[float, List[str]]:
    """Score a single song against a user's preferences.

    Recipe (default weights):
      * genre match                         +2.0
      * mood match                          +1.0
      * energy similarity                   +1.0 x (1 - |target - song energy|)
      * acoustic fit (only if the user set likes_acoustic)
                                            +0.5 x acousticness       (likes acoustic)
                                            +0.5 x (1 - acousticness) (dislikes acoustic)

    Preferences that are missing are skipped. Song attributes that are missing
    contribute nothing.

    Args:
        user_prefs: dict with optional keys ``genre``, ``mood``, ``energy``
            (0..1) and ``likes_acoustic`` (bool).
        song: a song dictionary as produced by ``load_songs``.
        weights: how much each feature is worth.

    Returns:
        ``(score, reasons)`` where ``reasons`` is a list of human-readable
        strings such as ``"genre match: pop (+2.00)"``.

    Raises:
        TypeError / ValueError: if the preferences are invalid.
    """
    prefs = _validate_prefs(user_prefs)
    score = 0.0
    reasons: List[str] = []

    song_genre = _song_text(song, "genre")
    if prefs["genre"] is not None and song_genre == prefs["genre"]:
        score += weights.genre
        reasons.append(f"genre match: {song_genre} ({weights.genre:+.2f})")

    song_mood = _song_text(song, "mood")
    if prefs["mood"] is not None and song_mood == prefs["mood"]:
        score += weights.mood
        reasons.append(f"mood match: {song_mood} ({weights.mood:+.2f})")

    song_energy = _song_number(song, "energy")
    if prefs["energy"] is not None and song_energy is not None:
        similarity = max(0.0, 1.0 - abs(prefs["energy"] - song_energy))
        points = weights.energy * similarity
        score += points
        reasons.append(
            f"energy similarity: {song_energy:.2f} vs target {prefs['energy']:.2f} ({points:+.2f})"
        )

    acousticness = _song_number(song, "acousticness")
    if prefs["likes_acoustic"] is not None and acousticness is not None:
        fit = acousticness if prefs["likes_acoustic"] else 1.0 - acousticness
        points = weights.acoustic * fit
        score += points
        label = "acoustic" if prefs["likes_acoustic"] else "produced/electronic"
        reasons.append(f"{label} sound fit: acousticness {acousticness:.2f} ({points:+.2f})")

    # Round away floating-point noise (e.g. 3.9999999) so ties compare equal.
    return round(score, 6), reasons


# --------------------------------------------------------------------------- #
# Ranking the whole catalog
# --------------------------------------------------------------------------- #
def _tie_break_key(song: Mapping) -> Tuple:
    """Deterministic secondary ordering: title, then artist, then id."""
    return (
        str(song.get("title", "")).lower(),
        str(song.get("artist", "")).lower(),
        str(song.get("id", "")),
    )


def rank_songs(user_prefs: Dict, songs: List[Dict], weights: ScoringWeights = DEFAULT_WEIGHTS) -> List[Tuple[Dict, float, List[str]]]:
    """Score every song and return ALL of them sorted best-first.

    Each item is ``(song_copy, score, reasons)``. Songs are copied so the
    caller's catalog is never modified. Ties are broken alphabetically by
    title (then artist, then id) so the output is always the same.
    """
    scored = []
    for song in songs:
        score, reasons = score_song(user_prefs, song, weights)
        scored.append((dict(song), score, reasons))
    scored.sort(key=lambda item: (-item[1], _tie_break_key(item[0])))
    return scored


def _validate_k(k) -> int:
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError(f"k must be an integer, got {k!r}")
    if k < 0:
        raise ValueError(f"k must be zero or positive, got {k}")
    return k


ARTIST_REPEAT_PENALTY = 0.75
GENRE_REPEAT_PENALTY = 0.35


def diversify(ranked: List[Tuple[Dict, float, List[str]]], k: int,
              artist_penalty: float = ARTIST_REPEAT_PENALTY,
              genre_penalty: float = GENRE_REPEAT_PENALTY) -> List[Tuple[Dict, float, List[str]]]:
    """Re-rank so the top ``k`` is not dominated by one artist or genre.

    Greedy approach: pick songs one at a time. Before each pick, every
    remaining song loses ``artist_penalty`` for each already-picked song by
    the same artist, and ``genre_penalty`` for each already-picked song in the
    same genre. The best adjusted score wins. Penalties are listed in the
    reasons so the adjustment is transparent.
    """
    remaining = list(ranked)
    picked: List[Tuple[Dict, float, List[str]]] = []
    while remaining and len(picked) < k:
        best_index, best_item = None, None
        for index, (song, score, reasons) in enumerate(remaining):
            same_artist = sum(1 for p, _, _ in picked if p.get("artist") and p.get("artist") == song.get("artist"))
            same_genre = sum(1 for p, _, _ in picked if p.get("genre") == song.get("genre"))
            penalty = artist_penalty * same_artist + genre_penalty * same_genre
            adjusted = round(score - penalty, 6)
            new_reasons = list(reasons)
            if same_artist and artist_penalty:
                new_reasons.append(f"diversity: artist already listed x{same_artist} ({-artist_penalty * same_artist:+.2f})")
            if same_genre and genre_penalty:
                new_reasons.append(f"diversity: genre already listed x{same_genre} ({-genre_penalty * same_genre:+.2f})")
            candidate = (song, adjusted, new_reasons)
            # remaining is already in deterministic order, so strict ">" keeps ties stable
            if best_item is None or adjusted > best_item[1]:
                best_index, best_item = index, candidate
        picked.append(best_item)
        remaining.pop(best_index)
    return picked


def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5,
                    weights: ScoringWeights = DEFAULT_WEIGHTS,
                    diverse: bool = False) -> List[Tuple[Dict, float, str]]:
    """Return the top ``k`` songs for a user.

    Args:
        user_prefs: preference dictionary (see ``score_song``).
        songs: the catalog, e.g. from ``load_songs``. It is not modified.
        k: how many recommendations to return. ``0`` returns an empty list;
           a ``k`` larger than the catalog returns every song.
        weights: scoring weights to use (see ``STRATEGIES``).
        diverse: if True, apply ``diversify`` to limit artist/genre repeats.

    Returns:
        A list of ``(song, score, explanation)`` tuples, highest score first.
        ``explanation`` is the reasons joined with "; ".

    Raises:
        TypeError / ValueError: for invalid ``k`` or invalid preferences.
    """
    k = _validate_k(k)
    _validate_prefs(user_prefs)  # report bad preferences even for an empty catalog
    if not songs or k == 0:
        return []

    ranked = rank_songs(user_prefs, songs, weights)
    top = diversify(ranked, k) if diverse else ranked[:k]
    return [(song, score, "; ".join(reasons)) for song, score, reasons in top]


def unmatched_preferences(user_prefs: Dict, songs: List[Dict]) -> List[str]:
    """List genre/mood preferences that no song in the catalog has.

    Useful for warning the user that a preference cannot be satisfied
    (e.g. asking for "k-pop" when the catalog has none).
    """
    prefs = _validate_prefs(user_prefs)
    warnings = []
    for field in ("genre", "mood"):
        wanted = prefs[field]
        if wanted is not None and not any(_song_text(s, field) == wanted for s in songs):
            warnings.append(f"no song in the catalog has {field} '{wanted}'")
    return warnings


# --------------------------------------------------------------------------- #
# Object-oriented wrapper
# --------------------------------------------------------------------------- #
class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """

    def __init__(self, songs: List[Song], weights: ScoringWeights = DEFAULT_WEIGHTS):
        self.songs = songs
        self.weights = weights

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        """Return the top ``k`` Song objects for ``user``, best first."""
        k = _validate_k(k)
        prefs = user.to_prefs()
        scored = []
        for song in self.songs:
            score, _ = score_song(prefs, asdict(song), self.weights)
            scored.append((song, score))
        scored.sort(key=lambda item: (-item[1], _tie_break_key(asdict(item[0]))))
        return [song for song, _ in scored[:k]]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Return a one-line, human-readable explanation of a song's score."""
        score, reasons = score_song(user.to_prefs(), asdict(song), self.weights)
        if not reasons:
            return f"Score {score:.2f}: no preferences matched this song."
        return f"Score {score:.2f}: " + "; ".join(reasons)
