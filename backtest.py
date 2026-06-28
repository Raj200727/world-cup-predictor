"""
backtest.py — World Cup Predictor V2 — Milestone 4
=====================================================
Rigorous out-of-sample evaluation framework comparing three TeamStats
sources from math_engine.py:

    1. Historical   — load_team_stats()    (WC 1930-2022 only)
    2. Recent Form   — load_form_stats()    (international_results only)
    3. Hybrid        — load_hybrid_stats()  (blend of the two, at every
                                             weight ratio in WEIGHT_GRID)

This file does NOT modify the prediction engine. It only calls the three
loaders above plus predict_match() and scores the output against real
results. math_engine.py is treated as a stable, frozen dependency.

Run with:
    python backtest.py

Supported tournaments are defined in TOURNAMENT_CONFIGS below — adding a
new one (e.g. WC 2026 after it concludes) is a single dict entry, nothing
else in this file needs to change.

KNOWN LIMITATION — read before trusting Historical-model backtest numbers
---------------------------------------------------------------------------
load_team_stats() filters WHICH SEASONS are included via its `seasons`
parameter (which this file uses correctly to prevent leakage — see
TOURNAMENT_CONFIGS), but its internal recency-decay weighting always
anchors to math_engine.BASE_YEAR (2023), not to the tournament's actual
cutoff date. This file was told not to modify load_team_stats(), so this
is not patched here. Practical effect: when backtesting WC 2018 (where
the correct "now" for decay purposes is 2018, not 2023), WC 2014 data is
decayed as if it were 5 years before 2023 (9 years old) rather than 4
years before 2018 (also reads as old, but the slope differs slightly from
the mathematically "correct" backtest). The Historical-model numbers
below are still valid for COMPARING model types and weight ratios
relative to each other (which is this milestone's actual goal), but are
not a perfectly leak-proof historical decay simulation. The Recent Form
and Hybrid models do not have this issue — load_form_stats() correctly
anchors decay to its own cutoff_date parameter.
"""

from __future__ import annotations

import csv
import logging
import math
import sqlite3

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent

import math_engine as me

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backtest")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = str(PROJECT_ROOT / "predictor.db")
LOG_LOSS_CLIP = 1e-9   # clip near-zero probabilities before log() to avoid -inf

# Configurable weight grid for the Hybrid model — NOT hardcoded into the
# evaluation logic. Add/remove ratios here; evaluate_weight_grid() will
# automatically test every one.
WEIGHT_GRID: list[tuple[float, float]] = [
    (i/10, 1-i/10)
    for i in range(10, -1, -1)
]


@dataclass
class TournamentConfig:
    """
    Everything needed to backtest one World Cup with zero data leakage.

    historical_seasons : passed to load_team_stats(seasons=...) — every
                         season strictly BEFORE the test tournament.
    form_cutoff_date    : passed to load_form_stats(cutoff_date=...) — the
                         tournament's start date. The form layer's 3-year
                         window looks backward from here automatically.
    """
    name:                str
    test_season:          int
    historical_seasons:   list[int]
    form_cutoff_date:     str
    form_window_months:   int = 36


# Add new tournaments here — nothing else in this file needs to change.
TOURNAMENT_CONFIGS: list[TournamentConfig] = [
    TournamentConfig(
        name                = "World Cup 2018",
        test_season          = 2018,
        historical_seasons   = [1994, 1998, 2002, 2006, 2010, 2014],
        form_cutoff_date     = "2018-06-14",   # WC 2018 opening match date
        form_window_months   = 36,
    ),
    TournamentConfig(
        name                = "World Cup 2022",
        test_season          = 2022,
        historical_seasons   = [1994, 1998, 2002, 2006, 2010, 2014, 2018],
        form_cutoff_date     = "2022-11-20",   # WC 2022 opening match date
        form_window_months   = 36,
    ),
]


# ---------------------------------------------------------------------------
# Per-match evaluation
# ---------------------------------------------------------------------------

