from pathlib import Path
import json, pickle, re, sys
sys.path.insert(0, str(Path(__file__).parent))
from symbol_wizard.models.document import *

root = Path(__file__).parent / 'symbol_wizard' / 'symbol_templates'
files = tuple(sorted((str(fp.relative_to(root)), fp.stat().st_mtime_ns, fp.stat().st_size) for fp in root.rglob('*.json')))
cache_key = ('template-index-v4', files)

def coerce_font(font, default_size=0.75):
    if isinstance(font, FontModel): return font
    if isinstance(font, dict):
        return FontModel(family=str(font.get('family','Arial')), size_grid=float(font.get('size_grid', default_size)), color=tuple(font.get('color',(0,0,0))))
    return FontModel(size_grid=default_size)

def text_any(value, default_text, default_x, default_y, font, default_h='left', default_v='upper'):
    fam = font.family if isinstance(font,FontModel) else 'Arial'; sz = font.size_grid if isinstance(font,FontModel) else .75; col=font.color if isinstance(font,FontModel) else (0,0,0)
    if isinstance(value, dict):
        tm=TextModel(text=str(value.get('text',default_text)), x=float(value.get('x',default_x)), y=float(value.get('y',default_y)), font_family=str(value.get('font_family',fam)), font_size_grid=float(value.get('font_size_grid',sz)), color=tuple(value.get('color',col)))
        tm.h_align=str(value.get('h_align',default_h)); tm.v_align=str(value.get('v_align',default_v)); tm.wrap_text=bool(value.get('wrap_text',False))
        for name in ('rotation','scale_x','scale_y'):
            if name in value: setattr(tm,name,value[name])
        return tm
    return TextModel(text=default_text,x=default_x,y=default_y,font_family=fam,font_size_grid=sz,color=col)

def is_large_ic_partition(name):
    n=str(name or '').upper().replace('-','_')
    exclude=('RELAIS','RELAY','DIODE','FET','TRANS','THYR','TRIAC','IGBT','OPTO','IND_','FILTER','DROSSEL','UEBTR','WIDERSTAND','KONDENSATOR','CAP','STECKER','CONNECTOR','ZUBEHOER','GND','BORDER','INFO','TESTPUNKT')
    if any(t in n for t in exclude): return False
    tokens=('CONTROLLER','PROZESSOR','PROCESSOR','CPU','SOC','FPGA','CPLD','DSP','ASIC','MCU','MPU','PMIC','BGA','LOGIK','LOGIC','MULTIFUNKTIONS','MUTLIFUNKTIONS','MULTIFUNCTION','VERSTAERKER_IC','AMPLIFIER_IC')
    return any(t in n for t in tokens)

def template_partition_from_path(fp):
    rel=fp.relative_to(root).with_suffix(''); parts=list(rel.parts)
    if parts and parts[0]=='mentor_known' and len(parts)>=2: return parts[-1]
    if len(parts)>=2: return parts[-2]
    return rel.name

def split_base_from_name(name):
    raw=str(name or '').strip(); leaf=raw.split('/')[-1].strip(); leaf=re.sub(r'\.(sym|json)$','',leaf,flags=re.I); leaf=re.sub(r'\.\d{1,3}$','',leaf); s=leaf.strip()
    if len(s)<4: return None,None
    suffix_words=('CONTROL','CTRL','PWR','POWER','SUPPLY','SUP','VDD','VSS','VCC','GND','GPIO','IO','PORT',r'BANK\d*','JTAG','TEST','CFG','CONFIG','CONF','CORE','ANA','ANALOG','DIG','DIGITAL','ADC','DAC','A2D','D2A','DDR',r'DDRX\d+','MEM','RAM','FLASH','SDRAM','USB','PCIE','PCIe','SATA','SDHC','EIM','RGMII','ETH','ENET','PHY','MIPI','CSI','DSI','DISP','HDMI','LVDS','SERDES','SPI','I2C','CAN','LIN','UART','RX','TX','RXD','TXD','PLL','CLK','CLOCK','OSC','MISC','NC')
    suffix_re=r'(?:'+'|'.join(suffix_words)+r')(?:[_-]?(?:\d+|[A-Z]))?'
    m=re.match(rf'^(?P<base>.+?)[_-](?P<part>{suffix_re})$',s,flags=re.I)
    if m and len(m.group('base'))>=3: return m.group('base'),m.group('part')
    m=re.match(r'^(?P<base>.+?)[_-](?P<part>\d{1,3}|[A-Z])$',s,flags=re.I)
    if m and len(m.group('base'))>=3: return m.group('base'),m.group('part')
    m=re.match(r'^(?P<base>[A-Za-z][A-Za-z0-9]{2,})-(?P<part>\d{1,3})$',s)
    if m: return m.group('base'),m.group('part')
    chunks=re.split(r'[_-]+',s)
    if len(chunks)>=2 and len(chunks[0])>=3:
        last=chunks[-1]
        if re.match(r'^(?:\d{1,3}|[A-Z]|[A-Z]{2,6}\d*)$',last,re.I): return '_'.join(chunks[:-1]),last
        if len(chunks)>=3: return '_'.join(chunks[:-1]),last
    return None,None

