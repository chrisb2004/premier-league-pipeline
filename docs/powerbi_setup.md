# Power BI setup (Windows)

Power BI Desktop only runs on Windows. These steps set up the whole project on a
Windows machine (or VM): run the pipeline into a local MySQL, then build the
dashboard on top of the star schema.

---

## Part 1: run the pipeline on Windows

### 1.1 Install the tools

| Tool | Where | Notes |
|---|---|---|
| Python 3.12 | python.org/downloads | Tick **"Add python.exe to PATH"** in the installer |
| MySQL Server 8.x | dev.mysql.com/downloads/installer | "Server only" or "Full". Remember the root password you set |
| MySQL Connector/NET | dev.mysql.com/downloads/connector/net | **Power BI needs this to talk to MySQL.** Without it, the MySQL connector in Power BI shows an error |
| Git | git-scm.com | Or download the repo as a ZIP from GitHub |
| Power BI Desktop | Microsoft Store | Free |

### 1.2 Clone and install

In PowerShell or Command Prompt:

```
git clone https://github.com/chrisb2004/premier-league-pipeline.git
cd premier-league-pipeline
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

If the repo is private, Git opens a browser window to log in to GitHub the first time.

Windows paths use `.venv\Scripts\...` where the Mac uses `.venv/bin/...`.

### 1.3 Create the database and `.env`

Create the empty database. Use **MySQL Workbench** or the **MySQL Command Line Client**
(from the Start menu); `mysql` is usually not on the Windows PATH:

```sql
CREATE DATABASE premier_league;
```

Then copy the template and fill in your Windows MySQL user and password:

```
copy .env.example .env
notepad .env
```

### 1.4 Run the pipeline

```
.venv\Scripts\python -m src.pipeline
```

Expected ending:

```
INFO    dim_team            34 rows
INFO    dim_season          10 rows
INFO    dim_date          3572 rows
INFO    fact_team_match   7600 rows
INFO  Done in ...
```

The first run also downloads the 10 season CSVs into `data\raw\`.

---

## Part 2: connect Power BI to MySQL

1. Open Power BI Desktop, then **Home → Get data → More… → MySQL database**.
2. **Server:** `localhost`  **Database:** `premier_league`
3. **Data Connectivity mode: Import.** See "Import vs DirectQuery" below.
4. Credentials: choose the **Database** tab (not Windows), and enter the MySQL user/password from `.env`.
5. In the Navigator, tick the four star schema tables only:
   `premier_league.dim_date`, `premier_league.dim_season`, `premier_league.dim_team`,
   `premier_league.fact_team_match`.
   **Don't** load `stg_matches`: it's raw staging data, not for reporting.
6. Click **Load**.

**Import vs DirectQuery.** Import copies the data into the .pbix file: visuals are fast, and
DAX works fully. DirectQuery leaves the data in MySQL and sends a query on every click. That's
useful for huge or live data, but slower, and it limits some DAX. 7,600 rows → Import.
To pick up new data after re-running the pipeline, click **Home → Refresh**.

**Optional: shorter table names.** Power BI may name the tables `premier_league dim_team`.
Right-click each table in the Data pane → Rename → `dim_team`, `dim_season`, `dim_date`,
`fact_team_match`. The DAX below assumes these names.

---

## Part 3: the data model (relationships)

Open **Model view** (the third icon on the left). Power BI may have auto-created some
relationships; check them against this list and fix or delete anything different.

| From (many side) | To (one side) | Active? |
|---|---|---|
| `fact_team_match[team_key]` | `dim_team[team_key]` | **Yes** |
| `fact_team_match[season_key]` | `dim_season[season_key]` | **Yes** |
| `fact_team_match[date_key]` | `dim_date[date_key]` | **Yes** |
| `fact_team_match[opponent_key]` | `dim_team[team_key]` | **No (inactive, dashed line)** |

To create one: drag the column from the fact table onto the matching column in the dimension.
For each relationship, double-click it and check:
**Cardinality: Many to one (\*:1)**, **Cross filter direction: Single**.

**Why `opponent_key` is inactive.** The fact table links to `dim_team` twice: as the team and as
the opponent (a "role-playing dimension"). Power BI allows only one active path between two
tables, otherwise "filter to Arsenal" would be ambiguous: Arsenal's matches, or matches against
Arsenal? `team_key` is the active one. A measure can switch to the opponent path with
`USERELATIONSHIP` (example at the end).

**Why single direction.** Filters flow from dimensions to the fact table (pick a season →
see that season's matches). Two-way filtering can create ambiguous paths and confusing results;
in a star schema, single is the standard.

### Model clean-up (2 minutes, makes the field list much easier to use)

- **Mark the date table:** select `dim_date` → Table tools → **Mark as date table** → pick `full_date`.
- **Sort month names by month number:** select `dim_date[month_name]` → Column tools →
  **Sort by column** → `month`. Otherwise months sort alphabetically (April, August, …).
- **Hide key columns** (right-click → Hide in report view): every `*_key` column in all tables,
  plus `match_id`. Report builders should pick `team_name`, never `team_key`.
- **Check `is_home`:** in the Data view it should show True/False. If it shows 1/0 instead,
  Home → Transform data → select the column → Data type → **True/False** → Close & Apply.

---

## Part 4: DAX measures

Create a home for them: Home → **Enter data** → name the table `_Measures` → Load.
Then select `_Measures` and use **New measure** for each one below. Keeping measures in their
own table, rather than scattered across the fact table, is a common convention.

### Basic measures

```DAX
Matches Played = COUNTROWS ( fact_team_match )

