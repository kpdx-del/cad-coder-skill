#!/usr/bin/env python
"""Sketch helpers: DXF primitives, dimensions and GB-style engineering annotations.

Import in generated scripts:
    from sketch_helpers import new_doc, dim_linear, feature_control_frame, ...

Conventions
-----------
- All geometry in millimetres, nominal scale 1:1 (dimension factor 1).
- Geometry on layer "0" (0.50 mm), annotations on layer "DIM" (0.25 mm).
- Deviations ``upper`` / ``lower`` are SIGNED values: upper=0.042, lower=0.026
  means two positive deviations; upper=0, lower=-0.180 means zero upper and
  negative lower deviation. Both must be supplied together.
- Helpers draw annotation elements; they do not choose tolerances, plan
  collision-free leader routes or certify standards compliance.
"""

import math

import ezdxf
from ezdxf.enums import TextEntityAlignment
from ezdxf.math import Vec2
from ezdxf.render.dimension import DimensionRenderer
from ezdxf.render.dim_linear import LinearDimension
from typography import register_font, text_width, add_text, style_for


class _OutsideTextDimension(LinearDimension):
    def total_text_width(self):
        font = self.dimension.doc.styles.get("CAD_TEXT").dxf.font
        self.measurement.text_width = lambda value: text_width(value, font, self.measurement.text_height)
        width = self.measurement.text_width(self.measurement.text)
        if self.tol.has_tolerance:
            if self.tol.maximum == 0:
                self.tol.text_upper = "0"
            if self.tol.minimum == 0:
                self.tol.text_lower = "0"
            values = [self.tol.text] if self.tol.text else [self.tol.text_upper, " " + self.tol.text_lower]
            self.tol.text_width = max(text_width(s, font, self.tol.char_height) for s in values)
            width += self.tol.text_width
        return width

    def precise_mtext(self, dim_text):
        if self.tol.has_tolerance:
            dim_text = dim_text.replace("\\H%.2fx" % self.tol.text_scale_factor,
                                        "\\H%.8fx" % self.tol.text_scale_factor)
        return dim_text

    def add_measurement_text(self, dim_text, pos, rotation):
        dim_text = self.precise_mtext(dim_text)
        # An unspecified MTEXT width is estimated from flattened tolerance
        # text by ezdxf, shifting the real glyphs off centre. Store real width.
        self.add_text(dim_text, pos, rotation, {"width": self.total_text_width()+.01})

    def default_text_location(self):
        pos = super().default_text_location()
        if self.tol.has_tolerance and not self.tol.text:
            stack_height = self.tol.char_height * (1 + self.tol.line_spacing)
            extra = max(0, stack_height-self.measurement.text_height) / 2
            pos += self.dim_line_vec.orthogonal().normalize(extra) if extra else Vec2()
        return pos

    def add_dimension_line(self, start, end):
        super().add_dimension_line(start, end)
        along = (Vec2(self.measurement.text_location)-self.dim_line_start).dot(self.dim_line_vec)
        length = (self.dim_line_end-self.dim_line_start).magnitude
        if along < 0 or along > length:
            far = self.dim_line_start + self.dim_line_vec * (along +
                  (1 if along > length else -1)*(self.total_text_width()/2+self.measurement.text_gap))
            near = self.dim_line_end if along > length else self.dim_line_start
            self.add_line(near, far, dxfattribs=self.dimension_line.dxfattribs(), remove_hidden_lines=True)

    def __init__(self, dimension, ucs=None, override=None):
        super().__init__(dimension, ucs, override)
        from drawing_checks import annotation_data
        data = annotation_data(dimension)
        # Measure the actual stacked MTEXT before placing the complete group.
        if data.get("text_side") == "above" and self.measurement.text:
            from ezdxf.entities import factory
            from typography import text_rect
            content = self.precise_mtext(self.tol.compile_mtext(self.measurement.text))
            probe = factory.new("MTEXT", dxfattribs={"text": content,
                                "char_height": self.measurement.text_height,
                                "style": self.measurement.text_style_name,
                                "attachment_point": self.measurement.text_attachment_point,
                                "width": self.total_text_width()+.01,
                                "insert": (0,0)}, doc=dimension.doc)
            rect = text_rect(probe)
            normal = self.dim_line_vec.orthogonal()
            pos = Vec2(self.measurement.text_location)
            clearance = max(.8, self.measurement.text_gap)
            distance = (pos-self.dim_line_start).dot(normal)
            minimum = -rect[1] + clearance
            if distance < minimum:
                self.measurement.text_location = pos + normal*(minimum-distance)
            self.geometry.set_text_box(self.init_text_box())
            dimension.dxf.text_midpoint = self.measurement.text_location
        along = (Vec2(self.measurement.text_location)-self.dim_line_start).dot(self.dim_line_vec)
        length = (self.dim_line_end-self.dim_line_start).magnitude
        policy = data.get("arrows", "auto")
        original = self.arrows_outside
        if policy == "inside":
            if length < self.required_arrows_space:
                raise ValueError("inside arrows do not fit; use outside arrows")
            self.arrows_outside = False
        elif policy == "outside" or (policy == "auto" and self.measurement.text and
                (self.measurement.is_wide_text or along < 0 or along > length)):
            self.arrows_outside = True
        # Native flip flags keep the editable DXF consistent with the geometry.
        dimension.dxf.flip_arrow_1 = int(original != self.arrows_outside)
        dimension.dxf.flip_arrow_2 = int(original != self.arrows_outside)


