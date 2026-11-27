"""Source-backed, independent corrections while assembly questions are pending.

No bearing model or unnumbered spacer is invented. Coordinates identify the
existing NTS reconstruction, not new manufacturing dimensions. Original DXFs
are preserved. Dependencies remain Python + ezdxf + existing preview libraries.
"""
from pathlib import Path
import sys
import json
import hashlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'cad_support'))
sys.path.insert(0,str(ROOT))
import ezdxf
from ezdxf.entities.boundary_paths import PolylinePath
from ezdxf.math import Vec2,is_point_in_polygon_2d,area
from ezdxf.math.clipping import polygon_line_intersections_2d
from ezdxf import edgeminer,edgesmith
from drawing_checks import annotation_data,mark_annotation
from typography import register_font,text_rect
from sketch_helpers import _DrawingRenderer,audit_annotations
from build_replicas import avoid_text_on_horizontal_lines
from render_dxf import render

SOURCE=ROOT/'revision-02/01_装配图_修订02.dxf'


def p(x,y): return Vec2(30+x*.28,5+(981-y)*.28)


def loop(e):
    return [Vec2(v[:2]) for v in e.paths[0].vertices] if e.dxftype()=='HATCH' else [Vec2(v) for v in e.get_points('xy')]


def equal_loop(a,b):
    return len(a)==len(b) and all(x.isclose(y,abs_tol=1e-7) for x,y in zip(a,b))


def remove_material(m,h):
    ring=loop(h)
    for e in list(m.query('LWPOLYLINE')):
        if e.closed and equal_loop(loop(e),ring): m.delete_entity(e)
    m.delete_entity(h)


def add_face(m,coords,part,*,hatch_angle=135):
    points=[p(*xy) for xy in coords]
    outline=m.add_lwpolyline(points,close=True)
    mark_annotation(outline,'assembly_part',part=part,material_boundary=True)
    h=m.add_hatch(dxfattribs={'layer':'HATCH'})
    h.set_pattern_fill('ANSI31',scale=.7,angle=hatch_angle-45,style=0)
    h.paths.add_polyline_path(points,is_closed=True)
    mark_annotation(h,'assembly_part',part=part,sectioned=True,boundary=outline.dxf.handle)
    return outline,h


def hidden_segments_removed(m,background,occluders):
    """Clip projected background strokes, preserving foreground material loops.

    Reuses ezdxf's polygon/line intersections. A mere coincident contact edge
    is retained: only intervals strictly inside a foreground face are hidden.
    """
    kept=[]
    for line in background:
        a,b=Vec2(line.dxf.start),Vec2(line.dxf.end)
        u=b-a
        cuts=[0.0,1.0]
        for face in occluders:
            cuts.extend((q-a).dot(u)/u.dot(u) for q in polygon_line_intersections_2d(face,(a,b)))
        cuts=sorted({round(max(0,min(1,t)),10) for t in cuts})
        for lo,hi in zip(cuts,cuts[1:]):
            if hi-lo<1e-9: continue
            mid=a+u*((lo+hi)/2)
            if any(is_point_in_polygon_2d(mid,face)>0 for face in occluders): continue
            e=m.add_line(a+u*lo,a+u*hi,dxfattribs={'layer':line.dxf.layer})
            mark_annotation(e,'assembly_background',visibility_clipped=True)
            kept.append(e)
        m.delete_entity(line)
    return kept


