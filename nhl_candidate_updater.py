import csv
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HISTORY = Path("data/nhl/odds_history.csv")
OUTPUT = Path("data/nhl/contrarian_candidates.csv")

FIELDS = [
    "game_date",
    "game_number",
    "matchup_id",
    "team",
    "spread",
    "spread_handle_pct",
    "moneyline",
    "moneyline_handle_pct",
]


def update_candidates():
    if not HISTORY.exists():
        raise FileNotFoundError(HISTORY)

    with HISTORY.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = set(FIELDS + ["captured_at"])
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("NHL history is missing required columns")
        history = list(reader)

    latest = {}

    for row in history:
        key = (row["game_date"], row["matchup_id"], row["team"])

        timestamp = datetime.fromisoformat(row["captured_at"])

        if (
            key not in latest
            or timestamp > latest[key][0]
        ):
            latest[key] = (timestamp, row)

    now = datetime.now(ZoneInfo("America/Toronto"))
    cutoff = (
        now.date()
        if now.hour >= 2
        else (now - timedelta(days=1)).date()
    )

    candidates = []

    for _, row in latest.values():
        try:
            game_date = datetime.strptime(
                row["game_date"], "%Y-%m-%d"
            ).date()

            spread_handle = float(row["spread_handle_pct"])
            ml_handle = float(row["moneyline_handle_pct"])
        except (ValueError, TypeError):
            continue

        if game_date < cutoff:
            continue

        if spread_handle >= 40 or ml_handle >= 40:
            continue

        candidates.append({
            field: row.get(field, "")
            for field in FIELDS
        })

    candidates.sort(
        key=lambda row: (
            row["game_date"],
            row["matchup_id"],
            row["team"],
        )
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")

    with temporary.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(candidates)

    temporary.replace(OUTPUT)

    print(f"History observations: {len(history)}")
    print(f"Current NHL candidates: {len(candidates)}")
    print(f"Updated: {OUTPUT}")


if __name__ == "__main__":
    update_candidates()
