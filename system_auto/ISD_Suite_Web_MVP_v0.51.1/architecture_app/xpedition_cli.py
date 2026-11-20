"""Windows workstation bridge. Project payloads always use the ISD SPOT model."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from .models import ArchitecturePackage
from .xpedition_connector import XpeditionConnector
from .xpedition_exchange import compare, binding


def read_spot(path):
    return ArchitecturePackage.model_validate_json(Path(path).read_text(encoding='utf-8-sig'))


def preview_document(preview):
    return {'reviewFormat':'isd.xpedition.review.v1','direction':preview.direction,
        'changes':[asdict(c) for c in preview.changes], 'warnings':preview.warnings,
        'context':preview.xpedition_context,
        'decisions':{str(i):'apply' if c.status=='ready' else 'open' if c.status=='conflict' else 'skip' for i,c in enumerate(preview.changes)}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['diagnose','link','create','preview','apply','read','roundtrip'])
    parser.add_argument('--spot',type=Path)
    parser.add_argument('--project',default='')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--review',type=Path)
    parser.add_argument('--parent',default='');parser.add_argument('--name',default='')
    parser.add_argument('--library',default='');parser.add_argument('--template',default='');parser.add_argument('--server',default='')
    parser.add_argument('--progid',default='ViewDraw.Application')
    args=parser.parse_args(argv)
    protected=[p for p in (args.spot,args.review,Path(args.project) if args.project else None) if p is not None]
    if any(args.output.resolve()==p.resolve() for p in protected):parser.error('--output darf keine Eingabe oder native Projektdatei überschreiben')
    from .xpedition_com import XpeditionCOM
    connector=XpeditionConnector(XpeditionCOM(args.progid))
    try:
        if args.command=='diagnose':
            result=connector.backend.diagnose(args.project)
        else:
            if not args.spot:parser.error('--spot erforderlich')
            package=read_spot(args.spot)
            if args.command=='link':
                updated=connector.link_project(package,args.project)
                result=updated.model_dump(mode='json',by_alias=True)
            elif args.command=='create':
                updated=connector.create_project(package,args.parent,args.name,args.library,args.template,args.server)
                result=updated.model_dump(mode='json',by_alias=True)
            elif args.command=='preview':
                preview=connector.forward_project_preview(package,args.project)
                result=preview_document(preview)
            elif args.command=='apply':
                if not args.review:parser.error('--review erforderlich')
                saved=json.loads(args.review.read_text(encoding='utf-8-sig'))
                if saved.get('reviewFormat')!='isd.xpedition.review.v1':raise ValueError('Ungültiges Prüfdokument')
                # Recompute from COM; only decisions from disk are trusted, never edited change payloads.
                preview=connector.forward_project_preview(package,saved['context']['project_path'])
                if preview.xpedition_context!=saved['context'] or [asdict(c) for c in preview.changes]!=saved['changes']:
                    raise ValueError('Prüfstand geändert. Neue Vorschau erzeugen.')
                decisions={int(k):v for k,v in saved['decisions'].items()}
                # Pure resolver avoids requiring a GUI on the bridge workstation.
                selected=[]
                for i,c in enumerate(preview.changes):
                    decision=decisions.get(i,'skip')
                    if decision=='open':raise ValueError('Offenen Konflikt im Prüfdokument lösen.')
                    if decision=='apply':
                        if c.status=='unsupported':raise ValueError('Nicht unterstützte Änderung ausgewählt.')
                        c.status='ready';selected.append(c)
                    elif decision!='skip':raise ValueError('Ungültige Prüfentscheidung')
                preview.changes=selected
                updated=connector.apply_forward(package,preview)
                result=updated.model_dump(mode='json',by_alias=True)
            elif args.command=='read':
                result=connector.backend.read_project(package,args.project or binding(package).get('projectPath','')).model_dump(mode='json',by_alias=True)
            else:
                observed=connector.backend.read_project(package,args.project or binding(package).get('projectPath',''))
                preview=compare(package,observed,'forward',baseline={})
                result={'nativeTest':True,'projectPath':binding(observed).get('projectPath'),
                    'ok':not preview.changes,'differences':[asdict(c) for c in preview.changes],
                    'note':'Lesender Vergleich. Vorher in Xpedition speichern, schließen und erneut öffnen. Keine automatische Neuverdrahtung oder CM-Prüfung.'}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(str(args.output.resolve()))
        return 0 if result.get('ok',True) else 1
    except Exception as error:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps({'ok':False,'error':str(error)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(str(error));return 1


if __name__=='__main__':raise SystemExit(main())
