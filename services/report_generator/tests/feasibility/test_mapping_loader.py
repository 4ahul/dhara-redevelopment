from feasibility.mapping_loader import MappingEntry, MappingFile


def test_mapping_entry_roundtrip():
    e = MappingEntry(
        cell="Details!R17",
        kind="yellow",
        semantic_name="road_width_m",
        from_="dp_report.road_width_m",
        fallback=18.3,
        transform="float",
    )
    assert e.cell == "Details!R17"
    assert e.sheet == "Details"
    assert e.coord == "R17"
    assert e.from_ == "dp_report.road_width_m"


def test_mapping_file_container():
    m = MappingFile(template="x.xlsx", scheme="33(7)(B)", cells=[])
    assert m.cells == []


def test_load_valid_yaml(tmp_path):
    from feasibility.mapping_loader import load_mapping
    y = """
template: t.xlsx
scheme: "33(7)(B)"
cells:
  - cell: Details!R17
    kind: yellow
    semantic_name: road_width_m
    from: dp_report.road_width_m
    fallback: 18.3
    transform: float
"""
    p = tmp_path / "m.yaml"
    p.write_text(y)
    m = load_mapping(str(p))
    assert m.scheme == "33(7)(B)"
    assert len(m.cells) == 1
    assert m.cells[0].from_ == "dp_report.road_width_m"
    assert m.cells[0].fallback == 18.3
