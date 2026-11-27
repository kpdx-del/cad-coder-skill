"""Editable vector reconstructions of the two user-supplied textbook images.

No source bitmap is inserted in either DXF. Assembly coordinates and unspecified
detail geometry are schematic. Copied technical labels are not new design data.
Requires Python 3.10+, ezdxf 1.4.5, matplotlib and fonttools; ISOCP/FangSong installed.
cad_support derives from kpdx-del/cad-coder-skill (MIT; license included).
"""
from pathlib import Path
import json
import math
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/'cad_support'))
import ezdxf
from ezdxf.enums import TextEntityAlignment as TA
from ezdxf.math import Vec2
from sketch_helpers import new_doc, dim_linear, datum_symbol, chamfer_note, audit_annotations, _draw_fcf_symbol
from typography import add_text, text_width, text_rect
from drawing_checks import mark_annotation, annotation_data
from drawing_layout import register_group, new_entities, _segment_hits_rect, _segments
from render_dxf import render


def text(m, value, xy, h=3.5, rotation=0, center=False):
    t=add_text(m,value,xy,h,rotation=rotation)
    if center:
        t.set_placement(xy,align=TA.MIDDLE_CENTER)
    return t


def poly(m, points, layer='0', close=False):
    return m.add_lwpolyline(points,close=close,dxfattribs={'layer':layer})


def frame(m, x, y, kind, value, datum=None, h=3.5):
    H=8
    w=max(15,text_width(value,m.doc.styles.get('CAD_TEXT').dxf.font,h)+3)
    dw=max(8,text_width(datum,m.doc.styles.get('CAD_TEXT').dxf.font,h)+3) if datum else 0
    right=x+8+w+dw
    poly(m,[(x,y),(right,y),(right,y+H),(x,y+H)],'DIM',True)
    m.add_line((x+8,y),(x+8,y+H),dxfattribs={'layer':'DIM'})
    if datum:
        m.add_line((x+8+w,y),(x+8+w,y+H),dxfattribs={'layer':'DIM'})
        text(m,datum,(x+8+w+dw/2,y+H/2),h,center=True)
    if kind=='total_runout':
        for dx in (-1,1):
            _draw_fcf_symbol(m,'circular_runout',x+4+dx,y+H/2,h)
    else:
        _draw_fcf_symbol(m,kind,x+4,y+H/2,h)
    text(m,value,(x+8+w/2,y+H/2),h,center=True)
    return x,y,right,y+H


def pointer(m, points):
    return m.add_leader(points,dimstyle='CAD_MM',override={'dimldrblk':'','dimasz':2.3},
                        dxfattribs={'layer':'DIM','has_arrowhead':1})


def hatch_polygon(m, points, angle=45, layer='HATCH'):
    poly(m,points,close=True)
    h=m.add_hatch(dxfattribs={'layer':layer})
    h.set_pattern_fill('ANSI31',scale=.7,angle=angle-45)
    h.paths.add_polyline_path(points,is_closed=True)


def legacy_roughness(m, xy, value, rotation=0):
    """Reproduce the source's bare-number legacy surface-texture notation."""
    r=math.radians(rotation)
    def p(x,y):
        return xy[0]+x*math.cos(r)-y*math.sin(r),xy[1]+x*math.sin(r)+y*math.cos(r)
    before={e.dxf.handle for e in m}
    anchor=poly(m,[p(-2.5,4),p(0,0),p(5,8)],'DIM')
    m.add_line(p(-2.5,4),p(2.5,4),dxfattribs={'layer':'DIM'})
    label=text(m,value,(0,5.4),3.2)
    box=text_rect(label)
    # The long sloping leg must clear the complete numeral glyphs as well.
    label_x=min(-2,box[1]*5/8-1.4-box[2])
    label.dxf.insert=p(label_x,5.4)
    label.dxf.rotation=rotation
    register_group(anchor,new_entities(m,before),'replica_roughness',tip=xy,value=value)
    return anchor


def slot(m, x, y, length, width):
    r=width/2
    lines=[m.add_line((x+r,y+r),(x+length-r,y+r)),
           m.add_line((x+r,y-r),(x+length-r,y-r))]
    m.add_arc((x+r,y),r,90,270)
    m.add_arc((x+length-r,y),r,270,90)
    return lines


