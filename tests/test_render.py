# -*- coding: utf-8 -*-
"""Renderer regression tests: PDF paper size, overflow refusal, font override."""
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import matplotlib  # noqa: E402
from sketch_helpers import new_doc, dim_linear  # noqa: E402
from render_dxf import render  # noqa: E402


def _sample_dxf(path, w=100.0, h=50.0):
    doc = new_doc()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (w, 0), (w, h), (0, h)], close=True)
    dim_linear(m, (0, 0), (w, 0), 12)
    doc.saveas(path)
    return path


class TestRender(unittest.TestCase):
    def test_diameter_glyph_has_open_bowl_not_half_filled(self):
        from PIL import Image, ImageChops
        from typography import add_text
        with tempfile.TemporaryDirectory() as td:
            d=new_doc()
            add_text(d.modelspace(),"Ø",(0,0),height=10)
            source=os.path.join(td,"glyph.dxf"); target=os.path.join(td,"glyph.png")
            d.saveas(source); render(source,target)
            with Image.open(target) as im:
                gray=im.convert("L")
                ink=ImageChops.invert(gray).point(lambda v:255 if v>80 else 0)
                crop=ink.crop(ink.getbbox())
                ratio=sum(v>0 for v in crop.getdata())/(crop.width*crop.height)
                self.assertGreater(ratio,.01)
                self.assertLess(ratio,.30,"Ø bowl was filled by the contour-nesting heuristic")

    def test_png_autofit(self):
        with tempfile.TemporaryDirectory() as td:
            dxf = _sample_dxf(os.path.join(td, "s.dxf"))
            png = os.path.join(td, "s.png")
            render(dxf, png)
            self.assertGreater(os.path.getsize(png), 1000)

    def test_pdf_a3_exact_page_size(self):
        with tempfile.TemporaryDirectory() as td:
            dxf = _sample_dxf(os.path.join(td, "s.dxf"))
            pdf = os.path.join(td, "s.pdf")
            render(dxf, pdf, paper="A3", scale=1.0)
            with open(pdf, "rb") as fh:
                data = fh.read()
            boxes = re.findall(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", data)
            self.assertTrue(boxes, "no MediaBox found in PDF")
            w_pt, h_pt = float(boxes[0][0]), float(boxes[0][1])
            self.assertAlmostEqual(w_pt, 420.0 / 25.4 * 72.0, delta=1.0)
            self.assertAlmostEqual(h_pt, 297.0 / 25.4 * 72.0, delta=1.0)

    def test_pdf_a4_exact_page_size(self):
        with tempfile.TemporaryDirectory() as td:
            dxf = _sample_dxf(os.path.join(td, "s.dxf"))
            pdf = os.path.join(td, "s.pdf")
            render(dxf, pdf, paper="A4", scale=1.0)
            with open(pdf, "rb") as fh:
                data = fh.read()
            boxes = re.findall(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", data)
            self.assertTrue(boxes)
            self.assertAlmostEqual(float(boxes[0][0]), 297.0 / 25.4 * 72.0, delta=1.0)
            self.assertAlmostEqual(float(boxes[0][1]), 210.0 / 25.4 * 72.0, delta=1.0)

    def test_overflow_raises_instead_of_shrinking(self):
        with tempfile.TemporaryDirectory() as td:
            dxf = _sample_dxf(os.path.join(td, "s.dxf"), w=300.0, h=200.0)
            with self.assertRaises(ValueError):
                render(dxf, os.path.join(td, "s.pdf"), paper="A4", scale=1.0)

    def test_scale_half_fits(self):
        with tempfile.TemporaryDirectory() as td:
            dxf = _sample_dxf(os.path.join(td, "s.dxf"), w=300.0, h=200.0)
            pdf = os.path.join(td, "s.pdf")
            render(dxf, pdf, paper="A4", scale=0.5)   # 1:2 -> 150x100 mm
            self.assertGreater(os.path.getsize(pdf), 1000)

    def test_wrong_units_rejected_for_paper(self):
        import ezdxf
        with tempfile.TemporaryDirectory() as td:
            dxf = _sample_dxf(os.path.join(td, "s.dxf"))
            doc = ezdxf.readfile(dxf)
            doc.header["$INSUNITS"] = 0
            doc.saveas(dxf)
            with self.assertRaises(ValueError):
                render(dxf, os.path.join(td, "s.pdf"), paper="A3", scale=1.0)

    def test_font_override(self):
        font = os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans.ttf")
        with tempfile.TemporaryDirectory() as td:
            dxf = _sample_dxf(os.path.join(td, "s.dxf"))
            png = os.path.join(td, "s.png")
            render(dxf, png, font=font)
            self.assertGreater(os.path.getsize(png), 1000)


if __name__ == "__main__":
    unittest.main()