def unit_from_payload(payload):
    try:
        src=payload.get('unit',payload) if isinstance(payload,dict) else payload
        body_src=src.get('body',{}) if isinstance(src,dict) else {}
        bd={k:v for k,v in dict(body_src).items() if k in SymbolBodyModel.__dataclass_fields__}
        bd['attribute_font']=coerce_font(bd.get('attribute_font'),.75); bd['refdes_font']=coerce_font(bd.get('refdes_font'),.9)
        if isinstance(bd.get('attribute_texts'),dict): bd['attribute_texts']={str(k): text_any(v,str(k),0,0,bd['attribute_font']) for k,v in bd.get('attribute_texts',{}).items()}
        body=SymbolBodyModel(**bd)
        pins=[]
        for pd in (src.get('pins',[]) or []):
            pd=dict(pd); pd['number_font']=coerce_font(pd.get('number_font'),.45); pd['label_font']=coerce_font(pd.get('label_font'),.55)
            if isinstance(pd.get('attribute_texts'),dict): pd['attribute_texts']={str(k): text_any(v,str(k),0,0,pd['label_font']) for k,v in pd.get('attribute_texts',{}).items()}
            pins.append(PinModel(**pd))
        texts=[TextModel(**dict(t)) for t in (src.get('texts',[]) or [])]
        graphics=[]
        for gd in (src.get('graphics',[]) or []):
            gd=dict(gd); style=gd.pop('style',None); g=GraphicModel(**gd)
            if isinstance(style,dict): g.style=StyleModel(**style)
            graphics.append(g)
        return SymbolUnitModel(name=str(src.get('name',payload.get('name','Template'))), body=body, pins=pins, texts=texts, graphics=graphics)
    except Exception as e:
        return None

result={}; split_groups={}
for fp in sorted(root.rglob('*.json')):
    try: data=json.load(open(fp,encoding='utf-8'))
    except Exception: continue
    entries=data if isinstance(data,list) else [data]
    for entry in entries:
        if not isinstance(entry,dict): continue
        unit=unit_from_payload(entry)
        if unit is None: continue
        rel=fp.relative_to(root).with_suffix('').as_posix()
        entry_name=str(entry.get('template_name') or entry.get('name') or Path(rel).name).strip() or Path(rel).name
        # strip prefixed partition from template_name if present
        part_name=template_partition_from_path(fp)
        if ' / ' in entry_name:
            entry_name=entry_name.split(' / ')[-1].strip()
        name=f'{part_name} / {entry_name}' if part_name and part_name!=entry_name else entry_name
        result[name]=unit
        if is_large_ic_partition(part_name):
            base, part_no=split_base_from_name(entry_name)
            if base:
                group_key=f'Split Symbols / {part_name} / {base}'
                unit.name=entry_name
                split_groups.setdefault(group_key,[]).append(unit)

grouped={}
for group_key, units in split_groups.items():
    # only if there are different concrete names
    if len({u.name for u in units})<2: continue
    units=sorted(units,key=lambda u: str(u.name).lower())
    grouped[group_key]=units
    first=units[0]
    first.body.attributes['MENTOR_SPLIT_TEMPLATE']='1'; first.body.attributes['MENTOR_SPLIT_PARTS']=str(len(units))
    first.body.visible_attributes['MENTOR_SPLIT_TEMPLATE']=False; first.body.visible_attributes['MENTOR_SPLIT_PARTS']=False
    result[group_key]=first
print('templates',len(result),'split groups',len(grouped))
with (root/'.template_index_cache.pickle').open('wb') as fh:
    pickle.dump({'cache_key':cache_key,'templates':result,'split_templates':grouped},fh,protocol=pickle.HIGHEST_PROTOCOL)
