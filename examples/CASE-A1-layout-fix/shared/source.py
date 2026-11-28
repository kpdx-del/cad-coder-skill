"""All groups use this same geometry interpreter. Run with the group as cwd."""
import json
from pathlib import Path
from sketch_helpers import new_doc,dim_linear,leader
from sheet import draw_sheet
from typography import add_text
seg,c,slots,diams,hd,wd,call,deep=json.loads(Path("spec.json").read_text(encoding="utf-8-sig"))
doc=new_doc(extension_gap=0)
m=doc.modelspace()
draw_sheet(m,title="CASE-A1")
def p(x,y): return 142+x,160+y
def line(a,b,layer="0"):
    m.add_line(p(*a),p(*b),dxfattribs={"layer":layer})
first=seg[0][0]; last=seg[-1][1]
top=[]
for i,(a,b,d) in enumerate(seg):
    r=d/2
    if i==0:
        top.extend([(a,r-c),(a+c,r)])
        if c: line((a+c,-r),(a+c,r))
    else:
        top.append((a,r))
        sr=min(r,seg[i-1][2]/2)
        line((a,-sr),(a,sr))
    top.append((b,r))
m.add_lwpolyline([p(x,y) for x,y in top]+[p(x,-y) for x,y in reversed(top)],close=True)
line((first-5,0),(54,0),"CENTER")
line((66.5,0),(last+5,0),"CENTER")
for a,length,width,depth in slots:
    r=width/2; left=a+r; right=a+length-r
    for y in (-r,r): line((left,y),(right,y))
    m.add_arc(p(left,0),r,90,270);m.add_arc(p(right,0),r,270,90)
for x,d,xd,up,lo in diams:
    dim_linear(m,p(x,-d/2),p(x,d/2),x-xd,angle=90,text="%%c<>",upper=up,lower=lo)
for x1,y1,x2,y2,yd in hd:
    dim_linear(m,p(x1,y1),p(x2,y2),y1-yd)
for x,w,xd in wd:
    dim_linear(m,p(x,-w/2),p(x,w/2),x-xd,angle=90,arrows="outside",text_location=p(xd-2,-w/2-6))
tx,ty,ex,ey,lx=call
leader(m,p(tx,ty),p(lx,ey),f"{c:g}×45°",elbow=p(ex,ey))
if isinstance(deep[0],list):
    for slot,label,point in zip(slots,("左槽深","右槽深"),deep,strict=True):
        add_text(m,f"{label} {slot[3]:g} mm",p(*point))
else:
    add_text(m,f"左槽深 {slots[0][3]:g} mm，右槽深 {slots[1][3]:g} mm",p(*deep))
add_text(m,"合成测试数据，非制造图",(43,42))
doc.saveas("drawing.dxf")
