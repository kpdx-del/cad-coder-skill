"""Preflight, provenance, declared dimension chains, annotation diagnostics.

Semantic checks use declared features; they never infer design intent from pixels.
All returned issues are JSON serializable. Empty issues != universal GB compliance.
"""
import argparse
import json
import math
import re
from pathlib import Path

from ezdxf.lldxf.const import LINEWEIGHT_BYBLOCK, LINEWEIGHT_BYLAYER, LINEWEIGHT_DEFAULT
from ezdxf.math import Vec2

APP = "CAD_CODER"
PART_REQUIRED = {
    "shaft": ("diameters", "axial_dimensions"),
    "gear": ("module", "teeth", "pressure_angle", "width", "bore"),
    "bearing_seat": ("interface_dimensions",),
    "key_spline": ("type", "specification", "connection"),
    "thread": ("type", "specification", "length"),
    "taper": ("independent_geometry", "reference_plane", "tolerance_method"),
}
CONDITIONAL = {
    "helical": ("helix_angle", "hand"),
    "design_fit": ("load_type", "rotation_relation", "operating_conditions"),
    "keyway": ("keyway_width", "keyway_depth", "keyway_length"),
    "datum_control": ("datum_scheme", "geometric_tolerances"),
    "nonstandard_thread": ("pitch", "hand", "starts"),
}


def issue(code, message, *, severity="error", entity=None, location=None,
          basis="Declared drawing inputs and geometry; see references/checking.md", suggestion=""):
    return dict(code=code, severity=severity, entity=entity, message=message,
                location=location, basis=basis, suggestion=suggestion)


def mark_annotation(entity, kind, **data):
    if APP not in entity.doc.appids:
        entity.doc.appids.new(APP)
    raw = json.dumps(dict(kind=kind, **data), ensure_ascii=True, separators=(",", ":"))
    entity.set_xdata(APP, [(1000, raw[n:n+240]) for n in range(0, len(raw), 240)])


def annotation_data(entity):
    if not entity.has_xdata(APP):
        return {}
    return json.loads("".join(t.value for t in entity.get_xdata(APP) if t.code == 1000))


def validate_inputs(spec, *, formal=True):
    """Validate supplied values and traceability, without inventing defaults.

    parameters: name -> {value, source: {kind, ...}}.
    source kinds: user(statement), reference(document, locator, edition),
    formula(expression, inputs), proposal(reason, confirmed).
    required lists additional geometry-specific parameter names.
    """
    out = []
    part = spec.get("part_type")
    if part not in PART_REQUIRED:
        return [issue("PART_TYPE", "Select a supported part_type")]
    if spec.get("mode") not in ("course", "engineering"):
        out.append(issue("MODE", "Select course or engineering mode"))
    if not spec.get("references"):
        out.append(issue("BASIS_MISSING", "Supply the course references or standard with edition"))
    parameters = spec.get("parameters", {})
    required = set(PART_REQUIRED[part]) | set(spec.get("required", []))
    for flag, names in CONDITIONAL.items():
        if spec.get("conditions", {}).get(flag) is True:
            required.update(names)
    for name in sorted(required):
        value = parameters.get(name, {}).get("value")
        if value is None or value == "" or value == [] or value == {}:
            out.append(issue("PARAM_MISSING", f"Missing required parameter: {name}",
                             severity="error" if formal else "warning", entity=name,
                             suggestion="Ask only for this missing information; draft may omit its feature"))
    for name, record in parameters.items():
        if "value" not in record or record["value"] is None:
            continue
        source = record.get("source", {})
        kind = source.get("kind")
        fields = {"user": ("statement",), "reference": ("document", "locator", "edition"),
                  "formula": ("expression", "inputs"), "proposal": ("reason",)}
        if kind not in fields or any(not source.get(k) for k in fields.get(kind, ())):
            out.append(issue("SOURCE_MISSING", f"Incomplete provenance for {name}", entity=name))
        if kind == "formula":
            for dependency in source.get("inputs", []):
                if dependency not in parameters or parameters[dependency].get("value") is None:
                    out.append(issue("FORMULA_INPUT", f"Missing input {dependency} for {name}", entity=name))
        if kind == "proposal" and source.get("confirmed") is not True:
            out.append(issue("DESIGN_UNCONFIRMED", f"Unconfirmed design suggestion: {name}",
                             severity="error" if formal else "warning", entity=name))
        if isinstance(record["value"], (int, float)) and not math.isfinite(record["value"]):
            out.append(issue("NONFINITE", f"Non-finite value: {name}", entity=name))
        if name in ("module", "teeth", "pressure_angle", "width", "length", "pitch", "starts"):
            value = record["value"]
            if not isinstance(value, (int, float)) or value <= 0:
                out.append(issue("POSITIVE_PARAMETER", f"Positive numeric value required: {name}", entity=name))
        if name in ("diameters", "axial_dimensions"):
            if not isinstance(record["value"], list) or any(not isinstance(v, (int,float)) or v <= 0 for v in record["value"]):
                out.append(issue("GEOMETRY_VALUES", f"Explicit positive geometry values required: {name}", entity=name))
        if "upper" in record or "lower" in record:
            if "upper" not in record or "lower" not in record or record["upper"] < record["lower"]:
                out.append(issue("DEVIATIONS", f"Invalid deviation pair: {name}", entity=name))
    graph = {name:record.get("source", {}).get("inputs", []) for name,record in parameters.items()
             if record.get("source", {}).get("kind") == "formula"}
    def cyclic(node, visiting, visited):
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        found = any(cyclic(n, visiting, visited) for n in graph.get(node, []) if n in graph)
        visiting.remove(node)
        visited.add(node)
        return found
    if any(cyclic(n, set(), set()) for n in graph):
        out.append(issue("FORMULA_CYCLE", "Formula inputs contain a circular dependency"))
    if spec.get("units") != "mm":
        out.append(issue("UNITS", "Explicit millimetre units required"))
    return out


