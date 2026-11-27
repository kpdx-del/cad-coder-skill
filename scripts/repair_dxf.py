"""Conservative typography repair in a new DXF, with before/after record."""
import argparse
import json
from pathlib import Path
import ezdxf
from drawing_checks import audit_drawing
from typography import check_glyphs, register_font, style_for


def _technical_fingerprint(doc):
    return ([(e.dxf.handle, e.dxftype(), e.dxf.text if e.dxftype() == "TEXT" else e.text)
             for block in doc.blocks for e in block if e.dxftype() in ("TEXT", "MTEXT")],
            [(e.dxf.handle, e.get_measurement(), sorted(e.get_acad_dstyle(doc.dimstyles.get(e.dxf.dimstyle)).items()))
             for e in doc.modelspace().query("DIMENSION")])


def repair_dxf(source, output, *, font="isocp___.ttf", cjk_font="simfang.ttf"):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError("Repair requires a new, unused output path; original is preserved")
    doc = ezdxf.readfile(source)
    before = _technical_fingerprint(doc)
    for style, name in (("CAD_TEXT", font), ("CAD_CJK", cjk_font)):
        registered = register_font(name)
        if style not in doc.styles:
            doc.styles.new(style, dxfattribs={"font": registered})
        else:
            doc.styles.get(style).dxf.font = registered
    changes = []
    for block in doc.blocks:
        for entity in block:
            if entity.dxftype() not in ("TEXT", "MTEXT"):
                continue
            style = style_for(entity.plain_text())
            check_glyphs(entity.plain_text(), doc.styles.get(style).dxf.font)
            old = entity.dxf.style
            if old != style:
                entity.dxf.style = style
                changes.append(dict(entity=entity.dxf.handle, field="style", before=old, after=style))
    # No arbitrary DIMENSION regeneration: unknown conventions stay intact.
    if _technical_fingerprint(doc) != before:
        raise AssertionError("Repair changed technical text or dimension data")
    doc.saveas(output)
    reopened = ezdxf.readfile(output)
    if _technical_fingerprint(reopened) != before:
        raise AssertionError("Technical data changed during DXF roundtrip")
    return dict(changes=changes, style_fonts={"CAD_TEXT": font, "CAD_CJK": cjk_font},
                issues=audit_drawing(reopened.modelspace()),
                limitations=["Font repair only; review layout and semantics before formal delivery"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    result = repair_dxf(args.source, args.output)
    Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return int(any(i["severity"] == "error" for i in result["issues"]))


if __name__ == "__main__":
    raise SystemExit(main())
