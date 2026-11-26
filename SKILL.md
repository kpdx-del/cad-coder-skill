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
- For a printable sheet, draw the requested border/title block yourself and use fixed paper/scale rendering. Leave personal fields blank unless supplied. Do not claim native DWG output or verified compatibility with a CAD application you have not tested.

Install dependencies with `python -m pip install -r <skill_dir>/requirements.txt`.

```python
import sys
sys.path.insert(0, "<skill_dir>/scripts")
from sketch_helpers import new_doc, dim_linear

def build():
    doc = new_doc()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (60, 0), (60, 20), (0, 20)], close=True)
    dim_linear(m, (0, 0), (60, 0), 12)
    return doc

if __name__ == "__main__":
    build().saveas("part.dxf")
```

Render: `python <skill_dir>/scripts/render_dxf.py part.dxf part.png`.
For physical paper: add `--paper A3 --scale 1` (or A4); PDF output is selected by the `.pdf` extension. Oversized drawings fail instead of silently shrinking. Use `--font path.ttf` for an installed CJK font when needed; no font is bundled. Previews use OUTLINE text (vector lettering): ezdxf 1.4.x FILLING mis-renders the diameter glyph as a half-filled disc; the DXF keeps normal text for CAD applications.

## Layers and lineweights

`new_doc()` creates the GB/T 17450-style two-width system: outlines on layer `0` (0.50 mm); `THIN`, `CENTER`, `HIDDEN`, `DIM`, `HATCH` at 0.25 mm. Put axes/pitch circles on CENTER, hidden/thread lines on HIDDEN, section hatching on HATCH, all dimensions and annotations on DIM.

## Layout and attachment rules

- Prefer straight leaders or one elbow. First move the label/frame near its feature; do not route several bends around the drawing. Keep independent leaders, arrows and text clear of one another.
- Native LEADER vertices start at the arrow tip, followed by an optional elbow and the annotation end.
- Geometric tolerance leaders enter the **left-edge midpoint** of the frame, with a horizontal final segment. `feature_control_frame(..., target=...)` / `frame_leader(...)` enforce this. A helper cannot choose the correct controlled feature for you.
- For a surface tolerance (e.g. flatness), the arrow should approach **normal to the tolerated surface**. Place the frame on the side that makes the auto elbow produce a perpendicular final approach (for a horizontal top surface with the frame to the right of the target, the approach is vertical). For a runout/size-dimension-aligned attachment, use `arrow=True` at the size-dimension attachment and blank the shared ordinary arrow with `dim_linear(..., suppress_arrow=1/2)` so exactly one arrow remains.
- For derived axes/median planes, connect the frame to the appropriate size-dimension line or its extension with `arrow=False` (plain extension, no arrowhead). Do not point at an arbitrary contour and imply a different tolerance requirement. Section views need applicable geometric tolerances too.
- For the chamfer-line convention, pass the real `chamfer_edge=(p1, p2)` to `chamfer_note`. The helper validates that the arrow-bearing segment is collinear with that edge's extension and points away from the edge; target defaults to p2 and must sit at an edge end or on its extension. Put any elbow on that extension, then one horizontal segment to the label. Violations raise ValueError — fix the geometry, do not bypass the check.
- When a linear dimension value is outside the measured interval, place arrow bodies OUTSIDE the extension lines and point their tips INWARD. The native renderer extension handles this before rendering, including reversed endpoints; its dimension lines and outside tails stay connected.
- For the GB/textbook datum convention, `datum_symbol` draws a black filled triangle (SOLID) with its **base touching the boundary**, outward apex connected to the boxed letter. For an axis datum, align the attachment with the size dimension and blank the ordinary arrow via `dim_linear(..., suppress_arrow=1/2)`: a pre-render native `DIMSAH + DIMBLK=NONE` override leaves the dimension line drawn full to that point with no gap (real DXF data, re-rendered by CAD apps). Do not use a leader arrow instead of the datum triangle.
- `roughness_symbol` draws the material-removal symbol with a short closing bar with Ra above the long bar; rotate with `angle` for inclined surfaces. Keep notation and orientation consistent with the selected standard/reference.
- Use continuous physical edges; split only what the drawing convention requires. A slot centreline extends beyond both ends. Clip hatching to the actual material boundary. For hatch edge paths, the geometric arc runs CCW start→end: to hatch a circle minus a keyway, add the arc with swapped angles and `ccw=False` (see example).