def avoid_text_on_horizontal_lines(m, lines):
    """Intentional clearances on horizontal/vertical axes, not arrow blocks."""
    rectangles=[]
    for dim in m.query('DIMENSION'):
        rectangles.extend(text_rect(t) for t in m.doc.blocks.get(dim.dxf.geometry).query('MTEXT'))
    for line in lines:
        vertical=abs(line.dxf.start.x-line.dxf.end.x)<1e-8
        x0,x1=sorted([line.dxf.start.y,line.dxf.end.y] if vertical else [line.dxf.start.x,line.dxf.end.x])
        y=line.dxf.start.x if vertical else line.dxf.start.y
        spans=[(x0,x1)]
        for left,bottom,right,top in rectangles:
            if vertical: left,bottom,right,top=bottom,left,top,right
            if bottom-.45<=y<=top+.45:
                cuts=[]
                for a,b in spans:
                    if right+.45<=a or left-.45>=b: cuts.append((a,b))
                    else:
                        if a<left-.45: cuts.append((a,left-.45))
                        if b>right+.45: cuts.append((right+.45,b))
                spans=cuts
        layer=line.dxf.layer
        m.delete_entity(line)
        for a,b in spans:
            if b-a>.1: m.add_line((y,a) if vertical else (a,y),(y,b) if vertical else (b,y),dxfattribs={'layer':layer})


def dimension(m, p1, p2, offset, angle=0, label=None, upper=None, lower=None, dec=3, suppress=None):
    d=dim_linear(m,p1,p2,offset,angle=angle,text=label,upper=upper,lower=lower,
                 arrows='auto',
                 suppress_arrow=suppress)
    if upper is not None and dec!=3:
        d.set_tolerance(upper=upper,lower=-lower,hfactor=2.5/3.5,dec=dec)
        d.render()
    # Measure the saved, rotated MTEXT including the complete deviation stack.
    u=Vec2.from_deg_angle(angle)
    ends=sorted([Vec2(p1).dot(u),Vec2(p2).dot(u)])
    boxes=[text_rect(t) for t in m.doc.blocks.get(d.dimension.dxf.geometry).query('MTEXT')]
    projections=[Vec2(x,y).dot(u) for box in boxes for x in (box[0],box[2]) for y in (box[1],box[3])]
    if projections:
        arrow=m.doc.dimstyles.get('CAD_MM').dxf.dimasz
        if min(projections)<ends[0]+arrow+1 or max(projections)>ends[1]-arrow-1:
            # Horizontal: right; vertical: below. Do not split or shrink the group.
            delta=ends[1]+3-min(projections) if abs(u.x)>.5 else ends[0]-3-max(projections)
            d.set_location(Vec2(d.dimension.dxf.text_midpoint)+u*delta,leader=False,relative=False)
            info=annotation_data(d.dimension)
            info.pop('kind')
            mark_annotation(d.dimension,'dimension',**dict(info,arrows='outside',full_group_outside=True))
            d.render()
    return d


def roughness_on_clear_surface(m, candidates, y, value):
    """Place the whole symbol between actual dimension/cutting strokes."""
    obstacles=[]
    for e in m:
        if e.dxftype()=='DIMENSION':
            obstacles.extend(m.doc.blocks.get(e.dxf.geometry))
        elif e.dxftype()=='LEADER':
            obstacles.append(e)
    for x in candidates:
        before={e.dxf.handle for e in m}
        anchor=legacy_roughness(m,(x,y),value)
        from drawing_layout import group_bounds
        rect=group_bounds(anchor)
        blocked=any(_segment_hits_rect(a,b,rect,.8) for e in obstacles for a,b in _segments(e))
        blocked=blocked or any(_segment_hits_rect((r[0],r[1]),(r[2],r[3]),rect,.8)
                               for e in obstacles if e.dxftype()=='MTEXT' for r in [text_rect(e)])
        if not blocked:
            return anchor
        for e in new_entities(m,before): m.delete_entity(e)
    raise ValueError('No space for surface texture symbol; reflow the drawing')


