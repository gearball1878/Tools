"""Atomic, selectable AI integration deltas with an immutable project baseline."""
from copy import deepcopy
import hashlib
import json
from .ecad_connector import AnnotationPreview, AnnotationChange

def fingerprint(package):
    return hashlib.sha256(json.dumps(package.model_dump(mode='json'),sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def integration_preview(package,analysis_id,builtins):
    from .requirements_service import compile_detected_document_analysis
    working=package.model_copy(deep=True)
    compile_detected_document_analysis(working,analysis_id,builtins)
    preview=AnnotationPreview('ai');preview.base_hash=fingerprint(package);preview.analysis_id=analysis_id
    preview.compiled_analysis=working.find_document_analysis(analysis_id).model_copy(deep=True)
    excluded={'document_analyses','source_documents','properties','layout','xpedition','project','property_definitions'}
    for field in type(package).model_fields:
        if field in excluded:continue
        before=getattr(package,field);after=getattr(working,field)
        if isinstance(before,list) and all(hasattr(o,'id') for o in before+after):
            old={o.id:o.model_dump(mode='json') for o in before};new={o.id:o.model_dump(mode='json') for o in after}
            for oid in sorted(old.keys()|new.keys()):
                if old.get(oid)!=new.get(oid):preview.changes.append(AnnotationChange(oid,field+'Object',old.get(oid),new.get(oid),detail='KI-Vorschlag · Quelle und fachlichen Zusammenhang prüfen.'))
        elif hasattr(before,'model_dump') and before.model_dump()!=after.model_dump():
            preview.changes.append(AnnotationChange(package.project.id,field,before.model_dump(mode='json'),after.model_dump(mode='json'),detail='KI-Vorschlag für das Projekt.'))
    preview.warnings.append('Zusammenhängende Objekte gemeinsam auswählen. Fehlende Beziehungspartner verhindern die Übernahme. Erkannte Requirements werden als Detected angelegt.')
    return preview

def apply_integration_preview(package,preview):
    from .models import ArchitecturePackage,CandidateReviewStatus
    if fingerprint(package)!=preview.base_hash:raise ValueError('Der Projektstand wurde geändert. KI-Änderungsvorschau neu erzeugen.')
    payload=package.model_dump(mode='json')
    accepted=set()
    for change in preview.changes:
        if change.status!='ready':raise ValueError('Offene Konflikte zuerst lösen.')
        if change.field.endswith('Object'):
            field=change.field[:-6];items=payload[field]
            payload[field]=[o for o in items if o['id']!=change.object_id]
            if change.after is not None:payload[field].append(deepcopy(change.after));accepted.add(change.object_id)
        else:payload[change.field]=deepcopy(change.after)
    candidate=ArchitecturePackage.model_validate(payload)
    analysis=candidate.find_document_analysis(preview.analysis_id)
    registry={o.id for field in type(candidate).model_fields for o in (getattr(candidate,field) if isinstance(getattr(candidate,field),list) else []) if hasattr(o,'id')}
    for field in type(analysis).model_fields:
        group=getattr(analysis,field)
        compiled=getattr(preview.compiled_analysis,field)
        if isinstance(group,list) and group and hasattr(group[0],'committed_object_id'):
            byid={c.id:c for c in compiled}
            for item in group:
                match=byid.get(item.id)
                if match and match.committed_object_id in registry:
                    item.committed_object_id=match.committed_object_id;item.review_status=CandidateReviewStatus.ACCEPTED
    return ArchitecturePackage.model_validate(candidate.export_dict())
