"""Revision 04: source-based NTS contours, curved gear recesses and slots.

Layout coordinates are not new manufacturing dimensions. Keeps revision 03
unchanged, including the user's prescribed bearings and independent spacer.
"""
from pathlib import Path
import sys
import importlib.util
import json
import math
import hashlib
from itertools import combinations

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'revision-03'))
spec=importlib.util.spec_from_file_location('assembly_revision03',ROOT/'revision-03/complete_assembly.py')
old=importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
ezdxf=old.ezdxf
p=old.p
Vec2=old.Vec2
area=old.area
annotation_data=old.annotation_data
mark_annotation=old.mark_annotation
from ezdxf.path import make_path
from ezdxf import bbox
from ezdxf.math import intersection_line_line_2d
from ezdxf.math.clipping import polygon_line_intersections_2d
from ezdxf.render.hatching import hatch_entity
from drawing_layout import _segment_hits_rect

ARROW=3.5
Q=math.tan(math.pi/8)
CASE_PROBES=[(500,307),(500,513),(470,307),(470,513),(780,307),(780,513)]


def loop(e):
    if e.dxftype()=='HATCH':
        from ezdxf.path import from_hatch_boundary_path
        path=from_hatch_boundary_path(e.paths[0])
    else: path=make_path(e)
    points=[Vec2(q) for q in path.flattening(.002,segments=8)]
    if points[-1].isclose(points[0],abs_tol=1e-8): points.pop()
    return points


def material_polygons(doc):
    return [(e,annotation_data(e),loop(e),[]) for e in doc.modelspace().query('LWPOLYLINE')
            if annotation_data(e).get('kind')=='assembly_face']


def curved_face(m,coords,region,mirror=False):
    points=[(*p(1376-x if mirror else x,y),-b if mirror else b) for x,y,b in coords]
    e=m.add_lwpolyline(points,format='xyb',close=True,dxfattribs={'layer':'PART_TOPOLOGY'})
    mark_annotation(e,'assembly_face',part=12,role='gear',region=region,sectioned=True,
                    geometry_source='supplied textbook Fig2-1, NTS layout')
    h=m.add_hatch(dxfattribs={'layer':'HATCH'})
    h.set_pattern_fill('ANSI31',scale=.5,angle=0,style=0)
    h.paths.add_polyline_path(points,is_closed=True,flags=1)
    mark_annotation(h,'assembly_hatch',part=12,role='gear',boundary=e.dxf.handle)


def closed_slot(m,cx,y0,y1,w,item):
    r=w/2
    points=[(*p(cx-r,y0+r),0),(*p(cx-r,y1-r),1),(*p(cx+r,y1-r),0),(*p(cx+r,y0+r),1)]
    e=m.add_lwpolyline(points,format='xyb',close=True)
    mark_annotation(e,'assembly_closed_keyway',item=item,source='reference-like obround, NTS',
                    axis_x=p(cx,0).x,end_planes=[p(0,y0).y,p(0,y1).y])
    return e


def replace_slots(m):
    for cx,y0,y1,w,item in [(399,32,106,20,4),(688,368,451,25,11),(688,718,836,20,16)]:
        a=p(cx-w/2,y0);b=p(cx+w/2,y1)
        for e in list(m):
            if e.dxftype() not in ('LINE','ARC') or e.dxf.layer!='0': continue
            bounds=bbox.extents([e],fast=False)
            if (bounds.extmin.x>=a.x-1e-6 and bounds.extmax.x<=b.x+1e-6
                and bounds.extmin.y>=b.y-1e-6 and bounds.extmax.y<=a.y+1e-6): m.delete_entity(e)
        # The reference gives no slot length. Move the schematic ends clear
        # of the shaft end faces; do not attach dimensional values to them.
        if item==4: y0,y1=43,106
        elif item==16: y0,y1=725,825
        closed_slot(m,cx,y0,y1,w,item)


def visible_material_boundaries(m):
    for e in m.query('LWPOLYLINE'):
        if annotation_data(e).get('kind')!='assembly_face': continue
        e.dxf.layer='PART_TOPOLOGY'
        for v in e.virtual_entities():
            v.dxf.layer='0';m.add_entity(v)
            mark_annotation(v,'assembly_visible_boundary',owner=e.dxf.handle)


