# -*- coding: utf-8 -*-
"""Regression tests for sketch_helpers (numbers, signs, attachment geometry,
DXF save/reload). Run: python -m unittest discover -s tests -v"""
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import ezdxf  # noqa: E402
from sketch_helpers import (  # noqa: E402
    new_doc, dim_linear, dim_angular, tolerance_text, leader, chamfer_note,
    roughness_symbol, datum_symbol, feature_control_frame, frame_leader,
    audit_annotations,
)
import part_templates  # noqa: E402


def _block_texts(dim):
    blk = dim.doc.blocks.get(dim.dimension.dxf.geometry)
    out = []
    for e in blk:
        if e.dxftype() == "MTEXT":
            out.append(e.text)
        elif e.dxftype() == "TEXT":
            out.append(e.dxf.text)
    return out


def _arrow_inserts(dim):
    blk = dim.doc.blocks.get(dim.dimension.dxf.geometry)
    return [e for e in blk if e.dxftype() == "INSERT"]


class TestDocument(unittest.TestCase):
    def test_units_layers_dimstyle(self):
        doc = new_doc()
        self.assertEqual(doc.header["$INSUNITS"], 4)
        self.assertEqual(doc.header["$MEASUREMENT"], 1)
        for layer in ("0", "THIN", "CENTER", "HIDDEN", "DIM", "HATCH"):
            self.assertIn(layer, doc.layers)
        self.assertEqual(doc.layers.get("0").dxf.lineweight, 50)
        style = doc.dimstyles.get("CAD_MM")
        self.assertEqual(style.dxf.dimlfac, 1)
        self.assertEqual(style.dxf.dimdsep, ord("."))
        self.assertEqual(style.dxf.dimtxt, 3.5)

    def test_text_height_and_font(self):
        doc = new_doc(text_height=5, font="simhei.ttf")
        self.assertEqual(doc.dimstyles.get("CAD_MM").dxf.dimtxt, 5)
        self.assertEqual(doc.styles.get("CAD_TEXT").dxf.font, "simhei.ttf")


class TestLinearDimension(unittest.TestCase):
    def test_measurement_roundtrip(self):
        doc = new_doc()
        dim_linear(doc.modelspace(), (0, 0), (35, 0), 12)
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "t.dxf")
            doc.saveas(p)
            doc2 = ezdxf.readfile(p)
            dims = list(doc2.modelspace().query("DIMENSION"))
            self.assertEqual(len(dims), 1)
            self.assertAlmostEqual(dims[0].get_measurement(), 35.0, places=6)
            self.assertEqual(doc2.header["$INSUNITS"], 4)

    def test_tolerance_both_positive(self):
        doc = new_doc()
        d = dim_linear(doc.modelspace(), (0, 0), (35, 0), 12,
                       upper=0.042, lower=0.026)
        self.assertEqual(d.get("dimtol"), 1)
        self.assertAlmostEqual(d.get("dimtp"), 0.042)
        self.assertAlmostEqual(d.get("dimtm"), -0.026)  # DXF stores negated lower
        txt = " ".join(_block_texts(d))
        self.assertIn("+0.042", txt)
        self.assertIn("+0.026", txt)   # signed lower, not forced negative
        self.assertNotIn(",", txt)     # decimal point, not comma
        self.assertIn("35", txt)       # mm 1:1, not 3500

    def test_tolerance_zero_upper_negative_lower(self):
        doc = new_doc()
        d = dim_linear(doc.modelspace(), (0, 0), (35, 0), 12,
                       upper=0, lower=-0.180)
        txt = " ".join(_block_texts(d))
        self.assertIn("0.000", txt)
        self.assertIn("-0.180", txt)

    def test_deviations_required_together(self):
        doc = new_doc()
        with self.assertRaises(ValueError):
            dim_linear(doc.modelspace(), (0, 0), (35, 0), 12, upper=0.02)
        with self.assertRaises(ValueError):
            dim_linear(doc.modelspace(), (0, 0), (35, 0), 12, lower=-0.02)

    def test_deviations_order(self):
        doc = new_doc()
        with self.assertRaises(ValueError):
            dim_linear(doc.modelspace(), (0, 0), (35, 0), 12,
                       upper=-0.05, lower=0.02)

    def test_outside_value_keeps_arrows_at_extension_lines(self):
        for p1, p2 in (((0, 0), (10, 0)), ((10, 0), (0, 0))):  # reversed order too
            doc = new_doc()
            d = dim_linear(doc.modelspace(), p1, p2, 8,
                           text_location=(25, -8))
            arrows = sorted(_arrow_inserts(d), key=lambda e: e.dxf.insert.x)
            self.assertEqual(len(arrows), 2)
            self.assertAlmostEqual(arrows[0].dxf.insert.x, 0.0)
            self.assertAlmostEqual(arrows[1].dxf.insert.x, 10.0)
            # native geometry stays connected: the audit finds no gap
            self.assertEqual(audit_annotations(doc.modelspace()), [])
        # Outside text: left arrow points right, right arrow points left.
        doc = new_doc()
        d = dim_linear(doc.modelspace(), (0, 0), (10, 0), 8,
                       text_location=(25, -8))
        arrows = sorted(_arrow_inserts(d), key=lambda e: e.dxf.insert.x)
        self.assertAlmostEqual(arrows[0].dxf.rotation % 360, 0.0)
        self.assertAlmostEqual(arrows[1].dxf.rotation % 360, 180.0)

    def test_inside_value_arrows_unchanged(self):
        doc = new_doc()
        d = dim_linear(doc.modelspace(), (0, 0), (60, 0), 12)
        arrows = sorted(_arrow_inserts(d), key=lambda e: e.dxf.insert.x)
        self.assertAlmostEqual(arrows[0].dxf.rotation % 360, 180.0)
        self.assertAlmostEqual(arrows[1].dxf.rotation % 360, 0.0)

    def test_diameter_prefix_keeps_measurement(self):
        doc = new_doc()
        d = dim_linear(doc.modelspace(), (0, -15), (0, 15), 20, angle=90,
                       text="%%c<>", upper=0, lower=-0.021)
        self.assertAlmostEqual(d.dimension.get_measurement(), 30.0)
        self.assertEqual(d.get("dimpost"), "%%c<>")


