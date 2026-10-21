import argparse
import csv
import re
from datetime import date, timedelta
from pathlib import Path

import nba_recover_history as recovery

TRACKER = Path("data/nba_weekly_ats_results.csv")

FIELDS = [
    "game_date", "week_start", "matchup_id", "team", "opponent",
    "qualifying_spread", "spread_handle_pct",
    "moneyline_handle_pct", "qualified_at",
    "team_score", "opponent_score", "ats_result"
]


def recover_picks():
    from collections import defaultdict

    grouped = defaultdict(list)

    with recovery.SOURCE.open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            key = recovery.game_key(row)
            if key:
                grouped[key].append(row)

    picks = []

    for key, observations in grouped.items():
        observations.sort(key=lambda row: row["captured_at"])

        baseline_spread = None
        baseline_probability = None

        for row in observations:
            spread = recovery.spread_value(row["spread"])
            probability = recovery.implied_probability(row["moneyline"])

            if spread is None or probability is None:
                continue

            if baseline_spread is None:
                baseline_spread = spread
                baseline_probability = probability

            spread_handle = recovery.number(row["spread_handle_pct"])
            moneyline_handle = recovery.number(row["moneyline_handle_pct"])

            if spread_handle is None or moneyline_handle is None:
                continue

            if (
                0 <= spread_handle < 40
                and 0 <= moneyline_handle < 40
                and baseline_spread - spread >= 1.0
                and probability > baseline_probability
            ):
                parts = row["matchup_id"].split("|")
                team = row["team"]
                opponents = [
                    part.strip() for part in parts[1:]
                    if recovery.clean_team(part) != recovery.clean_team(team)
                ]

                if len(opponents) != 1:
                    break

                game_day = date.fromisoformat(key[0])
                week_start = game_day - timedelta(
                    days=(game_day.weekday() + 1) % 7
                )

                picks.append({
                    "game_date": key[0],
                    "week_start": week_start.isoformat(),
                    "matchup_id": row["matchup_id"],
                    "team": team,
                    "opponent": opponents[0],
                    "qualifying_spread": row["spread"],
                    "spread_handle_pct": row["spread_handle_pct"],
                    "moneyline_handle_pct": row["moneyline_handle_pct"],
                    "qualified_at": row["captured_at"],
                    "team_score": "",
                    "opponent_score": "",
                    "ats_result": ""
                })
                break

    return sorted(picks, key=lambda row: (row["game_date"], row["team"]))


def identity(row):
    parts = row["matchup_id"].split("|")

    if len(parts) == 3:
        teams = tuple(sorted(recovery.clean_team(part) for part in parts[1:]))
        return row["game_date"], teams, recovery.clean_team(row["team"])

    return row["game_date"], (), recovery.clean_team(row["team"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    with TRACKER.open(newline="", encoding="utf-8-sig") as file:
        existing = list(csv.DictReader(file))

    known = {identity(row) for row in existing}
    recovered = recover_picks()
    new = [row for row in recovered if identity(row) not in known]

    print(f"Recovered candidates: {len(recovered)}")
    print(f"Already saved: {len(recovered) - len(new)}")
    print(f"New picks: {len(new)}")

    for row in new:
        print(
            f'{row["game_date"]} | {row["team"]} | '
            f'{row["qualifying_spread"]} | {row["qualified_at"]}'
        )

    if not args.save:
        print("PREVIEW ONLY â€” no files modified.")
        return

    if not new:
        print("Nothing to save.")
        return

    import shutil
    shutil.copy2(TRACKER, TRACKER.with_suffix(".before_auto_save.csv"))

    with TRACKER.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(existing + new)

    print(f"Saved {len(new)} new picks.")


if __name__ == "__main__":
    main()
