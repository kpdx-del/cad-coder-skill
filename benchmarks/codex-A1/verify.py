from pathlib import Path
from collections import Counter
import json,sys
import ezdxf
import pypdfium2 as pdfium
from pypdf import PdfWriter
from sketch_helpers import audit_annotations
from zipfile import ZipFile,ZIP_DEFLATED
root=Path(__file__).parent
writer=PdfWriter()
observed={}
for n in ("01","02","03"):
    p=root/n
    doc=ezdxf.readfile(p/"drawing.dxf")
    dims=list(doc.modelspace().query("DIMENSION"))
    sizes=[round(dim.get_measurement(),3) for dim in dims]
    dev=[(round(dim.get_measurement(),3),dim.override().get("dimtp"),-dim.override().get("dimtm",0)) for dim in dims if dim.override().get("dimtol")]
    pdf=pdfium.PdfDocument(p/"drawing.pdf")
    w,h=pdf[0].get_size()
    pdf[0].render(scale=1.2).to_pil().convert("RGB").save(p/"print-view.png")
    writer.append(str(p/"drawing.pdf"),outline_item=n)
    observed[n]=dict(size_mm=[round(v*25.4/72,3) for v in (w,h)],pages=len(pdf),measurements=sizes,expected_dimensions=Counter(sizes)==Counter([30,40,25,40,35,125,24,20,7,98,8,6]),tolerances=dev,arrow_check=audit_annotations(doc.modelspace(),required_arrows={e.dxf.handle:(1,2) for e in dims}))
writer.add_metadata({"/Title":"CASE-A1 | 01 / 02 / 03"})
writer.write(root/"compare.pdf")
(root/"verification.json").write_text(json.dumps(observed,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(observed,ensure_ascii=False))
with ZipFile(root/"CASE-A1.zip","w",ZIP_DEFLATED) as z:
    for n in observed:
        for f in ("drawing.dxf","drawing.pdf","source.py","preview.png","print-view.png"):
            z.write(root/n/f,n+"/"+f)
    for f in ("input.md","compare.pdf","verification.json","verify.py","check_slot_text.py","slot-check.json"):
        z.write(root/f,f)
