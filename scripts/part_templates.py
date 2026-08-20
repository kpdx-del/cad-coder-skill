#!/usr/bin/env python
"""Parameterized CAD part templates (ezdxf). Units: mm.
Geometry on layer 0, dimensions on layer DIM."""

import math
import ezdxf


def _new_doc():
    doc = ezdxf.new("R2010", setup=True)
    doc.layers.add("DIM", color=3)
    return doc


def hex_nut(d=10.0, pitch=1.5):
    """Hex nut front view. d: nominal thread diameter (mm)."""
    de = 1.8 * d
    s = de / 2.0
    w = s * math.sqrt(3)
    doc = _new_doc()
    msp = doc.modelspace()
    pts = [(s * math.cos(math.radians(30 + 60 * i)),
            s * math.sin(math.radians(30 + 60 * i))) for i in range(6)]
    msp.add_lwpolyline(pts, close=True)
    msp.add_circle((0, 0), d / 2.0)
    msp.add_circle((0, 0), (d + pitch * 1.0825) / 2.0,
                   dxfattribs={"linetype": "DASHED"})
    msp.add_linear_dim(base=(0, -s - 10), p1=(-w / 2, 0), p2=(w / 2, 0),
                       angle=0, dxfattribs={"layer": "DIM"}).render()
    msp.add_diameter_dim(center=(0, 0), radius=d / 2.0,
                         angle=45, dxfattribs={"layer": "DIM"}).render()
    return doc


def stepped_shaft(segments=None):
    """Stepped shaft side view. segments: list of (diameter, length)."""
    if segments is None:
        segments = [(20.0, 30.0), (30.0, 40.0), (16.0, 25.0)]
    doc = _new_doc()
    msp = doc.modelspace()
    max_r = max(s[0] for s in segments) / 2.0
    x = 0.0
    top, bot = [], []
    for dia, ln in segments:
        r = dia / 2.0
        top += [(x, r), (x + ln, r)]
        bot = [(x + ln, -r), (x, -r)] + bot
        msp.add_linear_dim(base=(0, -max_r - 12), p1=(x, 0), p2=(x + ln, 0),
                           angle=0, dxfattribs={"layer": "DIM"}).render()
        msp.add_diameter_dim(center=(x + ln / 2, 0), radius=r,
                             angle=90, dxfattribs={"layer": "DIM"}).render()
        x += ln
    msp.add_lwpolyline(top + bot, close=True)
    msp.add_line((0, 0), (x, 0), dxfattribs={"linetype": "CENTER"})
    return doc


def flange(d_outer=100.0, d_inner=40.0, n_bolts=4, d_bolt=10.0, d_pcd=70.0):
    """Flange front view with bolt circle."""
    doc = _new_doc()
    msp = doc.modelspace()
    msp.add_circle((0, 0), d_outer / 2.0)
    msp.add_circle((0, 0), d_inner / 2.0)
    msp.add_circle((0, 0), d_pcd / 2.0, dxfattribs={"linetype": "CENTER"})
    for i in range(n_bolts):
        a = math.radians(90 + 360.0 * i / n_bolts)
        msp.add_circle((d_pcd / 2 * math.cos(a), d_pcd / 2 * math.sin(a)), d_bolt / 2.0)
    msp.add_diameter_dim(center=(0, 0), radius=d_outer / 2.0, angle=30,
                         dxfattribs={"layer": "DIM"}).render()
    msp.add_diameter_dim(center=(0, 0), radius=d_inner / 2.0, angle=150,
                         dxfattribs={"layer": "DIM"}).render()
    msp.add_diameter_dim(center=(0, 0), radius=d_pcd / 2.0, angle=-60,
                         dxfattribs={"layer": "DIM"}).render()
    return doc


def plate_with_holes(w=120.0, h=80.0, d_hole=8.0, edge=15.0, nx=3, ny=2):
    """Rectangular plate with a grid of through holes."""
    doc = _new_doc()
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (w, 0), (w, h), (0, h)], close=True)
    for i in range(nx):
        for j in range(ny):
            x = edge + i * (w - 2 * edge) / max(nx - 1, 1)
            y = edge + j * (h - 2 * edge) / max(ny - 1, 1)
            msp.add_circle((x, y), d_hole / 2.0)
    msp.add_linear_dim(base=(0, -15), p1=(0, 0), p2=(w, 0), angle=0,
                       dxfattribs={"layer": "DIM"}).render()
    msp.add_linear_dim(base=(-15, 0), p1=(0, 0), p2=(0, h), angle=90,
                       dxfattribs={"layer": "DIM"}).render()
    return doc


TEMPLATES = {
    "hex_nut": hex_nut,
    "stepped_shaft": stepped_shaft,
    "flange": flange,
    "plate_with_holes": plate_with_holes,
}

if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "flange"
    out = sys.argv[2] if len(sys.argv) > 2 else name + ".dxf"
    TEMPLATES[name]().saveas(out)
    print(out)