def assert_ready(spec, *, formal=True):
    findings = validate_inputs(spec, formal=formal)
    errors = [i["message"] for i in findings if i["severity"] == "error"]
    if errors:
        raise ValueError("Drawing preflight failed: " + "; ".join(errors))
    return findings


def check_dimension_chain(edges):
    """Each declared edge: start/end node names, value, optional reference/function.

    Detect redundant/contradictory graph cycles. Never delete a functional size.
    Edge direction defines its signed value (end position minus start position).
    """
    graph = {}
    out = []
    for index, edge in enumerate(edges):
        start, end, value = edge["start"], edge["end"], edge["value"]
        stack, seen, found = [(start, 0.0)], set(), None
        while stack:
            node, distance = stack.pop()
            if node == end:
                found = distance
                break
            if node in seen:
                continue
            seen.add(node)
            stack += [(n, distance+v) for n, v in graph.get(node, []) if n not in seen]
        if found is not None:
            if not math.isclose(found, value, abs_tol=1e-6):
                out.append(issue("CHAIN_CONTRADICTION", f"Dimension {value} contradicts derived {found}", entity=index))
            elif not edge.get("reference", False):
                out.append(issue("CHAIN_CLOSED", "Redundant independent dimension closes a chain", entity=index,
                                 basis="Functional dimension selection; nominal graph relation",
                                 suggestion="Keep functional sizes; omit a confirmed nonfunctional derived size or mark reference"))
        if not edge.get("reference", False):
            graph.setdefault(start, []).append((end, value))
            graph.setdefault(end, []).append((start, -value))
    return out


def derive_difference(total, parts):
    """Worst-case remaining interval; tuples = (nominal, signed upper, lower).
    Calculation of limits is not a manufacturing tolerance allocation decision.
    """
    for nominal, upper, lower in [total, *parts]:
        if upper < lower:
            raise ValueError("upper deviation must be >= lower deviation")
    nominal = total[0] - sum(p[0] for p in parts)
    maximum = total[0]+total[1] - sum(p[0]+p[2] for p in parts)
    minimum = total[0]+total[2] - sum(p[0]+p[1] for p in parts)
    return nominal, maximum-nominal, minimum-nominal


