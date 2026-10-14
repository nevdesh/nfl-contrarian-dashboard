
import re
from datetime import datetime, timedelta


def parse_game_date(header, captured_at):
    match = re.fullmatch(
        r"NFL\s*-\s*([A-Z]+),\s*([A-Z]+)\s+(\d{1,2})",
        str(header).strip().upper()
    )

    if not match:
        return None

    weekday, month_name, day = match.groups()

    try:
        month = datetime.strptime(month_name[:3], "%b").month
        captured = datetime.fromisoformat(captured_at)
    except ValueError:
        return None

    candidates = []

    for year in (
        captured.year - 1,
        captured.year,
        captured.year + 1,
    ):
        try:
            candidate = datetime(
                year,
                month,
                int(day),
                tzinfo=captured.tzinfo,
            )
        except ValueError:
            continue

        if candidate.strftime("%A").upper() != weekday:
            continue

        if not (
            captured - timedelta(days=7)
            <= candidate
            <= captured + timedelta(days=370)
        ):
            continue

        candidates.append(candidate)

    if len(candidates) != 1:
        return None

    return candidates[0].date().isoformat()