class _DrawingRenderer(DimensionRenderer):
    def linear(self, dimension, ucs=None, override=None):
        return _OutsideTextDimension(dimension, ucs, override)

__all__ = [
    "new_doc", "dim_linear", "dim_diameter", "dim_radius", "dim_angular",
    "tolerance_text", "leader", "chamfer_note", "roughness_symbol",
    "datum_symbol", "feature_control_frame", "frame_leader",
    "audit_annotations",
    "cutting_marks", "section_axes",
]

_EPS = 1e-6

# ---------------------------------------------------------------- document


def new_doc(text_height=3.5, font="isocp___.ttf", *, cjk_font="simfang.ttf", extension_gap=1.0):
    """R2010 document, millimetres, CAD_MM dimension style, GB-ish layers.

    Layers / lineweights follow the common GB/T 17450 two-width system:
      0      0.50 mm  continuous  visible outlines
      THIN   0.25 mm  continuous  thin solid lines
      CENTER 0.25 mm  CENTER      axes, pitch circles
      HIDDEN 0.25 mm  DASHED      hidden / thread lines
      DIM    0.25 mm  continuous  dimensions & annotations
      HATCH  0.25 mm  continuous  section hatching
    Fonts must be installed (or in CAD_FONT_DIRS); no fallback is used.
    CAD_TEXT is ISOCP by default; CAD_CJK is FangSong. No font is bundled.
    """
    doc = ezdxf.new("R2010", setup=True)
    doc.dimension_renderer = _DrawingRenderer()
    doc.header["$INSUNITS"] = 4          # millimetres
    doc.header["$MEASUREMENT"] = 1       # metric
    doc.header["$LUNITS"] = 2            # decimal
    doc.header["$LUPREC"] = 2

    doc.styles.new("CAD_TEXT", dxfattribs={"font": register_font(font)})
    doc.styles.new("CAD_CJK", dxfattribs={"font": register_font(cjk_font)})

    for name, color, lw, lt in (
        ("THIN", 7, 25, "Continuous"),
        ("CENTER", 1, 25, "CENTER"),
        ("HIDDEN", 6, 25, "DASHED"),
        ("DIM", 3, 25, "Continuous"),
        ("HATCH", 8, 25, "Continuous"),
    ):
        doc.layers.add(name, color=color, lineweight=lw, linetype=lt)
    doc.layers.get("0").dxf.lineweight = 50

    doc.dimstyles.new("CAD_MM", dxfattribs={
        "dimtxt": text_height,      # dimension text height
        "dimasz": 2.5,              # arrow size
        "dimlfac": 1,               # measurement factor: mm, 1:1
        "dimdec": 2,                # nominal decimals
        "dimzin": 8,                # suppress trailing zeros of nominal
        "dimtzin": 0,               # keep trailing zeros of deviations
        "dimdsep": ord("."),        # decimal point, not comma
        "dimexo": extension_gap,    # explicitly chosen extension-line start gap
        "dimexe": 2.0,              # extension beyond dim line
        "dimgap": 0.8,
        "dimtad": 1,                # text above dim line
        "dimtih": 0, "dimtoh": 0,   # aligned text
        "dimblk": "",               # closed filled arrows
        "dimldrblk": "",
        "dimtxsty": "CAD_TEXT",
        "dimclrd": 0, "dimclre": 0, "dimclrt": 0,
    })
    return doc


# ------------------------------------------------------------- dimensions


def _validate_deviations(upper, lower):
    if (upper is None) != (lower is None):
        raise ValueError("upper and lower deviations must be supplied together")
    if upper is not None and upper < lower:
        raise ValueError("upper deviation must be >= lower deviation")


def _linear_base(p1, angle, offset):
    """Positive offset: horizontal dims below, vertical dims left."""
    if angle == 0:
        return (p1[0], p1[1] - offset)
    if angle == 90:
        return (p1[0] - offset, p1[1])
    a = math.radians(angle)
    return (p1[0] + offset * math.sin(a), p1[1] - offset * math.cos(a))


def _arrow_suppression_override(end):
    """Pre-render overrides that blank one arrow end.

    DIMSAH=1 makes the two ends use separate arrow blocks; the NONE block is
    an empty arrow in AutoCAD/ezdxf and, being an origin-zero arrow, the
    renderer does not shorten the dimension line on that end, so the line
    reaches the extension point with no gap. The other end keeps a closed
    filled arrow. This is real DXF data (re-rendered by CAD apps), not a
    post-render edit of the anonymous block.
    """
    if end == 1:
        return {"dimsah": 1, "dimblk1": "NONE", "dimblk2": ""}
    if end == 2:
        return {"dimsah": 1, "dimblk1": "", "dimblk2": "NONE"}
    raise ValueError("suppress_arrow must be 1 or 2 (the extension-line end)")


