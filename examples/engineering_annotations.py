#!/usr/bin/env python
"""Synthetic annotation demonstration, NOT a manufacturing design or assignment.

python examples/engineering_annotations.py out
Produces editable DXF, A3 1:1 PNG/PDF, parameters and inspection report.
All numeric values below are explicitly authored demonstration data.
"""
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ezdxf
from sketch_helpers import (new_doc, dim_linear, chamfer_note, roughness_symbol,
                           datum_symbol, feature_control_frame, cutting_marks, section_axes)
from typography import add_text
from sheet import draw_sheet
from drawing_checks import assert_ready, audit_drawing
from drawing_layout import choose_position, group_bounds
from render_dxf import render

CHAINS = {"shaft_axis": [
    {"start":"left", "end":"shoulder1", "value":40, "function":"locating"},
    {"start":"shoulder2", "end":"right", "value":35, "function":"coupling"},
    {"start":"left", "end":"right", "value":125, "function":"overall"},
]}


def parameters():
    data = {"diameters":[30,40,25], "axial_dimensions":[40,35,125],
            "demonstration_geometry":"two keyways: width/depth/length 8/4/24 and 6/3/20; chamfer 2x45deg",
            "demonstration_controls":"diameter 30 and 25: upper 0 lower -0.021; 40: +0.042/+0.026; keywidth upper 0 lower -0.016; residual upper 0 lower -0.2; roundness 0.01; symmetry 0.020; roughness Ra1.6/Ra3.2"}
    return {"mode":"course", "part_type":"shaft", "units":"mm",
            "references":["Textbook Ch.3 Figs.3-9/3-10/3-13, Table3-3; Ch.5 Fig.5-10: notation only; all numbers synthetic"],
            "parameters":{name:{"value":value,"source":{"kind":"reference", "document":"examples/engineering_annotations.py", "edition":"engineering-demo-v3", "locator":"parameters/build/section: repository-authored synthetic values"}}
                          for name,value in data.items()}, "chains":CHAINS}


def slot(m, x, y, length, width):
    r = width/2
    m.add_line((x+r,y+r),(x+length-r,y+r))
    m.add_line((x+r,y-r),(x+length-r,y-r))
    m.add_arc((x+r,y),r,90,270)
    m.add_arc((x+length-r,y),r,270,90)
    m.add_line((x-3,y),(x+length+3,y),dxfattribs={"layer":"CENTER"})


def section(m, cut, cy, radius, width, depth, label):
    cx=section_axes(m,cut,cy,radius,label)
    half = width/2
    side = math.sqrt(radius**2-half**2)
    bottom = radius-depth
    a = math.degrees(math.atan2(side,half))
    m.add_arc((cx,cy),radius,180-a,a)
    points=[(cx-half,cy+side),(cx-half,cy+bottom),(cx+half,cy+bottom),(cx+half,cy+side)]
    m.add_lwpolyline(points)
    hatch=m.add_hatch(dxfattribs={"layer":"HATCH"})
    hatch.set_pattern_fill("ANSI31",scale=.7)
    path=hatch.paths.add_edge_path()
    for p,q in zip(points,points[1:]):
        path.add_line(p,q)
    path.add_arc((cx,cy),radius,180-a,a,ccw=False)
    # Complete value group outside; native arrows and line tails move together.
    dim_linear(m,points[1],points[2],-18,upper=0,lower=-.016,
               text_location=(cx-22,cy+bottom+18))
    # Symmetry controls the keyway median plane: attach to WIDTH, not depth.
    wy = cy+bottom+18
    feature_control_frame(m,(cx+36,wy-3.5),"symmetry","0.020","A",target=(cx+half,wy),
                          arrow=False,zone="planes",feature={"kind":"derived","size_line":[(cx-half,wy),(cx+half,wy)]})
    sx = cx+radius+12
    dim_linear(m,(cx,cy-radius),(cx,cy+bottom),cx-sx,angle=90,
               upper=0,lower=-.2,arrows="inside")


