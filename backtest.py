"""
backtest.py — World Cup Predictor
===================================
Out-of-sample backtesting framework for the Poisson prediction model.

Default test: Train on WC 1930–2018, evaluate on WC 2022.
The test season is ALWAYS excluded from training data — no data leakage.

Usage
-----
    # Default: train 1930-2018, test 2022
    py backtest.py

    # Custom split
    py backtest.py --train-seasons 1994 1998 2002 2006 2010 2014 --test-season 2018

    # Include extra-time matches in training data
    py backtest.py --include-et

Output
------
    - Console report  (accuracy, log-loss, Brier, calibration, best/worst/upsets)
    - backtest_results.csv  (one row per match with predicted and actual)

Reusability
-----------
Import run_backtest() directly for future automated testing:

    from backtest import run_backtest, BacktestConfig
    cfg = BacktestConfig(train_seasons=[...], test_season=2026)
    report = run_backtest(cfg)
    print(report.summary())
"""

from __future__ import annotations

import argparse
import csv
import logging
import math
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

# ---------------------------------------------------------------------------
# Import math engine — zero duplication of Poisson logic
# ---------------------------------------------------------------------------
try:
    import math_engine as me
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).parent))
    import math_engine as me

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backtest")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DB_PATH         = "predictor.db"
CSV_OUTPUT_PATH = "backtest_results.csv"
LOG_LOSS_CLIP   = 1e-9   # clip near-zero probs before log() to avoid -inf

CALIBRATION_BUCKETS = [
    (0.50, 0.60),
    (0.60, 0.70),
    (0.70, 0.80),
    (0.80, 0.90),
    (0.90, 1.00),
]

# ---------------------------------------------------------------------------
# Configuration — makes the framework reusable for any season split
# ---------------------------------------------------------------------------

@dataclass
class BacktestConfig:
    """
    Defines one complete backtest run.
    Pass different configs to run_backtest() to test any train/test split.
    """
    db_path:        str       = DB_PATH
    test_season:    int       = 2022
    train_seasons:  list[int] = field(default_factory=lambda: list(range(1930, 2022, 4)))
    exclude_et:     bool      = True
    csv_output:     str       = CSV_OUTPUT_PATH
    top_n_best:     int       = 5
    top_n_worst:    int       = 5
    top_n_upsets:   int       = 5

    def __post_init__(self):
        # Hard guarantee: test season is never in training data
        self.train_seasons = [s for s in self.train_seasons if s != self.test_season]

    @property
    def label(self) -> str:
        min_t = min(self.train_seasons)
        max_t = max(self.train_seasons)
        return f"Train {min_t}–{max_t}  |  Test WC {self.test_season}"


# ---------------------------------------------------------------------------
# Per-match result
# ---------------------------------------------------------------------------

@dataclass
class MatchBacktestRow:
    """One predicted match vs actual outcome, with all derived metrics."""
    match_id:      int
    utc_date:      str
    home_team:     str
    away_team:     str
    home_score:    int
    away_score:    int
    actual_result: str   # "HOME_WIN" | "DRAW" | "AWAY_WIN"
    stage:         str

    p_home_win:    float
    p_draw:        float
    p_away_win:    float
    lambda_home:   float
    lambda_away:   float

    # Derived — set in __post_init__
    predicted_result: str   = field(init=False)
    correct:          bool  = field(init=False)
    log_loss:         float = field(init=False)
    brier_score:      float = field(init=False)
    favourite_prob:   float = field(init=False)
    was_upset:        bool  = field(init=False)

    def __post_init__(self):
        probs = {
            "HOME_WIN": self.p_home_win,
            "DRAW":     self.p_draw,
            "AWAY_WIN": self.p_away_win,
        }
        self.predicted_result = max(probs, key=probs.__getitem__)
        self.correct          = (self.predicted_result == self.actual_result)

        # Log loss: -log(p assigned to actual outcome)
        p_actual     = probs[self.actual_result]
        self.log_loss = -math.log(max(p_actual, LOG_LOSS_CLIP))

        # Multi-class Brier score: mean squared error across all 3 outcomes
        y = {"HOME_WIN": [1,0,0], "DRAW": [0,1,0], "AWAY_WIN": [0,0,1]}[self.actual_result]
        p = [self.p_home_win, self.p_draw, self.p_away_win]
        self.brier_score = sum((pi - yi)**2 for pi, yi in zip(p, y)) / 3.0

        # Favourite = the model's top pick and its probability
        self.favourite_prob = max(self.p_home_win, self.p_draw, self.p_away_win)

        # Upset: model was confident (≥65%) but wrong
        self.was_upset = (self.favourite_prob >= 0.65 and not self.correct)

    @property
    def score_str(self) -> str:
        return f"{self.home_score}–{self.away_score}"

    @property
    def result_str(self) -> str:
        return {
            "HOME_WIN": f"{self.home_team} win",
            "DRAW":     "Draw",
            "AWAY_WIN": f"{self.away_team} win",
        }[self.actual_result]

    @property
    def predicted_str(self) -> str:
        return {
            "HOME_WIN": f"{self.home_team} win",
            "DRAW":     "Draw",
            "AWAY_WIN": f"{self.away_team} win",
        }[self.predicted_result]


