from dashboard_style import apply_dashboard_style
import re
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from streamlit_autorefresh import st_autorefresh
from ncaa_movement_helper import load_movements

VSIN_URL = (
    "https://data.vsin.com/betting-splits/"
    "?source=DK&sport=NCAAF"
)
EV_URL = "https://evanalytics.com/"



st.set_page_config(
    page_title="NCAA College Football Contrarian Dashboard",
    page_icon="ðŸˆ",
    layout="wide",
)

apply_dashboard_style()

st.title("ðŸˆ NCAA College Football Contrarian Dashboard")
st.caption(
    "NCAA college football betting splits and odds movement"
)

# Refresh the dashboard every five minutes.
st_autorefresh(
    interval=5 * 60 * 1000,
    key="dashboard_refresh",
)

st.markdown(
    f"""
    **Sources**

    - [VSiN DraftKings NCAA football betting splits]({VSIN_URL})
    - [Evan Analytics odds]({EV_URL})
    """
)

st.info(
    "This dashboard refreshes automatically. Live page "
    "availability does not guarantee that the source tables "
    "were successfully interpreted. Until extraction is "
    "validated, use the CSV import workflow below for signals."
)


@st.cache_data(ttl=300, show_spinner=False)
def load_automated_vsin():
    """Load and validate automated VSiN qualifiers."""
    from io import StringIO

    df = pd.read_csv("data/ncaa_betting_splits.csv")

    if df.empty:
        raise ValueError("No NCAA betting data available yet.")

    required = {
        "game_date",
        "game_number",
        "team",
        "spread",
        "spread_handle_pct",
        "moneyline",
        "moneyline_handle_pct",
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            "Missing CSV columns: " + ", ".join(sorted(missing))
        )

    # Convert handle percentages to numeric values.
    for col in ["spread_handle_pct", "moneyline_handle_pct"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Require both markets to meet the original threshold.
    qualifies = (
        df["spread_handle_pct"].ge(0)
        & df["spread_handle_pct"].lt(40)
        & df["moneyline_handle_pct"].ge(0)
        & df["moneyline_handle_pct"].lt(40)
    )

    # Missing or zero values need additional verification.
    spread_missing = (
        df["spread"].isna()
        | df["spread"].astype(str).str.strip().isin(["", "nan"])
    )

    questionable = (
        df["spread_handle_pct"].isna()
        | df["moneyline_handle_pct"].isna()
        | df["spread_handle_pct"].eq(0)
        | df["moneyline_handle_pct"].eq(0)
        | spread_missing
    )

    df["Data Status"] = "Check thresholds"
    df.loc[qualifies, "Data Status"] = "Meets thresholds"
    df.loc[questionable, "Data Status"] = "Needs verification"

  
    # Attach historical movement by game date and team.
    movements = load_movements("data/ncaa_odds_history.csv")

    df["Spread Movement"] = "Insufficient Data"
    df["Moneyline Movement"] = "Insufficient Data"
    for column in (
        "Earliest Spread", "Latest Spread",
        "Earliest Moneyline", "Latest Moneyline",
    ):
        df[column] = "N/A"

    for index, row in df.iterrows():
        game_date = datetime.strptime(str(row["game_date"]).strip(), "%Y-%m-%d").strftime("%Y-%m-%d")

        movement = movements.get((game_date, row["team"]))

        if movement:
            df.at[index, "Spread Movement"] = movement["Spread Movement"]
            df.at[index, "Moneyline Movement"] = movement["Moneyline Movement"]
            for column in (
                "Earliest Spread", "Latest Spread",
                "Earliest Moneyline", "Latest Moneyline",
            ):
                df.at[index, column] = movement.get(column, "N/A")

    return df


@st.cache_data(ttl=300, show_spinner=False)
def check_source(url):
    """Check whether a public source page is reachable."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; NCAADashboard/1.0)"
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
        tables = pd.read_html(__import__("io").StringIO(response.text))
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

# Automated VSiN contrarian dashboard
st.subheader("Automated NCAA contrarian results")
st.caption(
    "DraftKings betting handle data captured by VSiN. "
    "The source is refreshed by GitHub Actions."
)

try:
    automated = load_automated_vsin()

    confirmed = automated[
        automated["Data Status"] == "Meets thresholds"
    ].copy()

    verification = automated[
        automated["Data Status"] == "Needs verification"
    ].copy()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Qualifying teams", len(confirmed))

    with col2:
        st.metric("Needs verification", len(verification))

    with col3:
        st.metric("Teams analyzed", len(automated))

    with col4:
        st.metric("Handle threshold", "<40%")

    display_columns = {
        "game_date": "Game Date",
        "team": "Team",
        "spread": "Spread",
        "spread_handle_pct": "Spread Handle %",
        "moneyline": "Moneyline",
        "moneyline_handle_pct": "Moneyline Handle %",
        "Earliest Spread": "Earliest Recorded Spread",
        "Latest Spread": "Latest Recorded Spread",
        "Earliest Moneyline": "Earliest Recorded Moneyline",
        "Latest Moneyline": "Latest Recorded Moneyline",
        "Spread Movement": "Favorable Spread Movement",
        "Moneyline Movement": "Favorable ML Movement",
        "Data Status": "Data Status",
    }

    st.markdown("### Qualifying contrarian teams")

    if confirmed.empty:
        st.info("No qualifying teams in the latest CSV.")
    else:
        movement_display = confirmed[list(display_columns)].rename(
            columns=display_columns
        ).copy()

        for column in (
            "Favorable Spread Movement",
            "Favorable ML Movement",
        ):
            movement_display[column] = movement_display[column].map({
                "Favorable": "\U0001F7E2 Favorable",
                "Unfavorable": "\U0001F534 Unfavorable",
                "Unchanged": "\u26AA Unchanged",
                "Insufficient Data": "\u26AA Insufficient Data",
            }).fillna(movement_display[column])

        st.dataframe(
            movement_display,
            use_container_width=True,
            hide_index=True,
            height=420,
            column_config={
                "Team": st.column_config.TextColumn(
                    "Team",
                    help="NCAA team meeting both handle thresholds",
                    pinned=True,
                ),
                "Spread Handle %": st.column_config.NumberColumn(
                    "Spread Handle %",
                    format="%.1f%%",
                ),
                "Moneyline Handle %": st.column_config.NumberColumn(
                    "Moneyline Handle %",
                    format="%.1f%%",
                ),
            },
        )

    st.markdown("### Teams requiring verification")

    if verification.empty:
        st.success("No flagged rows in the latest CSV.")
    else:
        st.warning(
            "These rows contain 0% handles or incomplete "
            "market information. Verify against VSiN "
            "before treating them as actionable."
        )

        st.dataframe(
            verification[list(display_columns)].rename(
                columns=display_columns
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.download_button(
        "Download automated contrarian results",
        automated.to_csv(index=False),
        "automated_ncaa_contrarians.csv",
        "text/csv",
        key="automated_download",
    )

except Exception as exc:
    st.error(
        "Could not load automated VSiN results: "
        + str(exc)
    )

st.divider()

st.subheader("1. Source status")

for name, url in [
    ("VSiN betting splits", VSIN_URL),
    ("Evan Analytics odds", EV_URL),
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
        "Upload VSiN splits CSV",
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

        splits = splits[
            splits["market"].isin(["spread", "moneyline"])
            & splits["handle_pct"].between(0, 100)
            & (splits["handle_pct"] < threshold)
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
                delta = old - new
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
            "ncaa_contrarian_analysis.csv",
            "text/csv",
        )

    except Exception as exc:
        st.error(f"Could not analyze these files: {exc}")

else:
    st.info(
        "Upload both CSV files to calculate contrarian signals. "
        "The live source checks above do not yet populate the "
        "analysis automatically."
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










