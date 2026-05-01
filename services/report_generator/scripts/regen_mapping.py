"""One-off: regenerate mappings/33_7_B.yaml from dossier + cell_mapper.py.

Not part of runtime. Run manually if inputs change.
"""

from __future__ import annotations

import ast
import datetime
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
DOSSIER = HERE / "dossiers" / "33_7_B.dossier.json"
CELL_MAPPER = HERE / "services" / "cell_mapper.py"
OUT = HERE / "mappings" / "33_7_B.yaml"


def parse_cell_mapper() -> dict:
    text = CELL_MAPPER.read_text(encoding="utf-8")
    pattern = re.compile(
        r'CellMapping\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"'
        r'(?:\s*,\s*"([^"]+)")?(?:\s*,\s*([^)]+))?\s*\)',
        re.DOTALL,
    )
    out = {}
    for m in pattern.finditer(text):
        sheet, cell, path, transform, default = (
            m.group(1),
            m.group(2),
            m.group(3),
            m.group(4) or "direct",
            (m.group(5) or "").strip(),
        )
        key = f"{sheet}!{cell}"
        if key not in out:
            out[key] = {"path": path, "transform": transform, "default": default}
    return out


def parse_default(raw: str):
    s = (raw or "").strip()
    if s in ("", "None"):
        return None
    try:
        return ast.literal_eval(s)
    except Exception:
        return None


def coord_slug(coord: str) -> str:
    sheet, c = coord.split("!", 1)
    return re.sub(r"[^a-z0-9]+", "_", sheet.lower()).strip("_") + "_" + c.lower()


def name_from_path(path: str) -> str:
    leaf = path.split("|")[0].split(".")[-1]
    return re.sub(r"[^a-z0-9]+", "_", leaf.lower()).strip("_")


EXPLICIT = {
    "Details!A1": {
        "name": "society_header_title",
        "kind": "black",
        "from_": "society_name",
        "fb": "",
        "tr": "str",
        "comment": "Society name header at top of Details sheet",
    },
    "Details!M1": {
        "name": "cts_fp_no_label",
        "kind": "black",
        "from_": "manual_inputs.cts_fp_no_label",
        "fb": "Cts No. /FP No.:-",
        "tr": "str",
        "comment": "Literal label prefix; real CTS/FP number lives in a yellow cell elsewhere",
    },
    "Details!M2": {
        "name": "village_name",
        "kind": "black",
        "sources": ["mcgm_property.village", "manual_inputs.village"],
        "fb": "",
        "tr": "str",
        "comment": "Village label/value",
    },
    "Details!O47": {
        "name": "details_o47",
        "kind": "yellow",
        "from_": "manual_inputs.details_o47",
        "fb": 0,
        "tr": "float",
        "comment": "No cell_mapper.py entry — review in template",
    },
    "MCGM PAYMENTS!B327": {
        "name": "nalla_note",
        "kind": "black",
        "from_": "manual_inputs.nalla_note",
        "fb": "",
        "tr": "str",
        "comment": "Conditional note re: nalla (stormwater drain) — typically blank",
    },
}


