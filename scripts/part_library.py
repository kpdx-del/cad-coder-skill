"""Offline read-only query for the first-slice 2D part library.

Only the Python standard library is used. Querying never imports ezdxf,
FreeCAD or CadQuery, never downloads anything, and never executes external
project code. It is an index/query of drawing conventions, parameter
provenance and review rules -- not a set of six generators, not 3D models,
not SolidWorks feature trees.

Exit codes
----------
0  command succeeded (list / search with matches / show / check produced)
1  not_found (search or show/check id unknown)
2  usage or input error (bad arguments, unreadable/invalid parameters file)
"""
import argparse
import json
import sys
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[1] / "library" / "catalog.json"

# Sentinel returned when a parameter record carries no actual value.
_MISSING = object()

# Only these states permit a category to be formally available. Every current
# category is still ``unverified``/``pending``, so flipping a single
# ``formal_available`` flag cannot promote it: data AND implementation must
# both be verified first.
VERIFIED_DATA_STATUSES = frozenset({"verified"})
VERIFIED_HELPER_STATUSES = frozenset({"verified"})


def load_catalog(path=CATALOG_PATH):
    """Read the catalog; only a local JSON file is touched.

    ``utf-8-sig`` tolerates the BOM that Windows tools often prepend.
    """
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _is_missing(value):
    """A value is missing when absent or empty; 0 is a real (present) value."""
    return value is None or value == "" or value == [] or value == {}


def _extract_value(record):
    """Return a parameter's value, or ``_MISSING`` when none is present.

    The documented form is ``{"value": ..., "source": {...}}``. A record that
    only carries ``source`` (provenance without an actual value) is missing,
    not a value. A bare non-dict value is used directly.
    """
    if isinstance(record, dict):
        if "value" in record:
            return record["value"]
        # source-only or otherwise-empty record carries no value
        return _MISSING
    return record


def _tokens(value):
    """Normalize a scalar or list value into lower-case string tokens."""
    if isinstance(value, (list, tuple)):
        return [str(v).strip().lower() for v in value]
    return [str(value).strip().lower()]


def _value_matches(value, choices):
    """Exact, case-insensitive match of a value against any choice."""
    if not choices:
        return False
    norm = {str(c).strip().lower() for c in choices}
    return any(tok in norm for tok in _tokens(value))


def find_category(catalog, identifier):
    """Exact id lookup (case-insensitive). No fuzzy fallback."""
    identifier = str(identifier).strip().lower()
    for cat in catalog["categories"]:
        if cat["id"].lower() == identifier:
            return cat
    return None


def list_categories(catalog):
    """Compact id/name/status listing for the six categories."""
    return [{"id": c["id"], "name_zh": c["name_zh"], "name_en": c["name_en"],
             "status": c["status"]} for c in catalog["categories"]]


def search(catalog, keyword):
    """Case-insensitive substring match over id/中文名/别名. No approximation."""
    kw = str(keyword).strip().lower()
    if not kw:
        return []
    out = []
    for cat in catalog["categories"]:
        haystack = [cat["id"].lower(), cat["name_zh"].lower(), cat["name_en"].lower()]
        haystack += [a.lower() for a in cat.get("aliases", [])]
        if any(kw in h for h in haystack):
            out.append({"id": cat["id"], "name_zh": cat["name_zh"],
                        "name_en": cat["name_en"], "status": cat["status"]})
    return out


def _resolved(parameters, name):
    """Resolve a parameter or condition input to its value, or ``_MISSING``."""
    if name not in parameters:
        return _MISSING
    return _extract_value(parameters[name])


