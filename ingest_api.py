"""
ingest_csv.py — Historical World Cup data loader
=================================================
Loads WC 2018 and 2022 match results from Kaggle CSV files into the same
historical_results SQLite table that math_engine.py reads from.

Run this ONCE after downloading the CSVs:
    py ingest_csv.py

CSV sources (free Kaggle download):
  WC 1930-2018: https://www.kaggle.com/datasets/evangower/fifa-world-cup
  WC 2022:      https://www.kaggle.com/datasets/swaptr/fifa-world-cup-2022-match-data

Place downloaded files in a data/ subfolder:
    world-cup-predictor/
        data/
            WorldCupMatches.csv      ← evangower dataset (1930-2018)
            Matches.csv              ← swaptr dataset (2022)
        ingest_csv.py
        ingest_api.py
        predictor.db
"""

import sqlite3
import csv
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ingest_csv")

DB_PATH   = "predictor.db"
DATA_DIR  = Path("data")

# Only load these two seasons — enough signal for the Poisson model
TARGET_SEASONS = {2018, 2022}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table(conn):
    """Create historical_results if it doesn't already exist (idempotent)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historical_results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id        INTEGER NOT NULL UNIQUE,
            competition     TEXT    NOT NULL,
            season          INTEGER NOT NULL,
            stage           TEXT,
            matchday        INTEGER,
            utc_date        DATETIME NOT NULL,
            home_team_id    INTEGER NOT NULL,
            home_team_name  TEXT    NOT NULL,
            away_team_id    INTEGER NOT NULL,
            away_team_name  TEXT    NOT NULL,
            home_score      INTEGER NOT NULL,
            away_score      INTEGER NOT NULL,
            winner          TEXT,
            extra_time      INTEGER DEFAULT 0,
            penalties       INTEGER DEFAULT 0,
            venue           TEXT,
            neutral_venue   INTEGER DEFAULT 1,
            ingested_at     DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def insert_row(conn, row: dict) -> bool:
    """Insert one match. Returns True if inserted, False if duplicate."""
    try:
        conn.execute("""
            INSERT INTO historical_results
                (match_id, competition, season, stage, utc_date,
                 home_team_id, home_team_name, away_team_id, away_team_name,
                 home_score, away_score, winner,
                 extra_time, penalties, neutral_venue, venue)
            VALUES
                (:match_id, :competition, :season, :stage, :utc_date,
                 :home_team_id, :home_team_name, :away_team_id, :away_team_name,
                 :home_score, :away_score, :winner,
                 :extra_time, :penalties, :neutral_venue, :venue)
        """, row)
        return True
    except sqlite3.IntegrityError:
        return False   # duplicate match_id — already loaded


def _winner(home: int, away: int) -> str:
    if home > away:
        return "HOME_TEAM"
    if away > home:
        return "AWAY_TEAM"
    return "DRAW"


# ---------------------------------------------------------------------------
# Parser: evangower WorldCupMatches.csv  (covers 1930–2018)
# ---------------------------------------------------------------------------

def load_evangower(conn) -> tuple[int, int]:
    """
    Expected columns (evangower dataset):
        Year, Datetime, Stage, Stadium, City,
        Home Team Name, Home Team Goals,
        Away Team Goals, Away Team Name,
        Win conditions, Attendance, ...

    Returns (inserted, skipped).
    """
    path = DATA_DIR / "WorldCupMatches.csv"
    if not path.exists():
        log.warning(f"Not found: {path} — skipping evangower dataset")
        return 0, 0

    inserted = skipped = 0

    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            try:
                season = int(str(row.get("Year", "")).strip())
            except ValueError:
                continue

            if season not in TARGET_SEASONS:
                continue

            try:
                home_score = int(str(row.get("Home Team Goals", "")).strip())
                away_score = int(str(row.get("Away Team Goals", "")).strip())
            except ValueError:
                log.debug(f"Row {i}: bad score values — skipping")
                continue

            home_name = str(row.get("Home Team Name", "")).strip()
            away_name = str(row.get("Away Team Name", "")).strip()
            if not home_name or not away_name:
                continue

            # Parse date — format varies ("25 Jun 2018 - 15:00" or "25 Jun 2018")
            raw_date = str(row.get("Datetime", "")).strip()
            utc_date = _parse_evangower_date(raw_date) or datetime(season, 6, 1)

            # Derive a stable match_id from season + row index
            # (evangower has no native ID column)
            match_id = int(f"18{season % 100:02d}{i:04d}")

            win_cond = str(row.get("Win conditions", "")).strip().lower()
            extra_time = "extra" in win_cond or "aet" in win_cond
            penalties  = "pen" in win_cond or "pso" in win_cond

            db_row = dict(
                match_id       = match_id,
                competition    = "WC",
                season         = season,
                stage          = str(row.get("Stage", "")).strip() or None,
                utc_date       = utc_date.isoformat(),
                home_team_id   = _team_id(home_name),
                home_team_name = home_name,
                away_team_id   = _team_id(away_name),
                away_team_name = away_name,
                home_score     = home_score,
                away_score     = away_score,
                winner         = _winner(home_score, away_score),
                extra_time     = int(extra_time),
                penalties      = int(penalties),
                neutral_venue  = 1,
                venue          = str(row.get("Stadium", "")).strip() or None,
            )

            if insert_row(conn, db_row):
                inserted += 1
            else:
                skipped += 1

    conn.commit()
    return inserted, skipped


def _parse_evangower_date(raw: str) -> datetime | None:
    for fmt in ("%d %b %Y - %H:%M", "%d %b %Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Parser: swaptr Matches.csv  (covers WC 2022)
# ---------------------------------------------------------------------------

def load_swaptr(conn) -> tuple[int, int]:
    """
    Expected columns (swaptr dataset — FBref sourced):
        Wk, Day, Date, Time, Home, Score, Away, Attend, Venue,
        Referee, Match Report, Notes

    Score is formatted as "X–Y" or "X-Y" (full-time result).

    Returns (inserted, skipped).
    """
    path = DATA_DIR / "Matches.csv"
    if not path.exists():
        log.warning(f"Not found: {path} — skipping swaptr 2022 dataset")
        log.warning("  Download from: https://www.kaggle.com/datasets/swaptr/fifa-world-cup-2022-match-data")
        return 0, 0

    inserted = skipped = 0

    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            score_raw = str(row.get("Score", "")).strip()
            home_score, away_score = _parse_swaptr_score(score_raw)
            if home_score is None:
                log.debug(f"Row {i}: unparseable score '{score_raw}' — skipping")
                continue

            home_name = str(row.get("Home", "")).strip()
            away_name = str(row.get("Away", "")).strip()
            if not home_name or not away_name:
                continue

            raw_date = str(row.get("Date", "")).strip()
            raw_time = str(row.get("Time", "")).strip()
            utc_date = _parse_swaptr_date(raw_date, raw_time) or datetime(2022, 11, 20)

            notes    = str(row.get("Notes", "")).strip().lower()
            extra_time = "aet" in notes or "extra" in notes
            penalties  = "pen" in notes or "pso" in notes

            match_id = int(f"2022{i:04d}")

            db_row = dict(
                match_id       = match_id,
                competition    = "WC",
                season         = 2022,
                stage          = _infer_stage_2022(row),
                utc_date       = utc_date.isoformat(),
                home_team_id   = _team_id(home_name),
                home_team_name = home_name,
                away_team_id   = _team_id(away_name),
                away_team_name = away_name,
                home_score     = home_score,
                away_score     = away_score,
                winner         = _winner(home_score, away_score),
                extra_time     = int(extra_time),
                penalties      = int(penalties),
                neutral_venue  = 1,
                venue          = str(row.get("Venue", "")).strip() or None,
            )

            if insert_row(conn, db_row):
                inserted += 1
            else:
                skipped += 1

    conn.commit()
    return inserted, skipped


def _parse_swaptr_score(raw: str) -> tuple[int | None, int | None]:
    """Handles '2–1', '2-1', '0–0 (aet)' etc."""
    raw = raw.replace("\u2013", "-").replace("\u2014", "-")  # en/em dash → hyphen
    raw = raw.split("(")[0].strip()                          # strip "(aet)" suffixes
    parts = raw.split("-")
    if len(parts) != 2:
        return None, None
    try:
        return int(parts[0].strip()), int(parts[1].strip())
    except ValueError:
        return None, None


def _parse_swaptr_date(date_str: str, time_str: str) -> datetime | None:
    combined = f"{date_str} {time_str}".strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(combined, fmt)
        except ValueError:
            continue
    return None


def _infer_stage_2022(row: dict) -> str:
    """Best-effort stage label from Wk or Round column if present."""
    wk = str(row.get("Wk", row.get("Round", ""))).strip()
    if not wk:
        return "GROUP_STAGE"
    wk_lower = wk.lower()
    if "group" in wk_lower or wk.isdigit():
        return "GROUP_STAGE"
    if "round of 16" in wk_lower or "r16" in wk_lower:
        return "LAST_16"
    if "quarter" in wk_lower:
        return "QUARTER_FINALS"
    if "semi" in wk_lower:
        return "SEMI_FINALS"
    if "final" in wk_lower:
        return "FINAL"
    return wk.upper().replace(" ", "_")


# ---------------------------------------------------------------------------
# Utility: deterministic team_id from name
# (keeps foreign-key relationships consistent without hitting the API)
# ---------------------------------------------------------------------------

def _team_id(name: str) -> int:
    """
    Generates a stable integer ID from a team name using a simple hash.
    Consistent within a run — the math engine only needs the name anyway.
    """
    return abs(hash(name.lower().strip())) % 900_000 + 100_000


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(conn):
    print("\n" + "─" * 56)
    print(f"  {'Season':<10} {'Matches':>8}  {'Avg goals':>10}")
    print("─" * 56)
    rows = conn.execute("""
        SELECT season,
               COUNT(*)                            AS matches,
               ROUND(AVG(home_score + away_score), 2) AS avg_goals
        FROM   historical_results
        WHERE  competition = 'WC'
        GROUP  BY season
        ORDER  BY season
    """).fetchall()
    for r in rows:
        print(f"  WC {r['season']:<6}  {r['matches']:>8}  {r['avg_goals']:>10}")
    total = conn.execute("SELECT COUNT(*) FROM historical_results").fetchone()[0]
    print("─" * 56)
    print(f"  {'TOTAL':<10} {total:>8}")
    print()

    print("  Sample rows:")
    samples = conn.execute("""
        SELECT home_team_name, home_score, away_score, away_team_name, season
        FROM   historical_results
        ORDER  BY RANDOM()
        LIMIT  5
    """).fetchall()
    for r in samples:
        print(f"    {r['home_team_name']:<22} {r['home_score']}–{r['away_score']}  "
              f"{r['away_team_name']:<22}  (WC {r['season']})")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if not Path(DB_PATH).exists():
        log.error(
            f"Database '{DB_PATH}' not found.\n"
            "  Run 'py ingest_api.py --mode upcoming' first to create it,\n"
            "  or this script will create a fresh DB automatically."
        )

    conn = get_conn()
    ensure_table(conn)

    log.info("Loading WC 2018 data (evangower / WorldCupMatches.csv) …")
    ins18, skip18 = load_evangower(conn)
    log.info(f"  WC 2018: {ins18} inserted, {skip18} skipped")

    log.info("Loading WC 2022 data (swaptr / Matches.csv) …")
    ins22, skip22 = load_swaptr(conn)
    log.info(f"  WC 2022: {ins22} inserted, {skip22} skipped")

    total = ins18 + ins22
    if total == 0:
        log.warning(
            "\n  No rows inserted. Make sure your CSVs are in the data/ folder:\n"
            "    data/WorldCupMatches.csv  (evangower — 1930-2018 WC matches)\n"
            "    data/Matches.csv          (swaptr — 2022 WC matches)\n"
            "\n  Download links:\n"
            "    https://www.kaggle.com/datasets/evangower/fifa-world-cup\n"
            "    https://www.kaggle.com/datasets/swaptr/fifa-world-cup-2022-match-data"
        )
    else:
        log.info(f"Done — {total} total rows inserted into historical_results")
        print_summary(conn)

    conn.close()


if __name__ == "__main__":
    main()