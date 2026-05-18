"""NBA 2K Player Rating System - Weighted Position Grades"""

import json
from pathlib import Path

DIR = Path(__file__).parent
CONFIG = json.loads((DIR / "config.json").read_text())
RATINGS = json.loads((DIR / "ratings.json").read_text())

GRADE_VALUES = {g: len(CONFIG["grades"]) - i for i, g in enumerate(CONFIG["grades"])}


def weighted_score(grades, weights):
    total = sum(weights[cat] * GRADE_VALUES[grade] for cat, grade in grades.items())
    return total / sum(weights.values())


def score_to_grade(score):
    for grade, val in GRADE_VALUES.items():
        if score >= val - 0.5:
            return grade
    return CONFIG["grades"][-1]


def print_player(name, positions):
    print(f"\n{'═' * 50}")
    print(f"  {name}")
    print(f"{'═' * 50}")
    for pos, grades in positions.items():
        weights = CONFIG["positions"][pos]
        score = weighted_score(grades, weights)
        overall = score_to_grade(score)
        print(f"\n  [{pos}] Overall: {overall} ({score:.2f})")
        print(f"  {'─' * 44}")
        for cat, grade in grades.items():
            w = weights[cat]
            tier = "★" * w
            print(f"    {cat:<22} {grade:>2}  {tier}")


def print_leaderboard():
    print(f"\n\n{'═' * 50}")
    print(f"  LEADERBOARD BY POSITION")
    print(f"{'═' * 50}")

    by_position = {}
    for name, positions in RATINGS.items():
        for pos, grades in positions.items():
            weights = CONFIG["positions"][pos]
            score = weighted_score(grades, weights)
            by_position.setdefault(pos, []).append((name, score, score_to_grade(score)))

    for pos in CONFIG["positions"]:
        players = by_position.get(pos, [])
        if not players:
            continue
        players.sort(key=lambda x: x[1], reverse=True)
        print(f"\n  {pos}")
        print(f"  {'─' * 44}")
        for i, (name, score, grade) in enumerate(players, 1):
            print(f"    {i}. {name:<22} {grade} ({score:.2f})")


def main():
    print("NBA 2K Player Ratings")
    print(f"Grade scale: {' > '.join(CONFIG['grades'])}")
    print(f"Weights: ★★★ = core  ★★ = defense  ★ = role skill")

    # Show unrated players
    unrated = [p for p in CONFIG["players"] if p not in RATINGS]
    if unrated:
        print(f"\n  Unrated: {', '.join(unrated)}")

    for name in CONFIG["players"]:
        if name in RATINGS:
            print_player(name, RATINGS[name])

    print_leaderboard()


if __name__ == "__main__":
    main()
