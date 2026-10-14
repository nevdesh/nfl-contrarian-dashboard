
import csv
import io
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
from collections import defaultdict
from pathlib import Path
from line_movement import (
    classify_movement,
    implied_probability,
    spread_number,
)

ODDS_HISTORY_URL = (
    "https://raw.githubusercontent.com/"
    "nevdesh/nfl-contrarian-dashboard/main/data/odds_history.csv"
)


def get_odds_history(history_path):
    try:
        with urlopen(ODDS_HISTORY_URL, timeout=10) as response:
            csv_text = response.read().decode("utf-8-sig")

        rows = list(csv.DictReader(io.StringIO(csv_text)))

        required_columns = {
            "matchup_id",
            "team",
            "captured_at",
            "spread",
            "moneyline",
        }

        if not rows or not required_columns.issubset(rows[0]):
            raise ValueError("GitHub odds history is empty or invalid")

        print(f"Loaded {len(rows)} odds observations from GitHub")
        return rows

    except (URLError, HTTPError, TimeoutError, ValueError, OSError) as error:
        print(f"GitHub download failed: {error}")
        print("Using local odds history instead")

        with open(history_path, newline="", encoding="utf-8-sig") as file:
            return list(csv.DictReader(file))
def load_movements(history_path="data/odds_history.csv"):
    history = defaultdict(list)

    for row in get_odds_history(history_path):
            matchup_id = row.get("matchup_id", "").strip()
            team = row.get("team", "").strip()

            if not matchup_id or not team:
                continue

            history[(matchup_id, team)].append(row)

    results = {}

    for (matchup_id, team), rows in history.items():
        rows.sort(key=lambda row: row["captured_at"])

        valid_spreads = [
            row for row in rows
            if spread_number(row.get("spread", "")) is not None
        ]

        valid_moneylines = [
            row for row in rows
            if implied_probability(row.get("moneyline", "")) is not None
        ]

        def movement(rows, field, parser, direction):
            if len(rows) < 2:
                return "Insufficient Data"

            return classify_movement(
                rows[0].get(field, ""),
                rows[-1].get(field, ""),
                parser,
                direction,
            )

        game_date = matchup_id.split(" | ", 1)[0]

        results[(game_date, team)] = {
            "Earliest Spread": valid_spreads[0]["spread"] if valid_spreads else "N/A",
            "Latest Spread": valid_spreads[-1]["spread"] if valid_spreads else "N/A",
            "Earliest Moneyline": valid_moneylines[0]["moneyline"] if valid_moneylines else "N/A",
            "Latest Moneyline": valid_moneylines[-1]["moneyline"] if valid_moneylines else "N/A",
            "Spread Movement": movement(
                valid_spreads, "spread", spread_number, -1
            ),
            "Moneyline Movement": movement(
                valid_moneylines, "moneyline", implied_probability, 1
            ),
        }

    return results


if __name__ == "__main__":
    results = load_movements()
    print(f"PASS: Loaded movement for {len(results)} team-matchups")
    for key, value in sorted(results.items()):
        print(key, value)
