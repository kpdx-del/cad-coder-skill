"""Complete the source-based NTS assembly after the user's two clarifications.

Independent spacer confirmed by user; prescribed tapered-bearing representation
uses GB/T 4459.7-2017 Fig./table A.1.5 proportions, not a selected bearing model.
No unprovided manufacturing dimensions are claimed by the layout coordinates.
"""
from pathlib import Path
import sys
import json
import math
import hashlib
from itertools import combinations

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'cad_support'))
sys.path.insert(0,str(ROOT))
import ezdxf
from ezdxf.math import Vec2,area,is_point_in_polygon_2d
from ezdxf.math.triangulation import mapbox_earcut_2d
from ezdxf.math.clipping import ConvexClippingPolygon2d
from ezdxf.entities.boundary_paths import PolylinePath
from typography import add_text,text_rect
from drawing_checks import annotation_data,mark_annotation
from drawing_layout import _segments
from sketch_helpers import audit_annotations,_DrawingRenderer
from build_replicas import avoid_text_on_horizontal_lines
from render_dxf import render,_drawing_extents
import revise_known as prior
from revise_known import p,loop,equal_loop,remove_material,hidden_segments_removed,readable_dimension


def face(m,coords,part,role,angle=45,pattern='ANSI31',scale=.7):
    points=[p(*q) for q in coords]
    boundary=m.add_lwpolyline(points,close=True)
    mark_annotation(boundary,'assembly_face',part=part,role=role,sectioned=angle is not None)
    if angle is not None:
        h=m.add_hatch(dxfattribs={'layer':'HATCH'})
        h.set_pattern_fill(pattern,scale=scale,angle=angle-45,style=0)
        h.paths.add_polyline_path(points,is_closed=True)
        mark_annotation(h,'assembly_hatch',part=part,role=role,boundary=boundary.dxf.handle)
    return boundary


def bearing(m,cx,cap_y,shoulder_y,inner,outer,part,angle):
    """Prescribed symbol: two flanged races and an unhatched inclined roller.

    15 degrees and A/2 roller thickness are drawing proportions from A.1.5,
    not the contact angle or dimensions of an inferred commercial bearing.
    Cup/cone axial positions are distinct. Overall assembly remains NTS.
    """
    direction=1 if shoulder_y>cap_y else -1
    T=abs(shoulder_y-cap_y);A=outer-inner
    theta=math.radians(15);c,s=math.cos(theta),math.sin(theta)
    U=T/2;R=inner+A/2;L=.43*T;W=A/2
    roller=[(U+du*c-dv*s,R+du*s+dv*c) for du,dv in [(-L/2,-W/2),(L/2,-W/2),(L/2,W/2),(-L/2,W/2)]]
    lo=min(q[0] for q in roller)-.4;hi=max(q[0] for q in roller)+.4
    B=.92*T;C=.78*T
    def floor(u): return R-W/(2*c)+math.tan(theta)*(u-U)
    def ceiling(u): return R+W/(2*c)+math.tan(theta)*(u-U)
    cone=[(T-B,inner),(T,inner),(T,inner+A/2),(hi,inner+A/2),
          (hi,floor(hi)),(lo,floor(lo)),(lo,inner+A/4),(T-B,inner+A/4)]
    cup=[(0,outer),(C,outer),(C,ceiling(C)),(0,ceiling(0))]
    for sign in (-1,1):
        def tr(points): return [(cx+sign*r,cap_y+direction*u) for u,r in points]
        for role,points,hatched in [('cup',cup,True),('cone',cone,True),('roller',roller,False)]:
            e=face(m,tr(points),part,role,angle if hatched else None)
            data=annotation_data(e);data.pop('kind')
            mark_annotation(e,'assembly_face',**dict(data,representation='prescribed',basis='GB/T 4459.7-2017 A.1.5',
                drawing_angle=15,not_a_selected_contact_angle=True,axis=list(p(cx,0)),cap_face_y=cap_y,
                shoulder_face_y=shoulder_y,cone_small_end_y=cap_y+direction*(T-B)))
    return {'cup_inner_radius_at_cap':ceiling(0),'cone_small_end_y':cap_y+direction*(T-B),
            'cup_far_end_y':cap_y+direction*C}


def find_cap_hatch(m,xy):
    matches=[h for h in m.query('HATCH') if isinstance(h.paths[0],PolylinePath)
             and is_point_in_polygon_2d(p(*xy),loop(h))>0]
    if len(matches)!=1: raise ValueError(f'cap not uniquely identifiable at {xy}')
    return matches[0]