def dim_linear(msp, p1, p2, offset, angle=0, text=None, *,
               upper=None, lower=None, text_location=None, suppress_arrow=None,
               arrows="auto", reference=False, text_side="above", witness_geometry=None):
    """Native linear DIMENSION.

    offset: signed distance of the dim line from p1 (see _linear_base).
    text: DIMPOST pattern, e.g. "%%c<>" prefixes a diameter mark to the
          real measurement.
    upper/lower: signed deviations, rendered stacked (both required).
    text_location: explicit value position. Arrows stay native: when the
          value is outside the measured interval the arrows have bodies outside the extension lines and tips inward;
          dimension lines and outside tails are rendered together.
    suppress_arrow: 1 or 2 blanks that end's arrow (e.g. for a datum
          triangle or a geometric-tolerance leader sharing the point);
          the dimension line is still drawn full to that point.
    """
    _validate_deviations(upper, lower)
    if arrows not in ("auto", "inside", "outside"):
        raise ValueError("arrows must be auto, inside or outside")
    if text_side not in ("above", "native"):
        raise ValueError("text_side must be above or native")
    base = _linear_base(p1, angle, offset)
    if (Vec2(p2)-Vec2(p1)).dot(Vec2.from_deg_angle(angle)) < 0:
        p1, p2 = p2, p1
        if suppress_arrow in (1, 2):
            suppress_arrow = 3-suppress_arrow
    override = {"dimpost": text} if text is not None else {}
    if suppress_arrow is not None:
        override.update(_arrow_suppression_override(suppress_arrow))
    d = msp.add_linear_dim(base=base,
                           p1=p1, p2=p2, angle=angle, dimstyle="CAD_MM",
                           override=override, dxfattribs={"layer": "DIM"})
    from drawing_checks import mark_annotation
    mark_annotation(d.dimension, "dimension", arrows=arrows, reference=reference,
                    text_side=text_side, blank_ends=[suppress_arrow] if suppress_arrow else [],
                    witness_geometry=witness_geometry.dxf.handle if witness_geometry is not None else None)
    if reference:
        d.update({"dimpost": "(" + (text or "<>") + ")"})
    if upper is not None:
        # DXF DIMTM stores the negated lower deviation.
        h = msp.doc.dimstyles.get("CAD_MM").dxf.dimtxt
        d.set_tolerance(upper=upper, lower=-lower, hfactor=2.5 / h, dec=3)
    if text_location is not None:
        d.set_location(text_location, leader=False, relative=False)
    d.render()
    return d


def dim_diameter(msp, center, radius, angle=30, text=None):
    override = {"dimpost": text} if text is not None else {}
    d = msp.add_diameter_dim(center=center, radius=radius, angle=angle,
                             dimstyle="CAD_MM", override=override,
                             dxfattribs={"layer": "DIM"})
    d.render()
    return d


def dim_radius(msp, center, radius, angle=30, text=None):
    override = {"dimpost": text} if text is not None else {}
    d = msp.add_radius_dim(center=center, radius=radius, angle=angle,
                           dimstyle="CAD_MM", override=override,
                           dxfattribs={"layer": "DIM"})
    d.render()
    return d


def dim_angular(msp, center, p1, p2, dist, text=None):
    """Native three-point angular DIMENSION measuring the smaller angle.

    dist: radius of the dimension arc. Verified against ezdxf 1.4.x, whose
    curved-dimension renderer no longer raises ZeroDivisionError.
    """
    for p in (p1, p2):
        if math.hypot(p[0] - center[0], p[1] - center[1]) < _EPS:
            raise ValueError("angle point coincides with center")
    a1 = math.degrees(math.atan2(p1[1] - center[1], p1[0] - center[0])) % 360
    a2 = math.degrees(math.atan2(p2[1] - center[1], p2[0] - center[0])) % 360
    span = (a2 - a1) % 360
    if span > 180:                      # always measure the smaller angle
        p1, p2 = p2, p1
        a1, a2 = a2, a1
        span = 360 - span
    mid = a1 + span / 2.0
    m = math.radians(mid)
    base = (center[0] + dist * math.cos(m), center[1] + dist * math.sin(m))
    override = {"dimpost": text} if text is not None else {}
    d = msp.add_angular_dim_3p(base=base, center=center, p1=p1, p2=p2,
                               dimstyle="CAD_MM", override=override,
                               dxfattribs={"layer": "DIM"})
    d.render()
    return d


def tolerance_text(msp, insert, nominal, upper, lower, height=3.5, *,
                   precision=3, rotation=0):
    """Editable standalone stacked MTEXT (not a measured dimension)."""
    _validate_deviations(upper, lower)
    up = "0" if upper == 0 else "%+.*f" % (precision, upper)
    lo = "0" if lower == 0 else "%+.*f" % (precision, lower)
    body = "\\A0;%s{\\H%.8fx;\\S%s^ %s;}" % (("%g" % nominal), 2.5/height, up, lo)
    return msp.add_mtext(body, dxfattribs={
        "layer": "DIM", "style": "CAD_TEXT", "char_height": height, "insert": insert,
        "rotation": rotation})


