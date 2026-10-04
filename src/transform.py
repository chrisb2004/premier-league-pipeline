"""Transform stage: staged matches -> clean matches -> one row per team per match."""
import pandas as pd

# Raw football-data.co.uk names -> readable names used from here on.
# Half-time scores and Referee are left out: the star schema doesn't use them.
COLUMN_NAMES = {
    "Date": "date",
    "HomeTeam": "home_team",
    "AwayTeam": "away_team",
    "FTHG": "home_goals",
    "FTAG": "away_goals",
    "FTR": "full_time_result",   # kept only so validate can check it against the goals
    "HS": "home_shots",
    "AS": "away_shots",          # 'AS' is a reserved word in SQL, another reason to rename
    "HST": "home_shots_on_target",
    "AST": "away_shots_on_target",
    "HC": "home_corners",
    "AC": "away_corners",
    "HY": "home_yellow_cards",
    "AY": "away_yellow_cards",
    "HR": "home_red_cards",
    "AR": "away_red_cards",
}

# Every team name in the source -> the full name shown on the dashboard.
# Teams already using their full name map to themselves, so that ANY name
# missing from this dict is treated as unknown (e.g. a newly promoted team).
TEAM_NAMES = {
    "Arsenal": "Arsenal",
    "Aston Villa": "Aston Villa",
    "Bournemouth": "Bournemouth",
    "Brentford": "Brentford",
    "Brighton": "Brighton & Hove Albion",
    "Burnley": "Burnley",
    "Cardiff": "Cardiff City",
    "Chelsea": "Chelsea",
    "Crystal Palace": "Crystal Palace",
    "Everton": "Everton",
    "Fulham": "Fulham",
    "Huddersfield": "Huddersfield Town",
    "Hull": "Hull City",
    "Ipswich": "Ipswich Town",
    "Leeds": "Leeds United",
    "Leicester": "Leicester City",
    "Liverpool": "Liverpool",
    "Luton": "Luton Town",
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Middlesbrough": "Middlesbrough",
    "Newcastle": "Newcastle United",
    "Norwich": "Norwich City",
    "Nott'm Forest": "Nottingham Forest",
    "Sheffield United": "Sheffield United",
    "Southampton": "Southampton",
    "Stoke": "Stoke City",
    "Sunderland": "Sunderland",
    "Swansea": "Swansea City",
    "Tottenham": "Tottenham Hotspur",
    "Watford": "Watford",
    "West Brom": "West Bromwich Albion",
    "West Ham": "West Ham United",
    "Wolves": "Wolverhampton Wanderers",
}

POINTS = {"W": 3, "D": 1, "L": 0}


# ---------------------------------------------------------------------------
# Step 1: clean, still one row per match
# ---------------------------------------------------------------------------

def parse_dates(raw: pd.Series) -> pd.Series:
    """Parse 'dd/mm/yy' (2016-17 file) and 'dd/mm/yyyy' (all others) explicitly.

    Giving pandas the exact format means it never guesses day-first vs
    month-first, and any value that fits neither format raises an error.
    """
    is_short = raw.str.len() == 8                                   # e.g. '13/08/16'
    short_dates = pd.to_datetime(raw[is_short], format="%d/%m/%y")
    long_dates = pd.to_datetime(raw[~is_short], format="%d/%m/%Y")  # e.g. '11/08/2017'
    # Stitch the two halves back together in the original row order
    return pd.concat([short_dates, long_dates]).reindex(raw.index)


def standardize_team_names(names: pd.Series) -> pd.Series:
    """Map source team names to full names; fail on any name we don't know."""
    unknown = sorted(set(names) - set(TEAM_NAMES))
    if unknown:
        raise ValueError(f"Unknown team names, add them to TEAM_NAMES: {unknown}")
    return names.map(TEAM_NAMES)


def clean_matches(staged: pd.DataFrame) -> pd.DataFrame:
    """Rename, keep needed columns, parse dates, standardize teams, add match_id."""
    matches = staged.rename(columns=COLUMN_NAMES)
    matches = matches[["season", *COLUMN_NAMES.values()]].copy()

    matches["date"] = parse_dates(matches["date"])
    matches["home_team"] = standardize_team_names(matches["home_team"])
    matches["away_team"] = standardize_team_names(matches["away_team"])

    # Chronological order, so match_id 1 is the first match of 2016-17.
    # home_team breaks ties between matches on the same day (a team plays once a day).
    matches = matches.sort_values(["date", "home_team"]).reset_index(drop=True)
    matches.insert(0, "match_id", matches.index + 1)
    return matches


# ---------------------------------------------------------------------------
# Step 2: reshape to one row per team per match
# ---------------------------------------------------------------------------

def _one_side(matches: pd.DataFrame, side: str, other: str) -> pd.DataFrame:
    """Every match from one side's point of view ('home' or 'away')."""
    return pd.DataFrame({
        "match_id": matches["match_id"],
        "season": matches["season"],
        "date": matches["date"],
        "team": matches[f"{side}_team"],
        "opponent": matches[f"{other}_team"],
        "is_home": side == "home",
        "goals_for": matches[f"{side}_goals"],
        "goals_against": matches[f"{other}_goals"],
        "shots": matches[f"{side}_shots"],
        "shots_on_target": matches[f"{side}_shots_on_target"],
        "corners": matches[f"{side}_corners"],
        "yellow_cards": matches[f"{side}_yellow_cards"],
        "red_cards": matches[f"{side}_red_cards"],
    })


def to_team_perspective(matches: pd.DataFrame) -> pd.DataFrame:
    """Turn each match into two rows (home team's view and away team's view),
    then compute result (W/D/L) and points."""
    home_rows = _one_side(matches, side="home", other="away")
    away_rows = _one_side(matches, side="away", other="home")
    team_rows = pd.concat([home_rows, away_rows], ignore_index=True)

    # Start everything as a draw, then overwrite wins and losses
    team_rows["result"] = "D"
    team_rows.loc[team_rows["goals_for"] > team_rows["goals_against"], "result"] = "W"
    team_rows.loc[team_rows["goals_for"] < team_rows["goals_against"], "result"] = "L"
    team_rows["points"] = team_rows["result"].map(POINTS)

    # Keep the two rows of each match next to each other, home team first
    return (team_rows
            .sort_values(["match_id", "is_home"], ascending=[True, False])
            .reset_index(drop=True))


if __name__ == "__main__":
    from src.db import get_engine
    from src.extract import read_staging

    matches = clean_matches(read_staging(get_engine()))
    team_rows = to_team_perspective(matches)

    print(f"{len(matches)} matches -> {len(team_rows)} team rows\n")
    print(matches.dtypes.to_string(), "\n")
    print(team_rows[team_rows["match_id"] == matches["match_id"].iloc[-380]]
          [["match_id", "date", "team", "opponent", "is_home",
            "goals_for", "goals_against", "result", "points"]].to_string(index=False))

    # Sanity check against reality: the 2023-24 final table (Man City 91, Arsenal 89, Liverpool 82)
    table = (team_rows[team_rows["season"] == "2023-24"]
             .groupby("team")["points"].sum()
             .sort_values(ascending=False))
    print("\n2023-24 top 3:\n" + table.head(3).to_string())