def remove_rect(m,coords):
    target=[p(*q) for q in coords]
    matches=[e for e in m.query('LWPOLYLINE') if e.closed and equal_loop(loop(e),target)]
    if len(matches)!=1: raise ValueError('expected exactly one old component outline')
    m.delete_entity(matches[0])


def unique_visible_boundaries(m):
    """Closed material loops stay editable on an off layer; show each edge once.

    Shared contact edges are split at endpoint junctions before deduplication.
    Hatches keep their own closed loops; there are no hand-filled gaps.
    """
    if 'PART_TOPOLOGY' not in m.doc.layers:
        m.doc.layers.new('PART_TOPOLOGY',dxfattribs={'color':8,'plot':0})
    m.doc.layers.get('PART_TOPOLOGY').off()
    boundaries=[e for e in m.query('LWPOLYLINE') if annotation_data(e).get('kind')=='assembly_face']
    segments=[]
    for e in boundaries:
        e.dxf.layer='PART_TOPOLOGY'
        points=loop(e)
        segments.extend((a,b) for a,b in zip(points,points[1:]+points[:1]) if (b-a).magnitude>1e-8)
    output=set()
    for a,b in segments:
        v=b-a;cuts=[0.,1.]
        for c,d in segments:
            for q in (c,d):
                t=(q-a).dot(v)/v.dot(v)
                if 1e-8<t<1-1e-8 and abs((q-a).det(v))<1e-7*v.magnitude: cuts.append(t)
        cuts=sorted(set(round(t,10) for t in cuts))
        for lo,hi in zip(cuts,cuts[1:]):
            x,y=a+v*lo,a+v*hi
            key=tuple(sorted((tuple(round(n,7) for n in x),tuple(round(n,7) for n in y))))
            if key in output: continue
            output.add(key)
            e=m.add_line(x,y)
            mark_annotation(e,'assembly_visible_boundary')


