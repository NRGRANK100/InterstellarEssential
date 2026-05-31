"""
Tests for the Generator (Module 2). No network, no NinjaTrader required —
we render against sample champion JSON and assert the emitted C# is well-formed
enough to trust (balanced braces, expected tokens, every param wired through).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.generator import generate, SPECS, list_specs       # noqa: E402
from src.generator.csharp_strategies import SPECS as CS_SPECS  # noqa: E402
from src.optimizer import strategies as strat_mod            # noqa: E402


def _sample_payload(strategy: str, params: dict) -> dict:
    return {
        "generated_at": "2026-05-31T00:00:00+00:00",
        "champion": {
            "strategy": strategy,
            "params": params,
            "score": 0.9123,
            "metrics": {"profit_factor": 1.05, "max_drawdown": 0.12},
        },
    }


def test_every_optimizer_strategy_has_csharp_spec():
    py = set(strat_mod.list_strategies())
    cs = set(list_specs())
    assert py == cs, f"registry mismatch: only-py={py - cs}  only-cs={cs - py}"


def test_csharp_param_keys_match_optimizer_space():
    """Each C# spec's json_keys must equal the optimizer's param names."""
    for name, spec in CS_SPECS.items():
        py_keys = set(strat_mod.REGISTRY[name].space)
        cs_keys = {json_key for _, _, json_key in spec.params}
        assert py_keys == cs_keys, f"{name}: py={py_keys} cs={cs_keys}"


def test_generate_bollinger(tmp_path=None):
    out_dir = Path(__file__).resolve().parents[1] / "output"
    params_json = out_dir / "_test_champion.json"
    out_dir.mkdir(exist_ok=True)
    params_json.write_text(json.dumps(
        _sample_payload("bollinger_breakout", {"period": 19, "mult": 2.1133})
    ))

    cs_path = generate(
        params_path=str(params_json),
        out_dir=str(out_dir),
        param_file=r"C:\NT8\active_params.json",
        risk_file=r"C:\NT8\risk_state.json",
        base_quantity=2,
    )
    src = Path(cs_path).read_text()

    # structural sanity
    assert src.count("{") == src.count("}"), "unbalanced braces"
    assert "class InterstellarEssential_BollingerBreakout : Strategy" in src
    assert "public int Period { get; set; } = 19;" in src
    assert "public double Mult { get; set; }" in src and "= 2.1133" in src
    assert "public int BaseQuantity { get; set; } = 2;" in src
    assert 'ExpectedStrategy = "bollinger_breakout"' in src
    # runtime plumbing present
    assert "LoadOptimizedParams" in src
    assert "RefreshRiskMultiplier" in src
    assert "bb = Bollinger(Mult, Period);" in src
    # risk layer wired into sizing
    assert "BaseQuantity * riskMultiplier" in src

    params_json.unlink()
    Path(cs_path).unlink()


def test_generate_all_strategies_render_and_balance():
    """Smoke-render every strategy with its low-end params; check brace balance."""
    out_dir = Path(__file__).resolve().parents[1] / "output"
    out_dir.mkdir(exist_ok=True)
    for name, strat in strat_mod.REGISTRY.items():
        params = {}
        for pname, spec in strat.space.items():
            params[pname] = spec[1] if spec[0] != "cat" else spec[1][0]
        pj = out_dir / f"_test_{name}.json"
        pj.write_text(json.dumps(_sample_payload(name, params)))
        cs_path = generate(params_path=str(pj), out_dir=str(out_dir))
        src = Path(cs_path).read_text()
        assert src.count("{") == src.count("}"), f"{name}: unbalanced braces"
        assert "int desired" in src, f"{name}: missing signal var"
        pj.unlink()
        Path(cs_path).unlink()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")