## Helpers

Import from `scripts/sketch_helpers.py`:

- `new_doc(text_height=3.5, font="arial.ttf")`: R2010, mm, CAD_MM dimension style (dimlfac=1, decimal point), CAD_TEXT style, layers above. For CJK pass an installed font file name, e.g. `new_doc(font="simhei.ttf")`.
- `dim_linear(msp, p1, p2, offset, angle=0, text=None, *, upper=None, lower=None, text_location=None, suppress_arrow=None)`: native DIMENSION. Positive offset places horizontal dimensions below, vertical dimensions left. `text="%%c<>"` prefixes a diameter mark to the real measurement. `suppress_arrow=1/2` blanks that end's arrow via native `DIMSAH + DIMBLK=NONE` while keeping the dimension line full to the point.
- `dim_diameter(msp, center, radius, angle=30, text=None)`, `dim_radius(...)`, `dim_angular(msp, center, p1, p2, dist, text=None)`: native dimensions; the angular helper measures the smaller angle via the ezdxf 1.4.x three-point renderer.
- Supply both deviations as **signed** values: `upper=0.042, lower=0.026` means two positive deviations; `upper=0, lower=-0.180` means zero upper and negative lower deviation. Preserve the given values; changing typography is not a reason to change the tolerance. Upper < lower or supplying only one raises ValueError.
- `tolerance_text(msp, insert, nominal, upper, lower, height=3.5, *, precision=3, rotation=0)`: editable standalone stacked MTEXT, not a measured dimension.
- `leader(msp, target, text_insert, label, height=3.5, *, elbow=None)`; `chamfer_note(msp, insert, size=2, angle=45, height=3.5, *, target=None, elbow=None, chamfer_edge=None)`.
- `roughness_symbol(msp, insert, value=3.2, angle=0, height=3.5)`; `datum_symbol(msp, boundary, label, height=3.5, *, side="below", filled=True)`. Pair datum/runout attachments with `suppress_arrow` on the dimension rather than editing the rendered block.
- `audit_annotations(msp)`: geometry audit returning a list of problems (empty = clean). For each DIMENSION it verifies two arrow block refs and an unbroken dimension line reaching every end; for each LEADER it verifies an arrow flag resolves to a real arrow. Call it before rendering and fail on any problem.
- `feature_control_frame(msp, insert, characteristic, value, datum=None, height=3.5, *, target=None, elbow=None, arrow=True)`: supported characteristics are `symmetry`, `cylindricity`, `circular_runout`, `flatness`; others raise ValueError. Returns `(left, bottom, right, top)`. Frames are editable lines/text, not native TOLERANCE entities. `frame_leader(msp, bounds, target, *, elbow=None, arrow=True, height=3.5)` attaches to an existing frame.

Optional arguments after `*` in the Python signatures are keyword-only. See [the runnable example](examples/engineering_annotations.py) for attachment geometry, deviations, datum-arrow suppression and a hatched keyway section.

Templates in `scripts/part_templates.py`: hex_nut, stepped_shaft, flange, plate_with_holes. These are starting sketches; review dimensions and layout for the requested use.

Validation after changing helpers: `python -m unittest discover -s <skill_dir>/tests -v` (40 tests). Also render the example and inspect it; numeric tests alone cannot establish readable sheet layout. The example additionally runs `audit_annotations` and raises on any missing arrow or incomplete line.
