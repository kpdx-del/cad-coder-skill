"""Revision06: real register anchors, unchanged labels and eight known heads."""
import unittest
import complete_assembly as c
from typography import text_rect


class Revision06Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=c.b.ezdxf.readfile(c.HERE/'完整减速箱_修订06_审阅版.dxf')
        cls.m=cls.doc.modelspace()

    def test_all_source_labels_and_arrows_survive_roundtrip(self):
        before=c.b.ezdxf.readfile(c.ROOT/'revision-05/装配图_修订05_审阅版.dxf')
        dims=list(self.m.query('DIMENSION'))
        self.assertEqual(9,len(dims))
        self.assertEqual(sorted(e.dxf.text for e in before.modelspace().query('DIMENSION')),
                         sorted(e.dxf.text for e in dims))
        self.assertFalse(self.doc.audit().has_errors)
        self.assertEqual([],c.b.old.audit_annotations(self.m,required_arrows={e.dxf.handle:(1,2) for e in dims}))

    def test_fit_witnesses_use_cap_register_not_sealing_journal(self):
        dim=next(e for e in self.m.query('DIMENSION') if e.dxf.text=='φ100H7/f9')
        self.assertTrue(c.V(dim.dxf.defpoint2).isclose(c.p(568,603)))
        self.assertTrue(c.V(dim.dxf.defpoint3).isclose(c.p(808,603)))
        self.assertEqual({'hole':'housing_100H7','shaft':'cap14_register_100f9'},c.meta(dim)['interface'])
        # Each witness origin is on the declared cap14 register generator.
        cap=[poly for _,data,poly,_ in c.b.material_polygons(self.doc) if data['part']==14]
        for point in (c.p(568,603),c.p(808,603)):
            self.assertTrue(any(c.b.old.is_point_in_polygon_2d(point,poly)==0 for poly in cap))
        block=self.doc.blocks.get(dim.dxf.geometry)
        label=next(e for e in block if e.dxftype()=='MTEXT')
        left,bottom,right,top=text_rect(label)
        self.assertLess(right,c.p(568,603).x)
        self.assertGreater(bottom,c.p(688,690).y)
        self.assertLess(top,c.p(688,662).y)

    def test_known_side_heads_touch_the_cap_and_have_no_hatch(self):
        heads=[e for e in self.m.query('LWPOLYLINE') if c.meta(e).get('kind')=='fastener_hex_side']
        self.assertEqual(8,len(heads))
        for head in heads:
            self.assertTrue(head.closed)
            self.assertIn(c.meta(head)['part'],(3,8))
            y=c.meta(head)['bearing_y']
            self.assertEqual(2,sum(abs(v-y)<1e-8 for _,v in head.get_points('xy')))
            middle=sum((c.V(p) for p in head.get_points('xy')),c.V())/4
            self.assertFalse(any(c.b.old.is_point_in_polygon_2d(middle,c.b.loop(h))>0 for h in self.m.query('HATCH')))


if __name__=='__main__':unittest.main()
