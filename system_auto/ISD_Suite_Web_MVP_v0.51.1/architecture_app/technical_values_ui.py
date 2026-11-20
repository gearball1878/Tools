"""Typed implementation values with units, conditions and source revisions."""
from __future__ import annotations
import json
from .help_ui import mask_help
from nicegui import ui
from .models import ArchitecturePackage, TechnicalValue
from .technical_comparison import TECHNICAL_KEYS, SCALES


def render_technical_values(get_package, save, owner):
    from .comparison_ui import render_comparison
    render_comparison(get_package(),owner)
    values = [v for v in get_package().technical_values if v.owner_id==owner.id]
    with ui.expansion(f'Belegte technische Kennwerte · {len(values)}',value=False).classes('w-full border rounded'):
        ui.button('Ist-Kennwert erfassen',icon='add',on_click=lambda:value_dialog(get_package,save,owner)).props('outline dense no-caps')
        for value in values:
            with ui.row().classes('w-full items-center'):
                ui.label(f'{value.key}: {value.value} {value.unit} · {value.origin}').classes('grow text-sm')
                ui.button(icon='edit',on_click=lambda _,v=value:value_dialog(get_package,save,owner,v)).props('flat round dense')


def value_dialog(get_package, save, owner, existing=None):
    from .requirement_profiles import MECHANICAL, SOFTWARE
    kind = type(owner).__name__
    allowed = SOFTWARE|{'performance','capacity','resourceBudget'} if kind=='SoftwareComponent' else MECHANICAL|{'material','power','performance'} if kind=='MechanicalComponent' else TECHNICAL_KEYS
    definitions = {d.key:d for d in get_package().property_definitions if d.key in allowed or not d.system and kind in d.object_types and 'realization_attributes' in d.scopes}
    if existing and existing.key not in definitions:
        from .property_schema import PropertyDefinition
        definitions[existing.key] = PropertyDefinition(key=existing.key,label=existing.key,data_type='json',object_types=[kind])
    with ui.dialog() as dialog, ui.card().classes('w-[850px] max-w-[95vw] max-h-[92vh] overflow-auto p-6 gap-3'):
        mask_help(dialog,'realizations',owner,mask='Ist-Kennwert bearbeiten')
        ui.label(owner.name+' · Ist-Kennwert').classes('text-xl font-bold')
        key = ui.select({k:d.label for k,d in definitions.items()},value=existing.key if existing else None,label='Kennwert').props('use-input outlined').classes('w-full')
        value_area = ui.column().classes('w-full'); controls={}
        def render_value():
            value_area.clear();d=definitions.get(key.value)
            if not d:return
            old = existing.value if existing and key.value==existing.key else None
            with value_area:
                if d.data_type=='number': controls['value']=ui.number('Ist-Wert',value=old if isinstance(old,(int,float)) else None).classes('w-full')
                elif d.data_type=='boolean': controls['value']=ui.select({True:'Ja',False:'Nein'},value=old,label='Ist-Wert').classes('w-full')
                elif d.choices or d.selection_source:
                    from .property_schema import selection_options
                    options=selection_options(d,owner,get_package())
                    if isinstance(old,str):options.setdefault(old,old+' (Bestand)')
                    controls['value']=ui.select(options,value=old,label='Ist-Wert').props('use-input').classes('w-full')
                else: controls['value']=ui.textarea('Ist-Wert'+(' (strukturierte Angabe als JSON)' if d.data_type in {'list','json'} else ''),value=json.dumps(old,ensure_ascii=False) if old is not None and d.data_type in {'list','json'} else old or '').classes('w-full')
                units=[u for u,(dim,_) in SCALES.items() if d.unit in SCALES and dim==SCALES[d.unit][0]] or [d.unit]
                if existing and existing.unit not in units:units.append(existing.unit)
                controls['unit']=ui.select(units,value=existing.unit if existing and existing.unit else d.unit,label='Einheit').classes('w-full')
        key.on_value_change(lambda _:render_value());render_value()
        origin=ui.select(['Explizite Designangabe','Berechnet','Simuliert','Gemessen'],value=existing.origin if existing else 'Explizite Designangabe',label='Herkunft').classes('w-full')
        variants=getattr(owner,'variants',[])
        variant=ui.select({v.id:v.name for v in variants},value=existing.variant_id if existing else getattr(owner,'selected_variant_id',None),label='Gültig für Variante',clearable=True).classes('w-full');variant.set_visibility(bool(variants))
        from .traceability import project_objects
        target_options={i:getattr(o,'name',getattr(o,'title',i)) for kind,group in project_objects(get_package()).items() if kind in {'Domain','ArchitectureElement','ArchitectureSignal','Signal','Port','FunctionElement','SystemDomain','SystemElement','SoftwareArchitectureElement','MechanicalArchitectureElement'} for i,o in group.items()}
        target=ui.select(target_options,value=existing.target_id if existing else None,label='Gültig für Architektur / Netz / Bus (leer: allgemein)',clearable=True).props('use-input').classes('w-full')
        conditions={}
        with ui.expansion('Bedingungen und Quellen',value=False).classes('w-full'):
            for k in dict.fromkeys(['Betriebsmodus','Temperatur','Lastfall']+list(existing.conditions if existing else {})):
                conditions[k]=ui.input(k,value=existing.conditions.get(k,'') if existing else '').classes('w-full')
            from .traceability import project_objects
            registry=project_objects(get_package())
            source_options={s.id:getattr(s,'title',getattr(s,'name',s.id)) for kind in ['TechnicalSource','SourceDocument'] for s in registry[kind].values()}
            sources=ui.select(source_options,value=existing.source_ids if existing else [],multiple=True,label='Quellen / Ergebnisbelege').props('use-input use-chips').classes('w-full')
            revision=ui.input('Wert- / Quellenrevision',value=existing.revision if existing else '').classes('w-full')
            rationale=ui.textarea('Bedingungen / Begründung',value=existing.rationale if existing else '').classes('w-full')
        def accept():
            try:
                if key.value not in definitions:raise ValueError('Kennwert wählen')
                d=definitions[key.value]; value=controls['value'].value
                if d.data_type in {'json','list'}:value=json.loads(value)
                if value is None or value=='':raise ValueError('Ist-Wert fehlt')
                current=existing.model_copy(deep=True) if existing else TechnicalValue(owner_id=owner.id,key=key.value,value=value)
                current.key=key.value;current.target_id=target.value;current.value=value;current.unit=controls['unit'].value or '';current.origin=origin.value
                current.conditions={k:c.value for k,c in conditions.items() if c.value};current.source_ids=list(sources.value or [])
                current.variant_id=variant.value;current.revision=revision.value or '';current.rationale=rationale.value or ''
                candidate=get_package().model_copy(deep=True)
                candidate.technical_values=[v for v in candidate.technical_values if v.id!=current.id]+[current]
                candidate=ArchitecturePackage.model_validate(candidate.model_dump())
                p=get_package();before=p.technical_values;p.technical_values=candidate.technical_values
                if save('Ist-Kennwert gespeichert') is False:p.technical_values=before;return
                dialog.close()
            except (ValueError,TypeError) as error:ui.notify(str(error),type='negative')
        ui.button('Kennwert speichern',icon='save',on_click=accept)
        if existing:
            def remove():
                p=get_package();before=p.technical_values;p.technical_values=[v for v in before if v.id!=existing.id]
                if save('Ist-Kennwert entfernt') is False:p.technical_values=before;return
                dialog.close()
            ui.button('Wert entfernen',icon='delete_outline',on_click=remove).props('outline color=negative')
        ui.button('Abbrechen',on_click=dialog.close).props('flat')
    dialog.open()
