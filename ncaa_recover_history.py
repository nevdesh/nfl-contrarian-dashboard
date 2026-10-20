import csv
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SOURCE = Path("data/ncaa_odds_history.csv")


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def clean_team(name):
    return re.sub(r"^\(\d+\)\s*", "", name.strip()).casefold()


def spread_value(value):
    match = re.match(r"^([+-]?\d+(?:\.\d+)?)", str(value).strip())
    return float(match.group(1)) if match else None


def implied_probability(value):
    match = re.fullmatch(r"([+-]\d+)", str(value).strip())
    if not match:
        return None

    odds = int(match.group(1))

    if odds == 0:
        return None

    if odds > 0:
        return 100 / (odds + 100)

    return -odds / (-odds + 100)


def game_key(row):
    parts = row["matchup_id"].split("|")
    if len(parts) != 3:
        return None

    date = parts[0].strip()
    teams = tuple(sorted([
        clean_team(parts[1]),
        clean_team(parts[2])
    ]))

    return date, teams, clean_team(row["team"])


def main():
    grouped = defaultdict(list)

    with SOURCE.open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            key = game_key(row)
            if key:
                grouped[key].append(row)

    recovered = []

    for key, observations in grouped.items():
        observations.sort(key=lambda r: r["captured_at"])

        baseline_spread = None
        baseline_probability = None

        for row in observations:
            spread = spread_value(row["spread"])
            probability = implied_probability(row["moneyline"])

            if spread is None or probability is None:
                continue

            if baseline_spread is None:
                baseline_spread = spread
                baseline_probability = probability

            spread_handle = number(row["spread_handle_pct"])
            moneyline_handle = number(row["moneyline_handle_pct"])

            if spread_handle is None or moneyline_handle is None:
                continue

            handles_ok = (
                0 < spread_handle < 40
                and 0 < moneyline_handle < 40
            )

            spread_movement = baseline_spread - spread
            moneyline_favorable = probability > baseline_probability

            if (
                handles_ok
                and spread_movement >= 1.0
                and moneyline_favorable
            ):
                recovered.append({
                    "game_date": key[0],
                    "team": row["team"],
                    "qualifying_spread": row["spread"],
                    "spread_handle_pct": row["spread_handle_pct"],
                    "moneyline_handle_pct": row["moneyline_handle_pct"],
                    "qualified_at": row["captured_at"],
                    "matchup_id": row["matchup_id"]
                })
                break

    recovered.sort(
        key=lambda r: (r["game_date"], r["team"])
    )

    print(f"Historical candidates found: {len(recovered)}")
    print()

    for row in recovered:
        print(
            f'{row["game_date"]} | '
            f'{row["team"]} | '
            f'Spread {row["qualifying_spread"]} | '
            f'Qualified {row["qualified_at"]}'
        )

    print()
    print("PREVIEW ONLY — no files were modified.")


if __name__ == "__main__":
    main()
