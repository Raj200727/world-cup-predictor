"""
ingest_api.py — World Cup Predictor
====================================
Fetches historical international match data and upcoming World Cup fixtures
from Football-Data.org and persists them to a local SQLite database.

Usage
-----
    # First time setup — pulls everything:
    python ingest_api.py --mode full

    # Subsequent runs — only new fixtures:
    python ingest_api.py --mode fixtures

    # Refresh upcoming fixtures only:
    python ingest_api.py --mode upcoming

Setup
-----
1. Sign up free at https://www.football-data.org/
2. Copy your API key from your account dashboard
3. Set it as an environment variable:
       export FOOTBALL_DATA_API_KEY="your_key_here"
   Or pass it directly:
       python ingest_api.py --api-key YOUR_KEY --mode full

Free tier covers: World Cup (WC), European Championship (EC), and more.
Rate limit: 10 requests/minute — this script respects that automatically.
"""

import os
import sys
import time
import logging
import sqlite3
import argparse
from datetime import datetime, timezone
from typing import Optional

import requests
from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    DateTime, Boolean, UniqueConstraint, text
)
from sqlalchemy.orm import DeclarativeBase, Session

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://api.football-data.org/v4"

# Football-Data.org competition codes (free tier)
COMPETITIONS = {
    "WC":  "FIFA World Cup",
    "EC":  "UEFA European Championship",
    "CL":  "UEFA Champions League",       # bonus: useful for club form
}

# World Cup competition ID on football-data.org
WORLD_CUP_ID = "WC"

# Seasons to pull for historical model training (adjust as needed)
HISTORICAL_SEASONS = [2018, 2022]

# Upcoming competition season (current World Cup)
UPCOMING_SEASON = 2026

# Seconds to wait between API calls (free tier = 10 req/min → 6s safe interval)
REQUEST_INTERVAL = 6.5

DB_PATH = "predictor.db"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ingest")

