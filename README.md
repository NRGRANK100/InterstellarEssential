# Interstellar Essential — Self-Optimizing NinjaTrader 8 Pipeline

A self-optimizing automated trading pipeline for **NinjaTrader 8**. A weekly
Python job searches a large parameter space across ten strategies, picks the
best performer, and hands optimized parameters to a live NinjaScript strategy
through a shared file — with a news/risk layer and a reporting bot on top.

The system is built in four parts:

| # | Module | Language | Status |
|---|--------|----------|--------|
| 1 | **Sunday Optimizer** — backtests ~500k parameter combos, walk-forward, picks champion | Python | ✅ implemented |
| 2 | **Generator** — Jinja2 fills a NinjaScript C# template + writes the shared param file | Python / C# | 🔜 scaffolded |
| 3 | **Risk Layer** — high-impact news + drawdown guard, halves position size | Python / C# | 🔜 scaffolded |
| 4 | **Monitoring** — Discord/Telegram bot: daily PnL, win rate, weekly "Strategy of the Week", execution audit | Python | 🔜 scaffolded |

---

## 1. Python environment setup

```bash
# Python 3.11+ recommended
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# secrets / config
cp .env.example .env               # then fill in API keys & the NT param path
```

Key dependencies (see `requirements.txt`): `numpy`, `pandas`, `optuna`,
`scipy`, `yfinance`, `Jinja2`, plus `discord.py` **or** `python-telegram-bot`
for the reporting module.

---

## 2. Module 1 — the Sunday Optimizer  ✅

> *"Backtest 500,000 parameter combinations across 10 strategies, evaluate the
> last 30 days, and select the best strategy using Profit Factor × (1 − Max
> Drawdown). Vectorized backtesting + multiprocessing, walk-forward analysis to
> reduce overfitting."*

```
src/optimizer/
├── data.py              # yfinance + NinjaTrader-CSV loaders -> canonical OHLCV
├── strategies.py        # 10 vectorized strategies, each with its search space
├── backtest.py          # vectorized backtester; score = PF × (1 − MaxDD)
├── walk_forward.py      # expanding-window WF scoring (anti-overfit objective)
└── sunday_optimizer.py  # Optuna studies, multiprocessing pool, JSON output
```

**Run it:**

```bash
# yfinance data (free, intraday limited to ~60 days of history)
python -m src.optimizer.sunday_optimizer \
    --source yfinance --symbol SPY --interval 5m --period 60d \
    --total-trials 500000 --eval-days 30 \
    --out output/active_params.json

# …or NinjaTrader-exported bars
python -m src.optimizer.sunday_optimizer \
    --source ninjatrader --csv-path data/ES_5min.csv \
    --total-trials 500000 --out output/active_params.json
```

**How it hits the requirements**

- **500k combinations / 10 strategies** — the trial budget is split evenly
  (~50k trials each). Optuna's **TPE sampler + median pruner** explores far
  more efficiently than a blind grid of the same size.
- **Speed** — backtesting is fully **vectorized** (numpy/pandas, no per-bar
  Python loop), and the ten strategy studies run **in parallel** across CPU
  cores via `ProcessPoolExecutor`.
- **Objective** — `score = profit_factor × (1 − max_drawdown)`, computed in
  `backtest.py` and maximized by Optuna.
- **Last 30 days** — `--eval-days 30` trims the champion-selection window.
- **Walk-forward** — `walk_forward.py` scores each parameter set across
  consecutive out-of-sample folds and penalizes inconsistency, so the search
  rewards parameters that generalize forward rather than memorize one window.
- **No look-ahead** — positions are shifted one bar (act on the *next* bar)
  and transaction costs are charged on turnover, so the optimizer can't cheat.

**Output — the shared parameter file.** The optimizer writes
`output/active_params.json` (the champion strategy, its parameters, and a full
leaderboard). This is the contract for the rest of the pipeline: because
NinjaTrader can't easily hot-swap scripts, the live NinjaScript strategy reads
this file **at session start** instead of being recompiled each week.

```jsonc
{
  "champion": {
    "strategy": "bollinger_breakout",
    "params": { "period": 19, "mult": 2.11 },
    "score": 0.92,
    "metrics": { "profit_factor": 1.05, "max_drawdown": 0.12, "win_rate": 0.52 }
  },
  "leaderboard": [ ]
}
```

**Tests** (synthetic data, no network — CI-safe):

```bash
python tests/test_optimizer.py        # or: python -m pytest tests/ -q
```

---

## 3. Roadmap — Modules 2–4

- **Generator (Jinja2):** read `active_params.json`, render a NinjaScript C#
  template (`templates/Strategy.cs.j2`) into `output/<Strategy>.cs`, and keep
  the shared param file as the runtime source of truth the strategy reads in
  `OnStateChange → State.Configure`.
- **Risk Layer:** poll FinancialModelingPrep / ForexFactory for high-impact
  events; expose a `risk_multiplier` (→ `0.5`) when high-impact news is
  imminent *or* the account is within 20% of max daily drawdown. NinjaScript
  multiplies its position size by this value.
- **Monitoring bot (Discord/Telegram):** daily trades / PnL / win-rate report,
  weekly "Strategy of the Week" from the optimizer leaderboard, and an audit
  routine that diffs expected backtest trades against actual broker
  executions to flag slippage / fills.

## Disclaimer

Research and educational tooling for your own automated trading. Backtested
performance does not guarantee future results. Validate on a simulation /
paper account before risking real capital.
