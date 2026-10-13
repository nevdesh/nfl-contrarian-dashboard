import re
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from streamlit_autorefresh import st_autorefresh

DRAFTKINGS_SPLITS_URL = (
    "https://dknetwork.draftkings.com/draftkings-sportsbook-betting-splits/"
    "?tb_eg=88808&tb_edate=n7days&tb_emt=0&itm_content=NFL"
)
EV_URL = "https://evanalytics.com/nfl/odds"

st.set_page_config(
    page_title="NFL Contrarian Dashboard",
    page_icon="🏈",
    layout="wide",
)

st.title("🏈 NFL Contrarian Dashboard")
st.caption(
    "DraftKings Network betting splits + EV Analytics NFL odds"
)

# Refresh the dashboard every five minutes.
st_autorefresh(
    interval=5 * 60 * 1000,
    key="dashboard_refresh",
)

st.markdown(
    f"""
    **Sources**

    - [DraftKings Network NFL betting splits]({DRAFTKINGS_SPLITS_URL})
    - [EV Analytics NFL odds]({EV_URL})
    """
)

st.info(
    "This dashboard refreshes automatically. Live page "
    "availability does not guarantee that the source tables "
    "were successfully interpreted. Until extraction is "
    "validated, use the CSV import workflow below for signals."
)


