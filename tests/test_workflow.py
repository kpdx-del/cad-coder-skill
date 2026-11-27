"""Behavioral regressions: preflight, Table3-3 attachment relations, fixes."""
import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ezdxf
from drawing_checks import (validate_inputs, assert_ready, audit_drawing,
                            check_dimension_chain, derive_difference, check_section_alignment)
from sketch_helpers import (new_doc, dim_linear, feature_control_frame, datum_symbol,
                           roughness_symbol, audit_annotations)
from typography import add_text, text_width, check_glyphs
from repair_dxf import repair_dxf


def record(value):
    return {"value":value,"source":{"kind":"user","statement":"Explicit synthetic test input"}}


def spec():
    return {"mode":"course","part_type":"shaft","units":"mm","references":["Synthetic fixture"],
            "parameters":{"diameters":record([30]),"axial_dimensions":record([40])}}


def codes(items):
    return {i["code"] for i in items}


class TestPreflight(unittest.TestCase):
    def test_complete_and_no_mutation(self):
        s=spec(); old=copy.deepcopy(s)
        self.assertEqual(assert_ready(s),[])
        self.assertEqual(s,old)

    def test_formal_blocks_but_draft_omits_unknown(self):
        s=spec(); del s["parameters"]["diameters"]
        with self.assertRaisesRegex(ValueError,"diameters"):
            assert_ready(s)
        self.assertEqual(assert_ready(s,formal=False)[0]["severity"],"warning")
        self.assertNotIn("diameters",s["parameters"])

    def test_sources_suggestions_formula_units(self):
        for change,expected in (({"units":"cm"},"UNITS"),({"mode":"?"},"MODE")):
            s=spec(); s.update(change)
            self.assertIn(expected,codes(validate_inputs(s)))
        s=spec(); s["parameters"]["roughness"]={"value":1.6,"source":{"kind":"proposal","reason":"Only a suggestion"}}
        self.assertIn("DESIGN_UNCONFIRMED",codes(validate_inputs(s)))
        s["parameters"]["roughness"]["source"]["confirmed"]=True
        self.assertEqual(validate_inputs(s),[])
        s["parameters"]["calculated"]={"value":3,"source":{"kind":"formula","expression":"a-b","inputs":["absent"]}}
        self.assertIn("FORMULA_INPUT",codes(validate_inputs(s)))

    def test_reference_locator_and_empty_geometry(self):
        s=spec(); s["parameters"]["diameters"]=record([])
        self.assertIn("PARAM_MISSING",codes(validate_inputs(s)))
        s=spec(); s["parameters"]["diameters"]["source"]={"kind":"reference","document":"book"}
        self.assertIn("SOURCE_MISSING",codes(validate_inputs(s)))

    def test_six_types_and_conditional_inputs(self):
        from drawing_checks import PART_REQUIRED
        for part,required in PART_REQUIRED.items():
            s=spec(); s.update(part_type=part,parameters={})
            self.assertEqual({i["entity"] for i in validate_inputs(s) if i["code"]=="PARAM_MISSING"},set(required))
        s=spec(); s["conditions"]={"helical":True,"datum_control":True}
        names={i["entity"] for i in validate_inputs(s) if i["code"]=="PARAM_MISSING"}
        self.assertEqual(names,{"helix_angle","hand","datum_scheme","geometric_tolerances"})

    def test_formula_cycle(self):
        s=spec()
        for a,b in (("a","b"),("b","a")):
            s["parameters"][a]={"value":3,"source":{"kind":"formula","expression":b,"inputs":[b]}}
        self.assertIn("FORMULA_CYCLE",codes(validate_inputs(s)))


class TestChains(unittest.TestCase):
    def test_closed_and_reference_and_conflict(self):
        edges=[dict(start="a",end="b",value=40),dict(start="b",end="c",value=50),
               dict(start="c",end="d",value=35),dict(start="a",end="d",value=125)]
        self.assertIn("CHAIN_CLOSED",codes(check_dimension_chain(edges)))
        edges[-1]["reference"]=True
        self.assertEqual(check_dimension_chain(edges),[])
        edges[-1]["value"]=126
        self.assertIn("CHAIN_CONTRADICTION",codes(check_dimension_chain(edges)))

    def test_open_chain_and_worst_case_limits(self):
        self.assertEqual(check_dimension_chain([dict(start="a",end="b",value=40),
                                               dict(start="a",end="d",value=125)]),[])
        nominal,upper,lower=derive_difference((125,.1,-.1),[(40,.03,-.02),(35,.04,-.01)])
        self.assertEqual(nominal,50)
        self.assertAlmostEqual(upper,.13)
        self.assertAlmostEqual(lower,-.17)


