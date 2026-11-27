"""Regressions from the nine reported screenshots: checks must see geometry."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ezdxf
from sketch_helpers import (new_doc,dim_linear,cutting_marks,section_axes,
                           feature_control_frame,roughness_symbol,audit_annotations)
from typography import add_text,text_rect
from drawing_layout import audit_layout,layout_data,choose_position,group_bounds
from sheet import draw_sheet


def codes(issues):
    return {i["code"] for i in issues}


class TestLayoutRegressions(unittest.TestCase):
    def test_demo_annular_end_chamfer_has_two_silhouettes(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location("chamfer_demo",ROOT/"examples"/"engineering_annotations.py")
        demo=importlib.util.module_from_spec(spec);spec.loader.exec_module(demo)
        d=demo.build()
        outline=next(e for e in d.modelspace().query("LWPOLYLINE")
                     if e.dxf.layer=="0" and len(e)==14)
        vertices=[tuple(p[:2]) for p in outline.get_points()]
        self.assertIn((125,197),vertices)
        self.assertIn((125,223),vertices)
        self.assertIn((127,195),vertices)
        self.assertIn((127,225),vertices)
        self.assertNotIn((125,195),vertices)
        self.assertNotIn((125,225),vertices)
        self.assertTrue(outline.closed)
        self.assertNotIn("WITNESS_OFF_CONTOUR",codes(audit_layout(d.modelspace())))
        diameters=[e for e in d.modelspace().query("DIMENSION") if abs(e.dxf.get("angle",0)-90)<1e-6]
        self.assertTrue(any(abs(e.get_measurement()-30)<1e-6 for e in diameters))

    def test_chamfer_virtual_corner_is_rejected_and_real_corner_connects(self):
        profile=[(0,-15),(0,13),(2,15),(40,15),(40,-15)]
        for top,should_fail in (((0,15),True),((2,15),False)):
            d=new_doc(extension_gap=0);m=d.modelspace()
            contour=m.add_lwpolyline(profile,close=True)
            dim=dim_linear(m,(0,-15),top,20,angle=90,text="%%c<>",witness_geometry=contour)
            self.assertEqual("WITNESS_OFF_CONTOUR" in codes(audit_layout(m)),should_fail)
            self.assertEqual(dim.dimension.get_measurement(),30)
            if not should_fail:
                lines=d.blocks[dim.dimension.dxf.geometry].query("LINE")
                self.assertTrue(any(abs(e.dxf.start.y-15)<1e-8 and abs(e.dxf.end.y-15)<1e-8
                                    and (abs(e.dxf.start.x-2)<1e-8 or abs(e.dxf.end.x-2)<1e-8)
                                    for e in lines))

    def test_real_witness_reference_roundtrip(self):
        d=new_doc(extension_gap=0);m=d.modelspace()
        contour=m.add_lwpolyline([(0,-15),(0,13),(2,15),(40,15),(40,-15)],close=True)
        dim_linear(m,(0,-15),(2,15),20,angle=90,text="%%c<>",witness_geometry=contour)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"witness.dxf";d.saveas(p)
            reopened=ezdxf.readfile(p)
            self.assertNotIn("WITNESS_OFF_CONTOUR",codes(audit_layout(reopened.modelspace())))

    def test_extension_line_touches_contour_when_selected(self):
        d=new_doc(extension_gap=0)
        dim=dim_linear(d.modelspace(),(0,0),(30,0),10)
        block=d.blocks[dim.dimension.dxf.geometry]
        extensions=[e for e in block.query("LINE") if abs(e.dxf.start.x-e.dxf.end.x)<1e-8]
        self.assertEqual(len(extensions),2)
        self.assertTrue(all(abs(e.dxf.start.y)<1e-8 for e in extensions))
        self.assertEqual(audit_annotations(d.modelspace()),[])

    def test_letter_and_chamfer_leader_crossing_is_detected(self):
        d=new_doc();m=d.modelspace()
        label=add_text(m,"C",(10,10))
        r=text_rect(label)
        m.add_leader([(r[0]-4,(r[1]+r[3])/2),(r[2]+4,(r[1]+r[3])/2)])
        self.assertIn("TEXT_LINE_COLLISION",codes(audit_layout(m)))

    def test_horizontal_external_text_above_continuous_tail(self):
        d=new_doc();m=d.modelspace()
        dim=dim_linear(m,(0,0),(8,0),10,upper=0,lower=-.016,text_location=(24,-10))
        text=d.blocks[dim.dimension.dxf.geometry].query("MTEXT")[0]
        self.assertGreaterEqual(text_rect(text)[1],-9.21)
        self.assertEqual(audit_annotations(m),[])
        self.assertNotIn("DIM_TEXT_SIDE",codes(audit_layout(m)))
        self.assertAlmostEqual(dim.dimension.get_measurement(),8)

    def test_vertical_external_text_left_and_two_arrows(self):
        d=new_doc();m=d.modelspace()
        dim=dim_linear(m,(0,0),(0,22),-10,angle=90,upper=0,lower=-.2,
                       text_location=(14,-12),arrows="inside")
        block=d.blocks[dim.dimension.dxf.geometry]
        self.assertEqual(len(block.query("INSERT")),2)
        self.assertTrue(all(e.dxf.name.upper()!="_NONE" for e in block.query("INSERT")))
        self.assertLessEqual(text_rect(block.query("MTEXT")[0])[2],9.21)
        self.assertEqual(audit_annotations(m),[])

    def test_moved_text_wrong_side_is_detected(self):
        d=new_doc();m=d.modelspace()
        dim=dim_linear(m,(0,0),(40,0),10)
        text=d.blocks[dim.dimension.dxf.geometry].query("MTEXT")[0]
        text.translate(0,-10,0)
        self.assertIn("DIM_TEXT_SIDE",codes(audit_layout(m)))

    def test_roughness_and_cutting_cannot_share_stroke(self):
        d=new_doc();m=d.modelspace()
        cutting_marks(m,30,30,"D")
        roughness_symbol(m,(30,51),3.2)
        self.assertIn("ANNOTATION_GROUP_CROSSING",codes(audit_layout(m)))

    def test_candidate_uses_entire_cut_group_and_fails_without_room(self):
        d=new_doc();cut=cutting_marks(d.modelspace(),30,30,"D")
        occupied=[group_bounds(cut)]
        self.assertEqual(choose_position([(28,50),(45,50)],(18,7),occupied),(45,50))
        with self.assertRaisesRegex(ValueError,"No annotation position"):
            choose_position([(28,50)],(18,7),occupied)

    def test_cutting_labels_and_marks_are_mirrored(self):
        d=new_doc();m=d.modelspace();cut=cutting_marks(m,50,70,"D")
        self.assertNotIn("CUT_LABEL_SYMMETRY",codes(audit_layout(m)))
        label=d.entitydb[layout_data(cut)["labels"][0]]
        label.translate(0,2,0)
        self.assertIn("CUT_LABEL_SYMMETRY",codes(audit_layout(m)))

    def test_moving_cutting_stroke_breaks_symmetry(self):
        d=new_doc();m=d.modelspace();cut=cutting_marks(m,50,70,"D")
        other=d.entitydb[layout_data(cut)["marks"][1]]
        other.translate(0,2,0)
        self.assertIn("CUT_MARK_SYMMETRY",codes(audit_layout(m)))

    def test_unexpected_none_arrow_is_detected(self):
        d=new_doc();m=d.modelspace();dim=dim_linear(m,(0,0),(30,0),10)
        block=d.blocks[dim.dimension.dxf.geometry]
        d.blocks.new("_NONE")
        block.query("INSERT")[0].dxf.name="_NONE"
        self.assertTrue(any("missing or unexpected arrow" in p for p in audit_annotations(m)))

    def test_linked_section_collinear_and_caption_centred(self):
        d=new_doc();m=d.modelspace();cut=cutting_marks(m,80,140,"D")
        self.assertEqual(section_axes(m,cut,40,12.5,"D"),80)
        axis=next(e for e in m if layout_data(e).get("role")=="section")
        self.assertNotIn("SECTION_COLLINEARITY",codes(audit_layout(m)))
        axis.translate(3,0,0)
        self.assertIn("SECTION_COLLINEARITY",codes(audit_layout(m)))
        self.assertIn("SECTION_CAPTION_CENTER",codes(audit_layout(m)))

    def test_title_block_blocks_entire_frame_and_leader(self):
        d=new_doc();m=d.modelspace();draw_sheet(m)
        feature_control_frame(m,(250,59),"flatness",.01)
        m.add_line((240,80),(245,40),dxfattribs={"layer":"DIM"})
        self.assertIn("TITLE_BLOCK_INTRUSION",codes(audit_layout(m)))

    def test_foreign_line_through_frame(self):
        d=new_doc();m=d.modelspace()
        frame=feature_control_frame(m,(20,20),"flatness",.01)
        m.add_line((10,23.5),(frame[2]+10,23.5),dxfattribs={"layer":"DIM"})
        self.assertIn("FRAME_LINE_COLLISION",codes(audit_layout(m)))

    def test_ordinary_frame_attachment_is_not_false_collision(self):
        d=new_doc();m=d.modelspace()
        feature_control_frame(m,(30,20),"flatness",.01,target=(10,0))
        self.assertEqual(audit_layout(m),[])

    def test_stacked_text_width_is_measured_and_persisted(self):
        d=new_doc();m=d.modelspace()
        dim=dim_linear(m,(0,0),(40,0),10,upper=.042,lower=.026)
        text=d.blocks[dim.dimension.dxf.geometry].query("MTEXT")[0]
        self.assertGreater(text.dxf.width,10)
        self.assertLess(text.dxf.width,30)
        self.assertGreaterEqual(text_rect(text)[1],-9.21)

    def test_link_metadata_and_geometry_survive_roundtrip(self):
        d=new_doc();m=d.modelspace();cut=cutting_marks(m,70,140,"C")
        section_axes(m,cut,40,15,"C")
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"linked.dxf";d.saveas(p); reopened=ezdxf.readfile(p)
            self.assertEqual(audit_layout(reopened.modelspace()),[])


if __name__=="__main__":
    unittest.main()
