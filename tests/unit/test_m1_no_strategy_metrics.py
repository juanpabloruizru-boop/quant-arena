"""Guard M1: el modulo de datos no computa metricas de ESTRATEGIA.

El gate M0b prohibe calcular retorno/Sharpe/drawdown de estrategias sobre
datos reales en M1. Este test escanea identificadores (no docstrings ni
comentarios) de src/qa/data en busca de metricas de estrategia. Los
log-retornos para z robusto (QA de datos) son permitidos y estan documentados.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA_DIR = REPO / "src" / "qa" / "data"

FORBIDDEN_IDENTIFIERS = ("sharpe", "sortino", "calmar", "drawdown", "max_dd", "expectancy")


def test_no_strategy_metric_identifiers_in_data_module() -> None:
    offenders: list[str] = []
    for f in sorted(DATA_DIR.rglob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                names.append(node.name)
            elif isinstance(node, ast.Name):
                names.append(node.id)
            elif isinstance(node, ast.Attribute):
                names.append(node.attr)
            for name in names:
                low = name.lower()
                if any(bad in low for bad in FORBIDDEN_IDENTIFIERS):
                    offenders.append(f"{f.name}:{getattr(node, 'lineno', '?')} {name}")
    assert not offenders, f"metricas de estrategia en M1: {offenders}"
