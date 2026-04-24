"""Compatibility shims for dhara_shared import paths."""

import importlib
import sys

# Some services import `dhara_shared.dhara_shared.*`.
# Alias that namespace to this package so both styles resolve.
sys.modules.setdefault("dhara_shared.dhara_shared", sys.modules[__name__])

for _name in ("config", "dhara_common"):
    try:
        _mod = importlib.import_module(f"{__name__}.{_name}")
        sys.modules.setdefault(f"dhara_shared.dhara_shared.{_name}", _mod)
    except ModuleNotFoundError:
        pass
