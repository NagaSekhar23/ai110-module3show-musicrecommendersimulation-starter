"""CSV loading, numeric conversion, malformed rows, and dataset integrity."""
import csv
import logging

import pytest

from src.recommender import DEFAULT_CSV_PATH, load_songs
from tests.conftest import HEADER


# ---- loading & conversion ------------------------------------------------- #
def test_load_songs_returns_list_of_dicts(catalog):
    assert isinstance(catalog, list)
    assert len(catalog) == 20
    assert all(isinstance(song, dict) for song in catalog)


def test_load_songs_converts_numeric_fields(catalog):
    first = catalog[0]
    assert first["id"] == 1 and isinstance(first["id"], int)
    for field in ("energy", "tempo_bpm", "valence", "danceability", "acousticness"):
        assert isinstance(first[field], float), field
    assert first["energy"] == pytest.approx(0.82)
    assert first["tempo_bpm"] == pytest.approx(118.0)


def test_load_songs_normalises_genre_and_mood_case(write_csv):
    path = write_csv(HEADER + "1,Track,Artist,  POP ,Happy,0.5,100,0.5,0.5,0.5\n")
    [song] = load_songs(path)
    assert song["genre"] == "pop"
    assert song["mood"] == "happy"


def test_load_songs_skips_malformed_rows(write_csv, caplog):
    path = write_csv(
        HEADER
        + "1,Good,Artist,pop,happy,0.5,100,0.5,0.5,0.5\n"
        + "2,Bad Energy,Artist,pop,happy,loud,100,0.5,0.5,0.5\n"   # not a number
        + "3,Too High,Artist,pop,happy,1.5,100,0.5,0.5,0.5\n"      # out of range
        + "4,,Artist,pop,happy,0.5,100,0.5,0.5,0.5\n"              # missing title
        + "5,No Energy,Artist,pop,happy,,100,0.5,0.5,0.5\n"        # missing energy
        + "x,Bad Id,Artist,pop,happy,0.5,100,0.5,0.5,0.5\n"        # bad id
        + "1,Duplicate,Artist,pop,happy,0.5,100,0.5,0.5,0.5\n"     # duplicate id
        + "6,Negative Tempo,Artist,pop,happy,0.5,-10,0.5,0.5,0.5\n"
    )
    with caplog.at_level(logging.WARNING):
        songs = load_songs(path)
    assert [s["title"] for s in songs] == ["Good"]
    assert len([r for r in caplog.records if "Skipping" in r.message]) == 7


def test_load_songs_skips_rows_with_too_many_or_too_few_values(write_csv):
    path = write_csv(
        HEADER
        + "1,Hello, World,Artist,pop,happy,0.5,100,0.5,0.5,0.5\n"  # unquoted comma -> extra value
        + "2,Short Row,Artist,pop\n"                               # too few values
        + "4,Trailing,Artist,pop,happy,0.5,100,0.5,0.5,0.5,EXTRA\n"  # surplus trailing value
        + '3,"Hello, Again",Artist,pop,happy,0.5,100,0.5,0.5,0.5\n'  # quoted comma is fine
    )
    assert [s["title"] for s in load_songs(path)] == ["Hello, Again"]


def test_load_songs_allows_missing_optional_numbers(write_csv):
    path = write_csv(HEADER + "1,Sparse,Artist,pop,happy,0.5,,,,\n")
    [song] = load_songs(path)
    assert song["energy"] == 0.5
    assert song["tempo_bpm"] is None and song["acousticness"] is None


def test_load_songs_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_songs(tmp_path / "nope.csv")


def test_load_songs_missing_required_column_raises(write_csv):
    path = write_csv("id,title,artist,genre\n1,A,B,pop\n")
    with pytest.raises(ValueError, match="missing required column"):
        load_songs(path)


def test_load_songs_empty_file_body_returns_empty_list(write_csv):
    assert load_songs(write_csv(HEADER)) == []


# ---- dataset integrity ---------------------------------------------------- #
def test_dataset_raw_rows_all_parse():
    """Every raw row in data/songs.csv must survive validation (none skipped)."""
    with DEFAULT_CSV_PATH.open(newline="", encoding="utf-8") as handle:
        raw_rows = list(csv.DictReader(handle))
    assert len(load_songs()) == len(raw_rows)


def test_dataset_ids_and_songs_are_unique(catalog):
    ids = [s["id"] for s in catalog]
    assert len(ids) == len(set(ids))
    pairs = [(s["title"].lower(), s["artist"].lower()) for s in catalog]
    assert len(pairs) == len(set(pairs))


def test_dataset_values_in_valid_ranges(catalog):
    for song in catalog:
        for field in ("energy", "valence", "danceability", "acousticness"):
            assert 0.0 <= song[field] <= 1.0, (song["title"], field)
        assert 40 <= song["tempo_bpm"] <= 220, song["title"]


def test_dataset_has_required_profile_genres(catalog):
    genres = {s["genre"] for s in catalog}
    assert {"pop", "lofi", "rock"} <= genres
    assert len(genres) >= 10
