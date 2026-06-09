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
    load_team_stats(db_path, seasons, exclude_extra_time)  → TeamStats dict
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

Future extension points
-----------------------
- Group-stage simulation:  call simulate_match() in a loop over group fixtures.
- Knockout simulation:     simulate_match() returns a SimResult with a
                           `winner` field — feed directly into bracket logic.
- Monte Carlo:             call simulate_match() N times; aggregate outcomes.
- Full 2026 bracket:       compose group + knockout simulators; read fixtures
                           from upcoming_fixtures table in predictor.db.
"""

from __future__ import annotations

import argparse
import logging
import math
import random
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

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

# Seasons considered "modern era" and always included by default.
# Extend this list to include older tournaments if you want more signal.
DEFAULT_SEASONS  = list(range(1994, 2023, 4))   # 1994 … 2022

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
        h["seasons"].add(row["season"])

        # Away team perspective
        a = _acc(away)
        a["scored"]   += aws * w
        a["conceded"] += hs  * w
        a["weight"]   += w
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

    mu = glob.goals_scored   # global baseline

    λ_home = mu * home.attack_strength * away.defense_strength
    λ_away = mu * away.attack_strength * home.defense_strength

    # Clamp to a sane range — prevents extreme λ from degenerate data
    λ_home = max(0.1, min(λ_home, 8.0))
    λ_away = max(0.1, min(λ_away, 8.0))

    return λ_home, λ_away


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
    λ_home, λ_away = expected_goals(stats, home_team, away_team)
    matrix         = scoreline_matrix(λ_home, λ_away, max_goals)
    hw, d, aw      = match_probabilities(matrix)
    scorelines     = _top_scorelines(matrix, home_team, away_team)

    return MatchResult(
        home_team     = _normalise(home_team),
        away_team     = _normalise(away_team),
        home_win_prob = hw,
        draw_prob     = d,
        away_win_prob = aw,
        lambda_home   = λ_home,
        lambda_away   = λ_away,
        scorelines    = scorelines,
        matrix        = matrix,
    )


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