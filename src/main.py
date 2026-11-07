"""
Command line runner for the Music Recommender Simulation.

Usage (from the project root):

    python -m src.main                      # interactive profile menu
    python -m src.main --profile chill_lofi # skip the menu
    python -m src.main --list-profiles      # show available profiles
    python -m src.main --k 3                # change number of results
    python -m src.main --strategy mood_first --diverse
"""

import argparse
import sys
from typing import Dict, List, Optional, Sequence, Tuple

from src.profiles import ALL_PROFILES, DEFAULT_PROFILE_KEY
from src.recommender import (
    DEFAULT_CSV_PATH,
    DEFAULT_STRATEGY,
    STRATEGIES,
    load_songs,
    recommend_songs,
    unmatched_preferences,
)

# Column layout for the results table: (header, width)
COLUMNS = (("#", 2), ("Title", 26), ("Artist", 17), ("Genre", 10), ("Mood", 11), ("Energy", 6), ("Score", 5))
TABLE_WIDTH = sum(width for _, width in COLUMNS) + 2 * (len(COLUMNS) - 1)


def _fit(text: str, width: int) -> str:
    """Truncate text to a column width, marking cut-offs with '~'."""
    text = str(text)
    return text if len(text) <= width else text[: width - 1] + "~"


def describe_prefs(prefs: Dict) -> str:
    """One-line summary of a preference dictionary."""
    parts = []
    for key in ("genre", "mood", "energy", "likes_acoustic"):
        if prefs.get(key) is not None:
            parts.append(f"{key}={prefs[key]}")
    return ", ".join(parts) if parts else "(no preferences)"


def format_recommendations(recommendations: List[Tuple[Dict, float, str]]) -> str:
    """Render recommendations as a fixed-width table with reasons underneath."""
    if not recommendations:
        return "  No recommendations (empty catalog or k=0)."

    header = "  ".join(f"{name:<{width}}" if name not in ("Energy", "Score") else f"{name:>{width}}"
                       for name, width in COLUMNS)
    lines = [header, "-" * TABLE_WIDTH]
    for rank, (song, score, explanation) in enumerate(recommendations, start=1):
        energy = song.get("energy")
        cells = [
            f"{rank:<2}",
            f"{_fit(song.get('title', '?'), 26):<26}",
            f"{_fit(song.get('artist') or 'Unknown', 17):<17}",
            f"{_fit(song.get('genre', '?'), 10):<10}",
            f"{_fit(song.get('mood', '?'), 11):<11}",
            f"{energy:>6.2f}" if isinstance(energy, (int, float)) else f"{'n/a':>6}",
            f"{score:>5.2f}",
        ]
        lines.append("  ".join(cells))
        for reason in (explanation.split("; ") if explanation else ["no matching preferences"]):
            lines.append(f"      - {reason}")
    return "\n".join(lines)


def print_profile_results(profile_name: str, prefs: Dict, recommendations, title_suffix: str = "") -> None:
    """Print a header for one profile followed by its results table."""
    print("=" * TABLE_WIDTH)
    print(f"Profile: {profile_name}{title_suffix}")
    print(f"Preferences: {describe_prefs(prefs)}")
    print("=" * TABLE_WIDTH)
    print(format_recommendations(recommendations))
    print()


def choose_profile_interactively(input_fn=input, max_attempts: int = 3) -> str:
    """Show a numbered menu and return the chosen profile key.

    Invalid entries are rejected with a message. Pressing Enter, hitting
    end-of-input, or exhausting ``max_attempts`` falls back to the default.
    """
    keys = list(ALL_PROFILES)
    default_index = keys.index(DEFAULT_PROFILE_KEY) + 1
    print("Choose a listener profile:")
    for number, key in enumerate(keys, start=1):
        print(f"  {number}. {ALL_PROFILES[key]['name']}  [{key}]")

    for _ in range(max_attempts):
        try:
            answer = input_fn(f"Enter 1-{len(keys)} (Enter = {default_index}): ").strip()
        except EOFError:
            break
        if answer == "":
            return DEFAULT_PROFILE_KEY
        if answer.isdigit() and 1 <= int(answer) <= len(keys):
            return keys[int(answer) - 1]
        if answer in ALL_PROFILES:
            return answer
        print(f"  '{answer}' is not a valid choice. Please enter a number from 1 to {len(keys)}.")

    print(f"Using default profile: {ALL_PROFILES[DEFAULT_PROFILE_KEY]['name']}")
    return DEFAULT_PROFILE_KEY


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Content-based music recommender simulation.")
    parser.add_argument("--profile", choices=list(ALL_PROFILES), help="profile key (skips the menu)")
    parser.add_argument("--k", type=int, default=5, help="number of recommendations (default 5)")
    parser.add_argument("--strategy", choices=list(STRATEGIES), default=DEFAULT_STRATEGY,
                        help="scoring strategy (default: balanced = genre 2, mood 1, energy 1)")
    parser.add_argument("--diverse", action="store_true",
                        help="penalise repeated artists/genres in the top results")
    parser.add_argument("--list-profiles", action="store_true", help="list profiles and exit")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_profiles:
        for key, profile in ALL_PROFILES.items():
            print(f"{key:<16} {profile['name']:<52} {describe_prefs(profile['prefs'])}")
        return 0

    if args.k < 0:
        print("Error: --k must be zero or a positive integer.", file=sys.stderr)
        return 2

    try:
        songs = load_songs(DEFAULT_CSV_PATH)
    except (OSError, ValueError) as exc:
        print(f"Error: could not load songs: {exc}", file=sys.stderr)
        return 1
    print(f"Loaded {len(songs)} songs from {DEFAULT_CSV_PATH.relative_to(DEFAULT_CSV_PATH.parents[1])}\n")

    if args.profile:
        profile_key = args.profile
    elif sys.stdin.isatty():
        profile_key = choose_profile_interactively()
        print()
    else:
        profile_key = DEFAULT_PROFILE_KEY
        print(f"No --profile given and no interactive terminal; using default '{profile_key}'.\n")

    profile = ALL_PROFILES[profile_key]
    for warning in unmatched_preferences(profile["prefs"], songs):
        print(f"Note: {warning}, so that preference cannot add points.")
    recommendations = recommend_songs(profile["prefs"], songs, k=args.k,
                                      weights=STRATEGIES[args.strategy], diverse=args.diverse)
    suffix = f"  (top {args.k}, strategy={args.strategy}{', diverse' if args.diverse else ''})"
    print_profile_results(profile["name"], profile["prefs"], recommendations, title_suffix=suffix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
