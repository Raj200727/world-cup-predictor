# World Cup 2026 Predictor ⚽
![Python](https://img.shields.io/badge/Python-3.13-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Live-red)
![SQLite](https://img.shields.io/badge/SQLite-Database-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Tests](https://github.com/Raj200727/world-cup-predictor/actions/workflows/test.yml/badge.svg)

A match probability engine for the 2026 FIFA World Cup, built entirely in Python. It uses a Poisson distribution model trained on 92 years of World Cup history (1930–2022) to generate win/draw/loss probabilities, expected goals, and exact scoreline likelihoods for every fixture in the tournament.

**[Live app →](https://world-cup-predictor-wjww6fmrzy7nzefe8epety.streamlit.app)**

![App screenshot](docs/screenshots/dashboard.png.png)

---

## What it does

Pick any WC 2026 fixture from the dropdown and the app tells you:

- **Win probability** for each side and for a draw, shown as a stacked bar so you can read the split at a glance
- **Expected goals (xG)** — how many goals the model thinks each team will score on average
- **Top 8 most likely exact scorelines**, coloured by outcome and sorted by probability
- **Goal matrix heatmap** — the full joint probability table for every 0–5 × 0–5 scoreline combination
- **Team profiles** — attack strength, defense strength, historical win/draw/loss rates, and sample size for each team

The model was backtested on WC 2018 and WC 2022 (training on all prior tournaments, testing on the target year) and scores **59.3% accuracy** and a **Brier score of 0.201** on the 2022 World Cup — competitive with bookmaker-implied odds after removing the vig.

---

## How the model works

This is a **Poisson-based attack/defense strength model**, sometimes called the Dixon-Coles-style approach (though without the full Dixon-Coles draw correction yet — that's on the v2 roadmap).

**Step 1 — Team strength calculation**

For every team in the training set, the model computes:

```
attack_strength  = team's weighted avg goals scored   ÷ global avg goals scored
defense_strength = team's weighted avg goals conceded ÷ global avg goals conceded
```

Matches are weighted by recency using exponential decay with a 16-year half-life, so WC 2022 contributes roughly 3× more signal than WC 1994. Extra-time and penalty results are excluded from training — a 0–0 that goes to penalties doesn't reflect the same attacking/defensive quality as a 0–0 in regulation.

**Step 2 — Expected goals**

For a given fixture:

```
λ_home = global_avg × home_attack × away_defense
λ_away = global_avg × away_attack × home_defense
```

No home advantage multiplier is applied — every World Cup match is at a neutral venue.

**Step 3 — Scoreline matrix**

Using `scipy.stats.poisson.pmf`, the model builds a 9×9 matrix where each cell `[i][j]` is `P(home scores i) × P(away scores j)`. Goals are treated as independent Poisson events.

**Step 4 — Outcome probabilities**

Sum all cells where `i > j` → home win. `i == j` → draw. `i < j` → away win. Normalise to account for matrix truncation at 8 goals.

**Known limitations (see v2 roadmap below):**
- Draws are slightly underestimated because the independent-goals assumption misses the real-world tactical correlation (teams that go ahead tend to drop tempo)
- Teams with very few historical appearances (South Africa, Canada, Qatar) fall back to the global average rather than team-specific ratings
- No Elo integration yet — head-to-head form and recent tournament performance aren't currently factored in

---

## Backtest results

| Test season | Matches | Accuracy | Log Loss | Brier Score |
|-------------|---------|----------|----------|-------------|
| WC 2022     | 59      | 59.3%    | 1.044    | 0.201       |
| WC 2018     | 64      | 53.1%    | 1.044    | 0.206       |

**Calibration (WC 2022):**

| Model confidence | Actual win rate | Delta |
|-----------------|-----------------|-------|
| 50–60%          | 50.0%           | −6.7% |
| 60–70%          | 60.0%           | −4.1% |
| 70–80%          | 71.4%           | −1.6% |
| 80–90%          | 33.3%           | −51%  |

The model is well-calibrated up to 80% confidence. The 80–90% bucket shows overconfidence — it had 3 matches in that range and called 2 of them wrong, including Argentina vs Saudi Arabia and Brazil vs Cameroon. Small sample, but worth noting.

**Baseline comparison (WC 2022):**

| Model                    | Log Loss | Brier  |
|--------------------------|----------|--------|
| Poisson (this model)     | 1.044    | 0.201  |
| Uniform (33/33/33)       | 1.099    | 0.222  |
| Home-favoured (40/30/30) | 1.063    | 0.214  |

The model beats every naive baseline on both tournaments.

---

## Project structure

```
world-cup-predictor/
│
├── app.py                  # Streamlit frontend — run this
├── math_engine.py          # Poisson model — all prediction logic lives here
├── backtest.py             # Out-of-sample validation framework
├── ingest_api.py           # Pulls WC 2026 fixtures from football-data.org
├── ingest_csv.py           # Loads WC 1930–2022 history from Kaggle CSVs
│
├── data/
│   ├── WorldCupMatches.csv # Evangower dataset (WC 1930–2018)
│   └── Matches.csv         # Swaptr dataset (WC 2022)
│
├── predictor.db            # SQLite database (generated — not committed to git)
├── backtest_results.csv    # Backtest output (generated)
│
├── requirements.txt        # Python dependencies
└── docs/
    └── screenshot.png      # App screenshot for README
```

---

## Setup

### Requirements

- Python 3.10+
- A free [football-data.org](https://www.football-data.org/) API key

### Install dependencies

```bash
pip install -r requirements.txt
```

### Build the database

**Step 1 — Pull WC 2026 fixtures from the API:**

```bash
export FOOTBALL_DATA_API_KEY="your_key_here"
python ingest_api.py --mode upcoming
```

**Step 2 — Download historical match data from Kaggle (free account required):**

- [evangower/fifa-world-cup](https://www.kaggle.com/datasets/evangower/fifa-world-cup) → save as `data/WorldCupMatches.csv`
- [swaptr/fifa-world-cup-2022-match-data](https://www.kaggle.com/datasets/swaptr/fifa-world-cup-2022-match-data) → save as `data/Matches.csv`

**Step 3 — Load historical data into the database:**

```bash
python ingest_csv.py
```

You should see:
```
WC 1930-2018: 900 inserted
WC 2022:       59 inserted
Total:        959 rows
```

### Run the app

```bash
streamlit run app.py
```

### Run the backtest

```bash
# Train on 1930-2018, test on 2022 (default)
python backtest.py

# Custom split
python backtest.py --test-season 2018
```

---

## Deploying to Streamlit Cloud

1. Push your repo to GitHub (make sure `predictor.db` is committed — see note below)
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo
3. Set the main file to `app.py`
4. Add your API key as a secret: `FOOTBALL_DATA_API_KEY = "your_key"`

> **Note on the database file:** `predictor.db` needs to be committed to the repo for Streamlit Cloud to have access to it, since the cloud environment doesn't have local file persistence. The file is around 300KB so this is fine for now. For a production deployment you'd swap this for a hosted database.

---

## Requirements

```
streamlit>=1.28.0
plotly>=5.17.0
scipy>=1.11.0
numpy>=1.24.0
pandas>=2.0.0
requests>=2.31.0
sqlalchemy>=2.0.0
```

---

## v2 Roadmap

The model is functional and beats naive baselines, but there are concrete improvements planned:

### Quick wins (a few hours each)

**Bayesian smoothing for small samples**
Teams like South Africa, Canada, and Qatar have very few historical WC appearances and currently fall back to the global average. Bayesian smoothing would blend their sparse data with the global prior in proportion to sample size, giving a better estimate than a hard cutoff at 3 matches:

```python
# Instead of: if matches < 3: use global average
# Do: blend team data with global prior
k = 10  # prior strength (tune via backtest)
smoothed_attack = (observed_goals + k * global_avg) / (matches + k)
```

**Draw calibration correction**
The model predicts 0% accuracy on draws in backtesting. The standard fix is a Dixon-Coles correction factor applied to the 0–0 and 1–0/0–1 cells of the scoreline matrix. Specifically:

```python
# Correction factor for low-scoring scorelines
def tau(x, y, lambda_h, lambda_a, rho):
    if x == 0 and y == 0: return 1 - lambda_h * lambda_a * rho
    if x == 1 and y == 0: return 1 + lambda_a * rho
    if x == 0 and y == 1: return 1 + lambda_h * rho
    if x == 1 and y == 1: return 1 - rho
    return 1.0
```
Estimate `rho` from historical draw rates. Expected improvement: draw accuracy from 0% to ~20–25%.

**Half-life tuning**
Run the backtest across half-lives of 8, 12, 16, and 20 years and pick whichever minimises average Brier score across both test seasons. One-liner to test:

```bash
python backtest.py --half-life 8
python backtest.py --half-life 12
# etc.
```

### Medium effort (a day each)

**Tournament simulator**
Simulate the entire WC 2026 bracket using Monte Carlo. The `simulate_match()` function in `math_engine.py` is already built for this. The remaining work is group-stage ranking logic (points → goal difference → goals scored → head-to-head) and knockout bracket generation. With 10,000 simulations you get stable champion probability estimates.

**Team Analysis page**
A second Streamlit page showing attack/defense rankings for all 48 WC 2026 teams, historical win rates, and a scatter plot of attack vs defense strength. Most of the data is already computed by `load_team_stats()`.

**Enhanced validation page**
Add calibration curves and reliability diagrams to the app using the existing `backtest.py` output. Lets a visitor understand the model's confidence properties visually.

### Higher effort (several days)

**Elo rating integration**
Elo ratings capture recent form in a way that historical WC data alone can't — a team that won the World Cup last cycle should be treated differently from a team that hasn't qualified in 20 years. The cleanest integration is as a prior that modulates expected goals before the Poisson calculation:

```python
elo_factor = (team_elo / opponent_elo) ** 0.3  # tune the exponent
lambda_adj = lambda_base * elo_factor
```

FIFA publishes official rankings; the [clubelo.com](http://clubelo.com) API provides historical Elo data for free.

**Rolling out-of-sample validation**
Instead of a single train/test split, run the backtest for every WC from 2002 onwards (training on all prior data each time) and plot accuracy, log-loss, and Brier score as a time series. Shows whether the model is improving as it sees more data, or whether the recent tactical evolution of football is making older data less useful.

---

## Portfolio notes

If you're sharing this as a portfolio project, the things worth highlighting are:

1. **The full pipeline** — from raw CSV/API ingestion through a SQLite store, a modular prediction engine, an out-of-sample backtest framework, and a deployed Streamlit UI. Most toy ML projects show one piece; this shows all of them connected.

2. **The backtest methodology** — training strictly on data before the test season, never leaking future information, and comparing against baselines rather than just reporting accuracy in isolation. This is what separates a genuine evaluation from a number that looks good on a slide.

3. **The calibration analysis** — showing that the model is well-calibrated in the 50–80% range and identifying where it breaks down (the 80–90% overconfidence bucket) is more honest and more impressive than just claiming "59.3% accuracy."

4. **The architecture decisions** — the math engine is stateless and functional so every layer can import it cleanly. The backtest framework takes a config object and returns a report object, making it reusable for any train/test split. These aren't accidental — they're design choices worth talking about in an interview.

---

## Data sources

- **WC 1930–2018 match results:** [evangower/fifa-world-cup](https://www.kaggle.com/datasets/evangower/fifa-world-cup) on Kaggle
- **WC 2022 match results:** [swaptr/fifa-world-cup-2022-match-data](https://www.kaggle.com/datasets/swaptr/fifa-world-cup-2022-match-data) on Kaggle
- **WC 2026 fixture schedule:** [football-data.org](https://www.football-data.org/) free tier API

---

## License

MIT
