"""
ingest_fixtures.py — WC 2026 fixture loader
========================================================================
Reads data/fixtures_2026.csv and completely replaces the contents of the
upcoming_fixtures table in predictor.db on every execution.

This script is the SINGLE SOURCE OF TRUTH for all upcoming fixtures
displayed by the Streamlit application.  When FIFA releases a new knockout
round, an operator updates fixtures_2026.csv and re-runs this script —
the app reflects the new fixtures automatically, with no code changes.

Pipeline
    fixtures_2026.csv
        → validate every row
        → DELETE FROM upcoming_fixtures
        → INSERT all valid rows
        → COMMIT
        → print summary

Run after any edit to fixtures_2026.csv:
    python ingest_fixtures.py

CSV source:
    data/fixtures_2026.csv  (hand-maintained or exported from the official
    FIFA / football-data.org schedule — see README for details)
"""

import csv
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ingest_fixtures")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

DB_PATH = PROJECT_ROOT / "predictor.db"
DATA_DIR = Path("data")
CSV_FILE = DATA_DIR / "fixtures_2026.csv"

REQUIRED_COLUMNS: set[str] = {
    "match_id",
    "competition",
    "season",
    "utc_date",
    "home_team_name",
    "away_team_name",
    "stage",
    "group",
    "status",
}

VALID_STAGES: set[str] = {
    "GROUP_STAGE",
    "ROUND_OF_32",
    "ROUND_OF_16",
    "QUARTERFINAL",
    "SEMIFINAL",
    "THIRD_PLACE",
    "FINAL",
}