def check_section_alignment(cutting_direction, section_direction):
    """Check a declared corresponding centre direction (not infer it from labels)."""
    a,b=Vec2(cutting_direction),Vec2(section_direction)
    if a.magnitude < 1e-9 or b.magnitude < 1e-9:
        return [issue("SECTION_DIRECTION", "Section/cutting direction cannot be zero")]
    if abs(a.det(b)) > 1e-6*a.magnitude*b.magnitude:
        return [issue("SECTION_ALIGNMENT", "Corresponding section centre direction must be parallel to its cutting direction")]
    return []


def _on_line(point, line):
    p, a, b = Vec2(point), Vec2(line[0]), Vec2(line[1])
    if a.isclose(b):
        raise ValueError("Declared feature line is degenerate")
    return abs((p-a).det(b-a)) <= 1e-5 * (b-a).magnitude


def _center_2d(entity):
    c = entity.dxf.get("center")
    return [float(c[0]), float(c[1])] if c is not None else None


def audit_fasteners(msp):
    """Structure audit for explicitly marked fastener representations.

    Only entities carrying a CAD_CODER ``thread_end`` or ``fastener_hex_side``
    marker are inspected; an unmarked (foreign) DXF is never interpreted as a
    bolt or nut. Marked entities that predate the association metadata are
    reported for manual review and are never auto-paired.
    """
    out = []
    out.extend(_audit_thread_end(msp))
    out.extend(_audit_hex_side(msp))
    return out


def _resolve_lineweight(entity):
    """Resolve an entity's effective line width in millimetres.

    An explicit entity override wins; BYLAYER defers to the layer. BYBLOCK
    and the document default cannot be resolved here and are reported as
    uncertain rather than guessed.
    """
    lw = entity.dxf.lineweight
    if lw == LINEWEIGHT_BYBLOCK:
        return ("byblock", None)
    if lw == LINEWEIGHT_DEFAULT:
        return ("default", None)
    if lw != LINEWEIGHT_BYLAYER:
        return ("value", float(lw) / 100.0)
    layer = entity.doc.layers.get(entity.dxf.layer)
    llw = layer.dxf.lineweight
    if llw == LINEWEIGHT_BYBLOCK:
        return ("byblock", None)
    if llw == LINEWEIGHT_DEFAULT or llw is None or llw <= 0:
        return ("default", None)
    return ("value", float(llw) / 100.0)