class TestAnnotationRegressions(unittest.TestCase):
    def test_section_direction_parallel_and_wrong(self):
        self.assertEqual(check_section_alignment((0,1),(0,-1)),[])
        self.assertIn("SECTION_ALIGNMENT",codes(check_section_alignment((0,1),(1,0))))
    def test_explicit_inside_outside_and_reversed_vertical(self):
        for angle,p1,p2,location in ((0,(0,0),(12,0),(25,-8)),(90,(0,12),(0,0),(-8,-20))):
            for policy in ("inside","outside"):
                d=new_doc(); dim=dim_linear(d.modelspace(),p1,p2,8,angle=angle,
                                          text_location=location,arrows=policy,upper=0,lower=-.043)
                self.assertEqual(audit_annotations(d.modelspace()),[])
                blk=d.blocks[dim.dimension.dxf.geometry]
                arrows=sorted(blk.query("INSERT"),key=lambda e:(e.dxf.insert.x,e.dxf.insert.y))
                self.assertAlmostEqual(arrows[0].dxf.rotation%360,(angle+(180 if policy=="inside" else 0))%360)
                self.assertAlmostEqual(dim.dimension.get_measurement(),12)

    def test_inside_too_narrow_fails(self):
        with self.assertRaisesRegex(ValueError,"do not fit"):
            dim_linear(new_doc().modelspace(),(0,0),(2,0),8,arrows="inside")

    def test_reversed_end_suppression_tracks_original_endpoint(self):
        d=new_doc(); dim=dim_linear(d.modelspace(),(30,0),(0,0),10,suppress_arrow=1)
        arrows=list(d.blocks[dim.dimension.dxf.geometry].query("INSERT"))
        blank=next(e for e in arrows if e.dxf.name.upper()=="_NONE")
        self.assertEqual(blank.dxf.insert.x,30)
        self.assertEqual(audit_annotations(d.modelspace()),[])

    def test_real_metrics_not_character_count(self):
        d=new_doc(); font=d.styles.get("CAD_TEXT").dxf.font
        self.assertGreater(text_width("WWWW",font),text_width("1111",font))
        with self.assertRaises(FileNotFoundError):
            new_doc(font="missing-cad-font-123.ttf")
        with self.assertRaises(ValueError):
            check_glyphs("汉字",font)

    def test_long_frame_common_and_ordered_datums(self):
        d=new_doc(); m=d.modelspace()
        b=feature_control_frame(m,(0,0),"coaxiality","0.000000125",["A-B","C"],zone="cylinder")
        from ezdxf import bbox
        for e in m.query("TEXT"):
            box=bbox.extents([e])
            self.assertGreaterEqual(box.extmin.x,b[0])
            self.assertLessEqual(box.extmax.x,b[2])
        self.assertTrue(any(t.dxf.text=="φ0.000000125" for t in m.query("TEXT")))
        with self.assertRaises(ValueError):
            feature_control_frame(m,(0,20),"symmetry",.02,["A","B","C","D"])

    def test_table3_3_derived_wrong_and_right(self):
        for target,expected in (((10,5),True),((10,0),False)):
            d=new_doc(); m=d.modelspace(); datum_symbol(m,(0,0),"A")
            feature_control_frame(m,(30,20),"symmetry",.02,"A",target=target,arrow=False,
                                  zone="planes",feature={"kind":"derived","size_line":[(0,0),(20,0)]})
            self.assertEqual("DERIVED_ALIGNMENT" in codes(audit_drawing(m,chains={})),expected)

    def test_vertical_size_extension_to_frame_preserves_values(self):
        d=new_doc(); m=d.modelspace(); datum_symbol(m,(-20,0),"D")
        dim=dim_linear(m,(0,0),(0,14),-10,angle=90,upper=0,lower=-.043,
                       arrows="inside",text_location=(6,-12))
        frame=feature_control_frame(m,(17,-33.5),"symmetry","0.020","D",target=(10,0),arrow=False,
                                    zone="planes",feature={"kind":"derived","size_line":[(10,0),(10,14)]})
        self.assertEqual(dim.dimension.get_measurement(),14)
        self.assertEqual(dim.get("dimtm"),.043)
        self.assertEqual(audit_drawing(m,chains={}),[])
        connection=m.query("LWPOLYLINE")[-1]
        self.assertEqual(tuple(connection.get_points()[0][:2]),(10,0))
        self.assertEqual(tuple(connection.get_points()[-1][:2]),(frame[0],-30))

    def test_table3_3_surface_offset_and_form_no_datum(self):
        d=new_doc(); m=d.modelspace(); datum_symbol(m,(-20,0),"A")
        feature_control_frame(m,(30,20),"roundness",.01,"A",target=(0,0),zone="annulus",
                              feature={"kind":"surface","surface_line":[(0,0),(20,0)],"size_line":[(0,-10),(0,10)]})
        self.assertTrue({"FORM_DATUM","SURFACE_SIZE_CONFLICT"} <= codes(audit_drawing(m,chains={})))

    def test_measurement_directions_not_forced_to_share_leader(self):
        d=new_doc();m=d.modelspace()
        feature_control_frame(m,(30,20),"flatness",.01,target=(10,0),
                              feature={"kind":"surface","surface_line":[(0,0),(20,0)],"measurement_direction":[1,0]})
        self.assertIn("MEASUREMENT_DIRECTION",codes(audit_drawing(m,chains={})))

    def test_zone_prefix_not_part_shape(self):
        d=new_doc(); m=d.modelspace()
        feature_control_frame(m,(0,0),"roundness","φ0.01",zone="annulus")
        self.assertIn("ZONE_PREFIX",codes(audit_drawing(m,chains={})))

    def test_unknown_external_dxf_requires_review(self):
        d=new_doc(); dim_linear(d.modelspace(),(0,0),(30,0),10)
        found=codes(audit_drawing(d.modelspace()))
        self.assertTrue({"CHAIN_REVIEW","SEMANTICS_REVIEW"}<=found)

    def test_roughness_below_bar_no_solid(self):
        d=new_doc(); m=d.modelspace()
        roughness_symbol(m,(0,0),3.2,method="GRIND")
        texts={t.dxf.text:t for t in m.query("TEXT")}
        bar=list(m.query("LWPOLYLINE"))[0].get_points()[-1]
        self.assertLess(texts["Ra 3.2"].dxf.insert.y,bar[1])
        self.assertGreater(texts["GRIND"].dxf.insert.y,bar[1])
        self.assertEqual(len(m.query("SOLID")),0)

    def test_duplicate_text_is_detected(self):
        d=new_doc(); m=d.modelspace()
        add_text(m,"125",(0,0)); add_text(m,"125",(1,1))
        self.assertIn("TEXT_OVERLAP",codes(audit_drawing(m,chains={})))

    def test_internal_gap_away_from_text(self):
        d=new_doc(); dim=dim_linear(d.modelspace(),(0,0),(100,0),10)
        blk=d.blocks[dim.dimension.dxf.geometry]
        line=next(e for e in blk.query("LINE") if abs(e.dxf.start.y+10)<1e-6 and abs(e.dxf.end.y+10)<1e-6)
        end=line.dxf.end; line.dxf.end=(15,-10,0)
        blk.add_line((20,-10),end)
        self.assertTrue(any("gap" in p for p in audit_annotations(d.modelspace())))


