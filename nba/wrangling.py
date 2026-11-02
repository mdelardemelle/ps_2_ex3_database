"""Read-only queries and preparation for the four NBA visualisations."""

import sqlite3
from pathlib import Path

import pandas as pd


def connect_database(path: str | Path) -> sqlite3.Connection:
    """Open an existing SQLite database without allowing changes."""
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)


def get_streaks(con: sqlite3.Connection) -> pd.DataFrame:
    """Return each franchise's signed regular-season streak after each game.

    Streaks reset at season boundaries; playoffs are excluded.
    An unknown outcome interrupts a run instead of joining across it.
    """
    query = """
        WITH team_games AS (
            SELECT team_id_home AS team_id, team_name_home AS team_name,
                   game_date, game_id, season_id, wl_home AS result
            FROM game WHERE season_type = 'Regular Season'
            UNION ALL
            SELECT team_id_away, team_name_away, game_date,
                   game_id, season_id, wl_away
            FROM game WHERE season_type = 'Regular Season'
        ), numbered AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY season_id, team_id ORDER BY game_date, game_id
            ) - ROW_NUMBER() OVER (
                PARTITION BY season_id, team_id, result
                ORDER BY game_date, game_id
            ) AS run_id
            FROM team_games
        )
        SELECT *, CAST(SUBSTR(season_id, 2) AS INTEGER) AS season_start,
               ROW_NUMBER() OVER (
                   PARTITION BY season_id, team_id
                   ORDER BY game_date, game_id
               ) AS game_number,
               CASE result WHEN 'W' THEN 1 WHEN 'L' THEN -1 END
               * ROW_NUMBER() OVER (
                   PARTITION BY season_id, team_id, result, run_id
                   ORDER BY game_date, game_id
               ) AS streak
        FROM numbered
        ORDER BY season_id, team_id, game_date, game_id
    """
    data = pd.read_sql_query(query, con, parse_dates=["game_date"])
    if data.duplicated(["team_id", "game_id"]).any():
        raise ValueError("Duplicate team/game records prevent valid streaks.")
    return data


def get_attendance(con: sqlite3.Connection) -> pd.DataFrame:
    """Annual regular-season extremes after reproducible attendance cleaning.

    Ignore missing/negative values and retain zeros. Remove only the two
    known erroneous game/value pairs documented in README. If Kaggle fixes
    either value, the corrected observation will be included automatically.
    The raw database and other statistics for these games remain intact.
    """
    return pd.read_sql_query(
        """
        SELECT CAST(STRFTIME('%Y', g.game_date) AS INTEGER) AS year,
               MIN(i.attendance) AS minimum,
               MAX(i.attendance) AS maximum, COUNT(*) AS games
        FROM game AS g
        JOIN (SELECT DISTINCT game_id, attendance FROM game_info) AS i
          ON g.game_id = i.game_id
        WHERE g.season_type = 'Regular Season'
          AND i.attendance IS NOT NULL AND i.attendance >= 0
          -- Known recording errors; exclude only these exact observations.
          AND NOT (g.game_id = '0029400853' AND i.attendance = 200049)
          AND NOT (g.game_id = '0029401063' AND i.attendance = 144442)
        GROUP BY year ORDER BY year
        """,
        con,
    )


def get_scoring(con: sqlite3.Connection) -> pd.DataFrame:
    """Annual combined points for both teams, per game and per quarter.

    Game totals include overtime. Quarter means use complete numeric
    quarter records; counts expose the different coverage of the series.
    """
    games = pd.read_sql_query(
        """
        SELECT game_id, game_date, pts_home, pts_away
        FROM game WHERE season_type = 'Regular Season'
        """,
        con,
        parse_dates=["game_date"],
    )
    quarters = pd.read_sql_query(
        "SELECT * FROM line_score", con
    ).drop_duplicates()
    data = games.merge(
        quarters,
        on="game_id",
        how="left",
        validate="1:1",
        suffixes=("", "_line"),
    )
    data["year"] = data["game_date"].dt.year
    for column in ["pts_home", "pts_away"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    valid = data[["pts_home", "pts_away"]].notna().all(axis=1)
    valid &= (data[["pts_home", "pts_away"]] >= 0).all(axis=1)
    data = data.loc[valid].copy()
    data["game_points"] = data["pts_home"] + data["pts_away"]
    columns = [
        f"pts_qtr{q}_{side}" for q in range(1, 5) for side in ("home", "away")
    ]
    for column in columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    complete = data[columns].notna().all(axis=1)
    complete &= (data[columns] >= 0).all(axis=1)
    for side in ("home", "away"):
        total = data[[f"pts_qtr{q}_{side}" for q in range(1, 5)]].sum(axis=1)
        complete &= (total > 0) & (total <= data[f"pts_{side}"])
    for q in range(1, 5):
        data[f"q{q}"] = (
            data[f"pts_qtr{q}_home"] + data[f"pts_qtr{q}_away"]
        ).where(complete)
    return data.groupby("year", as_index=False).agg(
        game_points=("game_points", "mean"),
        games=("game_points", "count"),
        q1=("q1", "mean"),
        q2=("q2", "mean"),
        q3=("q3", "mean"),
        q4=("q4", "mean"),
        quarter_games=("q1", "count"),
    )


def get_new_player_heights(con: sqlite3.Connection) -> pd.DataFrame:
    """Recorded heights grouped by first NBA year, not draft year.

    Each player appears once. Missing/malformed heights are omitted.
    This covers available player biographies, not complete annual rosters.
    """
    data = pd.read_sql_query(
        "SELECT person_id, height, from_year FROM common_player_info", con
    ).drop_duplicates("person_id")
    parts = data["height"].str.extract(r"^(\d+)-(\d{1,2})$")
    feet = pd.to_numeric(parts[0], errors="coerce")
    inches = pd.to_numeric(parts[1], errors="coerce")
    data["height_cm"] = (12 * feet + inches) * 2.54
    data["year"] = pd.to_numeric(data["from_year"], errors="coerce")
    valid = inches.between(0, 11) & data["height_cm"].between(120, 260)
    valid &= data["year"].notna() & (data["year"] % 1 == 0)
    data = data.loc[valid, ["person_id", "year", "height_cm"]].copy()
    data["year"] = data["year"].astype(int)
    return data.sort_values(["year", "person_id"]).reset_index(drop=True)