def readable_dimension(d):
    e=d.dimension
    data=annotation_data(e)
    data.pop('kind',None)
    mark_annotation(e,'dimension',**dict(data,arrows='auto',text_side='above',blank_ends=[]))
    d.update({'dimasz':2.8,'dimtxt':3.5,'dimblk':'','dimblk1':'','dimblk2':'','dimtxsty':'CAD_TEXT'})
    d.render()
    boxes=[text_rect(t) for t in e.doc.blocks.get(e.dxf.geometry).query('MTEXT')]
    left=min(r[0] for r in boxes);right=max(r[2] for r in boxes)
    low,high=sorted((e.dxf.defpoint2.x,e.dxf.defpoint3.x))
    if left<low+.8 or right>high-.8:
        location=Vec2(e.dxf.text_midpoint)+Vec2(high+3-left,0)
        d.set_location(location,leader=False,relative=False)
        mark_annotation(e,'dimension',**dict(data,arrows='outside',text_side='above',blank_ends=[],full_group_outside=True))
        d.render()
    elif right-left+2*2.8+1.6>high-low:
        # The text still fits between the witnesses; move only the arrow bodies.
        mark_annotation(e,'dimension',**dict(data,arrows='outside',text_side='above',blank_ends=[]))
        d.render()


def revise():
    doc=ezdxf.readfile(SOURCE)
    doc.dimension_renderer=_DrawingRenderer()
    m=doc.modelspace()
    doc.styles.get('CAD_TEXT').dxf.font=register_font('times.ttf')
    doc.styles.get('CAD_CJK').dxf.font=register_font('simfang.ttf')
    doc.dimstyles.get('CAD_MM').dxf.dimasz=2.8
    doc.dimstyles.get('CAD_MM').dxf.dimtxt=3.5
    doc.dimstyles.get('CAD_MM').dxf.dimexe=2
    for e in m.query('TEXT'):
        if e.dxf.height<4.5: e.dxf.height=3.5
        if e.dxf.text.startswith('装配关系示意复刻'):
            e.dxf.text='修订03待确认稿：已修闷盖、尺寸归属和可见性；轴承及薄壁段待答复'

    # Part 19 is a blind cap. Mirroring the through-cap's two halves omitted
    # its central floor. Replace both old halves with one closed material face.
    caps=[]
    for xy in ((280,630),(500,630)):
        matches=[h for h in m.query('HATCH') if isinstance(h.paths[0],PolylinePath) and is_point_in_polygon_2d(p(*xy),loop(h))>0]
        if len(matches)!=1: raise ValueError('Cannot identify cap 19 uniquely')
        caps.append(matches[0])
    for h in caps: remove_material(m,h)
    blind,_=add_face(m,[(265,644),(518,644),(518,618),(484,618),(484,602),(466,602),
                       (466,625),(334,625),(334,602),(315,602),(315,618),(265,618)],19)

    # Integral pinion shaft: use one external material outline, rather than
    # independent sleeve rectangles and a second solid outline inside a gear.
    old=next(e for e in m.query('LWPOLYLINE') if annotation_data(e).get('kind')=='replica_solid_shaft'
             and min(v[0] for v in e.get_points('xy'))<p(399,0).x)
    old_handle=old.dxf.handle
    m.delete_entity(old)
    rects=[(339,347,457,474),(354,291,365,347),(433,291,445,347),
           (354,474,365,532),(433,474,445,532)]
    for x0,y0,x1,y1 in rects:
        target=[p(x0,y0),p(x1,y0),p(x1,y1),p(x0,y1)]
        matches=[e for e in m.query('LWPOLYLINE') if e.closed and equal_loop(loop(e),target)]
        if len(matches)!=1: raise ValueError('Integral shaft sub-outline missing or ambiguous')
        m.delete_entity(matches[0])
    coords=[(372,32),(427,32),(427,118),(433,118),(433,291),(445,291),(445,347),
            (457,347),(457,474),(445,474),(445,532),(433,532),(433,580),(421,580),
            (421,588),(377,588),(377,580),(365,580),(365,532),(354,532),(354,474),
            (339,474),(339,347),(354,347),(354,291),(365,291),(365,118),(372,118)]
    shaft=m.add_lwpolyline([p(*q) for q in coords],close=True)
    mark_annotation(shaft,'replica_solid_shaft',part=5,section='longitudinal',hatch=False)
    for e in m:
        data=annotation_data(e)
        if data.get('end_on_contour')==old_handle:
            data.pop('kind')
            mark_annotation(e,'replica_cutaway_boundary',**dict(data,end_on_contour=shaft.dxf.handle))

    # Shared axial contact plane for shoulder and gear hub (not a tolerance).
    output=next(e for e in m.query('LWPOLYLINE') if annotation_data(e).get('kind')=='replica_solid_shaft'
                and min(v[0] for v in e.get_points('xy'))>p(399,0).x)
    old_y=p(0,355).y
    points=[(v[0],p(0,353).y if abs(v[1]-old_y)<1e-7 else v[1]) for v in output.get_points('xy')]
    output.set_points(points)

    # Fix the item 7 component identity, not merely its leader style.
    leader=next(e for e in m.query('LWPOLYLINE') if e.dxf.layer=='DIM' and len(e)==3
                and Vec2(e.get_points('xy')[0]).isclose(p(538,63),abs_tol=1e-7))
    pts=list(leader.get_points('xy'));pts[-1]=p(540,185)
    leader.set_points(pts)

    # Remove the background housing pads' hidden portion instead of drawing
    # a full rectangle across a foreground hatched cap.
    background=[]
    for x0,x1 in ((247,355),(815,974)):
        for y0,y1 in ((187,208),(614,637)):
            target=[p(x0,y0),p(x1,y0),p(x1,y1),p(x0,y1)]
            e=next(e for e in m.query('LWPOLYLINE') if e.closed and equal_loop(loop(e),target))
            for a,b in zip(target,target[1:]+target[:1]):
                background.append(m.add_line(a,b))
            m.delete_entity(e)
    for e in list(m.query('LINE')):
        if e.dxf.layer=='0' and any(abs(e.dxf.start.y-p(0,y).y)<1e-7 and
                                   abs(e.dxf.end.y-p(0,y).y)<1e-7 and
                                   abs(e.dxf.start.x-p(195,y).x)<1e-7 and
                                   abs(e.dxf.end.x-p(984,y).x)<1e-7 for y in (206,615)):
            background.append(e)
    faces=[loop(h) for h in m.query('HATCH') if isinstance(h.paths[0],PolylinePath)]
    visible=hidden_segments_removed(m,background,faces)

    # Source felt rings use a crossed texture, not the steel ring hatch.
    for h in m.query('HATCH'):
        if not isinstance(h.paths[0],PolylinePath): continue
        points=loop(h)
        if len(points)!=4: continue
        width=max(v.x for v in points)-min(v.x for v in points)
        height=max(v.y for v in points)-min(v.y for v in points)
        if abs(width-12*.28)<1e-7 and abs(height-10*.28)<1e-7 and any(
            is_point_in_polygon_2d(p(x,y),points)>0 for x,y in ((360,195),(438,195),(625,636),(751,636))):
            h.set_pattern_fill('ANSI37',scale=.18,style=0)
            mark_annotation(h,'assembly_part',part='6_or_17',material='felt',sectioned=True,
                            pattern_basis='crossed texture in supplied reference; not a material certification')

    # phi23 belongs to the exposed keyed shaft segment, not the bearing seat.
    old_dim=next(e for e in m.query('DIMENSION') if '23p6' in e.dxf.text)
    m.delete_entity(old_dim)
    d=m.add_linear_dim(base=p(399,20),p1=p(372,75),p2=p(427,75),text='φ23p6',dimstyle='CAD_MM',
                       dxfattribs={'layer':'DIM'})
    mark_annotation(d.dimension,'dimension',arrows='auto',text_side='above',blank_ends=[],
                    schematic_only=True,attachment=shaft.dxf.handle,interface='part5_external_key4_seat')
    for e in m.query('DIMENSION'):
        e.dxf.text=e.dxf.text.replace('%%c','φ')
        readable_dimension(e.override())

    # Rebuild axes before applying font-dependent text clearances. Old-font
    # gaps must not remain after the labels are moved or made wider.
    for e in list(m.query('LINE')):
        if e.dxf.layer!='CENTER': continue
        a,b=Vec2(e.dxf.start),Vec2(e.dxf.end)
        if any(abs(a.x-p(x,0).x)<1e-7 and abs(b.x-p(x,0).x)<1e-7 for x in (399,688)):
            m.delete_entity(e)
        elif abs(a.y-p(0,411).y)<1e-7 and abs(b.y-p(0,411).y)<1e-7:
            m.delete_entity(e)
    axes=[m.add_line(p(399,16),p(399,665),dxfattribs={'layer':'CENTER'}),
          m.add_line(p(688,145),p(688,850),dxfattribs={'layer':'CENTER'}),
          m.add_line(p(83,411),p(1085,411),dxfattribs={'layer':'CENTER'})]
    avoid_text_on_horizontal_lines(m,axes)
    return doc,blind.dxf.handle,len(visible)


