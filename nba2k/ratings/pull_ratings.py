"""Pull ratings from Google Sheets (Form responses) and generate data.json for the site."""

import json
import os
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

DIR = Path(__file__).parent
CONFIG = json.loads((DIR / "config.json").read_text())
OUTPUT = DIR.parent.parent / "docs" / "data.json"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

GRADE_VALUES = {g: len(CONFIG["grades"]) - i for i, g in enumerate(CONFIG["grades"])}

# Column ranges per position (0-indexed from start of grade columns)
# Based on sheet: Timestamp(0), Name(1), Player(2), Position(3), then grades start at 4
# PG: cols 4-9, 3&D: cols 10-12, Lock: cols 13-15, Backend: cols 16-18, Big: cols 19-22
POSITION_COLUMNS = {
    "PG": {"start": 4, "cats": ["Basketball IQ", "Inside Scoring", "Outside Scoring", "Perimeter Defense", "Ball Handling", "Passing/Vision"]},
    "3&D": {"start": 10, "cats": ["Basketball IQ", "Defense", "Outside Scoring"]},
    "Lock": {"start": 13, "cats": ["Basketball IQ", "Defense", "Outside Scoring"]},
    "Backend": {"start": 16, "cats": ["Basketball IQ", "Defense", "Rebounding"]},
    "Big": {"start": 19, "cats": ["Basketball IQ", "Rebounding", "Defense", "Passing/Vision"]},
}


def get_sheet():
    creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", str(DIR / "credentials.json"))
    creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet_id = os.environ.get("SHEET_ID", CONFIG.get("sheet_id", ""))
    return gc.open_by_key(sheet_id).sheet1


def parse_responses(rows):
    if len(rows) < 2:
        return {}

    votes = {}  # {player: {position: {voter: {cat: grade}}}}

    for row in rows[1:]:
        if len(row) < 5:
            continue

        voter = row[1].strip()
        player = row[2].strip()
        position = row[3].strip()

        if not voter or not player or position not in POSITION_COLUMNS:
            continue

        col_info = POSITION_COLUMNS[position]
        grades = {}
        for i, cat in enumerate(col_info["cats"]):
            col_idx = col_info["start"] + i
            if col_idx < len(row):
                val = row[col_idx].strip().upper()
                if val in GRADE_VALUES:
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
