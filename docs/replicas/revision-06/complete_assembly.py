"""Revision06: explicit cap-register fit witnesses and simplified hex heads."""
from pathlib import Path
import sys,importlib.util,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'revision-05'))
s=importlib.util.spec_from_file_location('revision05',ROOT/'revision-05/complete_assembly.py')
prior=importlib.util.module_from_spec(s);s.loader.exec_module(prior)
b=prior.b;p=prior.p;V=prior.V;meta=prior.meta;mark=prior.mark
sys.path.insert(0,str(ROOT.parent/'cad-coder-skill/scripts'))
from fasteners import hex_head_side


def build():
    doc=prior.build();m=doc.modelspace()
    fit=next(e for e in m.query('DIMENSION') if e.dxf.text=='φ100H7/f9')
    m.delete_entity(fit)
    # Witnesses start at actual cap14 register generators. The dimension line
    # sits below the cut material; its complete label is outside to the left.
    dim=m.add_linear_dim(base=p(688,690),p1=p(568,603),p2=p(808,603),
                         text='φ100H7/f9',dimstyle='CAD_MM',dxfattribs={'layer':'DIM'})
    mark(dim.dimension,'dimension',arrows='outside',blank_ends=[],text_side='above',schematic_only=True,
         interface={'hole':'housing_100H7','shaft':'cap14_register_100f9'},
         attachment_points=[list(p(568,603)),list(p(808,603))])
    dim.update({'dimasz':3.5,'dimtxt':3.5,'dimtxsty':'CAD_TEXT','dimblk':'','dimblk1':'','dimblk2':''})
    dim.set_location(p(490,683),leader=False,relative=False);dim.render()
    # Replace only the eight side-view heads identified as bolts3/8 by the
    # source. Circular flange details and unidentified hex plugs are untouched.
    for x,y,bearing_y,outward,part in [(304,165,176,1,3),(459,165,176,1,3),
                                      (562,156,171,1,8),(771,156,171,1,8),
                                      (304,647,644,-1,3),(459,647,644,-1,3),
                                      (562,650,649,-1,8),(771,650,649,-1,8)]:
        old=[p(x,y),p(x+34,y),p(x+34,y+13),p(x,y+13)]
        match=[e for e in m.query('LWPOLYLINE') if e.closed and len(e)==4 and b.old.equal_loop(b.loop(e),old)]
        if len(match)!=1:raise ValueError('source bolt head not uniquely identified')
        m.delete_entity(match[0])
        for e in list(m.query('LINE')):
            a,z=V(e.dxf.start),V(e.dxf.end)
            if any(a.isclose(p(x+dx,y),abs_tol=1e-7) and z.isclose(p(x+dx,y+13),abs_tol=1e-7) for dx in (10,24)) or (
                a.isclose(p(x+17,y-9),abs_tol=1e-7) and z.isclose(p(x+17,y+20),abs_tol=1e-7)):
                m.delete_entity(e)
        hex_head_side(m,p(x+17,0).x,p(0,bearing_y).y,34*.28,13*.28,outward=outward,part=part)
    for e in m.query('TEXT'):
        if e.dxf.text.startswith('修订05：'):e.dxf.text='修订06：止口配合界线与紧固件简化画法；NTS示意，非制造图'
    return doc


if __name__=='__main__':
    d=build();path=HERE/'完整减速箱_修订06_审阅版.dxf';d.saveas(path)
    d=b.ezdxf.readfile(path);assert not d.audit().has_errors
    issues=b.old.audit_annotations(d.modelspace(),required_arrows={e.dxf.handle:(1,2) for e in d.modelspace().query('DIMENSION')})
    assert not issues,issues
    spec=importlib.util.spec_from_file_location('batch_renderer',str(ROOT.parent/'cad-coder-skill/scripts/render_dxf.py'))
    renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
    renderer.render_many(path,[path.with_suffix('.png'),path.with_suffix('.pdf')],paper='A3',scale=1,margin=5)
    (HERE/'检查.json').write_text(json.dumps({'status':'needs_visual_review','arrow_issues':issues,
        'fit_interface':'housing bore H7 / cap14 register f9; original nominal value retained',
        'fasteners':'8 identified hex bolt heads; no specifications inferred'},ensure_ascii=False,indent=2),encoding='utf-8')