# ---------------------------------------------------------------------------
# Aggregate report
# ---------------------------------------------------------------------------

@dataclass
class BacktestReport:
    """All metrics, listings, and calibration for one backtest run."""
    config:  BacktestConfig
    rows:    list[MatchBacktestRow]

    # Aggregate metrics — populated by _compute()
    n_matches:    int   = field(init=False)
    n_correct:    int   = field(init=False)
    accuracy:     float = field(init=False)
    avg_log_loss: float = field(init=False)
    avg_brier:    float = field(init=False)

    n_home_wins:  int   = field(init=False)
    n_draws:      int   = field(init=False)
    n_away_wins:  int   = field(init=False)
    acc_home_win: float = field(init=False)
    acc_draw:     float = field(init=False)
    acc_away_win: float = field(init=False)

    # { bucket_label: (predicted_avg, actual_rate, count) }
    calibration:  dict  = field(init=False)

    best:   list[MatchBacktestRow] = field(init=False)
    worst:  list[MatchBacktestRow] = field(init=False)
    upsets: list[MatchBacktestRow] = field(init=False)

    def __post_init__(self):
        self._compute()

    def _compute(self):
        rows = self.rows
        n    = len(rows)
        self.n_matches    = n
        self.n_correct    = sum(1 for r in rows if r.correct)
        self.accuracy     = self.n_correct / n if n else 0.0
        self.avg_log_loss = sum(r.log_loss    for r in rows) / n if n else 0.0
        self.avg_brier    = sum(r.brier_score for r in rows) / n if n else 0.0

        hw = [r for r in rows if r.actual_result == "HOME_WIN"]
        dr = [r for r in rows if r.actual_result == "DRAW"]
        aw = [r for r in rows if r.actual_result == "AWAY_WIN"]
        self.n_home_wins  = len(hw)
        self.n_draws      = len(dr)
        self.n_away_wins  = len(aw)
        self.acc_home_win = sum(1 for r in hw if r.correct) / len(hw) if hw else 0.0
        self.acc_draw     = sum(1 for r in dr if r.correct) / len(dr) if dr else 0.0
        self.acc_away_win = sum(1 for r in aw if r.correct) / len(aw) if aw else 0.0

        self.calibration = _compute_calibration(rows)

        cfg         = self.config
        by_ll_asc   = sorted(rows, key=lambda r: r.log_loss)
        by_ll_desc  = sorted(rows, key=lambda r: r.log_loss, reverse=True)

        self.best   = by_ll_asc[:cfg.top_n_best]
        self.worst  = by_ll_desc[:cfg.top_n_worst]
        self.upsets = sorted(
            [r for r in rows if r.was_upset],
            key=lambda r: r.favourite_prob, reverse=True,
        )[:cfg.top_n_upsets]

    # ------------------------------------------------------------------
    def summary(self) -> str:
        W   = 58
        sep = "─" * W
        thk = "═" * W
        L   = []
        a   = L.append

        a(f"\n{thk}")
        a(f"  WORLD CUP PREDICTOR — Backtest Report")
        a(f"  {self.config.label}")
        a(thk)

        # Core metrics
        a(f"\n  {'Matches tested:':<30} {self.n_matches:>6}")
        a(f"  {'Correct predictions:':<30} {self.n_correct:>6}  ({self.accuracy:.1%})")
        a(f"  {'Log Loss:':<30} {self.avg_log_loss:>9.4f}")
        a(f"  {'Brier Score:':<30} {self.avg_brier:>9.4f}  {_brier_ctx(self.avg_brier)}")

        # Outcome breakdown
        a(f"\n{sep}")
        a(f"  {'Outcome':<14} {'Count':>6}  {'Accuracy':>9}")
        a(sep)
        a(f"  {'Home Win':<14} {self.n_home_wins:>6}  {self.acc_home_win:>9.1%}")
        a(f"  {'Draw':<14} {self.n_draws:>6}  {self.acc_draw:>9.1%}")
        a(f"  {'Away Win':<14} {self.n_away_wins:>6}  {self.acc_away_win:>9.1%}")
        a(sep)

        # Calibration
        a(f"\n  Calibration — when model predicts X% for favourite, does it win X% of the time?")
        a(sep)
        a(f"  {'Predicted range':<16} {'N':>5}  {'Pred avg':>9}  {'Actual rate':>12}  {'Delta':>7}")
        a(sep)
        for label, (pred_avg, actual_rate, count) in sorted(self.calibration.items()):
            if count == 0:
                a(f"  {label:<16} {'—':>5}")
                continue
            delta = actual_rate - pred_avg
            sign  = "+" if delta >= 0 else ""
            a(f"  {label:<16} {count:>5}  {pred_avg:>9.1%}  {actual_rate:>12.1%}  {sign}{delta:>6.1%}")
        a(sep)

        # Best predictions (most confident & correct → low log-loss)
        a(f"\n  Best predictions  (model most confident & correct)")
        a(sep)
        for r in self.best:
            a(f"  {r.home_team:<22} {r.score_str}  {r.away_team:<22}  LL={r.log_loss:.3f}")
        a(sep)

        # Worst predictions (most confidently wrong → high log-loss)
        a(f"\n  Worst predictions  (model most confidently wrong)")
        a(sep)
        for r in self.worst:
            a(f"  {r.home_team:<22} {r.score_str}  {r.away_team:<22}  "
              f"LL={r.log_loss:.3f}  (predicted: {r.predicted_str})")
        a(sep)

        # Upsets
        if self.upsets:
            a(f"\n  Biggest upsets  (model ≥65% confident — but wrong)")
            a(sep)
            for r in self.upsets:
                a(f"  {r.home_team:<22} {r.score_str}  {r.away_team:<22}  "
                  f"model: {r.predicted_str} @ {r.favourite_prob:.0%}")
            a(sep)
        else:
            a(f"\n  No upsets found (model never ≥65% confident on a wrong call).")

        a(f"\n{thk}\n")
        return "\n".join(L)


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

