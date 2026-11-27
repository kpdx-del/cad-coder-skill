"""A3/A4 landscape bound sheet; teaching title block (explicit profile)."""
from typography import add_text
from drawing_layout import register_group, new_entities


def draw_sheet(msp, paper="A3", *, title="", code="", material="", scale="1:1"):
    # GB/T 14689-2008 bound A3/A4: a=25, c=5; GB/T 10609.1-2008
    # overall title block 180x56, teaching subdivision rather than every
    # revision/sign-off cell of the production example. See sources.md.
    w, h = {"A3": (420, 297), "A4": (297, 210)}[paper]
    outer=msp.add_lwpolyline([(0,0),(w,0),(w,h),(0,h)], close=True, dxfattribs={"layer":"THIN"})
    inner=msp.add_lwpolyline([(25,5),(w-5,5),(w-5,h-5),(25,h-5)], close=True)
    register_group(outer,[outer,inner],"sheet")
    previous={e.dxf.handle for e in msp}
    x, y = w-185, 5
    border=msp.add_lwpolyline([(x,y),(x+180,y),(x+180,y+56),(x,y+56)], close=True)
    def line(a,b):
        msp.add_line(a,b,dxfattribs={"layer":"THIN"})
    for dy in (14,28,42):
        line((x,y+dy),(x+180,y+dy))
    for dx in (25,90,115):
        line((x+dx,y),(x+dx,y+28))
    for label, point in (("设计",(x+3,y+18)),("审核",(x+3,y+4)),
                         ("日期",(x+93,y+18)),("比例",(x+93,y+4))):
        add_text(msp,label,point)
    if scale:
        add_text(msp,scale,(x+119,y+4))
    for value, point in ((title,(x+4,y+46)),(code,(x+4,y+32)),
                         ("材料 "+material if material else "材料",(x+94,y+32))):
        if value:
            add_text(msp,value,point)
    # Signatures, dates, material etc are blank unless explicitly supplied.
    register_group(border,new_entities(msp,previous),"title_block")
    return (25,5,w-5,h-5)
