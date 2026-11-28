"""CASE-A1. Run with the common CAD helper scripts and ezdxf on PYTHONPATH."""
from pathlib import Path
import ezdxf
from drawing_checks import assert_ready
from render_dxf import EngineeringBackend, _make_context, plt
from ezdxf.addons.drawing import Frontend
from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy, ColorPolicy, TextPolicy
from sheet import draw_sheet
from sketch_helpers import new_doc, dim_linear, chamfer_note, audit_annotations
from typography import add_text, text_width

OUT = Path(__file__).resolve().parent
values = dict(diameters=[30, 40, 25], axial_dimensions=[40, 35, 125],
              keyway_width=[8, 6], keyway_depth=[4, 3], keyway_length=[24, 20],
              keyway_x=[7, 98], chamfer=[2, 45],
              deviations=[(0, -.021), (.042, .026), (0, -.021)])
spec = dict(part_type="shaft", mode="course", units="mm", references=["CASE-A1题面"],
            conditions={"keyway": True}, required=list(values),
            parameters={k: {"value": v, "source": {"kind": "user", "statement": "CASE-A1题面"}}
                        for k, v in values.items()})
assert_ready(spec)
doc = new_doc(extension_gap=.7)
m = doc.modelspace()
draw_sheet(m, title="CASE-A1")
# Keep the shaft origin exactly at the left end, with the axis on world X.
for e in list(m):
    e.translate(-149, -159, 0)
add_text(m, "合成测试数据，非制造图", (-113,-103), 4.2)
for label, val, y in [("左键槽深", 4, -116), ("右键槽深", 3, -125), ("单位", "mm", -134)]:
    add_text(m, label, (-113,y))
    dx = text_width(label, "simfang.ttf", 3.5)
    add_text(m, str(val), (-111+dx,y))

d1, d2, d3 = values["diameters"]
left, right, total = values["axial_dimensions"]
a, b, c = (d/2 for d in (d1,d2,d3))
x1, x2 = left, total-right
k, _ = values["chamfer"]
outline = [(0,a-k),(k,a),(x1,a),(x1,b),(x2,b),(x2,c),(total,c),
           (total,-c),(x2,-c),(x2,-b),(x1,-b),(x1,-a),(k,-a),(0,-a+k)]
boundary = m.add_lwpolyline(outline,close=True)
for x,r in [(k,a),(x1,a),(x2,c)]:
    m.add_line((x,-r),(x,r))
for x,length,width in zip(values["keyway_x"],values["keyway_length"],values["keyway_width"]):
    r = width/2
    l, u = x+r, x+length-r
    m.add_line((l,r),(u,r))
    m.add_line((l,-r),(u,-r))
    m.add_arc((l,0),r,90,270)
    m.add_arc((u,0),r,270,90)

# Preserve a small opening around the central diameter lettering.
for u,v in [(-6,60),(71,131)]:
    m.add_line((u,0),(v,0),dxfattribs={"layer":"CENTER","ltscale":1.3})
def horizontal(p,q,y,**kw):
    return dim_linear(m,p,q,p[1]-y,**kw)

def vertical(p,q,x,**kw):
    return dim_linear(m,p,q,p[0]-x,angle=90,**kw)

for (x,r,dx), (hi,lo) in zip([(k,a,-22),(70,b,70),(total,c,149)], values["deviations"]):
    vertical((x,-r),(x,r),dx,text="%%c<>",upper=hi,lower=lo,witness_geometry=boundary)
for start,length,width,dim_x in zip(values["keyway_x"],values["keyway_length"],values["keyway_width"],[19,108]):
    horizontal((start,0),(start+length,0),30)
    vertical((dim_x,-width/2),(dim_x,width/2),dim_x,
             text_location=(dim_x-2,8.9),arrows="outside")
horizontal((0,a-k),(7,0),44,arrows="inside")
horizontal((0,a-k),(98,0),59)
horizontal((0,-a+k),(x1,-b),-42,witness_geometry=boundary)
horizontal((x2,-b),(total,-c),-42,witness_geometry=boundary)
horizontal((0,-a+k),(total,-c),-56,witness_geometry=boundary)
chamfer_note(m,(17,-27),chamfer_edge=((0,-a+k),(k,-a)),elbow=(14,-27))
path=OUT/"drawing.dxf"
doc.set_modelspace_vport(height=305,center=(61,-10.5))
doc.saveas(path)
saved=ezdxf.readfile(path)
assert not saved.audit().has_errors
dims=saved.modelspace().query("DIMENSION")
assert len(dims)==12
issues=audit_annotations(saved.modelspace(), required_arrows={e.dxf.handle:(1,2) for e in dims})
print("Annotation audit:",issues)
assert not issues
# Matplotlib uses points, while DXF records the pen width in millimetres.
class PhysicalPens(EngineeringBackend):
    def get_lineweight(self, properties):
        return properties.lineweight * 72 / 25.4

fig=plt.figure(figsize=(420/25.4,297/25.4))
ax=fig.add_axes([0,0,1,1])
ax.set(xlim=(-149,271),ylim=(-159,138),aspect="equal")
ax.set_axis_off()
backend=PhysicalPens(ax,adjust_figure=False)
cfg=Configuration().with_changes(background_policy=BackgroundPolicy.WHITE,
                                 color_policy=ColorPolicy.BLACK,text_policy=TextPolicy.FILLING)
Frontend(_make_context(saved,None),backend,config=cfg).draw_layout(saved.modelspace(),finalize=False)
for target in ["drawing.pdf","preview.png"]:
    fig.savefig(OUT/target,dpi=180,facecolor="white")
plt.close(fig)


