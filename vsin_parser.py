
import argparse
import csv
import json
import re
from pathlib import Path

HANDLE_LIMIT = 40


def parse_percent(value):
    """Extract a percentage, ignoring VSiN movement arrows."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", str(value))
    return float(match.group(1)) if match else None


def parse_capture(path):
    """Read the VSiN HTML-table capture JSON."""
    tables = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(tables, list):
        raise ValueError("Expected a list of captured tables.")

    qualifying = []
    current_game_date = None
    matchup_number = 0

    for table in tables:
        rows = table.get("rows", [])

        for row in rows:
            if not isinstance(row, list):
                continue

            # VSiN separates each date with a header row.
            if row and str(row[0]).strip().startswith("NFL -"):
                current_game_date = str(row[0]).strip()
                matchup_number = 0
                continue

            # A normal team row has 11 columns.
            if len(row) < 11 or not current_game_date:
                continue

            team = str(row[1]).strip()
            if not team:
                continue

            # Every matchup contains two consecutive team rows.
            # The first team starts a new matchup.
            if matchup_number % 2 == 0:
                game_index = matchup_number // 2 + 1
            else:
                game_index = matchup_number // 2 + 1
            matchup_number += 1

            spread_handle = parse_percent(row[3])
            moneyline_handle = parse_percent(row[9])

            if spread_handle is None or moneyline_handle is None:
                continue

            if spread_handle < HANDLE_LIMIT and moneyline_handle < HANDLE_LIMIT:
                qualifying.append({
                    "game_date": current_game_date,
                    "game_number": game_index,
                    "team": team,
                    "spread": str(row[2]).strip(),
                    "spread_handle_pct": spread_handle,
                    "moneyline": str(row[8]).strip(),
                    "moneyline_handle_pct": moneyline_handle,
                })

    return qualifying


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", help="Path to VSiN *-tables.json")
    parser.add_argument(
        "--output",
        default="contrarian_qualifiers.csv",
        help="Output CSV filename",
    )
    args = parser.parse_args()

    qualifiers = parse_capture(args.capture)

    fields = [
        "game_date",
        "game_number",
        "team",
        "spread",
        "spread_handle_pct",
        "moneyline",
        "moneyline_handle_pct",
    ]

    with open(args.output, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(qualifiers)

    print(f"Found {len(qualifiers)} qualifying teams.")
    print(f"Saved results to {args.output}")

    for team in qualifiers:
        print(
            f"{team['team']}: "
            f"Spread {team['spread_handle_pct']}%, "
            f"ML {team['moneyline_handle_pct']}%"
        )


if __name__ == "__main__":
    main()
