"""
math_engine.py — World Cup Predictor
======================================
Poisson-based football match prediction engine.

Architecture
------------
This module is intentionally stateless and functional — every public
function accepts explicit arguments so that app.py, simulation runners,
and Monte Carlo loops can call them freely without hidden shared state.

Public API (import-safe)
------------------------
    Model selection (Milestone 5) — start here for new code:
    get_stats(model, ...)                                  → TeamStats dict (cached)
    predict(home, away, model, ...)                        → MatchResult
    describe_model(model)                                  → dict (label + description)
    clear_stats_cache()                                    → invalidate the stats cache

    Lower-level / model-specific loaders (still public, still supported):
    load_team_stats(db_path, seasons, exclude_extra_time)  → TeamStats dict ("historical")
    load_form_stats(db_path, cutoff_date, window_months)   → TeamStats dict ("form")
    load_hybrid_stats(db_path, historical_weight, ...)     → TeamStats dict ("hybrid")
    get_team_stats(stats, team_name)                       → TeamRecord
    expected_goals(stats, home, away)                      → (λ_home, λ_away)
    scoreline_matrix(λ_home, λ_away, max_goals)            → np.ndarray
    match_probabilities(matrix)                            → MatchResult
    predict_match(stats, home, away)                       → MatchResult
    simulate_match(stats, home, away, neutral)             → SimResult  ← for Monte Carlo
    available_teams(stats)                                 → list[str]

Design decisions
----------------
- No home advantage multiplier: all World Cup matches are at neutral venues.
- Extra-time / penalty results are EXCLUDED by default when building team
  strength (a 0-0 that crawls to pens distorts average goals conceded).
- Recency weighting: recent tournaments contribute more signal than 1930 data.
  The default decay gives WC 2022 ~3x the weight of WC 1930.
- Team name normalisation handles common variants (e.g. "Korea Republic" vs
  "South Korea") via an alias table that can be extended cheaply.
- All intermediate numpy arrays are float64 for numerical stability.
- Model configuration (default model, blend weights, form window) lives in
  ONE block — see "Model configuration (Milestone 5)" below — so app.py,
  the CLI, and any future simulation runner all read the same values.

Future extension points
-----------------------
- Group-stage simulation:  call simulate_match() in a loop over group fixtures.
- Knockout simulation:     simulate_match() returns a SimResult with a
                           `winner` field — feed directly into bracket logic.
- Monte Carlo:             call simulate_match() N times; aggregate outcomes.
- Full 2026 bracket:       compose group + knockout simulators; read fixtures
                           from upcoming_fixtures table in predictor.db. Use
                           get_stats(model=...) once per bracket run (cached)
                           rather than once per fixture.
"""

from __future__ import annotations

import argparse
import logging
import math
import random
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from services.tournament_rating_service import (build_tournament_ratings,)
from services.opponent_strength_service import (build_opponent_strength,get_opponent_strength,)
import numpy as np
from scipy.stats import poisson

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("math_engine")

# ---------------------------------------------------------------------------
# Constants & configuration defaults
# ---------------------------------------------------------------------------

DB_PATH          = "predictor.db"
MAX_GOALS        = 8        # scoreline matrix dimension (0..MAX_GOALS goals each side)
MIN_MATCHES      = 3        # minimum matches a team needs to get its own stats
                             # (below this → fall back to global average)
DECAY_HALF_LIFE  = 16.0    # years — WC 2022 weight ≈ 3× WC 1990, ≈ 6× WC 1930
BASE_YEAR        = 2023     # reference point for recency decay

# --- Recent Form layer constants (Milestone 2) ------------------------------
# Separate from the WC-history constants above. The form layer reads from
# international_results (not historical_results) and decays much faster —
# a qualifier from 6 years ago should barely matter for "current form",
# whereas a World Cup from 16 years ago still carries some signal for the
# historical layer. These two decay systems are intentionally independent;
# do not reuse DECAY_HALF_LIFE / BASE_YEAR for the form layer.
FORM_DECAY_HALF_LIFE = 3.0     # years — much shorter than the WC layer's 16.0

# Seasons considered "modern era" and always included by default.
# Extend this list to include older tournaments if you want more signal.
DEFAULT_SEASONS  = list(range(1994, 2023, 4))   # 1994 … 2022


# ===========================================================================
# Model configuration (Milestone 5)
# ===========================================================================
# Single source of truth for "which model does the app run by default, and
# with what parameters". Nothing below changes the math from Milestones
# 2/3 — load_team_stats() / load_form_stats() / blend_team_record() are
# untouched. This block only sets the DEFAULT values handed to those
# functions, and is the only constant block downstream code should ever
# read for the active default.
#
# DEFAULT_HISTORICAL_WEIGHT / DEFAULT_FORM_WEIGHT were updated from the
# original 0.70/0.30 placeholder to 0.40/0.60 per the Milestone 4 backtest
# result: 40% Historical / 60% Recent Form produced the best average Log
# Loss across WC 2018 and WC 2022. If a future backtest validates a new
# ratio, update ONLY the two lines below — every caller (predict_match(),
# get_stats(), the Streamlit app) reads from here, nothing is hardcoded
# a second time anywhere else.
# ---------------------------------------------------------------------------

DEFAULT_MODEL              = "hybrid"   # "historical" | "form" | "hybrid"
DEFAULT_HISTORICAL_WEIGHT  = 0.40       # validated, Milestone 4 backtest
DEFAULT_FORM_WEIGHT        = 0.60       # validated, Milestone 4 backtest
FORM_WINDOW_MONTHS         = 36         # passed to load_form_stats()
FORM_HALF_LIFE             = FORM_DECAY_HALF_LIFE   # display-facing alias, see note below

SUPPORTED_MODELS = ("historical", "form", "hybrid")

# Human-readable labels/descriptions, used by both the CLI and the Streamlit
# "model info" panel — kept here so UI copy and config can't drift apart.
MODEL_INFO: dict[str, dict] = {
    "historical": {
        "label": "Historical",
        "description": "World Cup history only (1930–2022), recency-weighted "
                        f"with a {DECAY_HALF_LIFE:.0f}-year half-life.",
    },
    "form": {
        "label": "Recent Form",
        "description": f"Last {FORM_WINDOW_MONTHS} months of international "
                        f"results, competition-weighted and recency-weighted "
                        f"with a {FORM_HALF_LIFE:.1f}-year half-life.",
    },
    "hybrid": {
        "label": "Hybrid (Recommended)",
        "description": f"{DEFAULT_HISTORICAL_WEIGHT:.0%} Historical World Cup "
                        f"strength + {DEFAULT_FORM_WEIGHT:.0%} Recent "
                        f"International Form. Recent window: "
                        f"{FORM_WINDOW_MONTHS} months. Competition-weighted. "
                        f"Recency-weighted.",
    },
}
# NOTE on FORM_HALF_LIFE vs FORM_DECAY_HALF_LIFE: the Milestone 2 decay
# function _form_recency_weight() reads FORM_DECAY_HALF_LIFE directly (its
# default arg is bound to that name at function-definition time) — that
# function is frozen and untouched per Milestone 5 scope. FORM_HALF_LIFE is
# purely a display-facing alias so the config block has a single home for
# the value, without renaming the constant the decay math actually depends on.

