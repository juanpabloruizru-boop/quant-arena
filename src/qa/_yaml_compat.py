"""Compatibilidad PyYAML <-> ruamel.yaml.

Si PyYAML está instalado y operativo (Linux, macOS, Windows estándar), lo usa directamente.
Si no (ej. Windows con Python 3.15 sin MSVC), recurre a ruamel.yaml (pure Python) como fallback.
"""
from __future__ import annotations

import sys
from typing import Any, TextIO

try:
    import yaml as _orig_yaml
    _HAS_PYYAML = True
except (ImportError, OSError):
    _orig_yaml = None
    _HAS_PYYAML = False

if _HAS_PYYAML and _orig_yaml is not None:
    safe_load = _orig_yaml.safe_load
    safe_load_all = getattr(_orig_yaml, "safe_load_all", None)
    safe_dump = _orig_yaml.safe_dump
    dump = _orig_yaml.dump
    load = getattr(_orig_yaml, "safe_load", None)
    YAMLError = _orig_yaml.YAMLError
    MarkedYAMLError = getattr(_orig_yaml, "MarkedYAMLError", YAMLError)
    __version__ = getattr(_orig_yaml, "__version__", "6.0.2")
    __with_libyaml__ = getattr(_orig_yaml, "__with_libyaml__", False)
else:
    try:
        from ruamel.yaml import YAML as _RuamelYAML

        _ruamel = _RuamelYAML(typ="safe", pure=True)
        _ruamel.default_flow_style = False
        _ruamel.allow_unicode = True

        def safe_load(stream: str | TextIO) -> Any:
            """Carga YAML de forma segura (equivale a yaml.safe_load)."""
            return _ruamel.load(stream)

        def safe_load_all(stream: str | TextIO) -> Any:
            """Carga múltiples documentos YAML (equivale a yaml.safe_load_all)."""
            return _ruamel.load_all(stream)

        def safe_dump(data: Any, stream: TextIO | None = None, **kw: Any) -> str | None:
            """Vuelca a YAML de forma segura (equivale a yaml.safe_dump)."""
            allowed = {"default_flow_style", "allow_unicode", "indent", "width"}
            filtered = {k: v for k, v in kw.items() if k in allowed}
            if stream is None:
                return str(_ruamel.dump(data, **filtered))
            _ruamel.dump(data, stream, **filtered)
            return None

        def dump(data: Any, stream: TextIO | None = None, **kw: Any) -> str | None:
            return safe_dump(data, stream, **kw)

        def load(stream: str | TextIO, Loader: Any = None) -> Any:
            return safe_load(stream)

        class YAMLError(Exception):
            pass

        class MarkedYAMLError(YAMLError):
            pass

        __version__ = "6.0.3-compat"
        __with_libyaml__ = False

        sys.modules["yaml"] = sys.modules[__name__]
    except (ImportError, OSError):
        pass
