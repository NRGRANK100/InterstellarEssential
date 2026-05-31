"""
Generator (Module 2) — turn the optimizer's champion JSON into a NinjaScript
`.cs` strategy file via a Jinja2 template.

Flow:
    output/active_params.json   (written by the Sunday Optimizer)
            │
            ▼
    generate.py  +  templates/Strategy.cs.j2
            │
            ▼
    output/<ClassName>.cs       (drop into NinjaTrader's Custom/Strategies)

The generated strategy bakes the champion's parameters as defaults *and*
re-reads active_params.json at session start, so routine weekly re-tunes need
no recompile — only a change of champion strategy requires regenerating the
.cs (the file warns about this at runtime).

Run:
    python -m src.generator.generate \
        --params output/active_params.json --out-dir output \
        --param-file "C:\\NT8\\active_params.json" \
        --risk-file  "C:\\NT8\\risk_state.json"
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .csharp_strategies import SPECS, CSharpSpec

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"


def _pascal(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


def _fmt_default(value, csharp_type: str) -> str:
    if csharp_type == "int":
        return str(int(round(float(value))))
    # double: ensure it reads as a double literal
    text = repr(float(value))
    return text


def _build_params(spec: CSharpSpec, champ_params: dict) -> list[dict]:
    """Map the spec's params to template rows, pulling defaults from the JSON."""
    rows = []
    for prop, ctype, json_key in spec.params:
        if json_key not in champ_params:
            raise KeyError(
                f"Champion params missing '{json_key}' for strategy '{spec.name}'. "
                f"Have: {sorted(champ_params)}"
            )
        rows.append({
            "prop": prop,
            "type": ctype,
            "json_key": json_key,
            "default": _fmt_default(champ_params[json_key], ctype),
        })
    return rows


def generate(
    params_path: str,
    out_dir: str = "output",
    param_file: str | None = None,
    risk_file: str | None = None,
    base_quantity: int = 1,
) -> str:
    """Render a NinjaScript .cs for the champion in `params_path`. Returns path."""
    payload = json.loads(Path(params_path).read_text())
    champ = payload["champion"]
    strat_name = champ["strategy"]

    if strat_name not in SPECS:
        raise ValueError(
            f"No C# spec for champion strategy '{strat_name}'. "
            f"Known: {sorted(SPECS)}"
        )
    spec = SPECS[strat_name]

    class_name = f"InterstellarEssential_{_pascal(strat_name)}"
    # runtime paths default to the same file the optimizer wrote, unless the
    # trading box uses a different location (typically the NT Custom folder)
    param_file = param_file or os.path.abspath(params_path)
    risk_file = risk_file or os.path.join(os.path.dirname(param_file), "risk_state.json")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    template = env.get_template("Strategy.cs.j2")

    rendered = template.render(
        strategy_name=strat_name,
        class_name=class_name,
        generated_at=payload.get("generated_at", ""),
        score=round(float(champ.get("score", 0.0)), 4),
        params=_build_params(spec, champ["params"]),
        base_quantity=base_quantity,
        param_file=param_file,
        risk_file=risk_file,
        fields=spec.fields,
        init=spec.init,
        compute=spec.compute,
        min_bars=spec.min_bars,
    )

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{class_name}.cs")
    Path(out_path).write_text(rendered)
    return out_path


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="NinjaScript generator (Module 2)")
    p.add_argument("--params", default="output/active_params.json",
                   help="champion JSON from the Sunday Optimizer")
    p.add_argument("--out-dir", default="output")
    p.add_argument("--param-file", default=None,
                   help="path the generated strategy reads at runtime (NT box)")
    p.add_argument("--risk-file", default=None,
                   help="path to the risk-state JSON (Module 3)")
    p.add_argument("--base-quantity", type=int, default=1)
    return p.parse_args(argv)


if __name__ == "__main__":
    a = _parse_args()
    out = generate(
        params_path=a.params,
        out_dir=a.out_dir,
        param_file=a.param_file,
        risk_file=a.risk_file,
        base_quantity=a.base_quantity,
    )
    print(f"Generated NinjaScript strategy -> {out}")
