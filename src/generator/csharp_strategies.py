"""
C# strategy translation specs.

For each Python strategy in `src.optimizer.strategies.REGISTRY` there is a
matching C# spec here so the Generator can emit a NinjaScript `.cs` file that
reproduces the optimizer's chosen logic. A consistency test asserts the two
registries stay in lock-step.

Each spec carries:
  * params   — ordered (PropertyName, csharp_type, json_key) tuples. `json_key`
               matches the key the optimizer writes in active_params.json.
  * fields   — private field declarations (cached indicators / series).
  * init     — code for State.DataLoaded (build indicators).
  * compute  — OnBarUpdate body that sets `int desired` in {-1, 0, +1}.
  * min_bars — expression for BarsRequiredToTrade.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CSharpSpec:
    name: str
    params: list[tuple[str, str, str]]
    fields: str
    init: str
    compute: str
    min_bars: str


SPECS: dict[str, CSharpSpec] = {}


def _add(spec: CSharpSpec) -> None:
    SPECS[spec.name] = spec


# ── crossovers ──────────────────────────────────────────────────────────

_add(CSharpSpec(
    name="sma_crossover",
    params=[("Fast", "int", "fast"), ("Slow", "int", "slow")],
    fields="private SMA fastMa;\n\t\tprivate SMA slowMa;",
    init="fastMa = SMA(Fast);\n\t\t\tslowMa = SMA(Slow);",
    compute=(
        "int desired = 0;\n"
        "\t\t\tif (fastMa[0] > slowMa[0]) desired = 1;\n"
        "\t\t\telse if (fastMa[0] < slowMa[0]) desired = -1;"
    ),
    min_bars="Slow + 5",
))

_add(CSharpSpec(
    name="ema_crossover",
    params=[("Fast", "int", "fast"), ("Slow", "int", "slow")],
    fields="private EMA fastMa;\n\t\tprivate EMA slowMa;",
    init="fastMa = EMA(Fast);\n\t\t\tslowMa = EMA(Slow);",
    compute=(
        "int desired = 0;\n"
        "\t\t\tif (fastMa[0] > slowMa[0]) desired = 1;\n"
        "\t\t\telse if (fastMa[0] < slowMa[0]) desired = -1;"
    ),
    min_bars="Slow + 5",
))

# ── mean reversion (state held until opposite signal) ───────────────────

_add(CSharpSpec(
    name="rsi_reversion",
    params=[("Period", "int", "period"), ("Lower", "int", "lower"), ("Upper", "int", "upper")],
    fields="private RSI rsi;\n\t\tprivate int lastSignal = 0;",
    init="rsi = RSI(Period, 1);",
    compute=(
        "int desired = lastSignal;\n"
        "\t\t\tif (rsi[0] < Lower) desired = 1;\n"
        "\t\t\telse if (rsi[0] > Upper) desired = -1;\n"
        "\t\t\tlastSignal = desired;"
    ),
    min_bars="Period + 5",
))

_add(CSharpSpec(
    name="bollinger_breakout",
    params=[("Period", "int", "period"), ("Mult", "double", "mult")],
    fields="private Bollinger bb;\n\t\tprivate int lastSignal = 0;",
    init="bb = Bollinger(Mult, Period);",
    compute=(
        "int desired = lastSignal;\n"
        "\t\t\tif (Close[0] > bb.Upper[0]) desired = 1;\n"
        "\t\t\telse if (Close[0] < bb.Lower[0]) desired = -1;\n"
        "\t\t\tlastSignal = desired;"
    ),
    min_bars="Period + 5",
))

_add(CSharpSpec(
    name="macd",
    params=[("Fast", "int", "fast"), ("Slow", "int", "slow"), ("SignalLen", "int", "signal")],
    fields="private MACD macdInd;",
    init="macdInd = MACD(Fast, Slow, SignalLen);",
    compute=(
        "int desired = 0;\n"
        "\t\t\tif (macdInd.Default[0] > macdInd.Avg[0]) desired = 1;\n"
        "\t\t\telse if (macdInd.Default[0] < macdInd.Avg[0]) desired = -1;"
    ),
    min_bars="Slow + SignalLen + 5",
))

_add(CSharpSpec(
    name="donchian_breakout",
    params=[("Period", "int", "period")],
    fields="private int lastSignal = 0;",
    init="// channel computed inline from MAX/MIN",
    compute=(
        "double hi = MAX(High, Period)[1];\n"
        "\t\t\tdouble lo = MIN(Low, Period)[1];\n"
        "\t\t\tint desired = lastSignal;\n"
        "\t\t\tif (Close[0] > hi) desired = 1;\n"
        "\t\t\telse if (Close[0] < lo) desired = -1;\n"
        "\t\t\tlastSignal = desired;"
    ),
    min_bars="Period + 5",
))

_add(CSharpSpec(
    name="momentum",
    params=[("Lookback", "int", "lookback"), ("Threshold", "double", "threshold")],
    fields="",
    init="// rate-of-change computed inline",
    compute=(
        "double roc = (Close[0] - Close[Lookback]) / Close[Lookback];\n"
        "\t\t\tint desired = 0;\n"
        "\t\t\tif (roc > Threshold) desired = 1;\n"
        "\t\t\telse if (roc < -Threshold) desired = -1;"
    ),
    min_bars="Lookback + 5",
))

_add(CSharpSpec(
    name="stochastic",
    params=[("Period", "int", "period"), ("Lower", "int", "lower"), ("Upper", "int", "upper")],
    fields="private Stochastics stoch;\n\t\tprivate int lastSignal = 0;",
    init="stoch = Stochastics(3, Period, 3);",
    compute=(
        "double k = stoch.K[0];\n"
        "\t\t\tint desired = lastSignal;\n"
        "\t\t\tif (k < Lower) desired = 1;\n"
        "\t\t\telse if (k > Upper) desired = -1;\n"
        "\t\t\tlastSignal = desired;"
    ),
    min_bars="Period + 5",
))

_add(CSharpSpec(
    name="atr_breakout",
    params=[("Period", "int", "period"), ("Mult", "double", "mult")],
    fields="private ATR atr;\n\t\tprivate int lastSignal = 0;",
    init="atr = ATR(Period);",
    compute=(
        "double refPrice = Close[1];\n"
        "\t\t\tint desired = lastSignal;\n"
        "\t\t\tif (Close[0] > refPrice + Mult * atr[0]) desired = 1;\n"
        "\t\t\telse if (Close[0] < refPrice - Mult * atr[0]) desired = -1;\n"
        "\t\t\tlastSignal = desired;"
    ),
    min_bars="Period + 5",
))

_add(CSharpSpec(
    name="vwap_reversion",
    params=[("Period", "int", "period"), ("Band", "double", "band")],
    fields=(
        "private Series<double> tpv;\n"
        "\t\tprivate Series<double> tv;\n"
        "\t\tprivate Series<double> dist;\n"
        "\t\tprivate int lastSignal = 0;"
    ),
    init=(
        "tpv = new Series<double>(this);\n"
        "\t\t\ttv = new Series<double>(this);\n"
        "\t\t\tdist = new Series<double>(this);"
    ),
    compute=(
        "double typical = (High[0] + Low[0] + Close[0]) / 3.0;\n"
        "\t\t\ttpv[0] = typical * Volume[0];\n"
        "\t\t\ttv[0]  = Volume[0];\n"
        "\t\t\tdouble sumTv = SUM(tv, Period)[0];\n"
        "\t\t\tdouble vwap = sumTv != 0 ? SUM(tpv, Period)[0] / sumTv : Close[0];\n"
        "\t\t\tdist[0] = Close[0] - vwap;\n"
        "\t\t\tdouble sd = StdDev(dist, Period)[0];\n"
        "\t\t\tint desired = lastSignal;\n"
        "\t\t\tif (dist[0] > Band * sd) desired = -1;\n"
        "\t\t\telse if (dist[0] < -Band * sd) desired = 1;\n"
        "\t\t\tlastSignal = desired;"
    ),
    min_bars="Period + 5",
))


def list_specs() -> list[str]:
    return list(SPECS)