def section(m, cx, cy, radius, width, floor_x, residual, prefix=False):
    """Side-open keyway section, retaining source labels and its limitations."""
    half=width/2
    side=math.sqrt(radius**2-half**2)
    a=math.degrees(math.asin(half/radius))
    m.add_arc((cx,cy),radius,a,360-a)
    path=[(cx+side,cy-half),(cx+floor_x,cy-half),(cx+floor_x,cy+half),(cx+side,cy+half)]
    poly(m,path)
    h=m.add_hatch(dxfattribs={'layer':'HATCH'})
    h.set_pattern_fill('ANSI31',scale=.7)
    boundary=h.paths.add_edge_path()
    boundary.add_arc((cx,cy),radius,a,360-a)
    for p,q in zip(path,path[1:]): boundary.add_line(p,q)
    m.add_line((cx-radius-5,cy),(cx+radius+5,cy),dxfattribs={'layer':'CENTER'})
    m.add_line((cx,cy-radius-5),(cx,cy+radius+5),dxfattribs={'layer':'CENTER'})
    # Residual size is explicitly supplied by the source, not estimated.
    d=dimension(m,(cx-radius,cy),(cx+floor_x,cy),radius+14,upper=0,lower=-.180)
    assert abs(d.dimension.get_measurement()-residual)<1e-7
    sx=cx+radius+15
    d=dimension(m,(cx+floor_x,cy-half),(cx+floor_x,cy+half),cx+floor_x-sx,
                angle=90,label='%%c<>' if prefix else None,upper=0,lower=-.040 if prefix else -.036)
    f=frame(m,sx+10,cy-half-34,'symmetry','0.020','D')
    # The size arrow inside the interval points down; the FCF extension
    # below approaches upwards. Keep a separate opposed pointer here.
    pointer(m,[(sx,cy-half),(sx,cy-half-30),(f[0],cy-half-30)])
    m.add_line((cx+floor_x,cy+half),(cx+radius+14,cy+half),dxfattribs={'layer':'DIM'})
    poly(m,[(cx+radius+4,cy+half),(cx+radius+7,cy+half+5),(cx+radius+20,cy+half+5)],'DIM')
    legacy_roughness(m,(cx+radius+12,cy+half+5),'6.3')
    return {'radius_is_schematic':not prefix,'width_as_printed':('φ' if prefix else '')+str(width),
            'residual_as_printed':residual}


