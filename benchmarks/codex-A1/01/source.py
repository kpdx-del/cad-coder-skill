# Independent CASE-A1 builder. Shared helpers retain their upstream MIT attribution.
from pathlib import Path
import hashlib, json
import ezdxf
from sketch_helpers import new_doc, dim_linear, chamfer_note, leader, audit_annotations
from typography import add_text, text_width
from sheet import draw_sheet
from drawing_checks import assert_ready, audit_drawing
from render_dxf import render_many

OUT=Path(__file__).resolve().parent
INPUT=OUT.parent/'input.md'
assert hashlib.sha256(INPUT.read_bytes()).hexdigest()=='031d0552ecb5242cfaa891bd13ffd166621166b6402dc914904c8da4328c805a'
def user(value):
    return {'value':value,'source':{'kind':'user','statement':'input.md / case.txt'}}
spec={'mode':'course','part_type':'shaft','units':'mm','references':['input.md case.txt synthetic data'],
      'parameters':{'diameters':user([30,40,25]),'axial_dimensions':user([40,35,125]),
                    'keyway_width':user([8,6]),'keyway_depth':user([4,3]),'keyway_length':user([24,20]),
                    'slots':user([[7,24,8,4],[98,20,6,3]]),'chamfer':user([2,45]),
                    'deviations':user([[0,-.021],[.042,.026],[0,-.021]])},
      'required':['slots','chamfer','deviations'],'conditions':{}}
assert_ready(spec)
doc=new_doc(extension_gap=1)
msp=doc.modelspace()
# Sheet placement preserves shaft coordinates x=0..125, y=0.
draw_sheet(msp,'A3',title='CASE-A1',scale='1:1')
from ezdxf.math import Matrix44
shift=Matrix44.translate(-140,-145,0)
for entity in list(msp): entity.transform(shift)
# Main visible outline, closed; two chamfer slopes and full end-circle projection.
profile=[(0,-13),(2,-15),(40,-15),(40,-20),(90,-20),(90,-12.5),(125,-12.5),
         (125,12.5),(90,12.5),(90,20),(40,20),(40,15),(2,15),(0,13)]
outline=msp.add_lwpolyline(profile,close=True)
msp.add_line((2,-15),(2,15))
msp.add_line((-6,0),(131,0),dxfattribs={'layer':'CENTER'})
# Closed slots: two parallel straight lines, two true semicircles.
for start,length,width,depth in [(7,24,8,4),(98,20,6,3)]:
    r=width/2; a=start+r; b=start+length-r
    msp.add_line((a,r),(b,r)); msp.add_line((a,-r),(b,-r))
    msp.add_arc((a,0),r,90,270); msp.add_arc((b,0),r,270,90)
    for xx in (a,b):
        msp.add_line((xx,-r-2),(xx,r+2),dxfattribs={'layer':'CENTER'})
# Diameters with native signed stacked deviations.
dim_linear(msp,(25,-15),(25,15),65,angle=90,text='%%c<>',upper=0,lower=-.021,witness_geometry=outline)
dim_linear(msp,(65,-20),(65,20),0,angle=90,text='%%c<>',upper=.042,lower=.026,witness_geometry=outline)
dim_linear(msp,(120,-12.5),(120,12.5),-30,angle=90,text='%%c<>',upper=0,lower=-.021,witness_geometry=outline)
# Slot length below; start positions measured from actual left end at y=0.
dim_linear(msp,(7,0),(31,0),34)
dim_linear(msp,(98,0),(118,0),34)
dim_linear(msp,(0,0),(7,0),-44,text_location=(3.5,47),arrows='outside')
dim_linear(msp,(0,0),(98,0),-60)
# Slot width: witness points on straight walls; small span uses external arrows.
dim_linear(msp,(23,-4),(23,4),-14,angle=90,arrows='outside')
dim_linear(msp,(105,-3),(105,3),10,angle=90,arrows='outside')
# Independent axial dimensions only: 40, 35 and 125. Actual left end witness.
dim_linear(msp,(0,-13),(40,-15),39)
dim_linear(msp,(90,-20),(125,-12.5),32)
dim_linear(msp,(0,-13),(125,-12.5),55)
# Chamfer callout follows real upper chamfer extension, one annotation for entire ring.
chamfer_note(msp,(-65,-24),size=2,angle=45,target=(0,13),elbow=(-37,-24),chamfer_edge=((2,15),(0,13)))
# Depth notes do not invent an extra view or hidden geometry.
leader(msp,(18,2),(12,25),'槽深',elbow=(12,19))
add_text(msp,'4',(12+text_width('槽深','simfang.ttf')+1,25.8))
leader(msp,(108,1.5),(113,25),'槽深',elbow=(113,19))
add_text(msp,'3',(113+text_width('槽深','simfang.ttf')+1,25.8))
add_text(msp,'合成测试数据，非制造图',(-105,-103))
add_text(msp,'mm',(-105,124))
# Keep paper/export metadata explicit.
doc.header['$LWDISPLAY']=True
path=OUT/'drawing.dxf'; doc.saveas(path)
reopened=ezdxf.readfile(path); rm=reopened.modelspace()
required={d.dxf.handle:(1,2) for d in rm.query('DIMENSION')}
arrow_issues=audit_annotations(rm,required_arrows=required)
issues=audit_drawing(rm,chains={'shaft_axis':[
    {'start':'left','end':'shoulder1','value':40,'function':'locating'},
    {'start':'shoulder2','end':'right','value':35,'function':'coupling'},
    {'start':'left','end':'right','value':125,'function':'overall'}]})
report={'input_sha256':hashlib.sha256(INPUT.read_bytes()).hexdigest(),'dimensions':len(required),
        'fonts':{s:reopened.styles.get(s).dxf.font for s in ('CAD_TEXT','CAD_CJK')},
        'arrow_and_annotation_issues':arrow_issues,'drawing_issues':issues,
        'dxf_audit_errors':len(reopened.audit().errors)}
(OUT/'check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
render_many(path,[OUT/'preview.png',OUT/'drawing.pdf'],paper='A3',scale=1,margin=0,dpi=160)
print(json.dumps(report,ensure_ascii=False,default=str))


