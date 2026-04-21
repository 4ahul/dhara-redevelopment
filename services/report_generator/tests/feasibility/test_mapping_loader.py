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
