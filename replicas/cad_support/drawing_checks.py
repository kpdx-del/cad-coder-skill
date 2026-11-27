"""Preflight, provenance, declared dimension chains, annotation diagnostics.

Semantic checks use declared features; they never infer design intent from pixels.
All returned issues are JSON serializable. Empty issues != universal GB compliance.
"""
import argparse
import json
import math
import re
from pathlib import Path

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