def _compute_calibration(rows: list[MatchBacktestRow]) -> dict:
    """
    For each probability bucket, collect all matches where the model's
    top-pick fell in that range, then measure the actual win rate.
    """
    results = {}

    for lo, hi in CALIBRATION_BUCKETS:
        label = f"{lo*100:.0f}–{hi*100:.0f}%"
        bucket = []

        for r in rows:
            candidates = [("HOME_WIN", r.p_home_win),
                          ("DRAW",     r.p_draw),
                          ("AWAY_WIN", r.p_away_win)]
            fav_outcome, fav_prob = max(candidates, key=lambda x: x[1])

            in_bucket = (lo <= fav_prob < hi) if hi < 1.0 else (lo <= fav_prob <= hi)
            if in_bucket:
                bucket.append((fav_outcome, fav_prob, r.actual_result))

        count = len(bucket)
        if count == 0:
            results[label] = (0.0, 0.0, 0)
        else:
            pred_avg    = sum(p for _, p, _ in bucket) / count
            actual_wins = sum(1 for fav, _, actual in bucket if fav == actual)
            results[label] = (pred_avg, actual_wins / count, count)

    return results


def _brier_ctx(brier: float) -> str:
    if brier < 0.18: return "(excellent — better than typical bookmaker)"
    if brier < 0.22: return "(good — competitive with market odds)"
    if brier < 0.26: return "(fair — reasonable for a base model)"
    if brier < 0.30: return "(below average)"
    return "(poor — baseline uniform scores ~0.33)"


# ---------------------------------------------------------------------------
# Database fetch
# ---------------------------------------------------------------------------