def build():
    doc,_,_=prior.revise();m=doc.modelspace()
    # Remove the incomplete earlier bearing symbols and the cap/seal material.
    for e in list(m):
        data=annotation_data(e)
        if data.get('kind')=='replica_bearing': m.delete_entity(e)
    for xy in ((280,185),(500,185),(540,185),(540,635),(840,635),(399,635)):
        remove_material(m,find_cap_hatch(m,xy))
    for h in list(m.query('HATCH')):
        if annotation_data(h).get('material')=='felt': remove_material(m,h)
    # Old disconnected rectangles are replaced by one shaft shoulder or by the
    # separately confirmed spacer, rather than unowned material fragments.
    for a,b,c,d in ((619,291,628,335),(748,291,756,335),(619,474,633,532),(743,474,756,532)):
        remove_rect(m,[(a,b),(c,b),(c,d),(a,d)])
    for y in (291,532):
        for a,b in ((315,365),(433,484),(568,628),(748,808)):
            for e in list(m.query('LINE')):
                if Vec2(e.dxf.start).isclose(p(a,y),abs_tol=1e-7) and Vec2(e.dxf.end).isclose(p(b,y),abs_tol=1e-7):
                    m.delete_entity(e)

    specs={
        'input_upper':bearing(m,399,224,291,34,85,'input_upper_bearing',135),
        'input_lower':bearing(m,399,602,532,34,85,18,45),
        'output_upper':bearing(m,688,228,291,60,120,9,135),
        'output_lower':bearing(m,688,594,532,55,120,15,45),
    }
    # Exposed ends of the housing bearing-seat generators remain visible when
    # the shorter cup ends before the adjacent housing cavity boundary.
    for key,cx,outer,edge_y in [('input_upper',399,85,291),('input_lower',399,85,532),
                              ('output_upper',688,120,291),('output_lower',688,120,532)]:
        for sign in (-1,1):
            e=m.add_line(p(cx+sign*outer,specs[key]['cup_far_end_y']),p(cx+sign*outer,edge_y))
            mark_annotation(e,'housing_seat_continuation',part='housing',bearing=key)
    iu=specs['input_upper']['cup_inner_radius_at_cap'];il=specs['input_lower']['cup_inner_radius_at_cap']
    ou=specs['output_upper']['cup_inner_radius_at_cap'];ol=specs['output_lower']['cup_inner_radius_at_cap']
    # Through cap 2, including the two open-to-bore felt grooves.
    face(m,[(265,176),(365,176),(365,190),(353,190),(353,200),(365,200),(365,202),
            (399-iu,202),(399-iu,224),(314,224),(314,202),(265,202)],2,'cap_left',45)
    face(m,[(433,176),(518,176),(518,202),(484,202),(484,224),(399+iu,224),
            (399+iu,202),(433,202),(433,200),(445,200),(445,190),(433,190)],2,'cap_right',45)
    # Blind cap 19: continuous central floor and a clearance pocket.
    face(m,[(265,644),(518,644),(518,618),(484,618),(484,602),(399+il,602),
            (399+il,625),(399-il,625),(399-il,602),(314,602),(314,618),(265,618)],19,'blind_cap',135)
    # Blind cap 7: nose abuts the cup, with axial clearance above the shaft.
    face(m,[(521,171),(865,171),(865,203),(808,203),(808,228),(688+ou,228),
            (778,214),(600,214),(688-ou,228),(568,228),(568,203),(521,203)],7,'blind_cap',45)
    # Through cap 14. The groove is cut from the metal face, not painted over it.
    face(m,[(521,649),(639,649),(639,641),(627,641),(627,631),(639,631),(639,618),
            (615,618),(688-ol,594),(568,594),(568,617),(521,617)],14,'cap_left',135)
    face(m,[(737,649),(865,649),(865,617),(808,617),(808,594),(688+ol,594),
            (761,618),(737,618),(737,631),(749,631),(749,641),(737,641)],14,'cap_right',135)
    for a,b,y,part in ((353,365,190,6),(433,445,190,6),(627,639,631,17),(737,749,631,17)):
        face(m,[(a,y),(b,y),(b,y+10),(a,y+10)],part,'felt',45,'ANSI37',.18)

    # Reposition only unprovided layout planes, keeping all printed fit labels.
    input_shaft=next(e for e in m.query('LWPOLYLINE') if annotation_data(e).get('kind')=='replica_solid_shaft'
                     and min(v[0] for v in e.get_points('xy'))<p(399,0).x)
    end=specs['input_lower']['cone_small_end_y']
    pts=[]
    for x,y in input_shaft.get_points('xy'):
        if abs(y-p(0,580).y)<1e-7: y=p(0,end).y
        if abs(y-p(0,588).y)<1e-7: y=p(0,end+8).y
        pts.append((x,y))
    input_shaft.set_points(pts)
    mark_annotation(input_shaft,'assembly_face',part=5,role='solid_shaft',sectioned=False)
    for e in m.query('SPLINE'):
        if annotation_data(e).get('kind')=='replica_cutaway_boundary':
            points=list(e.fit_points);points[-1]=(*p(377,end+8),0);e.fit_points=points
    output=next(e for e in m.query('LWPOLYLINE') if annotation_data(e).get('kind')=='replica_solid_shaft')
    coords=[(628,228),(748,228),(748,291),(757,291),(757,353),(748,353),(748,469),
            (743,469),(743,594),(737,594),(737,706),(732,706),(732,831),(726,837),
            (652,837),(646,831),(646,706),(639,706),(639,594),(633,594),(633,469),
            (628,469),(628,353),(619,353),(619,291),(628,291)]
    output.set_points([p(*q) for q in coords])
    mark_annotation(output,'assembly_face',part=10,role='solid_shaft',sectioned=False)
    # One independent annular spacer has two cut faces in this longitudinal view.
    for a,b in ((619,633),(743,757)):
        face(m,[(a,469),(b,469),(b,532),(a,532)],'spacer_unlisted','independent_spacer',135)

    # Give the retained gear faces explicit ownership for material checks.
    for h in m.query('HATCH'):
        if annotation_data(h).get('kind')!='replica_gear_section': continue
        matches=[e for e in m.query('LWPOLYLINE') if e.closed and equal_loop(loop(e),loop(h))]
        if len(matches)!=1: raise ValueError('gear outline not unique')
        # The source web opening meets the lower recess. It is a notch in
        # the outer boundary, not an interior island touching that boundary:
        # a touching "hole" gives ambiguous hatch/triangulation results.
        hole=[Vec2(v[:2]) for v in h.paths[1].vertices]
        for e in list(m.query('LWPOLYLINE')):
            if e.closed and equal_loop(loop(e),hole): m.delete_entity(e)
        bottom=min(q.y for q in hole)
        contact=[q for q in hole if abs(q.y-bottom)<1e-7]
        ring=loop(matches[0]);repaired=[];joined=False
        for a,b in zip(ring,ring[1:]+ring[:1]):
            repaired.append(a)
            if abs(a.y-bottom)<1e-7 and abs(b.y-bottom)<1e-7 and all(
                min(a.x,b.x)<q.x<max(a.x,b.x) for q in contact):
                ordered=sorted(contact,key=lambda q:(q-a).magnitude)
                top=max(q.y for q in hole)
                repaired.extend([ordered[0],Vec2(ordered[0].x,top),Vec2(ordered[1].x,top),ordered[1]])
                joined=True
        if not joined: raise ValueError('source gear cutout must meet the lower recess')
        matches[0].set_points(repaired)
        h.paths.clear()
        h.paths.add_polyline_path(repaired,is_closed=True)
        mark_annotation(matches[0],'assembly_face',part=12,role='gear',sectioned=True)
        mark_annotation(h,'assembly_hatch',part=12,role='gear',boundary=matches[0].dxf.handle)

    # Re-associate dimensions to their real interfaces. Values stay as printed.
    replacements=[('72H7/f9',(314,224),(484,224),(399,211),'case_cap2_spigot'),
                  ('72H7',(314,252),(484,252),(399,252),'case_bore72'),
                  ('30k6',(365,277),(433,277),(399,310),'shaft5_inner_ring'),
                  ('45k6',(633,550),(743,550),(688,510),'shaft10_inner_ring'),
                  ('100H7',(568,570),(808,570),(688,570),'case_bore100'),
                  ('100H7/f9',(568,603),(808,603),(688,612),'case_cap14_spigot'),
                  ('35p6',(646,780),(732,780),(688,857),'shaft10_external_key16_seat')]
    for label,a,b,base,interface in replacements:
        old=next(e for e in m.query('DIMENSION') if e.dxf.text=='φ'+label)
        m.delete_entity(old)
        d=m.add_linear_dim(base=p(*base),p1=p(*a),p2=p(*b),text='φ'+label,dimstyle='CAD_MM',dxfattribs={'layer':'DIM'})
        mark_annotation(d.dimension,'dimension',arrows='auto',text_side='above',blank_ends=[],schematic_only=True,interface=interface)
        readable_dimension(d)

    # Attach bearing item leaders to actual roller symbols, not empty space.
    for start,part in (((643,63),9),((778,817),15),((400,817),18)):
        leader=next(e for e in m.query('LWPOLYLINE') if e.dxf.layer=='DIM' and len(e)==3
                    and Vec2(e.get_points('xy')[0]).isclose(p(*start),abs_tol=1e-7))
        rollers=[e for e in m.query('LWPOLYLINE') if annotation_data(e).get('part')==part and annotation_data(e).get('role')=='roller']
        roller=min(rollers,key=lambda e:sum(q.x for q in loop(e))) if part in (9,18) else max(rollers,key=lambda e:sum(q.x for q in loop(e)))
        center=sum(loop(roller),Vec2())/len(loop(roller));points=list(leader.get_points('xy'));points[-1]=center;leader.set_points(points)
    # Item 12 must end on the gear rim, not its recess. Item 13 belongs
    # to the cap/case adjustment interface; the former endpoint entered
    # cap metal and made its leader cross item 14.
    for item,start,target,part in [(12,(817,63),(907,360),12),(13,(973,817),(855,616),'adjustment_interface')]:
        e=next(e for e in m.query('LWPOLYLINE') if e.dxf.layer=='DIM' and len(e)==3
               and Vec2(e.get_points('xy')[0]).isclose(p(*start),abs_tol=1e-7))
        points=list(e.get_points('xy'));points[-1]=p(*target);e.set_points(points)
        mark_annotation(e,'assembly_item_leader',item=item,target_part=part)

    # Rebuild visible background after changing the foreground component faces.
    for e in list(m):
        if annotation_data(e).get('kind')=='assembly_background': m.delete_entity(e)
    backgrounds=[]
    for x0,x1 in ((247,355),(815,974)):
        for y0,y1 in ((187,208),(614,637)):
            corners=[p(x0,y0),p(x1,y0),p(x1,y1),p(x0,y1)]
            backgrounds.extend(m.add_line(a,b) for a,b in zip(corners,corners[1:]+corners[:1]))
    backgrounds.extend(m.add_line(p(195,y),p(984,y)) for y in (206,615))
    material=[loop(e) for e in m.query('LWPOLYLINE') if annotation_data(e).get('kind')=='assembly_face']
    # These are projection masks, not material: a casing edge behind a blind
    # cap must not reappear across the cap's internal clearance pocket.
    silhouettes=[[(265,176),(518,176),(518,202),(484,202),(484,224),(314,224),(314,202),(265,202)],
                 [(265,644),(518,644),(518,618),(484,618),(484,602),(314,602),(314,618),(265,618)],
                 [(521,171),(865,171),(865,203),(808,203),(808,228),(568,228),(568,203),(521,203)],
                 [(521,649),(865,649),(865,617),(808,617),(808,594),(568,594),(568,617),(521,617)]]
    hidden_segments_removed(m,backgrounds,material+[[p(*q) for q in poly] for poly in silhouettes])

    # Main axes are regenerated so former label gaps do not survive re-layout.
    for e in list(m.query('LINE')):
        if e.dxf.layer!='CENTER': continue
        a,b=Vec2(e.dxf.start),Vec2(e.dxf.end)
        if any(abs(a.x-p(x,0).x)<1e-7 and abs(b.x-p(x,0).x)<1e-7 for x in (399,688)) or (
            abs(a.y-p(0,411).y)<1e-7 and abs(b.y-p(0,411).y)<1e-7): m.delete_entity(e)
    axes=[m.add_line(p(399,16),p(399,665),dxfattribs={'layer':'CENTER'}),
          m.add_line(p(688,145),p(688,850),dxfattribs={'layer':'CENTER'}),
          m.add_line(p(83,411),p(1085,411),dxfattribs={'layer':'CENTER'})]
    avoid_text_on_horizontal_lines(m,axes)
    unique_visible_boundaries(m)
    for e in m.query('TEXT'):
        if e.dxf.text.startswith('修订03待确认稿'):
            e.dxf.text='修订03：教材规定画法与独立隔套；未注几何为示意，非制造图'
        elif e.dxf.text.startswith('1、13—'): e.set_placement(p(580,909),align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        elif e.dxf.text.startswith('5—齿轮轴'): e.set_placement(p(580,937),align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    t=add_text(m,'未编号薄壁段按用户确认绘为独立隔套；未指定轴承型号。',p(580,960),3.)
    t.set_placement(p(580,960),align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    return doc,specs


def material_polygons(doc):
    m=doc.modelspace();result=[]
    for e in m.query('LWPOLYLINE'):
        data=annotation_data(e)
        if data.get('kind')!='assembly_face': continue
        holes=[]
        hatch=next((h for h in m.query('HATCH') if annotation_data(h).get('boundary')==e.dxf.handle),None)
        if hatch:
            holes=[[Vec2(v[:2]) for v in path.vertices] for path in list(hatch.paths)[1:]]
        result.append((e,data,loop(e),holes))
    return result


def overlap_area(a,b):
    ta=mapbox_earcut_2d(a[2],a[3]);tb=mapbox_earcut_2d(b[2],b[3]);total=0.
    for x in ta:
        clip=ConvexClippingPolygon2d(x)
        for y in tb:
            polygons=clip.clip_polygon(y)
            total+=sum(area(q) for q in polygons if len(q)>2)
    return total


def audit(doc):
    m=doc.modelspace();issues=[]
    required={e.dxf.handle:(1,2) for e in m.query('DIMENSION')}
    issues.extend(audit_annotations(m,required_arrows=required))
    parts=material_polygons(doc)
    for h in m.query('HATCH'):
        data=annotation_data(h)
        if data.get('kind')!='assembly_hatch': continue
        boundary=doc.entitydb[data['boundary']]
        if not boundary.closed or not equal_loop(loop(h),loop(boundary)):
            issues.append(f'hatch/boundary mismatch {h.dxf.handle}')
    for a,b in combinations(parts,2):
        amount=overlap_area(a,b)
        if amount>1e-6:
            issues.append(f'material overlap {a[1]["part"]}/{a[1]["role"]} {a[0].dxf.handle} vs '
                          f'{b[1]["part"]}/{b[1]["role"]} {b[0].dxf.handle}: {amount:.6g} model-area')
    return issues


if __name__=='__main__':
    original_hash=hashlib.sha256(prior.SOURCE.read_bytes()).hexdigest()
    doc,specs=build()
    path=HERE/'装配图_修订03_审阅版.dxf';doc.saveas(path)
    check=ezdxf.readfile(path);assert not check.audit().has_errors
    issues=audit(check)
    report={'status':'passed_declared_checks' if not issues else 'failed','issues':issues,'bearing_layout':specs,
            'bearing_layout_units':'reference-image layout coordinates, not physical bearing dimensions',
            'user_confirmed':['independent spacer','textbook prescribed bearing representation; no model selected'],
            'scope':'NTS two-dimensional assembly and declared material regions; not a manufacturing/3D certification'}
    (HERE/'装配复核结果.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    for ext in ('png','pdf'): render(path,path.with_suffix('.'+ext),paper='A3',scale=1,margin=5)
    assert original_hash==hashlib.sha256(prior.SOURCE.read_bytes()).hexdigest()
