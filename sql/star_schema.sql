-- Star schema for the Premier League dashboard.
-- Run by src/load.py on every pipeline run: drop everything, then recreate.

-- Drop the fact table first: its foreign keys point at the dimensions,
-- so MySQL won't let us drop a dimension while the fact table still exists.
DROP TABLE IF EXISTS fact_team_match;
DROP TABLE IF EXISTS dim_team;
DROP TABLE IF EXISTS dim_season;
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_team (
    team_key   SMALLINT     NOT NULL PRIMARY KEY,
    team_name  VARCHAR(50)  NOT NULL UNIQUE
);

CREATE TABLE dim_season (
    season_key    SMALLINT  NOT NULL PRIMARY KEY,
    season_label  CHAR(7)   NOT NULL UNIQUE      -- e.g. '2024-25'
);

-- One row per calendar day from the first to the last match (not only match days),
-- so date-based charts in Power BI have no gaps.
CREATE TABLE dim_date (
    date_key    INT         NOT NULL PRIMARY KEY,  -- yyyymmdd, e.g. 20250815
    full_date   DATE        NOT NULL UNIQUE,
    year        SMALLINT    NOT NULL,
    month       TINYINT     NOT NULL,
    month_name  VARCHAR(9)  NOT NULL,
    iso_week    TINYINT     NOT NULL,
    day_name    VARCHAR(9)  NOT NULL,
    is_weekend  BOOLEAN     NOT NULL
);

-- Grain: one row per team per match (each match appears twice: home and away view)
CREATE TABLE fact_team_match (
    match_id         INT               NOT NULL,
    team_key         SMALLINT          NOT NULL,
    opponent_key     SMALLINT          NOT NULL,
    season_key       SMALLINT          NOT NULL,
    date_key         INT               NOT NULL,
    game_number      TINYINT           NOT NULL,  -- team's 1st..38th match of the season
    is_home          BOOLEAN           NOT NULL,
    goals_for        TINYINT UNSIGNED  NOT NULL,
    goals_against    TINYINT UNSIGNED  NOT NULL,
    shots            TINYINT UNSIGNED  NOT NULL,
    shots_on_target  TINYINT UNSIGNED  NOT NULL,
    corners          TINYINT UNSIGNED  NOT NULL,
    yellow_cards     TINYINT UNSIGNED  NOT NULL,
    red_cards        TINYINT UNSIGNED  NOT NULL,
    result           CHAR(1)           NOT NULL,  -- 'W', 'D' or 'L'
    points           TINYINT UNSIGNED  NOT NULL,

    PRIMARY KEY (match_id, team_key),
    FOREIGN KEY (team_key)     REFERENCES dim_team (team_key),
    FOREIGN KEY (opponent_key) REFERENCES dim_team (team_key),
    FOREIGN KEY (season_key)   REFERENCES dim_season (season_key),
    FOREIGN KEY (date_key)     REFERENCES dim_date (date_key)
);