EXPECTED_COMPETITION = "WC"
EXPECTED_SEASON      = 2026


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table(conn: sqlite3.Connection) -> None:
    """Create upcoming_fixtures if it doesn't already exist (idempotent)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS upcoming_fixtures (
            id             INTEGER  PRIMARY KEY AUTOINCREMENT,
            match_id       INTEGER  NOT NULL UNIQUE,
            competition    TEXT     NOT NULL,
            season         INTEGER  NOT NULL,
            utc_date       DATETIME NOT NULL,
            home_team_name TEXT     NOT NULL,
            away_team_name TEXT     NOT NULL,
            stage          TEXT     NOT NULL,
            "group" TEXT,
            status         TEXT     NOT NULL,
            ingested_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fixtures_stage "
        "ON upcoming_fixtures(stage)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fixtures_utc_date "
        "ON upcoming_fixtures(utc_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fixtures_home "
        "ON upcoming_fixtures(home_team_name)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fixtures_away "
        "ON upcoming_fixtures(away_team_name)"
    )
    conn.commit()


def clear_table(conn: sqlite3.Connection) -> int:
    """Delete all rows from upcoming_fixtures. Returns the row count removed."""
    cursor = conn.execute("DELETE FROM upcoming_fixtures")
    return cursor.rowcount


def insert_fixture(conn: sqlite3.Connection, row: dict) -> bool:
    """Insert one fixture. Returns True if inserted, False on integrity error."""
    try:
        conn.execute("""
            INSERT INTO upcoming_fixtures
                (match_id, competition, season, utc_date,
                 home_team_name, away_team_name, stage, "group", status)
            VALUES
                (:match_id,
    :competition,
    :season,
    :utc_date,
    :home_team_name,
    :away_team_name,
    :stage,
    :group,
    :status)
        """, row)
        return True
    except sqlite3.IntegrityError as exc:
        log.warning(f"  Integrity error on match_id={row.get('match_id')}: {exc}")
        return False


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _check_columns(fieldnames: list[str] | None) -> list[str]:
    """Return list of missing required column names."""
    present = set(fieldnames or [])
    return sorted(REQUIRED_COLUMNS - present)


def _parse_utc_date(raw: str) -> str | None:
    """
    Accept ISO-8601 datetime strings and return a normalised
    'YYYY-MM-DD HH:MM:SS' string, or None if unparseable.

    Accepted formats:
        2026-06-12 19:00:00
        2026-06-12T19:00:00
        2026-06-12T19:00:00Z
    """
    raw = raw.strip().replace("T", " ").rstrip("Z")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def _parse_match_id(raw: str) -> int | None:
    """Return integer match_id or None if not a positive integer."""
    try:
        val = int(str(raw).strip())
        return val if val > 0 else None
    except ValueError:
        return None


def _parse_season(raw: str) -> int | None:
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def validate_row(
    raw_row: dict,
    row_num: int,
) -> tuple[dict | None, list[str]]:
    """
    Validate one raw CSV row.

    Returns
    -------
    (db_row, [])          — row is valid; db_row is ready for INSERT
    (None,  [error, ...]) — row is invalid; list contains error messages
    """
    errors: list[str] = []

    # --- match_id ---
    match_id = _parse_match_id(raw_row.get("match_id", ""))
    if match_id is None:
        errors.append("match_id must be a positive integer")

    # --- competition ---
    competition = str(raw_row.get("competition", "")).strip().upper()
    if competition != EXPECTED_COMPETITION:
        errors.append(
            f"competition must be '{EXPECTED_COMPETITION}', got '{competition}'"
        )

    # --- season ---
    season = _parse_season(raw_row.get("season", ""))
    if season != EXPECTED_SEASON:
        errors.append(
            f"season must be {EXPECTED_SEASON}, got '{raw_row.get('season')}'"
        )

    # --- utc_date ---
    utc_date = _parse_utc_date(str(raw_row.get("utc_date", "")))
    if utc_date is None:
        errors.append(
            f"utc_date '{raw_row.get('utc_date')}' is not a valid datetime"
        )

    # --- teams ---
    home = str(raw_row.get("home_team_name", "")).strip()
    away = str(raw_row.get("away_team_name", "")).strip()

    if not home:
        errors.append("home_team_name is empty")
    if not away:
        errors.append("away_team_name is empty")
    if home and away and home.upper() not in ("TBD",) and home == away:
        errors.append(
            f"home_team_name and away_team_name are identical ('{home}')"
        )

    # --- stage ---
    stage = str(raw_row.get("stage", "")).strip().upper()
    if stage not in VALID_STAGES:
        errors.append(
            f"stage '{stage}' is not valid. "
            f"Allowed: {', '.join(sorted(VALID_STAGES))}"
        )

    # --- status ---
    status = str(raw_row.get("status", "")).strip()
    if not status:
        errors.append("status is empty")

    if errors:
        return None, errors

    db_row = {
    "match_id": match_id,
    "competition": competition,
    "season": season,
    "utc_date": utc_date,
    "home_team_name": home,
    "away_team_name": away,
    "stage": stage,
    "group": str(raw_row.get("group", "")).strip() or None,
    "status": status,
}
    return db_row, []


# ---------------------------------------------------------------------------
# Load pipeline
# ---------------------------------------------------------------------------

def load_fixtures(conn: sqlite3.Connection) -> dict:
    """
    Read fixtures_2026.csv, validate every row, then atomically replace
    the contents of upcoming_fixtures with the valid rows.

    Returns a stats dict consumed by print_summary().
    """
    if not CSV_FILE.exists():
        log.error(f"Not found: {CSV_FILE}")
        log.error(
            "  Create data/fixtures_2026.csv with the WC 2026 schedule, "
            "then re-run this script."
        )
        return {
            "read": 0, "inserted": 0, "skipped": 0,
            "cleared": 0, "by_stage": {},
        }

    rows_read     = 0
    rows_skipped  = 0
    valid_rows: list[dict] = []

    # ------------------------------------------------------------------ #
    #  Pass 1 — read and validate every row BEFORE touching the database  #
    # ------------------------------------------------------------------ #
    with open(CSV_FILE, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        missing_cols = _check_columns(reader.fieldnames)
        if missing_cols:
            log.error(
                f"CSV is missing required columns: {', '.join(missing_cols)}"
            )
            return {
                "read": 0, "inserted": 0, "skipped": 0,
                "cleared": 0, "by_stage": {},
            }

        for raw_row in reader:
            rows_read += 1
            db_row, errors = validate_row(raw_row, rows_read)

            if errors:
                for msg in errors:
                    log.warning(f"  Row {rows_read}: {msg} — skipping")
                rows_skipped += 1
            else:
                valid_rows.append(db_row)

    # ------------------------------------------------------------------ #
    #  Pass 2 — atomic replace inside a single transaction                #
    # ------------------------------------------------------------------ #
    rows_inserted = 0
    rows_cleared  = 0
    by_stage: dict[str, int] = {}

    try:
        with conn:                          # BEGIN / COMMIT or ROLLBACK
            rows_cleared = clear_table(conn)
            log.info(f"Cleared {rows_cleared:,} existing fixture(s).")

            for db_row in valid_rows:
                if insert_fixture(conn, db_row):
                    rows_inserted += 1
                    stage = db_row["stage"]
                    by_stage[stage] = by_stage.get(stage, 0) + 1
                else:
                    rows_skipped += 1

    except Exception as exc:
        log.error(f"Transaction failed — database rolled back. Reason: {exc}")
        raise

    return {
        "read":     rows_read,
        "inserted": rows_inserted,
        "skipped":  rows_skipped,
        "cleared":  rows_cleared,
        "by_stage": by_stage,
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(stats: dict) -> None:
    print("\n" + "─" * 56)
    print("  INGEST FIXTURES — SUMMARY")
    print("─" * 56)
    print(f"  {'Rows read:':<24} {stats['read']:>8,}")
    print(f"  {'Rows inserted:':<24} {stats['inserted']:>8,}")
    print(f"  {'Rows skipped:':<24} {stats['skipped']:>8,}")
    print(f"  {'Previous rows cleared:':<24} {stats['cleared']:>8,}")
    print("─" * 56)

    if stats["by_stage"]:
        print("\n  Stage breakdown:")
        print("─" * 56)

        stage_order = [
            "GROUP_STAGE",
            "ROUND_OF_32",
            "ROUND_OF_16",
            "QUARTERFINAL",
            "SEMIFINAL",
            "THIRD_PLACE",
            "FINAL",
        ]
        for stage in stage_order:
            count = stats["by_stage"].get(stage)
            if count is not None:
                print(f"    {stage:<28} {count:>8,}")

        # Print any unexpected stages that aren't in stage_order
        for stage, count in stats["by_stage"].items():
            if stage not in stage_order:
                print(f"    {stage:<28} {count:>8,}")

        print("─" * 56)

    if stats["inserted"] > 0:
        print("\n  Database updated successfully.")
    else:
        print("\n  WARNING: No fixtures were inserted.")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if not Path(DB_PATH).exists():
        log.warning(
            f"'{DB_PATH}' not found — it will be created automatically. "
            "Run ingest_csv.py and ingest_form.py first if you expect "
            "historical data to already be present."
        )

    conn = get_conn()
    ensure_table(conn)

    log.info(f"Loading WC 2026 fixtures from {CSV_FILE} …")
    stats = load_fixtures(conn)

    if stats["read"] == 0:
        log.warning(f"No rows read — check that {CSV_FILE} exists and is not empty.")
    else:
        log.info(
            f"Done — read {stats['read']:,}, "
            f"inserted {stats['inserted']:,}, "
            f"skipped {stats['skipped']:,}"
        )
        print_summary(stats)

    conn.close()


if __name__ == "__main__":
    main()