"""Custom property fields embedded in object-specific edit masks."""
from __future__ import annotations
import json
from nicegui import ui
from .property_schema import applicable, selection_options, validate_value


def custom_inputs(package,obj, *, include_system=False, exclude_keys=()):
    controls=[]
    definitions=[d for d in package.property_definitions if (include_system or not d.system) and not d.readonly and d.key not in exclude_keys]
    entries=[(scope,d) for scope in ('requirement_attributes','realization_attributes') for d in applicable(definitions,obj,scope)]
    if entries:
        with ui.expansion('Objektattribute' if include_system else 'Eigene Objektattribute',value=True).classes('w-full border rounded'):
            for scope,d in entries:
                value=getattr(obj,scope).get(d.key)
                label=('Anforderung · ' if scope=='requirement_attributes' else 'Realisierung · ')+d.label
                structured=d.data_type in {'json','list'} and not d.selection_source or d.data_type=='number' and isinstance(value,dict)
                selected=bool(d.choices or d.selection_source)
                if selected:
                    options=selection_options(d,obj,package)
                    for v in value if isinstance(value,list) else [value]:
                        if isinstance(v,str):options.setdefault(v,v+' (Bestand)')
                    field=ui.select(options,value=value,label=label,multiple=d.data_type=='list',clearable=True).props('use-input use-chips' if d.data_type=='list' else 'use-input').classes('w-full')
                elif structured:field=ui.textarea(label+' (strukturierte Angabe als JSON)',value=json.dumps(value,ensure_ascii=False) if value is not None else '').classes('w-full')
                elif d.data_type=='number':field=ui.number(label+(f' [{d.unit}]' if d.unit else ''),value=value).classes('w-full')
                elif d.data_type=='boolean':field=ui.select({True:'Ja',False:'Nein'},value=value,label=label,clearable=True).classes('w-full')
                else:field=ui.input(label,value=value or '').classes('w-full')
                controls.append((scope,d,field,structured,selected,value))
    def apply(target):
        pending=[]
        for scope,d,field,structured,selected,old in controls:
            value=field.value
            if structured:value=json.loads(value) if value else None
            elif d.data_type in {'text','reference','enum'} and value=='':value=None
            validate_value(d,value)
            if selected and value!=old:
                from .requirement_profiles import validate_selection
                validate_selection(d,target,package,value)
            pending.append((scope,d.key,value))
        for scope,key,value in pending:getattr(target,scope)[key]=value
        return target
    return apply
