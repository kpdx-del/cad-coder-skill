#!/usr/bin/env python
"""Render a DXF modelspace to PNG (white background, dark lines)."""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy


def render(dxf_path, png_path):
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    fig = plt.figure()
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    cfg = Configuration().with_changes(background_policy=BackgroundPolicy.WHITE)
    Frontend(ctx, out, config=cfg).draw_layout(msp, finalize=True)
    fig.savefig(png_path, dpi=200, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(png_path)


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2])
