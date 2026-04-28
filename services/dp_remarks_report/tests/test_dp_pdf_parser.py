"""Tests for DP Remark PDF parser."""

import os
import unittest

from services.dp_remarks_report.services.dp_pdf_parser import parse_dp_pdf

TEST_DOCS = os.path.join(os.path.dirname(__file__), "..", "..", "..", "test_docs")
SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "sample")


def _load_pdf(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


class TestDP2034Parser(unittest.TestCase):
    """Tests using test_docs/DP Remark 2034 FP 18.pdf (4 pages, FP-based)."""

    @classmethod
    def setUpClass(cls):
        pdf_path = os.path.join(TEST_DOCS, "DP Remark 2034 FP 18.pdf")
        cls.result = parse_dp_pdf(_load_pdf(pdf_path))

    def test_format_detection(self):
        self.assertEqual(self.result["report_type"], "DP_2034")

    def test_reference_no(self):
        self.assertIn("DP34202211111425031", self.result["reference_no"])

    def test_report_date(self):
        self.assertEqual(self.result["report_date"], "04/11/2022")

    def test_applicant_name(self):
        self.assertIn("Jinish", self.result["applicant_name"])

    def test_fp_no(self):
        self.assertEqual(self.result["fp_no"], "18")

    def test_tps_name(self):
        self.assertIsNotNone(self.result["tps_name"])
        self.assertIn("VILE PARLE", self.result["tps_name"])

    def test_ward(self):
        self.assertEqual(self.result["ward"], "K/W")

    def test_village(self):
        self.assertIsNotNone(self.result["village"])
        self.assertIn("VILE PARLE", self.result["village"])

    def test_zone(self):
        zone = self.result["zone_name"]
        self.assertIsNotNone(zone)
        self.assertTrue("R" in zone or "Residential" in zone)

    def test_existing_road(self):
        self.assertIsNotNone(self.result["dp_roads"])

    def test_proposed_road(self):
        self.assertEqual(self.result["proposed_road"], "NIL")

    def test_proposed_road_widening(self):
        self.assertEqual(self.result["proposed_road_widening"], "NIL")

    def test_reservations(self):
        self.assertEqual(self.result["reservations_affecting"], "NO")
        self.assertEqual(self.result["reservations_abutting"], "NO")

    def test_existing_amenities(self):
        self.assertEqual(self.result["existing_amenities_affecting"], "NO")
        self.assertEqual(self.result["existing_amenities_abutting"], "NO")

    def test_water_pipeline(self):
        wp = self.result["water_pipeline"]
        self.assertIsNotNone(wp)
        self.assertEqual(wp["diameter_mm"], 250)
        self.assertAlmostEqual(wp["distance_m"], 3.44, places=1)

    def test_sewer_line(self):
        sl = self.result["sewer_line"]
        self.assertIsNotNone(sl)
        self.assertEqual(sl["node_no"], "15240911")
        self.assertAlmostEqual(sl["distance_m"], 6.82, places=1)
        self.assertAlmostEqual(sl["invert_level_m"], 28.50, places=1)

    def test_ground_level(self):
        gl = self.result["ground_level"]
        self.assertIsNotNone(gl)
        self.assertAlmostEqual(gl["min_m"], 32.40, places=1)
        self.assertAlmostEqual(gl["max_m"], 33.00, places=1)
        self.assertEqual(gl["datum"], "THD")

    def test_rl_remarks_traffic(self):
        self.assertIsNotNone(self.result["rl_remarks_traffic"])

    def test_rl_remarks_survey(self):
        self.assertIsNotNone(self.result["rl_remarks_survey"])

    def test_pdf_text_present(self):
        self.assertIsNotNone(self.result["pdf_text"])
        self.assertGreater(len(self.result["pdf_text"]), 100)


class TestDP2034GovtSample(unittest.TestCase):
    """Tests using sample/Remark_ReportDP34202505111599881.pdf (9 pages, CTS-based)."""

    @classmethod
    def setUpClass(cls):
        pdf_path = os.path.join(SAMPLE_DIR, "Remark_ReportDP34202505111599881.pdf")
        cls.result = parse_dp_pdf(_load_pdf(pdf_path))

    def test_format_detection(self):
        self.assertEqual(self.result["report_type"], "DP_2034")

    def test_cts_nos(self):
        self.assertIsNotNone(self.result["cts_nos"])
        self.assertIn("1", self.result["cts_nos"])

    def test_has_crz_details(self):
        self.assertIsNotNone(self.result["crz_zone_details"])

    def test_has_drainage(self):
        self.assertIsNotNone(self.result["drainage"])
        self.assertIn("node_id", self.result["drainage"])

    def test_has_ep_nos(self):
        self.assertIsNotNone(self.result["ep_nos"])
        self.assertGreater(len(self.result["ep_nos"]), 0)

    def test_has_sm_nos(self):
        self.assertIsNotNone(self.result["sm_nos"])
        self.assertGreater(len(self.result["sm_nos"]), 0)

    def test_has_corrections_dcpr(self):
        self.assertIsNotNone(self.result["corrections_dcpr"])

    def test_has_modifications_sec37(self):
        self.assertIsNotNone(self.result["modifications_sec37"])

    def test_has_road_realignment(self):
        self.assertIsNotNone(self.result["road_realignment"])

    def test_has_high_voltage_line(self):
        self.assertIsNotNone(self.result["high_voltage_line"])

    def test_has_flamingo_esz(self):
        self.assertIsNotNone(self.result["flamingo_esz"])

    def test_has_buffer_sgnp(self):
        self.assertIsNotNone(self.result["buffer_sgnp"])


class TestSRDP1991Parser(unittest.TestCase):
    """Tests using test_docs/DP Remark 1991 .pdf (2 pages, CTS-based)."""

    @classmethod
    def setUpClass(cls):
        pdf_path = os.path.join(TEST_DOCS, "DP Remark 1991 .pdf")
        cls.result = parse_dp_pdf(_load_pdf(pdf_path))

    def test_format_detection(self):
        self.assertEqual(self.result["report_type"], "SRDP_1991")

    def test_reference_no(self):
        self.assertIn("SRDP202211111425043", self.result["reference_no"])

    def test_report_date(self):
        self.assertEqual(self.result["report_date"], "04/11/2022")

    def test_applicant_name(self):
        self.assertIn("Jinish", self.result["applicant_name"])

    def test_cts_nos(self):
        cts = self.result["cts_nos"]
        self.assertIsNotNone(cts)
        # CTS numbers: 852,853,855 and 854
        self.assertIn("852", cts)
        self.assertIn("854", cts)

    def test_village(self):
        self.assertIsNotNone(self.result["village"])
        self.assertIn("VILE PARLE", self.result["village"])

    def test_ward(self):
        self.assertEqual(self.result["ward"], "K/W")

    def test_zone(self):
        self.assertIn("RESIDENTIAL", self.result["zone_name"].upper())
        self.assertEqual(self.result["zone_code"], "R")

    def test_reservations(self):
        self.assertEqual(self.result["reservations_affecting"], "NO")
        self.assertEqual(self.result["reservations_abutting"], "NO")

    def test_designations(self):
        self.assertEqual(self.result["designations_affecting"], "NO")
        self.assertEqual(self.result["designations_abutting"], "NO")

    def test_dp_roads(self):
        self.assertIsNotNone(self.result["dp_roads"])
        self.assertIn("EXISTING", self.result["dp_roads"].upper())

    def test_rl_remarks_traffic(self):
        self.assertIsNotNone(self.result["rl_remarks_traffic"])

    def test_2034_fields_are_none(self):
        """1991 format should not have 2034-specific fields."""
        self.assertIsNone(self.result["fp_no"])
        self.assertIsNone(self.result["water_pipeline"])
        self.assertIsNone(self.result["sewer_line"])
        self.assertIsNone(self.result["ground_level"])
        self.assertIsNone(self.result["drainage"])
        self.assertIsNone(self.result["crz_zone_details"])

    def test_pdf_text_present(self):
        self.assertIsNotNone(self.result["pdf_text"])
        self.assertGreater(len(self.result["pdf_text"]), 100)


class TestFormatDetection(unittest.TestCase):
    """Tests for format detection edge cases."""

    def test_unknown_format(self):
        # Minimal valid PDF with blank content
        import io

        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        buf = io.BytesIO()
        writer.write(buf)
        result = parse_dp_pdf(buf.getvalue())
        self.assertEqual(result["report_type"], "UNKNOWN")

    def test_invalid_pdf(self):
        result = parse_dp_pdf(b"this is not a pdf file at all")
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
