import argparse
import csv
import json
import re
import shutil
from pathlib import Path
from urllib.request import Request, urlopen

TRACKER = Path("data/ncaa_weekly_ats_results.csv")


def clean_team(name):
    name = re.sub(r"^\(\d+\)\s*", "", str(name).strip())
    name = name.replace("José", "Jose")
    name = re.sub(r"\bST\b", "State", name, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", name).casefold()


def get_games(game_date):
    url = (
        "https://site.api.espn.com/apis/site/v2/"
        "sports/football/college-football/scoreboard"
        f"?dates={game_date.replace('-', '')}&limit=500"
    )

    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})

    with urlopen(request, timeout=20) as response:
        data = json.load(response)

    games = []

    for event in data.get("events", []):
        if event.get("status", {}).get("type", {}).get("name") != "STATUS_FINAL":
            continue

        competitors = event.get("competitions", [{}])[0].get("competitors", [])

        if len(competitors) != 2:
            continue

        try:
            scores = {
                clean_team(team["team"]["displayName"]): int(team["score"])
                for team in competitors
            }
        except (KeyError, ValueError, TypeError):
            continue

        games.append(scores)

    return games


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    with TRACKER.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        fields = reader.fieldnames
        rows = list(reader)

    pending = [row for row in rows if not row["ats_result"].strip()]

    if not pending:
        print("All saved picks are already graded.")
        print("No files modified.")
        return

    dates = sorted({row["game_date"] for row in pending})
    games_by_date = {day: get_games(day) for day in dates}

    updates = []

    for row in pending:
        team = clean_team(row["team"])
        opponent = clean_team(row["opponent"])

        matches = [
            game for game in games_by_date[row["game_date"]]
            if team in game and opponent in game
        ]

        if len(matches) != 1:
            print(f'Unmatched or unfinished: {row["team"]}')
            continue

        game = matches[0]

        try:
            spread = float(row["qualifying_spread"])
        except ValueError:
            print(f'Invalid spread: {row["team"]}')
            continue

        team_score = game[team]
        opponent_score = game[opponent]
        margin = team_score + spread - opponent_score

        result = "YES" if margin > 0 else "NO" if margin < 0 else "PUSH"

        updates.append((row, team_score, opponent_score, result))

        print(
            f'{row["team"]}: {team_score}-{opponent_score} | '
            f'Spread {spread:+g} | ATS {result}'
        )

    print(f"New results available: {len(updates)}")

    if not args.save:
        print("PREVIEW ONLY — no files modified.")
        return

    if not updates:
        print("Nothing to save.")
        return

    shutil.copy2(
        TRACKER,
        TRACKER.with_suffix(".before_espn_update.csv")
    )

    for row, team_score, opponent_score, result in updates:
        row["team_score"] = str(team_score)
        row["opponent_score"] = str(opponent_score)
        row["ats_result"] = result

    with TRACKER.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(updates)} final results.")


if __name__ == "__main__":
    main()

