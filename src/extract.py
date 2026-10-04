"""Extract stage: raw season CSVs -> MySQL staging table -> pandas DataFrame."""
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
from sqlalchemy.engine import Engine

from src.db import get_engine

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# Last 10 complete seasons, in football-data.co.uk's short code ("1617" = 2016-17)
SEASONS = ["1617", "1718", "1819", "1920", "2021", "2122", "2223", "2324", "2425", "2526"]

# Note: no "www." -- the www address answers with a redirect
BASE_URL = "https://football-data.co.uk/mmz4281/{code}/E0.csv"

# The only columns we keep. Files have 62-132 columns depending on the season
# (mostly betting odds), so we always select by name, never by position.
NEEDED_COLUMNS = [
    "Date", "HomeTeam", "AwayTeam",
    "FTHG", "FTAG", "FTR",          # full-time goals and result
    "HTHG", "HTAG", "HTR",          # half-time goals and result
    "HS", "AS", "HST", "AST",       # shots, shots on target
    "HC", "AC",                     # corners
    "HY", "AY", "HR", "AR",         # yellow and red cards
    "Referee",
]

STAGING_TABLE = "stg_matches"

def season_label(code: str) -> str:
    """'1617' -> '2016-17'"""
    return f"20{code[:2]}-{code[2:]}"


def download_missing(seasons: list[str] = SEASONS) -> None:
    """Download any season CSV not already in data/raw/."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for code in seasons:
        path = RAW_DIR / f"E0_{code}.csv"

        if path.exists() and path.stat().st_size > 0:
            continue

        print(f"Downloading {season_label(code)}...")

        with urlopen(BASE_URL.format(code=code)) as response:  # follows redirects
            content = response.read()
            
        # A "successful" download can still be empty (we hit this with curl)
        if not content:
            raise RuntimeError(f"Downloaded file for {season_label(code)} is empty")
        
        # Saves the file
        path.write_bytes(content) 


def read_season_csv(code: str) -> pd.DataFrame:
    """Read one season's CSV, keep the needed columns, and tag it with the season."""
    path = RAW_DIR / f"E0_{code}.csv"

    # utf-8-sig strips the invisible BOM some files start with ';' without it the
    # first column is read as 'ï»¿Div' instead of 'Div'.
    # Date stays a string here: parsing it is the transform stage's job.
    df = pd.read_csv(path, encoding="utf-8-sig", dtype={"Date": str})

    missing = []
    
    for col in NEEDED_COLUMNS:
        if col not in df.columns:
            missing.append(col)

    if missing:
        raise ValueError(f"{path.name} is missing columns: {missing}")

    df = df[NEEDED_COLUMNS].copy()
    df.insert(0, "season", season_label(code))  # put season first for readability
    return df


def write_staging(df: pd.DataFrame, engine: Engine) -> None:
    """Write all seasons to the staging table, replacing it so re-runs are safe."""
    df.to_sql(STAGING_TABLE, engine, if_exists="replace", index=False)


def read_staging(engine: Engine) -> pd.DataFrame:
    """Read the staging table back: from here on, MySQL is the source system."""
    return pd.read_sql(f"SELECT * FROM {STAGING_TABLE}", engine)


def extract(engine: Engine | None = None) -> pd.DataFrame:
    """Run the full extract stage and return the staged matches."""
    engine = engine or get_engine()
    download_missing()
    all_seasons = pd.concat([read_season_csv(code) for code in SEASONS], ignore_index=True)
    write_staging(all_seasons, engine)
    return read_staging(engine)


if __name__ == "__main__":
    matches = extract()
    print(f"{len(matches)} rows in {STAGING_TABLE}")
    print(matches.groupby("season").size().to_string())
    print(matches.dtypes.to_string())