# ---------------------------------------------------------------- leaders


def leader(msp, target, text_insert, label, height=3.5, *, elbow=None):
    """Editable LEADER + text. Vertices start at the arrow tip (target),
    then an optional single elbow, then the annotation end. This helper
    does not route around geometry or detect collisions."""
    vertices = [target, text_insert] if elbow is None else [target, elbow, text_insert]
    ld = msp.add_leader(vertices=vertices,
                        override={"dimldrblk": "", "dimasz": height * 0.7},
                        dxfattribs={"layer": "DIM"})
    text = add_text(msp, label, (text_insert[0], text_insert[1] + 0.8), height)
    from drawing_layout import register_group
    register_group(ld, [ld,text], "leader")
    return ld


def _cross(ax, ay, bx, by):
    return ax * by - ay * bx


def chamfer_note(msp, insert, size=2.0, angle=45, height=3.5, *,
                 target=None, elbow=None, chamfer_edge=None):
    """Chamfer callout (C2 / 2x30deg) with an optional validated leader.

    chamfer_edge=(p1, p2): the real chamfer line. The arrow-bearing segment
    (target -> elbow, or target -> insert without elbow) must be collinear
    with that edge's extension and point away from the edge; target defaults
    to p2 and must lie at an edge end or on its extension. With an elbow,
    the final elbow -> insert segment must be horizontal.
    Without target/chamfer_edge this degrades to plain callout text.
    """
    label = "%g×%g°" % (size, angle)
    if chamfer_edge is not None and target is None:
        target = chamfer_edge[1]
    if target is not None and chamfer_edge is not None:
        pa, pb = chamfer_edge
        ex, ey = pb[0] - pa[0], pb[1] - pa[1]
        el = math.hypot(ex, ey)
        if el < _EPS:
            raise ValueError("degenerate chamfer edge")
        tx, ty = target[0] - pa[0], target[1] - pa[1]
        tol = 1e-6 * max(1.0, el)
        if abs(_cross(tx, ty, ex, ey)) > tol * max(1.0, math.hypot(tx, ty)):
            raise ValueError("target is not on the chamfer edge line")
        t = (tx * ex + ty * ey) / (el * el)
        if _EPS < t < 1 - _EPS:
            raise ValueError("target must be at an edge end or on its extension")
        nxt = elbow if elbow is not None else insert
        vx, vy = nxt[0] - target[0], nxt[1] - target[1]
        vl = math.hypot(vx, vy)
        if vl < _EPS:
            raise ValueError("zero-length arrow segment")
        if abs(_cross(vx, vy, ex, ey)) > 1e-6 * vl * el:
            raise ValueError("arrow segment is not collinear with the chamfer edge")
        outward = (vx * ex + vy * ey) > 0 if t >= 1 - _EPS else (vx * ex + vy * ey) < 0
        if not outward:
            raise ValueError("arrow segment must run along the extension away from the edge")
        if elbow is not None and abs(elbow[1] - insert[1]) > _EPS:
            raise ValueError("final segment to the label must be horizontal")
    if target is None:
        return add_text(msp, label, insert, height)
    ld = leader(msp, target, insert, label, height=height, elbow=elbow)
    from drawing_checks import mark_annotation
    mark_annotation(ld, "chamfer", edge=chamfer_edge)
    return ld


# ------------------------------------------------- roughness / datum / FCF


def roughness_symbol(msp, insert, value=3.2, angle=0.0, height=3.5, *,
                     method=None, lay=None):
    """Material-removal roughness symbol with a short closing bar.

    Apex touches the surface at ``insert``; long leg at 60 deg with a
    horizontal bar, Ra value below the bar. ``angle`` rotates the whole
    symbol for inclined/vertical surfaces (text rotates with it).
    """
    h = height
    previous = {e.dxf.handle for e in msp}
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)

    def rot(p):
        return (insert[0] + p[0] * ca - p[1] * sa,
                insert[1] + p[0] * sa + p[1] * ca)

    short = (-0.5 * h, 0.866 * h)          # 120 deg leg
    long_ = (1.0 * h, 1.732 * h)           # 60 deg leg, length 2h
    font = msp.doc.styles.get("CAD_TEXT").dxf.font
    label = "Ra %g" % value
    method_font = msp.doc.styles.get(style_for(method or "")).dxf.font
    bar_width = max(text_width(label, font, h),
                    text_width(method or "", method_font, h)) + 0.8 * h
    bar_end = (long_[0] + bar_width, long_[1])

    msp.add_lwpolyline([rot(short), rot((0, 0)), rot(long_), rot(bar_end)],
                       dxfattribs={"layer": "DIM"})
    msp.add_line(rot(short), rot((0.5*h, 0.866*h)), dxfattribs={"layer":"DIM"})
    # Textbook Fig. 5-10 (printed p.120): parameter below the long bar.
    add_text(msp, label, rot((long_[0] + 0.2*h, long_[1] - 1.15*h)), h, rotation=angle)
    if method:
        add_text(msp, method, rot((long_[0] + 0.2*h, long_[1] + 0.3*h)), h, rotation=angle)
    if lay:
        add_text(msp, lay, rot((long_[0] + 0.2*h, -1.2*h)), h, rotation=angle)
    from drawing_layout import register_group, new_entities
    members = new_entities(msp, previous)
    register_group(members[0], members, "roughness", surface_point=insert)


