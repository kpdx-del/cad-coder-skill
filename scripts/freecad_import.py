"""Run inside FreeCADCmd/FreeCAD: modern editable-Draft DXF import."""
from pathlib import Path
import os
import json
import shutil
import FreeCAD as App
import importDXF


def convert(source, destination, staging):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if destination.exists(): raise FileExistsError(destination)
    staging=Path(staging);staging.mkdir(parents=True,exist_ok=True)
    # The Windows C++ reader fails on some non-ASCII source paths.
    # Only the temporary input is renamed; the original is never written.
    temporary=staging/'input.dxf';shutil.copyfile(source,temporary)
    pref=App.ParamGet('User parameter:BaseApp/Preferences/Mod/Draft')
    saved={key:pref.GetBool(key,False) for key in
           ('dxfUseLegacyImporter','dxfShowDialog','dxfImportAsDraft','dxftext','importDxfHatches')}
    doc=None
    try:
        for key,value in {'dxfUseLegacyImporter':False,'dxfShowDialog':False,
                          'dxfImportAsDraft':True,'dxftext':True,'importDxfHatches':True}.items():
            pref.SetBool(key,value)
        doc=importDXF.open(str(temporary))
        if not doc or not doc.Objects: raise RuntimeError('FreeCAD returned an empty document')
        doc.Label=source.stem
        doc.recompute();doc.saveAs(str(destination))
        count=len(doc.Objects);App.closeDocument(doc.Name);doc=None
        doc=App.openDocument(str(destination));doc.recompute()
        if len(doc.Objects)!=count: raise RuntimeError('object count changed after reopening')
        texts=[o for o in doc.Objects if 'Text' in o.PropertiesList]
        dimensions=[o for o in doc.Objects if 'Dimension' in str(type(getattr(o,'Proxy',None)))]
        return {'version':App.Version()[:3],'objects':count,'texts':len(texts),'dimensions':len(dimensions),
                'types':sorted(set(o.TypeId for o in doc.Objects)), 'reopened':True,
                'limitations':['2D import; no 3D feature history inferred','visual review required']}
    finally:
        if doc: App.closeDocument(doc.Name)
        for key,value in saved.items():pref.SetBool(key,value)


if os.environ.get('CAD_JOB_FILE'):
    job=json.loads(Path(os.environ['CAD_JOB_FILE']).read_text(encoding='utf-8'))
    report=convert(job['source'],job['destination'],job['staging'])
    Path(job['report']).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
