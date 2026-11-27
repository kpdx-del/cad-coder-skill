"""Small JSON CLI for local CAD capabilities and cached multi-format rendering."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def doctor(freecad=None):
    sw=[]
    if sys.platform=='win32':
        import winreg
        for progid in ('SldWorks.Application','SldWorks.Application.31'):
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,progid+r'\CLSID') as key:
                    sw.append({'progid':progid,'clsid':winreg.QueryValue(key,None)})
            except FileNotFoundError: pass
    return {'freecad':str(Path(freecad).resolve()) if freecad and Path(freecad).is_file() else None,
            'solidworks_registered':sw,'solidworks_verified':False,
            'note':'Registration is not an API connection or license check.'}


def render_job(source,destination,formats,paper=None,scale=1.,font=None,margin=10.):
    from render_dxf import render_many
    from typography import resolve_font
    import ezdxf
    import matplotlib
    source=Path(source).resolve();destination=Path(destination).resolve()
    if len(set(formats))!=len(formats) or not set(formats)<={'png','pdf','svg'}:
        raise ValueError('formats must be unique png/pdf/svg values')
    doc=ezdxf.readfile(source)
    fonts=sorted({font} if font else {s.dxf.font for s in doc.styles if s.dxf.name in
                 {e.dxf.style for e in ezdxf.disassemble.recursive_decompose(doc.modelspace()) if e.dxftype() in ('TEXT','MTEXT')}})
    key={'source':digest(source),'formats':formats,'paper':paper,'scale':scale,'font':font,'margin':margin,
         'fonts':[(str(resolve_font(f)),digest(resolve_font(f))) for f in fonts],
         'renderer':digest(Path(__file__).with_name('render_dxf.py')),
         'typography':digest(Path(__file__).with_name('typography.py')),'ezdxf':ezdxf.__version__,
         'matplotlib':matplotlib.__version__}
    fingerprint=hashlib.sha256(json.dumps(key,sort_keys=True).encode()).hexdigest()
    folder=destination/fingerprint;manifest=folder/'manifest.json'
    if manifest.exists():
        cached=json.loads(manifest.read_text(encoding='utf-8'))
        if all(Path(p).is_file() and digest(p)==h for p,h in cached['outputs'].items()):
            return dict(status='ok',cache_hit=True,outputs=list(cached['outputs']))
    folder.mkdir(parents=True,exist_ok=True)
    outputs=[folder/('drawing.'+ext) for ext in formats]
    render_many(source,outputs,paper=paper,scale=scale,font=font,margin=margin,doc=doc)
    manifest.write_text(json.dumps({'key':key,'outputs':{str(p):digest(p) for p in outputs}},indent=2),encoding='utf-8')
    return dict(status='ok',cache_hit=False,outputs=[str(p) for p in outputs])


def freecad_job(source,destination,executable):
    import tempfile
    destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cad_fc_',dir=destination.parent) as temporary:
        root=Path(temporary);home=root/'home';home.mkdir()
        spec=root/'job.json';report=root/'report.json'
        spec.write_text(json.dumps({'source':str(Path(source).resolve()),'destination':str(destination),
                                   'staging':str(root/'stage'),'report':str(report)}),encoding='utf-8')
        env=os.environ.copy();env['FREECAD_USER_HOME']=str(home);env['CAD_JOB_FILE']=str(spec)
        env.pop('PYTHONHOME',None);env.pop('PYTHONPATH',None)
        run=subprocess.run([executable,'-u',str(root/'user.cfg'),'-s',str(root/'system.cfg'),
                            str(Path(__file__).with_name('freecad_import.py'))],env=env,
                           stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        log=destination.with_suffix('.import.log');log.write_bytes(run.stdout)
        if run.returncode or not report.exists():
            raise RuntimeError('FreeCAD did not produce a verified report; see '+str(log))
        data=json.loads(report.read_text(encoding='utf-8'))
        destination.with_suffix('.inspection.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        return dict(status='needs_visual_review',outputs=[str(destination)],inspection=data,log=str(log))


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    d=sub.add_parser('doctor');d.add_argument('--freecad')
    r=sub.add_parser('render');r.add_argument('source');r.add_argument('destination');r.add_argument('--formats',nargs='+',default=['png','pdf'])
    r.add_argument('--paper',choices=['A3','A4']);r.add_argument('--scale',type=float,default=1.);r.add_argument('--font');r.add_argument('--margin',type=float,default=10.)
    f=sub.add_parser('freecad');f.add_argument('source');f.add_argument('destination');f.add_argument('--executable',required=True)
    args=vars(p.parse_args());command=args.pop('command');started=time.perf_counter()
    try:
        result=doctor(**args) if command=='doctor' else render_job(**args) if command=='render' else freecad_job(**args)
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as exc:
        print(json.dumps({'status':'error','error':str(exc)},ensure_ascii=False));return 1
    result['elapsed_seconds']=round(time.perf_counter()-started,4)
    print(json.dumps(result,ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