def checks(doc,blind_handle):
    m=doc.modelspace()
    cap=doc.entitydb[blind_handle]
    assert cap.closed and is_point_in_polygon_2d(p(399,635),loop(cap))>0
    assert is_point_in_polygon_2d(p(399,610),loop(cap))<0,'preserve the clearance pocket'
    # Use existing ezdxf linked-edge machinery, independently of close=True.
    edges=list(edgesmith.edges_from_entities_2d(cap.virtual_entities()))
    found=edgeminer.find_all_loops(edgeminer.Deposit(edges),timeout=2)
    assert len(found)==1 and abs(abs(edgesmith.loop_area(found[0]))-area(loop(cap)))<1e-6
    requirements={e.dxf.handle:(1,2) for e in m.query('DIMENSION')}
    issues=audit_annotations(m,required_arrows=requirements)
    assert not issues,issues
    for e in m.query('DIMENSION'):
        d=e.override()
        assert abs(d.get('dimasz')-2.8)<1e-7
        assert abs(d.get('dimtxt')-3.5)<1e-7
    small=next(e for e in m.query('DIMENSION') if '23p6' in e.dxf.text)
    assert Vec2(small.dxf.defpoint2).isclose(p(372,75),abs_tol=1e-7)
    assert Vec2(small.dxf.defpoint3).isclose(p(427,75),abs_tol=1e-7)
    faces=[loop(h) for h in m.query('HATCH') if isinstance(h.paths[0],PolylinePath)]
    for e in m:
        if annotation_data(e).get('kind')=='assembly_background':
            midpoint=(Vec2(e.dxf.start)+Vec2(e.dxf.end))/2
            assert not any(is_point_in_polygon_2d(midpoint,f)>0 for f in faces)


if __name__=='__main__':
    before=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    doc,blind,visible=revise()
    path=HERE/'装配图_修订03_待确认.dxf'
    doc.saveas(path)
    reopened=ezdxf.readfile(path)
    assert not reopened.audit().has_errors
    checks(reopened,blind)
    for ext in ('png','pdf'): render(path,path.with_suffix('.'+ext),paper='A3',scale=1,margin=5)
    assert before==hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    report=dict(status='awaiting_clarification',source_preserved=True,
                completed=['blind cap19 closed floor','integral pinion shaft outline','phi23 external shaft association',
                           'shaft/gear shared contact plane','item7 leader','background visibility','reference-like serif font',
                           '2.8mm filled dimension arrows'],
                checks='saved DXF, independent cap loop, two arrow heads, source point and background visibility',
                pending=['bearing representation/model reply','unnumbered thin-wall section identity reply'],
                visible_background_segments=visible,fonts={'Latin':'times.ttf','Chinese':'simfang.ttf'},
                scope='NTS partial reconstruction; not a completed or certified assembly')
    (HERE/'本轮进度与检查.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
