
import csv
import re
from collections import defaultdict


def spread_number(value):
    text = str(value).strip()
    match = re.match(r"^([+-]?\d+(?:\.\d+)?)(?!\d)", text)
    return float(match.group(1)) if match else None


def implied_probability(value):
    text = str(value).strip()
    match = re.fullmatch(r"([+-]\d+)", text)

    if not match:
        return None

    odds = int(match.group(1))

    if odds == 0:
        return None

    if odds > 0:
        return 100 / (odds + 100)

    return -odds / (-odds + 100)


def classify_movement(first, latest, parser, direction):
    a = parser(first)
    b = parser(latest)

    if a is None or b is None:
        return "Insufficient Data"

    difference = (b - a) * direction

    if abs(difference) < 0.000001:
        return "Unchanged"

    return "Favorable" if difference > 0 else "Unfavorable"


def calculate_movements(history_path):
    history = defaultdict(list)

    with open(history_path, newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            key = (row["matchup_id"], row["team"])
            history[key].append(row)

    results = []

    for (matchup_id, team), rows in sorted(history.items()):
        rows.sort(key=lambda row: row["captured_at"])

        first = rows[0]
        latest = rows[-1]

        valid_spreads = [
            row for row in rows
            if spread_number(row["spread"]) is not None
        ]

        valid_moneylines = [
            row for row in rows
            if implied_probability(row["moneyline"]) is not None
        ]

        def movement_from_valid(valid_rows, field, parser, direction):
            if len(valid_rows) < 2:
                return "Insufficient Data"

            return classify_movement(
                valid_rows[0][field],
                valid_rows[-1][field],
                parser,
                direction,
            )

        results.append({
            "matchup_id": matchup_id,
            "team": team,
            "first_observed_at": first["captured_at"],
            "latest_observed_at": latest["captured_at"],
            "first_spread": first["spread"],
            "latest_spread": latest["spread"],
            "first_moneyline": first["moneyline"],
            "latest_moneyline": latest["moneyline"],
            "spread_movement": movement_from_valid(
                valid_spreads, "spread", spread_number, -1
            ),
            "moneyline_movement": movement_from_valid(
                valid_moneylines, "moneyline", implied_probability, 1
            ),
        })

    return results


if __name__ == "__main__":
    results = calculate_movements("data/odds_history.csv")

    print(
        f"{'TEAM':25} "
        f"{'SPREAD MOVEMENT':20} "
        f"{'ML MOVEMENT':20}"
    )
    print("-" * 70)

    for row in results:
        print(
            f"{row['team'][:25]:25} "
            f"{row['spread_movement']:20} "
            f"{row['moneyline_movement']:20}"
        )
