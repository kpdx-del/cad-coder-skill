#!/usr/bin/env python
"""Render a DXF modelspace to a black-and-white PNG / PDF preview.

Auto-fit mode (default):
    python render_dxf.py part.dxf part.png

Fixed paper mode (requires DXF units = millimetres):
    python render_dxf.py part.dxf part.pdf --paper A3 --scale 1
    python render_dxf.py part.dxf part.png --paper A4 --scale 0.5

--scale 1 means 1:1, --scale 0.5 means 1:2. The drawing is centred on the
paper inside --margin (default 10 mm). If the scaled drawing plus margins
does not fit the sheet, the script raises an error instead of silently
shrinking it. This sets paper and scale only; it does not draw a border or
title block.

--font PATH.ttf overrides the preview font for every text entity (the DXF
itself is not modified). No font file is bundled.
"""
import argparse
import math
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import ezdxf  # noqa: E402
from ezdxf import bbox, disassemble  # noqa: E402
from ezdxf.addons.drawing import RenderContext, Frontend  # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402
from ezdxf.addons.drawing.config import (  # noqa: E402
    Configuration, BackgroundPolicy, ColorPolicy, TextPolicy,
)

# landscape sheets in millimetres
PAPERS = {"A3": (420.0, 297.0), "A4": (297.0, 210.0)}


def _drawing_extents(msp):
    """Bounding box including rendered dimensions, leaders and text."""
    entities = list(disassemble.recursive_decompose(msp))
    return bbox.extents(entities)


def _make_context(doc, font_path):
    if font_path is None:
        return RenderContext(doc)
    from ezdxf.fonts import fonts as ezfonts
    loaded = ezfonts.sideload_ttf(font_path, cap_height=0.7)
    family = loaded.name

    class _FontContext(RenderContext):
        def resolve_font(self, entity):
            return ezfonts.find_font_face(family)

    return _FontContext(doc)


def render(dxf_path, out_path, paper=None, scale=1.0, font=None, margin=10.0):
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    ext = _drawing_extents(msp)
    if not ext.has_data:
        raise ValueError("drawing is empty: %s" % dxf_path)

    # Outline text: vector CAD-style lettering. The FILLING policy mis-fills
    # the diameter glyph (half-disc artifact) in ezdxf 1.4.x; outlines render
    # every symbol correctly. The DXF itself keeps normal text for CAD apps.
    cfg = Configuration().with_changes(
        background_policy=BackgroundPolicy.WHITE,
        color_policy=ColorPolicy.BLACK,
        text_policy=TextPolicy.OUTLINE,
    )
    ctx = _make_context(doc, font)

    if paper is None:
        fig = plt.figure()
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()
        ax.set_xlim(ext.extmin.x, ext.extmax.x)
        ax.set_ylim(ext.extmin.y, ext.extmax.y)
        ax.set_aspect("equal")
        Frontend(ctx, MatplotlibBackend(ax), config=cfg).draw_layout(msp, finalize=True)
        fig.savefig(out_path, dpi=200, facecolor="white")
        plt.close(fig)
        print(out_path)
        return out_path

    # ---- fixed paper mode ----
    if paper not in PAPERS:
        raise ValueError("unsupported paper %r; choose from %s" % (paper, ", ".join(PAPERS)))
    if scale <= 0:
        raise ValueError("scale must be positive")
    if doc.header.get("$INSUNITS", 0) != 4:
        raise ValueError("fixed paper output requires DXF units = millimetres ($INSUNITS=4)")
    pw, ph = PAPERS[paper]
    if 2 * margin >= min(pw, ph):
        raise ValueError("margin too large for the sheet")
    win_w = (pw - 2 * margin) / scale      # model-space window, mm
    win_h = (ph - 2 * margin) / scale
    dw, dh = ext.size.x, ext.size.y
    if dw > win_w + 1e-9 or dh > win_h + 1e-9:
        raise ValueError(
            "drawing %.1f x %.1f mm at scale %g does not fit %s "
            "(available %.1f x %.1f mm model space); reduce scale or use larger paper"
            % (dw, dh, scale, paper, win_w, win_h))

    cx = (ext.extmin.x + ext.extmax.x) / 2.0
    cy = (ext.extmin.y + ext.extmax.y) / 2.0
    fig = plt.figure(figsize=(pw / 25.4, ph / 25.4))
    ax = fig.add_axes([margin / pw, margin / ph,
                       (pw - 2 * margin) / pw, (ph - 2 * margin) / ph])
    ax.set_axis_off()
    ax.set_xlim(cx - win_w / 2.0, cx + win_w / 2.0)
    ax.set_ylim(cy - win_h / 2.0, cy + win_h / 2.0)
    ax.set_aspect("equal")
    # keep the exact paper figsize and limits: no autoscale, no figure resize
    backend = MatplotlibBackend(ax, adjust_figure=False)
    Frontend(ctx, backend, config=cfg).draw_layout(msp, finalize=False)
    if str(out_path).lower().endswith(".pdf"):
        fig.savefig(out_path, facecolor="white")   # exact figsize -> exact page
    else:
        fig.savefig(out_path, dpi=200, facecolor="white")
    plt.close(fig)
    print(out_path)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dxf")
    ap.add_argument("out", help="output .png or .pdf")
    ap.add_argument("--paper", choices=sorted(PAPERS), default=None)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--font", default=None, help="TTF path overriding preview font")
    ap.add_argument("--margin", type=float, default=10.0, help="sheet margin in mm")
    args = ap.parse_args(argv)
    try:
        render(args.dxf, args.out, paper=args.paper, scale=args.scale,
               font=args.font, margin=args.margin)
    except ValueError as e:
        print("error:", e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())