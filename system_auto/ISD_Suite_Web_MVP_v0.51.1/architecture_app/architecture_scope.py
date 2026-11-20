"""Enforced requirement and target scope for architecture synthesis/review."""
import hashlib
import json

TARGET_FIELDS={'system':{'system_elements'},'hardware':{'domains','elements','interfaces'},
               'mechanical':{'mechanical_elements'},'software':{'software_elements'}}


def selected_requirements(package,identifiers):
    identifiers=list(dict.fromkeys(identifiers))
    lookup={r.id:r for r in package.requirements}
    if not identifiers:raise ValueError('Mindestens ein Requirement auswählen')
    if set(identifiers)-lookup.keys():raise ValueError('Ausgewähltes Requirement existiert nicht mehr')
    if any(lookup[i].maturity.value in {'Rejected','Obsolete'} for i in identifiers):
        raise ValueError('Abgelehnte oder obsolete Requirements nicht zur Umsetzung auswählen')
    if any(lookup[i].customer_decision=='Rejected' for i in identifiers):raise ValueError('Abgelehnte Kundenanforderung nicht zur Umsetzung auswählen')
    return [lookup[i] for i in identifiers]


def proposal_basis(package):
    raw=package.export_dict()
    raw.pop('architectureProposals',None)
    raw.get('project',{}).pop('updatedAt',None)
    raw.get('project',{}).pop('updated_at',None)
    return hashlib.sha256(json.dumps(raw,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def scoped_context(context,identifiers,targets):
    """Keep existing implementation context, but no outside requirement content."""
    allowed=set(identifiers)
    def clean(value,key=''):
        if isinstance(value,list):
            if key in {'requirementIds','requirement_ids'}:return [i for i in value if i in allowed]
            return [clean(v) for v in value if not isinstance(v,dict) or
                not ((key=='requirements' or v.get('kind')=='Requirement' or v.get('type')=='Requirement')
                     and (v.get('id') or v.get('object',{}).get('id')) not in allowed)]
        if isinstance(value,dict):
            return {k:clean(v,k) for k,v in value.items() if k not in {'requirementId','requirement_id'} or v in allowed}
        return value
    result=clean(context)
    ec=result.get('engineeringContext',{})
    outside={o['object']['id'] for o in context.get('engineeringContext',{}).get('objects',[]) if o.get('objectType')=='Requirement' and o['object']['id'] not in allowed}
    ec['requirementEvidence']={i:v for i,v in ec.get('requirementEvidence',{}).items() if i in allowed}
    ec['objects']=[o for o in ec.get('objects',[]) if o.get('objectType')!='Requirement' or o.get('object',{}).get('id') in allowed]
    ec['relations']=[r for r in ec.get('relations',[]) if r.get('sourceId') not in outside and r.get('targetId') not in outside]
    result.pop('acceptedReviewNotes',None);result.pop('rejectedReviewFeedback',None)
    result['confirmedScope']={'requirementIds':list(identifiers),'targetViews':list(targets)}
    return result


def validate_result_scope(result,identifiers,targets):
    targets=set(targets)
    if not targets or targets-set(TARGET_FIELDS):raise ValueError('Gültige Zielarchitektur auswählen')
    fields=set().union(*(TARGET_FIELDS[t] for t in targets))
    for field in set().union(*TARGET_FIELDS.values()):
        candidates=getattr(result,field)
        if candidates and field not in fields:raise ValueError('Vorschlag enthält nicht gewählte Zielarchitektur: '+field)
        for candidate in candidates:
            if set(candidate.requirement_ids)-set(identifiers):raise ValueError('Vorschlag verweist auf Requirement außerhalb der Auswahl')
    for candidate in result.function_elements:
        if candidate.discipline not in targets:raise ValueError('FE liegt außerhalb der Zielarchitektur')
        if set(candidate.requirement_ids)-set(identifiers):raise ValueError('FE verweist auf Requirement außerhalb der Auswahl')


def validate_review_scope(package,proposal):
    scope=proposal.properties.get('confirmedScope')
    if not scope:return
    if scope['basis']!=proposal_basis(package):raise ValueError('Projektstand geändert. Architekturvorschlag neu erzeugen und prüfen.')
    selected_requirements(package,scope['requirementIds'])
    validate_result_scope(proposal,scope['requirementIds'],scope['targetViews'])