def main() -> int:
    dossier = json.loads(DOSSIER.read_text(encoding="utf-8"))
    lookup = parse_cell_mapper()
    cells = dossier["cells"]

    lines = [
        "# Mapping file for FINAL TEMPLATE _ 33 (7)(B) .xlsx",
        "# Generated from dossier + services/cell_mapper.py.",
        "# 58/63 cells: sourced from cell_mapper.py _COMMON blocks (30(A)+33(7)(B) CLUBBING).",
        "# 5/63 cells: explicit overrides (see scripts/regen_mapping.py EXPLICIT dict).",
        "",
        'template: "FINAL TEMPLATE _ 33 (7)(B) .xlsx"',
        'scheme: "33(7)(B)"',
        "version: 1",
        "generated_from_dossier: dossiers/33_7_B.dossier.json",
        "last_reviewed_by: auto (cell_mapper.py import)",
        f"last_reviewed_at: {datetime.date.today().isoformat()}",
        "cells:",
    ]

    used: set = set()

    def unique(n: str) -> str:
        base = n
        i = 2
        while n in used:
            n = f"{base}_{i}"
            i += 1
        used.add(n)
        return n

    def emit_fallback(fb):
        if isinstance(fb, str):
            return f'    fallback: "{fb}"'
        return f"    fallback: {fb}"

    for c in cells:
        coord = c["cell"]
        kind = c["kind"]
        ph = c["current_value"]
        ph_str = (str(ph) if ph else "")[:80].replace("\n", " ").replace('"', "'")
        row_label = (c["signals"].get("row_label") or "").strip()

        lines.append("")

        if coord in EXPLICIT:
            o = EXPLICIT[coord]
            name = unique(o["name"])
            lines.append(f"  # {o['comment']}")
            lines.append(f"  # placeholder: {ph_str!r}")
            lines.append(f"  - cell: {coord}")
            lines.append(f"    kind: {kind}")
            lines.append(f"    semantic_name: {name}")
            if "calc" in o:
                lines.append(f"    calc: {o['calc']}")
                if o.get("calc_args"):
                    args_yaml = (
                        "{ " + ", ".join(f"{k}: {v}" for k, v in o["calc_args"].items()) + " }"
                    )
                    lines.append(f"    calc_args: {args_yaml}")
            elif "sources" in o:
                lines.append("    sources:")
                for p in o["sources"]:
                    lines.append(f"      - {p}")
            else:
                lines.append(f"    from: {o['from_']}")
            lines.append(emit_fallback(o["fb"]))
            lines.append(f"    transform: {o['tr']}")
            continue

        rec = lookup.get(coord)
        if not rec:
            lines.append("  # WARN: no match in cell_mapper.py — placeholder")
            lines.append(f"  - cell: {coord}")
            lines.append(f"    kind: {kind}")
            lines.append(f"    semantic_name: {unique(coord_slug(coord))}")
            lines.append(f"    from: manual_inputs.{coord_slug(coord)}")
            lines.append("    fallback: 0")
            lines.append("    transform: float")
            continue

        path = rec["path"]
        transform = rec["transform"]
        if transform == "direct":
            transform = "float"
        default = parse_default(rec["default"])
        name = unique(name_from_path(path))

        if row_label and not row_label.startswith("="):
            safe_label = row_label.replace("\n", " ").replace("\r", " ")
            lines.append(f"  # {safe_label[:60]}")

        lines.append(f"  - cell: {coord}")
        lines.append(f"    kind: {kind}")
        lines.append(f"    semantic_name: {name}")

        alts = path.split("|")
        if len(alts) > 1:
            lines.append("    sources:")
            for alt in alts:
                lines.append(f"      - {alt}")
        else:
            lines.append(f"    from: {path}")

        fb_val = 0 if default is None else default
        lines.append(emit_fallback(fb_val))
        lines.append(f"    transform: {transform}")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Sanity
    import yaml

    data = yaml.safe_load(OUT.read_text(encoding="utf-8"))
    names = [x["semantic_name"] for x in data["cells"]]
    dups = [n for n in set(names) if names.count(n) > 1]
    print(f"Wrote {OUT}")
    print(f"  cells={len(data['cells'])}")
    print(f"  yellow={sum(1 for c in data['cells'] if c['kind'] == 'yellow')}")
    print(f"  black={sum(1 for c in data['cells'] if c['kind'] == 'black')}")
    print(f"  semantic_name duplicates={len(dups)} {dups}")
    calc = sum(1 for c in data["cells"] if "calc" in c)
    src_from = sum(1 for c in data["cells"] if "from" in c)
    src_sources = sum(1 for c in data["cells"] if "sources" in c)
    print(f"  calc={calc}, from={src_from}, sources={src_sources}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
