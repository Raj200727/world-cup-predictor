"""
ingest_form.py — Recent international match data loader (Milestone 1)
========================================================================
Loads international football results (all competitions — qualifiers,
continental championships, Nations League, friendlies, etc.) from
results.csv into a new international_results SQLite table.

This is a PURE ETL script. It does not compute attack/defense ratings,
expected goals, Poisson probabilities, or any hybrid model logic.
That work belongs to Milestone 2 (math_engine.py changes).

The historical_results table (WC 1930-2022) is untouched. This script
only ever writes to international_results — V1 remains fully functional
and unmodified.

Run this ONCE after downloading the CSV:
    py ingest_form.py

CSV source (free Kaggle download):
  https://www.kaggle.com/datasets/martj42/international-football-results-from-1872-to-2017

Place the downloaded file in a data/ subfolder:
    world-cup-predictor/
        data/
            results.csv          ← martj42 dataset
        ingest_form.py
        ingest_csv.py
        ingest_api.py
        predictor.db
"""

import sqlite3
import csv
import hashlib
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ingest_form")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH   = "predictor.db"
DATA_DIR  = Path("data")
CSV_FILE  = DATA_DIR / "results.csv"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table(conn):
    """Create international_results if it doesn't already exist (idempotent)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS international_results (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id             INTEGER NOT NULL UNIQUE,
            match_date           DATE    NOT NULL,
            tournament           TEXT    NOT NULL,
            competition_category TEXT    NOT NULL,
            tournament_tier      TEXT    NOT NULL,
            home_team            TEXT    NOT NULL,
            away_team            TEXT    NOT NULL,
            home_score           INTEGER NOT NULL,
            away_score           INTEGER NOT NULL,
            neutral_venue        INTEGER DEFAULT 0,
            competition_weight   REAL    NOT NULL,
            ingested_at          DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Indexes — match_date and tournament_tier are filtered on every query
    # the future math_engine.py form-loader will run; home/away support
    # per-team lookups the same way historical_results is queried today.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_intl_date "
        "ON international_results(match_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_intl_tier "
        "ON international_results(tournament_tier)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_intl_home "
        "ON international_results(home_team)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_intl_away "
        "ON international_results(away_team)"
    )
    conn.commit()


def insert_row(conn, row: dict) -> bool:
    """Insert one match. Returns True if inserted, False if duplicate."""
    try:
        conn.execute("""
            INSERT OR IGNORE INTO international_results
                (match_id, match_date, tournament, competition_category,
                 tournament_tier, home_team, away_team,
                 home_score, away_score, neutral_venue, competition_weight)
            VALUES
                (:match_id, :match_date, :tournament, :competition_category,
                 :tournament_tier, :home_team, :away_team,
                 :home_score, :away_score, :neutral_venue, :competition_weight)
        """, row)
        return conn.execute("SELECT changes()").fetchone()[0] > 0
    except sqlite3.IntegrityError:
        return False   # duplicate match_id — already loaded


# ---------------------------------------------------------------------------
# Tournament classification
# ---------------------------------------------------------------------------
# ONE centralized mapping. Every tournament name from results.csv is looked
# up here. competition_category groups related tournaments for reporting;
# tournament_tier drives how math_engine.py will weight the data in
# Milestone 2; competition_weight is the pre-computed numeric weight.
#
# Unknown tournaments (anything not listed below) automatically default to
# EXCLUDED / 0.00 via TOURNAMENT_MAP.get() with a fallback tuple — see
# _classify_tournament().
# ---------------------------------------------------------------------------

TOURNAMENT_MAP: dict[str, tuple[str, str, float]] = {
    # name → (competition_category, tournament_tier, competition_weight)

    # ---- FIFA World Cup family --------------------------------------------
    "FIFA World Cup":                      ("WORLD_CUP",        "CORE",     1.00),
    "FIFA World Cup qualification":        ("QUALIFIER",        "CORE",     0.75),

    # ---- Continental championships (main tournaments) ---------------------
    "UEFA Euro":                           ("CONTINENTAL",      "CORE",     0.90),
    "Copa América":                        ("CONTINENTAL",      "CORE",     0.90),
    "African Cup of Nations":              ("CONTINENTAL",      "CORE",     0.90),
    "AFC Asian Cup":                       ("CONTINENTAL",      "CORE",     0.90),
    "Gold Cup":                            ("CONTINENTAL",      "CORE",     0.85),
    "CONCACAF Championship":               ("CONTINENTAL",      "CORE",     0.85),
    "Oceania Nations Cup":                 ("CONTINENTAL",      "CORE",     0.80),

    # ---- Continental championship qualifiers -------------------------------
    "UEFA Euro qualification":             ("CONTINENTAL_QUAL", "CORE",     0.55),
    "Copa América qualification":          ("CONTINENTAL_QUAL", "CORE",     0.55),
    "African Cup of Nations qualification":("CONTINENTAL_QUAL", "CORE",     0.55),
    "AFC Asian Cup qualification":         ("CONTINENTAL_QUAL", "CORE",     0.55),
    "Gold Cup qualification":              ("CONTINENTAL_QUAL", "CORE",     0.50),
    "CONCACAF Championship qualification": ("CONTINENTAL_QUAL", "CORE",     0.50),
    "Oceania Nations Cup qualification":   ("CONTINENTAL_QUAL", "CORE",     0.45),

    # ---- Nations League family ---------------------------------------------
    "UEFA Nations League":                 ("NATIONS_LEAGUE",   "CORE",     0.60),
    "CONCACAF Nations League":             ("NATIONS_LEAGUE",   "CORE",     0.60),
    "CONCACAF Nations League qualification":("NATIONS_LEAGUE",  "CORE",     0.50),

    # ---- Friendlies — included, low weight, recency-restricted in M2 -------
    "Friendly":                            ("FRIENDLY",         "SECONDARY", 0.25),

    # ---- Excluded entirely ---------------------------------------------------
    "Olympic Games":                       ("EXCLUDED",         "EXCLUDED", 0.00),
    "Confederations Cup":                  ("EXCLUDED",         "EXCLUDED", 0.00),
}

# Fallback for any tournament name NOT in TOURNAMENT_MAP above.
# Per spec: unknown tournaments default to EXCLUDED.
_UNKNOWN_TOURNAMENT_DEFAULT: tuple[str, str, float] = ("EXCLUDED", "EXCLUDED", 0.00)


def _classify_tournament(tournament: str) -> tuple[str, str, float]:
    """
    Look up (competition_category, tournament_tier, competition_weight)
    for a raw tournament name from results.csv.

    Returns the EXCLUDED default for any tournament not explicitly mapped.
    """
    return TOURNAMENT_MAP.get(tournament.strip(), _UNKNOWN_TOURNAMENT_DEFAULT)


# ---------------------------------------------------------------------------
# Team normalization
# ---------------------------------------------------------------------------
# Identical alias table to the one in math_engine.py — copied verbatim,
# NOT reinvented. If math_engine.py's _ALIASES table is ever extended,
# this dict must be updated to match.
# ---------------------------------------------------------------------------

_ALIASES: dict[str, str] = {
    # Korean peninsula
    "korea republic":         "South Korea",
    "korea dpr":              "North Korea",
    "north korea":            "North Korea",
    # German reunification
    "west germany":           "Germany",
    "east germany":           "Germany",
    # Soviet successor states
    "ussr":                   "Russia",
    "soviet union":           "Russia",
    "yugoslavia":             "Serbia",
    "czechoslovakia":         "Czechia",
    # African / Asian variants
    "ivory coast":            "Côte d'Ivoire",
    "cote d'ivoire":          "Côte d'Ivoire",
    "iran":                   "IR Iran",
    # Other common variants
    "united states":          "USA",
    "trinidad and tobago":    "Trinidad & Tobago",
    "cape verde":             "Cabo Verde",
    "republic of ireland":    "Ireland",
    "northern ireland":       "Northern Ireland",
}


def _normalise(name: str) -> str:
    """
    Return canonical team name, collapsing historical aliases.
    Identical logic to math_engine.py's _normalise() — kept isolated
    in this single helper so it's easy to verify against the source
    of truth in math_engine.py.
    """
    if not name:
        return name
    key = name.strip().lower()
    return _ALIASES.get(key, name.strip())


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def _parse_date(raw: str) -> str | None:
    """Parse results.csv date column ('YYYY-MM-DD') to ISO date string."""
    raw = raw.strip()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _parse_neutral(raw: str) -> int:
    """Convert results.csv 'TRUE'/'FALSE' string to 0/1 int."""
    return 1 if raw.strip().upper() == "TRUE" else 0


def _make_match_id(match_date: str, home: str, away: str) -> int:
    """
    Deterministic integer match_id derived from date + teams.
    Same inputs ALWAYS produce the same ID — no randomness, no
    autoincrement-on-source dependency. This is what makes repeated
    runs of this script idempotent via INSERT OR IGNORE.

    IMPORTANT: Python's built-in hash() for strings is randomized per
    process (PYTHONHASHSEED), so it would produce a DIFFERENT id on
    every run — silently breaking idempotency and duplicating every
    row. hashlib.sha256 is used instead because it is guaranteed to
    return the same digest for the same input on every run, on every
    machine, regardless of process or interpreter.
    """
    key = f"{match_date}|{home.lower()}|{away.lower()}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:15], 16)   # 15 hex chars fits safely under SQLite's INTEGER range


# ---------------------------------------------------------------------------
# Insert pipeline
# ---------------------------------------------------------------------------

def load_results(conn) -> dict:
    """
    Read results.csv, classify + normalise every row, and insert into
    international_results.

    Pipeline per row:
        read row → normalise team names → classify tournament →
        skip if EXCLUDED → generate deterministic match_id → insert

    Returns a stats dict used by print_summary().
    """
    if not CSV_FILE.exists():
        log.error(f"Not found: {CSV_FILE}")
        log.error(
            "  Download from: https://www.kaggle.com/datasets/"
            "martj42/international-football-results-from-1872-to-2017"
        )
        return {
            "read": 0, "inserted": 0, "skipped": 0, "excluded": 0,
            "by_category": {}, "by_tier": {},
        }

    rows_read     = 0
    rows_inserted = 0
    rows_skipped  = 0   # bad rows (unparseable date/score) or duplicates
    rows_excluded = 0   # tournament classified as EXCLUDED

    by_category: dict[str, int] = {}
    by_tier:     dict[str, int] = {}

    with open(CSV_FILE, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for raw_row in reader:
            rows_read += 1

            match_date = _parse_date(raw_row.get("date", ""))
            if match_date is None:
                log.debug(f"Row {rows_read}: unparseable date — skipping")
                rows_skipped += 1
                continue

            try:
                home_score = int(str(raw_row.get("home_score", "")).strip())
                away_score = int(str(raw_row.get("away_score", "")).strip())
            except ValueError:
                log.debug(f"Row {rows_read}: bad score values — skipping")
                rows_skipped += 1
                continue

            home_raw = str(raw_row.get("home_team", "")).strip()
            away_raw = str(raw_row.get("away_team", "")).strip()
            if not home_raw or not away_raw:
                rows_skipped += 1
                continue

            home_team = _normalise(home_raw)
            away_team = _normalise(away_raw)

            tournament = str(raw_row.get("tournament", "")).strip()
            category, tier, weight = _classify_tournament(tournament)

            if tier == "EXCLUDED":
                rows_excluded += 1
                continue

            neutral_venue = _parse_neutral(str(raw_row.get("neutral", "FALSE")))
            match_id = _make_match_id(match_date, home_team, away_team)

            db_row = dict(
                match_id             = match_id,
                match_date           = match_date,
                tournament           = tournament,
                competition_category = category,
                tournament_tier      = tier,
                home_team            = home_team,
                away_team            = away_team,
                home_score           = home_score,
                away_score           = away_score,
                neutral_venue        = neutral_venue,
                competition_weight   = weight,
            )

            if insert_row(conn, db_row):
                rows_inserted += 1
                by_category[category] = by_category.get(category, 0) + 1
                by_tier[tier]         = by_tier.get(tier, 0) + 1
            else:
                rows_skipped += 1   # duplicate match_id, already loaded

    conn.commit()

    return {
        "read":        rows_read,
        "inserted":    rows_inserted,
        "skipped":     rows_skipped,
        "excluded":    rows_excluded,
        "by_category": by_category,
        "by_tier":     by_tier,
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(stats: dict) -> None:
    print("\n" + "─" * 56)
    print("  INGEST FORM — SUMMARY")
    print("─" * 56)
    print(f"  {'Rows read:':<24} {stats['read']:>8,}")
    print(f"  {'Rows inserted:':<24} {stats['inserted']:>8,}")
    print(f"  {'Rows skipped:':<24} {stats['skipped']:>8,}")
    print(f"  {'Rows excluded:':<24} {stats['excluded']:>8,}")
    print("─" * 56)

    if stats["by_category"]:
        print("\n  Breakdown by competition category:")
        print("─" * 56)
        for cat, count in sorted(stats["by_category"].items(),
                                 key=lambda x: -x[1]):
            print(f"    {cat:<30} {count:>8,}")
        print("─" * 56)

    if stats["by_tier"]:
        print("\n  Breakdown by tournament tier:")
        print("─" * 56)
        for tier, count in sorted(stats["by_tier"].items(),
                                  key=lambda x: -x[1]):
            print(f"    {tier:<30} {count:>8,}")
        print("─" * 56)

    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if not Path(DB_PATH).exists():
        log.warning(
            f"'{DB_PATH}' not found — it will be created automatically. "
            "Run ingest_api.py / ingest_csv.py first if you expect "
            "historical_results to already exist."
        )

    conn = get_conn()
    ensure_table(conn)

    log.info(f"Loading international match data from {CSV_FILE} …")
    stats = load_results(conn)

    if stats["read"] == 0:
        log.warning("No rows read — check that data/results.csv exists.")
    else:
        log.info(
            f"Done — read {stats['read']:,}, inserted {stats['inserted']:,}, "
            f"skipped {stats['skipped']:,}, excluded {stats['excluded']:,}"
        )
        print_summary(stats)

    conn.close()


if __name__ == "__main__":
    main()