def datum_symbol(msp, boundary, label, height=3.5, *, side="below", filled=True):
    """Datum feature symbol: triangle base ON the boundary at ``boundary``,
    outward apex connected by a stem to a boxed letter.

    side="below"/"above" for a horizontal boundary. filled=True uses a SOLID
    entity (black filled triangle); False draws an open triangle.
    For an axis datum align the attachment with the size dimension and
    suppress the ordinary arrow sharing that position (caller's job).
    """
    if side not in ("below", "above"):
        raise ValueError("side must be 'below' or 'above'")
    x, y = boundary
    sgn = -1.0 if side == "below" else 1.0
    h = height
    bw = 0.7 * h                      # half base width
    apex = (x, y + sgn * 1.2 * h)
    base_l, base_r = (x - bw, y), (x + bw, y)
    if filled:
        msp.add_solid([base_l, base_r, apex], dxfattribs={"layer": "DIM"})
    else:
        msp.add_lwpolyline([base_l, base_r, apex], close=True,
                           dxfattribs={"layer": "DIM"})
    stem_end = (x, apex[1] + sgn * 1.2 * h)
    msp.add_line(apex, stem_end, dxfattribs={"layer": "DIM"})
    box_top = stem_end[1]
    box_bot = box_top + sgn * 2 * h
    msp.add_lwpolyline([(x - h, box_top), (x + h, box_top),
                        (x + h, box_bot), (x - h, box_bot)], close=True,
                       dxfattribs={"layer": "DIM"})
    t = add_text(msp, label, (x, (box_top + box_bot) / 2.0), h)
    t.set_placement((x, (box_top + box_bot) / 2.0),
                    align=TextEntityAlignment.MIDDLE_CENTER)
    from drawing_checks import mark_annotation
    mark_annotation(t, "datum", label=label, boundary=boundary)
    return t


def _audit_dimension(dim):
    """Check one rendered DIMENSION: two arrow block refs and an unbroken
    dimension line reaching the expected endpoint on every end."""
    from ezdxf.math import Vec3
    out = []
    handle = dim.dxf.handle
    try:
        blk = dim.doc.blocks.get(dim.dxf.geometry)
    except ezdxf.DXFKeyError:
        return ["dimension %s has no rendered geometry block" % handle]
    inserts = [e for e in blk if e.dxftype() == "INSERT"]
    lines = [e for e in blk if e.dxftype() == "LINE"]

    o = Vec3(dim.dxf.defpoint)
    p1 = Vec3(dim.dxf.defpoint2)
    p2 = Vec3(dim.dxf.defpoint3)
    # The dim line direction is the dimension's nominal angle, not the
    # defpoint2->defpoint3 delta: the two measurement points may differ
    # perpendicular to the line (e.g. a total length across stepped ends),
    # which would tilt the derived axis and misjudge an otherwise horizontal
    # dimension line.
    if (p2 - p1).magnitude < _EPS:
        return ["dimension %s has zero-length measurement" % handle]
    ang = math.radians(dim.dxf.get("angle", 0.0))
    u = Vec3(math.cos(ang), math.sin(ang), 0.0)
    n = u.orthogonal()

    def along(p):
        return (p - o).dot(u)

    def perp(p):
        return (p - o).dot(n)

    if len(inserts) != 2:
        out.append("dimension %s: expected 2 arrow block refs, found %d"
                   % (handle, len(inserts)))

    # expected dimension-line coordinate at each end
    from ezdxf.entities import DimStyleOverride
    asz = float(DimStyleOverride(dim).get("dimasz", 2.5))
    center = (along(p1) + along(p2)) / 2.0
    expected = []
    arrow_intervals = []
    for end_p in (p1, p2):
        c = along(end_p)
        if inserts:
            nearest = min(inserts, key=lambda e: abs(along(e.dxf.insert) - c))
            if abs(along(nearest.dxf.insert)-c) > 1e-5 or abs(perp(nearest.dxf.insert)) > 1e-5:
                out.append("dimension %s: arrow tip detached from extension line" % handle)
            blank = str(nearest.dxf.name).upper() == "_NONE"
        else:
            blank = False
        from drawing_checks import annotation_data
        declared = annotation_data(dim)
        end_index = 1 if end_p == p1 else 2
        if "blank_ends" in declared and blank != (end_index in declared["blank_ends"]):
            out.append("dimension %s: missing or unexpected arrow at end %d" % (handle,end_index))
        # blank (NONE) end: line reaches the extension point itself;
        # visible arrow end: line reaches the actual arrow base, inside or outside
        if blank:
            expected.append(c)
        else:
            rotation = math.radians(nearest.dxf.rotation) - ang if inserts else 0
            expected.append(c - asz * math.cos(rotation))
            arrow_intervals.append(sorted((c, expected[-1])))
    exp_lo, exp_hi = min(expected), max(expected)

    # collect line segments lying on the dimension line (perp ~ 0)
    segments = []
    for e in lines:
        a, b = Vec3(e.dxf.start), Vec3(e.dxf.end)
        if abs(perp(a)) < 1e-5 and abs(perp(b)) < 1e-5:
            segments.append(sorted((along(a), along(b))))
    if not segments:
        out.append("dimension %s: no dimension line on the measurement axis" % handle)
    else:
        segments.sort()
        # Filled arrow bodies occupy these intervals; they are not gaps.
        coverage = sorted(segments + arrow_intervals)
        merged = [list(coverage[0])]
        for a, b in coverage[1:]:
            if a <= merged[-1][1] + 1e-5:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        # outer coverage only: gaps at text are legitimate (text on the line)
        if merged[0][0] > exp_lo + 1e-5:
            out.append("dimension %s: dimension line does not reach the "
                       "first end (starts %.3f, expected %.3f)"
                       % (handle, merged[0][0], exp_lo))
        if merged[-1][1] < exp_hi - 1e-5:
            out.append("dimension %s: dimension line does not reach the "
                       "second end (ends %.3f, expected %.3f)"
                       % (handle, merged[-1][1], exp_hi))
        from ezdxf import bbox
        text_intervals = []
        for entity in blk:
            if entity.dxftype() not in ("TEXT", "MTEXT"):
                continue
            box = bbox.extents([entity])
            if box.has_data:
                projected = [along(Vec3(x, y)) for x in (box.extmin.x, box.extmax.x)
                             for y in (box.extmin.y, box.extmax.y)]
                text_intervals.append((min(projected)-1, max(projected)+1))
        for before, after in zip(merged, merged[1:]):
            a, b = max(before[1], exp_lo), min(after[0], exp_hi)
            if b-a > 1e-5 and not any(x <= a+1e-5 and y >= b-1e-5 for x,y in text_intervals):
                out.append("dimension %s: unintended internal gap %.3f..%.3f" % (handle, a, b))
    return out