def _audit_thread_end(msp):
    out = []
    marked = [e for e in msp if annotation_data(e).get("kind") == "thread_end"]
    groups, legacy = {}, []
    for e in marked:
        data = annotation_data(e)
        group, role = data.get("group"), data.get("role")
        if group is None or role not in ("crest", "root"):
            legacy.append((e, data))
            continue
        roles = groups.setdefault(group, {})
        if role in roles:
            out.append(issue("THREAD_DUPLICATE_ROLE",
                             "Thread end group declares duplicate %s entities" % role,
                             entity=e.dxf.handle,
                             basis="GB/T 4459.1: one crest and one root per end view",
                             suggestion="Keep a single crest and a single root"))
            continue
        roles[role] = (e, data)
    for e, _ in legacy:
        out.append(issue("THREAD_GROUP_REVIEW",
                         "Marked thread entity lacks explicit crest/root association; review manually",
                         severity="review", entity=e.dxf.handle,
                         basis="Association metadata is required to detect thread structure after round-trip",
                         suggestion="Regenerate with thread_end or associate crest/root explicitly; do not guess pairing"))
    for roles in groups.values():
        crest, root = roles.get("crest"), roles.get("root")
        if crest is None or root is None:
            present = crest if crest is not None else root
            missing = "root (thin 3/4 arc)" if crest is not None else "crest (thick full circle)"
            e, _ = present
            out.append(issue("THREAD_MEMBER_MISSING",
                             "Thread end group is missing its " + missing,
                             entity=e.dxf.handle, location=_center_2d(e),
                             basis="GB/T 4459.1 thread end view needs both crest and root entities",
                             suggestion="Restore the paired entity or regenerate the thread end view"))
            continue
        ce, cdata = crest
        re_, rdata = root
        # The written sibling fields are checked, not ignored: each role must
        # name its counterpart, and both must agree on the pairing.
        if cdata.get("sibling") != re_.dxf.handle or rdata.get("sibling") != ce.dxf.handle:
            out.append(issue("THREAD_SIBLING",
                             "Thread crest/root sibling references are broken or not mutual",
                             entity=ce.dxf.handle,
                             basis="Association metadata must point each role at its counterpart",
                             suggestion="Restore the crest/root sibling references"))
        internal = bool(cdata.get("internal", False))
        major, minor = cdata.get("major"), cdata.get("minor")
        if not (isinstance(major, (int, float)) and isinstance(minor, (int, float))
                and math.isfinite(major) and math.isfinite(minor) and 0 < minor < major):
            out.append(issue("THREAD_METADATA",
                             "Thread end metadata has invalid major/minor diameters",
                             entity=ce.dxf.handle,
                             basis="Only the supplied major/minor diameters are validated",
                             suggestion="Regenerate with explicit 0 < minor < major"))
            continue
        crest_d = minor if internal else major
        root_d = major if internal else minor
        c_w, r_w = _resolve_lineweight(ce), _resolve_lineweight(re_)
        if "byblock" in (c_w[0], r_w[0]):
            out.append(issue("THREAD_WEIGHT_REVIEW",
                             "Thread crest/root line weight depends on BYBLOCK; review manually",
                             severity="review", entity=ce.dxf.handle,
                             basis="GB/T 4459.1: crest thick full circle, root thin 3/4 arc",
                             suggestion="Set explicit or layer line weights so thick/thin is unambiguous"))
        elif "default" in (c_w[0], r_w[0]):
            out.append(issue("THREAD_WEIGHT_REVIEW",
                             "Thread crest/root line weight defers to the document default; review manually",
                             severity="review", entity=ce.dxf.handle,
                             basis="GB/T 4459.1: crest thick full circle, root thin 3/4 arc",
                             suggestion="Set explicit or layer line weights so thick/thin is unambiguous"))
        elif not (c_w[1] > r_w[1]):
            out.append(issue("THREAD_WEIGHT",
                             "Crest must be thicker than root (effective %.2f vs %.2f mm)" % (c_w[1], r_w[1]),
                             entity=ce.dxf.handle, location=_center_2d(ce),
                             basis="GB/T 4459.1: crest is the thick full circle, root is the thin 3/4 arc",
                             suggestion="Restore the effective thick/thin line weights"))
        out.extend(_audit_thread_role(ce, "crest", crest_d))
        out.extend(_audit_thread_role(re_, "root", root_d))
        cc, rc = _center_2d(ce), _center_2d(re_)
        if cc is None or rc is None:
            out.append(issue("THREAD_CENTER_OFFSET",
                             "Thread crest/root centre cannot be read", entity=ce.dxf.handle))
        elif math.hypot(cc[0]-rc[0], cc[1]-rc[1]) > 1e-5:
            out.append(issue("THREAD_CENTER_OFFSET",
                             "Thread crest and root centres are offset",
                             entity=ce.dxf.handle, location=[cc, rc],
                             basis="GB/T 4459.1: crest and root share the same axis",
                             suggestion="Coincide the crest and root centres"))
    return out


