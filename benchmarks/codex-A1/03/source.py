"""CASE-A1, independently constructed from input.md.
Public helpers: cad-coder (alexzeng2014, derivative kpdx-del), MIT.
Run with the supplied public helper and cad-deps directories on PYTHONPATH.
"""
from pathlib import Path
import json, hashlib
import ezdxf
from sketch_helpers import new_doc, dim_linear, chamfer_note, leader, audit_annotations
from typography import add_text, resolve_font
from drawing_checks import assert_ready, audit_drawing
from sheet import draw_sheet
from render_dxf import render_many

OUT=Path(__file__).resolve().parent
INPUT=OUT.parent/'input.md'
assert hashlib.sha256(INPUT.read_bytes()).hexdigest()=='031d0552ecb5242cfaa891bd13ffd166621166b6402dc914904c8da4328c805a'
spec={'mode':'course','part_type':'shaft','units':'mm','references':['input.md / case.txt, synthetic test'],
      'parameters':{k:{'value':v,'source':{'kind':'user','statement':'input.md / case.txt'}} for k,v in {
          'diameters':[30,40,25], 'axial_dimensions':[40,35,125],
          'slots':[[7,24,8,4],[98,20,6,3]], 'deviations':[[0,-.021],[.042,.026],[0,-.021]],
          'left_chamfer':[2,45]}.items()},'required':['slots','deviations','left_chamfer'],'conditions':{}}
assert_ready(spec)
doc=new_doc(extension_gap=1)
m=doc.modelspace()
draw_sheet(m,'A3',title='CASE-A1',scale='1:1')
add_text(m,'合成测试数据，非制造图',(40,75))
add_text(m,'单位',(370,70))
add_text(m,'mm',(382,70))
# Translation on sheet; geometry remains true millimetres.
ox,oy=145,175
def p(x,y): return (ox+x,oy+y)
contour=m.add_lwpolyline([p(x,y) for x,y in [(0,-13),(2,-15),(40,-15),(40,-20),(90,-20),(90,-12.5),(125,-12.5),(125,12.5),(90,12.5),(90,20),(40,20),(40,15),(2,15),(0,13)]],close=True)
# Projected boundary of the full circular chamfer face.
m.add_line(p(2,-15),p(2,15))
m.add_line(p(40,-15),p(40,15))
m.add_line(p(90,-12.5),p(90,12.5))
for a,b in [(-5,17),(25,52),(64,103),(112,130)]:
    m.add_line(p(a,0),p(b,0),dxfattribs={'layer':'CENTER'})

def slot(x,l,w):
    r=w/2
    m.add_line(p(x+r,r),p(x+l-r,r))
    m.add_line(p(x+r,-r),p(x+l-r,-r))
    m.add_arc(p(x+r,0),r,90,270)
    m.add_arc(p(x+l-r,0),r,270,90)
slot(7,24,8)
slot(98,20,6)
# Axial dimensions: only the three independent overall/segment dimensions.
dim_linear(m,p(0,-13),p(40,-20),37,witness_geometry=contour)
dim_linear(m,p(90,-20),p(125,-12.5),30,witness_geometry=contour)
dim_linear(m,p(0,-13),p(125,-12.5),52,witness_geometry=contour)
# Diameters; projected generators establish the size.
dim_linear(m,p(10,-15),p(10,15),65,angle=90,text='%%c<>',upper=0,lower=-.021,witness_geometry=contour)
dim_linear(m,p(65,-20),p(65,20),0,angle=90,text='%%c<>',upper=.042,lower=.026,witness_geometry=contour)
dim_linear(m,p(120,-12.5),p(120,12.5),-25,angle=90,text='%%c<>',upper=0,lower=-.021,witness_geometry=contour)
# Slot lengths and positions measured to the extremities of the rounded ends.
dim_linear(m,p(7,0),p(31,0),-34)
dim_linear(m,p(98,0),p(118,0),-34)
dim_linear(m,p(0,13),p(7,0),-37,arrows='outside',text_location=p(-5,53))
dim_linear(m,p(0,13),p(98,0),-52)
# Width dimensions: arrows outside the narrow spacing; centreline interruptions
# above deliberately keep all dimension glyphs clear of the axis.
dim_linear(m,p(24,-4),p(24,4),0,angle=90,arrows='outside')
dim_linear(m,p(111,-3),p(111,3),0,angle=90,arrows='outside')
leader(m,p(13,-4),p(11,-38),'槽深',elbow=p(5,-38))
add_text(m,'4',p(23,-37.2))
leader(m,p(103,-3),p(104,-38),'槽深',elbow=p(98,-38))
add_text(m,'3',p(116,-37.2))
chamfer_note(m,p(-45,-14),size=2,angle=45,target=p(0,13),elbow=p(-27,-14),chamfer_edge=(p(2,15),p(0,13)))
doc.saveas(OUT/'drawing.dxf')
reopened=ezdxf.readfile(OUT/'drawing.dxf')
required={d.dxf.handle:(1,2) for d in reopened.modelspace().query('DIMENSION')}
report={'input_sha256':hashlib.sha256(INPUT.read_bytes()).hexdigest(),
        'fonts':{'CAD_TEXT':str(resolve_font('isocp___.ttf')),'CAD_CJK':str(resolve_font('simfang.ttf'))},
        'arrows':audit_annotations(reopened.modelspace(),required_arrows=required),
        'audit':[str(x) for x in audit_drawing(reopened.modelspace())],
        'entity_counts':{t:len(reopened.modelspace().query(t)) for t in ['DIMENSION','ARC','LINE','LWPOLYLINE']}}
(OUT/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
render_many(OUT/'drawing.dxf',[OUT/'drawing.pdf',OUT/'preview.png'],paper='A3',scale=1,margin=0,dpi=200,doc=reopened)
print(json.dumps(report,ensure_ascii=False,indent=2))