# ---------------------------------------------------------------------------
# Team name aliases
# Normalises historical naming inconsistencies so stats accumulate correctly.
# Keys are raw DB values; values are the canonical display name.
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
    """Return canonical team name, collapsing historical aliases."""
    if not name:
        return name
    key = name.strip().lower()
    return _ALIASES.get(key, name.strip())


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TeamRecord:
    """
    Per-team statistics computed from historical_results.
    All rate figures are per-match averages at neutral venues.
    """
    name:              str
    matches:           int
    goals_scored:      float   # weighted average goals scored per match
    goals_conceded:    float   # weighted average goals conceded per match
    attack_strength:   float   # goals_scored  / global_avg_scored
    defense_strength:  float   # goals_conceded / global_avg_conceded
    win_rate:          float
    draw_rate:         float
    loss_rate:         float
    seasons_seen:      list[int] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"{self.name:<25}  "
            f"GP={self.matches:>3}  "
            f"Atk={self.attack_strength:.3f}  "
            f"Def={self.defense_strength:.3f}  "
            f"W/D/L={self.win_rate:.0%}/{self.draw_rate:.0%}/{self.loss_rate:.0%}"
        )


@dataclass
class MatchResult:
    """
    Full probability distribution for a single match.
    Includes scoreline matrix and aggregated outcome probabilities.
    """
    home_team:      str
    away_team:      str
    home_win_prob:  float
    draw_prob:      float
    away_win_prob:  float
    lambda_home:    float   # expected goals — home side
    lambda_away:    float   # expected goals — away side
    historical_lambda_home: float
    historical_lambda_away: float

    live_adjustment_home: float
    live_adjustment_away: float
    scorelines:     list[tuple[str, float]]   # top N "(h-a)", prob — sorted desc
    matrix:         np.ndarray                # full [MAX_GOALS+1 × MAX_GOALS+1] matrix

    def summary(self, top_n: int = 5) -> str:
        lines = [
            f"\n{'─'*54}",
            f"  {self.home_team}  vs  {self.away_team}",
            f"{'─'*54}",
            f"  Expected goals:  {self.home_team} {self.lambda_home:.2f}  |  "
            f"{self.away_team} {self.lambda_away:.2f}",
            f"  Win:   {self.home_team:<20}  {self.home_win_prob:>6.1%}",
            f"  Draw:  {'─'*20}  {self.draw_prob:>6.1%}",
            f"  Win:   {self.away_team:<20}  {self.away_win_prob:>6.1%}",
            f"{'─'*54}",
            f"  Top {top_n} most likely scorelines:",
        ]
        for score, prob in self.scorelines[:top_n]:
            bar = "█" * int(prob * 200)
            lines.append(f"    {score:<8}  {prob:>5.1%}  {bar}")
        lines.append(f"{'─'*54}")
        return "\n".join(lines)


@dataclass
class SimResult:
    """
    Result of a single simulated match (used by Monte Carlo / bracket runners).
    Randomly sampled from the Poisson scoreline distribution.
    """
    home_team:   str
    away_team:   str
    home_goals:  int
    away_goals:  int
    winner:      str      # team name of winner, or "DRAW" (group stage)
    went_to_aet: bool     # True if knockout match needed extra time (future use)
    went_to_pen: bool     # True if knockout match needed penalties (future use)

    @property
    def score_str(self) -> str:
        return f"{self.home_goals}–{self.away_goals}"


# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

TeamStats = dict[str, TeamRecord]

# ---------------------------------------------------------------------------
# Database layer
# ---------------------------------------------------------------------------

def _connect(db_path: str) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Database not found: {db_path}\n"
            "  Run ingest_api.py and ingest_csv.py first."
        )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _recency_weight(season: int, base_year: int = BASE_YEAR,
                    half_life: float = DECAY_HALF_LIFE) -> float:
    """
    Exponential decay weight.  Matches from `base_year` have weight 1.0;
    older seasons contribute progressively less.

    half_life=16 means a tournament 16 years ago has weight 0.5.
    """
    age = max(0, base_year - season)
    return math.exp(-math.log(2) * age / half_life)


def _form_recency_weight(
    match_date: str,
     reference_date: datetime,
    half_life: float  = FORM_DECAY_HALF_LIFE,
) -> float:
    """
    Exponential decay weight for the Recent Form layer (Milestone 2).

    Mirrors _recency_weight() above but operates on a full ISO date
    string (international_results.match_date is 'YYYY-MM-DD', not a
    bare season/year int like historical_results.season) and uses the
    much shorter FORM_DECAY_HALF_LIFE instead of the WC layer's
    DECAY_HALF_LIFE. The WC decay function above is left completely
    unmodified — this is a parallel, independent implementation.

    half_life=3.0 means a match 3 years ago has weight 0.5.
    """
    try:
        match_year_fraction = datetime.fromisoformat(str(match_date)[:10])
        age_years = (
            reference_date - match_year_fraction
        ).days / 365.25
    except (ValueError, TypeError):
        age_years = 0.0   # unparseable date — treat as fully recent rather than drop it

    age_years = max(0.0, age_years)
    return math.exp(-math.log(2) * age_years / half_life)