def _audit_thread_role(entity, role, diameter):
    out = []
    handle = entity.dxf.handle
    kind = entity.dxftype()
    if role == "crest" and kind != "CIRCLE":
        out.append(issue("THREAD_ROLE", "Crest must be a thick full circle", entity=handle,
                         location=_center_2d(entity),
                         basis="GB/T 4459.1: crest is the full circle",
                         suggestion="Restore the crest as a full CIRCLE"))
    if role == "root" and kind != "ARC":
        out.append(issue("THREAD_ROLE", "Root must be a thin 3/4 arc", entity=handle,
                         location=_center_2d(entity),
                         basis="GB/T 4459.1: root is a thin 3/4 circle",
                         suggestion="Restore the root as an ARC"))
    if kind in ("CIRCLE", "ARC"):
        radius = entity.dxf.radius
        # A single clear report: compare the radius to the given diameter/2.
        if not math.isclose(radius, diameter / 2.0, rel_tol=0.0, abs_tol=1e-6):
            out.append(issue("THREAD_RADIUS",
                             ("%s radius %g does not equal declared %g"
                              % (role.capitalize(), radius, diameter / 2.0)),
                             entity=handle, location=_center_2d(entity),
                             basis="Only supplied major/minor diameters are checked",
                             suggestion="Restore the declared crest/root radius"))
        if role == "root" and kind == "ARC":
            span = (entity.dxf.end_angle - entity.dxf.start_angle) % 360.0
            if abs(span - 270.0) > 1e-3:
                out.append(issue("THREAD_ARC_SPAN",
                                 "Root arc spans %g degrees, expected about 270" % span,
                                 entity=handle, location=_center_2d(entity),
                                 basis="GB/T 4459.1: thread root is an approximately 3/4 circle",
                                 suggestion="Restore the ~270 degree thin arc"))
    return out


def _audit_hex_side(msp):
    out = []
    marked = [e for e in msp if annotation_data(e).get("kind") == "fastener_hex_side"]
    groups, legacy = {}, []
    for e in marked:
        data = annotation_data(e)
        group, role = data.get("group"), data.get("role")
        if group is None or role not in ("boundary", "face", "centerline"):
            legacy.append((e, data))
            continue
        groups.setdefault(group, {}).setdefault(role, []).append((e, data))
    for e, _ in legacy:
        out.append(issue("HEX_GROUP_REVIEW",
                         "Marked fastener side entity lacks explicit boundary/face association; review manually",
                         severity="review", entity=e.dxf.handle,
                         basis="Association metadata is required to detect side-view structure after round-trip",
                         suggestion="Regenerate with hex_head_side or associate boundary/faces explicitly; do not guess pairing"))
    for group, roles in groups.items():
        boundary = (roles.get("boundary") or [None])[0]
        faces = roles.get("face", [])
        if boundary is None:
            ref = faces[0][0] if faces else None
            out.append(issue("HEX_CONTOUR_MISSING",
                             "Fastener side outer contour is missing",
                             entity=ref.dxf.handle if ref is not None else group,
                             basis="GB/T 4459.1: side view needs its closed outer profile",
                             suggestion="Restore the boundary LWPOLYLINE or regenerate the side view"))
            if len(faces) != 2:
                out.append(issue("HEX_FACE_MISSING",
                                 "Fastener side must have two projected face edges, found %d" % len(faces),
                                 entity=ref.dxf.handle if ref is not None else group,
                                 basis="GB/T 4459.1: side view shows both projected flats at +/-e/4",
                                 suggestion="Restore the missing face edge"))
        else:
            b, bdata = boundary
            out.extend(_audit_hex_boundary(b, bdata))
            declared = bdata.get("faces")
            actual = {f.dxf.handle for f, _ in faces}
            if isinstance(declared, list):
                for face_handle in declared:
                    if face_handle not in actual:
                        out.append(issue("HEX_FACE_MISSING",
                                         "Projected face edge is missing or its association is broken",
                                         entity=b.dxf.handle,
                                         basis="GB/T 4459.1: side-view flats must stay associated with the contour",
                                         suggestion="Restore the face edge and its group reference"))
            else:
                out.append(issue("HEX_GROUP_REVIEW",
                                 "Fastener side contour lacks its declared face-edge list; review manually",
                                 severity="review", entity=b.dxf.handle))
                if len(faces) != 2:
                    out.append(issue("HEX_FACE_MISSING",
                                     "Fastener side must have two projected face edges, found %d" % len(faces),
                                     entity=b.dxf.handle,
                                     basis="GB/T 4459.1: side view shows both projected flats at +/-e/4",
                                     suggestion="Restore the missing face edge"))
        # The centre line is recorded but not structurally checked: it is a
        # drawing aid, not manufacturing data.
        projection = _hex_projection(bdata) if boundary is not None else None
        for f, fdata in faces:
            out.extend(_audit_hex_face(f, fdata,
                                       expected_xs=projection[0] if projection else None,
                                       y_span=projection[1] if projection else None))
    return out


