---
name: cad-coder
description: Generate editable 2D mechanical drawings in DXF using Python ezdxf, with dimensions, stacked tolerances, roughness, datum symbols and geometric tolerance frames. Render PNG/PDF previews for inspection. Use for text-to-CAD sketches, dimensioned part drawings and DXF annotation corrections.
---

# CAD-Coder — mechanical drawing edition

Derivative of [alexzeng2014/cad-coder-skill](https://github.com/alexzeng2014/cad-coder-skill), maintained by kpdx-del. Preserve the upstream MIT license and attribution when sharing this skill.

## Work and verification

- Read supplied drawings before choosing geometry. Preserve specified dimensions and deviations; distinguish given values from design assumptions. Do not infer exact tolerances from image proportions.
- For GB drawings, use the requested standard edition and supplied textbook/reference conventions. These helpers implement drawing elements, not an automatic standards-compliance checker. Verify unfamiliar symbol requirements with authoritative references.
- Use millimetres and `new_doc()`. Nominal geometry is 1:1, dimension multiplier is 1. Default normal text is 3.5 mm and stacked deviations are 2.5 mm; use a consistent hierarchy across the sheet.
- Generate and execute a Python builder, save DXF, reopen and audit it, then render and visually inspect the whole sheet and crowded details. Fix gaps, crossings and incorrect attachments before delivery. Deliver DXF plus the builder and preview; a raster image is not editable CAD.
- For a printable sheet, draw the requested border/title block and use fixed paper/scale rendering. Leave personal fields blank unless supplied. Do not claim native DWG output or verified compatibility with a CAD application you have not tested.

Install dependencies with `python -m pip install -r <skill_dir>/requirements.txt`.

```python
import sys
sys.path.insert(0, "<skill_dir>/scripts")
from sketch_helpers import new_doc, dim_linear

def build():
    doc = new_doc()
    m = doc.modelspace()
    m.add_lwpolyline([(0,0),(60,0),(60,20),(0,20)], close=True)
    dim_linear(m, (0,0), (60,0), 12)
    return doc

if __name__ == "__main__":
    build().saveas("part.dxf")
```

Render: `python <skill_dir>/scripts/render_dxf.py part.dxf part.png`.
For physical paper: add `--paper A3 --scale 1`; PDF is also supported. Oversized drawings fail instead of silently shrinking. Use `--font` for an installed CJK font when needed; no font is bundled.

## Layout and attachment rules

- Prefer straight leaders or one elbow. First move the label/frame near its feature; do not route several bends around the drawing. Keep independent leaders, arrows and text clear of one another.
- Native LEADER vertices start at the arrow tip, followed by an optional elbow and the annotation end.
- Geometric tolerance leaders enter the **left-edge midpoint** of the frame, with a horizontal final segment. Place the frame to the right of the target; use `feature_control_frame(..., target=...)` or `frame_leader(...)`. A helper cannot choose the correct controlled feature for you.
- For derived axes/median planes, connect the frame to the appropriate size-dimension line or its extension. Use `arrow=False` for a plain extension connection; do not point at an arbitrary contour and imply a different tolerance requirement. Section views need applicable geometric tolerances too.
- For the requested chamfer-line convention, pass the real `chamfer_edge=(p1,p2)` to `chamfer_note`. Its arrow-bearing segment must be collinear with that edge's extension; target defaults to p2. Put any elbow on that extension, then use at most one horizontal segment to the label. Do not use an unrelated horizontal/vertical edge as the target.
- When a linear dimension's value is outside the measured interval, put arrow bodies outside the extension lines and tips toward the interval. `dim_linear` implements this, including reversed endpoints. Dimensions with values inside retain their normal arrow placement.
- For the supplied GB/textbook datum convention, `datum_symbol` draws a black filled triangle with its **base touching the boundary**, its outward apex connected to the boxed letter. For an axis datum, align attachment with the size dimension and suppress any ordinary arrow occupying the same position. Do not use a leader arrow instead of the datum triangle.
- `roughness_symbol` draws a material-removal symbol with Ra below the long bar. Keep the notation and symbol orientation consistent with the selected standard/reference.
- Use continuous physical edges; split only what the drawing convention requires. A slot centreline extends beyond both ends. Orient section centrelines to their corresponding section directions, and clip hatching to the actual material boundary.

## Helpers

Import from `scripts/sketch_helpers.py`:

- `new_doc(text_height=3.5, font="DejaVuSans.ttf")`: R2010, mm, CAD_MM dimension style, DIM and CENTER layers; use geometry layer 0, annotation layer DIM.
- `dim_linear(msp,p1,p2,offset,angle=0,text=None,upper=None,lower=None,text_location=None)`: native DIMENSION. Positive offset places horizontal dimensions below, vertical dimensions left. `text="%%c<>"` prefixes a diameter mark to the real measurement.
- `dim_diameter(...)`, `dim_radius(...)`, `dim_angular(msp,center,p1,p2,dist,text=None)`: native dimensions; angular helper measures the smaller angle.
- Supply both deviations as **signed** values: `upper=0.042,lower=0.026` means two positive deviations; `upper=0,lower=-0.180` means a zero upper deviation and negative lower deviation. Preserve the given values; changing typography is not a reason to change the tolerance.
- `tolerance_text(msp,insert,nominal,upper,lower,height=3.5,precision=3,rotation=0)`: editable standalone stacked MTEXT, not a measured dimension.
- `leader(msp,target,text_insert,label,height=3.5,elbow=None)`; `chamfer_note(msp,insert,size=2,angle=45,height=3.5,target=None,elbow=None,chamfer_edge=None)`.
- `roughness_symbol(msp,insert,value=3.2,angle=0,height=3.5)`; `datum_symbol(msp,boundary,label,height=3.5,side="below",filled=True)`.
- `feature_control_frame(msp,insert,characteristic,value,datum=None,height=3.5,target=None,elbow=None,arrow=True)`: supported characteristics are symmetry, cylindricity, circular_runout and flatness. Returns `(left,bottom,right,top)`. Frames are editable lines/text, not native TOLERANCE entities. `frame_leader(msp,bounds,target,...)` attaches to an existing frame.

Optional arguments after `*` in the Python signatures are keyword-only. See [the runnable example](examples/engineering_annotations.py) for attachment geometry, deviations and a hatched keyway section.

Templates in `scripts/part_templates.py`: hex_nut, stepped_shaft, flange, plate_with_holes. These are starting sketches; review dimensions and layout for the requested use.

Validation after changing helpers: `python -m unittest discover -s <skill_dir>/tests -v`. Also render the example and inspect it; numeric tests alone cannot establish readable sheet layout.
