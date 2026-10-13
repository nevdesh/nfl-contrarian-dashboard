NFL Contrarian Dashboard
A Streamlit dashboard for researching NFL contrarian betting candidates.
What it does
Links to DraftKings Network betting splits and EV Analytics NFL odds.
Lets you upload verified CSV data from those sources.
Finds teams with handle below the selected threshold in both the moneyline and spread markets.
Compares earlier and later odds and flags favorable movement.
Important limitation
The dashboard currently checks whether the source pages are reachable and shows any ordinary HTML tables it can detect. It does not automatically extract the live betting data from those sites yet. Until that integration is implemented and tested, use the CSV upload workflow. Do not treat a page being reachable as proof that its data was imported.
CSV formats
Splits CSV
Required columns: `game`, `team`, `market`, `handle_pct`
Use `moneyline` and `spread` as the market names. `handle_pct` is a number from 0 to 100.
Odds history CSV
Required columns: `game`, `team`, `market`, `line`, `timestamp`
Use American odds for moneyline values (such as `+145` or `-120`) and signed spreads from the named team's perspective (such as `+3.5`). Include at least two timestamps for each team and market.
Run locally
Install Python.
In a terminal, go into this folder.
Run `pip install -r requirements.txt`.
Run `streamlit run app.py`.
This is a research aid, not betting advice. Verify data and market definitions before using any signal.
