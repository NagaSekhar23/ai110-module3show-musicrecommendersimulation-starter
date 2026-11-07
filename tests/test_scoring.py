"""score_song, rank_songs and recommend_songs behaviour."""
import copy

import pytest

from src.recommender import (
    DEFAULT_WEIGHTS,
    EXPERIMENT_WEIGHTS,
    rank_songs,
    recommend_songs,
    score_song,
)


def make_song(**overrides):
    song = {
        "id": 1, "title": "Song", "artist": "Artist", "genre": "pop", "mood": "happy",
        "energy": 0.8, "tempo_bpm": 120.0, "valence": 0.8, "danceability": 0.8, "acousticness": 0.2,
    }
    song.update(overrides)
    return song


# ---- individual components ----------------------------------------------- #
def test_genre_match_adds_two_points():
    score, reasons = score_song({"genre": "pop"}, make_song())
    assert score == pytest.approx(2.0)
    assert reasons == ["genre match: pop (+2.00)"]


def test_genre_match_is_case_insensitive():
    score, _ = score_song({"genre": " POP "}, make_song())
    assert score == pytest.approx(2.0)


def test_genre_mismatch_adds_nothing():
    assert score_song({"genre": "rock"}, make_song()) == (0.0, [])


def test_mood_match_adds_one_point():
    score, reasons = score_song({"mood": "happy"}, make_song())
    assert score == pytest.approx(1.0)
    assert reasons == ["mood match: happy (+1.00)"]


def test_mood_mismatch_adds_nothing():
    assert score_song({"mood": "sad"}, make_song())[0] == 0.0


@pytest.mark.parametrize(
    "target, song_energy, expected",
    [(0.8, 0.8, 1.0), (0.8, 0.6, 0.8), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.3, 0.45, 0.85)],
)
def test_energy_similarity(target, song_energy, expected):
    score, reasons = score_song({"energy": target}, make_song(energy=song_energy))
    assert score == pytest.approx(expected)
    assert reasons[0].startswith("energy similarity")


def test_energy_similarity_is_symmetric():
    a, _ = score_song({"energy": 0.2}, make_song(energy=0.7))
    b, _ = score_song({"energy": 0.7}, make_song(energy=0.2))
    assert a == pytest.approx(b)


@pytest.mark.parametrize("likes, expected", [(True, 0.5 * 0.2), (False, 0.5 * 0.8)])
def test_acoustic_preference(likes, expected):
    score, _ = score_song({"likes_acoustic": likes}, make_song(acousticness=0.2))
    assert score == pytest.approx(expected)


def test_combined_score_matches_recipe():
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.7, "likes_acoustic": False}
    score, reasons = score_song(prefs, make_song(energy=0.8, acousticness=0.2))
    # 2.0 genre + 1.0 mood + (1 - 0.1) energy + 0.5 * 0.8 acoustic
    assert score == pytest.approx(2.0 + 1.0 + 0.9 + 0.4)
    assert len(reasons) == 4


def test_custom_weights_change_score():
    prefs = {"genre": "pop", "energy": 0.8}
    default, _ = score_song(prefs, make_song(), DEFAULT_WEIGHTS)
    experiment, _ = score_song(prefs, make_song(), EXPERIMENT_WEIGHTS)
    assert default == pytest.approx(3.0)       # 2.0 + 1.0
    assert experiment == pytest.approx(3.0)    # 1.0 + 2.0
    _, reasons = score_song({"genre": "pop"}, make_song(), EXPERIMENT_WEIGHTS)
    assert reasons == ["genre match: pop (+1.00)"]


# ---- missing / invalid input --------------------------------------------- #
def test_empty_preferences_score_zero():
    assert score_song({}, make_song()) == (0.0, [])


def test_none_and_blank_preferences_are_treated_as_missing():
    assert score_song({"genre": None, "mood": "  ", "energy": None}, make_song()) == (0.0, [])


def test_song_missing_attributes_contributes_nothing():
    song = {"id": 9, "title": "Bare"}
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.5, "likes_acoustic": True}
    assert score_song(prefs, song) == (0.0, [])