Total Points = SUM ( fact_team_match[points] )

Wins   = CALCULATE ( COUNTROWS ( fact_team_match ), fact_team_match[result] = "W" )
Draws  = CALCULATE ( COUNTROWS ( fact_team_match ), fact_team_match[result] = "D" )
Losses = CALCULATE ( COUNTROWS ( fact_team_match ), fact_team_match[result] = "L" )

Goals For       = SUM ( fact_team_match[goals_for] )
Goals Against   = SUM ( fact_team_match[goals_against] )
Goal Difference = [Goals For] - [Goals Against]
```

(Enter each measure separately: one `Name = expression` per New measure.)

### Rates

```DAX
Win % = DIVIDE ( [Wins], [Matches Played] )

Goals per Game = DIVIDE ( [Goals For], [Matches Played] )

Points per Game = DIVIDE ( [Total Points], [Matches Played] )
```

`DIVIDE` returns blank instead of an error when dividing by zero. Format **Win %** as a
percentage (Measure tools → Format → Percentage).

### Form over the last 5 matches

Uses `game_number` (each team's 1st–38th match of the season). Use these with a **single
season selected**.

```DAX
Form Points (Last 5) =
VAR LastGame = MAX ( fact_team_match[game_number] )
RETURN
    CALCULATE (
        [Total Points],
        fact_team_match[game_number] > LastGame - 5,
        fact_team_match[game_number] <= LastGame
    )
```

```DAX
Form (Last 5) =
VAR LastGame = MAX ( fact_team_match[game_number] )
RETURN
    CONCATENATEX (
        FILTER ( fact_team_match, fact_team_match[game_number] > LastGame - 5 ),
        fact_team_match[result],
        "",
        fact_team_match[game_number], ASC
    )
```

The second one shows something like `WWDLW`, oldest to newest.

**How they work:** `MAX(game_number)` finds the team's latest game in the current filter
(38 for a finished season). `CALCULATE` then **replaces** the filter on `game_number` with
"the last 5 games", while keeping the filters on team and season. That idea, CALCULATE changing
the filter context, is the most important concept in DAX.

### League position

```DAX
Position =
IF (
    ISBLANK ( [Matches Played] ),
    BLANK (),
    RANKX (
        ALLSELECTED ( dim_team ),
        [Total Points] + [Goal Difference] / 1000,
        ,
        DESC,
        DENSE
    )
)
```

Ranks teams by points, with goal difference as the tie-breaker (dividing by 1000 keeps it
smaller than one point). `ALLSELECTED` ranks against all teams in the current selection, not
just the row's own team. The `IF ( ISBLANK ( ... ) )` returns blank for teams that didn't play
in the selected season. Without it, RANKX still gives those teams a rank (21st), and since one
measure isn't blank, the table shows all 34 teams instead of 20.

### Cumulative points (for the season race chart)

```DAX
Cumulative Points =
VAR CurrentGame = MAX ( fact_team_match[game_number] )
RETURN
    CALCULATE ( [Total Points], fact_team_match[game_number] <= CurrentGame )
```

### Home vs away

Add a **calculated column** (not a measure) on `fact_team_match`: select the table → New column:

```DAX
Venue = IF ( fact_team_match[is_home], "Home", "Away" )
```

Columns are computed once per row and can go on an axis or legend; measures are computed per
visual cell. "Home"/"Away" is a category, so it's a column.

### Bonus: using the inactive opponent relationship

```DAX
Points Conceded to Opponent =
CALCULATE (
    [Total Points],
    USERELATIONSHIP ( fact_team_match[opponent_key], dim_team[team_key] )
)
```

With `dim_team[team_name]` on rows, this shows the points other teams took **against** that team.

---

## Part 5: page 1 layout

Target: one solid page with three areas.

**1. Season slicer** (top). Slicer visual → `dim_season[season_label]`.
Format → Slicer settings → **Single select** on. Dropdown style saves space.

**2. League table** (left, largest). Table visual with:
`Position`, `dim_team[team_name]`, `Matches Played`, `Wins`, `Draws`, `Losses`,
`Goals For`, `Goals Against`, `Goal Difference`, `Total Points`, `Form (Last 5)`.
Sort by `Position` ascending (click the column header). Teams not in the selected season
disappear automatically, because all their measures are blank (this is why `Position` needs
its ISBLANK check).

**3. Team trends over seasons** (top right). Line chart:
X-axis `dim_season[season_label]`, Y-axis `Points per Game`, Legend `dim_team[team_name]`.
34 lines is unreadable, so add a **team slicer** (multi-select) and pick 3–6 teams.
This visual should ignore the season slicer: select the season slicer → Format →
**Edit interactions** → click the **"None"** icon above the line chart.

**4. Home vs away** (bottom right). Clustered column chart:
X-axis `dim_team[team_name]`, Y-axis `Points per Game`, Legend `fact_team_match[Venue]`.
Shows how much each team relies on home form in the selected season.

**Sanity check:** select 2023-24. Manchester City should be 1st on 91 points, Arsenal 2nd on
89 (same +62 goal difference), Liverpool 3rd on 82. If not, a relationship is wrong.

## Page 2 (bonus): season race

Line chart: X-axis `fact_team_match[game_number]`, Y-axis `Cumulative Points`,
Legend `dim_team[team_name]`, with the season slicer and a team slicer. Shows how a title race
developed match by match.

---

## Saving

Save as `dashboard\premier_league.pbix`, and export screenshots of each page as PNGs into
`dashboard\` for the README. Commit and push them from the VM, or copy them back to the Mac.
