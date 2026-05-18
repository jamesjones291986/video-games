"""Generate initial data.json from local ratings.json (no Google Sheets needed)."""

import json
from pathlib import Path

DIR = Path(__file__).parent
CONFIG = json.loads((DIR / "config.json").read_text())
RATINGS = json.loads((DIR / "ratings.json").read_text())
OUTPUT = DIR.parent.parent / "docs" / "data.json"

GRADE_VALUES = {g: len(CONFIG["grades"]) - i for i, g in enumerate(CONFIG["grades"])}


def score_to_grade(score):
    for grade, val in GRADE_VALUES.items():
        if score >= val - 0.5:
            return grade
    return CONFIG["grades"][-1]


def main():
    results = {}
    for player, positions in RATINGS.items():
        results[player] = {}
        for pos, grades in positions.items():
            weights = CONFIG["positions"][pos]
            total = sum(weights[c] * GRADE_VALUES[g] for c, g in grades.items())
            weight_sum = sum(weights[c] for c in grades)
            score = total / weight_sum
            results[player][pos] = {
                "grades": grades,
                "overall": score_to_grade(score),
                "score": round(score, 2),
                "vote_count": 1,
            }

    leaderboard = {}
    for player, positions in results.items():
        for pos, data in positions.items():
            leaderboard.setdefault(pos, []).append({
                "player": player,
                "overall": data["overall"],
                "score": data["score"],
                "vote_count": data["vote_count"],
            })
    for pos in leaderboard:
        leaderboard[pos].sort(key=lambda x: x["score"], reverse=True)

    output = {
        "players": results,
        "leaderboard": leaderboard,
        "config": {
            "grades": CONFIG["grades"],
            "positions": CONFIG["positions"],
            "players": CONFIG["players"],
            "form_url": CONFIG.get("form_url", ""),
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2))
    print(f"Written to {OUTPUT}")


if __name__ == "__main__":
    main()