@dataclass
class MatchEval:
    """One predicted match scored against its actual result."""
    home_team:      str
    away_team:      str
    home_score:      int
    away_score:      int
    actual_result:   str   # "HOME_WIN" | "DRAW" | "AWAY_WIN"
    p_home_win:      float
    p_draw:          float
    p_away_win:      float

    predicted_result: str   = field(init=False)
    correct:           bool  = field(init=False)
    log_loss:           float = field(init=False)
    brier_score:        float = field(init=False)
    prob_correct:        float = field(init=False)   # prob assigned to actual outcome

    def __post_init__(self):
        probs = {
            "HOME_WIN": self.p_home_win,
            "DRAW":     self.p_draw,
            "AWAY_WIN": self.p_away_win,
        }
        self.predicted_result = max(probs, key=probs.__getitem__)
        self.correct           = (self.predicted_result == self.actual_result)

        p_actual           = probs[self.actual_result]
        self.prob_correct    = p_actual
        self.log_loss         = -math.log(max(p_actual, LOG_LOSS_CLIP))

        y = {"HOME_WIN": [1,0,0], "DRAW": [0,1,0], "AWAY_WIN": [0,0,1]}[self.actual_result]
        p = [self.p_home_win, self.p_draw, self.p_away_win]
        self.brier_score = sum((pi - yi) ** 2 for pi, yi in zip(p, y)) / 3.0


def evaluate_match(
    stats:          me.TeamStats,
    home_team:       str,
    away_team:       str,
    home_score:      int,
    away_score:      int,
) -> MatchEval:
    """
    Predict one match via math_engine.predict_match() and score it against
    the actual result. The prediction engine itself is never modified —
    this only calls it and wraps the output for scoring.
    """
    pred = me.predict_match(stats, home_team, away_team)

    if home_score > away_score:
        actual = "HOME_WIN"
    elif away_score > home_score:
        actual = "AWAY_WIN"
    else:
        actual = "DRAW"

    return MatchEval(
        home_team      = pred.home_team,
        away_team      = pred.away_team,
        home_score     = home_score,
        away_score     = away_score,
        actual_result  = actual,
        p_home_win     = pred.home_win_prob,
        p_draw         = pred.draw_prob,
        p_away_win     = pred.away_win_prob,
    )


# ---------------------------------------------------------------------------
# Metrics — each one a small, focused, reusable function
# ---------------------------------------------------------------------------

def compute_accuracy(matches: list[MatchEval]) -> float:
    """Fraction of matches where the model's top pick matched the actual result."""
    if not matches:
        return 0.0
    return sum(1 for m in matches if m.correct) / len(matches)


def compute_brier_score(matches: list[MatchEval]) -> float:
    """Mean multi-class Brier score across all matches."""
    if not matches:
        return 0.0
    return sum(m.brier_score for m in matches) / len(matches)


def compute_log_loss(matches: list[MatchEval]) -> float:
    """Mean log loss across all matches."""
    if not matches:
        return 0.0
    return sum(m.log_loss for m in matches) / len(matches)


def compute_avg_prob_correct(matches: list[MatchEval]) -> float:
    """Average probability the model assigned to the ACTUAL outcome."""
    if not matches:
        return 0.0
    return sum(m.prob_correct for m in matches) / len(matches)


@dataclass
class ModelMetrics:
    """Bundled metrics for one model evaluated on one tournament."""
    model_label:       str
    n_matches:           int
    accuracy:             float
    brier_score:           float
    log_loss:              float
    avg_prob_correct:      float
    matches:               list[MatchEval] = field(default_factory=list, repr=False)


def _metrics_from_matches(label: str, matches: list[MatchEval]) -> ModelMetrics:
    return ModelMetrics(
        model_label        = label,
        n_matches           = len(matches),
        accuracy             = compute_accuracy(matches),
        brier_score           = compute_brier_score(matches),
        log_loss              = compute_log_loss(matches),
        avg_prob_correct       = compute_avg_prob_correct(matches),
        matches                = matches,
    )


# ---------------------------------------------------------------------------
# Database fetch — the matches being tested (never used for training)
# ---------------------------------------------------------------------------

