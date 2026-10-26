"""Guard de seguridad estructural (principio: prohibido dinero real / listeners).

Falla si en ``src/qa`` aparece:
- import de clientes de trading autenticados (ccxt, python-binance, pybit, ...);
- servidores/listeners (socket bind/listen, http.server, socketserver, uvicorn,
  fastapi, flask, starlette, tornado, aiohttp.web);
- texto que sugiera secretos de exchange (api_secret, listenKey, apiKey con valor).

Los scripts de verificacion de M0 (scripts/probe_binance.py) solo hacen GET
publicos de lectura; el alcance de este test es el paquete productivo src/qa.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "qa"

FORBIDDEN_MODULE_ROOTS = {
    # clientes de trading / exchange autenticados
    "ccxt",
    "binance",
    "pybit",
    "deribit",
    "bybit",
    "okx",
    "krakenex",
    "coinbase",
    "coinbasepro",
    "web3",
    # servidores / listeners / daemons
    "socketserver",
    "http.server",
    "uvicorn",
    "fastapi",
    "flask",
    "starlette",
    "tornado",
    "aiohttp.web",
    "websockets.server",
}

FORBIDDEN_ATTR_CALLS = {"bind", "listen", "start_server", "serve_forever"}

FORBIDDEN_TEXT = ("api_secret", "listenKey", "apiSecret", "secret_key")


def _py_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def test_src_has_files() -> None:
    assert len(_py_files()) >= 9


def test_no_forbidden_imports() -> None:
    offenders: list[str] = []
    for f in _py_files():
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                root = name.split(".")[0]
                if name in FORBIDDEN_MODULE_ROOTS or root in FORBIDDEN_MODULE_ROOTS:
                    offenders.append(f"{f}: {name}")
    assert not offenders, f"imports prohibidos: {offenders}"


def test_no_listening_sockets() -> None:
    offenders: list[str] = []
    for f in _py_files():
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Attribute) and fn.attr in FORBIDDEN_ATTR_CALLS:
                    offenders.append(f"{f}:{node.lineno}: .{fn.attr}()")
                if isinstance(fn, ast.Name) and fn.id == "socket":
                    offenders.append(f"{f}:{node.lineno}: socket()")
    assert not offenders, f"sockets/llamadas prohibidas: {offenders}"


def test_no_secret_like_text() -> None:
    offenders: list[str] = []
    for f in _py_files():
        text = f.read_text(encoding="utf-8")
        for bad in FORBIDDEN_TEXT:
            if bad in text:
                offenders.append(f"{f}: {bad}")
    assert not offenders, f"texto sospechoso de credenciales: {offenders}"


def test_env_is_gitignored() -> None:
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore.splitlines()
    assert not (REPO / ".env").exists(), ".env commiteado: prohibido"
