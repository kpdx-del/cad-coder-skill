"""Local-cutaway correction of the user-supplied NTS teaching illustration."""
from pathlib import Path
import sys,importlib.util,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'revision-04'))
spec=importlib.util.spec_from_file_location('revision04',ROOT/'revision-04/complete_assembly.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
from ezdxf.math.clipping import ConcaveClippingPolygon2d
p=b.p;V=b.Vec2;meta=b.annotation_data;mark=b.mark_annotation


def build():
    d,_=b.build();m=d.modelspace()
    # Source: one rounded end; the other runs out at the shaft end.
    for e in list(m.query('LWPOLYLINE')):
        data=meta(e)
        if data.get('kind')!='assembly_closed_keyway' or data['item']==11:continue
        item=data['item'];m.delete_entity(e)
        coords=([(389,32,0),(389,96,1),(409,96,0),(409,32,0)] if item==4 else
                [(678,837,0),(678,728,-1),(698,728,0),(698,837,0)])
        e=m.add_lwpolyline([(*p(x,y),bulge) for x,y,bulge in coords],format='xyb')
        mark(e,'assembly_end_key',item=item,representation='one round end, open to shaft end; source Fig2-1')
    cut=[(117,410),(170,428),(235,451),(301,477),(348,513),(370,546),(373,568),
         (371,583),(366,597),(366,609),(370,625),(372,644)]
    for e in list(m.query('SPLINE')):
        if meta(e).get('kind')=='replica_cutaway_boundary':m.delete_entity(e)
    curve=m.add_spline([p(*q) for q in cut],dxfattribs={'layer':'THIN'})
    mark(curve,'assembly_break_boundary',source='user-confirmed local cutaway; NTS')
    sampled=[V(q) for q in b.make_path(curve).flattening(.03)]
    mask=[p(0,0),p(1200,0),p(1200,981),p(372,981),*reversed(sampled),p(0,410)]
    clipping=ConcaveClippingPolygon2d(mask)
    for h in list(m.query('HATCH')):
        data=meta(h)
        if data.get('part')==18 and sum(q.x for q in b.loop(h))/len(b.loop(h))<p(399,0).x:
            m.delete_entity(h) # concealed behind the uncut case front
        elif data.get('part')==19:
            owner=data['boundary'];regions=[]
            # Intersect disjoint triangles: concave clipping with a coincident
            # endpoint otherwise drops this U-shaped cap in ezdxf 1.4.5.
            for cut_triangle in b.old.mapbox_earcut_2d(mask):
                clip=b.old.ConvexClippingPolygon2d(cut_triangle)
                for material_triangle in b.old.mapbox_earcut_2d(b.loop(h)):
                    regions.extend(q for q in clip.clip_polygon(material_triangle) if len(q)>2 and b.area(q)>1e-8)
            m.delete_entity(h)
            for region in regions:
                boundary=m.add_lwpolyline(region,close=True,dxfattribs={'layer':'PART_TOPOLOGY'})
                section=m.add_hatch(dxfattribs={'layer':'HATCH'})
                section.set_pattern_fill('ANSI31',scale=.5,angle=90,style=0)
                section.paths.add_polyline_path(region,is_closed=True)
                mark(section,'assembly_section',part=19,material_owner=owner,boundary=boundary.dxf.handle)
    # Clip INTERNAL display edges to the exposed region; material envelopes
    # stay untouched. The uncut outer case and its bolt heads remain visible.
    candidates=[]
    for e in list(m.query('LWPOLYLINE')):
        if meta(e).get('kind') in ('replica_casing_lip','replica_cavity_boundary') and min(q.x for q in b.loop(e))<p(399,0).x:
            candidates.extend(e.virtual_entities());m.delete_entity(e)
    for e in list(m.query('LINE')):
        data=meta(e);owner=d.entitydb.get(data.get('owner',''))
        part=meta(owner).get('part') if owner else None
        if (part in (5,18,19) and e.dxf.layer=='0') or (
            data.get('kind')=='assembly_case_projection' and max(e.dxf.start.x,e.dxf.end.x)<p(568,0).x):
            candidates.append(e.copy());m.delete_entity(e)
    for e in candidates:
        if e.dxftype()!='LINE':continue
        for a,z in clipping.clip_line(V(e.dxf.start),V(e.dxf.end)):
            line=m.add_line(a,z);mark(line,'assembly_exposed_projection')
    # Source unsectioned front face and its local curved contours.
    for a,z in [((265,625),(370,625)),((265,625),(265,644)),((265,644),(372,644))]:m.add_line(p(*a),p(*z))
    for points in [[(217,503),(219,511),(231,517),(235,533),(236,567),(242,590),(257,606),(283,616),(306,617),(313,614)],
                   [(318,518),(322,537),(326,563),(331,589)]]:
        m.add_spline([p(*q) for q in points],dxfattribs={'layer':'THIN'})
    # Gear end-face projections and separate thin chain pitch generators.
    for y in (347,474):m.add_line(p(339,y),p(457,y))
    for e in m.query('LINE'):
        for x in (344,451):
            if V(e.dxf.start).isclose(p(x,342),abs_tol=1e-7) and V(e.dxf.end).isclose(p(x,479),abs_tol=1e-7):
                e.dxf.layer='CENTER';e.dxf.ltscale=.3;mark(e,'gear_pitch_generator',part=5)
    # Locally sectioned pinion strip, not hatching the whole longitudinal shaft.
    points=[p(*q) for q in [(443,347),(440,365),(441,388),(435,416),(442,442),(449,459),(450,474),(457,474),(457,347)]]
    boundary=m.add_lwpolyline(points,close=True,dxfattribs={'layer':'PART_TOPOLOGY'})
    h=m.add_hatch(dxfattribs={'layer':'HATCH'});h.set_pattern_fill('ANSI31',scale=.5,style=0)
    h.paths.add_polyline_path(points,is_closed=True);mark(h,'assembly_section',part=5,boundary=boundary.dxf.handle)
    m.add_spline(points[:-2],dxfattribs={'layer':'THIN'})
    fit=next(e for e in m.query('DIMENSION') if e.dxf.text=='φ100H7/f9')
    mark(fit,'dimension',arrows='auto',blank_ends=[],text_side='above',schematic_only=True,
         interface={'hole':'housing_100H7','shaft':'cap14_register_100f9'},
         attachment_points=[list(p(568,603)),list(p(808,603))])
    for e in m.query('TEXT'):
        if e.dxf.text.startswith('修订04：'):e.dxf.text='修订05：按参照修正局部剖切、分度线和端部键；NTS示意，非制造图'
    return d


if __name__=='__main__':
    doc=build();path=HERE/'装配图_修订05_审阅版.dxf';doc.saveas(path)
    saved=b.ezdxf.readfile(path);assert not saved.audit().has_errors
    issues=b.old.audit_annotations(saved.modelspace(),required_arrows={e.dxf.handle:(1,2) for e in saved.modelspace().query('DIMENSION')})
    assert not issues,issues
    renderer_spec=importlib.util.spec_from_file_location('batch_renderer',str(ROOT.parent/'scripts/render_dxf.py'))
    renderer=importlib.util.module_from_spec(renderer_spec);renderer_spec.loader.exec_module(renderer)
    renderer.render_many(path,[path.with_suffix('.png'),path.with_suffix('.pdf')],paper='A3',scale=1,margin=5)
    (HERE/'检查.json').write_text(json.dumps({'arrows':issues,'status':'needs_visual_review',
        'scope':'local cutaway source reconstruction, not manufacturing dimensions'},ensure_ascii=False,indent=2),encoding='utf-8')