class TestAngular(unittest.TestCase):
    def test_native_three_point(self):
        doc = new_doc()
        d = dim_angular(doc.modelspace(), (0, 0), (30, 0), (0, 30), 20)
        self.assertAlmostEqual(d.dimension.get_measurement(), 90.0, places=6)
        self.assertIn("90", " ".join(_block_texts(d)))

    def test_smaller_angle_and_degenerate(self):
        doc = new_doc()
        d = dim_angular(doc.modelspace(), (0, 0), (0, 30), (30, 0), 20)
        self.assertAlmostEqual(d.dimension.get_measurement(), 90.0, places=6)
        with self.assertRaises(ValueError):
            dim_angular(doc.modelspace(), (0, 0), (0, 0), (30, 0), 20)


class TestLeadersAndChamfer(unittest.TestCase):
    def test_leader_vertices_start_at_arrow_tip(self):
        doc = new_doc()
        m = doc.modelspace()
        leader(m, (5, 5), (20, 12), "NOTE", elbow=(12, 12))
        ld = m.query("LEADER")[0]
        verts = [tuple(v) for v in ld.vertices]
        self.assertEqual(verts[0], (5, 5, 0))
        self.assertEqual(verts[1], (12, 12, 0))
        self.assertEqual(verts[2], (20, 12, 0))

    def test_chamfer_collinear_valid(self):
        doc = new_doc()
        m = doc.modelspace()
        chamfer_note(m, (-14, 9), size=2, target=(0, 13), elbow=(-4, 9),
                     chamfer_edge=((0, 13), (2, 15)))
        ld = m.query("LEADER")[0]
        self.assertEqual(tuple(ld.vertices[0]), (0, 13, 0))
        labels = [t.dxf.text for t in m.query("TEXT")]
        self.assertIn("C2", labels)

    def test_chamfer_noncollinear_raises(self):
        doc = new_doc()
        with self.assertRaises(ValueError):
            chamfer_note(doc.modelspace(), (10, 20), target=(2, 15),
                         elbow=(10, 15),  # horizontal, not along the 45deg edge
                         chamfer_edge=((0, 13), (2, 15)))

    def test_chamfer_internal_target_raises(self):
        doc = new_doc()
        with self.assertRaises(ValueError):
            chamfer_note(doc.modelspace(), (10, 20), target=(1, 14),
                         elbow=(5, 18), chamfer_edge=((0, 13), (2, 15)))

    def test_chamfer_nonhorizontal_final_raises(self):
        doc = new_doc()
        with self.assertRaises(ValueError):
            chamfer_note(doc.modelspace(), (10, 25), target=(2, 15),
                         elbow=(6, 19), chamfer_edge=((0, 13), (2, 15)))