@st.cache_data(ttl=300, show_spinner=False)
def check_source(url):
    """Check whether a public source page is reachable."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; NFLDashboard/1.0)"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    tables = []

    try:
        tables = pd.read_html(response.text)
    except (ValueError, ImportError):
        pass

    return {
        "status": response.status_code,
        "title": title,
        "table_count": len(tables),
        "tables": [df.head(10) for df in tables[:5]],
    }


with st.sidebar:
    st.header("Settings")
    threshold = st.slider(
        "Minority handle threshold (%)",
        min_value=10,
        max_value=49,
        value=40,
    )
    min_spread_move = st.selectbox(
        "Minimum favorable spread movement",
        options=[0.5, 1.0, 1.5, 2.0],
        index=0,
        format_func=lambda x: f"{x:.1f} points",
    )
    check_now = st.button(
        "Check source websites now",
        use_container_width=True,
    )

if check_now:
    check_source.clear()

st.subheader("1. Source status")

for name, url in [
    ("DraftKings Network betting splits", DRAFTKINGS_SPLITS_URL),
    ("EV Analytics odds", EV_URL),
]:
    with st.expander(name, expanded=True):
        try:
            with st.spinner(f"Checking {name}..."):
                result = check_source(url)

            st.success(
                f"Page reachable (HTTP {result['status']})"
            )
            st.write("Page title:", result["title"] or "Not detected")
            st.write(
                "HTML tables detected:",
                result["table_count"],
            )

            if result["tables"]:
                st.caption(
                    "Table previews are for inspection only; "
                    "they have not been automatically mapped "
                    "to teams or markets."
                )
                for i, table in enumerate(result["tables"], start=1):
                    st.write(f"Table {i}")
                    st.dataframe(table, use_container_width=True)
            else:
                st.warning(
                    "No ordinary HTML tables detected. The site "
                    "may load data dynamically or restrict requests."
                )

        except requests.RequestException as exc:
            st.error(f"Could not retrieve this page: {exc}")


st.divider()
st.subheader("2. Import verified market data")

st.markdown(
    """
    The two CSV files must describe the same teams and markets.
    This import workflow lets you analyze verified data even when
    the websites do not expose scrape-friendly tables.

    **Splits CSV columns:** `game`, `team`, `market`,
    `handle_pct`

    **Odds history CSV columns:** `game`, `team`, `market`,
    `line`, `timestamp`

    Use `spread` or `moneyline` for the market. Use American
    odds for moneylines (for example, `+145` or `-120`) and
    signed point spreads for spreads (for example, `+3.5`).
    The odds history needs at least two timestamps per team
    and market to calculate movement.
    """
)

split_template = pd.DataFrame(columns=[
    "game", "team", "market", "handle_pct"
])
odds_template = pd.DataFrame(columns=[
    "game", "team", "market", "line", "timestamp"
])

left, right = st.columns(2)

with left:
    st.download_button(
        "Download splits CSV template",
        split_template.to_csv(index=False),
        "splits_template.csv",
        "text/csv",
    )
    splits_file = st.file_uploader(
        "Upload DraftKings splits CSV",
        type="csv",
        key="splits_upload",
    )

with right:
    st.download_button(
        "Download odds history CSV template",
        odds_template.to_csv(index=False),
        "odds_history_template.csv",
        "text/csv",
    )
    odds_file = st.file_uploader(
        "Upload odds history CSV",
        type="csv",
        key="odds_upload",
    )


def team_key(value):
    return re.sub(
        r"[^a-z0-9]",
        "",
        str(value).lower(),
    )


def implied_probability(american_odds):
    if american_odds < 0:
        return -american_odds / (-american_odds + 100)
    return 100 / (american_odds + 100)


if splits_file is not None and odds_file is not None:
    try:
        splits = pd.read_csv(splits_file)
        odds = pd.read_csv(odds_file)

        required_splits = {
            "game", "team", "market", "handle_pct"
        }
        required_odds = {
            "game", "team", "market", "line", "timestamp"
        }

        missing_splits = required_splits - set(splits.columns)
        missing_odds = required_odds - set(odds.columns)

        if missing_splits or missing_odds:
            if missing_splits:
                st.error(
                    "Missing split columns: "
                    + ", ".join(sorted(missing_splits))
                )
            if missing_odds:
                st.error(
                    "Missing odds columns: "
                    + ", ".join(sorted(missing_odds))
                )
            st.stop()

        for frame in (splits, odds):
            frame["game_key"] = frame["game"].map(team_key)
            frame["team_key"] = frame["team"].map(team_key)
            frame["market"] = (
                frame["market"].astype(str).str.lower().str.strip()
            )

        splits["handle_pct"] = pd.to_numeric(
            splits["handle_pct"], errors="coerce"
        )
        odds["line"] = pd.to_numeric(
            odds["line"], errors="coerce"
        )
        odds["timestamp"] = pd.to_datetime(
            odds["timestamp"], utc=True, errors="coerce"
        )

        # First identify teams that qualify in BOTH markets.
        # A team must have a valid handle percentage below the threshold
        # for both moneyline and spread to enter the contrarian shortlist.
        valid_splits = splits[
            splits["market"].isin(["spread", "moneyline"])
            & splits["handle_pct"].between(0, 100)
        ].copy()

        market_counts = (
            valid_splits[valid_splits["handle_pct"] < threshold]
            .groupby(["game_key", "team_key"])["market"]
            .nunique()
        )
        qualifying_teams = market_counts[market_counts == 2].index

        if len(qualifying_teams) == 0:
            splits = valid_splits.iloc[0:0].copy()
        else:
            qualified_index = pd.MultiIndex.from_frame(
                valid_splits[["game_key", "team_key"]]
            )
            splits = valid_splits[
                qualified_index.isin(qualifying_teams)
                & (valid_splits["handle_pct"] < threshold)
            ].copy()

        odds = odds.dropna(
            subset=["line", "timestamp", "game_key", "team_key"]
        ).sort_values("timestamp")

        keys = ["game_key", "team_key", "market"]

        first = (
            odds.groupby(keys, as_index=False)
            .first()
            .rename(columns={
                "line": "earliest_line",
                "timestamp": "earliest_time",
            })
        )

        last = (
            odds.groupby(keys, as_index=False)
            .last()
            .rename(columns={
                "line": "latest_line",
                "timestamp": "latest_time",
            })
        )

        movement = first[
            keys + ["earliest_line", "earliest_time"]
        ].merge(
            last[keys + ["latest_line", "latest_time"]],
            on=keys,
            how="inner",
        )

        # Ensure the odds history actually contains a movement.
        movement = movement[
            movement["latest_time"] > movement["earliest_time"]
        ].copy()

        result = splits.merge(
            movement,
            on=keys,
            how="left",
        )

        def evaluate(row):
            old = row.get("earliest_line")
            new = row.get("latest_line")

            if pd.isna(old) or pd.isna(new):
                return "Insufficient odds history"

            if row["market"] == "spread":
                # Spreads are entered from the candidate team's perspective.
                # Example: +3.0 to +3.5 or -3.0 to -2.5 both favor that team.
                delta = new - old
                if delta >= min_spread_move:
                    return "Favorable movement"
                if delta <= -min_spread_move:
                    return "Movement against team"
                return "No significant movement"

            old_prob = implied_probability(old)
            new_prob = implied_probability(new)
            delta = new_prob - old_prob

            if delta >= 0.005:
                return "Favorable movement"
            if delta <= -0.005:
                return "Movement against team"
            return "No significant movement"

        result["Signal"] = result.apply(evaluate, axis=1)

        result["Assessment"] = result["Signal"].map({
            "Favorable movement": "Contrarian candidate",
            "Movement against team": "No confirmation",
            "No significant movement": "Watchlist",
            "Insufficient odds history": "Needs more data",
        })

        result = result.rename(columns={
            "handle_pct": "Handle %",
            "earliest_line": "Earlier line",
            "latest_line": "Latest line",
            "earliest_time": "Earlier timestamp",
            "latest_time": "Latest timestamp",
        })

        st.subheader("3. Contrarian shortlist")

        candidates = result[
            result["Signal"] == "Favorable movement"
        ]

        if candidates.empty:
            st.info(
                "No matching candidates were found in the "
                "uploaded data. Check the timestamps and team names."
            )
        else:
            st.dataframe(
                candidates[[
                    "game", "team", "market", "Handle %",
                    "Earlier line", "Latest line",
                    "Earlier timestamp", "Latest timestamp",
                    "Assessment",
                ]],
                use_container_width=True,
                hide_index=True,
            )

        st.subheader("All qualifying teams")
        st.dataframe(
            result[[
                "game", "team", "market", "Handle %",
                "Earlier line", "Latest line",
                "Earlier timestamp", "Latest timestamp",
                "Signal", "Assessment",
            ]],
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Download analysis CSV",
            result.to_csv(index=False),
            "nfl_contrarian_analysis.csv",
            "text/csv",
        )

    except Exception as exc:
        st.error(f"Could not analyze these files: {exc}")

else:
    st.info(
        "Upload both CSV files to calculate contrarian signals. "
        "The live website checks above do not yet import betting data "
        "automatically. Teams must be below the handle threshold in BOTH "
        "moneyline and spread to qualify."
    )

st.divider()
st.caption(
    "Last dashboard render: "
    + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
)
st.caption(
    "For research only. Low handle percentage and favorable "
    "movement do not establish who caused the move or predict "
    "a winning outcome. Verify market, team, and timestamps."
)
