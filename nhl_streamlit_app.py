from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from dashboard_style import apply_dashboard_style

CANDIDATES_PATH = Path("data/nhl/contrarian_candidates.csv")
HISTORY_PATH = Path("data/nhl/odds_history.csv")
HANDLE_LIMIT = 40.0
MIN_MONEYLINE_CENTS = 10


def read_csv(path):
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def implied_probability(value):
    try:
        odds = int(str(value).strip())
    except (ValueError, TypeError):
        return None

    if odds > 0:
        return 100 / (odds + 100)
    if odds < 0:
        return -odds / (-odds + 100)
    return None


def american_line_value(odds):
    """Express American odds as cents relative to even money."""
    if odds > 0:
        return odds - 100
    if odds < 0:
        return -(abs(odds) - 100)
    raise ValueError("American odds cannot be zero")


def analyze_candidates(candidates, history):
    results = []

    for _, candidate in candidates.iterrows():
        try:
            spread_handle = float(candidate["spread_handle_pct"])
            ml_handle = float(candidate["moneyline_handle_pct"])
        except (ValueError, KeyError, TypeError):
            continue

        if not (
            0 <= spread_handle < HANDLE_LIMIT
            and 0 <= ml_handle < HANDLE_LIMIT
        ):
            continue

        matching = history[
            (history["game_date"] == candidate["game_date"])
            & (history["matchup_id"] == candidate["matchup_id"])
            & (history["team"] == candidate["team"])
        ].copy() if not history.empty else pd.DataFrame()

        status = "INSUFFICIENT DATA FOR MONEYLINE MOVEMENT"
        first_ml = ""
        latest_ml = ""
        snapshots = 0
        movement_cents = None

        if not matching.empty:
            matching = matching.sort_values("captured_at")
            matching = matching.drop_duplicates("captured_at")

            valid_rows = []

            for _, observation in matching.iterrows():
                raw_price = str(observation["moneyline"]).strip()

                try:
                    price = int(raw_price)
                    if price == 0 or abs(price) < 100:
                        continue
                except (ValueError, TypeError):
                    continue

                valid_rows.append((observation["captured_at"], price))

            snapshots = len(valid_rows)

            # The newest observation must have valid moneyline odds.
            # Never confirm movement using an outdated latest price.
            latest_observation = matching.iloc[-1]
            latest_raw = str(latest_observation["moneyline"]).strip()

            try:
                latest_observed_price = int(latest_raw)
                latest_is_valid = (
                    latest_observed_price != 0
                    and abs(latest_observed_price) >= 100
                )
            except (ValueError, TypeError):
                latest_is_valid = False

            if snapshots >= 2 and latest_is_valid:
                first_ml = str(valid_rows[0][1])
                latest_ml = str(valid_rows[-1][1])

                movement_cents = (
                    american_line_value(valid_rows[0][1])
                    - american_line_value(valid_rows[-1][1])
                )

                if movement_cents >= MIN_MONEYLINE_CENTS:
                    status = "FAVORABLE MONEYLINE MOVEMENT"
                elif movement_cents > 0:
                    status = "FAVORABLE, BELOW 10-CENT THRESHOLD"
                elif movement_cents < 0:
                    status = "UNFAVORABLE MONEYLINE MOVEMENT"
                else:
                    status = "NO MONEYLINE MOVEMENT"
        results.append({
            "Game Date": candidate["game_date"],
            "Team": candidate["team"],
            "Puck Line": candidate.get("spread", ""),
            "Spread Handle %": spread_handle,
            "Moneyline Handle %": ml_handle,
            "First Moneyline": first_ml,
            "Latest Moneyline": latest_ml,
            "Snapshots": snapshots,
            "Movement (cents)": movement_cents,
            "Status": status,
        })

    return pd.DataFrame(results)



def filter_active_games(candidates):
    now = datetime.now(ZoneInfo("America/Toronto"))
    cutoff_date = (
        now.date() if now.hour >= 2
        else (now - timedelta(days=1)).date()
    )

    dates = pd.to_datetime(
        candidates["game_date"], errors="coerce"
    ).dt.date

    return candidates[dates >= cutoff_date].copy()


st.set_page_config(
    page_title="NHL Contrarian Dashboard",
    page_icon="\U0001F3D2",
    layout="wide",
)

st_autorefresh(interval=60000, key="nhl_auto_refresh")

apply_dashboard_style()

st.title("NHL Contrarian Dashboard")
st.caption(
    "Contrarian betting candidates with low spread and moneyline handle "
    "and favorable moneyline movement."
)

st.info(
    "Qualification requires both handle percentages below 40% and at least "
    "10 cents of favorable moneyline movement. Candidates with insufficient "
    "history are not confirmed picks."
)

if st.button("Refresh data"):
    st.cache_data.clear()

candidates = read_csv(CANDIDATES_PATH)
history = read_csv(HISTORY_PATH)

if candidates.empty:
    st.warning("No NHL candidates found. Check data/nhl/contrarian_candidates.csv.")
elif history.empty:
    st.warning("No NHL odds history found. Check data/nhl/odds_history.csv.")
else:
    required_candidates = {
        "game_date", "matchup_id", "team", "spread",
        "spread_handle_pct", "moneyline_handle_pct",
    }
    required_history = {
        "captured_at", "game_date", "matchup_id", "team", "moneyline",
    }

    if not required_candidates.issubset(candidates.columns):
        st.error("The NHL candidates CSV is missing required columns.")
    elif not required_history.issubset(history.columns):
        st.error("The NHL odds history CSV is missing required columns.")
    else:
        candidates = filter_active_games(candidates)
        results = analyze_candidates(candidates, history)

        if results.empty:
            st.warning("No candidates currently meet both handle thresholds.")
        else:
            confirmed = results[
                results["Status"] == "FAVORABLE MONEYLINE MOVEMENT"
            ]
            insufficient = results[
                results["Status"] == "INSUFFICIENT DATA FOR MONEYLINE MOVEMENT"
            ]

            col1, col2, col3 = st.columns(3)
            col1.metric("Low-handle candidates", len(results))
            col2.metric("Confirmed movement", len(confirmed))
            col3.metric("Insufficient history", len(insufficient))

            st.subheader("Contrarian candidates")
            st.dataframe(results, use_container_width=True, hide_index=True)

            st.subheader("Confirmed candidates")
            if confirmed.empty:
                st.info("No candidates currently meet all qualification rules.")
            else:
                st.dataframe(
                    confirmed, use_container_width=True, hide_index=True
                )

            st.caption(
                "Price movement is provisional until its source and bookmaker "
                "are verified. The displayed movement threshold uses the "
                "absolute American-odds number change; crossing +100/-100 needs "
                "special interpretation."
            )
