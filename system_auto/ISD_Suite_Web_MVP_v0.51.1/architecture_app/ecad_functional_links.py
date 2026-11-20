"""Explicit sheet-pin connectivity for abstract FE interfaces and dependencies."""
from .kicad_readback import _children, _value


def sheet_links(tree, chain):
    from .kicad_project_readback import _Graph, _on, _bus
    graph=_Graph();segments=[];pins=[];labels=[];points=set();aliases={}
    def at(node):
        values=_children(node,'at')
        return tuple(float(v) for v in values[0][1:3]) if values else None
    for alias in _children(tree,'bus_alias'):
        if len(alias)>1:aliases[alias[1]]=[str(v) for values in _children(alias,'members') for v in values[1:]]
    for kind in ('wire','bus'):
        for item in _children(tree,kind):
            positions=[tuple(float(v) for v in point[1:3]) for pts in _children(item,'pts') for point in _children(pts,'xy')]
            if len(positions)!=2:continue
            a,b=positions;segments.append((kind,a,b));points.update((a,b));graph.join((kind,a),(kind,b))
    for junction in _children(tree,'junction'):
        point=at(junction)
        if point:points.add(point)
    for sheet in _children(tree,'sheet'):
        key='/'.join((*chain,_value(sheet,'uuid')))
        for pin in _children(sheet,'pin'):
            point=at(pin)
            if point:
                pins.append({'block':key,'name':str(pin[1]),'direction':str(pin[2]),'point':point});points.add(point)
    for kind in ('label','global_label','hierarchical_label'):
        for label in _children(tree,kind):
            point=at(label)
            if point:labels.append({'name':str(label[1]),'point':point});points.add(point)
    for kind,a,b in segments:
        for point in points:
            if _on(point,a,b):graph.join((kind,point),(kind,a))
    named={}
    for label in labels:
        for kind in ('wire','bus'):
            node=(kind,label['point'])
            if node not in graph.parent:continue
            token=(kind,label['name'])
            if token in named:graph.join(node,named[token])
            else:named[token]=node
    groups={}
    for pin in pins:
        for kind in ('wire','bus'):
            node=(kind,pin['point'])
            if node in graph.parent:
                groups.setdefault(graph.find(node),{'pins':[],'names':[]})['pins'].append({k:v for k,v in pin.items() if k!='point'})
    for label in labels:
        for kind in ('wire','bus'):
            node=(kind,label['point'])
            if node not in graph.parent:continue
            group=groups.get(graph.find(node))
            if group:
                name,members=_bus(label['name'],aliases)
                group['names'].extend([label['name'],name,*(members or [])])
    return list(groups.values())