class TestFramesDatumRoughness(unittest.TestCase):
    def test_frame_bounds_and_leader_attachment(self):
        doc = new_doc()
        m = doc.modelspace()
        bounds = feature_control_frame(m, (45, -30), "circular_runout", 0.025,
                                       "A", target=(35, 0))
        left, bottom, right, top = bounds
        self.assertGreater(right, left)
        self.assertAlmostEqual(top - bottom, 7.0)
        ld = m.query("LEADER")[0]
        verts = [tuple(v) for v in ld.vertices]
        self.assertEqual(verts[0], (35, 0, 0))
        self.assertAlmostEqual(verts[-1][0], left)
        self.assertAlmostEqual(verts[-1][1], (bottom + top) / 2)
        self.assertAlmostEqual(verts[-2][1], verts[-1][1])  # horizontal final
        texts = [t.dxf.text for t in m.query("TEXT")]
        self.assertIn("0.025", texts)
        self.assertIn("A", texts)

    def test_surface_leader_approach_perpendicular(self):
        doc = new_doc()
        m = doc.modelspace()
        b = feature_control_frame(m, (75, 32), "flatness", 0.01, target=(65, 20))
        ld = m.query("LEADER")[0]
        v = [tuple(p) for p in ld.vertices]
        self.assertAlmostEqual(v[0][0], v[1][0])   # vertical (normal) approach
        self.assertAlmostEqual(v[1][1], v[2][1])   # horizontal final segment
        self.assertAlmostEqual(v[2][0], b[0])      # enters left edge
        self.assertAlmostEqual(v[2][1], (b[1] + b[3]) / 2)

    def test_frame_plain_extension_no_arrow(self):
        doc = new_doc()
        m = doc.modelspace()
        feature_control_frame(m, (155, -55), "symmetry", 0.02, "A",
                              target=(150, -12.5), arrow=False)
        self.assertEqual(len(m.query("LEADER")), 0)
        self.assertTrue(len(m.query("LWPOLYLINE")) >= 2)

    def test_unsupported_characteristic_raises(self):
        doc = new_doc()
        with self.assertRaises(ValueError):
            feature_control_frame(doc.modelspace(), (0, 0), "position", 0.1)

    def test_all_supported_characteristics_draw(self):
        doc = new_doc()
        m = doc.modelspace()
        for i, ch in enumerate(("symmetry", "cylindricity",
                                "circular_runout", "flatness")):
            b = feature_control_frame(m, (0, -20 * i), ch, 0.02)
            self.assertGreater(b[2], b[0])

    def test_datum_solid_base_on_boundary(self):
        doc = new_doc()
        m = doc.modelspace()
        datum_symbol(m, (-35, -20), "A")
        solids = list(m.query("SOLID"))
        self.assertEqual(len(solids), 1)
        s = solids[0]
        self.assertAlmostEqual(s.dxf.vtx0[1], -20.0)  # base touches boundary
        self.assertAlmostEqual(s.dxf.vtx1[1], -20.0)
        self.assertLess(s.dxf.vtx2[1], -20.0)         # apex outward (below)
        self.assertIn("A", [t.dxf.text for t in m.query("TEXT")])

    def test_roughness_closed_symbol(self):
        doc = new_doc()
        m = doc.modelspace()
        roughness_symbol(m, (75, 20), value=1.6)
        self.assertEqual(len(m.query("SOLID")), 0)    # removal bar, no filled triangle
        self.assertEqual(len(m.query("LINE")), 1)
        self.assertIn("Ra 1.6", [t.dxf.text for t in m.query("TEXT")])
        self.assertEqual(len(m.query("LWPOLYLINE")), 1)  # legs + bar

    def test_suppress_arrow_blanks_end_and_keeps_full_line(self):
        doc = new_doc()
        m = doc.modelspace()
        d = dim_linear(m, (40, -20), (40, 20), 75, angle=90, text="%%c<>",
                       upper=0.042, lower=0.026, suppress_arrow=1)
        blk = doc.blocks.get(d.dimension.dxf.geometry)
        inserts = [e for e in blk if e.dxftype() == "INSERT"]
        # one explicit blank (_NONE) + one visible filled arrow
        names = sorted(e.dxf.name for e in inserts)
        self.assertEqual(names, ["_CLOSEDFILLED", "_NONE"])
        visible = [e for e in inserts if e.dxf.name == "_CLOSEDFILLED"]
        self.assertAlmostEqual(visible[0].dxf.insert.y, 20.0)
        # the dimension line still reaches the blank (datum) end, no gap
        vlines = [e for e in blk if e.dxftype() == "LINE"
                  and abs(e.dxf.start.x + 35) < 1e-6
                  and abs(e.dxf.end.x + 35) < 1e-6]
        self.assertEqual(len(vlines), 1)
        ys = sorted((vlines[0].dxf.start.y, vlines[0].dxf.end.y))
        self.assertAlmostEqual(ys[0], -20.0)           # line reaches datum base
        self.assertAlmostEqual(ys[1], 17.5)
        self.assertEqual(audit_annotations(m), [])

    def test_suppress_arrow_invalid_end_raises(self):
        doc = new_doc()
        with self.assertRaises(ValueError):
            dim_linear(doc.modelspace(), (0, 0), (35, 0), 12, suppress_arrow=3)

    def test_tolerance_text_stacked(self):
        doc = new_doc()
        m = doc.modelspace()
        tolerance_text(m, (0, 0), 50, 0.05, -0.02)
        mt = m.query("MTEXT")[0]
        self.assertIn("\\S", mt.text)
        self.assertIn("+0.050", mt.text)
        self.assertIn("-0.020", mt.text)


