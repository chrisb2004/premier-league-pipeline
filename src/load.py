"""Load stage: team-perspective rows -> star schema tables in MySQL."""
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "sql" / "star_schema.sql"


# ---------------------------------------------------------------------------
# Build each table as a DataFrame
# ---------------------------------------------------------------------------

def build_dim_team(team_rows: pd.DataFrame) -> pd.DataFrame:
    """One row per team, numbered alphabetically."""
    names = sorted(team_rows["team"].unique())
    return pd.DataFrame({"team_key": range(1, len(names) + 1), "team_name": names})


def build_dim_season(team_rows: pd.DataFrame) -> pd.DataFrame:
    """One row per season, numbered in order ('2016-17' sorts before '2017-18')."""
    labels = sorted(team_rows["season"].unique())
    return pd.DataFrame({"season_key": range(1, len(labels) + 1), "season_label": labels})


def date_to_key(dates: pd.Series) -> pd.Series:
    """2025-08-15 -> 20250815: readable, unique, and sorts like the date itself."""
    return dates.dt.strftime("%Y%m%d").astype(int)


def build_dim_date(team_rows: pd.DataFrame) -> pd.DataFrame:
    """One row for every calendar day between the first and last match."""
    days = pd.Series(pd.date_range(team_rows["date"].min(), team_rows["date"].max(), freq="D"))
    return pd.DataFrame({
        "date_key": date_to_key(days),
        "full_date": days.dt.date,
        "year": days.dt.year,
        "month": days.dt.month,
        "month_name": days.dt.month_name(),
        "iso_week": days.dt.isocalendar().week.astype(int),
        "day_name": days.dt.day_name(),
        "is_weekend": days.dt.dayofweek >= 5,   # Monday = 0 ... Saturday = 5, Sunday = 6
    })


def build_fact(team_rows: pd.DataFrame, dim_team: pd.DataFrame,
               dim_season: pd.DataFrame) -> pd.DataFrame:
    """Replace names and dates with keys pointing into the dimension tables."""
    team_key = dict(zip(dim_team["team_name"], dim_team["team_key"]))
    season_key = dict(zip(dim_season["season_label"], dim_season["season_key"]))

    fact = team_rows.sort_values("match_id").copy()   # match_id is chronological
    fact["team_key"] = fact["team"].map(team_key)
    fact["opponent_key"] = fact["opponent"].map(team_key)
    fact["season_key"] = fact["season"].map(season_key)
    fact["date_key"] = date_to_key(fact["date"])
    # Count each team's matches within a season: 1, 2, ... 38
    fact["game_number"] = fact.groupby(["season", "team"]).cumcount() + 1

    return fact[[
        "match_id", "team_key", "opponent_key", "season_key", "date_key", "game_number",
        "is_home", "goals_for", "goals_against", "shots", "shots_on_target",
        "corners", "yellow_cards", "red_cards", "result", "points",
    ]]


# ---------------------------------------------------------------------------
# Write to MySQL
# ---------------------------------------------------------------------------

def recreate_schema(engine: Engine) -> None:
    """Run sql/star_schema.sql: drop the four tables and create them empty."""
    statements = [s.strip() for s in SCHEMA_FILE.read_text().split(";") if s.strip()]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def load(team_rows: pd.DataFrame, engine: Engine) -> dict[str, int]:
    """Rebuild the star schema and fill it. Returns row counts per table."""
    dim_team = build_dim_team(team_rows)
    dim_season = build_dim_season(team_rows)
    dim_date = build_dim_date(team_rows)
    fact = build_fact(team_rows, dim_team, dim_season)

    recreate_schema(engine)

    # Dimensions first: the fact table's foreign keys need their rows to exist.
    # "append" because the tables already exist with our own types and keys;
    # "replace" would throw away that structure and let pandas guess again.
    tables = {"dim_team": dim_team, "dim_season": dim_season,
              "dim_date": dim_date, "fact_team_match": fact}
    for name, df in tables.items():
        df.to_sql(name, engine, if_exists="append", index=False)

    return {name: len(df) for name, df in tables.items()}


if __name__ == "__main__":
    from src.db import get_engine
    from src.extract import read_staging
    from src.transform import clean_matches, to_team_perspective
    from src.validate import validate_matches

    engine = get_engine()
    matches = clean_matches(read_staging(engine))
    validate_matches(matches)
    counts = load(to_team_perspective(matches), engine)
    print(counts)

    # Query the star schema with plain SQL: the 2023-24 top 5
    league_table = pd.read_sql("""
        SELECT t.team_name, COUNT(*) AS played, SUM(f.points) AS points,
               SUM(f.goals_for) - SUM(f.goals_against) AS goal_diff
        FROM fact_team_match f
        JOIN dim_team   t ON t.team_key = f.team_key
        JOIN dim_season s ON s.season_key = f.season_key
        WHERE s.season_label = '2023-24'
        GROUP BY t.team_name
        ORDER BY points DESC, goal_diff DESC
        LIMIT 5
    """, engine)
    print(league_table.to_string(index=False))
