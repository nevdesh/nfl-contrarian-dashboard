
import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from vsin_parser import parse_percent

FIELDS = [
    "captured_at",
    "game_date",
    "game_number",
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
        team_count = 0

        for row in table.get("rows", []):
            if not isinstance(row, list):
                continue

            if row and str(row[0]).strip().startswith("NFL -"):
                current_date = str(row[0]).strip()
                team_count = 0
                continue

            if len(row) < 11 or not current_date:
                continue

            team = str(row[1]).strip()
            if not team:
                continue

            game_number = team_count // 2 + 1
            team_count += 1

            key = (current_date, game_number, team)
            if key in seen:
                continue
            seen.add(key)

            observations.append({
                "captured_at": timestamp,
                "game_date": current_date,
                "game_number": game_number,
                "team": team,
                "spread": str(row[2]).strip(),
                "moneyline": str(row[8]).strip(),
                "spread_handle_pct": parse_percent(row[3]),
                "moneyline_handle_pct": parse_percent(row[9]),
                "source_capture": Path(path).name,
            })

    return observations


def append_history(capture, output):
    output = Path(output)
    new_rows = extract_observations(capture)

    existing = []
    if output.exists():
        with output.open(newline="", encoding="utf-8") as file:
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
