"""Offline part-library index/query: retrieval, provenance, status boundaries."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import part_library as pl  # noqa: E402

CATALOG = pl.load_catalog()
SIX = {"bolt", "nut", "washer", "bearing", "key", "spacer"}


def rec(value):
    return {"value": value, "source": {"kind": "user", "statement": "synthetic test input"}}


class CatalogIntegrity(unittest.TestCase):
    def test_six_categories_present_and_lookup(self):
        ids = {c["id"] for c in CATALOG["categories"]}
        self.assertEqual(ids, SIX)
        for cid in SIX:
            self.assertIsNotNone(pl.find_category(CATALOG, cid))

    def test_list_is_compact_id_name_status(self):
        rows = pl.list_categories(CATALOG)
        self.assertEqual([r["id"] for r in rows],
                         ["bolt", "nut", "washer", "bearing", "key", "spacer"])
        for r in rows:
            self.assertIn("name_zh", r)
            self.assertIn("status", r)

    def test_every_category_has_sources_and_status(self):
        for c in CATALOG["categories"]:
            self.assertIn("standards", c)
            self.assertIn("github", c)
            self.assertIn("drawing", c)
            self.assertIn("parameters", c)
            impl = c["implementation"]
            self.assertIn("formal_available", impl)
            self.assertIn("data_status", impl)
            self.assertIn("formal_reason", impl)
            self.assertIs(impl["formal_available"], False)

    def test_parameter_names_are_unique_within_category(self):
        for c in CATALOG["categories"]:
            names = ([p["name"] for p in c["parameters"]["required"]]
                     + [p["name"] for p in c["parameters"]["conditional"]]
                     + [p["name"] for p in c["parameters"]["optional"]])
            self.assertEqual(len(names), len(set(names)), c["id"])

    def test_all_standards_have_traceable_url(self):
        for c in CATALOG["categories"]:
            for s in c["standards"]:
                self.assertTrue(s.get("url"), s.get("id"))


class SearchBehavior(unittest.TestCase):
    def test_chinese_and_english_aliases_case_insensitive(self):
        self.assertIn("bolt", {m["id"] for m in pl.search(CATALOG, "六角头螺栓")})
        self.assertIn("nut", {m["id"] for m in pl.search(CATALOG, "HEX NUT")})
        self.assertIn("washer", {m["id"] for m in pl.search(CATALOG, "平垫圈")})
        self.assertIn("bearing", {m["id"] for m in pl.search(CATALOG, "圆锥滚子轴承")})
        self.assertIn("key", {m["id"] for m in pl.search(CATALOG, "flat key")})
        self.assertIn("spacer", {m["id"] for m in pl.search(CATALOG, "Spacer")})

    def test_unknown_returns_no_match_not_approximation(self):
        self.assertEqual(pl.search(CATALOG, "齿轮"), [])
        self.assertEqual(pl.search(CATALOG, "gearrr"), [])
        self.assertEqual(pl.search(CATALOG, "xyz-not-a-part"), [])


class CheckBehavior(unittest.TestCase):
    def test_missing_required_reported_once(self):
        report = pl.check(CATALOG, "bolt", {})
        self.assertEqual([m["name"] for m in report["missing"]], ["type", "specification"])
        self.assertEqual(report["status"], "incomplete")

    def test_known_parameters_are_not_reported_missing(self):
        params = {"type": rec("六角头"), "specification": rec("M12×60")}
        report = pl.check(CATALOG, "bolt", params)
        self.assertEqual([m["name"] for m in report["missing"]], [])

    def test_conditional_reported_pending_when_unknown(self):
        params = {"type": rec("六角头"), "specification": rec("M12×60")}
        report = pl.check(CATALOG, "bolt", params)
        pending = {p["name"] for p in report["conditional_pending"]}
        self.assertEqual(pending, {"pitch", "thread_length"})
        # optional are never flagged
        for m in report["missing"] + report["conditional_pending"]:
            self.assertNotIn(m["name"], {"property_class", "material", "surface"})

    def test_conditional_trigger_activates_to_missing(self):
        params = {"type": rec("平垫圈A级"), "nominal_diameter": rec("M12"),
                  "view_spec": rec(["section"])}
        report = pl.check(CATALOG, "washer", params)
        missing = {m["name"] for m in report["missing"]}
        pending = {p["name"] for p in report["conditional_pending"]}
        self.assertIn("thickness", missing)          # view given -> required
        self.assertIn("series", pending)             # still unknown
        # no view spec -> thickness pending, not silently absent
        report2 = pl.check(CATALOG, "washer",
                           {"type": rec("平垫圈A级"), "nominal_diameter": rec("M12")})
        self.assertIn("thickness", {p["name"] for p in report2["conditional_pending"]})

    def test_conditional_triggers_on_value_not_field_presence(self):
        base = {"type": rec("平垫圈A级 GB/T 97.1-2002"),
                "nominal_diameter": rec("M12"), "series": rec("已指定")}
        end = pl.check(CATALOG, "washer", dict(base, view_spec=rec("end")))
        self.assertNotIn("thickness", {m["name"] for m in end["missing"]})
        self.assertNotIn("thickness", {p["name"] for p in end["conditional_pending"]})
        side = pl.check(CATALOG, "washer", dict(base, view_spec=rec("side")))
        self.assertIn("thickness", {m["name"] for m in side["missing"]})
        unknown = pl.check(CATALOG, "washer", base)
        self.assertIn("thickness", {p["name"] for p in unknown["conditional_pending"]})

    def test_source_only_record_is_missing(self):
        params = {"type": {"source": {"kind": "user", "statement": "no value"}},
                  "nominal_diameter": rec("M12"), "series": rec("已指定"),
                  "view_spec": rec("end")}
        report = pl.check(CATALOG, "washer", params)
        self.assertIn("type", {m["name"] for m in report["missing"]})

    def test_boolean_condition_explicit_false_stops_asking(self):
        bolt = {"type": rec("六角头 GB/T 5782"), "specification": rec("M12×60")}
        # 明确不需要螺纹终止线 -> 不追问，不当作 pending
        no_term = pl.check(CATALOG, "bolt", dict(bolt, thread_termination=rec(False)))
        pending = {p["name"] for p in no_term["conditional_pending"]}
        self.assertNotIn("thread_length", pending)
        self.assertNotIn("thread_length", {m["name"] for m in no_term["missing"]})
        # 明确需要 -> thread_length 进入 missing
        term = pl.check(CATALOG, "bolt", dict(bolt, thread_termination=rec(True)))
        self.assertIn("thread_length", {m["name"] for m in term["missing"]})

    def test_enum_condition_fine_requires_pitch_coarse_does_not(self):
        bolt = {"type": rec("六角头 GB/T 5782"), "specification": rec("M12×60")}
        fine = pl.check(CATALOG, "bolt", dict(bolt, thread_form=rec("fine")))
        self.assertIn("pitch", {m["name"] for m in fine["missing"]})
        coarse = pl.check(CATALOG, "bolt", dict(bolt, thread_form=rec("coarse")))
        self.assertNotIn("pitch", {p["name"] for p in coarse["conditional_pending"]})
        self.assertNotIn("pitch", {m["name"] for m in coarse["missing"]})

    def test_unknown_condition_value_is_pending_not_false(self):
        bolt = {"type": rec("六角头 GB/T 5782"), "specification": rec("M12×60"),
                "thread_form": rec("extra_fine")}
        report = pl.check(CATALOG, "bolt", bolt)
        self.assertIn("pitch", {p["name"] for p in report["conditional_pending"]})

    def test_zero_is_present_but_reported_invalid(self):
        params = {"inner_diameter": rec(0), "outer_diameter": rec(20),
                  "length": rec(10), "interface": rec("轴肩")}
        report = pl.check(CATALOG, "spacer", params)
        self.assertNotIn("inner_diameter", [m["name"] for m in report["missing"]])
        self.assertEqual([z["name"] for z in report["invalid_zero"]], ["inner_diameter"])

    def test_none_and_empty_are_missing(self):
        for bad in (None, "", [], {}):
            params = {"inner_diameter": rec(bad), "outer_diameter": rec(20),
                      "length": rec(10), "interface": rec("轴肩")}
            report = pl.check(CATALOG, "spacer", params)
            self.assertIn("inner_diameter", [m["name"] for m in report["missing"]])

    def test_check_does_not_mutate_input(self):
        params = {"type": rec("六角头"), "specification": rec("M12×60")}
        before = copy.deepcopy(params)
        pl.check(CATALOG, "bolt", params)
        self.assertEqual(params, before)

    def test_check_always_flags_formal_unavailable(self):
        # Even a complete parameter set cannot claim a formal drawing.
        params = {"type": rec("六角头"), "specification": rec("M12×60"),
                  "pitch": rec(1.75), "thread_length": rec(30)}
        report = pl.check(CATALOG, "bolt", params)
        self.assertIs(report["implementation"]["formal_available"], False)
        self.assertEqual(report["implementation"]["data_status"], "unverified")
        self.assertIn("note", report)

    def test_formal_flag_cannot_promote_unverified_data(self):
        altered = copy.deepcopy(CATALOG)
        cat = pl.find_category(altered, "washer")
        cat["implementation"]["formal_available"] = True
        params = {"type": rec("平垫圈A级"), "nominal_diameter": rec("M12"),
                  "series": rec("已指定"), "view_spec": rec("end")}
        report = pl.check(altered, "washer", params)
        self.assertIs(report["implementation"]["formal_available"], False)
        self.assertEqual(report["implementation"]["data_status"], "unverified")

    def test_unknown_id_returns_none(self):
        self.assertIsNone(pl.check(CATALOG, "nope", {}))

    def test_spacer_has_no_designated_standard_and_does_not_fabricate(self):
        cat = pl.find_category(CATALOG, "spacer")
        self.assertEqual(cat["standards"], [])
        self.assertEqual(cat["implementation"]["data_status"], "no_designated_standard")


class CatalogStatusBoundary(unittest.TestCase):
    def test_product_standards_are_catalog_status_only(self):
        cat = pl.find_category(CATALOG, "bolt")
        product = next(s for s in cat["standards"] if s["id"] == "GB/T 5782-2025")
        self.assertEqual(product["verified"], "catalog_status_only_not_dimension_tables")
        representation = next(s for s in cat["standards"] if s["id"] == "GB/T 4459.1-1995")
        self.assertEqual(representation["kind"], "drawing_representation")

    def test_none_of_the_six_can_formally_draw(self):
        for c in CATALOG["categories"]:
            self.assertIs(c["implementation"]["formal_available"], False, c["id"])

    def test_bearing_is_catalog_status_only_not_full_text(self):
        cat = pl.find_category(CATALOG, "bearing")
        self.assertEqual(cat["drawing"]["representation_status"], "catalog_status_only")


class OfflineNoCadDependency(unittest.TestCase):
    def test_cli_module_never_imports_cad_libraries(self):
        src = Path(pl.__file__).read_text(encoding="utf-8")
        for forbidden in ("import ezdxf", "from ezdxf", "import FreeCAD",
                          "import cadquery", "from cadquery", "import OCP"):
            self.assertNotIn(forbidden, src)


class CliSubprocess(unittest.TestCase):
    SCRIPT = str(ROOT / "scripts" / "part_library.py")

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", self.SCRIPT, *args],
                              capture_output=True, text=True, encoding="utf-8",
                              cwd=str(ROOT), timeout=60)

    def test_list_exit_zero(self):
        proc = self.run_cli("list")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = json.loads(proc.stdout)
        self.assertEqual(len(rows), 6)

    def test_search_hit_and_miss_exit_codes(self):
        hit = self.run_cli("search", "hex bolt")
        self.assertEqual(hit.returncode, 0, hit.stderr)
        self.assertTrue(json.loads(hit.stdout)["found"])
        miss = self.run_cli("search", "齿轮")
        self.assertEqual(miss.returncode, 1)
        self.assertFalse(json.loads(miss.stdout)["found"])

    def test_show_hit_and_miss(self):
        show = self.run_cli("show", "bearing")
        self.assertEqual(show.returncode, 0, show.stderr)
        self.assertEqual(json.loads(show.stdout)["id"], "bearing")
        miss = self.run_cli("show", "gearbox")
        self.assertEqual(miss.returncode, 1)

    def test_check_with_parameters_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "params.json"
            path.write_text(json.dumps({"type": {"value": "六角头", "source": {}},
                                        "specification": {"value": "M12×60", "source": {}}}),
                            encoding="utf-8")
            proc = self.run_cli("check", "bolt", "--parameters", str(path))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(report["missing"], [])
            self.assertEqual({p["name"] for p in report["conditional_pending"]},
                             {"pitch", "thread_length"})

    def test_check_usage_error_exit_code(self):
        proc = self.run_cli("check", "bolt", "--parameters", "no-such-file.json")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