def check(catalog, category_id, parameters):
    """Report only true missing items and pending conditional items.

    Never fills in values and never mutates ``parameters``. ``value == 0`` is
    present (not missing) but is reported invalid for positive parameters.
    ``None``/empty records and ``source``-only records (no ``value``) are
    missing.

    Conditional parameters are decided by an explicit condition input
    (``trigger_key``) and its value, never by the mere presence of a field:

    * value matches ``trigger_required`` -> the parameter is missing;
    * value matches ``trigger_not_required`` -> explicitly not needed, skip;
    * condition input absent or unrecognized -> reported as pending
      (待确认), never silently assumed absent ("unknown" is not "false").
    """
    cat = find_category(catalog, category_id)
    if cat is None:
        return None

    present = set()
    for name, rec in parameters.items():
        val = _extract_value(rec)
        if val is not _MISSING and not _is_missing(val):
            present.add(name)

    missing, pending, invalid_zero = [], [], []

    for p in cat["parameters"]["required"]:
        if p["name"] not in present:
            missing.append({"name": p["name"], "label_zh": p.get("label_zh", ""),
                            "kind": "required"})

    for p in cat["parameters"]["conditional"]:
        name = p["name"]
        if name in present:
            continue
        key = p.get("trigger_key")
        if not key:
            pending.append({"name": name, "label_zh": p.get("label_zh", ""),
                            "condition": p.get("condition", "")})
            continue
        tv = _resolved(parameters, key)
        if tv is _MISSING or _is_missing(tv):
            pending.append({"name": name, "label_zh": p.get("label_zh", ""),
                            "condition": p.get("condition", "")})
            continue
        if _value_matches(tv, p.get("trigger_required", [])):
            missing.append({"name": name, "label_zh": p.get("label_zh", ""),
                            "kind": "conditional",
                            "condition": p.get("condition", "")})
        elif _value_matches(tv, p.get("trigger_not_required", [])):
            continue  # explicitly not needed; do not re-ask
        else:
            pending.append({"name": name, "label_zh": p.get("label_zh", ""),
                            "condition": p.get("condition", "")})

    # Zero is a present value, so it must not appear as missing; for positive
    # parameters it is still reported as invalid.
    all_params = (cat["parameters"]["required"] + cat["parameters"]["conditional"]
                  + cat["parameters"]["optional"])
    for p in all_params:
        name = p["name"]
        if name in present and p.get("positive") and _extract_value(parameters[name]) == 0:
            invalid_zero.append({"name": name, "label_zh": p.get("label_zh", "")})

    # Formal availability is derived from consistent data/implementation state,
    # not from a single flag. Flipping ``formal_available`` while data or
    # helper status stay unverified/pending must not claim formal drawing.
    impl = cat["implementation"]
    flag = bool(impl.get("formal_available", False))
    data_status = impl.get("data_status")
    helper_status = impl.get("helper_status")
    data_ready = data_status in VERIFIED_DATA_STATUSES
    helper_ready = helper_status in VERIFIED_HELPER_STATUSES
    formal_available = flag and data_ready and helper_ready
    formal_reason = impl.get("formal_reason", "")
    if flag and not formal_available:
        blockers = []
        if not data_ready:
            blockers.append("data_status=" + str(data_status))
        if not helper_ready:
            blockers.append("helper_status=" + str(helper_status))
        formal_reason = ("formal_available 与数据/实现状态不一致（"
                         + "、".join(blockers)
                         + "），保持不可正式出图；" + formal_reason)

    complete = not (missing or pending or invalid_zero)
    return {
        "category": cat["id"],
        "name_zh": cat["name_zh"],
        "status": "ok" if complete else "incomplete",
        "missing": missing,
        "conditional_pending": pending,
        "invalid_zero": invalid_zero,
        "implementation": {
            "helper_status": helper_status,
            "data_status": data_status,
            "formal_available": formal_available,
            "formal_reason": formal_reason,
        },
        "note": "参数齐全不代表可正式出图；正式出图前必须核对资料与实现状态。"
                "值 0 不是缺失但可报告无效；None/空记录、仅有 source 而无 value 的记录是缺失。",
    }


def _print(obj, *, indent=None):
    print(json.dumps(obj, ensure_ascii=False, indent=indent))


def _not_found(kind, key):
    _print({"found": False, kind: key, "message": "not_found"})
    return 1


def build_parser():
    parser = argparse.ArgumentParser(
        prog="part_library.py",
        description="Offline read-only query of the 2D part library index.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="compact list of the six categories")

    sp = sub.add_parser("search", help="case-insensitive id/name/alias search")
    sp.add_argument("keyword", help="中文/英文关键词")

    sh = sub.add_parser("show", help="full source/drawing/parameter/status record")
    sh.add_argument("id", help="category id")

    ck = sub.add_parser("check", help="report missing/pending parameters only")
    ck.add_argument("id", help="category id")
    ck.add_argument("--parameters", required=True,
                    help="JSON path of provided parameters (value/source form)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    catalog = load_catalog()

    if args.command == "list":
        _print(list_categories(catalog))
        return 0

    if args.command == "search":
        matches = search(catalog, args.keyword)
        if not matches:
            return _not_found("query", args.keyword)
        _print({"found": True, "matches": matches})
        return 0

    if args.command == "show":
        cat = find_category(catalog, args.id)
        if cat is None:
            return _not_found("id", args.id)
        _print(cat, indent=2)
        return 0

    if args.command == "check":
        cat = find_category(catalog, args.id)
        if cat is None:
            return _not_found("id", args.id)
        try:
            raw = json.loads(Path(args.parameters).read_text(encoding="utf-8-sig"))
        except OSError as exc:
            _print({"error": "cannot read parameters file", "detail": str(exc)})
            return 2
        except json.JSONDecodeError as exc:
            _print({"error": "parameters file is not valid JSON", "detail": str(exc)})
            return 2
        if isinstance(raw, dict) and "parameters" in raw:
            parameters = raw["parameters"]
        else:
            parameters = raw
        if not isinstance(parameters, dict):
            _print({"error": "parameters must be a JSON object (name -> {value, source})"})
            return 2
        report = check(catalog, args.id, parameters)
        _print(report, indent=2)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