def unique_lines(m):
    """Split/deduplicate all visible straight outlines, including projections."""
    entities=list(m.query('LINE[layer=="0"]'))
    segments=[(Vec2(e.dxf.start),Vec2(e.dxf.end),annotation_data(e)) for e in entities]
    for e in entities: m.delete_entity(e)
    seen=set()
    for a,b,data in segments:
        v=b-a;cuts=[0.,1.]
        for c,d,_ in segments:
            for q in (c,d):
                t=(q-a).dot(v)/v.dot(v)
                if 1e-8<t<1-1e-8 and abs((q-a).det(v))<1e-7*v.magnitude: cuts.append(t)
        cuts=sorted(set(round(t,10) for t in cuts))
        for lo,hi in zip(cuts,cuts[1:]):
            x,y=a+v*lo,a+v*hi
            key=tuple(sorted((tuple(round(n,7) for n in x),tuple(round(n,7) for n in y))))
            if key in seen: continue
            seen.add(key);e=m.add_line(x,y)
            if data:
                d=dict(data);kind=d.pop('kind');mark_annotation(e,kind,**d)


def projection(m,points,feature,occluders):
    """Projected edges are separate from material faces and never hatched."""
    for a,b in zip(points,points[1:]):
        a,b=p(*a),p(*b);v=b-a;cuts=[0.,1.]
        for poly in occluders:
            cuts.extend((q-a).dot(v)/v.dot(v) for q in polygon_line_intersections_2d(poly,(a,b)))
        cuts=sorted({round(max(0,min(1,t)),10) for t in cuts})
        for lo,hi in zip(cuts,cuts[1:]):
            if hi-lo<1e-9: continue
            midpoint=a+v*(lo+hi)/2
            if any(old.is_point_in_polygon_2d(midpoint,poly)>0 for poly in occluders): continue
            e=m.add_line(a+v*lo,a+v*hi)
            mark_annotation(e,'assembly_case_projection',feature=feature)


def readable_dimension(d):
    e=d.dimension;data=annotation_data(e);data.pop('kind',None)
    mark_annotation(e,'dimension',**dict(data,arrows='auto',text_side='above',blank_ends=[]))
    d.update({'dimasz':ARROW,'dimtxt':3.5,'dimblk':'','dimblk1':'','dimblk2':'','dimtxsty':'CAD_TEXT'})
    d.render()
    boxes=[old.text_rect(t) for t in e.doc.blocks.get(e.dxf.geometry).query('MTEXT')]
    left=min(r[0] for r in boxes);right=max(r[2] for r in boxes)
    low,high=sorted((e.dxf.defpoint2.x,e.dxf.defpoint3.x))
    if left<low+.8 or right>high-.8:
        d.set_location(Vec2(e.dxf.text_midpoint)+Vec2(high+3-left,0),leader=False,relative=False)
        mark_annotation(e,'dimension',**dict(data,arrows='outside',text_side='above',blank_ends=[]))
        d.render()
    elif right-left+2*ARROW+1.6>high-low:
        mark_annotation(e,'dimension',**dict(data,arrows='outside',text_side='above',blank_ends=[]))
        d.render()