def _audit_leader(ld):
    """Check that a LEADER flagged with an arrow resolves to a real arrow."""
    out = []
    if not bool(ld.dxf.has_arrowhead):
        return out
    name = ld.override().get("dimldrblk", "")
    if name is None or str(name).upper() == "NONE":
        out.append("leader %s flags an arrow but resolves to no arrow"
                   % ld.dxf.handle)
    if len(ld.vertices) < 2:
        out.append("leader %s has fewer than 2 vertices" % ld.dxf.handle)
    return out


def audit_required_arrows(dim, required_ends=(1, 2)):
    """Check an independent requirement for visible linear-dimension arrows.

    This does not accept ``blank_ends`` as a waiver. Legitimate datum/shared
    replacements must be selected and verified separately by the caller.
    """
    from ezdxf import bbox
    from ezdxf.math import Vec3
    if dim.dimtype not in (0, 1):
        raise ValueError("required-arrow checks currently support linear/aligned dimensions")
    if any(end not in (1, 2) for end in required_ends):
        raise ValueError("required arrow ends must be 1 or 2")
    try:
        block = dim.doc.blocks.get(dim.dxf.geometry)
    except ezdxf.DXFKeyError:
        return ["dimension %s: required arrows have no geometry block" % dim.dxf.handle]
    style = dim.override()
    names = style.get_arrow_names()
    origin = Vec3(dim.dxf.defpoint)
    angle = math.radians(dim.dxf.get("angle", 0))
    direction = Vec3(math.cos(angle), math.sin(angle), 0)
    points = (Vec3(dim.dxf.defpoint2), Vec3(dim.dxf.defpoint3))
    inserts = list(block.query("INSERT"))
    problems = []
    for end in required_ends:
        prefix = "dimension %s: required arrow at end %d" % (dim.dxf.handle, end)
        tip = origin + direction * (points[end-1] - origin).dot(direction)
        matching = [arrow for arrow in inserts if arrow.dxf.insert.isclose(tip, abs_tol=1e-5)]
        if len(matching) != 1:
            problems.append(prefix + ": missing, displaced or duplicated")
            continue
        arrow = matching[0]
        if (str(names[end-1]).upper() == "NONE" or
                str(arrow.dxf.name).upper() == "_NONE" or
                float(style.get("dimasz", 2.5)) <= 0):
            problems.append(prefix + ": disabled by style or blank block")
            continue
        hidden = any(entity.dxf.get("invisible", 0) or
                     entity.doc.layers.get(entity.dxf.layer).is_off() or
                     entity.doc.layers.get(entity.dxf.layer).is_frozen()
                     for entity in (dim, arrow))
        if hidden:
            problems.append(prefix + ": hidden entity or layer")
        extent = bbox.extents([arrow])
        if not extent.has_data or min(extent.size.x, extent.size.y) <= 1e-6:
            problems.append(prefix + ": empty or degenerate visible geometry")
    return problems