class TestAudit(unittest.TestCase):
    def _clean_sheet(self):
        doc = new_doc()
        m = doc.modelspace()
        dim_linear(m, (0, 0), (60, 0), 12)
        dim_linear(m, (40, -20), (40, 20), 30, angle=90, suppress_arrow=1)
        leader(m, (5, 5), (20, 12), "NOTE", elbow=(12, 12))
        return doc

    def test_clean_sheet_passes(self):
        self.assertEqual(audit_annotations(self._clean_sheet().modelspace()), [])

    def test_missing_arrow_is_detected(self):
        doc = self._clean_sheet()
        dim = list(doc.modelspace().query("DIMENSION"))[0]
        blk = doc.blocks.get(dim.dxf.geometry)
        arrow = next(e for e in blk if e.dxftype() == "INSERT")
        blk.delete_entity(arrow)
        problems = audit_annotations(doc.modelspace())
        self.assertTrue(any("arrow block refs" in p for p in problems))

    def test_shortened_dimension_line_is_detected(self):
        doc = self._clean_sheet()
        dim = list(doc.modelspace().query("DIMENSION"))[0]
        blk = doc.blocks.get(dim.dxf.geometry)
        line = next(e for e in blk if e.dxftype() == "LINE"
                    and e.dxf.start.y == e.dxf.end.y)
        # pull the start inward by an extra arrow length, leaving a gap
        line.dxf.start = (line.dxf.start[0] + 5.0, line.dxf.start[1])
        problems = audit_annotations(doc.modelspace())
        self.assertTrue(any("does not reach" in p for p in problems))

    def test_leader_flag_with_none_arrow_is_detected(self):
        doc = new_doc()
        m = doc.modelspace()
        ld = m.add_leader(vertices=[(0, 0), (5, 5), (10, 5)],
                          override={"dimldrblk": "NONE", "dimasz": 2.5})
        self.assertTrue(bool(ld.dxf.has_arrowhead))
        problems = audit_annotations(m)
        self.assertTrue(any("resolves to no arrow" in p for p in problems))


class TestTemplates(unittest.TestCase):
    def test_templates_units_and_reload(self):
        for name, fn in part_templates.TEMPLATES.items():
            doc = fn()
            self.assertEqual(doc.header["$INSUNITS"], 4, name)
            with tempfile.TemporaryDirectory() as td:
                p = os.path.join(td, name + ".dxf")
                doc.saveas(p)
                doc2 = ezdxf.readfile(p)
                self.assertEqual(len(doc2.modelspace()), len(doc.modelspace()))

    def test_flange_measurement_mm(self):
        doc = part_templates.flange(d_outer=100.0)
        meas = [d.get_measurement() for d in doc.modelspace().query("DIMENSION")]
        self.assertTrue(any(abs(v - 100.0) < 1e-6 for v in meas))


if __name__ == "__main__":
    unittest.main()