@pytest.mark.parametrize("energy", [1.5, -0.1, "high", True, float("nan")])
def test_invalid_energy_preference_raises(energy):
    with pytest.raises(ValueError):
        score_song({"energy": energy}, make_song())


def test_invalid_likes_acoustic_raises():
    with pytest.raises(ValueError):
        score_song({"likes_acoustic": "yes"}, make_song())


def test_non_dict_preferences_raise():
    with pytest.raises(TypeError):
        score_song(["pop"], make_song())


def test_non_text_genre_preference_raises():
    with pytest.raises(TypeError):
        score_song({"genre": 5}, make_song())


# ---- ranking & top-k ------------------------------------------------------ #
def test_recommend_ranks_highest_score_first(catalog):
    results = recommend_songs({"genre": "pop", "mood": "happy", "energy": 0.8}, catalog, k=5)
    scores = [score for _, score, _ in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0][0]["title"] == "Sunrise City"


def test_recommend_returns_song_score_explanation_tuples(catalog):
    song, score, explanation = recommend_songs({"genre": "lofi"}, catalog, k=1)[0]
    assert isinstance(song, dict) and "title" in song
    assert isinstance(score, float)
    assert isinstance(explanation, str) and "genre match" in explanation


@pytest.mark.parametrize("k", [0, 1, 3, 5, 20])
def test_recommend_returns_exactly_k(catalog, k):
    assert len(recommend_songs({"genre": "pop"}, catalog, k=k)) == k


def test_k_larger_than_catalog_returns_all(catalog):
    assert len(recommend_songs({"genre": "pop"}, catalog, k=100)) == len(catalog)


def test_top_k_is_prefix_of_full_ranking(catalog):
    prefs = {"genre": "rock", "mood": "intense", "energy": 0.9}
    full = [s["id"] for s, _, _ in rank_songs(prefs, catalog)]
    top3 = [s["id"] for s, _, _ in recommend_songs(prefs, catalog, k=3)]
    assert top3 == full[:3]


@pytest.mark.parametrize("k", [-1, 2.5, "5", None, True])
def test_invalid_k_raises(catalog, k):
    with pytest.raises((TypeError, ValueError)):
        recommend_songs({"genre": "pop"}, catalog, k=k)


def test_empty_catalog_returns_empty_list():
    assert recommend_songs({"genre": "pop"}, [], k=5) == []


def test_empty_catalog_still_rejects_bad_prefs():
    with pytest.raises(ValueError):
        recommend_songs({"energy": 9}, [], k=5)


def test_recommend_does_not_mutate_catalog(catalog):
    snapshot = copy.deepcopy(catalog)
    results = recommend_songs({"genre": "pop", "mood": "happy", "energy": 0.8}, catalog, k=5)
    results[0][0]["title"] = "CHANGED"
    assert catalog == snapshot


def test_ties_are_broken_alphabetically_by_title():
    songs = [
        make_song(id=1, title="Zebra"),
        make_song(id=2, title="Apple"),
        make_song(id=3, title="Mango"),
    ]
    results = recommend_songs({"genre": "pop"}, songs, k=3)
    assert [s["title"] for s, _, _ in results] == ["Apple", "Mango", "Zebra"]


def test_ranking_is_deterministic_regardless_of_input_order(catalog):
    prefs = {"genre": "rock", "mood": "intense", "energy": 0.9, "likes_acoustic": False}
    forward = [s["id"] for s, _, _ in recommend_songs(prefs, catalog, k=10)]
    backward = [s["id"] for s, _, _ in recommend_songs(prefs, list(reversed(catalog)), k=10)]
    assert forward == backward


def test_real_tie_in_dataset_is_resolved_by_title(catalog):
    # Broken Amplifier and Storm Runner both score exactly 4.44 for this profile.
    prefs = {"genre": "rock", "mood": "intense", "energy": 0.9, "likes_acoustic": False}
    (a, sa, _), (b, sb, _) = recommend_songs(prefs, catalog, k=2)
    assert sa == pytest.approx(sb)
    assert [a["title"], b["title"]] == ["Broken Amplifier", "Storm Runner"]
