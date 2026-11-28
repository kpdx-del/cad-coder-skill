from sketch_helpers import new_doc, dim_linear, chamfer_note
from sheet import draw_sheet
from typography import add_text

doc = new_doc(extension_gap=0)
m = doc.modelspace()
draw_sheet(m, title="CASE-A1")
def p(x,y):
    return (142+x,160+y)
def line(a,b,layer="0"):
    m.add_line(p(*a),p(*b),dxfattribs={"layer":layer})
def horizontal(a,b,y):
    return dim_linear(m,p(*a),p(*b),a[1]-y)
def vertical(a,b,x,**opts):
    return dim_linear(m,p(*a),p(*b),a[0]-x,angle=90,**opts)

profile=[(0,-13),(2,-15),(40,-15),(40,-20),(90,-20),(90,-12.5),(125,-12.5),
         (125,12.5),(90,12.5),(90,20),(40,20),(40,15),(2,15),(0,13)]
m.add_lwpolyline([p(*v) for v in profile],close=True)
for x,r in [(2,15),(40,15),(90,12.5)]:
    line((x,-r),(x,r))
line((-5,0),(49,0),"CENTER")
line((61.5,0),(130,0),"CENTER")
def slot(start,length,width):
    radius=width/2
    a,b=start+radius,start+length-radius
    for y in (-radius,radius):
        line((a,y),(b,y))
    m.add_arc(p(a,0),radius,90,270)
    m.add_arc(p(b,0),radius,270,90)
slot(7,24,8)
slot(98,20,6)
for x,r,location,upper,lower in [(2,15,-32,0,-0.021),(60,20,60,0.042,0.026),(125,12.5,154,0,-0.021)]:
    vertical((x,-r),(x,r),location,text="%%c<>",upper=upper,lower=lower)
horizontal((0,-13),(40,-20),-39)
horizontal((90,-20),(125,-12.5),-39)
horizontal((0,-13),(125,-12.5),-53)
for x1,x2,y in [(7,31,38),(98,118,38)]:
    horizontal((x1,0),(x2,0),y)
horizontal((0,13),(7,0),51)
horizontal((0,13),(98,0),65)
for x,r,xd in [(25,4,-13),(112,3,140)]:
    vertical((x,-r),(x,r),xd,arrows="outside",text_location=p(xd-2,-r-6))
chamfer_note(m,p(15,-25),size=2,angle=45,target=p(2,-15),elbow=p(12,-25),chamfer_edge=(p(0,-13),p(2,-15)))
add_text(m,"左槽深 4 mm，右槽深 3 mm", (43,53))
add_text(m,"合成测试数据，非制造图", (43,42))
doc.saveas("drawing.dxf")
