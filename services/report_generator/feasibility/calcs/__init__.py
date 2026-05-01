"""Importing this package registers every built-in calc with calc_registry.

We import submodules dynamically to avoid unused-import lint warnings while preserving
side-effect registration of calculators.
"""

from importlib import import_module as _import_module

for _mod in (
    "area_derivations",
    "financial_derivations",
    "height_derivations",
    "metadata_calcs",
    "noc_flags",
    "period_derivations",
):
    _import_module(f"{__name__}.{_mod}")
