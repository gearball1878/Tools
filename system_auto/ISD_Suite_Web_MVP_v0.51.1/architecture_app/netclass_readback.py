"""Reviewed imports of KiCad class definitions and pattern-based assignments."""
from copy import deepcopy
from fnmatch import fnmatchcase
from .ecad_connector import AnnotationChange
from .netclasses import NetClassDefinition


def _matches(settings,name,qualified=()):
    result=[]
    candidates=[name,'/'+name,*qualified]
    for entry in settings.get('netclass_patterns',[]):
        pattern=entry.get('pattern','')
        if any(fnmatchcase(candidate,pattern) for candidate in candidates):
            value=entry.get('netclass')
            if isinstance(value,str) and value not in result:result.append(value)
    for net,values in (settings.get('netclass_assignments') or {}).items():
        if net in candidates:
            for value in ([values] if isinstance(values,str) else values or []):
                if isinstance(value,str) and value not in result:result.append(value)
    priorities={c['name']:c.get('priority',i) for i,c in enumerate(settings.get('classes',[])) if 'name' in c}
    return sorted(result,key=lambda c:priorities.get(c,2147483647))


def inspect_netclasses(package,project,preview,desired,baseline):
    settings=project.get('net_settings',{})
    preview.net_settings=deepcopy(settings)
    binding=package.properties.get('ecadConnectors',{}).get('kicad',{})
    previous=binding.get('netSettingsBaseline') or project.get('isd_suite',{}).get('netSettingsBaseline')
    if previous is None:
        from .kicad_rules import project_settings
        import json
        previous=json.loads(project_settings([s for s in package.signals if s.source and s.sinks],'baseline',package.net_classes))['net_settings']
    if not settings or settings==previous:return
    old={c['name']:c for c in previous.get('classes',[]) if 'name' in c}
    known={c.name:c.model_dump(mode='json') for c in package.net_classes}
    changed=False
    for index,item in enumerate(settings.get('classes',[])):
        name=item.get('name')
        if not name or item==old.get(name):continue
        values={k:v for k,v in item.items() if k not in ['name','priority']}
        if name not in known:known[name]=NetClassDefinition(name=name,origin='KiCad').model_dump(mode='json')
        known[name].update(priority=item.get('priority',index),ecad_parameters=values,origin='KiCad');changed=True
    if changed:
        # Numeric rules remain ECAD-owned and are read-only in ISD.
        catalog=list(known.values())
        original=[c.model_dump(mode='json') for c in package.net_classes]
        base_catalog=baseline.get('net_classes',original)
        conflicts=any(c['name'] in {v['name'] for v in base_catalog} and c!=next(v for v in base_catalog if v['name']==c['name'])
                      and c!=known.get(c['name']) for c in original)
        preview.changes.append(AnnotationChange(package.project.id,'project.net_classes',original,catalog,
            'conflict' if conflicts else 'ready','KiCad-Netzklassen, Prioritäten und explizite Regelparameter'))
    for sid,data in desired['signal'].items():
        targets=data['bus_contents'] if data['connection_type']=='Bus' else [data]
        for obj in targets:
            qualified=[]
            for endpoint in ([data['source']] if data.get('source') else [])+data.get('sinks',[]):
                ae=desired['element'].get(endpoint['element_id'],{})
                domain=desired['domain'].get(ae.get('domain_id'),{})
                if domain and ae:
                    qualified.extend(['/'+domain['name']+'/'+obj['name'],'/'+domain['name']+'/'+ae['name']+'/'+obj['name']])
            now=_matches(settings,obj['name'],qualified);before=_matches(previous,obj['name'],qualified)
            if now==before:continue
            if not now:
                obj.setdefault('realization_attributes',{})['netClass']=None
                obj['realization_attributes']['netClasses']=None
            else:
                obj.setdefault('realization_attributes',{})['netClass']=now[0]
                obj['realization_attributes']['netClasses']=now[1:] or None
            obj['realization_attributes']['classPriority']={n:i for i,n in enumerate(now)}
            obj.setdefault('attributes',{}).setdefault('attributeProvenance',{})['netClass']={'source':'KiCad','projectRevision':project.get('meta',{}).get('version')}