def audit_annotations(msp, *, required_arrows=None):
    """Audit rendered annotation geometry.

    Returns a list of human-readable problems (empty list = clean). For every
    DIMENSION it verifies two arrow block refs and an unbroken dimension line
    reaching each end; for every LEADER it verifies an arrow flag resolves to
    a real arrow. Call this after building a sheet and before rendering so a
    missing arrow or incomplete line fails loudly instead of slipping through.
    required_arrows maps dimension handles to independently required end
    numbers; these requirements cannot be waived by generated blank_ends.
    """
    problems = []
    for dim in msp.query("DIMENSION"):
        if dim.dimtype in (0, 1):
            problems.extend(_audit_dimension(dim))
            if required_arrows is not None and dim.dxf.handle in required_arrows:
                problems.extend(audit_required_arrows(dim, required_arrows[dim.dxf.handle]))
    for ld in msp.query("LEADER"):
        problems.extend(_audit_leader(ld))
    return problems


_FCF_CHARS = ("symmetry", "cylindricity", "circular_runout", "flatness", "roundness", "coaxiality", "perpendicularity", "parallelism")


def _draw_fcf_symbol(msp, characteristic, cx, cy, h):
    attribs = {"layer": "DIM"}
    if characteristic == "flatness":
        msp.add_lwpolyline([(cx - 0.55 * h, cy - 0.3 * h), (cx + 0.35 * h, cy - 0.3 * h),
                            (cx + 0.55 * h, cy + 0.3 * h), (cx - 0.35 * h, cy + 0.3 * h)],
                           close=True, dxfattribs=attribs)
    elif characteristic == "cylindricity":
        msp.add_circle((cx, cy), 0.32 * h, dxfattribs=attribs)
        for dx in (-0.52 * h, 0.52 * h):
            msp.add_line((cx + dx - 0.22 * h, cy - 0.42 * h),
                         (cx + dx + 0.22 * h, cy + 0.42 * h), dxfattribs=attribs)
    elif characteristic == "circular_runout":
        tip = (cx + 0.35 * h, cy + 0.45 * h)
        msp.add_line((cx - 0.35 * h, cy - 0.45 * h), tip, dxfattribs=attribs)
        d = math.atan2(0.9, 0.7)
        for da in (math.radians(155), math.radians(205)):
            msp.add_line(tip, (tip[0] + 0.3 * h * math.cos(d + da),
                               tip[1] + 0.3 * h * math.sin(d + da)),
                         dxfattribs=attribs)
    elif characteristic == "symmetry":
        msp.add_line((cx - 0.6 * h, cy), (cx + 0.6 * h, cy), dxfattribs=attribs)
        for dy in (-0.3 * h, 0.3 * h):
            msp.add_line((cx - 0.35 * h, cy + dy), (cx + 0.35 * h, cy + dy),
                         dxfattribs=attribs)
    elif characteristic in ("roundness", "coaxiality"):
        msp.add_circle((cx, cy), 0.48*h, dxfattribs=attribs)
        if characteristic == "coaxiality":
            msp.add_circle((cx, cy), 0.25*h, dxfattribs=attribs)
    elif characteristic == "perpendicularity":
        msp.add_line((cx-.55*h, cy-.4*h), (cx+.55*h, cy-.4*h), dxfattribs=attribs)
        msp.add_line((cx, cy-.4*h), (cx, cy+.5*h), dxfattribs=attribs)
    elif characteristic == "parallelism":
        for dx in (-.25*h, .25*h):
            msp.add_line((cx+dx-.2*h,cy-.5*h),(cx+dx+.2*h,cy+.5*h), dxfattribs=attribs)
    else:
        raise ValueError("unsupported characteristic %r; supported: %s"
                         % (characteristic, ", ".join(_FCF_CHARS)))