# ---------------------------------------------------------------------------
# Database schema
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class Team(Base):
    """Lookup table for teams — populated automatically during ingestion."""
    __tablename__ = "teams"

    id          = Column(Integer, primary_key=True)   # football-data team id
    name        = Column(String, nullable=False)
    short_name  = Column(String)
    tla         = Column(String)                       # 3-letter abbreviation
    crest_url   = Column(String)
    area        = Column(String)                       # country / continent
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HistoricalResult(Base):
    """
    One row per completed match used to calculate team attack/defense strength.
    Only STATUS='FINISHED' matches are stored here.
    """
    __tablename__ = "historical_results"
    __table_args__ = (
        UniqueConstraint("match_id", name="uq_historical_match"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    match_id        = Column(Integer, nullable=False)          # football-data match id
    competition     = Column(String, nullable=False)           # e.g. "WC"
    season          = Column(Integer, nullable=False)          # e.g. 2022
    stage           = Column(String)                           # e.g. "GROUP_STAGE"
    matchday        = Column(Integer)
    utc_date        = Column(DateTime, nullable=False)

    home_team_id    = Column(Integer, nullable=False)
    home_team_name  = Column(String, nullable=False)
    away_team_id    = Column(Integer, nullable=False)
    away_team_name  = Column(String, nullable=False)

    home_score      = Column(Integer, nullable=False)
    away_score      = Column(Integer, nullable=False)
    winner          = Column(String)                           # "HOME_TEAM" | "AWAY_TEAM" | "DRAW"

    # Extra context useful for weighting/filtering
    extra_time      = Column(Boolean, default=False)
    penalties       = Column(Boolean, default=False)
    venue           = Column(String)
    neutral_venue   = Column(Boolean, default=True)            # World Cup = always neutral

    ingested_at     = Column(DateTime, default=datetime.utcnow)


class UpcomingFixture(Base):
    """
    Future / scheduled matches for the current World Cup.
    Re-fetched regularly so kickoff times and group assignments stay current.
    """
    __tablename__ = "upcoming_fixtures"
    __table_args__ = (
        UniqueConstraint("match_id", name="uq_upcoming_match"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    match_id        = Column(Integer, nullable=False)
    competition     = Column(String, nullable=False)
    season          = Column(Integer, nullable=False)
    stage           = Column(String)
    matchday        = Column(Integer)
    utc_date        = Column(DateTime, nullable=False)

    home_team_id    = Column(Integer)
    home_team_name  = Column(String)
    away_team_id    = Column(Integer)
    away_team_name  = Column(String)

    status          = Column(String)                           # "SCHEDULED" | "TIMED" | "POSTPONED"
    group           = Column(String)                           # "Group A" etc.

    ingested_at     = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IngestLog(Base):
    """Simple audit trail — one row per ingest run."""
    __tablename__ = "ingest_log"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    run_at          = Column(DateTime, default=datetime.utcnow)
    mode            = Column(String)
    competition     = Column(String)
    season          = Column(Integer)
    rows_inserted   = Column(Integer, default=0)
    rows_skipped    = Column(Integer, default=0)
    status          = Column(String)                           # "OK" | "ERROR"
    error_msg       = Column(String)


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class FootballDataClient:
    """Thin wrapper around football-data.org v4 REST API."""

    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update({
            "X-Auth-Token": api_key,
            "Accept": "application/json",
        })
        self._last_call: float = 0.0

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """
        GET with automatic rate-limit throttling.
        Raises on HTTP errors — caller decides how to handle them.
        """
        elapsed = time.monotonic() - self._last_call
        if elapsed < REQUEST_INTERVAL:
            wait = REQUEST_INTERVAL - elapsed
            log.debug(f"Rate-limit pause: {wait:.1f}s")
            time.sleep(wait)

        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        log.debug(f"GET {url}  params={params}")

        resp = self.session.get(url, params=params, timeout=30)
        self._last_call = time.monotonic()

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("X-RequestCounter-Reset", 60))
            log.warning(f"Rate limited — waiting {retry_after}s before retry")
            time.sleep(retry_after)
            return self._get(endpoint, params)

        resp.raise_for_status()
        return resp.json()

    def get_competition_matches(
        self,
        competition: str,
        season: int,
        status: Optional[str] = None,
    ) -> list[dict]:
        """
        Returns all matches for a competition/season.
        status: "FINISHED" | "SCHEDULED" | "TIMED" | None (all)
        """
        params: dict = {"season": season}
        if status:
            params["status"] = status

        data = self._get(f"competitions/{competition}/matches", params=params)
        matches = data.get("matches", [])
        log.info(
            f"  → {competition} {season} [{status or 'ALL'}]: {len(matches)} matches returned"
        )
        return matches

    def get_competition_teams(self, competition: str, season: int) -> list[dict]:
        """Returns team list for a competition/season."""
        data = self._get(
            f"competitions/{competition}/teams",
            params={"season": season},
        )
        teams = data.get("teams", [])
        log.info(f"  → {competition} {season}: {len(teams)} teams returned")
        return teams


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_datetime(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    # API returns ISO-8601 with Z suffix
    raw = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw).replace(tzinfo=None)  # store as naive UTC
    except ValueError:
        return None


def _parse_team(raw: Optional[dict]) -> tuple[Optional[int], Optional[str]]:
    if not raw:
        return None, None
    return raw.get("id"), raw.get("name") or raw.get("shortName")


def _parse_score(raw: Optional[dict]) -> tuple[Optional[int], Optional[int]]:
    """Extract fulltime score. Returns (None, None) if match not finished."""
    if not raw:
        return None, None
    ft = raw.get("fullTime") or {}
    return ft.get("home"), ft.get("away")


def _went_to_extra(raw: Optional[dict]) -> bool:
    if not raw:
        return False
    et = raw.get("extraTime") or {}
    return et.get("home") is not None


def _went_to_pens(raw: Optional[dict]) -> bool:
    if not raw:
        return False
    pen = raw.get("penalties") or {}
    return pen.get("home") is not None


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

def upsert_team(session: Session, raw: dict) -> None:
    team_id = raw.get("id")
    if not team_id:
        return
    existing = session.get(Team, team_id)
    if existing:
        existing.name       = raw.get("name", existing.name)
        existing.short_name = raw.get("shortName", existing.short_name)
        existing.tla        = raw.get("tla", existing.tla)
        existing.crest_url  = raw.get("crest", existing.crest_url)
        existing.area       = (raw.get("area") or {}).get("name", existing.area)
    else:
        session.add(Team(
            id          = team_id,
            name        = raw.get("name"),
            short_name  = raw.get("shortName"),
            tla         = raw.get("tla"),
            crest_url   = raw.get("crest"),
            area        = (raw.get("area") or {}).get("name"),
        ))


def insert_historical(
    session: Session,
    match: dict,
    competition: str,
    season: int,
) -> tuple[bool, bool]:
    """
    Returns (inserted: bool, skipped: bool).
    Skips non-FINISHED matches and duplicates.
    """
    if match.get("status") != "FINISHED":
        return False, True

    match_id = match["id"]
    if session.execute(
        text("SELECT 1 FROM historical_results WHERE match_id = :mid"),
        {"mid": match_id},
    ).fetchone():
        return False, True   # already exists

    home_id, home_name = _parse_team(match.get("homeTeam"))
    away_id, away_name = _parse_team(match.get("awayTeam"))
    home_score, away_score = _parse_score(match.get("score"))

    if home_score is None or away_score is None:
        log.warning(f"  ⚠ Match {match_id} has FINISHED status but no score — skipping")
        return False, True

    score_raw = match.get("score") or {}
    winner_raw = score_raw.get("winner")

    session.add(HistoricalResult(
        match_id        = match_id,
        competition     = competition,
        season          = season,
        stage           = match.get("stage"),
        matchday        = match.get("matchday"),
        utc_date        = _parse_datetime(match.get("utcDate")),
        home_team_id    = home_id,
        home_team_name  = home_name,
        away_team_id    = away_id,
        away_team_name  = away_name,
        home_score      = home_score,
        away_score      = away_score,
        winner          = winner_raw,
        extra_time      = _went_to_extra(score_raw),
        penalties       = _went_to_pens(score_raw),
        venue           = (match.get("venue") or "").strip() or None,
        neutral_venue   = True,
    ))
    return True, False


def upsert_upcoming(
    session: Session,
    match: dict,
    competition: str,
    season: int,
) -> tuple[bool, bool]:
    """
    Upserts a scheduled/timed match into upcoming_fixtures.
    Returns (upserted: bool, skipped: bool).
    """
    status = match.get("status", "")
    if status == "FINISHED":
        # Finished matches belong in historical_results, not upcoming
        return False, True

    match_id = match["id"]
    home_id, home_name = _parse_team(match.get("homeTeam"))
    away_id, away_name = _parse_team(match.get("awayTeam"))

    existing = session.execute(
        text("SELECT id FROM upcoming_fixtures WHERE match_id = :mid"),
        {"mid": match_id},
    ).fetchone()

    if existing:
        session.execute(
            text("""
                UPDATE upcoming_fixtures
                SET home_team_id   = :htid,
                    home_team_name = :htn,
                    away_team_id   = :atid,
                    away_team_name = :atn,
                    status         = :status,
                    utc_date       = :utc_date,
                    stage          = :stage,
                    matchday       = :matchday,
                    "group"        = :grp,
                    updated_at     = :now
                WHERE match_id = :mid
            """),
            {
                "htid":     home_id,
                "htn":      home_name,
                "atid":     away_id,
                "atn":      away_name,
                "status":   status,
                "utc_date": _parse_datetime(match.get("utcDate")),
                "stage":    match.get("stage"),
                "matchday": match.get("matchday"),
                "grp":      match.get("group"),
                "now":      datetime.utcnow(),
                "mid":      match_id,
            },
        )
        return True, False

    session.add(UpcomingFixture(
        match_id        = match_id,
        competition     = competition,
        season          = season,
        stage           = match.get("stage"),
        matchday        = match.get("matchday"),
        utc_date        = _parse_datetime(match.get("utcDate")),
        home_team_id    = home_id,
        home_team_name  = home_name,
        away_team_id    = away_id,
        away_team_name  = away_name,
        status          = status,
        group           = match.get("group"),
    ))
    return True, False


# ---------------------------------------------------------------------------
# Ingest modes
# ---------------------------------------------------------------------------

def ingest_historical(client: FootballDataClient, session: Session) -> None:
    """Pull FINISHED World Cup matches for all HISTORICAL_SEASONS."""
    log.info("=== Historical ingestion ===")
    for season in HISTORICAL_SEASONS:
        log.info(f"Fetching WC {season} finished matches …")
        inserted = skipped = 0
        try:
            matches = client.get_competition_matches(WORLD_CUP_ID, season, status="FINISHED")
            for m in matches:
                ins, skip = insert_historical(session, m, WORLD_CUP_ID, season)
                inserted += ins
                skipped  += skip
            session.commit()
            log.info(f"  WC {season}: {inserted} inserted, {skipped} skipped")
            _log_run(session, "historical", WORLD_CUP_ID, season, inserted, skipped, "OK")
        except requests.HTTPError as e:
            session.rollback()
            msg = str(e)
            log.error(f"  HTTP error for WC {season}: {msg}")
            _log_run(session, "historical", WORLD_CUP_ID, season, 0, 0, "ERROR", msg)


def ingest_upcoming(client: FootballDataClient, session: Session) -> None:
    """Pull SCHEDULED / TIMED fixtures for the current World Cup season."""
    log.info("=== Upcoming fixtures ingestion ===")
    log.info(f"Fetching WC {UPCOMING_SEASON} scheduled fixtures …")
    inserted = skipped = 0
    try:
        matches = client.get_competition_matches(WORLD_CUP_ID, UPCOMING_SEASON)
        for m in matches:
            ins, skip = upsert_upcoming(session, m, WORLD_CUP_ID, UPCOMING_SEASON)
            inserted += ins
            skipped  += skip
        session.commit()
        log.info(f"  WC {UPCOMING_SEASON}: {inserted} upserted, {skipped} skipped")
        _log_run(session, "upcoming", WORLD_CUP_ID, UPCOMING_SEASON, inserted, skipped, "OK")
    except requests.HTTPError as e:
        session.rollback()
        msg = str(e)
        log.error(f"  HTTP error for WC {UPCOMING_SEASON}: {msg}")
        _log_run(session, "upcoming", WORLD_CUP_ID, UPCOMING_SEASON, 0, 0, "ERROR", msg)


def ingest_teams(client: FootballDataClient, session: Session) -> None:
    """Populate/refresh the teams lookup table."""
    log.info("=== Teams ingestion ===")
    for season in HISTORICAL_SEASONS + [UPCOMING_SEASON]:
        try:
            teams = client.get_competition_teams(WORLD_CUP_ID, season)
            for t in teams:
                upsert_team(session, t)
            session.commit()
            log.info(f"  Teams for WC {season}: {len(teams)} upserted")
        except requests.HTTPError as e:
            session.rollback()
            log.error(f"  Could not fetch teams for WC {season}: {e}")


def _log_run(
    session: Session,
    mode: str,
    competition: str,
    season: int,
    inserted: int,
    skipped: int,
    status: str,
    error_msg: Optional[str] = None,
) -> None:
    session.add(IngestLog(
        mode          = mode,
        competition   = competition,
        season        = season,
        rows_inserted = inserted,
        rows_skipped  = skipped,
        status        = status,
        error_msg     = error_msg,
    ))
    session.commit()


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

def init_db(db_path: str):
    """Create all tables if they don't exist and return engine + session."""
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    log.info(f"Database ready: {db_path}")
    return engine


# ---------------------------------------------------------------------------
# Verification helper — prints row counts after ingestion
# ---------------------------------------------------------------------------

def print_summary(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    print("\n" + "─" * 52)
    print(f"{'Table':<30} {'Rows':>8}")
    print("─" * 52)
    for table in ["teams", "historical_results", "upcoming_fixtures", "ingest_log"]:
        try:
            count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:<28} {count:>8,}")
        except sqlite3.OperationalError:
            print(f"  {table:<28} {'(missing)':>8}")
    print("─" * 52)

    print("\nSample historical results:")
    rows = cur.execute("""
        SELECT home_team_name, away_team_name, home_score, away_score, season
        FROM   historical_results
        ORDER  BY utc_date DESC
        LIMIT  5
    """).fetchall()
    for r in rows:
        print(f"  {r[0]:<22} {r[2]}–{r[3]}  {r[1]:<22}  (WC {r[4]})")

    print("\nSample upcoming fixtures:")
    rows = cur.execute("""
        SELECT home_team_name, away_team_name, utc_date, stage
        FROM   upcoming_fixtures
        ORDER  BY utc_date
        LIMIT  5
    """).fetchall()
    for r in rows:
        print(f"  {r[0]:<22} vs {r[1]:<22}  {r[2]}  [{r[3]}]")

    conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Ingest World Cup data from Football-Data.org into SQLite"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "historical", "upcoming", "fixtures"],
        default="full",
        help=(
            "full     = teams + historical + upcoming  (first run)\n"
            "historical = historical results only\n"
            "upcoming / fixtures = upcoming fixtures only"
        ),
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("FOOTBALL_DATA_API_KEY"),
        help="Football-Data.org API key (or set FOOTBALL_DATA_API_KEY env var)",
    )
    parser.add_argument(
        "--db",
        default=DB_PATH,
        help=f"Path to SQLite database file (default: {DB_PATH})",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.api_key:
        print(
            "ERROR: No API key found.\n"
            "  Set the FOOTBALL_DATA_API_KEY environment variable, or pass --api-key.\n"
            "  Sign up free at https://www.football-data.org/",
            file=sys.stderr,
        )
        sys.exit(1)

    # Initialise DB
    engine = init_db(args.db)
    client = FootballDataClient(args.api_key)

    with Session(engine) as session:
        mode = args.mode
        log.info(f"Starting ingest — mode={mode}")

        if mode == "full":
            ingest_teams(client, session)
            ingest_historical(client, session)
            ingest_upcoming(client, session)

        elif mode == "historical":
            ingest_teams(client, session)
            ingest_historical(client, session)

        elif mode in ("upcoming", "fixtures"):
            ingest_upcoming(client, session)

    print_summary(args.db)
    log.info("Done.")


if __name__ == "__main__":
    main()