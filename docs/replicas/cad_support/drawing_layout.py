"""Annotation groups and explicit sheet relationships, stored with the DXF.

This is a small geometric check/placement layer, not an automatic CAD solver.
Attachments remain anchored; a candidate is chosen before drawing its group.
"""
import json
from ezdxf import bbox, disassemble
from ezdxf.math import Vec2

APP = "CAD_LAYOUT"


def layout_data(entity):
    if not entity.has_xdata(APP):
        return {}
    return json.loads("".join(tag.value for tag in entity.get_xdata(APP) if tag.code == 1000))


def register_group(anchor, entities, role, **relationships):
    if APP not in anchor.doc.appids:
        anchor.doc.appids.new(APP)
    data = dict(role=role, members=[e.dxf.handle for e in entities], **relationships)
    raw = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
    anchor.set_xdata(APP, [(1000, raw[i:i+240]) for i in range(0,len(raw),240)])


def new_entities(msp, previous):
    return [e for e in msp if e.dxf.handle not in previous]


def group_bounds(anchor):
    data=layout_data(anchor)
    boxes=[_rect(anchor.doc.entitydb[h]) for h in data["members"]]
    boxes=[b for b in boxes if b]
    return min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)


def overlaps(a, b, gap=0):
    return (min(a[2]+gap,b[2])-max(a[0]-gap,b[0]) > 1e-6 and
            min(a[3]+gap,b[3])-max(a[1]-gap,b[1]) > 1e-6)


def choose_position(candidates, size, occupied, *, clearance=2):
    """First fitting constrained candidate; never move a feature attachment.
    Caller supplies meaningful candidates (e.g. positions along one surface).
    """
    width,height=size
    for x,y in candidates:
        rect=(x,y,x+width,y+height)
        if not any(overlaps(rect,other,clearance) for other in occupied):
            return x,y
    raise ValueError("No annotation position fits; reflow views or enlarge sheet")


def _rect(entity):
    if entity.dxftype() in ("TEXT","MTEXT"):
        from typography import text_rect
        return text_rect(entity)
    box=bbox.extents([entity])
    return (box.extmin.x,box.extmin.y,box.extmax.x,box.extmax.y) if box.has_data else None


def _segment_hits_rect(a, b, rect, clearance=0):
    """Liang-Barsky clipping against the interior of a padded text rectangle."""
    x0,y0,x1,y1=rect
    x0-=clearance; y0-=clearance; x1+=clearance; y1+=clearance
    a,b=Vec2(a),Vec2(b)
    delta=b-a
    low,high=0.0,1.0
    for p,q in ((-delta.x,a.x-x0),(delta.x,x1-a.x),(-delta.y,a.y-y0),(delta.y,y1-a.y)):
        if abs(p)<1e-12:
            if q<=1e-7:
                return False
        elif p<0:
            low=max(low,q/p)
        else:
            high=min(high,q/p)
    return high-low>1e-7 and high>0 and low<1


def _segments(entity):
    kind=entity.dxftype()
    if kind=="LINE":
        return [(entity.dxf.start,entity.dxf.end)]
    if kind=="LEADER":
        return list(zip(entity.vertices,entity.vertices[1:]))
    if kind=="SOLID":
        points=list(entity.wcs_vertices())
        return list(zip(points,points[1:]+points[:1]))
    if kind in ("LWPOLYLINE","POLYLINE","ARC","CIRCLE"):
        from ezdxf.path import make_path
        points=list(make_path(entity).flattening(.05))
        return list(zip(points,points[1:]))
    return []


def _crossing(a,b,c,d):
    a,b,c,d=map(Vec2,(a,b,c,d))
    u,v=b-a,d-c
    denominator=u.det(v)
    if abs(denominator)<1e-9:
        if u.magnitude<1e-9 or abs((c-a).det(u))>1e-6*u.magnitude:
            return False
        direction=u.normalize()
        p,q=sorted(((c-a).dot(direction),(d-a).dot(direction)))
        return min(u.magnitude,q)-max(0,p)>.1
    t=(c-a).det(v)/denominator
    s=(c-a).det(u)/denominator
    return 1e-6<t<1-1e-6 and 1e-6<s<1-1e-6