def build():
    doc,specs=old.build();m=doc.modelspace()
    # Replace display edges only; closed editable material topology stays.
    for e in list(m):
        data=annotation_data(e)
        if data.get('kind')=='assembly_visible_boundary': m.delete_entity(e)
        elif data.get('part')==12 and data.get('kind') in ('assembly_face','assembly_hatch'):
            m.delete_entity(e)
    rim=[(457,353,0),(476,353,0),(476,382,Q),(487,393,0),(522,393,0),
         (522,427,0),(487,427,Q),(476,438,0),(476,469,0),(457,469,0)]
    hub=[(594,353,0),(628,353,0),(628,469,0),(594,469,0),(594,438,Q),
         (583,427,0),(546,427,0),(546,393,0),(583,393,Q),(594,382,0)]
    for mirror in (False,True):
        curved_face(m,rim,'rim_web',mirror);curved_face(m,hub,'hub_web',mirror)
    replace_slots(m)
    # Thin adjustment strips at the already drawn cap/case contact interface.
    # NTS layout, not an asserted shim thickness or a newly selected component.
    for a,b in ((521,568),(808,865)):
        old.face(m,[(a,615),(b,615),(b,617),(a,617)],13,'adjustment_shim',None)
    # Native hatch patterns are clipped to their own closed faces. A consistent
    # denser phase makes the thin web and race sections readable at A3 size.
    for h in m.query('HATCH'):
        if h.dxf.pattern_name=='ANSI31':
            h.set_pattern_fill('ANSI31',scale=.5,angle=h.dxf.pattern_angle,style=0)
    visible_material_boundaries(m)
    material=[poly for _,_,poly,_ in material_polygons(doc)]
    for e in m.query('LWPOLYLINE'):
        if annotation_data(e).get('kind')!='replica_cavity_boundary': continue
        points=[]
        for x,y in e.get_points('xy'):
            if abs(y-p(0,525).y)<1e-7: y=p(0,513).y
            elif abs(y-p(0,511).y)<1e-7: y=p(0,499).y
            points.append((x,y))
        e.set_points(points)
    caps=[[(265,176),(518,176),(518,202),(484,202),(484,224),(314,224),(314,202),(265,202)],
          [(265,644),(518,644),(518,618),(484,618),(484,602),(314,602),(314,618),(265,618)],
          [(521,171),(865,171),(865,203),(808,203),(808,228),(568,228),(568,203),(521,203)],
          [(521,649),(865,649),(865,617),(808,617),(808,594),(568,594),(568,617),(521,617)]]
    occluders=material+[[p(*q) for q in poly] for poly in caps]
    for points,name in [
        ([(484,198),(568,198),(568,307),(484,307),(484,198)],'upper_case_land'),
        ([(484,513),(568,513),(568,625),(484,625),(484,513)],'lower_case_land'),
        ([(314,307),(808,307)],'upper_inner_wall_bridge'),
        ([(314,513),(808,513)],'lower_inner_wall_bridge'),
    ]: projection(m,points,name,occluders)
    # Visible recess lips and web-hole edges are projections, not extra metal.
    for mirror in (False,True):
        for a,b,y in [(457,628,353),(457,628,469),(522,546,393),(522,546,427)]:
            pts=[(1376-a if mirror else a,y),(1376-b if mirror else b,y)]
            projection(m,pts,'gear_projected_lip',material)
    # Re-route the three lower-right item leaders into separate free regions.
    # A shorter segment through the cap avoids following its hatch direction.
    for item,start,end in [(15,(778,817),(775.5,563)),(14,(892,817),(850,645)),(13,(973,817),(865,616))]:
        leader=next(e for e in m.query('LWPOLYLINE') if e.dxf.layer=='DIM' and len(e)==3
                    and Vec2(e.get_points('xy')[0]).isclose(p(*start),abs_tol=1e-7))
        locations={15:[(793,802),(835,802),end],14:[(955,735),(997,735),end],13:[(1080,680),(1122,680),end]}
        leader.set_points([p(*q) for q in [locations[item][1],locations[item][0],end]])
        mark_annotation(leader,'assembly_item_leader',item=item,target_part=item)
        label=next(e for e in m.query('TEXT') if e.dxf.text==str(item))
        q=locations[item][0];label.set_placement(p(q[0]+20,q[1]-12),align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    # Enlarge actual native dimension arrowheads, then recalculate placement.
    doc.dimstyles.get('CAD_MM').dxf.dimasz=ARROW
    for d in m.query('DIMENSION'): readable_dimension(d.override())
    # The head is now fully inside the shaft. Its item pointer follows it.
    leader=next(e for e in m.query('LWPOLYLINE') if e.dxf.layer=='DIM' and len(e)==3
                and Vec2(e.get_points('xy')[0]).isclose(p(291,70),abs_tol=1e-7))
    points=list(leader.get_points('xy'));points[-1]=p(399,55);leader.set_points(points)
    for e in list(m.query('LINE')):
        if e.dxf.layer!='CENTER': continue
        a,b=Vec2(e.dxf.start),Vec2(e.dxf.end)
        if any(abs(a.x-p(x,0).x)<1e-7 and abs(b.x-p(x,0).x)<1e-7 for x in (399,688)) or (
            abs(a.y-p(0,411).y)<1e-7 and abs(b.y-p(0,411).y)<1e-7): m.delete_entity(e)
    axes=[m.add_line(p(399,16),p(399,665),dxfattribs={'layer':'CENTER'}),
          m.add_line(p(688,145),p(688,850),dxfattribs={'layer':'CENTER'}),
          m.add_line(p(83,411),p(1085,411),dxfattribs={'layer':'CENTER'})]
    old.avoid_text_on_horizontal_lines(m,axes)
    unique_lines(m)
    for e in m.query('TEXT'):
        if e.dxf.text.startswith('修订03：'):
            e.dxf.text='修订04：齿轮、箱体可见轮廓及闭合键槽；未注几何为示意，非制造图'
    return doc,specs


def audit(doc):
    m=doc.modelspace();issues=old.audit_annotations(m,required_arrows={d.dxf.handle:(1,2) for d in m.query('DIMENSION')})
    parts=material_polygons(doc)
    for e,data,points,holes in parts:
        triangles=old.mapbox_earcut_2d(points,holes)
        if abs(sum(area(t) for t in triangles)-area(points))>1e-6:
            issues.append('material triangulation failed '+e.dxf.handle)
    for h in m.query('HATCH'):
        data=annotation_data(h)
        if data.get('kind')!='assembly_hatch': continue
        boundary=doc.entitydb[data['boundary']]
        if not boundary.closed or not old.equal_loop(loop(h),loop(boundary)):
            issues.append('hatch boundary mismatch '+h.dxf.handle)
    for a,b in combinations(parts,2):
        if old.overlap_area(a,b)>1e-6: issues.append('material overlap '+str((a[1]['part'],b[1]['part'])))
    leaders=[e for e in m.query('LWPOLYLINE') if e.dxf.layer=='DIM' and len(e)==3]
    labels=[(e.dxf.text,old.text_rect(e)) for e in m.query('TEXT') if e.dxf.text in {str(i) for i in range(1,20)}]
    for i,e in enumerate(leaders):
        points=[Vec2(q) for q in e.get_points('xy')]
        for f in leaders[i+1:]:
            other=[Vec2(q) for q in f.get_points('xy')]
            if any(intersection_line_line_2d((a,b),(x,y),virtual=False) is not None
                   for a,b in zip(points,points[1:]) for x,y in zip(other,other[1:])):
                issues.append('item leader intersection '+e.dxf.handle+'/'+f.dxf.handle)
        for label,rect in labels:
            if any(_segment_hits_rect(a,b,rect) for a,b in zip(points,points[1:])):
                issues.append('item leader crosses label '+label)
    straight=[(Vec2(e.dxf.start),Vec2(e.dxf.end)) for e in m.query('LINE[layer=="0"]')]
    for x,y in CASE_PROBES:
        q=p(x,y)
        if not any(point_on_segment(q,a,b) for a,b in straight):
            issues.append('missing declared case edge '+str((x,y)))
    for e in m.query('LWPOLYLINE'):
        if annotation_data(e).get('kind')=='assembly_closed_keyway':
            if not e.closed or sum(abs(q[2])==1 for q in e.get_points('xyb'))!=2:
                issues.append('incomplete obround '+e.dxf.handle)
    return issues


def point_on_segment(q,a,b):
    v=b-a;t=(q-a).dot(v)/v.dot(v)
    return -1e-7<=t<=1+1e-7 and abs((q-a).det(v))/v.magnitude<1e-6


if __name__=='__main__':
    original=hashlib.sha256((ROOT/'revision-03/装配图_修订03_审阅版.dxf').read_bytes()).hexdigest()
    doc,specs=build();path=HERE/'装配图_修订04_审阅版.dxf';doc.saveas(path)
    check=ezdxf.readfile(path);assert not check.audit().has_errors
    issues=audit(check)
    (HERE/'装配复核结果.json').write_text(json.dumps({'status':'passed_declared_checks' if not issues else 'failed',
        'issues':issues,'arrows_mm':ARROW,'scope':'NTS 2D source reconstruction; declared geometry checks only'},ensure_ascii=False,indent=2),encoding='utf-8')
    print('issues',issues)
    for ext in ('png','pdf'): old.render(path,path.with_suffix('.'+ext),paper='A3',scale=1,margin=5)
    assert original==hashlib.sha256((ROOT/'revision-03/装配图_修订03_审阅版.dxf').read_bytes()).hexdigest()
