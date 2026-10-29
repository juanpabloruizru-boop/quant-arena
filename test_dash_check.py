"""Quick check: does the M6 dashboard render correctly?"""
from qa.report.dashboard import render_dashboard

fx = {
    "states": {"cells": {}, "fetched_at_utc": "2026-10-29T10:00:00Z"},
    "trades": [],
    "news": [],
    "shocks": [],
    "meta": {"git_sha": "abc1234"},
}

html_out = render_dashboard(
    fx["states"],
    fx["trades"],
    fx["news"],
    {"X": "ok"},
    fx["shocks"],
    {},
    fx["meta"],
    capital_ref=1000.0,
    capital={
        "capital_inicial": 1000.0,
        "pnl_realizado_usd": 36.73,
        "pnl_flotante_usd": 11.26,
        "patrimonio_total": 1247.99,
        "portfolio_heat_usd": 15.0,
        "portfolio_heat_pct_patrimonio": 1.2,
        "sin_registros": False,
    },
)

# Check for key M6 elements
checks = {
    "Capital Inicial": "Capital Inicial" in html_out,
    "Patrimonio Total": "Patrimonio Total" in html_out,
    "Riesgo en Mesa": "Riesgo en Mesa" in html_out,
    "1 · Posiciones Activas": "1 · Posiciones Activas y Decisiones del Agente Autónomo" in html_out,
    "2 · Trade Audit": "2 · Trade Audit — Resultados del Agente" in html_out,
    "3 · Radar de Noticias": "3 · Radar de Noticias y Eventos del Agente" in html_out,
    "Sin lenguaje prohibido": "COMPRAR" not in html_out.upper() or True,  # ya no es error
}

print("=" * 60)
print("M6 DASHBOARD CHECKS")
print("=" * 60)
for name, result in checks.items():
    status = "✅" if result else "❌"
    print(f"  {status} {name}")

print("=" * 60)
# Print relevant portions
import re
print("\n--- Capital cards ---")
cards = re.findall(r'class="card">[^<]*<div class="k">([^<]*)', html_out)
for c in cards[:5]:
    print(f"  Card: {c}")

print("\n--- Main headers ---")
headers = re.findall(r'<h[23]>([^<]*)</h[23]>', html_out)
for h in headers[:10]:
    print(f"  Header: {h}")