def build():
    assert_ready(parameters())
    # Explicit project convention: dimension extension lines touch contours.
    doc = new_doc(extension_gap=0)
    m=doc.modelspace()
    draw_sheet(m,title="标注演示轴（非制造设计）",code="CAD-CODER DEMO",material="",scale="1:1")
    add_text(m,"工程图标注示例",(35,278),height=5)
    add_text(m,"全部数值为演示数据；不作为作业答案或制造依据",(35,267))
    ox,oy=125,210
    # One annular 2x45deg chamfer at the left shaft end appears on BOTH
    # silhouettes. The 2 is a chamfer size, not a count of corners.
    outline=[(0,-13),(0,13),(2,15),(40,15),(40,20),(90,20),(90,12.5),
             (125,12.5),(125,-12.5),(90,-12.5),(90,-20),(40,-20),(40,-15),(2,-15)]
    shaft_profile=[(ox+x,oy+y) for x,y in outline]
    shaft_outline=m.add_lwpolyline(shaft_profile,close=True)
    m.add_line((ox-5,oy),(ox+130,oy),dxfattribs={"layer":"CENTER"})
    slot(m,ox+7,oy,24,8)
    slot(m,ox+98,oy,20,6)
    dim_linear(m,shaft_profile[0],(ox+40,oy-15),shaft_profile[0][1]-(oy-40),
               witness_geometry=shaft_outline)
    dim_linear(m,(ox+90,oy-12.5),(ox+125,oy-12.5),27.5)
    dim_linear(m,shaft_profile[0],(ox+125,oy-12.5),shaft_profile[0][1]-(oy-52),
               witness_geometry=shaft_outline)
    # Middle length 50 is derived from total - two functional end lengths.
    # Full diameter exists at the two post-chamfer silhouette corners.
    # Keep the dimension line at ox-25 using the actual lower corner.
    dim_linear(m,shaft_profile[-1],shaft_profile[2],shaft_profile[-1][0]-(ox-25),angle=90,text="%%c<>",
               upper=0,lower=-.021,witness_geometry=shaft_outline)
    # Both ordinary arrows remain. Datum connects further down the SAME size line.
    datum_y=oy-30
    m.add_line((ox-25,oy-15),(ox-25,datum_y),dxfattribs={"layer":"DIM"})
    datum_symbol(m,(ox-25,datum_y),"A")
    dim_linear(m,(ox+55,oy-20),(ox+55,oy+20),0,angle=90,text="%%c<>",upper=.042,lower=.026)
    dim_linear(m,(ox+125,oy-12.5),(ox+125,oy+12.5),-25,angle=90,text="%%c<>",upper=0,lower=-.021)
    chamfer_note(m,(ox-18,oy+34),target=(ox+2,oy+15),elbow=(ox+21,oy+34),
                 chamfer_edge=((ox,oy+13),(ox+2,oy+15)))
    feature_control_frame(m,(ox+72,oy+39),"roundness",.01,target=(ox+65,oy+20),zone="annulus",
                          feature={"kind":"surface","surface_line":[(ox+40,oy+20),(ox+90,oy+20)],
                                   "size_line":[(ox+55,oy-20),(ox+55,oy+20)]})
    roughness_symbol(m,(ox+80,oy+20),1.6)
    # Reserve the entire cutting-symbol zone before choosing a surface symbol.
    cut_c=cutting_marks(m,ox+27,oy,"C")
    cut_d=cutting_marks(m,ox+110,oy,"D")
    occupied=[group_bounds(cut_d)]
    rx,_=choose_position([(ox+96,oy+12.5),(ox+122,oy+12.5)],(18,7),occupied,clearance=2)
    roughness_symbol(m,(rx,oy+12.5),3.2)
    # Different rows keep the linked projection centres while giving each
    # width/FCF group its own annotation band. No independent section x values.
    section(m,cut_c,117,15,8,4,"C")
    section(m,cut_d,100,12.5,6,3,"D")
    add_text(m,"中段长度由总长与两端功能长度推导；不重复封闭标注",(35,35))
    add_text(m,"图框：A3装订式；标题栏：教学分栏；个人字段留空",(35,25))
    return doc


def main():
    out=Path(sys.argv[1] if len(sys.argv)>1 else "out")
    out.mkdir(parents=True,exist_ok=True)
    path=out/"engineering_annotations.dxf"
    build().saveas(path)
    doc=ezdxf.readfile(path)
    if doc.audit().has_errors:
        raise AssertionError("DXF structural audit failed")
    report=audit_drawing(doc.modelspace(),chains=CHAINS)
    (out/"inspection.json").write_text(json.dumps({"issues":report,"limitations":["Synthetic annotation demo; not a fully toleranced manufacturing design","Visual review still required for contour/leader collisions"]},ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"parameters.json").write_text(json.dumps(parameters(),ensure_ascii=False,indent=2),encoding="utf-8")
    errors=[i for i in report if i["severity"]=="error"]
    if errors:
        raise AssertionError(json.dumps(errors,ensure_ascii=False,indent=2))
    for ext in ("png","pdf"):
        render(path,out/(path.stem+"."+ext),paper="A3",scale=1,margin=0)


if __name__=="__main__":
    main()