def load_team_stats(
    db_path: str               = DB_PATH,
    seasons: Optional[list[int]] = None,
    exclude_extra_time: bool   = True,
) -> TeamStats:
    """
    Read historical_results and compute per-team strength metrics.

    Parameters
    ----------
    db_path            : path to predictor.db
    seasons            : list of WC seasons to include; None → DEFAULT_SEASONS
    exclude_extra_time : if True, exclude matches that went to extra time/pens
                         (avoids distorting average goals with artificially
                         drawn 90-minute scores)

    Returns
    -------
    dict mapping canonical team name → TeamRecord
    """
    seasons = seasons or DEFAULT_SEASONS
    log.info(f"Loading team stats | seasons={seasons} | excl_et={exclude_extra_time}")

    conn = _connect(db_path)

    season_placeholders = ",".join("?" * len(seasons))
    et_clause = "AND extra_time = 0 AND penalties = 0" if exclude_extra_time else ""

    query = f"""
        SELECT
            home_team_name,
            away_team_name,
            home_score,
            away_score,
            winner,
            season,
            extra_time,
            penalties
        FROM historical_results
        WHERE competition = 'WC'
          AND season IN ({season_placeholders})
          {et_clause}
    """

    rows = conn.execute(query, seasons).fetchall()
    conn.close()

    if not rows:
        raise ValueError(
            f"No historical data found for seasons {seasons}.\n"
            "  Check that ingest_csv.py was run and historical_results is populated."
        )

    log.info(f"  Loaded {len(rows)} matches for stats calculation")

    # ------------------------------------------------------------------
    # Accumulate weighted statistics per canonical team name
    # ------------------------------------------------------------------

    # Structure: { team_name: { "scored": w_sum, "conceded": w_sum,
    #                           "weight": w_sum, "wins": w, "draws": w,
    #                           "losses": w, "seasons": set } }
    accum: dict[str, dict] = {}

    def _acc(name: str) -> dict:
        cn = _normalise(name)
        if cn not in accum:
            accum[cn] = {
                "scored":   0.0,
                "conceded": 0.0,
                "weight":   0.0,
                "wins":     0.0,
                "draws":    0.0,
                "losses":   0.0,
                "raw_matches": 0,
                "seasons":  set(),
            }
        return accum[cn]

    for row in rows:
        w = _recency_weight(row["season"])
        home = _normalise(row["home_team_name"])
        away = _normalise(row["away_team_name"])
        hs   = row["home_score"]
        aws  = row["away_score"]

        # Home team perspective
        h = _acc(home)
        h["scored"]   += hs  * w
        h["conceded"] += aws * w
        h["weight"]   += w
        h["raw_matches"] += 1
        h["seasons"].add(row["season"])

        # Away team perspective
        a = _acc(away)
        a["scored"]   += aws * w
        a["conceded"] += hs  * w
        a["weight"]   += w
        a["raw_matches"] += 1
        a["seasons"].add(row["season"])

        # Wins / draws / losses (full-time result only)
        winner = row["winner"]
        if winner == "HOME_TEAM":
            h["wins"]   += w
            a["losses"] += w
        elif winner == "AWAY_TEAM":
            a["wins"]   += w
            h["losses"] += w
        else:  # DRAW or None
            h["draws"] += w
            a["draws"] += w

    # ------------------------------------------------------------------
    # Global baseline averages (weighted)
    # ------------------------------------------------------------------

    total_weight  = sum(v["weight"] for v in accum.values())
    global_scored = sum(v["scored"] for v in accum.values()) / total_weight
    global_conceded = global_scored   # symmetric at neutral venues

    log.info(
        f"  Global avg goals scored/conceded per team per match: "
        f"{global_scored:.4f}"
    )

    # ------------------------------------------------------------------
    # Build TeamRecord objects
    # ------------------------------------------------------------------

    stats: TeamStats = {}

    for name, v in accum.items():
        w = v["weight"]
        if w == 0:
            continue

        avg_scored   = v["scored"]   / w
        avg_conceded = v["conceded"] / w
        matches_est  = round(w)          # approximate integer match count

        # Attack / defense strength relative to global baseline
        atk = avg_scored   / global_scored   if global_scored   > 0 else 1.0
        dfn = avg_conceded / global_conceded if global_conceded > 0 else 1.0

        win_rate  = v["wins"]   / w
        draw_rate = v["draws"]  / w
        loss_rate = v["losses"] / w

        stats[name] = TeamRecord(
            name             = name,
            matches          = matches_est,
            goals_scored     = avg_scored,
            goals_conceded   = avg_conceded,
            attack_strength  = atk,
            defense_strength = dfn,
            win_rate         = win_rate,
            draw_rate        = draw_rate,
            loss_rate        = loss_rate,
            seasons_seen     = sorted(v["seasons"]),
        )

    log.info(f"  Built stats for {len(stats)} teams")

    # ------------------------------------------------------------------
    # Add a sentinel "GLOBAL_AVERAGE" entry for fallback lookups
    # ------------------------------------------------------------------

    stats["__global__"] = TeamRecord(
        name             = "__global__",
        matches          = round(total_weight),
        goals_scored     = global_scored,
        goals_conceded   = global_conceded,
        attack_strength  = 1.0,
        defense_strength = 1.0,
        win_rate         = 0.0,
        draw_rate        = 0.0,
        loss_rate        = 0.0,
    )

    return stats


# ---------------------------------------------------------------------------
# Recent Form layer (Milestone 2)
# ---------------------------------------------------------------------------
# Completely independent of load_team_stats() above. Reads ONLY from
# international_results — historical_results is never touched here.
#
# The returned TeamStats dict has the EXACT same shape as load_team_stats()'s
# output (same TeamRecord dataclass, same "__global__" sentinel key), so it
# is a drop-in replacement anywhere a TeamStats dict is expected:
#
#     form_stats = load_form_stats()
#     result = predict_match(form_stats, "Canada", "South Africa")
#
# predict_match() / expected_goals() / scoreline_matrix() / simulate_match()
# have NO knowledge of which loader produced the TeamStats dict they were
# given — that separation is what makes this drop-in compatible.
# ---------------------------------------------------------------------------

