from datetime import datetime, timezone
from urllib.request import Request, urlopen
import json
import re
import unicodedata

import nba_auto_tracker as tracker


def normalize(name):
    name = re.sub(r"^\(\d+\)\s*", "", str(name).strip())
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r"\bST\b", "State", name, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", name).casefold()


def kickoff_before_qualification(pick, events):
    team = normalize(pick["team"])
    opponent = normalize(pick["opponent"])

    matches = []

    for event in events:
        competitions = event.get("competitions", [])
        if not competitions:
            continue

        competitors = competitions[0].get("competitors", [])
        names = {
            normalize(c.get("team", {}).get("displayName", ""))
            for c in competitors
        }

        if len(competitors) == 2 and names == {team, opponent}:
            matches.append(event)

    if len(matches) != 1:
        return False

    try:
        kickoff = datetime.fromisoformat(
            matches[0]["date"].replace("Z", "+00:00")
        )
        qualified = datetime.fromisoformat(
            pick["qualified_at"].replace("Z", "+00:00")
        )

        if kickoff.tzinfo is None or qualified.tzinfo is None:
            return False

        return qualified.astimezone(timezone.utc) < kickoff.astimezone(timezone.utc)

    except (KeyError, TypeError, ValueError):
        return False


def load_events(game_date):
    url = (
        "https://site.api.espn.com/apis/site/v2/"
        "sports/basketball/nba/scoreboard"
        f"?dates={game_date.replace('-', '')}&limit=500"
    )

    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})

    with urlopen(request, timeout=20) as response:
        return json.load(response).get("events", [])


def main():
    original_recover = tracker.recover_picks

    def protected_recover():
        picks = original_recover()
        cache = {}
        accepted = []

        for pick in picks:
            day = pick["game_date"]

            if day not in cache:
                cache[day] = load_events(day)

            if kickoff_before_qualification(pick, cache[day]):
                accepted.append(pick)
            else:
                print(
                    f'Skipped (kickoff check): '
                    f'{pick["game_date"]} | {pick["team"]}'
                )

        return accepted

    tracker.recover_picks = protected_recover

    try:
        tracker.main()
    finally:
        tracker.recover_picks = original_recover


if __name__ == "__main__":
    main()
