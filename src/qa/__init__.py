"""QUANT-ARENA v2: laboratorio de investigacion reproducible.

Sin dinero real, sin claves de exchange, sin ordenes, sin listeners.
"""

# Compatibilidad PyYAML -> ruamel.yaml y pandas -> pure Python/NumPy (Windows App Control)
import qa._pandas_compat  # noqa: F401
import qa._yaml_compat  # noqa: F401

__version__ = "0.1.0"