def shaft_drawing():
    d=new_doc(extension_gap=0)
    m=d.modelspace()
    d.dimstyles.get('CAD_MM').dxf.dimexe=3
    text(m,'图2-2  一级齿轮减速器低速输出轴——原图示意复刻',(20,282),5)
    text(m,'保留原图标注；局部矛盾未擅改，详见复刻说明。非完整制造图。',(20,271),3.5)
    x0,cy=48,190
    xs=[0,60,101,146,192,214,235]
    radii=[19,24,25,27.5,29.5,25]
    top=[(x0,cy+17),(x0+2,cy+19),(x0+60,cy+19)]
    for i in range(1,6):
        top.extend([(x0+xs[i],cy+radii[i]),(x0+xs[i+1],cy+radii[i])])
    bottom=[(x,2*cy-y) for x,y in reversed(top)]
    poly(m,top+bottom,close=True)
    axis=m.add_line((x0-6,cy),(x0+241,cy),dxfattribs={'layer':'CENTER'})
    slot(m,x0+10,cy,40,10)
    gear_slot=slot(m,x0+151,cy,36,14)
    # Drawing dimensions: middle 41 = total minus the other five lengths,
    # intentionally not added as a redundant independent dimension.
    for a,b,y in [(0,235,260),(0,60,249),(101,146,249),(146,192,249),(192,214,249),(214,235,249),
                  (0,50,238),(151,187,238),(187,192,238)]:
        def ordinate(x):
            if x==0: return cy+17
            if x in (50,151,187): return cy
            i=xs.index(x)
            return cy+max(radii[max(0,i-1):min(6,i+1)])
        dimension(m,(x0+a,ordinate(a)),(x0+b,ordinate(b)),ordinate(a)-y)
    left=dimension(m,(x0+10,cy-19),(x0+10,cy+19),0,angle=90,label='%%c<>',upper=.048,lower=.009)
    dimension(m,(x0+76,cy-24),(x0+76,cy+24),0,angle=90,label='%%c<>')
    seat=dimension(m,(x0+109,cy-25),(x0+109,cy+25),0,angle=90,label='%%c<>',upper=.018,lower=.002)
    dimension(m,(x0+123,cy-25),(x0+123,cy+25),0,angle=90,label='%%c<>',upper=.018,lower=.002)
    dimension(m,(x0+168,cy-27.5),(x0+168,cy+27.5),0,angle=90,label='%%c<>',upper=.060,lower=.041)
    dimension(m,(x0+202,cy-29.5),(x0+202,cy+29.5),0,angle=90,label='%%c<>')
    tail=dimension(m,(x0+235,cy-25),(x0+235,cy+25),-10,angle=90,label='%%c<>',upper=.018,lower=.002,dec=4)
    for dx,yy,letter in [(10,cy-19,'D'),(109,cy-25,'B'),(245,cy-25,'A')]:
        datum_symbol(m,(x0+dx,yy),letter,side='below',filled=True)
    # Full circumferential chamfer appears on both silhouettes.
    chamfer_note(m,(x0+24,cy+36),size=2,target=(x0+2,cy+19),elbow=(x0+19,cy+36),
                 chamfer_edge=((x0,cy+17),(x0+2,cy+19)))
    # Preserve unlabeled cutting arrows from the supplied figure, rather
    # than inventing C-C/D-D labels absent from this image.
    for dx,radius in ((38,19),(170,27.5)):
        for sign in (-1,1):
            y=cy+sign*(radius+10)
            arrow=pointer(m,[(x0+dx+3,y),(x0+dx,y),(x0+dx,y-sign*5)])
            mark_annotation(arrow,'replica_cut',axis_y=cy,radius=radius,sign=sign,cut_x=x0+dx)
    for dx,r,val in [(30,19,'1.6'),(83,24,'1.6'),(116,25,'1.6'),(224,25,'1.6')]:
        legacy_roughness(m,(x0+dx,cy+r),val)
    roughness_on_clear_surface(m,[x0+dx for dx in (178,174,182,160)],cy+27.5,'3.2')
    # Each shoulder symbol is on the extension of its own end-face contour.
    for dx,tip_y,rotation,end_y in [(192,cy-38,90,cy-43),(214,cy-42,-90,114)]:
        line=m.add_line((x0+dx,cy-29.5),(x0+dx,end_y),dxfattribs={'layer':'DIM'})
        symbol=legacy_roughness(m,(x0+dx,tip_y),'3.2',rotation)
        mark_annotation(symbol,'replica_shoulder_texture',controlled_face_x=x0+dx,
                        face_endpoint=[x0+dx,cy-29.5],tip=[x0+dx,tip_y],extension=line.dxf.handle)
    f=frame(m,x0+129,137,'cylindricity','0.005')
    frame(m,x0+129,129,'total_runout','0.015','A-B')
    # Separate the two opposed arrows at the lower diameter witness.
    pointer(m,[(x0+123,cy-25),(x0+123,137),(f[0],137)])
    f2=frame(m,x0+247,120,'circular_runout','0.025','A')
    pointer(m,[(x0+214,124),(f2[0],124)])
    sections=[section(m,x0+38,85,24,10,17,41),section(m,x0+170,73,27.5,14,23,50.5,True)]
    avoid_text_on_horizontal_lines(m,[axis,*gear_slot])
    text(m,'原图疑点：左断面41与主视图φ38不一致；右键槽宽度前φ按原图保留。',(20,12),3.5)
    return d,{'mode':'source-reconstruction','nominal_axis_lengths':xs,'nominal_diameters':[38,48,50,55,59,50],
              'derived_middle_length':41,'source_conflicts':['left section residual41 exceeds shaft diameter38',
              'right keyway width is printed with a diameter prefix'],
              'schematic_only':['undimensioned keyway start','section positions','left section diameter','unnoted fillets'],
              'sections':sections}