def _fetch_test_matches(db_path: str, test_season: int) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT home_team_name, away_team_name, home_score, away_score
        FROM   historical_results
        WHERE  competition = 'WC'
          AND  season = ?
        ORDER  BY utc_date
        """,
        (test_season,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Tournament-level evaluation — one model, one tournament
# ---------------------------------------------------------------------------

def evaluate_tournament(
    stats:          me.TeamStats,
    test_matches:    list[dict],
    model_label:      str,
) -> ModelMetrics:
    """
    Evaluate one already-built TeamStats dict against one tournament's
    actual matches. Does not build stats itself — see evaluate_model()
    for that — so this function stays focused purely on scoring.
    """
    match_evals = [
        evaluate_match(
            stats,
            row["home_team_name"],
            row["away_team_name"],
            row["home_score"],
            row["away_score"],
        )
        for row in test_matches
    ]
    return _metrics_from_matches(model_label, match_evals)


# ---------------------------------------------------------------------------
# Model-level evaluation — builds stats AND evaluates, for one model type
# ---------------------------------------------------------------------------

def evaluate_model(
    db_path:          str,
    config:            TournamentConfig,
    model_type:         str,                      # "historical" | "form" | "hybrid"
    historical_weight:  Optional[float] = None,    # required if model_type == "hybrid"
    form_weight:         Optional[float] = None,    # required if model_type == "hybrid"
) -> ModelMetrics:
    """
    Build the requested TeamStats source with a leakage-safe cutoff for
    this tournament, then evaluate it. This is the single place that
    decides HOW each model type is built for backtesting purposes.

    model_type "historical" → load_team_stats(seasons=config.historical_seasons)
    model_type "form"        → load_form_stats(cutoff_date=config.form_cutoff_date, ...)
    model_type "hybrid"       → load_hybrid_stats(..., historical_weight=, form_weight=)

    See the module docstring's KNOWN LIMITATION note regarding the
    historical model's recency-decay anchor.
    """
    test_matches = _fetch_test_matches(db_path, config.test_season)
    if not test_matches:
        raise ValueError(
            f"No test matches found for {config.name} (season={config.test_season})."
        )

    if model_type == "historical":
        stats = me.load_team_stats(
            db_path = db_path,
            seasons  = config.historical_seasons,
        )
        label = "Historical"

    elif model_type == "form":
        stats = me.load_form_stats(
            db_path        = db_path,
            cutoff_date     = config.form_cutoff_date,
            window_months   = config.form_window_months,
        )
        label = "Recent Form"

    elif model_type == "hybrid":
        if historical_weight is None or form_weight is None:
            raise ValueError(
                "hybrid model_type requires historical_weight and form_weight"
            )
        stats = me.load_hybrid_stats(
            db_path             = db_path,
            historical_weight    = historical_weight,
            form_weight          = form_weight,
            cutoff_date           = config.form_cutoff_date,
            seasons               = config.historical_seasons,
            window_months         = config.form_window_months,
        )
        label = f"Hybrid {historical_weight:.0%}/{form_weight:.0%}"

    else:
        raise ValueError(f"Unknown model_type: {model_type!r}")

    return evaluate_tournament(stats, test_matches, label)


# ---------------------------------------------------------------------------
# Weight-grid evaluation — every hybrid ratio, for one tournament
# ---------------------------------------------------------------------------

def evaluate_weight_grid(
    db_path:      str,
    config:        TournamentConfig,
    weight_grid:    Optional[list[tuple[float, float]]] = None,
) -> list[ModelMetrics]:
    """
    Evaluate every (historical_weight, form_weight) pair in weight_grid
    for one tournament. weight_grid defaults to the module-level
    WEIGHT_GRID constant but can be overridden per call — nothing here
    is hardcoded into the function body itself.

    Includes the 100/0 and 0/100 endpoints, which are mathematically
    equivalent to the pure Historical and pure Form models respectively
    (useful as a sanity check that the hybrid blending math is correct —
    see the verification step in this milestone's testing).
    """
    grid = weight_grid if weight_grid is not None else WEIGHT_GRID
    results = []
    for hist_w, form_w in grid:
        metrics = evaluate_model(
            db_path             = db_path,
            config                = config,
            model_type             = "hybrid",
            historical_weight       = hist_w,
            form_weight              = form_w,
        )
        results.append(metrics)
    return results


# ---------------------------------------------------------------------------
# Full evaluation — every model type, every tournament
# ---------------------------------------------------------------------------

def run_full_evaluation(
    db_path:       str                        = DB_PATH,
    configs:        Optional[list[TournamentConfig]] = None,
    weight_grid:     Optional[list[tuple[float, float]]] = None,
) -> dict[str, list[ModelMetrics]]:
    """
    Run Historical, Recent Form, and the full Hybrid weight grid against
    every configured tournament.

    Returns
    -------
    dict mapping tournament name → list of ModelMetrics (Historical,
    Recent Form, then every Hybrid ratio in weight_grid order)
    """
    configs = configs if configs is not None else TOURNAMENT_CONFIGS
    all_results: dict[str, list[ModelMetrics]] = {}

    for config in configs:
        log.info(f"Evaluating {config.name} ...")
        tournament_results: list[ModelMetrics] = []

        tournament_results.append(
            evaluate_model(db_path, config, model_type="historical")
        )
        tournament_results.append(
            evaluate_model(db_path, config, model_type="form")
        )
        tournament_results.extend(
            evaluate_weight_grid(db_path, config, weight_grid=weight_grid)
        )

        all_results[config.name] = tournament_results
        log.info(f"  {config.name}: {len(tournament_results)} models evaluated")

    return all_results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _format_results_table(results: list[ModelMetrics]) -> str:
    """One tournament's results, sorted by best (lowest) Log Loss."""
    sorted_results = sorted(results, key=lambda m: m.log_loss)

    w = 64
    lines = [
        "─" * w,
        f"  {'Model':<22} {'Accuracy':>9}  {'Brier':>8}  {'LogLoss':>9}  {'AvgP✓':>7}",
        "─" * w,
    ]
    for m in sorted_results:
        lines.append(
            f"  {m.model_label:<22} {m.accuracy:>9.1%}  {m.brier_score:>8.4f}  "
            f"{m.log_loss:>9.4f}  {m.avg_prob_correct:>7.1%}"
        )
    lines.append("─" * w)
    return "\n".join(lines)


def print_tournament_report(tournament_name: str, results: list[ModelMetrics]) -> None:
    w = 64
    print("\n" + "=" * w)
    print(f"  {tournament_name}")
    print("=" * w)
    print(_format_results_table(results))


def print_overall_best(all_results: dict[str, list[ModelMetrics]]) -> None:
    """
    Aggregate every (tournament, model) pair across ALL tournaments and
    report the single best model by each metric, plus which weight ratio
    won overall (averaged across tournaments, hybrid models only).
    """
    flat: list[tuple[str, ModelMetrics]] = [
        (tname, m) for tname, results in all_results.items() for m in results
    ]

    best_accuracy = max(flat, key=lambda x: x[1].accuracy)
    best_brier     = min(flat, key=lambda x: x[1].brier_score)
    best_log_loss   = min(flat, key=lambda x: x[1].log_loss)

    # Best weight ratio: average log loss for each Hybrid ratio across all
    # tournaments it appeared in, then pick the lowest average. Historical
    # and Recent Form are excluded here since they're not a "ratio".
    ratio_scores: dict[str, list[float]] = {}
    for tname, m in flat:
        if m.model_label.startswith("Hybrid"):
            ratio_scores.setdefault(m.model_label, []).append(m.log_loss)

    best_ratio_label = None
    best_ratio_avg    = float("inf")
    for label, scores in ratio_scores.items():
        avg = sum(scores) / len(scores)
        if avg < best_ratio_avg:
            best_ratio_avg = avg
            best_ratio_label = label

    w = 64
    print("\n" + "=" * w)
    print("  Overall Best")
    print("=" * w)
    print(f"  Best Accuracy   {best_accuracy[1].accuracy:>8.1%}   "
          f"({best_accuracy[1].model_label}, {best_accuracy[0]})")
    print(f"  Best Brier      {best_brier[1].brier_score:>8.4f}   "
          f"({best_brier[1].model_label}, {best_brier[0]})")
    print(f"  Best LogLoss    {best_log_loss[1].log_loss:>8.4f}   "
          f"({best_log_loss[1].model_label}, {best_log_loss[0]})")
    if best_ratio_label:
        print(f"  Best Weight Ratio   {best_ratio_label}   "
              f"(avg LogLoss {best_ratio_avg:.4f} across all tournaments)")
    print("=" * w + "\n")


# ---------------------------------------------------------------------------
# CSV export — one row per (tournament, model) for further analysis
# ---------------------------------------------------------------------------

def write_summary_csv(
    all_results: dict[str, list[ModelMetrics]],
    path:          str = "backtest_summary.csv",
) -> None:
    fields = ["tournament", "model", "n_matches", "accuracy",
              "brier_score", "log_loss", "avg_prob_correct"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for tname, results in all_results.items():
            for m in results:
                writer.writerow({
                    "tournament":        tname,
                    "model":             m.model_label,
                    "n_matches":          m.n_matches,
                    "accuracy":           f"{m.accuracy:.4f}",
                    "brier_score":         f"{m.brier_score:.4f}",
                    "log_loss":            f"{m.log_loss:.4f}",
                    "avg_prob_correct":     f"{m.avg_prob_correct:.4f}",
                })
    log.info(f"Summary CSV written: {path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    log.info("Running full Milestone 4 evaluation (Historical / Form / Hybrid grid)")

    all_results = run_full_evaluation(db_path=DB_PATH)

    for tname, results in all_results.items():
        print_tournament_report(tname, results)

    print_overall_best(all_results)

    write_summary_csv(all_results)


if __name__ == "__main__":
    main()