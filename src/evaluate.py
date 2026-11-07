"""
Evaluation script: runs every profile and the weight-shift experiment.

    python -m src.evaluate                  # full report
    python -m src.evaluate --section core   # only the three core profiles

Sections:
  core         top 5 for the three core profiles (original weights)
  adversarial  top 5 for the edge-case profiles (original weights)
  experiment   original vs. experimental weights, side by side
  strategies   Happy Pop Lover under every strategy, with and without diversity
"""

import argparse
import sys
from collections import Counter
from typing import Dict, List, Optional, Sequence

from src.main import print_profile_results
from src.profiles import ADVERSARIAL_PROFILES, ALL_PROFILES, CORE_PROFILES
from src.recommender import (
    DEFAULT_WEIGHTS,
    EXPERIMENT_WEIGHTS,
    STRATEGIES,
    ScoringWeights,
    load_songs,
    recommend_songs,
)


def _weights_label(weights: ScoringWeights) -> str:
    return (f"genre={weights.genre}, mood={weights.mood}, "
            f"energy={weights.energy}, acoustic={weights.acoustic}")


def run_profiles(profiles: Dict[str, Dict], songs: List[Dict], k: int = 5) -> None:
    for profile in profiles.values():
        results = recommend_songs(profile["prefs"], songs, k=k)
        print_profile_results(profile["name"], profile["prefs"], results)


def compare_rankings(baseline: List[str], experiment: List[str]) -> List[str]:
    """Describe how a top-k list changed between two runs."""
    notes = []
    for title in experiment:
        if title not in baseline:
            notes.append(f"NEW  #{experiment.index(title) + 1} {title}")
    for title in baseline:
        if title not in experiment:
            notes.append(f"OUT  (was #{baseline.index(title) + 1}) {title}")
        elif baseline.index(title) != experiment.index(title):
            notes.append(f"MOVE #{baseline.index(title) + 1} -> #{experiment.index(title) + 1} {title}")
    return notes or ["no change in the top 5"]


def run_experiment(songs: List[Dict], k: int = 5) -> None:
    print(f"Original weights:     {_weights_label(DEFAULT_WEIGHTS)}")
    print(f"Experimental weights: {_weights_label(EXPERIMENT_WEIGHTS)}\n")
    for profile in ALL_PROFILES.values():
        base = recommend_songs(profile["prefs"], songs, k=k, weights=DEFAULT_WEIGHTS)
        exp = recommend_songs(profile["prefs"], songs, k=k, weights=EXPERIMENT_WEIGHTS)
        base_titles = [s["title"] for s, _, _ in base]
        exp_titles = [s["title"] for s, _, _ in exp]
        print(f"--- {profile['name']} ---")
        print(f"{'rank':<5}{'original (score)':<38}{'experimental (score)':<38}")
        for i in range(k):
            left = f"{base_titles[i]} ({base[i][1]:.2f})" if i < len(base) else ""
            right = f"{exp_titles[i]} ({exp[i][1]:.2f})" if i < len(exp) else ""
            print(f"{i + 1:<5}{left:<38}{right:<38}")
        for note in compare_rankings(base_titles, exp_titles):
            print(f"     {note}")
        print()


def run_strategies(songs: List[Dict], profile_key: str = "happy_pop", k: int = 5) -> None:
    profile = ALL_PROFILES[profile_key]
    print(f"Profile: {profile['name']}\n")
    for name, weights in STRATEGIES.items():
        for diverse in (False, True):
            results = recommend_songs(profile["prefs"], songs, k=k, weights=weights, diverse=diverse)
            label = f"{name}{' + diverse' if diverse else ''}"
            ranked = ", ".join(f"{s['title']} ({score:.2f})" for s, score, _ in results)
            print(f"{label:<24} {ranked}")
    print()


def dataset_summary(songs: List[Dict]) -> None:
    genres = Counter(s["genre"] for s in songs)
    moods = Counter(s["mood"] for s in songs)
    artists = Counter(s["artist"] for s in songs)
    print(f"Songs: {len(songs)}")
    print("Genres: " + ", ".join(f"{g}={n}" for g, n in genres.most_common()))
    print("Moods:  " + ", ".join(f"{m}={n}" for m, n in moods.most_common()))
    repeated = {a: n for a, n in artists.items() if n > 1}
    print("Artists with more than one song: " + ", ".join(f"{a}={n}" for a, n in repeated.items()))
    print()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the recommender.")
    parser.add_argument("--section", choices=["all", "data", "core", "adversarial", "experiment", "strategies"], default="all")
    args = parser.parse_args(argv)

    songs = load_songs()
    sections = {
        "data": ("DATASET SUMMARY", lambda: dataset_summary(songs)),
        "core": ("CORE PROFILES (original weights)", lambda: run_profiles(CORE_PROFILES, songs)),
        "adversarial": ("ADVERSARIAL PROFILES (original weights)", lambda: run_profiles(ADVERSARIAL_PROFILES, songs)),
        "experiment": ("EXPERIMENT: halve genre weight, double energy weight", lambda: run_experiment(songs)),
        "strategies": ("SCORING STRATEGIES AND DIVERSITY", lambda: run_strategies(songs)),
    }
    chosen = list(sections) if args.section == "all" else [args.section]
    for key in chosen:
        title, run = sections[key]
        print(f"\n######## {title} ########\n")
        run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
