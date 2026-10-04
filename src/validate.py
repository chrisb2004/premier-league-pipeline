"""Validate stage: data quality checks on the clean, one-row-per-match data.

Each check returns a list of problem descriptions (empty list = passed).
validate_matches() runs them all and raises one error listing every problem,
so a bad run reports everything at once instead of one issue per run.
"""
import pandas as pd

MATCHES_PER_SEASON = 380   # 20 teams, each plays the other 19 home and away
TEAMS_PER_SEASON = 20

KEY_COLUMNS = ["match_id", "season", "date", "home_team", "away_team",
               "home_goals", "away_goals", "full_time_result"]

NON_NEGATIVE_COLUMNS = [
    "home_goals", "away_goals",
    "home_shots", "away_shots", "home_shots_on_target", "away_shots_on_target",
    "home_corners", "away_corners",
    "home_yellow_cards", "away_yellow_cards", "home_red_cards", "away_red_cards",
]


class ValidationError(Exception):
    """Raised when the data fails one or more quality checks."""


def check_no_duplicates(matches: pd.DataFrame) -> list[str]:
    """The same fixture on the same date must appear only once."""
    dupes = matches[matches.duplicated(["date", "home_team", "away_team"], keep=False)]
    if dupes.empty:
        return []
    examples = dupes[["date", "home_team", "away_team"]].head(3).to_dict("records")
    return [f"{len(dupes)} rows are duplicate matches, e.g. {examples}"]


def check_no_negatives(matches: pd.DataFrame) -> list[str]:
    """Goals, shots, corners and cards are counts, so never below zero."""
    problems = []
    for col in NON_NEGATIVE_COLUMNS:
        negative = (matches[col] < 0).sum()
        if negative:
            problems.append(f"{negative} negative values in '{col}'")
    return problems


def check_result_matches_goals(matches: pd.DataFrame) -> list[str]:
    """full_time_result (H/D/A) must agree with the goal counts."""
    expected = pd.Series("D", index=matches.index)
    expected[matches["home_goals"] > matches["away_goals"]] = "H"
    expected[matches["home_goals"] < matches["away_goals"]] = "A"

    wrong = matches[matches["full_time_result"] != expected]
    if wrong.empty:
        return []
    return [f"{len(wrong)} matches where the result disagrees with the score, "
            f"e.g. match_ids {wrong['match_id'].head(5).tolist()}"]


def check_season_sizes(matches: pd.DataFrame) -> list[str]:
    """Every season must have exactly 380 matches and 20 distinct teams."""
    problems = []
    for season, games in matches.groupby("season"):
        if len(games) != MATCHES_PER_SEASON:
            problems.append(f"{season}: {len(games)} matches, expected {MATCHES_PER_SEASON}")
        teams = set(games["home_team"]) | set(games["away_team"])
        if len(teams) != TEAMS_PER_SEASON:
            problems.append(f"{season}: {len(teams)} teams, expected {TEAMS_PER_SEASON}")
    return problems


def check_no_missing(matches: pd.DataFrame) -> list[str]:
    """Key columns must never be empty."""
    missing = matches[KEY_COLUMNS].isna().sum()
    return [f"{count} missing values in '{col}'" for col, count in missing.items() if count]


ALL_CHECKS = [
    check_no_missing,   # first: missing values can make the other checks misleading
    check_no_duplicates,
    check_no_negatives,
    check_result_matches_goals,
    check_season_sizes,
]


def validate_matches(matches: pd.DataFrame) -> None:
    """Run every check; raise ValidationError listing all problems, if any."""
    problems = []
    for check in ALL_CHECKS:
        problems.extend(check(matches))
    if problems:
        message = "\n".join(f"  - {p}" for p in problems)
        raise ValidationError(f"Data failed {len(problems)} quality check(s):\n{message}")


if __name__ == "__main__":
    from src.db import get_engine
    from src.extract import read_staging
    from src.transform import clean_matches

    matches = clean_matches(read_staging(get_engine()))
    validate_matches(matches)
    print(f"All {len(ALL_CHECKS)} checks passed on {len(matches)} matches.")
