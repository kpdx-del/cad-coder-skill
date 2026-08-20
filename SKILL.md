---
name: cad-coder
description: Generate editable 2D CAD sketches as DXF files from natural-language descriptions using Python ezdxf scripts, then render a PNG preview. Use when the user asks to draw, generate, or design a CAD part/sketch (flange, shaft, nut, plate, bracket, gear outline, hole patterns, etc.), wants a .dxf output, dimensioned sketches with annotations (linear/radius/diameter/angle dims, tolerances, chamfers, surface roughness), or asks for text-to-CAD / CAD-Coder style generation. Output DXF opens in AutoCAD, SolidWorks, CAXA, CATIA, UG, Onshape.
---

# CAD-Coder: text-guided DXF generation

Workflow (always in this order):

1. Parse the user description into a part type and concrete dimensions (mm). If key dimensions are missing, pick sensible engineering defaults and state them.
2. Write a Python script that builds the part with `ezdxf` and saves `<name>.dxf`. Follow the code structure below.
3. Run it, then render a preview:
   `python <skill_dir>/scripts/render_dxf.py <name>.dxf <name>.png`
4. Show the PNG to the user and report the DXF path. On any error, fix the script and re-run; never deliver unexecuted code.

Environment: `ezdxf` and `matplotlib` must be installed (`pip install ezdxf matplotlib`).

## Code structure (mirror CAD-Coder paper: imports / builder function / main)

```python
import math, ezdxf
import sys; sys.path.insert(0, r"<skill_dir>/scripts")
from sketch_helpers import *   # new_doc + annotation helpers

def build(d=10.0):             # free parameters with defaults
    doc = new_doc()            # R2010, DIM layer, linetypes set up
    msp = doc.modelspace()
    # geometry on layer 0, dimensions via helpers below
    return doc

if __name__ == "__main__":
    build().saveas("part.dxf")
```

## Annotation helpers (`scripts/sketch_helpers.py`)

- `new_doc()` - document with DIM layer and linetypes (CENTER, DASHED).
- `dim_linear(msp, p1, p2, offset, angle=0, text=None)` - linear dimension.
- `dim_diameter(msp, center, radius, angle=30, text=None)` / `dim_radius(...)` - circle dims.
- `dim_angular(msp, center, p1, p2, dist, text=None)` - angle arc + label (manual; do NOT use ezdxf add_angular_dim_2l, its renderer crashes with ZeroDivisionError).
- `tolerance_text(msp, insert, nominal, upper, lower)` - stacked tolerance MTEXT.
- `roughness_symbol(msp, insert, value=3.2, angle=0)` - Ra check-mark symbol.
- `chamfer_note(msp, insert, size=2.0)` - chamfer callout text.
- `leader(msp, target, text_insert, label)` - leader + text.

## Parameterized templates (`scripts/part_templates.py`)

Ready-made builders: `hex_nut(d, pitch)`, `stepped_shaft(segments=[(dia,len),...])`, `flange(d_outer, d_inner, n_bolts, d_bolt, d_pcd)`, `plate_with_holes(w, h, d_hole, edge, nx, ny)`.
Run directly: `python <skill_dir>/scripts/part_templates.py flange out.dxf`, or import and customize parameters from the user description. For other part types, write a new builder in the same style.

## Rules

- Units mm; geometry on layer 0, all dimensions/annotations on layer DIM.
- Use CENTER linetype for axes/pitch circles, DASHED for hidden/thread lines.
- Always add dimensions the user mentioned; add obvious primary dimensions even if not mentioned.
- Render preview with white background via render_dxf.py (already configured).
- DXF is the deliverable; keep the .py script next to it so users can tweak parameters and regenerate.