def _hex_projection(data):
    """Projected flat positions derived from the boundary's own dimensions."""
    cx = data.get("center_x"); ac = data.get("across_corners")
    by = data.get("bearing_y"); thickness = data.get("thickness")
    outward = data.get("outward", 1)
    if None in (cx, ac, by, thickness):
        return None
    y1 = by + outward * thickness
    expected_xs = {round(cx - ac / 4.0, 6), round(cx + ac / 4.0, 6)}
    return expected_xs, sorted([round(by, 6), round(y1, 6)])


def _audit_hex_boundary(boundary, data):
    out = []
    handle = boundary.dxf.handle
    if boundary.dxftype() != "LWPOLYLINE":
        return [issue("HEX_CONTOUR", "Outer contour must be a closed LWPOLYLINE", entity=handle,
                      basis="GB/T 4459.1 side-view profile",
                      suggestion="Restore the boundary as a closed LWPOLYLINE")]
    cx = data.get("center_x"); by = data.get("bearing_y")
    ac = data.get("across_corners"); thickness = data.get("thickness")
    outward = data.get("outward", 1)
    if None in (cx, by, ac, thickness):
        out.append(issue("HEX_GROUP_REVIEW",
                         "Fastener side contour lacks projection metadata; review manually",
                         severity="review", entity=handle))
        return out
    r = ac / 2.0
    y1 = by + outward * thickness
    if not boundary.closed:
        out.append(issue("HEX_CONTOUR", "Outer contour is not closed", entity=handle,
                         basis="GB/T 4459.1: side profile is closed",
                         suggestion="Close the boundary"))
    pts = [(round(float(p[0]), 6), round(float(p[1]), 6)) for p in boundary.get_points("xy")]
    expected = sorted([(round(cx - r, 6), round(by, 6)),
                       (round(cx + r, 6), round(by, 6)),
                       (round(cx + r, 6), round(y1, 6)),
                       (round(cx - r, 6), round(y1, 6))])
    if sorted(pts) != expected:
        out.append(issue("HEX_CONTOUR",
                         "Outer contour corners do not match the across-corners projection (outer x=+/-e/2)",
                         entity=handle, location=pts,
                         basis="GB/T 4459.1: with across-corners e, side-view outer x = +/-e/2",
                         suggestion="Restore boundary corners to center_x +/- across_corners/2"))
    elif len(pts) == 4 and any(pts[i][0] != pts[(i + 1) % 4][0] and pts[i][1] != pts[(i + 1) % 4][1]
                               for i in range(4)):
        out.append(issue("HEX_CONTOUR",
                         "Outer contour edges are not axis-aligned (self-intersecting outline)",
                         entity=handle, location=pts,
                         basis="GB/T 4459.1: side profile is a plain rectangle",
                         suggestion="Restore the four rectangle corners in cyclic order"))
    return out