class Assembly:
    def __init__(self):
        self.d=new_doc(extension_gap=0)
        self.m=self.d.modelspace()
        self.d.dimstyles.get('CAD_MM').dxf.dimtxt=3.2
        self.d.dimstyles.get('CAD_MM').dxf.dimasz=1.8
        self.d.dimstyles.get('CAD_MM').dxf.dimexe=1.2
    def p(self,p): return 30+p[0]*.28,5+(981-p[1])*.28
    def line(self,a,b,layer='0'): return self.m.add_line(self.p(a),self.p(b),dxfattribs={'layer':layer})
    def poly(self,pts,close=False,hatched=False,angle=45,layer='0'):
        points=[self.p(p) for p in pts]
        if hatched:
            before={e.dxf.handle for e in self.m}
            hatch_polygon(self.m,points,angle)
            return new_entities(self.m,before)
        return poly(self.m,points,layer,close)
    def rect(self,x0,y0,x1,y1,hatch=False): self.poly([(x0,y0),(x1,y0),(x1,y1),(x0,y1)],True,hatch)
    def circle(self,c,r,layer='0'): self.m.add_circle(self.p(c),r*.28,dxfattribs={'layer':layer})
    def label(self,s,xy,h=3.5): text(self.m,s,self.p(xy),h,center=True)
    def roundrect(self,x0,y0,x1,y1,r):
        self.line((x0+r,y0),(x1-r,y0));self.line((x0+r,y1),(x1-r,y1))
        self.line((x0,y0+r),(x0,y1-r));self.line((x1,y0+r),(x1,y1-r))
        for c,a,b in [((x0+r,y0+r),90,180),((x1-r,y0+r),0,90),((x1-r,y1-r),270,360),((x0+r,y1-r),180,270)]:
            self.m.add_arc(self.p(c),r*.28,a,b)
    def capsule(self,cx,y0,y1,w):
        r=w/2
        self.line((cx-r,y0+r),(cx-r,y1-r));self.line((cx+r,y0+r),(cx+r,y1-r))
        self.m.add_arc(self.p((cx,y0+r)),r*.28,0,180)
        self.m.add_arc(self.p((cx,y1-r)),r*.28,180,360)
    def bolt(self,c,r=13):
        self.circle(c,r);self.circle(c,r*.7)
        self.line((c[0]-r-7,c[1]),(c[0]+r+7,c[1]),'CENTER')
        self.line((c[0],c[1]-r-7),(c[0],c[1]+r+7),'CENTER')
    def bearing(self,cx,y0,y1,inside,outside,reverse=False):
        """Schematic single-row tapered roller, not a model-specific bearing.

        Both raceways and roller generatrices converge on the same axis apex.
        The lower bearing is reversed. Rings hatched; rolling elements unhatched.
        """
        width=outside-inside
        B=y1-y0
        inner_top=inside+.30*width
        outer_top=outside-.10*width
        apex=B*inner_top/(.16*width)
        ki,ko=inner_top/apex,outer_top/apex
        kc=(ki+ko)/2
        def ray(k,z): return k*(apex-z)
        def end(k,t):
            z=(t+kc*k*apex)/(1+kc*k)
            return ray(k,z),z
        for sign in (-1,1):
            def s(r,z): return cx+sign*r,(y1-z if reverse else y0+z)
            outer=[s(outside,0),s(outside,B),s(ray(ko,B),B),s(ray(ko,0),0)]
            # The large-end rib retains the rolling element; not a solid box.
            inner=[s(inside,0),s(inner_top+.07*width,0),s(inner_top+.07*width,.09*B),
                   s(ray(ki,.09*B),.09*B),s(ray(ki,B),B),s(inside,B)]
            for role,points in [('outer_ring',outer),('inner_ring',inner)]:
                entities=self.poly(points,True,True,45 if reverse else 135)
                for e in entities:
                    mark_annotation(e,'replica_bearing',part=role,bearing_type='single_row_tapered_roller',
                                    axis=list(self.p((cx,y0))),apex=list(self.p((cx,y1-apex if reverse else y0+apex))))
            # The two slightly inset contact rays preserve the common apex.
            kr0,kr1=ki+.006,ko-.006
            top_t=.20*B-kc*ray(kc,.20*B)
            bottom_t=.80*B-kc*ray(kc,.80*B)
            roller=self.poly([s(*end(kr0,top_t)),s(*end(kr1,top_t)),
                              s(*end(kr1,bottom_t)),s(*end(kr0,bottom_t))],True)
            mark_annotation(roller,'replica_bearing',part='roller',bearing_type='single_row_tapered_roller',
                            reverse=reverse,apex=list(self.p((cx,y1-apex if reverse else y0+apex))))
    def fit(self,x0,x1,y,label,feature_y=None,feature=None):
        source_y=y if feature_y is None else feature_y
        d=self.m.add_linear_dim(base=self.p(((x0+x1)/2,y)),p1=self.p((x0,source_y)),p2=self.p((x1,source_y)),
                                text=label,dimstyle='CAD_MM',dxfattribs={'layer':'DIM'})
        mark_annotation(d.dimension,'dimension',arrows='inside',text_side='above',blank_ends=[],
                        schematic_only=True,source='原图配合标签；装配几何按图像比例示意',
                        attachment=feature,attachment_points=[list(self.p((x0,source_y))),list(self.p((x1,source_y)))])
        d.render()
    def item(self,n,start,end):
        x,y=start
        self.label(str(n),(x+18,y-11),4)
        self.poly([(x,y),(x+38,y),end],layer='DIM')