def load_form_stats(
    db_path:        str            = DB_PATH,
    cutoff_date:    Optional[str]  = None,
    window_months:  int            = 36,
) -> TeamStats:
    """
    Read international_results and compute per-team Recent Form strength
    metrics. Mirrors load_team_stats() structurally, but:

      - reads international_results instead of historical_results
      - has no season filter — instead uses a rolling date window
      - weight = competition_weight (read from the DB column, NOT
        hardcoded here) × _form_recency_weight() (3-year half-life)

    Parameters
    ----------
    db_path        : path to predictor.db
    cutoff_date     : ISO date string ('YYYY-MM-DD') to treat as "today"
                      for both the rolling window and the recency decay.
                      None → uses today's date. Pass an explicit cutoff
                      for backtesting (e.g. cutoff_date="2022-11-01" to
                      build form stats as they would have looked just
                      before WC 2022 kicked off).
    window_months   : how many months before cutoff_date to include.
                      Default 36 (3 years) — see Priority 1A evaluation.

    Returns
    -------
    dict mapping canonical team name → TeamRecord
    (identical shape to load_team_stats()'s return value)
    """
    if cutoff_date is None:
        cutoff_date = datetime.utcnow().date().isoformat()

    cutoff_dt   = datetime.fromisoformat(cutoff_date[:10])
    window_start = (
        cutoff_dt.replace(year=cutoff_dt.year - (window_months // 12))
        if window_months % 12 == 0
        else cutoff_dt.fromordinal(cutoff_dt.toordinal() - window_months * 30)
    )
    window_start_str = window_start.date().isoformat()

    log.info(
        f"Loading form stats | window={window_start_str} → {cutoff_date} "
        f"({window_months}mo) | half_life={FORM_DECAY_HALF_LIFE}y"
    )

    conn = _connect(db_path)

    query = """
        SELECT
            home_team,
            away_team,
            home_score,
            away_score,
            match_date,
            competition_weight,
            tournament_tier
        FROM international_results
        WHERE tournament_tier != 'EXCLUDED'
          AND match_date >= ?
          AND match_date <  ?
    """

    rows = conn.execute(query, (window_start_str, cutoff_date)).fetchall()
    conn.close()

    if not rows:
        raise ValueError(
            f"No international form data found in window "
            f"{window_start_str} → {cutoff_date}.\n"
            "  Check that ingest_form.py was run and international_results "
            "is populated."
        )

    log.info(f"  Loaded {len(rows)} matches for form stats calculation")

    # ------------------------------------------------------------------
    # Accumulate weighted statistics per canonical team name
    # Identical accumulator shape to load_team_stats() — "seasons" here
    # holds match_date strings rather than int years, used only for the
    # TeamRecord.seasons_seen field (kept for interface compatibility).
    # ------------------------------------------------------------------

    accum: dict[str, dict] = {}

    def _acc(name: str) -> dict:
        cn = _normalise(name)
        if cn not in accum:
            accum[cn] = {
                "scored":   0.0,
                "conceded": 0.0,
                "weight":   0.0,
                "wins":     0.0,
                "draws":    0.0,
                "losses":   0.0,
                "raw_matches": 0,
                "seasons":  set(),
            }
        return accum[cn]

    for row in rows:
        # weight = competition_weight (from DB, not hardcoded) × recency
        comp_w = row["competition_weight"]
        rec_w = _form_recency_weight(
        row["match_date"],
        cutoff_dt
        )
        w      = comp_w * rec_w

        home = _normalise(row["home_team"])
        away = _normalise(row["away_team"])
        hs   = row["home_score"]
        aws  = row["away_score"]

        # Home team perspective
        h = _acc(home)
        h["scored"]   += hs  * w
        h["conceded"] += aws * w
        h["weight"]   += w
        h["raw_matches"] += 1
        h["seasons"].add(row["match_date"][:4])   # year string, for display only

        # Away team perspective
        a = _acc(away)
        a["scored"]   += aws * w
        a["conceded"] += hs  * w
        a["weight"]   += w
        a["raw_matches"] += 1
        a["seasons"].add(row["match_date"][:4])

        # Wins / draws / losses (full-time result, derived from scores —
        # international_results has no pre-computed "winner" column)
        if hs > aws:
            h["wins"]   += w
            a["losses"] += w
        elif aws > hs:
            a["wins"]   += w
            h["losses"] += w
        else:
            h["draws"] += w
            a["draws"] += w

    # ------------------------------------------------------------------
    # Global baseline averages (weighted) — identical formula to
    # load_team_stats(), computed independently over the form dataset.
    # ------------------------------------------------------------------

    total_weight  = sum(v["weight"] for v in accum.values())
    global_scored = sum(v["scored"] for v in accum.values()) / total_weight
    global_conceded = global_scored   # symmetric — same assumption as WC layer

    log.info(
        f"  Global avg goals scored/conceded per team per match (form): "
        f"{global_scored:.4f}"
    )

    # ------------------------------------------------------------------
    # Build TeamRecord objects — identical construction to load_team_stats()
    # ------------------------------------------------------------------

    stats: TeamStats = {}

    for name, v in accum.items():
        w = v["weight"]
        if w == 0:
            continue

        avg_scored   = v["scored"]   / w
        avg_conceded = v["conceded"] / w

        atk = avg_scored   / global_scored   if global_scored   > 0 else 1.0
        dfn = avg_conceded / global_conceded if global_conceded > 0 else 1.0

        win_rate  = v["wins"]   / w
        draw_rate = v["draws"]  / w
        loss_rate = v["losses"] / w

        stats[name] = TeamRecord(
            name             = name,
            matches          = v["raw_matches"],
            goals_scored     = avg_scored,
            goals_conceded   = avg_conceded,
            attack_strength  = atk,
            defense_strength = dfn,
            win_rate         = win_rate,
            draw_rate        = draw_rate,
            loss_rate        = loss_rate,
            seasons_seen     = sorted(int(y) for y in v["seasons"]),
        )

    log.info(f"  Built form stats for {len(stats)} teams")

    # ------------------------------------------------------------------
    # Sentinel "GLOBAL_AVERAGE" entry — identical convention to
    # load_team_stats(), so get_team_stats() fallback logic works
    # unmodified against form_stats too.
    # ------------------------------------------------------------------

    stats["__global__"] = TeamRecord(
        name             = "__global__",
        matches          = round(total_weight),
        goals_scored     = global_scored,
        goals_conceded   = global_conceded,
        attack_strength  = 1.0,
        defense_strength = 1.0,
        win_rate         = 0.0,
        draw_rate        = 0.0,
        loss_rate        = 0.0,
    )

    return stats


# ---------------------------------------------------------------------------
# Hybrid model (Milestone 3)
# ---------------------------------------------------------------------------
# Combines the historical WC layer (load_team_stats) and the recent-form
# layer (load_form_stats) into a single TeamStats dict. This is purely a
# blending step — it calls the two existing loaders and combines their
# output, with zero duplication of the accumulation/decay logic that
# already lives in those two functions.
#
# The result is the SAME TeamRecord dataclass used everywhere else, so it
# plugs directly into predict_match() / simulate_match() with no changes
# to the Poisson engine. load_team_stats(), load_form_stats(), and
# load_hybrid_stats() are now three interchangeable TeamStats sources.
# ---------------------------------------------------------------------------

def blend_team_record(
    historical:         Optional[TeamRecord],
    form:                Optional[TeamRecord],
    historical_weight:   float = DEFAULT_HISTORICAL_WEIGHT,
    form_weight:         float = DEFAULT_FORM_WEIGHT,
) -> TeamRecord:
    """
    Blend one team's historical and recent-form TeamRecords into a single
    hybrid TeamRecord. All blending logic for the hybrid model is isolated
    here — load_hybrid_stats() never blends fields directly.

    Only the CORE rating parameters (attack_strength, defense_strength)
    are weight-blended, per spec. Everything else follows the edge-case
    and "informational only" rules below rather than being averaged:

      - If both records exist: attack/defense are blended; matches,
        goals_scored/conceded, win/draw/loss rates, and seasons_seen
        come from the FORM record (recent form is the more relevant
        source for "what does this team look like right now" stats),
        with the historical record's name/seasons folded in for context.
      - If only historical exists: returned as-is (no blending possible).
      - If only form exists: returned as-is (no blending possible).

    Parameters
    ----------
    historical          : TeamRecord from load_team_stats(), or None if
                          the team has no WC history
    form                 : TeamRecord from load_form_stats(), or None if
                          the team has no recent international form
    historical_weight    : weight applied to the historical attack/defense
    form_weight          : weight applied to the form attack/defense

    Returns
    -------
    TeamRecord — the same dataclass used throughout the project
    """
    # Edge case: team exists in only one dataset — use it as-is, unmodified.
    if historical is not None and form is None:
        return historical
    if form is not None and historical is None:
        return form
    if historical is None and form is None:
        raise ValueError("blend_team_record() requires at least one of historical/form")

    # Both exist — blend attack/defense strength only, per spec.
    hybrid_attack  = historical_weight * historical.attack_strength \
                    + form_weight       * form.attack_strength
    hybrid_defense = historical_weight * historical.defense_strength \
                    + form_weight       * form.defense_strength

    # Informational fields: sourced from FORM (more relevant to "current"
    # team state) rather than averaged — per spec, wins/draws/losses and
    # goals scored/conceded are explicitly NOT blended.
    return TeamRecord(
        name             = form.name,
        matches          = form.matches,
        goals_scored     = form.goals_scored,
        goals_conceded   = form.goals_conceded,
        attack_strength  = hybrid_attack,
        defense_strength = hybrid_defense,
        win_rate         = form.win_rate,
        draw_rate        = form.draw_rate,
        loss_rate        = form.loss_rate,
        seasons_seen = sorted(set(historical.seasons_seen) | set(form.seasons_seen)),
    )


def load_hybrid_stats(
    db_path:            str            = DB_PATH,
    historical_weight:   float          = DEFAULT_HISTORICAL_WEIGHT,
    form_weight:         float          = DEFAULT_FORM_WEIGHT,
    cutoff_date:         Optional[str]  = None,
    seasons:             Optional[list[int]] = None,
    window_months:       int            = 36,
) -> TeamStats:
    """
    Build a hybrid TeamStats dict by blending the historical WC layer and
    the recent-form layer for every team that appears in either dataset.

    Internally calls load_team_stats() and load_form_stats() directly —
    no duplicated accumulation, decay, or query logic. This function only
    unions the two team sets and blends per-team via blend_team_record().

    Parameters
    ----------
    db_path             : path to predictor.db
    historical_weight    : weight applied to historical attack/defense
                           (default DEFAULT_HISTORICAL_WEIGHT = 0.70)
    form_weight          : weight applied to form attack/defense
                           (default DEFAULT_FORM_WEIGHT = 0.30)
    cutoff_date           : passed straight through to load_form_stats() —
                           lets a future backtest milestone build hybrid
                           stats "as of" a historical date with no leakage
    seasons               : passed straight through to load_team_stats()
    window_months         : passed straight through to load_form_stats()

    Returns
    -------
    dict mapping canonical team name → TeamRecord
    (identical shape to load_team_stats() / load_form_stats())
    """
    log.info("Loading hybrid stats...")

    historical = load_team_stats(db_path=db_path, seasons=seasons)
    form       = load_form_stats(
        db_path        = db_path,
        cutoff_date     = cutoff_date,
        window_months   = window_months,
    )

    log.info(f"  Historical teams: {len(available_teams(historical))}")
    log.info(f"  Form teams:       {len(available_teams(form))}")
    log.info(
        f"  Blend ratio: {historical_weight:.0%} historical / "
        f"{form_weight:.0%} form"
    )

    # Union of both team sets (excluding the "__global__" sentinel, which
    # is rebuilt fresh below rather than blended like a real team).
    hist_teams = set(historical) - {"__global__"}
    form_teams = set(form)       - {"__global__"}
    all_teams  = hist_teams | form_teams

    hybrid: TeamStats = {}
    for team in all_teams:
        hybrid[team] = blend_team_record(
            historical          = historical.get(team),
            form                 = form.get(team),
            historical_weight    = historical_weight,
            form_weight          = form_weight,
        )

    # Global sentinel: blend the two global baselines the same way as any
    # other team, so get_team_stats() fallback behaviour stays consistent
    # for hybrid stats too.
    hybrid["__global__"] = blend_team_record(
        historical          = historical["__global__"],
        form                 = form["__global__"],
        historical_weight    = historical_weight,
        form_weight          = form_weight,
    )

    log.info(f"  Hybrid teams: {len(available_teams(hybrid))}")

    return hybrid


def compare_team_models(
    team_name:          str,
    db_path:             str            = DB_PATH,
    historical_weight:   float          = DEFAULT_HISTORICAL_WEIGHT,
    form_weight:         float          = DEFAULT_FORM_WEIGHT,
    cutoff_date:         Optional[str]  = None,
) -> str:
    """
    Debugging / validation helper — prints a side-by-side comparison of a
    team's historical, recent-form, and hybrid attack/defense ratings.

    Used for manually sanity-checking the blend before any future milestone
    adds automatic weight tuning. Not used by the prediction engine itself.

    Example
    -------
        >>> print(compare_team_models("Argentina"))
        ================================================
          Argentina
        ================================================
          Historical
            Attack:  1.31
            Defense: 0.42
          Recent Form
            Attack:  1.40
            Defense: 0.27
          Hybrid (70/30)
            Attack:  1.34
            Defense: 0.37
        ================================================
    """
    historical = load_team_stats(db_path=db_path)
    form       = load_form_stats(db_path=db_path, cutoff_date=cutoff_date)

    canonical = _normalise(team_name)

    # Same lookup style as load_hybrid_stats(): may be None if the team
    # doesn't appear in that dataset. get_team_stats() is used only for
    # display purposes below, since it provides the global-average
    # fallback when a team is genuinely absent from BOTH datasets.
    h_raw = historical.get(canonical)
    f_raw = form.get(canonical)

    h_rec = h_raw if h_raw is not None else get_team_stats(historical, team_name)
    f_rec = f_raw if f_raw is not None else get_team_stats(form, team_name)

    hybrid_rec = blend_team_record(
        historical          = h_raw,
        form                 = f_raw,
        historical_weight    = historical_weight,
        form_weight          = form_weight,
    )

    w = 48
    lines = [
        "=" * w,
        f"  {_normalise(team_name)}",
        "=" * w,
        "  Historical",
        f"    Attack:  {h_rec.attack_strength:.2f}",
        f"    Defense: {h_rec.defense_strength:.2f}",
        "  Recent Form",
        f"    Attack:  {f_rec.attack_strength:.2f}",
        f"    Defense: {f_rec.defense_strength:.2f}",
        f"  Hybrid ({historical_weight:.0%}/{form_weight:.0%})",
        f"    Attack:  {hybrid_rec.attack_strength:.2f}",
        f"    Defense: {hybrid_rec.defense_strength:.2f}",
        "=" * w,
    ]
    return "\n".join(lines)


# ===========================================================================
# Model selection & caching (Milestone 5)
# ===========================================================================
# This section is purely integration plumbing. It does not introduce any
# new statistics, weighting, or probability logic — it only:
#   1. gives every caller (app.py, the CLI, future tournament/bracket
#      runners) ONE function to ask for "the stats for model X", instead
#      of each caller needing to know which of the three loaders to call
#      and with which config constants
#   2. caches the result of each (model, params) combination so a Streamlit
#      session — or a loop predicting many fixtures — doesn't re-read and
#      re-aggregate the SQLite tables on every single prediction
#
# get_team_stats(), expected_goals(), scoreline_matrix(), predict_match(),
# and simulate_match() are completely unaware this section exists — they
# still just accept a TeamStats dict, exactly as before. That's what keeps
# this backwards compatible: nothing about their signature or behaviour
# changed.
# ---------------------------------------------------------------------------

# Process-level cache: {cache_key: TeamStats}. A plain dict is sufficient
# here (and avoids pulling in functools.lru_cache, which can't hash the
# Optional[list[int]] `seasons` argument cleanly) — cache_key is built from
# only the primitive values that actually affect the query/blend result.
_STATS_CACHE: dict[tuple, TeamStats] = {}


def _cache_key(
    model:               str,
    db_path:              str,
    seasons:               Optional[tuple[int, ...]],
    cutoff_date:           Optional[str],
    window_months:         int,
    historical_weight:     Optional[float],
    form_weight:            Optional[float],
) -> tuple:
    """Build a hashable cache key from only the args relevant to `model`."""
    return (model, db_path, seasons, cutoff_date, window_months,
            historical_weight, form_weight)


def clear_stats_cache() -> None:
    """
    Drop every cached TeamStats result.

    Call this if the underlying database has changed since stats were last
    loaded (e.g. after re-running ingest_api.py / ingest_csv.py / a fresh
    Streamlit deploy with new data) — otherwise get_stats() keeps returning
    the stale, previously-cached dict for the same (model, params) key.
    """
    _STATS_CACHE.clear()


def get_stats(
    model:               str                  = DEFAULT_MODEL,
    db_path:              str                  = DB_PATH,
    seasons:               Optional[list[int]]  = None,
    cutoff_date:           Optional[str]        = None,
    window_months:         int                  = FORM_WINDOW_MONTHS,
    historical_weight:     float                = DEFAULT_HISTORICAL_WEIGHT,
    form_weight:            float                = DEFAULT_FORM_WEIGHT,
    use_cache:              bool                 = True,
) -> TeamStats:
    """
    Single entry point for "give me a TeamStats dict for model X".

    This is the function app.py, the CLI, and any future tournament
    simulator should call — not load_team_stats() / load_form_stats() /
    load_hybrid_stats() directly — so that model selection stays in one
    place and so repeated calls with the same parameters reuse a cached
    result instead of rebuilding from SQLite every time.

    Parameters
    ----------
    model               : "historical" | "form" | "hybrid" (default:
                          DEFAULT_MODEL, currently "hybrid")
    db_path              : path to predictor.db
    seasons               : WC seasons to include — only used by
                          "historical" and "hybrid"; None → DEFAULT_SEASONS
                          (passed straight through to load_team_stats())
    cutoff_date           : "as of" date for the form layer — only used by
                          "form" and "hybrid"; None → today
    window_months         : recent-form rolling window — only used by
                          "form" and "hybrid"; default FORM_WINDOW_MONTHS
    historical_weight     : blend weight — only used by "hybrid";
                          default DEFAULT_HISTORICAL_WEIGHT (0.40)
    form_weight            : blend weight — only used by "hybrid";
                          default DEFAULT_FORM_WEIGHT (0.60)
    use_cache              : if True (default), reuse a previously built
                          TeamStats dict for an identical (model, params)
                          call instead of re-querying the database

    Returns
    -------
    TeamStats dict — identical shape regardless of which model was chosen,
    so every downstream function (get_team_stats(), expected_goals(),
    predict_match(), simulate_match()) works unmodified.

    Raises
    ------
    ValueError if `model` is not one of SUPPORTED_MODELS.
    """
    if model not in SUPPORTED_MODELS:
        raise ValueError(
            f"Unknown model {model!r}. Supported models: {SUPPORTED_MODELS}"
        )

    seasons_key = tuple(seasons) if seasons is not None else None
    key = _cache_key(
        model, db_path, seasons_key, cutoff_date, window_months,
        historical_weight if model == "hybrid" else None,
        form_weight if model == "hybrid" else None,
    )

    if use_cache and key in _STATS_CACHE:
        log.debug(f"  get_stats() cache hit — model={model}")
        return _STATS_CACHE[key]

    if model == "historical":
        stats = load_team_stats(db_path=db_path, seasons=seasons)

    elif model == "form":
        stats = load_form_stats(
            db_path        = db_path,
            cutoff_date     = cutoff_date,
            window_months   = window_months,
        )

    else:  # "hybrid"
        stats = load_hybrid_stats(
            db_path             = db_path,
            historical_weight    = historical_weight,
            form_weight           = form_weight,
            cutoff_date           = cutoff_date,
            seasons               = seasons,
            window_months         = window_months,
        )

    if use_cache:
        _STATS_CACHE[key] = stats

    return stats


def describe_model(model: str = DEFAULT_MODEL) -> dict:
    """
    Return the display-facing info dict for `model` from MODEL_INFO.

    Used by the Streamlit "model details" panel so the UI never hardcodes
    model copy itself — it just renders whatever this returns.
    """
    if model not in SUPPORTED_MODELS:
        raise ValueError(
            f"Unknown model {model!r}. Supported models: {SUPPORTED_MODELS}"
        )
    return MODEL_INFO[model]


# ---------------------------------------------------------------------------
# Team lookup
# ---------------------------------------------------------------------------

def get_team_stats(stats: TeamStats, team_name: str) -> TeamRecord:
    """
    Retrieve a TeamRecord by name, with fuzzy normalisation and fallback.

    Falls back to global average for teams with < MIN_MATCHES appearances
    (e.g. WC 2026 debutants).  Logs a warning so the caller is aware.
    """
    canonical = _normalise(team_name)

    if canonical in stats and stats[canonical].matches >= MIN_MATCHES:
        return stats[canonical]

    # Partial-match fallback (e.g. "Korea" → "South Korea")
    matches = [k for k in stats if canonical.lower() in k.lower() or
               k.lower() in canonical.lower()]
    matches = [m for m in matches if m != "__global__"]

    if len(matches) == 1 and stats[matches[0]].matches >= MIN_MATCHES:
        log.debug(f"  Fuzzy match: '{team_name}' → '{matches[0]}'")
        return stats[matches[0]]

    log.warning(
        f"  '{team_name}' not found or insufficient data "
        f"(< {MIN_MATCHES} matches) — using global average"
    )
    return stats["__global__"]


def available_teams(stats: TeamStats) -> list[str]:
    """Return sorted list of all teams with their own historical data."""
    return sorted(k for k in stats if k != "__global__")


# ---------------------------------------------------------------------------
# Poisson engine
# ---------------------------------------------------------------------------

def expected_goals(
    stats: TeamStats,
    home_team: str,
    away_team: str,
    home_live: dict | None = None,
    away_live: dict | None = None,
) -> tuple[float, float]:
    """
    Compute expected goals (λ) for each side using the standard
    Dixon-Coles / Maher attack × defense strength model.

    Formula (neutral venue — no home advantage term):
        λ_home = global_avg × home_attack × away_defense
        λ_away = global_avg × away_attack × home_defense

    Returns
    -------
    (lambda_home, lambda_away) — Poisson rate parameters
    """
    glob  = stats["__global__"]
    home  = get_team_stats(stats, home_team)
    away  = get_team_stats(stats, away_team)

    strengths = build_opponent_strength()

    home_strength = get_opponent_strength(
        home_team,
        strengths,
    )

    away_strength = get_opponent_strength(
        away_team,
        strengths,
    )
    mu = glob.goals_scored   # global baseline

    λ_home = mu * home.attack_strength * away.defense_strength
    λ_away = mu * away.attack_strength * home.defense_strength
    
    historical_lambda_home = (
        mu *
        home.attack_strength *
        away.defense_strength
    )

    historical_lambda_away = (
        mu *
        away.attack_strength *
        home.defense_strength
    )

    λ_home = historical_lambda_home
    λ_away = historical_lambda_away

    if home_live is None:
            home_live = {}
    if away_live is None:
            away_live = {}

        # Safely inject default values for any missing keys
    for key in ["attack", "defense", "form"]:
        home_live.setdefault(key, 0.50)
        away_live.setdefault(key, 0.50)

    home_attack_factor = 1.0 + (
        (home_live["attack"] - 0.50) * 0.12
    )

    away_attack_factor = 1.0 + (
        (away_live["attack"] - 0.50) * 0.12
    )

    home_defense_factor = 1.0 - (
        (home_live["defense"] - 0.50) * 0.08
    )

    away_defense_factor = 1.0 - (
        (away_live["defense"] - 0.50) * 0.08
    )

    home_form_factor = 1.0 + (
        (home_live["form"] - 0.50) * 0.10
    )

    away_form_factor = 1.0 + (
        (away_live["form"] - 0.50) * 0.10
    )
    OPPONENT_STRENGTH_WEIGHT = 0.08

    home_opponent_factor = (
        1.0 +
        ((away_strength - 1.0) * OPPONENT_STRENGTH_WEIGHT)
    )

    away_opponent_factor = (
        1.0 +
        ((home_strength - 1.0) * OPPONENT_STRENGTH_WEIGHT)
    )

    λ_home *= home_opponent_factor
    λ_away *= away_opponent_factor
    
    λ_home *= (
        home_attack_factor *
        away_defense_factor *
        home_form_factor
    )

    λ_away *= (
        away_attack_factor *
        home_defense_factor *
        away_form_factor
    )
    λ_home = max(0.1, min(λ_home, 8.0))
    λ_away = max(0.1, min(λ_away, 8.0))

    live_adjustment_home = (
        λ_home / historical_lambda_home
    )

    live_adjustment_away = (
        λ_away / historical_lambda_away
    )
    # Clamp to a sane range — prevents extreme λ from degenerate data
    λ_home = max(0.1, min(λ_home, 8.0))
    λ_away = max(0.1, min(λ_away, 8.0))
    print(f"Home Strength : {home_strength:.3f}")
    print(f"Away Strength : {away_strength:.3f}")
    return (
        λ_home,
        λ_away,
        historical_lambda_home,
        historical_lambda_away,
        live_adjustment_home,
        live_adjustment_away,
    )

def scoreline_matrix(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = MAX_GOALS,
) -> np.ndarray:
    """
    Build a (max_goals+1) × (max_goals+1) probability matrix where
    matrix[i][j] = P(home scores i) × P(away scores j).

    Rows = home goals (0 → max_goals)
    Cols = away goals (0 → max_goals)

    The matrix rows sum to ≈ 1.0 (residual probability for > max_goals
    is truncated; with max_goals=8 this is < 0.001 for typical λ).
    """
    home_probs = np.array([poisson.pmf(g, lambda_home) for g in range(max_goals + 1)])
    away_probs = np.array([poisson.pmf(g, lambda_away) for g in range(max_goals + 1)])

    # Outer product → joint probability matrix
    matrix = np.outer(home_probs, away_probs)

    return matrix


def match_probabilities(matrix: np.ndarray) -> tuple[float, float, float]:
    """
    Aggregate a scoreline matrix into Win / Draw / Loss probabilities.

    Returns
    -------
    (home_win_prob, draw_prob, away_win_prob)
    """
    size = matrix.shape[0]
    home_win = 0.0
    draw     = 0.0
    away_win = 0.0

    for i in range(size):       # home goals
        for j in range(size):   # away goals
            p = matrix[i, j]
            if i > j:
                home_win += p
            elif i == j:
                draw     += p
            else:
                away_win += p

    # Normalise — ensures they sum to 1.0 despite matrix truncation
    total = home_win + draw + away_win
    if total > 0:
        home_win /= total
        draw     /= total
        away_win /= total

    return home_win, draw, away_win


def _top_scorelines(
    matrix: np.ndarray,
    home_team: str,
    away_team: str,
    top_n: int = 10,
) -> list[tuple[str, float]]:
    """Return the top_n most probable exact scorelines, sorted descending."""
    size = matrix.shape[0]
    scores = []
    for i in range(size):
        for j in range(size):
            label = f"{i}–{j}"
            scores.append((label, float(matrix[i, j])))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_n]


# ---------------------------------------------------------------------------
# High-level prediction (main public interface for app.py)
# ---------------------------------------------------------------------------

def predict_match(
    stats: TeamStats,
    home_team: str,
    away_team: str,
    max_goals: int = MAX_GOALS,
) -> MatchResult:
    """
    Full match prediction: expected goals → scoreline matrix → probabilities.

    This is the primary function called by app.py.

    Parameters
    ----------
    stats     : TeamStats dict from load_team_stats()
    home_team : team listed as "home" in the fixture (cosmetic only — no advantage applied)
    away_team : team listed as "away" in the fixture

    Returns
    -------
    MatchResult with probabilities, expected goals, and top scorelines
    """
    tournament_ratings = build_tournament_ratings()

    home_live = tournament_ratings.get(
        home_team,
        {"overall": 0.50},
    )

    away_live = tournament_ratings.get(
        away_team,
        {"overall": 0.50},
    )
    (
    λ_home,
    λ_away,
    historical_home,
    historical_away,
    home_adjustment,
    away_adjustment,
) = expected_goals(
    stats,
    home_team,
    away_team,
    home_live,
    away_live,
)
    print("\n==============================")
    print(f"{home_team} vs {away_team}")
    print("------------------------------")
    print(f"Historical λ : {historical_home:.3f} | {historical_away:.3f}")
    print(f"Adjustment   : {home_adjustment:.3f} | {away_adjustment:.3f}")
    print(f"Final λ      : {λ_home:.3f} | {λ_away:.3f}")
    print("==============================")
    matrix         = scoreline_matrix(λ_home, λ_away, max_goals)
    hw, d, aw      = match_probabilities(matrix)
    scorelines     = _top_scorelines(matrix, home_team, away_team)

    return MatchResult(
        home_team=_normalise(home_team),
        away_team=_normalise(away_team),

        home_win_prob=hw,
        draw_prob=d,
        away_win_prob=aw,

        lambda_home=λ_home,
        lambda_away=λ_away,

        historical_lambda_home=historical_home,
        historical_lambda_away=historical_away,

        live_adjustment_home=home_adjustment,
        live_adjustment_away=away_adjustment,

        scorelines=scorelines,
        matrix=matrix,
    )


def predict(
    home_team:            str,
    away_team:             str,
    model:                  str            = DEFAULT_MODEL,
    db_path:                str            = DB_PATH,
    seasons:                 Optional[list[int]] = None,
    cutoff_date:             Optional[str]  = None,
    window_months:           int            = FORM_WINDOW_MONTHS,
    historical_weight:       float          = DEFAULT_HISTORICAL_WEIGHT,
    form_weight:              float          = DEFAULT_FORM_WEIGHT,
    max_goals:                int            = MAX_GOALS,
    use_cache:                bool           = True,
) -> MatchResult:
    """
    Model-aware convenience wrapper around predict_match() (Milestone 5).

    predict_match() still takes a pre-built `stats` dict as its first
    argument and is unchanged — this function exists alongside it so a
    caller can ask for a prediction by MODEL NAME instead of having to
    build the TeamStats dict themselves first:

        predict("Argentina", "Brazil")                    # uses DEFAULT_MODEL ("hybrid")
        predict("Argentina", "Brazil", model="historical")
        predict("Argentina", "Brazil", model="form")

    Internally this is just get_stats(model=...) followed by
    predict_match(stats, ...) — no new prediction logic, no change to the
    Poisson engine. get_stats() caching means calling predict() repeatedly
    for the same model/params (e.g. once per fixture in a tournament
    bracket) does not re-read or re-aggregate the database each time.

    Returns
    -------
    MatchResult — identical to predict_match()'s return value.
    """
    stats = get_stats(
        model               = model,
        db_path              = db_path,
        seasons               = seasons,
        cutoff_date           = cutoff_date,
        window_months         = window_months,
        historical_weight     = historical_weight,
        form_weight            = form_weight,
        use_cache              = use_cache,
    )
    return predict_match(stats, home_team, away_team, max_goals=max_goals)


# ---------------------------------------------------------------------------
# Simulation (used by Monte Carlo and bracket runners)
# ---------------------------------------------------------------------------

def simulate_match(
    stats: TeamStats,
    home_team: str,
    away_team: str,
    knockout: bool = False,
    rng: Optional[random.Random] = None,
) -> SimResult:
    """
    Sample a single match result from the Poisson distribution.

    Group stage (knockout=False):
        Result may be a DRAW.

    Knockout stage (knockout=True):
        If scores are level after 90 min, one penalty shootout winner is
        selected proportionally (the team with the higher λ wins pens with
        a slight edge, modelling real-world penalties only roughly).

    Parameters
    ----------
    stats     : TeamStats dict
    home_team : team name
    away_team : team name
    knockout  : if True, resolve draws via simulated penalty shootout
    rng       : optional seeded random.Random for reproducible Monte Carlo runs

    Returns
    -------
    SimResult with goals, winner, and extra-time / penalty flags
    """
    _rng = rng or random

    λ_home, λ_away = expected_goals(stats, home_team, away_team)

    # Sample goals from Poisson distributions
    home_goals = _rng.choices(
        range(MAX_GOALS + 1),
        weights=[poisson.pmf(g, λ_home) for g in range(MAX_GOALS + 1)],
    )[0]

    away_goals = _rng.choices(
        range(MAX_GOALS + 1),
        weights=[poisson.pmf(g, λ_away) for g in range(MAX_GOALS + 1)],
    )[0]

    went_to_aet = False
    went_to_pen = False
    h_canon = _normalise(home_team)
    a_canon = _normalise(away_team)

    if home_goals > away_goals:
        winner = h_canon
    elif away_goals > home_goals:
        winner = a_canon
    else:
        if knockout:
            went_to_aet = True
            # Penalty model: slight edge to the stronger attacking team
            home_pen_edge = λ_home / (λ_home + λ_away)
            if _rng.random() < home_pen_edge:
                winner = h_canon
            else:
                winner = a_canon
            went_to_pen = True
        else:
            winner = "DRAW"

    return SimResult(
        home_team   = h_canon,
        away_team   = a_canon,
        home_goals  = home_goals,
        away_goals  = away_goals,
        winner      = winner,
        went_to_aet = went_to_aet,
        went_to_pen = went_to_pen,
    )


def run_monte_carlo(
    stats: TeamStats,
    home_team: str,
    away_team: str,
    n: int = 100_000,
    knockout: bool = False,
    seed: Optional[int] = None,
) -> dict:
    """
    Run N simulations of a single match and return aggregated outcome rates.

    Useful for validating the analytical model and for stress-testing
    edge cases (e.g. teams with sparse historical data).

    Returns
    -------
    dict with keys: home_win, draw, away_win, avg_home_goals, avg_away_goals
    """
    rng = random.Random(seed)
    wins_h = wins_a = draws = 0
    total_hg = total_ag = 0.0

    h_canon = _normalise(home_team)
    a_canon = _normalise(away_team)

    for _ in range(n):
        sim = simulate_match(stats, home_team, away_team, knockout=knockout, rng=rng)
        total_hg += sim.home_goals
        total_ag += sim.away_goals
        if sim.winner == h_canon:
            wins_h += 1
        elif sim.winner == a_canon:
            wins_a += 1
        else:
            draws += 1

    return {
        "home_win":       wins_h / n,
        "draw":           draws  / n,
        "away_win":       wins_a / n,
        "avg_home_goals": total_hg / n,
        "avg_away_goals": total_ag / n,
        "n_simulations":  n,
    }


# ---------------------------------------------------------------------------
# CLI demo / sanity test
# ---------------------------------------------------------------------------

def _cli_demo(db_path: str, home: str, away: str, mc_runs: int) -> None:
    print(f"\n{'═'*54}")
    print("  WORLD CUP PREDICTOR — Math Engine")
    print(f"{'═'*54}")

    # Load stats
    print(f"\n  Loading team statistics from {db_path} …")
    stats = load_team_stats(db_path)
    print(f"  Teams with historical data: {len(available_teams(stats))}")

    # Show individual team records
    print(f"\n  Team profiles:")
    for team in [home, away]:
        rec = get_team_stats(stats, team)
        print(f"    {rec}")

    # Analytical prediction
    result = predict_match(stats, home, away)
    print(result.summary(top_n=8))

    # Monte Carlo validation
    if mc_runs > 0:
        print(f"\n  Monte Carlo validation ({mc_runs:,} simulations) …")
        mc = run_monte_carlo(stats, home, away, n=mc_runs, seed=42)
        print(f"    MC  home win:       {mc['home_win']:>6.1%}  "
              f"(analytical: {result.home_win_prob:.1%})")
        print(f"    MC  draw:           {mc['draw']:>6.1%}  "
              f"(analytical: {result.draw_prob:.1%})")
        print(f"    MC  away win:       {mc['away_win']:>6.1%}  "
              f"(analytical: {result.away_win_prob:.1%})")
        print(f"    MC  avg goals:      {mc['avg_home_goals']:.2f} – "
              f"{mc['avg_away_goals']:.2f}")

    # Knockout sim example
    print(f"\n  Knockout simulation (single sample, seed=99):")
    sim = simulate_match(stats, home, away, knockout=True, rng=random.Random(99))
    aet_str = " (AET+Pens)" if sim.went_to_pen else ""
    print(f"    {sim.home_team} {sim.home_goals} – {sim.away_goals} "
          f"{sim.away_team}{aet_str}")
    print(f"    → Winner: {sim.winner}")

    print(f"\n{'═'*54}\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Math engine CLI — run a match prediction demo"
    )
    parser.add_argument(
        "--db", default=DB_PATH,
        help=f"Path to predictor.db (default: {DB_PATH})"
    )
    parser.add_argument(
        "--home", default="Argentina",
        help="Home team name (default: Argentina)"
    )
    parser.add_argument(
        "--away", default="Brazil",
        help="Away team name (default: Brazil)"
    )
    parser.add_argument(
        "--mc", type=int, default=100_000,
        help="Monte Carlo simulation count (0 to skip, default: 100000)"
    )
    parser.add_argument(
        "--seasons", type=int, nargs="+", default=None,
        help="WC seasons to include (default: 1994-2022)"
    )
    parser.add_argument(
        "--include-et", action="store_true",
        help="Include extra-time / penalty matches in stats calculation"
    )
    parser.add_argument(
        "--list-teams", action="store_true",
        help="Print all teams with historical data and exit"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable verbose debug logging"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list_teams:
        stats = load_team_stats(args.db, args.seasons, not args.include_et)
        print(f"\n  Teams with historical WC data ({len(available_teams(stats))}):\n")
        for t in available_teams(stats):
            print(f"    {stats[t]}")
        raise SystemExit(0)

    _cli_demo(
        db_path  = args.db,
        home     = args.home,
        away     = args.away,
        mc_runs  = args.mc,
    )