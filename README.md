# Interstellar Essential — Self-Optimizing NinjaTrader 8 Pipeline

A self-optimizing automated trading pipeline for **NinjaTrader 8**. A weekly
Python job searches a large parameter space across ten strategies, picks the
best performer, and hands optimized parameters to a live NinjaScript strategy
through a shared file — with a news/risk layer and a reporting bot on top.

The system is built in four parts:

| # | Module | Language | Status |
|---|--------|----------|--------|
| 1 | **Sunday Optimizer** — backtests ~500k parameter combos, walk-forward, picks champion | Python | ✅ implemented |
| 2 | **Generator** — Jinja2 fills a NinjaScript C# template from the champion JSON | Python / C# | ✅ implemented |
| 3 | **Risk Layer** — high-impact news + drawdown guard, halves position size | Python / C# | ✅ implemented |
| 4 | **Monitoring** — Discord/Telegram bot: daily PnL, win rate, weekly "Strategy of the Week", execution audit | Python | ✅ implemented |

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

## 3. Module 2 — the Generator  ✅

> *"A Jinja2-based generator that fills a NinjaScript C# template with optimized
> parameters and outputs a `.cs` strategy file. Since NinjaTrader can't easily
> hot-swap scripts, use a shared JSON parameter file the strategy reads at
> session startup."*

```
src/generator/
├── csharp_strategies.py   # C# translation of all 10 optimizer strategies
└── generate.py            # load champion JSON -> render template -> .cs
templates/
└── Strategy.cs.j2         # NinjaScript C# template
```

**Run it (after the optimizer has written `active_params.json`):**

```bash
python -m src.generator.generate \
    --params output/active_params.json --out-dir output \
    --param-file "C:\NT8\bin\Custom\active_params.json" \
    --risk-file  "C:\NT8\bin\Custom\risk_state.json" \
    --base-quantity 1
# -> output/InterstellarEssential_<Champion>.cs   (drop into NT Custom/Strategies)
```

**How it hits the requirements**

- **Jinja2 template → `.cs`:** `templates/Strategy.cs.j2` is rendered with the
  champion's name, parameters, and indicator/signal C# for that strategy.
- **All 10 strategies covered:** `csharp_strategies.py` mirrors the optimizer's
  registry; a test asserts the two registries (and their param names) never
  drift apart.
- **No hot-swap needed:** the generated strategy bakes the champion's params as
  **defaults** *and* re-reads `active_params.json` in `State.Configure` at
  session start, so a routine weekly re-tune needs **no recompile**. Only a
  change of *champion strategy* requires regenerating the `.cs` (the file
  detects this at runtime and warns).
- **Dependency-free C#:** parameters are read with a tiny built-in regex JSON
  reader, so no extra NinjaTrader references are required.
- **Risk-layer ready:** position size is computed as
  `BaseQuantity × riskMultiplier`, where the multiplier is read from the
  risk-state file (Module 3) at runtime.

**Tests:** `python tests/test_generator.py`

---

## 4. Module 3 — the Risk Layer  ✅

> *"A news/risk engine using FinancialModelingPrep or ForexFactory to detect
> high-impact news. If high-impact news occurs OR the account reaches within
> 20% of max daily drawdown, automatically reduce position size by 50%."*

```
src/risk/
├── news.py        # FinancialModelingPrep + ForexFactory high-impact detection
├── drawdown.py    # daily-drawdown buffer guard
└── engine.py      # combine triggers -> write risk_state.json
```

**Run it (on the trading box, e.g. on a schedule / each loop):**

```bash
python -m src.risk.engine \
    --fmp-key "$FMP_API_KEY" --news-source fmp \
    --max-daily-drawdown 1000 --day-pnl -820 \
    --window-minutes 60 --currencies USD \
    --out output/risk_state.json
```

**How it hits the requirements**

- **High-impact news:** `news.py` pulls the FinancialModelingPrep economic
  calendar (ForexFactory weekly JSON as a fallback) and trips if a *High*-impact
  event for the watched currency falls within ±`window-minutes` of now.
- **Drawdown guard:** `drawdown.py` trips when the day's loss has reached ≥ 80%
  of the configured max daily drawdown — i.e. the account is *within 20%* of the
  limit.
- **−50% size:** if **either** trigger fires, `engine.py` writes
  `risk_multiplier = 0.5` (else `1.0`) into `output/risk_state.json`. The
  generated NinjaScript re-reads this file at runtime and sizes orders as
  `BaseQuantity × risk_multiplier` (fail-safe: never upsizes on a read error).
- **Resilient:** all network calls are lazy, timed out, and degrade gracefully
  (a failed fetch never blocks trading).

**Tests:** `python tests/test_risk.py`  (14 tests, no network)

---

## 5. Module 4 — Monitoring & Audit  ✅

> *"A Discord or Telegram bot that reports daily trades, PnL, and win rate, plus
> weekly 'Strategy of the Week' results, and an audit routine comparing expected
> backtest trades to actual broker executions to detect slippage."*

```
src/monitoring/
├── notifier.py    # pluggable Console / Discord / Telegram notifier
├── trade_log.py   # Trade model, NinjaTrader executions CSV loader, daily_stats
├── reports.py     # daily report + weekly "Strategy of the Week"
├── audit.py       # backtest-vs-execution slippage / fill audit
└── run.py         # CLI: --daily / --weekly / --audit
```

**Run it:**

```bash
# daily PnL / win-rate report from a NinjaTrader executions export
python -m src.monitoring.run --daily --executions data/executions.csv --notifier console

# weekly "Strategy of the Week" from the optimizer's leaderboard
python -m src.monitoring.run --weekly --params output/active_params.json --notifier telegram

# execution audit: expected backtest trades vs actual broker fills
python -m src.monitoring.run --audit --expected output/expected_trades.json \
    --actual data/executions.csv --notifier discord
```

**How it hits the requirements**

- **Pluggable bot:** `--notifier {console,discord,telegram}` — both Discord
  (webhook) and Telegram (Bot API) are supported; **console is the default** so
  nothing breaks before you add credentials (set them in `.env`).
- **Daily report:** trades, gross PnL, win rate, largest win/loss from the
  executions file.
- **Strategy of the Week:** reads the optimizer's champion + leaderboard.
- **Execution audit:** matches expected trades to actual fills by side/time,
  computes **signed slippage** (positive = adverse), and flags excessive
  slippage, quantity mismatches, missing fills, and extra fills.

**Tests:** `python tests/test_monitoring.py`  (8 tests, no network)

---

## Run all tests

```bash
for t in optimizer generator risk monitoring; do python tests/test_$t.py; done
# optimizer 6 · generator 4 · risk 14 · monitoring 8  — all network-free

## Disclaimer

Research and educational tooling for your own automated trading. Backtested
performance does not guarantee future results. Validate on a simulation /
paper account before risking real capital.