def assembly_drawing():
    a=Assembly();m=a.m
    text(m,'装配关系示意复刻：未注位置按图像比例，非制造图',(35,291),3.5)
    a.roundrect(117,206,1062,615,78)
    # Base, raised pads and casing inner lip.
    for x0,x1 in [(247,355),(815,974)]:
        a.rect(x0,187,x1,208);a.rect(x0,614,x1,637)
    # Continuous casing lips; join the bearing-seat boundaries exactly.
    for pts in [[(314,283),(193,283),(193,538),(314,538),(314,532),(312,525),
                 (207,525),(207,297),(312,297),(314,291)],
                [(808,283),(985,283),(985,537),(808,537),(808,532),(808,525),
                 (973,525),(973,296),(808,296),(808,291)]]:
        e=a.poly(pts,True)
        mark_annotation(e,'replica_casing_lip',closed_required=True)
    for pts in [[(314,291),(314,307),(231,307),(217,320),(217,511),(231,525),(314,525),(314,532)],
                [(808,291),(808,307),(943,307),(955,320),(955,511),(943,525),(808,525),(808,532)]]:
        e=a.poly(pts)
        mark_annotation(e,'replica_cavity_boundary',joins_bearing_seat=True)
    # Left bearing caps and right cap bridge; separate material regions.
    upper_left=[(265,176),(365,176),(365,195),(334,195),(334,224),(315,224),(315,202),(265,202)]
    upper_right=[(433,176),(518,176),(518,202),(484,202),(484,224),(466,224),(466,195),(433,195)]
    upper_bridge=[(521,171),(865,171),(865,203),(809,203),(809,253),(790,253),(778,226),
                  (600,226),(586,253),(568,253),(568,203),(521,203)]
    for pts in [upper_left,upper_right]:
        a.poly(pts,True,True)
        a.poly([(x,820-y) for x,y in pts],True,True,135)
    a.poly(upper_bridge,True,True)
    for pts in [[(521,649),(639,649),(639,618),(625,618),(625,594),(600,594),(586,567),(568,567),(568,617),(521,617)],
                [(738,649),(865,649),(865,617),(809,617),(809,567),(790,567),(778,594),(750,594),(750,618),(738,618)]]:
        a.poly(pts,True,True,135)
    # Bearing outer rings and shoulders.
    a.bearing(399,220,291,34,85);a.bearing(399,532,602,34,85,True)
    a.bearing(688,228,291,60,120);a.bearing(688,532,602,55,120,True)
    for x0,x1 in [(315,365),(433,484),(568,628),(748,808)]:
        a.line((x0,291),(x1,291));a.line((x0,532),(x1,532))
    # Shaft profiles: no longitudinal hatching of solid shafts.
    shaft_in=[(372,32),(427,32),(427,118),(433,118),(433,347),(445,347),(445,474),
              (433,474),(433,580),(421,580),(421,588),(377,588),(377,580),(365,580),
              (365,474),(354,474),(354,347),(365,347),(365,118),(372,118)]
    input_contour=a.poly(shaft_in,True)
    mark_annotation(input_contour,'replica_solid_shaft',section='longitudinal',hatch=False)
    shaft_out=[(628,228),(748,228),(748,335),(755,335),(755,355),(748,355),(748,474),
               (743,474),(743,642),(737,642),(737,706),(732,706),(732,831),(726,837),
               (652,837),(646,831),(646,706),(639,706),(639,642),(633,642),(633,474),
               (628,474),(628,355),(619,355),(619,335),(628,335)]
    output_contour=a.poly(shaft_out,True)
    mark_annotation(output_contour,'replica_solid_shaft',section='longitudinal',hatch=False)
    a.capsule(399,32,106,20);a.capsule(688,368,451,25);a.capsule(688,718,836,20)
    axes=[a.line((399,16),(399,665),'CENTER'),a.line((688,145),(688,850),'CENTER')]
    # Input pinion's conventional diagonal tooth lines.
    a.rect(339,347,457,474)
    for dx in [0,8,16]: a.line((365+dx,347),(402+dx,474),'THIN')
    a.line((344,342),(344,479),'THIN');a.line((451,342),(451,479),'THIN')
    # Gear web and its open annular recesses, mirrored about the hub.
    gear=[(457,353),(476,353),(476,382),(483,393),(585,393),(594,383),(594,353),(628,353),
          (628,469),(594,469),(594,439),(585,427),(483,427),(476,438),(476,469),(457,469)]
    for pts,cx in [(gear,534),([(1376-x,y) for x,y in reversed(gear)],842)]:
        entities=a.poly(pts,True,True)
        hatch=next(e for e in entities if e.dxftype()=='HATCH')
        hatch.dxf.hatch_style=0  # normal island detection; exclude the opening
        hatch.paths.add_polyline_path([a.p(p) for p in [(cx-12,395),(cx+12,395),(cx+12,427),(cx-12,427)]],is_closed=True,flags=0)
        mark_annotation(hatch,'replica_gear_section',unhatched_hole_center=list(a.p((cx,411))))
    for x in (455,461,915,921): a.line((x,350),(x,472),'THIN')
    for cx in (534,842):
        a.rect(cx-12,395,cx+12,427)
        a.line((cx,383),(cx,440),'CENTER')
    # Spacers, felt seals, shoulders and shaft-cap bolts.
    for x0,x1,y0,y1 in [(354,365,291,347),(433,445,291,347),(619,628,291,335),(748,756,291,335),
                         (354,365,474,532),(433,445,474,532),(619,633,474,532),(743,756,474,532)]:
        a.rect(x0,y0,x1,y1)
    for x,y in [(360,195),(438,195),(625,636),(751,636)]:
        a.rect(x-6,y-5,x+6,y+5,True)
    for x,y in [(304,165),(459,165),(562,156),(771,156),(304,647),(459,647),(562,650),(771,650)]:
        a.rect(x,y,x+34,y+13)
        a.line((x+10,y),(x+10,y+13),'THIN');a.line((x+24,y),(x+24,y+13),'THIN')
        a.line((x+17,y-9),(x+17,y+20),'CENTER')
    for c in [(285,250),(524,250),(863,250),(156,342),(1021,342),(1021,479),(524,572),(863,572)]:
        a.bolt(c)
    for c in [(156,479),(285,573)]:
        a.bolt(c,22);a.circle(c,29)
        a.poly([(c[0]+27*math.cos(i*math.pi/3),c[1]+27*math.sin(i*math.pi/3)) for i in range(6)],True)
    for c in [(155,282),(1021,573)]: a.bolt(c,6)
    # Source cutaway curve, deliberately represented as an editable spline.
    cutaway=m.add_spline([a.p(p) for p in [(117,410),(170,428),(235,451),(301,477),(348,513),(373,556),(377,588)]])
    mark_annotation(cutaway,'replica_cutaway_boundary',end_on_contour=input_contour.dxf.handle)
    axes.append(a.line((83,411),(1085,411),'CENTER'))
    # Fit annotations copied verbatim. Their carrier geometry is schematic.
    for args in [(315,484,221,'%%c72H7/f9'),(315,484,252,'%%c72H7'),
                 (365,433,277,'%%c30k6'),(628,748,438,'%%c50H7/p6'),(633,743,550,'%%c45k6'),
                 (568,808,586,'%%c100H7'),(568,808,618,'%%c100H7/f9')]:
        a.fit(*args)
    # These witness lines must terminate on the referenced shaft seat, not
    # on arbitrary points five pixels from the dimension line.
    a.fit(365,433,147,'%%c23p6',feature_y=165,feature=input_contour.dxf.handle)
    a.fit(639,737,720,'%%c35p6',feature_y=700,feature=output_contour.dxf.handle)
    avoid_text_on_horizontal_lines(m,axes)
    # Item leader polyline: no extra numbered components or fabricated BOM.
    top_items=[(1,(81,73),(250,202)),(2,(142,73),(279,181)),(3,(204,73),(320,171)),
               (4,(291,70),(398,43)),(5,(433,63),(421,122)),(6,(477,63),(361,196)),
               (7,(538,63),(498,174)),(8,(590,63),(581,164)),(9,(643,63),(600,260)),
               (10,(696,63),(688,267)),(11,(762,63),(688,383)),(12,(817,63),(846,353))]
    for n,start,end in top_items: a.item(n,start,end)
    for n,start,end in [(19,(299,817),(349,632)),(18,(400,817),(344,570)),(17,(484,817),(625,637)),
                         (16,(563,817),(688,753)),(15,(778,817),(772,573)),(14,(892,817),(843,643)),
                         (13,(973,817),(817,631))]:
        x,y=start
        a.label(str(n),(x+20,y-12),4)
        a.poly([(x,y),(x+52,y),(end[0],end[1])],layer='DIM')
    a.label('图 2-1   一级圆柱齿轮减速器',(580,880),5)
    a.label('1、13—调整垫片；2、7、14、19—轴承盖；3、8—螺栓；4、11、16—键；',(580,919),3.8)
    a.label('5—齿轮轴；6、17—毡封油圈；9、15、18—轴承；10—输出轴；12—大齿轮',(580,951),3.8)
    return a.d,{'mode':'schematic-assembly-reconstruction','scale':'NTS: original gives no overall dimensions',
                 'fit_labels_as_printed':['23p6','72H7/f9','72H7','30k6','50H7/p6','45k6','100H7','100H7/f9','35p6'],
                 'item_numbers':list(range(1,20)),
                 'bearing_type':'single-row tapered roller; schematic prescribed-style representation',
                 'bearing_model':None,
                 'limits':['unprovided positions and shapes reconstructed by image proportion',
                           'bearing outlines not model-specific; cage detail omitted',
                           'no tooth counts, bearing models or loads inferred']}


