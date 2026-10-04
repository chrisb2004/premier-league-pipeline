# Premier League Analytics Pipeline

## Who I am and how to work with me
I'm a Computer Engineering student building this project for an internship application
(AI Software Engineering intern, Intel AIDA). I'm comfortable with SQL, Java, C#, and
Python for DSA, but new to data pipelines, pandas, and Power BI.

**I need to understand everything we build, well enough to explain it in an interview.**
- Build ONE stage at a time. Do not write the whole project at once.
- Before writing code for a stage, briefly explain what we're about to do and why.
- After each stage, explain the key decisions (why this library, why this structure,
  what could go wrong) and wait for me before moving on.
- Prefer simple, readable code over clever code. Add short comments.
- When I ask "why", give a real answer, including alternatives we didn't choose.

## Goal
A Python ETL pipeline that takes real Premier League match data, cleans and validates it,
loads it into a star schema in MySQL, and feeds a Power BI dashboard.

## Data source
- football-data.co.uk, free historical CSVs, one file per season (Premier League = E0).
- Use the last 10 complete seasons.
- Expected columns include Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR, HTHG, HTAG, HTR,
  HS, AS, HST, AST, HC, AC, HY, AY, HR, AR, Referee, plus betting-odds columns we ignore.
- Verify the columns against the actual files first: formats vary between seasons
  (e.g. date format dd/mm/yy vs dd/mm/yyyy, missing columns in older files).
  Handling this is part of the point of the project.

## Stack
Python 3.11+, pandas, SQLAlchemy + PyMySQL, MySQL, pytest, python-dotenv, Power BI Desktop.
Database credentials go in a `.env` file that is NOT committed (add it to `.gitignore`).

## Project structure
```
data/raw/            downloaded CSVs (not committed)
src/extract.py       load CSVs into a MySQL staging table
src/transform.py     clean, standardize, compute metrics
src/validate.py      data quality checks
src/load.py          build the star schema tables
src/pipeline.py      runs everything end to end
tests/               pytest tests for transform and validate
dashboard/           .pbix file and screenshots
README.md
```

## Pipeline stages
1. **Extract**: read each season's CSV, add a `season` column, write everything to a
   staging table `stg_matches` in MySQL. Then read it back from MySQL into pandas,
   so the project shows SQL as the source system.
2. **Transform**: parse dates consistently, standardize team names, keep only the needed
   columns, and reshape to one row per team per match (team perspective), computing
   result (W/D/L), points, goals for/against, and home/away flag.
3. **Validate**: checks that fail loudly with clear messages:
   - no duplicate matches (same date + home + away)
   - goals, shots, and cards are never negative
   - FTR matches the goal counts
   - every season has 380 matches and 20 teams
   - no missing values in key columns
4. **Load**: write the star schema (replace tables on each run so the pipeline can be
   re-run safely).

## Star schema
- `fact_team_match` (grain: one row per team per match): match_id, date_key, season_key,
  team_key, opponent_key, is_home, goals_for, goals_against, shots, shots_on_target,
  corners, yellow_cards, red_cards, result, points
- `dim_team`: team_key, team_name
- `dim_season`: season_key, season_label (e.g. "2024-25")
- `dim_date`: date_key, date, year, month, matchday-week info

The team-perspective grain makes per-team stats in Power BI simple (no home/away
double-counting logic in DAX). Be ready to explain this choice.

## Tests (pytest)
Small, focused tests for the transform logic (W/D/L and points are correct, reshaping
produces 2 rows per match) and for the validation checks (each check catches bad data).

## Power BI (I build this myself in the GUI)
Claude Code can't operate Power BI, but should help me with: connecting to MySQL,
setting up relationships between fact and dimension tables, and writing DAX measures
(total points, win %, goals per game, points per game, form over last 5 matches).
Target: one solid page (league table by season, team trends over seasons, home vs away).
A second page is a bonus.

## README
Project overview, pipeline diagram (Mermaid), schema description, how to run it,
validation checks explained, dashboard screenshot.

## Schedule (about 4 hours/day, I also have coursework)
- **Friday**: explore the CSVs (1 h), setup + repo (1-1.5 h), extract stage (1-1.5 h)
- **Saturday**: transform + validate (2-2.5 h), load star schema (1.5-2 h), tests if time
- **Sunday**: Power BI dashboard (2.5-3 h), README + final clean run (1-1.5 h)

If behind schedule, cut in this order: tests, then the second dashboard page.
Never cut: working end-to-end run, README.
