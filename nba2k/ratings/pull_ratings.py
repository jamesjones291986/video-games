"""Pull ratings from Google Sheets (Form responses) and generate data.json for the site."""

import json
import os
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

DIR = Path(__file__).parent
CONFIG = json.loads((DIR / "config.json").read_text())
OUTPUT = DIR / "docs" / "data.json"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

GRADE_VALUES = {g: len(CONFIG["grades"]) - i for i, g in enumerate(CONFIG["grades"])}


def get_sheet():
    creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", str(DIR / "credentials.json"))
    creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet_id = os.environ.get("SHEET_ID", CONFIG.get("sheet_id", ""))
    return gc.open_by_key(sheet_id).sheet1


def parse_responses(rows):
    """Parse form responses handling multi-section column layout.

    Google Forms with sections creates columns for ALL categories across all sections.
    Each row only has values in the columns for the section the voter filled out.
    We match column headers to position categories to figure out which grades belong where.
    """
    if len(rows) < 2:
        return {}

    headers = [h.strip() for h in rows[0]]
    votes = {}  # {player: {position: {voter: {cat: grade}}}}

    # Build a map of column index → (position, category) by matching headers to config
    col_map = {}
    for i, header in enumerate(headers):
        for pos, cats in CONFIG["positions"].items():
            if header in cats:
                col_map.setdefault(i, []).append((pos, header))

    for row in rows[1:]:
        if len(row) < 4:
            continue

        voter = row[1].strip() if len(row) > 1 else ""
        player = row[2].strip() if len(row) > 2 else ""
        position = row[3].strip() if len(row) > 3 else ""

        if not voter or not player or position not in CONFIG["positions"]:
            continue

        expected_cats = set(CONFIG["positions"][position].keys())
        grades = {}

        for i in range(4, len(row)):
            val = row[i].strip().upper() if i < len(row) else ""
            if val not in GRADE_VALUES:
                continue
            if i in col_map:
                for pos, cat in col_map[i]:
                    if pos == position and cat in expected_cats:
                        grades[cat] = val
                        break

        # Fallback: if column matching didn't work, try sequential assignment
        if not grades:
            cats = list(CONFIG["positions"][position].keys())
            grade_vals = [row[i].strip().upper() for i in range(4, len(row))
                         if i < len(row) and row[i].strip().upper() in GRADE_VALUES]
            for cat, val in zip(cats, grade_vals):
                grades[cat] = val

        if grades:
            votes.setdefault(player, {}).setdefault(position, {})[voter] = grades

    return votes


def aggregate(votes):
    results = {}
    for player, positions in votes.items():
        results[player] = {}
        for pos, voter_grades in positions.items():
            weights = CONFIG["positions"][pos]
            categories = list(weights.keys())

            avg_grades = {}
            for cat in categories:
                values = [GRADE_VALUES[vg[cat]] for vg in voter_grades.values() if cat in vg]
                if values:
                    avg_grades[cat] = sum(values) / len(values)

            if avg_grades:
                total = sum(weights[c] * v for c, v in avg_grades.items())
                weight_sum = sum(weights[c] for c in avg_grades)
                overall_score = total / weight_sum
                results[player][pos] = {
                    "grades": {c: score_to_grade(v) for c, v in avg_grades.items()},
                    "overall": score_to_grade(overall_score),
                    "score": round(overall_score, 2),
                    "vote_count": len(voter_grades),
                }
    return results


def score_to_grade(score):
    for grade, val in GRADE_VALUES.items():
        if score >= val - 0.5:
            return grade
    return CONFIG["grades"][-1]


def build_leaderboard(results):
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
    return leaderboard


def main():
    print("Pulling ratings from Google Sheets...")
    sheet = get_sheet()
    rows = sheet.get_all_values()
    print(f"  Found {len(rows) - 1} responses")

    votes = parse_responses(rows)
    results = aggregate(votes)
    leaderboard = build_leaderboard(results)

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
    print(f"  Written to {OUTPUT}")


if __name__ == "__main__":
    main()