def save_and_check(name, doc, provenance, out_dir=HERE):
    out_dir=Path(out_dir)
    out_dir.mkdir(parents=True,exist_ok=True)
    path=out_dir/(name+'.dxf')
    doc.saveas(path)
    reopened=ezdxf.readfile(path)
    assert not reopened.audit().has_errors
    m=reopened.modelspace()
    dims=list(m.query('DIMENSION'))
    # Independent requirement: every ordinary dimension here retains two heads.
    requirements={dim.dxf.handle:(1,2) for dim in dims}
    issues=audit_annotations(m,required_arrows=requirements)
    if issues: raise ValueError('\n'.join(issues))
    assert not m.query('IMAGE'), 'editable reconstruction must not just embed the source bitmap'
    # Negative check on a separate in-memory copy: a real missing arrow must
    # fail independently of the generating flags. Original output is preserved.
    negative=ezdxf.readfile(path)
    broken=next(iter(negative.modelspace().query('DIMENSION')))
    block=negative.blocks.get(broken.dxf.geometry)
    block.delete_entity(next(iter(block.query('INSERT'))))
    assert audit_annotations(negative.modelspace(),required_arrows={broken.dxf.handle:(1,2)})
    for ext in ('png','pdf'):
        render(path,out_dir/(name+'.'+ext),paper='A3',scale=1,margin=5)
    provenance.update({'dxf_structure':'passed','required_dimension_arrows':'passed',
                       'native_dimension_count':len(dims),'leader_count':len(m.query('LEADER')),
                       'ordinary_dimension_arrow_count':len(dims)*2,'deleted_arrow_negative_check':'passed',
                       'raster_images_in_dxf':0,'not_verified':['specific CAD software editing','complete manufacturing design','all-standard semantic compliance']})
    (out_dir/(name+'_检查与来源.json')).write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    for name,builder in [('01_一级圆柱齿轮减速器_示意复刻',assembly_drawing),('02_低速输出轴_原图复刻',shaft_drawing)]:
        doc,provenance=builder()
        save_and_check(name,doc,provenance)
