"""Pull ratings from Google Sheets (Form responses) and generate data.json for the site.

Auto-detects column structure from the sheet data itself — if you change the form,
the script adapts. Only weights in config.json need manual updates.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

DIR = Path(__file__).parent
CONFIG = json.loads((DIR / "config.json").read_text())
OUTPUT = DIR.parent.parent / "docs" / "data.json"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

GRADE_VALUES = {g: len(CONFIG["grades"]) - i for i, g in enumerate(CONFIG["grades"])}
VALID_GRADES = set(GRADE_VALUES.keys())


def get_sheet():
    creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", str(DIR / "credentials.json"))
    creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet_id = os.environ.get("SHEET_ID", CONFIG.get("sheet_id", ""))
    return gc.open_by_key(sheet_id).sheet1


def detect_columns(rows):
    """Auto-detect which columns belong to which position by looking at actual data."""
    headers = rows[0]
    position_cols = {}

    for row in rows[1:]:
        if len(row) < 5:
            continue
        position = row[3].strip()
        if not position:
            continue

        for i in range(4, len(row)):
            if i < len(row) and row[i].strip().upper() in VALID_GRADES:
                if position not in position_cols:
                    position_cols[position] = set()
                position_cols[position].add(i)

    result = {}
    for pos, cols in position_cols.items():
        result[pos] = [(i, headers[i].strip() if i < len(headers) else f"Col{i}") for i in sorted(cols)]

    return result


def parse_timestamp(ts_str):
    """Parse Google Sheets timestamp format."""
    for fmt in ("%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(ts_str.strip(), fmt)
        except ValueError:
            continue
    return None


def get_week_key(dt):
    """Return ISO week string like '2026-W20'."""
    return f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"


def get_month_key(dt):
    """Return month string like '2026-05'."""
    return dt.strftime("%Y-%m")


def parse_responses(rows, position_cols):
    """Parse responses, returning both flat votes and time-tagged votes."""
    if len(rows) < 2:
        return {}, []

    votes = {}
    timed_votes = []  # [(timestamp, player, position, grades)]

    for row in rows[1:]:
        if len(row) < 5:
            continue

        timestamp = parse_timestamp(row[0]) if row[0] else None
        voter = row[1].strip()
        player = row[2].strip()
        position = row[3].strip()

        if not voter or not player or position not in position_cols:
            continue

        grades = {}
        for col_idx, cat_name in position_cols[position]:
            if col_idx < len(row):
                val = row[col_idx].strip().upper()
                if val in VALID_GRADES:
                    grades[cat_name] = val

        if grades:
            votes.setdefault(player, {}).setdefault(position, {})[voter] = grades
            if timestamp:
                timed_votes.append((timestamp, player, position, grades))

    return votes, timed_votes


def calc_score(grades, pos):
    """Calculate weighted score for a set of grades."""
    config_weights = CONFIG.get("positions", {}).get(pos, {})
    weights = {c: config_weights.get(c, 1) for c in grades}
    total = sum(weights[c] * GRADE_VALUES[g] for c, g in grades.items())
    weight_sum = sum(weights.values())
    return total / weight_sum if weight_sum else 0


def build_history(timed_votes):
    """Group votes by player/position/week and calculate rolling scores."""
    # Group by player → position → week
    weekly = {}  # {player: {position: {week_key: [scores]}}}

    for ts, player, position, grades in timed_votes:
        week = get_week_key(ts)
        score = calc_score(grades, position)
        weekly.setdefault(player, {}).setdefault(position, {}).setdefault(week, []).append(score)

    # Average scores per week
    history = {}  # {player: {position: [{week, score, grade}]}}
    for player, positions in weekly.items():
        history[player] = {}
        for pos, weeks in positions.items():
            entries = []
            for week in sorted(weeks.keys()):
                scores = weeks[week]
                avg = sum(scores) / len(scores)
                entries.append({
                    "week": week,
                    "score": round(avg, 2),
                    "grade": score_to_grade(avg),
                    "votes": len(scores),
                })
            history[player][pos] = entries

    return history


def aggregate(votes, position_cols):
    results = {}
    for player, positions in votes.items():
        results[player] = {}
        for pos, voter_grades in positions.items():
            categories = [cat for _, cat in position_cols[pos]]
            config_weights = CONFIG.get("positions", {}).get(pos, {})

            avg_grades = {}
            for cat in categories:
                values = [GRADE_VALUES[vg[cat]] for vg in voter_grades.values() if cat in vg]
                if values:
                    avg_grades[cat] = sum(values) / len(values)

            if avg_grades:
                weights = {c: config_weights.get(c, 1) for c in avg_grades}
                total = sum(weights[c] * v for c, v in avg_grades.items())
                weight_sum = sum(weights.values())
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

    position_cols = detect_columns(rows)
    print(f"  Detected positions: {list(position_cols.keys())}")

    votes, timed_votes = parse_responses(rows, position_cols)
    results = aggregate(votes, position_cols)
    leaderboard = build_leaderboard(results)
    history = build_history(timed_votes)

    positions_config = {}
    for pos, cols in position_cols.items():
        config_weights = CONFIG.get("positions", {}).get(pos, {})
        positions_config[pos] = {cat: config_weights.get(cat, 1) for _, cat in cols}

    output = {
        "players": results,
        "leaderboard": leaderboard,
        "history": history,
        "config": {
            "grades": CONFIG["grades"],
            "positions": positions_config,
            "players": CONFIG["players"],
            "form_url": CONFIG.get("form_url", ""),
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2))
    print(f"  Written to {OUTPUT}")


if __name__ == "__main__":
    main()
