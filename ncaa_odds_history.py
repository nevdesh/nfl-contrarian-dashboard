
import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from vsin_parser import parse_percent
from ncaa_game_dates import parse_game_date
FIELDS = [
    "captured_at",
    "game_date",
    "game_number",
    "matchup_id",
    "team",
    "spread",
    "moneyline",
    "spread_handle_pct",
    "moneyline_handle_pct",
    "source_capture",
]


def capture_timestamp(path):
    match = re.search(
        r"vsin-(\d{8}T\d{6}Z)-tables\.json$",
        Path(path).name,
    )
    if not match:
        raise ValueError("Unrecognized capture filename")

    return datetime.strptime(
        match.group(1), "%Y%m%dT%H%M%SZ"
    ).replace(tzinfo=timezone.utc).isoformat()



def extract_observations(path):
    tables = json.loads(
        Path(path).read_text(encoding="utf-8")
    )
    if not isinstance(tables, list):
        raise ValueError("Expected a list of tables")

    timestamp = capture_timestamp(path)
    observations = []
    seen = set()

    for table in tables:
        current_date = None
        team_rows = []

        def save_matchup(rows, game_number):
            if len(rows) != 2:
                raise ValueError(
                    f"Incomplete matchup on {current_date}: "
                    f"expected 2 teams, got {len(rows)}"
                )

            teams = [str(r[1]).strip() for r in rows]
            if not all(teams) or teams[0] == teams[1]:
                raise ValueError(
                    f"Invalid matchup teams: {teams}"
                )

            

            # Convert the VSiN date header to a full calendar date.
            game_date_iso = parse_game_date(current_date, timestamp)

            if game_date_iso is None:
                raise ValueError(
                    f"Could not determine game date: {current_date}"
                )

            # Sort team names so display order cannot change the ID.
            matchup_id = " | ".join([
                game_date_iso,
                *sorted(teams, key=str.casefold),
            ])



            for row in rows:
                team = str(row[1]).strip()
                key = (matchup_id, team)

                if key in seen:
                    continue
                seen.add(key)

                observations.append({
                    "captured_at": timestamp,
                    "game_date": current_date,
                    "game_number": game_number,
                    "matchup_id": matchup_id,
                    "team": team,
                    "spread": str(row[2]).strip(),
                    "moneyline": str(row[8]).strip(),
                    "spread_handle_pct": parse_percent(row[3]),
                    "moneyline_handle_pct": parse_percent(row[9]),
                    "source_capture": Path(path).name,
                })

        game_number = 0

        for row in table.get("rows", []):
            if not isinstance(row, list):
                continue

            if row and str(row[0]).strip().startswith("CFB -"):
                if team_rows:
                    raise ValueError(
                        "Incomplete matchup before date header"
                    )
                current_date = str(row[0]).strip()
                game_number = 0
                continue

            if len(row) < 11 or not current_date:
                continue

            team = str(row[1]).strip()
            if not team:
                continue

            team_rows.append(row)

            if len(team_rows) == 2:
                game_number += 1
                save_matchup(team_rows, game_number)
                team_rows = []

        if team_rows:
            raise ValueError(
                f"Incomplete matchup at end of table: {current_date}"
            )

    return observations



def append_history(capture, output):
    output = Path(output)
    new_rows = extract_observations(capture)

    existing = []
    if output.exists():
        with output.open(newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames != FIELDS:
                raise ValueError("Existing history has unexpected columns")
            existing = list(reader)

    keys = {
        (
            row["source_capture"],
            row["game_date"],
            str(row["game_number"]),
            row["team"],
        )
        for row in existing
    }

    added = 0
    for row in new_rows:
        key = (
            row["source_capture"],
            row["game_date"],
            str(row["game_number"]),
            row["team"],
        )
        if key not in keys:
            existing.append(row)
            keys.add(key)
            added += 1

    output.parent.mkdir(parents=True, exist_ok=True)

    temporary = output.with_suffix(".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(existing)

    temporary.replace(output)
    print(f"Added {added} observations; total {len(existing)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("capture")
    parser.add_argument(
        "--output",
        default="data/odds_history.csv",
    )
    args = parser.parse_args()

    append_history(args.capture, args.output)


