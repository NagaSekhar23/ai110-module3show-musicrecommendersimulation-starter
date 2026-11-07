"""Scoring strategies, diversity re-ranking, and unmatched-preference warnings."""
import pytest

from src import main as cli
from src.profiles import CORE_PROFILES
from src.recommender import (
    DEFAULT_WEIGHTS,
    STRATEGIES,
    diversify,
    get_strategy,
    rank_songs,
    recommend_songs,
    unmatched_preferences,
)


def song(id, title, artist, genre, mood="happy", energy=0.5, acousticness=0.5):
    return {"id": id, "title": title, "artist": artist, "genre": genre, "mood": mood,
            "energy": energy, "acousticness": acousticness}


# ---- strategies ----------------------------------------------------------- #
def test_balanced_strategy_is_the_original_recipe():
    assert get_strategy("balanced") == DEFAULT_WEIGHTS
    assert (DEFAULT_WEIGHTS.genre, DEFAULT_WEIGHTS.mood, DEFAULT_WEIGHTS.energy) == (2.0, 1.0, 1.0)


def test_unknown_strategy_raises():
    with pytest.raises(ValueError, match="unknown strategy"):
        get_strategy("random")


def test_each_strategy_emphasises_its_feature():
    assert STRATEGIES["genre_first"].genre == max(vars(STRATEGIES["genre_first"]).values())
    assert STRATEGIES["mood_first"].mood == max(vars(STRATEGIES["mood_first"]).values())
    assert STRATEGIES["energy_focused"].energy == max(vars(STRATEGIES["energy_focused"]).values())


def test_mood_first_prefers_mood_over_genre():
    songs = [song(1, "Genre Only", "A", "pop", mood="sad"), song(2, "Mood Only", "B", "rock", mood="happy")]
    prefs = {"genre": "pop", "mood": "happy"}
    assert recommend_songs(prefs, songs, k=1)[0][0]["title"] == "Genre Only"
    assert recommend_songs(prefs, songs, k=1, weights=STRATEGIES["mood_first"])[0][0]["title"] == "Mood Only"


# ---- diversity ------------------------------------------------------------ #
def test_diversify_demotes_repeated_artist():
    songs = [
        song(1, "A1", "Same", "pop"), song(2, "A2", "Same", "pop"),
        song(3, "B1", "Other", "rock"),
    ]
    ranked = rank_songs({"genre": "pop"}, songs)  # A1=2, A2=2, B1=0
    picked = diversify(ranked, k=3, artist_penalty=3.0, genre_penalty=0.0)
    assert [s["title"] for s, _, _ in picked] == ["A1", "B1", "A2"]
    assert "diversity: artist already listed" in picked[2][2][-1]


def test_diversify_scores_never_increase_down_the_list(catalog):
    results = recommend_songs(CORE_PROFILES["happy_pop"]["prefs"], catalog, k=10, diverse=True)
    scores = [score for _, score, _ in results]
    assert scores == sorted(scores, reverse=True)


def test_diverse_mode_reduces_artist_repeats_on_real_data(catalog):
    prefs = CORE_PROFILES["happy_pop"]["prefs"]
    plain = [s["artist"] for s, _, _ in recommend_songs(prefs, catalog, k=3)]
    diverse = [s["artist"] for s, _, _ in recommend_songs(prefs, catalog, k=3, diverse=True)]
    assert plain.count("Neon Echo") == 2
    assert diverse.count("Neon Echo") == 1


def test_diverse_mode_returns_same_songs_when_k_is_whole_catalog(catalog):
    prefs = CORE_PROFILES["chill_lofi"]["prefs"]
    plain = {s["id"] for s, _, _ in recommend_songs(prefs, catalog, k=len(catalog))}
    diverse = {s["id"] for s, _, _ in recommend_songs(prefs, catalog, k=len(catalog), diverse=True)}
    assert plain == diverse


def test_diverse_mode_does_not_change_default_output(catalog):
    prefs = CORE_PROFILES["intense_rock"]["prefs"]
    assert recommend_songs(prefs, catalog, k=5) == recommend_songs(prefs, catalog, k=5, diverse=False)


# ---- unmatched preferences ------------------------------------------------ #
def test_unmatched_preferences_flags_missing_genre(catalog):
    assert unmatched_preferences({"genre": "k-pop", "mood": "happy"}, catalog) == [
        "no song in the catalog has genre 'k-pop'"
    ]


def test_unmatched_preferences_empty_when_all_present(catalog):
    assert unmatched_preferences(CORE_PROFILES["happy_pop"]["prefs"], catalog) == []


def test_cli_strategy_and_diverse_flags(capsys):
    assert cli.main(["--profile", "happy_pop", "--strategy", "mood_first", "--diverse"]) == 0
    out = capsys.readouterr().out
    assert "strategy=mood_first, diverse" in out


def test_cli_warns_about_unknown_genre(capsys):
    assert cli.main(["--profile", "unknown_genre"]) == 0
    assert "no song in the catalog has genre 'k-pop'" in capsys.readouterr().out
