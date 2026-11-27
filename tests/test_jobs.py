import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import cad_job
import render_dxf
import ezdxf


class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source=self.root/'图纸.dxf'
        self.doc=ezdxf.new('R2010');self.doc.units=4
        self.doc.styles.new('TEST',dxfattribs={'font':'times.ttf'})
        self.doc.modelspace().add_line((0,0),(30,10))
        self.text=self.doc.modelspace().add_text('H7/f9',dxfattribs={'style':'TEST','height':3.5})
        self.doc.saveas(self.source)
    def tearDown(self):self.tmp.cleanup()

    def test_multi_output_parses_once_and_cache_reuses_verified_outputs(self):
        with patch.object(ezdxf,'readfile',wraps=ezdxf.readfile) as read:
            result=cad_job.render_job(self.source,self.root/'render',['png','pdf'])
            self.assertEqual(1,read.call_count)
        self.assertFalse(result['cache_hit'])
        with patch.object(render_dxf,'render_many',side_effect=AssertionError('must not redraw')):
            cached=cad_job.render_job(self.source,self.root/'render',['png','pdf'])
        self.assertTrue(cached['cache_hit'])
        Path(cached['outputs'][0]).write_bytes(b'corrupted')
        self.assertFalse(cad_job.render_job(self.source,self.root/'render',['png','pdf'])['cache_hit'])

    def test_technical_text_change_invalidates_cache_without_geometry_change(self):
        first=cad_job.render_job(self.source,self.root/'render',['png'])
        self.text.dxf.text='H7/k6';self.doc.saveas(self.source)
        second=cad_job.render_job(self.source,self.root/'render',['png'])
        self.assertFalse(second['cache_hit']);self.assertNotEqual(first['outputs'],second['outputs'])

    def test_invalid_export_format_is_rejected(self):
        with self.assertRaises(ValueError):cad_job.render_job(self.source,self.root/'render',['dwg'])

    def test_freecad_refuses_to_overwrite_existing_file(self):
        dest=self.root/'existing.FCStd';dest.write_bytes(b'original')
        with self.assertRaises(FileExistsError):cad_job.freecad_job(self.source,dest,'unused')
        self.assertEqual(b'original',dest.read_bytes())