def audit_layout(msp):
    from drawing_checks import issue, annotation_data
    out=[]
    groups={}
    anchors=[]
    for e in msp:
        data=layout_data(e)
        if data:
            anchors.append((e,data))
            for handle in data["members"]:
                groups[handle]=(e.dxf.handle,data["role"])

    # Sheet reservations include full frames/lines, not just their text.
    for anchor,data in anchors:
        if data["role"] != "title_block":
            continue
        forbidden=_rect(anchor)
        own=set(data["members"])
        for e in msp:
            role=groups.get(e.dxf.handle,(None,None))[1]
            if e.dxf.handle in own or role=="sheet" or e.dxf.layer=="CENTER":
                continue
            r=_rect(e)
            padded=(forbidden[0]-2,forbidden[1]-2,forbidden[2]+2,forbidden[3]+2)
            if r and (overlaps(r,forbidden,gap=2) or any(_segment_hits_rect(a,b,padded) for a,b in _segments(e))):
                out.append(issue("TITLE_BLOCK_INTRUSION","Drawing group intrudes into title-block clearance",entity=e.dxf.handle,location=list(r)))

    texts=[]; segments=[]
    for root in msp:
        group,role=groups.get(root.dxf.handle,(root.dxf.handle,None))
        if role in ("sheet","title_block"):
            continue
        for e in disassemble.recursive_decompose([root]):
            if e.dxftype() in ("TEXT","MTEXT"):
                rect=_rect(e)
                if rect:
                    texts.append((root,e,group,role,rect))
            elif e.dxf.get("layer","") not in ("CENTER","HATCH","HIDDEN"):
                segments.extend((root,group,a,b) for a,b in _segments(e))
    for root,text,group,role,rect in texts:
        for line_root,line_group,a,b in segments:
            # A dimension's own line still must not pass through its text.
            # Frame borders, roughness bars and cutting labels are also checked.
            if _segment_hits_rect(a,b,rect,clearance=.15):
                out.append(issue("TEXT_LINE_COLLISION",f"Line crosses text/clearance: {text.plain_text()}",
                                 entity=root.dxf.handle,location=list(rect),
                                 suggestion=f"Reposition the annotation group; line entity={line_root.dxf.handle}"))
                break

    # Independent cutting/roughness symbols must not share or cross strokes.
    reported=set()
    for index,(ra,ga,a,b) in enumerate(segments):
        role_a=groups.get(ra.dxf.handle,(None,None))[1]
        for rb,gb,c,d in segments[index+1:]:
            role_b=groups.get(rb.dxf.handle,(None,None))[1]
            pair=frozenset((ga,gb))
            if ga==gb or pair in reported:
                continue
            if {role_a,role_b}!={"cutting","roughness"} and not (role_a==role_b=="leader"):
                continue
            if _crossing(a,b,c,d):
                out.append(issue("ANNOTATION_GROUP_CROSSING","Independent annotation groups cross or share a stroke",entity=ra.dxf.handle,
                                 suggestion=f"Reposition group; other entity={rb.dxf.handle}"))
                reported.add(pair)

    # Frame interiors must be free of foreign leaders and dimension lines.
    for anchor,data in anchors:
        if data["role"] != "frame":
            continue
        rect=_rect(anchor)
        inner=(rect[0]+.15,rect[1]+.15,rect[2]-.15,rect[3]-.15)
        for line_root,line_group,a,b in segments:
            if line_group==anchor.dxf.handle:
                continue
            if _segment_hits_rect(a,b,inner):
                out.append(issue("FRAME_LINE_COLLISION","Foreign line crosses geometric-tolerance frame",entity=anchor.dxf.handle,
                                 suggestion=f"Move group; line entity={line_root.dxf.handle}"))
                break

    for anchor,data in anchors:
        if data["role"]=="cutting":
            center=Vec2(data["center"])
            labels=[msp.doc.entitydb[h] for h in data["labels"]]
            points=[Vec2(e.dxf.align_point) for e in labels]
            if abs(points[0].x-points[1].x)>1e-6 or abs((points[0].y+points[1].y)/2-center.y)>1e-6:
                out.append(issue("CUT_LABEL_SYMMETRY","Cutting labels are not mirrored around shaft centre",entity=anchor.dxf.handle))
            marks=[msp.doc.entitydb[h] for h in data["marks"]]
            for attribute in ("start","end"):
                p,q=[Vec2(getattr(mark.dxf,attribute)) for mark in marks]
                if abs(p.x-q.x)>1e-6 or abs((p.y+q.y)/2-center.y)>1e-6:
                    out.append(issue("CUT_MARK_SYMMETRY","Cutting strokes are not mirrored",entity=anchor.dxf.handle))
                    break
        elif data["role"]=="section":
            cut=msp.doc.entitydb[data["cut"]]
            # Source cutting stub and actual section centre line supply positions.
            p=Vec2(cut.dxf.start)
            a,b=Vec2(anchor.dxf.start),Vec2(anchor.dxf.end)
            direction=b-a
            if abs((p-a).det(direction))>1e-6*direction.magnitude:
                out.append(issue("SECTION_COLLINEARITY","Section centre is not on the corresponding cutting line",entity=anchor.dxf.handle))
            label=msp.doc.entitydb[data["label"]]
            if abs(label.dxf.align_point.x-(a.x+b.x)/2)>1e-6:
                out.append(issue("SECTION_CAPTION_CENTER","Section caption is not centred",entity=label.dxf.handle))

    for dim in msp.query("DIMENSION"):
        data=annotation_data(dim)
        source_handle=data.get("witness_geometry")
        if source_handle:
            source=msp.doc.entitydb.get(source_handle)
            if source is None or not source.is_alive:
                out.append(issue("WITNESS_SOURCE_MISSING","Dimension contour reference is missing",entity=dim.dxf.handle))
            elif source.dxftype() not in ("LINE","LWPOLYLINE") or (
                    source.dxftype()=="LWPOLYLINE" and source.has_arc):
                out.append(issue("WITNESS_REVIEW","Review witness connection on this contour type",entity=dim.dxf.handle,severity="review"))
            else:
                segments_on_contour=_segments(source)
                for name in ("defpoint2","defpoint3"):
                    point=Vec2(getattr(dim.dxf,name))
                    distances=[]
                    for a,b in segments_on_contour:
                        a,b=Vec2(a),Vec2(b)
                        vector=b-a
                        length_squared=vector.dot(vector)
                        if length_squared < 1e-12:
                            continue
                        fraction=max(0,min(1,(point-a).dot(vector)/length_squared))
                        distances.append((point-(a+vector*fraction)).magnitude)
                    if not distances or min(distances)>1e-6:
                        out.append(issue("WITNESS_OFF_CONTOUR","Dimension witness starts off the declared real contour",entity=dim.dxf.handle,
                                         location=[point.x,point.y],suggestion="Use an actual contour point after chamfer/fillet; do not keep the removed virtual corner"))
        if data.get("text_side") != "above":
            continue
        angle=dim.dxf.get("angle",0)
        normal=Vec2.from_deg_angle(angle).orthogonal()
        origin=Vec2(dim.dxf.defpoint)
        for text in dim.doc.blocks[dim.dxf.geometry].query("MTEXT TEXT"):
            rect=_rect(text)
            if not rect:
                continue
            distances=[(Vec2(x,y)-origin).dot(normal) for x in (rect[0],rect[2]) for y in (rect[1],rect[3])]
            if min(distances)<.6:
                out.append(issue("DIM_TEXT_SIDE","Dimension text must be above/left of the dimension line",entity=dim.dxf.handle,location=list(rect)))
    return out
