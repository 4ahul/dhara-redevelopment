"""Shared utilities and models for Dhara AI microservices."""

import importlib
import sys

# Standard sub-packages
for _name in ("config", "dhara_common", "models"):
    try:
        _mod = importlib.import_module(f"{__name__}.{_name}")
        # Alias dhara_shared.models for convenience if needed by legacy tests
        if _name == "models":
            sys.modules.setdefault("dhara_shared.models", _mod)
    except ModuleNotFoundError:
        pass