def _fetch_test_matches(db_path: str, test_season: int) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id AS match_id, utc_date, home_team_name, away_team_name,
               home_score, away_score, winner, stage, extra_time, penalties
        FROM   historical_results
        WHERE  competition = 'WC'
          AND  season = ?
        ORDER  BY utc_date
        """,
        (test_season,),
    ).fetchall()
    conn.close()
    log.info(f"Fetched {len(rows)} test matches for WC {test_season}")
    return [dict(r) for r in rows]


def _actual_result(row: dict) -> str:
    winner = (row.get("winner") or "").strip()
    if winner == "HOME_TEAM": return "HOME_WIN"
    if winner == "AWAY_TEAM": return "AWAY_WIN"
    if winner == "DRAW":      return "DRAW"
    hs, aws = row.get("home_score", 0), row.get("away_score", 0)
    if hs > aws: return "HOME_WIN"
    if aws > hs: return "AWAY_WIN"
    return "DRAW"


# ---------------------------------------------------------------------------
# Core runner — the only function future code needs to call
# ---------------------------------------------------------------------------

def run_backtest(config: BacktestConfig) -> BacktestReport:
    """
    Run a complete out-of-sample backtest.

    Steps
    -----
    1. Build training stats (config.train_seasons — test season excluded)
    2. Fetch test matches from DB
    3. Predict every match via math_engine.predict_match()
    4. Compute all metrics inside BacktestReport
    5. Write backtest_results.csv

    Returns
    -------
    BacktestReport — fully computed, ready to print or inspect programmatically
    """
    log.info(f"Backtest: {config.label}")

    # 1. Training stats
    stats = me.load_team_stats(
        db_path            = config.db_path,
        seasons            = config.train_seasons,
        exclude_extra_time = config.exclude_et,
    )
    log.info(f"  {len(me.available_teams(stats))} teams in training set")

    # 2. Test matches
    if not Path(config.db_path).exists():
        raise FileNotFoundError(f"DB not found: {config.db_path}")
    test_rows = _fetch_test_matches(config.db_path, config.test_season)
    if not test_rows:
        raise ValueError(f"No matches found for WC {config.test_season} — run ingest first")

    # 3. Predict
    bt_rows: list[MatchBacktestRow] = []
    skipped = 0

    for row in test_rows:
        home = row["home_team_name"]
        away = row["away_team_name"]
        try:
            pred = me.predict_match(stats, home, away)
        except Exception as exc:
            log.warning(f"  Skipping {home} vs {away}: {exc}")
            skipped += 1
            continue

        bt_rows.append(MatchBacktestRow(
            match_id      = row["match_id"],
            utc_date      = str(row["utc_date"]),
            home_team     = pred.home_team,
            away_team     = pred.away_team,
            home_score    = row["home_score"],
            away_score    = row["away_score"],
            actual_result = _actual_result(row),
            stage         = row.get("stage") or "",
            p_home_win    = pred.home_win_prob,
            p_draw        = pred.draw_prob,
            p_away_win    = pred.away_win_prob,
            lambda_home   = pred.lambda_home,
            lambda_away   = pred.lambda_away,
        ))

    if skipped:
        log.warning(f"  {skipped} matches skipped")
    log.info(f"  Predicted {len(bt_rows)} matches")

    # 4. Build report (metrics computed inside __post_init__)
    report = BacktestReport(config=config, rows=bt_rows)

    # 5. Write CSV
    _write_csv(bt_rows, config.csv_output)

    return report


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def _write_csv(rows: list[MatchBacktestRow], path: str) -> None:
    fields = [
        "date", "stage", "home_team", "away_team",
        "home_score", "away_score",
        "actual_result", "predicted_result", "correct",
        "p_home_win", "p_draw", "p_away_win",
        "lambda_home", "lambda_away",
        "log_loss", "brier_score", "favourite_prob", "was_upset",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({
                "date":             r.utc_date,
                "stage":            r.stage,
                "home_team":        r.home_team,
                "away_team":        r.away_team,
                "home_score":       r.home_score,
                "away_score":       r.away_score,
                "actual_result":    r.actual_result,
                "predicted_result": r.predicted_result,
                "correct":          r.correct,
                "p_home_win":       f"{r.p_home_win:.4f}",
                "p_draw":           f"{r.p_draw:.4f}",
                "p_away_win":       f"{r.p_away_win:.4f}",
                "lambda_home":      f"{r.lambda_home:.4f}",
                "lambda_away":      f"{r.lambda_away:.4f}",
                "log_loss":         f"{r.log_loss:.4f}",
                "brier_score":      f"{r.brier_score:.4f}",
                "favourite_prob":   f"{r.favourite_prob:.4f}",
                "was_upset":        r.was_upset,
            })
    log.info(f"  CSV → {path}  ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# Supplementary analyses (importable by future tools / app.py)
# ---------------------------------------------------------------------------

def stage_breakdown(report: BacktestReport) -> str:
    """Accuracy and Brier score broken down by tournament stage."""
    stage_data: dict[str, list] = defaultdict(list)
    for r in report.rows:
        stage_data[r.stage or "UNKNOWN"].append(r)

    W   = 58
    sep = "─" * W
    L   = [f"\n  Stage breakdown", sep,
           f"  {'Stage':<22} {'N':>4}  {'Accuracy':>9}  {'Brier':>8}",  sep]
    for stage in sorted(stage_data):
        rows = stage_data[stage]
        n    = len(rows)
        acc  = sum(1 for r in rows if r.correct) / n
        b    = sum(r.brier_score for r in rows) / n
        L.append(f"  {stage:<22} {n:>4}  {acc:>9.1%}  {b:>8.4f}")
    L.append(sep)
    return "\n".join(L)


def team_performance(report: BacktestReport) -> str:
    """Per-team accuracy — shows which teams the model struggled with most."""
    td: dict[str, dict] = defaultdict(lambda: {"n": 0, "correct": 0, "ll": 0.0})
    for r in report.rows:
        for team in [r.home_team, r.away_team]:
            td[team]["n"]       += 1
            td[team]["correct"] += int(r.correct)
            td[team]["ll"]      += r.log_loss

    W   = 58
    sep = "─" * W
    L   = [f"\n  Per-team accuracy", sep,
           f"  {'Team':<24} {'GP':>3}  {'Accuracy':>9}  {'Avg LL':>8}", sep]
    for team, d in sorted(td.items(), key=lambda x: -x[1]["n"]):
        acc    = d["correct"] / d["n"]
        avg_ll = d["ll"] / d["n"]
        L.append(f"  {team:<24} {d['n']:>3}  {acc:>9.1%}  {avg_ll:>8.4f}")
    L.append(sep)
    return "\n".join(L)


def compare_to_baselines(report: BacktestReport) -> str:
    """
    Compare model metrics against three naive baselines:
      - Uniform:       33.3% / 33.3% / 33.3%
      - Home-favoured: 40%   / 30%   / 30%
      - Oracle freq:   actual outcome frequencies in the test set
    """
    n    = report.n_matches
    rows = report.rows

    def metrics(ph, pd, pa):
        ll = sum(-math.log(max({"HOME_WIN":ph,"DRAW":pd,"AWAY_WIN":pa}[r.actual_result],
                               LOG_LOSS_CLIP)) for r in rows) / n
        y_map = {"HOME_WIN":[1,0,0],"DRAW":[0,1,0],"AWAY_WIN":[0,0,1]}
        br = sum(sum((p-y)**2 for p,y in zip([ph,pd,pa], y_map[r.actual_result]))/3
                 for r in rows) / n
        return ll, br

    hw_r = report.n_home_wins / n
    dr_r = report.n_draws     / n
    aw_r = report.n_away_wins / n

    cases = [
        ("Poisson model",           report.avg_log_loss, report.avg_brier),
        ("Uniform (33/33/33)",       *metrics(1/3, 1/3, 1/3)),
        ("Home-favoured (40/30/30)", *metrics(0.40, 0.30, 0.30)),
        ("Oracle freq",              *metrics(hw_r, dr_r, aw_r)),
    ]

    W   = 62
    sep = "─" * W
    L   = [f"\n  Comparison to baselines", sep,
           f"  {'Model / Baseline':<28} {'Log Loss':>10}  {'Brier':>8}  {'LL delta':>10}", sep]

    base_ll = cases[0][1]
    for name, ll, br in cases:
        delta = ll - base_ll
        sign  = "+" if delta > 0 else ""
        flag  = "◀ this model" if name.startswith("Poisson") else ""
        L.append(f"  {name:<28} {ll:>10.4f}  {br:>8.4f}  {sign}{delta:>9.4f}  {flag}")
    L.append(sep)
    return "\n".join(L)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Backtest the World Cup Poisson model out-of-sample"
    )
    p.add_argument("--db",            default=DB_PATH,         help="Path to predictor.db")
    p.add_argument("--test-season",   type=int, default=2022,  help="Season to test (default: 2022)")
    p.add_argument("--train-seasons", type=int, nargs="+",     help="Seasons to train on")
    p.add_argument("--include-et",    action="store_true",     help="Include extra-time matches in training")
    p.add_argument("--csv",           default=CSV_OUTPUT_PATH, help="Output CSV path")
    p.add_argument("--no-stage",      action="store_true",     help="Skip stage breakdown")
    p.add_argument("--no-teams",      action="store_true",     help="Skip per-team breakdown")
    p.add_argument("--debug",         action="store_true",     help="Verbose logging")
    return p.parse_args()


def main():
    args = _parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    test_season   = args.test_season
    train_seasons = args.train_seasons or list(range(1930, test_season, 4))

    config = BacktestConfig(
        db_path       = args.db,
        test_season   = test_season,
        train_seasons = train_seasons,
        exclude_et    = not args.include_et,
        csv_output    = args.csv,
    )

    report = run_backtest(config)

    print(report.summary())

    if not args.no_stage:
        print(stage_breakdown(report))

    print(compare_to_baselines(report))

    if not args.no_teams:
        print(team_performance(report))

    print(f"\n  Output CSV: {args.csv}\n")


if __name__ == "__main__":
    main()