def _audit_hex_face(face, data, expected_xs=None, y_span=None):
    out = []
    handle = face.dxf.handle
    if face.dxftype() != "LINE":
        return [issue("HEX_FACE", "Projected face edge must be a LINE", entity=handle,
                      basis="GB/T 4459.1 side-view flats are straight edges",
                      suggestion="Restore the face edge as a LINE")]
    if expected_xs is None and (data.get("x") is None or data.get("bearing_y") is None
                                or data.get("y1") is None):
        return [issue("HEX_GROUP_REVIEW",
                      "Projected face edge lacks position metadata; review manually",
                      severity="review", entity=handle)]
    sx, sy = float(face.dxf.start.x), float(face.dxf.start.y)
    ex, ey = float(face.dxf.end.x), float(face.dxf.end.y)
    if expected_xs is not None:
        if abs(sx - ex) > 1e-5 or not any(abs(sx - tx) <= 1e-5 and abs(ex - tx) <= 1e-5
                                          for tx in expected_xs):
            out.append(issue("HEX_FACE",
                             "Projected face edge is off its boundary projection x in {%s}"
                             % ", ".join("%g" % t for t in sorted(expected_xs)),
                             entity=handle, location=[sx, sy, ex, ey],
                             basis="GB/T 4459.1: with across-corners e, side-view flats are at x=+/-e/4",
                             suggestion="Restore the face edge to the projected flat position"))
    else:
        x = data.get("x")
        if x is not None and (abs(sx - x) > 1e-5 or abs(ex - x) > 1e-5):
            out.append(issue("HEX_FACE",
                             "Projected face edge is off its expected x=%g" % x,
                             entity=handle, location=[sx, sy, ex, ey],
                             basis="GB/T 4459.1: with across-corners e, side-view flats are at x=+/-e/4",
                             suggestion="Restore the face edge to the projected flat position"))
    if y_span is not None:
        actual_y = sorted([round(sy, 6), round(ey, 6)])
        if actual_y != y_span:
            out.append(issue("HEX_FACE",
                             "Projected face edge does not span the head thickness",
                             entity=handle, location=[sx, sy, ex, ey],
                             basis="Face edge runs between bearing surface and head top",
                             suggestion="Restore the face edge vertical span"))
    else:
        by = data.get("bearing_y"); y1 = data.get("y1")
        if by is not None and y1 is not None:
            expected_y = sorted([round(by, 6), round(y1, 6)])
            actual_y = sorted([round(sy, 6), round(ey, 6)])
            if actual_y != expected_y:
                out.append(issue("HEX_FACE",
                                 "Projected face edge does not span the head thickness",
                                 entity=handle, location=[sx, sy, ex, ey],
                                 basis="Face edge runs between bearing surface and head top",
                                 suggestion="Restore the face edge vertical span"))
    return out


