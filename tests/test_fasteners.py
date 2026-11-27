"""End-view circle weights and orthographic side-view relationships."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ezdxf
from sketch_helpers import new_doc
from fasteners import hex_end,hex_head_side,thread_end
from drawing_checks import audit_fasteners,annotation_data,mark_annotation


class FastenerChecks(unittest.TestCase):
    def test_internal_and_external_thread_weights_are_reversed(self):
        for internal in (True,False):
            m=new_doc().modelspace();full,arc=thread_end(m,(0,0),20,17,internal=internal)
            self.assertEqual('0',full.dxf.layer);self.assertEqual('THIN',arc.dxf.layer)
            self.assertAlmostEqual(8.5 if internal else 10,full.dxf.radius)
            self.assertAlmostEqual(10 if internal else 8.5,arc.dxf.radius)
            self.assertEqual(270,arc.dxf.end_angle-arc.dxf.start_angle)

    def test_side_faces_follow_the_hex_end_projection_without_hatch(self):
        for outward in (-1,1):
            m=new_doc().modelspace();end=hex_end(m,(0,0),30)
            hex_head_side(m,0,50,30,12,outward=outward)
            projected=sorted(set(round(x,7) for x,y in end.get_points('xy')))
            side=[e for e in m.query('LINE') if e.dxf.layer=='0']
            self.assertEqual([-15,-7.5,7.5,15],projected)
            self.assertEqual([-7.5,7.5],sorted(e.dxf.start.x for e in side))
            self.assertTrue(all(e.dxf.start.y==50 and e.dxf.end.y==50+outward*12 for e in side))
            self.assertFalse(list(m.query('HATCH')))

    def test_invalid_thread_sizes_are_rejected(self):
        with self.assertRaises(ValueError):thread_end(new_doc().modelspace(),(0,0),20,21)


def _roundtrip(doc):
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)/"fastener.dxf";doc.saveas(path)
        return ezdxf.readfile(path)


def _codes(msp):
    return {i["code"] for i in audit_fasteners(msp)}


class FastenerStructureAudit(unittest.TestCase):
    """Association survives save/reopen; deliberate corruption is detected."""

    def test_thread_end_roundtrip_is_clean_for_internal_and_external(self):
        for internal in (True,False):
            doc=new_doc();m=doc.modelspace()
            thread_end(m,(0,0),20,17,internal=internal)
            self.assertEqual(_codes(_roundtrip(doc).modelspace()),set())

    def test_hex_side_roundtrip_is_clean_for_both_outward(self):
        for outward in (-1,1):
            doc=new_doc();m=doc.modelspace()
            hex_head_side(m,0,50,30,12,outward=outward)
            self.assertEqual(_codes(_roundtrip(doc).modelspace()),set())

    def test_deleted_thread_crest_is_reported(self):
        doc=new_doc();m=doc.modelspace()
        thread_end(m,(0,0),20,17)
        reopened=_roundtrip(doc).modelspace()
        crest=next(e for e in reopened if annotation_data(e).get("role")=="crest")
        reopened.delete_entity(crest)
        self.assertIn("THREAD_MEMBER_MISSING",_codes(reopened))

    def test_deleted_thread_root_is_reported(self):
        doc=new_doc();m=doc.modelspace()
        thread_end(m,(0,0),20,17)
        reopened=_roundtrip(doc).modelspace()
        root=next(e for e in reopened if annotation_data(e).get("role")=="root")
        reopened.delete_entity(root)
        self.assertIn("THREAD_MEMBER_MISSING",_codes(reopened))

    def test_swapped_thread_weights_are_reported(self):
        for internal in (True,False):
            doc=new_doc();m=doc.modelspace()
            thread_end(m,(0,0),20,17,internal=internal)
            reopened=_roundtrip(doc).modelspace()
            crest=next(e for e in reopened if annotation_data(e).get("role")=="crest")
            root=next(e for e in reopened if annotation_data(e).get("role")=="root")
            crest.dxf.layer="THIN";root.dxf.layer="0"
            self.assertIn("THREAD_WEIGHT",_codes(reopened))

    def test_changed_thread_radius_is_reported(self):
        doc=new_doc();m=doc.modelspace()
        thread_end(m,(0,0),20,17)
        reopened=_roundtrip(doc).modelspace()
        crest=next(e for e in reopened if annotation_data(e).get("role")=="crest")
        crest.dxf.radius=crest.dxf.radius+1.0
        self.assertIn("THREAD_RADIUS",_codes(reopened))

    def test_offset_thread_centres_are_reported(self):
        doc=new_doc();m=doc.modelspace()
        thread_end(m,(0,0),20,17)
        reopened=_roundtrip(doc).modelspace()
        crest=next(e for e in reopened if annotation_data(e).get("role")=="crest")
        crest.dxf.center=(1.0,0.0,0.0)
        self.assertIn("THREAD_CENTER_OFFSET",_codes(reopened))

    def test_shrunk_thread_arc_span_is_reported(self):
        doc=new_doc();m=doc.modelspace()
        thread_end(m,(0,0),20,17)
        reopened=_roundtrip(doc).modelspace()
        root=next(e for e in reopened if annotation_data(e).get("role")=="root")
        root.dxf.end_angle=180
        self.assertIn("THREAD_ARC_SPAN",_codes(reopened))

    def test_thread_crest_wrong_entity_type_is_reported(self):
        m=new_doc().modelspace()
        root=m.add_arc((0,0),8.5,30,300,dxfattribs={"layer":"THIN"})
        wrong=m.add_arc((0,0),10,30,300,dxfattribs={"layer":"0"})
        from drawing_checks import mark_annotation
        mark_annotation(wrong,"thread_end",role="crest",group="g",sibling=root.dxf.handle,
                        internal=False,major=20,minor=17)
        mark_annotation(root,"thread_end",role="root",group="g",sibling=wrong.dxf.handle,
                        internal=False,major=20,minor=17)
        self.assertEqual(_codes(m),{"THREAD_ROLE"})

    def test_deleted_hex_face_edge_is_reported(self):
        doc=new_doc();m=doc.modelspace()
        hex_head_side(m,0,50,30,12)
        reopened=_roundtrip(doc).modelspace()
        faces=[e for e in reopened if annotation_data(e).get("role")=="face"]
        self.assertEqual(len(faces),2)
        reopened.delete_entity(faces[0])
        self.assertIn("HEX_FACE_MISSING",_codes(reopened))

    def test_deleted_hex_boundary_is_reported(self):
        doc=new_doc();m=doc.modelspace()
        hex_head_side(m,0,50,30,12)
        reopened=_roundtrip(doc).modelspace()
        boundary=next(e for e in reopened if annotation_data(e).get("role")=="boundary")
        reopened.delete_entity(boundary)
        self.assertIn("HEX_CONTOUR_MISSING",_codes(reopened))

    def test_open_hex_boundary_is_reported(self):
        doc=new_doc();m=doc.modelspace()
        hex_head_side(m,0,50,30,12)
        reopened=_roundtrip(doc).modelspace()
        boundary=next(e for e in reopened if annotation_data(e).get("role")=="boundary")
        boundary.closed=False
        self.assertIn("HEX_CONTOUR",_codes(reopened))

    def test_moved_hex_face_edge_is_reported(self):
        for outward in (-1,1):
            doc=new_doc();m=doc.modelspace()
            hex_head_side(m,0,50,30,12,outward=outward)
            reopened=_roundtrip(doc).modelspace()
            face=next(e for e in reopened if annotation_data(e).get("role")=="face")
            face.dxf.start=(face.dxf.start.x+2.0,face.dxf.start.y)
            face.dxf.end=(face.dxf.end.x+2.0,face.dxf.end.y)
            self.assertIn("HEX_FACE",_codes(reopened))

    def test_legacy_unassociated_mark_is_review_not_guessed(self):
        m=new_doc().modelspace()
        circle=m.add_circle((0,0),10)
        from drawing_checks import mark_annotation
        mark_annotation(circle,"thread_end",internal=False,major=20,minor=17)
        issues=audit_fasteners(m)
        self.assertEqual([i["code"] for i in issues],["THREAD_GROUP_REVIEW"])
        self.assertEqual(issues[0]["severity"],"review")

    def test_foreign_unmarked_dxf_is_not_interpreted(self):
        m=new_doc().modelspace()
        m.add_circle((0,0),10);m.add_arc((0,0),8,30,300);m.add_line((0,0),(5,0))
        self.assertEqual(audit_fasteners(m),[])


class FastenerDefectRegression(unittest.TestCase):
    """Regression for defects found by independent review, not worker tests."""

    def test_effective_lineweight_override_is_reported(self):
        for internal in (True,False):
            doc=new_doc();m=doc.modelspace()
            thread_end(m,(0,0),20,17,internal=internal)
            reopened=_roundtrip(doc).modelspace()
            root=next(e for e in reopened if annotation_data(e).get("role")=="root")
            root.dxf.lineweight=50
            self.assertIn("THREAD_WEIGHT",_codes(reopened))
            doc=new_doc();m=doc.modelspace()
            thread_end(m,(0,0),20,17,internal=internal)
            reopened=_roundtrip(doc).modelspace()
            crest=next(e for e in reopened if annotation_data(e).get("role")=="crest")
            crest.dxf.lineweight=25
            self.assertIn("THREAD_WEIGHT",_codes(reopened))

    def test_layer_lineweight_change_is_reported(self):
        doc=new_doc();m=doc.modelspace()
        thread_end(m,(0,0),20,17)
        reopened=_roundtrip(doc).modelspace()
        reopened.doc.layers.get("THIN").dxf.lineweight=50
        self.assertIn("THREAD_WEIGHT",_codes(reopened))

    def test_wrapped_thread_arc_span_is_accepted(self):
        doc=new_doc();m=doc.modelspace()
        thread_end(m,(0,0),20,17)
        reopened=_roundtrip(doc).modelspace()
        root=next(e for e in reopened if annotation_data(e).get("role")=="root")
        root.dxf.start_angle=300;root.dxf.end_angle=210
        self.assertEqual(_codes(reopened),set())

    def test_thread_root_replaced_by_circle_reports_role_without_crash(self):
        m=new_doc().modelspace()
        full,arc=thread_end(m,(0,0),20,17)
        data=annotation_data(arc);center=arc.dxf.center;radius=arc.dxf.radius
        m.delete_entity(arc)
        substitute=m.add_circle(center,radius,dxfattribs={"layer":"THIN"})
        mark_annotation(substitute,**data)
        self.assertIn("THREAD_ROLE",_codes(m))

    def test_broken_thread_sibling_reference_is_reported(self):
        doc=new_doc();m=doc.modelspace()
        thread_end(m,(0,0),20,17)
        reopened=_roundtrip(doc).modelspace()
        root=next(e for e in reopened if annotation_data(e).get("role")=="root")
        data=annotation_data(root);data["sibling"]="BAD0"
        mark_annotation(root,**data)
        self.assertIn("THREAD_SIBLING",_codes(reopened))

    def test_duplicate_thread_role_is_reported_not_overwritten(self):
        m=new_doc().modelspace()
        full,arc=thread_end(m,(0,0),20,17)
        extra=m.add_circle((0,0),10)
        mark_annotation(extra,"thread_end",role="crest",group=full.dxf.handle,
                        sibling=arc.dxf.handle,internal=False,major=20,minor=17)
        self.assertIn("THREAD_DUPLICATE_ROLE",_codes(m))

    def test_changed_thread_radius_reported_once(self):
        doc=new_doc();m=doc.modelspace()
        thread_end(m,(0,0),20,17)
        reopened=_roundtrip(doc).modelspace()
        crest=next(e for e in reopened if annotation_data(e).get("role")=="crest")
        crest.dxf.radius=crest.dxf.radius+1.0
        codes=[i["code"] for i in audit_fasteners(reopened)]
        self.assertEqual(codes.count("THREAD_RADIUS"),1)

    def test_nonfinite_and_nonpositive_fastener_sizes_are_rejected(self):
        import math
        m=new_doc().modelspace()
        for bad in (float("inf"),float("nan"),0,-1):
            with self.assertRaises(ValueError):thread_end(m,(0,0),bad,17)
            with self.assertRaises(ValueError):thread_end(m,(0,0),20,bad)
            with self.assertRaises(ValueError):hex_head_side(m,0,50,bad,12)
            with self.assertRaises(ValueError):hex_head_side(m,0,50,30,bad)
            with self.assertRaises(ValueError):hex_end(m,(0,0),bad)

    def test_bowtie_hex_boundary_is_reported(self):
        doc=new_doc();m=doc.modelspace()
        hex_head_side(m,0,50,30,12)
        reopened=_roundtrip(doc).modelspace()
        boundary=next(e for e in reopened if annotation_data(e).get("role")=="boundary")
        pts=list(boundary.get_points("xy"))
        boundary.set_points([pts[0],pts[2],pts[1],pts[3]],format="xy")
        self.assertIn("HEX_CONTOUR",_codes(reopened))

    def test_hex_face_checked_against_boundary_projection_not_own_metadata(self):
        doc=new_doc();m=doc.modelspace()
        hex_head_side(m,0,50,30,12)
        reopened=_roundtrip(doc).modelspace()
        face=next(e for e in reopened if annotation_data(e).get("role")=="face")
        data=annotation_data(face)
        face.dxf.start=(face.dxf.start.x+2.0,face.dxf.start.y)
        face.dxf.end=(face.dxf.end.x+2.0,face.dxf.end.y)
        data["x"]=face.dxf.start.x
        mark_annotation(face,**data)
        self.assertIn("HEX_FACE",_codes(reopened))


if __name__=='__main__':unittest.main()
