#!/usr/bin/env python
"""Sketch helpers: DXF primitives, dimensions, and engineering annotations.
Import this in generated scripts: from sketch_helpers import *
All geometry in mm. Dimensions/annotations go on layer DIM (green)."""

import math
import ezdxf


def new_doc():
    doc = ezdxf.new("R2010", setup=True)
    doc.layers.add("DIM", color=3)
    return doc


def dim_linear(msp, p1, p2, offset, angle=0, text=None):
    """Linear dimension. offset: distance of dim line from geometry (signed)."""
    override = {}
    if text is not None:
        override["DIMPOST"] = text
    d = msp.add_linear_dim(base=(p1[0], p1[1] - offset) if angle == 0 else (p1[0] - offset, p1[1]),
                           p1=p1, p2=p2, angle=angle, override=override,
                           dxfattribs={"layer": "DIM"})
    d.render()
    return d


def dim_diameter(msp, center, radius, angle=30, text=None):
    override = {}
    if text is not None:
        override["DIMPOST"] = text
    d = msp.add_diameter_dim(center=center, radius=radius, angle=angle,
                             override=override, dxfattribs={"layer": "DIM"})
    d.render()
    return d


def dim_radius(msp, center, radius, angle=30, text=None):
    override = {}
    if text is not None:
        override["DIMPOST"] = text
    d = msp.add_radius_dim(center=center, radius=radius, angle=angle,
                           override=override, dxfattribs={"layer": "DIM"})
    d.render()
    return d


def dim_angular(msp, center, p1, p2, dist, text=None):
    """Manual angle annotation (ezdxf angular-dim renderer has a zero-division bug).
    Draws an arc of radius dist between rays center->p1 and center->p2 with a label."""
    a1 = math.degrees(math.atan2(p1[1] - center[1], p1[0] - center[0])) % 360
    a2 = math.degrees(math.atan2(p2[1] - center[1], p2[0] - center[0])) % 360
    span = (a2 - a1) % 360
    if span > 180:
        a1, a2 = a2, a1
        span = 360 - span
    if a2 < a1:
        a2 += 360
    msp.add_arc(center=center, radius=dist, start_angle=a1, end_angle=a2,
                dxfattribs={"layer": "DIM"})
    amid = math.radians((a1 + a2) / 2.0)
    label = text if text is not None else "%g deg" % round(span, 2)
    msp.add_text(label, height=max(2.5, dist * 0.18),
                 dxfattribs={"layer": "DIM",
                             "insert": (center[0] + (dist + 3) * math.cos(amid),
                                        center[1] + (dist + 3) * math.sin(amid))})

def tolerance_text(msp, insert, nominal, upper, lower, height=3.5):
    """Bilateral tolerance as stacked MTEXT, e.g. 50 +0.05/-0.02."""
    up = ("%+.3f" % upper).rstrip("0").rstrip(".")
    lo = ("%+.3f" % lower).rstrip("0").rstrip(".")
    body = "{\\C1;%s}\\H0.7x;{\\S%s^ %s;}" % (nominal, up, lo)
    return msp.add_mtext(body, dxfattribs={
        "layer": "DIM", "char_height": height, "insert": insert})


def roughness_symbol(msp, insert, value=3.2, angle=0.0, height=3.5):
    """Surface roughness: check-mark symbol with Ra value text."""
    import math
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    def rot(p):
        return (insert[0] + p[0] * ca - p[1] * sa,
                insert[1] + p[0] * sa + p[1] * ca)
    h = height
    pts = [rot((0, 0)), rot((h * 0.35, h * 0.8)), rot((h * 1.1, h * 0.8))]
    msp.add_lwpolyline(pts, dxfattribs={"layer": "DIM"})
    msp.add_text("Ra %.1f" % value, height=height * 0.6,
                 dxfattribs={"layer": "DIM",
                             "insert": rot((h * 0.5, h * 1.0)),
                             "rotation": angle})


def chamfer_note(msp, insert, size=2.0, angle=45, height=3.5):
    """Chamfer callout text like C2 or 2x30deg."""
    if angle == 45:
        label = "C%g" % size
    else:
        label = "%gx%g\\U+00B0" % (size, angle)
    msp.add_text(label, height=height, dxfattribs={"layer": "DIM", "insert": insert})


def leader(msp, target, text_insert, label, height=3.5):
    """Simple leader line with text label pointing at target."""
    msp.add_leader(vertices=[text_insert, target], dxfattribs={"layer": "DIM"})
    msp.add_text(label, height=height,
                 dxfattribs={"layer": "DIM", "insert": text_insert})
