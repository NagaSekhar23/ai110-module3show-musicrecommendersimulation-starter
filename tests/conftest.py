import pytest

from src.recommender import load_songs


@pytest.fixture(scope="session")
def catalog():
    """The real dataset, loaded once for all tests."""
    return load_songs()


@pytest.fixture
def write_csv(tmp_path):
    """Write CSV text to a temporary file and return its path."""
    def _write(text: str):
        path = tmp_path / "songs.csv"
        path.write_text(text, encoding="utf-8")
        return path
    return _write


HEADER = "id,title,artist,genre,mood,energy,tempo_bpm,valence,danceability,acousticness\n"
