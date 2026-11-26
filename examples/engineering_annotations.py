#!/usr/bin/env python
"""Runnable engineering-annotation demo (synthetic values, no personal data).

    python examples/engineering_annotations.py out

Produces out/engineering_annotations.dxf / .png / .pdf (A4, 1:1).
Demonstrates: signed stacked deviations, diameter prefixes, outside-value
arrow flipping, a validated chamfer leader, datum triangle, roughness
symbols, geometric tolerance frames (arrow and plain extension attachment),
a hatched keyway section and GB-ish layers/lineweights.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

from sketch_helpers import (  # noqa: E402
    new_doc, dim_linear, tolerance_text, chamfer_note, roughness_symbol,
    datum_symbol, feature_control_frame, audit_annotations,
)
from render_dxf import render  # noqa: E402


def build():
    doc = new_doc()
    m = doc.modelspace()

    # ---- main view: stepped shaft, chamfer C2 at the left top corner ----
    outline = [(0, -15), (0, 13), (2, 15), (40, 15), (40, 20), (90, 20),
               (90, 12.5), (125, 12.5), (125, -12.5), (90, -12.5),
               (90, -20), (40, -20), (40, -15)]
    m.add_lwpolyline(outline, close=True)
    m.add_line((-5, 0), (130, 0), dxfattribs={"layer": "CENTER"})

    # length chain + total
    dim_linear(m, (0, -15), (40, -15), 13)
    dim_linear(m, (40, -20), (90, -20), 8)
    dim_linear(m, (90, -12.5), (125, -12.5), 15.5)
    dim_linear(m, (0, -15), (125, -12.5), 25)

    # diameters as vertical linear dims with %%c prefix and deviations
    dim_linear(m, (0, -15), (0, 15), 20, angle=90, text="%%c<>",
               upper=0, lower=-0.021)
    d40 = dim_linear(m, (40, -20), (40, 20), 75, angle=90, text="%%c<>",
                     upper=0.042, lower=0.026, suppress_arrow=1)  # two positive deviations
    d25 = dim_linear(m, (125, -12.5), (125, 12.5), -25, angle=90, text="%%c<>",
                     upper=0, lower=-0.021, suppress_arrow=1)

    # datum A aligned with the phi40 size dimension (axis datum); the blank
    # end (suppress_arrow=1) leaves the dimension line full to the triangle
    # base, so the datum triangle sits flush with no arrow-length gap
    datum_symbol(m, (-35, -20), "A")

    # chamfer note: arrow segment collinear with the real chamfer extension
    chamfer_note(m, (-14, 9), size=2, target=(0, 13), elbow=(-4, 9),
                 chamfer_edge=((0, 13), (2, 15)))

    # flatness on the phi40 surface: frame placed to the RIGHT of the target
    # so the auto elbow gives a vertical (surface-normal) arrow approach
    feature_control_frame(m, (75, 32), "flatness", 0.01, target=(65, 20))
    roughness_symbol(m, (75, 20), value=1.6)
    roughness_symbol(m, (105, 12.5), value=3.2)

    # ---- keyway section of the phi25 step (hatched material) ----
    cx = 170.0
    r = 12.5
    half_w, depth = 4.0, 4.0
    y_side = math.sqrt(r * r - half_w * half_w)      # 11.8427
    y_bot = r - depth                                # 8.5
    a1 = math.degrees(math.atan2(y_side, half_w))    # 71.337 deg
    a2 = 180.0 - a1
    m.add_arc((cx, 0), r, a2, a1)                    # long way around
    m.add_line((cx - half_w, y_side), (cx - half_w, y_bot))
    m.add_line((cx - half_w, y_bot), (cx + half_w, y_bot))
    m.add_line((cx + half_w, y_bot), (cx + half_w, y_side))
    m.add_line((cx - 18, 0), (cx + 18, 0), dxfattribs={"layer": "CENTER"})
    m.add_line((cx, -18), (cx, 18), dxfattribs={"layer": "CENTER"})

    hatch = m.add_hatch(color=8, dxfattribs={"layer": "HATCH"})
    hatch.set_pattern_fill("ANSI31", scale=0.5)
    path = hatch.paths.add_edge_path()
    path.add_line((cx - half_w, y_side), (cx - half_w, y_bot))
    path.add_line((cx - half_w, y_bot), (cx + half_w, y_bot))
    path.add_line((cx + half_w, y_bot), (cx + half_w, y_side))
    # geometric arc is CCW start->end; a2->a1 is the LONG way around the
    # material, traversed clockwise (ccw=False) to close the path
    path.add_arc((cx, 0), r, a2, a1, ccw=False)

    # keyway width 8, value outside -> arrows flip outside, tips in; extend
    # the dimension line out to the value so it reads as one annotation
    dim_linear(m, (cx - half_w, y_bot), (cx + half_w, y_bot), -14,
               text_location=(185, 22.5))
    m.add_line((cx + half_w, 22.5), (184, 22.5), dxfattribs={"layer": "DIM"})

    # circular runout of the phi25 surface about datum A: leader arrow aligned
    # with the phi25 size dimension; the blank end (suppress_arrow=1) leaves
    # one arrow at that attachment, supplied by the runout leader
    feature_control_frame(m, (155, -55), "circular_runout", 0.025, "A",
                          target=(150, -12.5), arrow=True)

    # standalone stacked tolerance text (editable MTEXT, not a dimension)
    tolerance_text(m, (130, -58), 50, 0.05, -0.02)

    m.add_text("ANNOTATION DEMO - SYNTHETIC VALUES", height=4,
               dxfattribs={"layer": "DIM", "insert": (-35, -65)})
    m.add_text("KEYWAY SECTION", height=3.5,
               dxfattribs={"layer": "DIM", "insert": (158, -25)})

    # fail loudly on any missing arrow or incomplete dimension line
    problems = audit_annotations(m)
    if problems:
        raise AssertionError("annotation geometry audit failed:\n  - "
                             + "\n  - ".join(problems))
    return doc


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "out"
    os.makedirs(out_dir, exist_ok=True)
    dxf = os.path.join(out_dir, "engineering_annotations.dxf")
    build().saveas(dxf)
    print(dxf)
    render(dxf, os.path.join(out_dir, "engineering_annotations.png"))
    render(dxf, os.path.join(out_dir, "engineering_annotations.pdf"),
           paper="A4", scale=1.0)


if __name__ == "__main__":
    main()