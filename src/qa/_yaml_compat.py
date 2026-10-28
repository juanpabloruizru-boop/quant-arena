"""Compatibilidad PyYAML -> ruamel.yaml (pure Python) para Python 3.15+ en Windows sin MSVC.

Este módulo proporciona la API de PyYAML (yaml.safe_load, yaml.safe_dump, etc.)
usando ruamel.yaml como backend puro en Python. Se importa automáticamente al
iniciar la CLI (qa/cli.py).
"""
from __future__ import annotations

import sys
from typing import Any, TextIO

# ruamel.yaml es pure Python, no requiere compilación C
from ruamel.yaml import YAML as _RuamelYAML

# Instancia configurada para comportamiento seguro (equivalente a safe_load)
_ruamel = _RuamelYAML(typ="safe", pure=True)
_ruamel.default_flow_style = False
_ruamel.allow_unicode = True


def safe_load(stream: str | TextIO) -> Any:
    """Carga YAML de forma segura (equivale a yaml.safe_load)."""
    if hasattr(stream, "read"):
        return _ruamel.load(stream)
    return _ruamel.load(stream)


def safe_load_all(stream: str | TextIO) -> Any:
    """Carga múltiples documentos YAML (equivale a yaml.safe_load_all)."""
    if hasattr(stream, "read"):
        return _ruamel.load_all(stream)
    return _ruamel.load_all(stream)


def safe_dump(data: Any, stream: TextIO | None = None, **kw: Any) -> str | None:
    """Vuelca a YAML de forma segura (equivale a yaml.safe_dump)."""
    # ruamel.yaml no acepta todos los kwargs de PyYAML; filtramos los comunes
    allowed = {"default_flow_style", "allow_unicode", "indent", "width"}
    filtered = {k: v for k, v in kw.items() if k in allowed}
    if stream is None:
        return str(_ruamel.dump(data, **filtered))
    _ruamel.dump(data, stream, **filtered)
    return None


def dump(data: Any, stream: TextIO | None = None, **kw: Any) -> str | None:
    """Alias para safe_dump (compatibilidad)."""
    return safe_dump(data, stream, **kw)


def load(stream: str | TextIO, Loader: Any = None) -> Any:
    """Carga YAML (equivale a yaml.load con Loader seguro por defecto)."""
    if Loader is not None:
        # Ignoramos Loader personalizado por seguridad; usamos safe
        pass
    return safe_load(stream)


# Exponer clases de error para compatibilidad
class YAMLError(Exception):
    pass


class MarkedYAMLError(YAMLError):
    pass


# Constantes de versión
__version__ = "6.0.3-compat"
__with_libyaml__ = False

# Inyectar en sys.modules para que `import yaml` funcione
sys.modules["yaml"] = sys.modules[__name__]


# Auto-inyección opcional: si se importa este módulo, yaml queda disponible
# Uso: `import qa._yaml_compat` al inicio de cli.py