def audit_drawing(msp, *, chains=None):
    """Read-only structured audit. Unknown semantic associations require review."""
    from sketch_helpers import audit_annotations
    out=[]
    for message in audit_annotations(msp):
        match=re.search(r"(?:dimension|leader) ([0-9A-F]+)",message)
        out.append(issue("ANNOTATION_GEOMETRY", message,entity=match[1] if match else None))
    datums = {annotation_data(e).get("label") for e in msp if annotation_data(e).get("kind") == "datum"}
    frames = [e for e in msp if annotation_data(e).get("kind") == "frame"]
    for entity in frames:
        data = annotation_data(entity)
        handle = entity.dxf.handle
        char, value, feature = data["characteristic"], data["value"], data.get("feature")
        if char in ("roundness", "cylindricity", "flatness") and data["datums"]:
            out.append(issue("FORM_DATUM", "This form tolerance must not reference a datum", entity=handle,
                             basis="Textbook Ch.3 Table 3-3"))
        if char in ("symmetry", "coaxiality", "circular_runout") and not data["datums"]:
            out.append(issue("DATUM_REQUIRED", "Location/runout needs a declared datum", entity=handle))
        zone = data.get("zone")
        diameter = value.startswith(("φ", "Sφ", "%%c"))
        if (zone in ("circle", "cylinder", "sphere")) != diameter and zone is not None:
            out.append(issue("ZONE_PREFIX", "Diameter prefix conflicts with declared tolerance zone", entity=handle))
        if char in ("roundness", "cylindricity", "symmetry", "flatness", "circular_runout") and diameter:
            out.append(issue("ZONE_PREFIX", "This project's zone width is not a diameter", entity=handle))
        for cell in data["datums"]:
            for label in cell.split("-"):
                if label not in datums:
                    out.append(issue("DATUM_UNDEFINED", f"Referenced datum {label} is not declared", entity=handle))
        if not feature or not data.get("target"):
            out.append(issue("SEMANTICS_REVIEW", "Confirm controlled feature and attachment", severity="review", entity=handle))
            continue
        target = data["target"]
        if feature.get("measurement_direction") and data.get("leader"):
            ld=msp.doc.entitydb[data["leader"]]
            vertices=ld.vertices if ld.dxftype()=="LEADER" else ld.get_points()
            actual=Vec2(vertices[1])-Vec2(vertices[0])
            expected=Vec2(feature["measurement_direction"])
            if abs(actual.det(expected)) > 1e-6*actual.magnitude*expected.magnitude:
                out.append(issue("MEASUREMENT_DIRECTION", "Leader approach conflicts with declared zone measurement direction",entity=handle))
        if feature["kind"] == "derived":
            if not _on_line(target, feature["size_line"]):
                out.append(issue("DERIVED_ALIGNMENT", "Derived-feature attachment must align with its size line", entity=handle,
                                 basis="Textbook Fig.3-10/Table 3-3"))
        elif feature["kind"] == "surface":
            if not _on_line(target, feature["surface_line"]):
                out.append(issue("SURFACE_ATTACHMENT", "Surface attachment must meet the contour or its extension", entity=handle))
            if feature.get("size_line") and _on_line(target, feature["size_line"]):
                out.append(issue("SURFACE_SIZE_CONFLICT", "Surface indicator must be offset from size line", entity=handle))
    for ld in msp.query("LEADER"):
        vertices = [Vec2(v) for v in ld.vertices]
        if len(vertices) > 4:
            out.append(issue("LEADER_BENDS", "Leader exceeds two bends", entity=ld.dxf.handle))
        if any(a.isclose(b) for a, b in zip(vertices, vertices[1:])):
            out.append(issue("LEADER_ZERO_SEGMENT", "Leader has a zero-length segment", entity=ld.dxf.handle))
        data = annotation_data(ld)
        if data.get("kind") == "chamfer" and data.get("edge") and len(vertices) >= 2:
            if not all(_on_line(p, data["edge"]) for p in vertices[:2]):
                out.append(issue("CHAMFER_DIRECTION", "Arrow-bearing segment is off chamfer extension", entity=ld.dxf.handle))
    out.extend(_text_collisions(msp))
    from drawing_layout import audit_layout
    out.extend(audit_layout(msp))
    out.extend(audit_fasteners(msp))
    for edges in (chains or {}).values():
        out.extend(check_dimension_chain(edges))
    if chains is None and msp.query("DIMENSION"):
        out.append(issue("CHAIN_REVIEW", "Declare functional chains before certifying dimension completeness", severity="review"))
    if not frames:
        out.append(issue("SEMANTICS_REVIEW", "No semantic annotations: external DXF requires feature review", severity="review"))
    return out


def _text_collisions(msp):
    from ezdxf import disassemble
    from typography import text_rect
    # Test text-vs-text with actual entity bounding boxes; hatch/centerline
    # intersections and intentional frame borders are not collisions.
    texts = []
    for entity in disassemble.recursive_decompose(msp):
        if entity.dxftype() in ("TEXT", "MTEXT"):
            box = text_rect(entity)
            if box:
                texts.append((entity, box))
    out = []
    for i, (a, ba) in enumerate(texts):
        for b, bb in texts[i+1:]:
            ox = min(ba[2], bb[2])-max(ba[0], bb[0])
            oy = min(ba[3], bb[3])-max(ba[1], bb[1])
            if ox > 0.15 and oy > 0.15:
                out.append(issue("TEXT_OVERLAP", f"Text bounding boxes overlap: {a.plain_text()} / {b.plain_text()}", entity=a.dxf.handle,
                                 location=list(ba),
                                 suggestion=f"Move intact annotation; other text handle={b.dxf.handle}"))
    return out


def main():
    import ezdxf
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dxf")
    parser.add_argument("--spec", help="JSON preflight parameters and declared chains")
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8")) if args.spec else None
    doc = ezdxf.readfile(args.dxf)
    findings = validate_inputs(spec) if spec else []
    findings += audit_drawing(doc.modelspace(), chains=spec.get("chains") if spec else None)
    Path(args.report).write_text(json.dumps(dict(issues=findings, automatic_coverage="See references/checking.md"),
                                           ensure_ascii=False, indent=2), encoding="utf-8")
    return int(any(i["severity"] == "error" for i in findings))


if __name__ == "__main__":
    raise SystemExit(main())
