"""User profiles, end-to-end behaviour, and the command-line interface."""
import pytest

from src import main as cli
from src.profiles import ALL_PROFILES, CORE_PROFILES, DEFAULT_PROFILE_KEY
from src.recommender import recommend_songs


def titles(results):
    return [song["title"] for song, _, _ in results]


# ---- profile sanity (integration) ----------------------------------------- #
def test_all_profiles_produce_five_results(catalog):
    for key, profile in ALL_PROFILES.items():
        assert len(recommend_songs(profile["prefs"], catalog, k=5)) == 5, key


def test_happy_pop_top_pick_is_happy_pop(catalog):
    top, _, _ = recommend_songs(CORE_PROFILES["happy_pop"]["prefs"], catalog, k=1)[0]
    assert (top["genre"], top["mood"]) == ("pop", "happy")


def test_chill_lofi_top_three_are_lofi(catalog):
    results = recommend_songs(CORE_PROFILES["chill_lofi"]["prefs"], catalog, k=3)
    assert all(song["genre"] == "lofi" for song, _, _ in results)
    assert results[0][0]["mood"] == "chill"


def test_intense_rock_top_two_are_rock(catalog):
    results = recommend_songs(CORE_PROFILES["intense_rock"]["prefs"], catalog, k=2)
    assert all(song["genre"] == "rock" for song, _, _ in results)


def test_unknown_genre_still_returns_mood_and_energy_matches(catalog):
    results = recommend_songs(ALL_PROFILES["unknown_genre"]["prefs"], catalog, k=5)
    assert not any("genre match" in why for _, _, why in results)
    assert results[0][0]["mood"] == "happy"


# ---- CLI ------------------------------------------------------------------ #
def test_cli_runs_with_explicit_profile(capsys):
    assert cli.main(["--profile", "chill_lofi", "--k", "3"]) == 0
    out = capsys.readouterr().out
    assert "Loaded 20 songs" in out
    assert "Chill Lofi Listener" in out
    assert "Library Rain" in out
    assert "genre match: lofi" in out


def test_cli_defaults_without_terminal(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert cli.main([]) == 0
    assert "Happy Pop Lover" in capsys.readouterr().out


def test_cli_rejects_negative_k(capsys):
    assert cli.main(["--k", "-2"]) == 2
    assert "must be zero or a positive" in capsys.readouterr().err


def test_cli_rejects_unknown_profile():
    with pytest.raises(SystemExit):
        cli.main(["--profile", "does_not_exist"])


def test_cli_list_profiles(capsys):
    assert cli.main(["--list-profiles"]) == 0
    out = capsys.readouterr().out
    for key in ALL_PROFILES:
        assert key in out


def fake_input(answers):
    answers = iter(answers)

    def _input(prompt=""):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError
    return _input


def test_menu_accepts_number(capsys):
    assert cli.choose_profile_interactively(fake_input(["2"])) == list(ALL_PROFILES)[1]


def test_menu_accepts_profile_key():
    assert cli.choose_profile_interactively(fake_input(["intense_rock"])) == "intense_rock"


def test_menu_reprompts_after_invalid_input(capsys):
    assert cli.choose_profile_interactively(fake_input(["banana", "99", "3"])) == list(ALL_PROFILES)[2]
    assert capsys.readouterr().out.count("not a valid choice") == 2


def test_menu_enter_uses_default():
    assert cli.choose_profile_interactively(fake_input([""])) == DEFAULT_PROFILE_KEY


def test_menu_falls_back_to_default_after_too_many_errors(capsys):
    assert cli.choose_profile_interactively(fake_input(["x", "y", "z"])) == DEFAULT_PROFILE_KEY
    assert "Using default profile" in capsys.readouterr().out


def test_menu_handles_end_of_input():
    assert cli.choose_profile_interactively(fake_input([])) == DEFAULT_PROFILE_KEY


def test_format_recommendations_empty():
    assert "No recommendations" in cli.format_recommendations([])


def test_evaluate_script_runs(capsys):
    from src import evaluate
    assert evaluate.main([]) == 0
    out = capsys.readouterr().out
    assert "EXPERIMENT" in out and "Intense Rock Listener" in out


def test_compare_rankings_reports_moves():
    from src.evaluate import compare_rankings
    notes = compare_rankings(["A", "B", "C"], ["B", "A", "D"])
    assert "NEW  #3 D" in notes
    assert "OUT  (was #3) C" in notes
    assert "MOVE #1 -> #2 A" in notes