class TestRepairAndDemo(unittest.TestCase):
    def test_repair_preserves_source_text_and_values(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"original.dxf"; target=Path(td)/"fixed.dxf"
            d=new_doc(); dim_linear(d.modelspace(),(0,0),(30,0),10,upper=0,lower=-.043)
            d.modelspace().add_text("SOURCE",dxfattribs={"height":3.5})
            d.saveas(source); before=source.read_bytes()
            result=repair_dxf(source,target)
            self.assertEqual(source.read_bytes(),before)
            self.assertTrue(result["changes"])
            new=ezdxf.readfile(target)
            self.assertEqual(new.modelspace().query("DIMENSION")[0].get_measurement(),30)
            with self.assertRaises(ValueError):
                repair_dxf(source,source)
            with self.assertRaises(ValueError):
                repair_dxf(source,target)

    def test_demo_roundtrip_no_reported_errors_and_no_closed_chain(self):
        spec_module=importlib.util.spec_from_file_location("demo",ROOT/"examples"/"engineering_annotations.py")
        demo=importlib.util.module_from_spec(spec_module); spec_module.loader.exec_module(demo)
        d=demo.build()
        self.assertEqual(audit_drawing(d.modelspace(),chains=demo.CHAINS),[])
        self.assertEqual(check_dimension_chain(demo.CHAINS["shaft_axis"]),[])
        # Verify real source/section positions; no independent hard-coded x.
        from drawing_layout import layout_data
        sections=[e for e in d.modelspace() if layout_data(e).get("role")=="section"]
        self.assertEqual(len(sections),2)
        for axis in sections:
            cut=d.entitydb[layout_data(axis)["cut"]]
            self.assertEqual(axis.dxf.start.x,cut.dxf.start.x)
        self.assertFalse(any(t.dxf.text in ("姓名","学号") for t in d.modelspace().query("TEXT")))


if __name__=="__main__":
    unittest.main()