def feature_control_frame(msp, insert, characteristic, value, datum=None,
                          height=3.5, *, target=None, elbow=None, arrow=True,
                          zone=None, feature=None):
    """Geometric tolerance frame at bottom-left ``insert``; returns
    (left, bottom, right, top). Cells: symbol | value | datum letters.

    Drawn as editable lines/text (not a native TOLERANCE entity).
    With ``target``, attaches a leader entering the LEFT-edge midpoint
    with a horizontal final segment (see frame_leader).
    """
    if characteristic not in _FCF_CHARS:
        raise ValueError("unsupported characteristic %r; supported: %s"
                         % (characteristic, ", ".join(_FCF_CHARS)))
    previous = {e.dxf.handle for e in msp}
    x, y = insert
    H = 2 * height
    vstr = ("%g" % value) if isinstance(value, (int, float)) else str(value)
    datums = []
    if datum is not None:
        datums = list(datum) if isinstance(datum, (list, tuple)) else [str(datum)]
    if len(datums) > 3:
        raise ValueError("at most three ordered datum cells")
    if zone in ("circle", "cylinder") and not vstr.startswith(("φ", "%%c")):
        vstr = "φ" + vstr
    elif zone == "sphere" and not vstr.startswith("Sφ"):
        vstr = "Sφ" + vstr
    font = msp.doc.styles.get("CAD_TEXT").dxf.font
    widths = [H, max(H, text_width(vstr, font, height) + height)]
    widths += [max(H, text_width(d, font, height) + height) for d in datums]
    total = sum(widths)
    border = msp.add_lwpolyline([(x, y), (x + total, y), (x + total, y + H), (x, y + H)],
                       close=True, dxfattribs={"layer": "DIM"})
    cx = x
    for w in widths[:-1]:
        cx += w
        msp.add_line((cx, y), (cx, y + H), dxfattribs={"layer": "DIM"})
    _draw_fcf_symbol(msp, characteristic, x + widths[0] / 2, y + H / 2, height)
    t = add_text(msp, vstr, (0, 0), height)
    t.set_placement((x + widths[0] + widths[1] / 2, y + H / 2),
                    align=TextEntityAlignment.MIDDLE_CENTER)
    cell_x = x + widths[0] + widths[1]
    for d, w in zip(datums, widths[2:]):
        t = add_text(msp, d, (0, 0), height)
        t.set_placement((cell_x + w / 2, y + H / 2),
                        align=TextEntityAlignment.MIDDLE_CENTER)
        cell_x += w
    bounds = (x, y, x + total, y + H)
    from drawing_checks import mark_annotation
    mark_annotation(border, "frame", characteristic=characteristic, value=vstr,
                    datums=datums, zone=zone, feature=feature, target=target, bounds=bounds)
    if target is not None:
        ld = frame_leader(msp, bounds, target, elbow=elbow, arrow=arrow, height=height)
        mark_annotation(border, "frame", characteristic=characteristic, value=vstr,
                        datums=datums, zone=zone, feature=feature, target=target,
                        bounds=bounds, leader=ld.dxf.handle)
    from drawing_layout import register_group, new_entities
    register_group(border, new_entities(msp, previous), "frame")
    return bounds


def cutting_marks(msp, x, y, label, *, half_span=26, height=3.5):
    """Mirrored cut marks and labels; return the shared section anchor."""
    from drawing_layout import register_group
    members, labels = [], []
    for sign in (-1,1):
        a,b=(x,y+sign*(half_span-6)),(x,y+sign*half_span)
        members.append(msp.add_line(a,b))
        members.append(msp.add_leader([(x+7,b[1]),b],override={"dimasz":2.5},dxfattribs={"layer":"DIM"}))
        text=add_text(msp,label,(0,0),height)
        text.set_placement((x-5,y+sign*(half_span+4)),align=TextEntityAlignment.MIDDLE_CENTER)
        members.append(text); labels.append(text.dxf.handle)
    register_group(members[0],members,"cutting",center=(x,y),labels=labels,
                   marks=[members[0].dxf.handle,members[3].dxf.handle])
    return members[0]


def section_axes(msp, cut, cy, radius, label, *, height=3.5):
    """Project section centre from the ACTUAL cutting mark, not another x input."""
    from drawing_layout import register_group
    cx=cut.dxf.start.x
    vertical=msp.add_line((cx,cy-radius-5),(cx,cy+radius+5),dxfattribs={"layer":"CENTER"})
    horizontal=msp.add_line((cx-radius-5,cy),(cx+radius+5,cy),dxfattribs={"layer":"CENTER"})
    text=add_text(msp,label+"-"+label,(0,0),height)
    text.set_placement((cx,cy-radius-12),align=TextEntityAlignment.MIDDLE_CENTER)
    register_group(vertical,[vertical,horizontal,text],"section",cut=cut.dxf.handle,label=text.dxf.handle)
    return cx


def frame_leader(msp, bounds, target, *, elbow=None, arrow=True, height=3.5):
    """Connect ``target`` to the left-edge midpoint of an existing frame.

    The final segment is always horizontal. Without an explicit elbow a
    vertical-then-horizontal route is generated when needed. arrow=False
    draws a plain extension connection (no arrowhead) for derived
    axes/median planes attached to a size dimension line.
    """
    left, bottom, right, top = bounds
    mid_y = (bottom + top) / 2.0
    attach = (left, mid_y)
    if elbow is not None:
        if abs(elbow[1] - mid_y) > _EPS:
            raise ValueError("elbow must lie on the frame's horizontal mid-line")
    elif abs(target[1] - mid_y) > _EPS:
        # target left of the frame: vertical extension then horizontal;
        # target under/over the frame: elbow outside the frame's left edge
        ex = target[0] if target[0] < left else left - 2 * height
        elbow = (ex, mid_y)
    pts = [target] + ([elbow] if elbow is not None else []) + [attach]
    if arrow:
        return msp.add_leader(vertices=pts,
                              override={"dimldrblk": "", "dimasz": height * 0.7},
                              dxfattribs={"layer": "DIM"})
    return msp.add_lwpolyline(pts, dxfattribs={"layer": "DIM"})
