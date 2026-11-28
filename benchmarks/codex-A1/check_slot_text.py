"""CASE-A1: flag horizontal centerlines passing through slot-width text bounds."""
from pathlib import Path
import json
import ezdxf
from ezdxf import bbox

def conflicts(path):
    m=ezdxf.readfile(path).modelspace()
    axes=[(min(l.dxf.start.x,l.dxf.end.x),max(l.dxf.start.x,l.dxf.end.x),l.dxf.start.y)
          for l in m.query('LINE[layer=="CENTER"]') if abs(l.dxf.start.y-l.dxf.end.y)<1e-6]
    hits=[]
    for d in m.query("DIMENSION"):
        if d.get_measurement() not in (6,8): continue
        for t in d.virtual_entities():
            if t.dxftype() not in ("TEXT","MTEXT"): continue
            box=bbox.extents([t])
            if any(box.extmin.y < y < box.extmax.y and a < box.extmax.x and box.extmin.x < b for a,b,y in axes):
                hits.append(d.get_measurement())
    return hits
if __name__=="__main__":
    root=Path(__file__).parent
    paths={n:root/n/"drawing.dxf" for n in ("01","02","03")}
    results={n:conflicts(p) for n,p in paths.items()}
    print(results)
    (root/"slot-check.json").write_text(json.dumps(results,indent=2))
