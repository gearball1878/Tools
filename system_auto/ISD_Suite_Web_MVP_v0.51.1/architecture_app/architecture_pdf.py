"""Searchable vector PDF with internal links for architecture review."""
from __future__ import annotations

import hashlib
import io
import json
import math
from collections import Counter
from textwrap import shorten

from .models import ArchitecturePackage


def _export_hw_architecture_pdf(package: ArchitecturePackage, revision: int = 0) -> bytes:
    from .hardware_topology import is_global_ground, block_port_visible
    package = package.model_copy(deep=True)
    grounds = {s.id for s in package.signals if is_global_ground(s)}
    package.connections = [c for c in package.connections if c.signal_id not in grounds]
    for domain in package.domains:
        for element in domain.elements:
            element.ports = [p for p in element.ports if block_port_visible(package, p)]
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen.canvas import Canvas
    from pathlib import Path

    hardware_functions = [f for f in package.function_elements if f.discipline == 'hardware']
    font = "Helvetica"
    candidate = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if candidate.exists():
        if "ISDDejaVu" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("ISDDejaVu", str(candidate)))
        font = "ISDDejaVu"

    data = json.dumps(package.export_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    checksum = hashlib.sha256(data).hexdigest()
    buffer = io.BytesIO()
    pdf = Canvas(buffer, pagesize=landscape(A3), pageCompression=1)
    pdf.setTitle(f"{package.project.name} · Architektur · Stand {revision}")
    pdf.setAuthor("ISD Suite")
    pdf.setSubject(f"SPOT SHA-256: {checksum}; Gesamtarchitektur; Revision {revision}")
    width, height = landscape(A3)
    navy, blue, gray = HexColor("#17365D"), HexColor("#2563EB"), HexColor("#52657B")

    def label(x: float, y: float, value: str, size: int = 10, color=navy) -> None:
        pdf.setFillColor(color)
        pdf.setFont(font, size)
        pdf.drawString(x, y, shorten(str(value), width=90, placeholder="…"))

    def header(title: str, section: str) -> None:
        pdf.setFillColor(navy)
        pdf.rect(0, height - 78, width, 78, fill=1, stroke=0)
        label(42, height - 35, title, 17, HexColor("#FFFFFF"))
        label(42, height - 57, f"{section} · Revision {revision} · SPOT SHA-256 {checksum[:20]}…", 9, HexColor("#DFEBFA"))
        pdf.setStrokeColor(HexColor("#D7E1ED"))
        pdf.line(42, 36, width - 42, 36)
        label(42, 22, "ISD Suite · vektorbasierter Architektur-Export", 8, gray)
        label(width - 120, 22, f"Seite {pdf.getPageNumber()}", 8, gray)

    def link_box(x: float, y: float, box_width: float, box_height: float, target: str) -> None:
        pdf.linkRect("", target, (x, y, x + box_width, y + box_height), relative=0, thickness=0)

    # A single scalable opening sheet shows the actual domain topology and the
    # elements inside each domain. Its paper height grows with the model so
    # labels keep a readable point size instead of being shrunk to fit A3.
    element_domain = {element.id: domain.id for domain in package.domains for element in domain.elements}
    domain_names = {domain.id: domain.name for domain in package.domains}
    domain_links: Counter[tuple[str, str]] = Counter()
    internal_links: Counter[str] = Counter()
    cross_labels: dict[str, list[str]] = {domain.id: [] for domain in package.domains}
    for connection in package.connections:
        if not connection.endpoints:
            continue
        source = element_domain.get(connection.endpoints[0].element_id)
        if not source:
            continue
        for destination in {element_domain.get(endpoint.element_id) for endpoint in connection.endpoints[1:]}:
            if destination == source:
                internal_links[source] += 1
            elif destination:
                domain_links[source, destination] += 1
                cross_labels[source].append(f"→ {domain_names[destination]}: {connection.name}")

    def overview_card_height(domain) -> int:
        return (106 + 26 * math.ceil(len(domain.elements) / 2)
                + 18 * min(4, len(cross_labels[domain.id])))

    columns = 4
    card_width = 246
    gutter = (width - 84 - columns * card_width) / (columns - 1)
    row_heights = [max(overview_card_height(domain)
                       for domain in package.domains[row:row + columns])
                   for row in range(0, len(package.domains), columns)]
    overview_height = max(520, 195 + sum(row_heights) + max(0, len(row_heights) - 1) * 36 + 104)
    pdf.setPageSize((width, overview_height))
    height = overview_height
    pdf.bookmarkPage("overview")
    pdf.addOutlineEntry("Gesamtarchitektur · Grafik", "overview", level=0)
    header(package.project.name, "Gesamtarchitektur · Domains, Elemente und Verbindungen")
    label(44, height - 107,
          f"{len(package.domains)} Domains  ·  {sum(len(d.elements) for d in package.domains)} Architecture Elements"
          f"  ·  {len(package.connections)} Verbindungen · {len(hardware_functions)} FE", 11)
    label(44, height - 128, "Pfeile: tatsächliche Verbindungen zwischen Domains · Zahl am Pfeil: mehrere Verbindungen", 9, gray)
    boxes: dict[str, tuple[float, float, float, float]] = {}
    top = height - 160
    for index, domain in enumerate(package.domains):
        col, row = index % columns, index // columns
        card_height = overview_card_height(domain)
        x = 42 + col * (card_width + gutter)
        y = top - sum(row_heights[:row]) - row * 36 - card_height
        boxes[domain.id] = x, y, card_width, card_height

    # Draw relationships underneath the domain cards so long connections do
    # not obscure any element name. Parallel connections share one arrow.
    for (source, target), count in sorted(domain_links.items()):
        if source not in boxes or target not in boxes:
            continue
        sx, sy, sw, sh = boxes[source]
        tx, ty, tw, th = boxes[target]
        start_x, start_y = sx + sw, sy + sh / 2
        end_x, end_y = tx, ty + th / 2
        pdf.setStrokeColor(HexColor("#437fae"))
        pdf.setLineWidth(1.6 + min(count, 5) * .25)
        path = pdf.beginPath()
        path.moveTo(start_x, start_y)
        path.curveTo(start_x + 27, start_y, end_x - 27, end_y, end_x, end_y)
        pdf.drawPath(path)
        pdf.line(end_x, end_y, end_x - 7, end_y + 3.5)
        pdf.line(end_x, end_y, end_x - 7, end_y - 3.5)
        if count > 1:
            middle_x = (start_x + end_x) / 2
            middle_y = (start_y + end_y) / 2
            pdf.setFillColor(HexColor("#FFFFFF"))
            pdf.circle(middle_x, middle_y, 9, fill=1, stroke=0)
            label(middle_x - 4, middle_y - 3, str(count), 8, blue)

    for domain in package.domains:
        x, y, card_width, card_height = boxes[domain.id]
        pdf.setFillColor(HexColor("#F2F6FB"))
        pdf.setStrokeColor(HexColor(domain.color if domain.color.startswith("#") else "#2563EB"))
        pdf.setLineWidth(2)
        pdf.roundRect(x, y, card_width, card_height, 9, fill=1, stroke=1)
        label(x + 12, y + card_height - 24, shorten(domain.name, width=30, placeholder="…"), 12)
        label(x + 12, y + card_height - 43,
              f"{len(domain.elements)} AE · {internal_links[domain.id]} interne Verbindungen", 8, gray)
        if not domain.elements:
            label(x + 12, y + 35, "Noch keine Architecture Elements", 8, gray)
        for index, element in enumerate(domain.elements):
            chip_x = x + 10 + (index % 2) * 118
            chip_y = y + card_height - 76 - (index // 2) * 26
            pdf.setFillColor(HexColor("#FFFFFF"))
            pdf.setStrokeColor(HexColor("#CCDCEB"))
            pdf.roundRect(chip_x, chip_y, 111, 22, 4, fill=1, stroke=1)
            label(chip_x + 5, chip_y + 7, shorten(element.name, width=18, placeholder="…"), 8)
            link_box(chip_x, chip_y, 111, 22, "element-" + element.id)
        outgoing = sorted(cross_labels[domain.id])
        if len(outgoing) > 4:
            outgoing = outgoing[:3] + [f"→ {len(outgoing) - 3} weitere Verbindungen in den Domain-Details"]
        for index, description in enumerate(outgoing):
            label(x + 12, y + 30 + (len(outgoing) - 1 - index) * 15,
                  shorten(description, width=38, placeholder="…"), 8, gray)
        label(x + 12, y + 12, "Domain-Details öffnen ↗", 8, blue)
        link_box(x, y, card_width, 25, "domain-" + domain.id)
    if not package.domains:
        label(48, height - 205, "Noch keine Domains vorhanden. Architektur im HW-/ECAD-Reiter anlegen.", 12, gray)
    if package.system_definition.core_idea:
        label(44, 95, "Kernidee: " + package.system_definition.core_idea, 9, gray)
    if package.system_definition.system_boundary:
        label(44, 75, "Systemgrenze: " + package.system_definition.system_boundary, 9, gray)
    if package.requirements:
        label(44, 52, "Requirements-Verzeichnis öffnen ↗", 9, blue)
        link_box(42, 45, 250, 22, "requirements")
    pdf.showPage()
    width, height = landscape(A3)
    pdf.setPageSize((width, height))

    name_by_id = {element.id: element.name for domain in package.domains for element in domain.elements}
    for domain in package.domains:
        pdf.bookmarkPage("domain-" + domain.id)
        pdf.addOutlineEntry(domain.name, "domain-" + domain.id, level=1)
        header(domain.name, "Domain · Architekturdiagramm")
        pdf.linkAbsolute("Zur Gesamtarchitektur", "overview", Rect=(width - 210, height - 54, width - 38, height - 25))
        elements = domain.elements
        # Each card and edge is drawn with PDF vector primitives; overflow uses
        # more pages so that font sizes remain useful in a printed A3 drawing.
        pages = max(1, math.ceil(len(elements) / 12))
        for page in range(pages):
            if page:
                header(domain.name, f"Domain · Fortsetzung {page + 1}")
            subset = elements[page * 12:(page + 1) * 12]
            positions: dict[str, tuple[float, float]] = {}
            box_w, box_h = (width - 120) / 3, 82
            for n, element in enumerate(subset):
                col, row = n % 3, n // 3
                x, y = 48 + col * (box_w + 10), height - 210 - row * 106
                positions[element.id] = (x + box_w / 2, y + box_h / 2)
            for connection in package.connections:
                endpoints = [endpoint.element_id for endpoint in connection.endpoints]
                if not endpoints or endpoints[0] not in positions:
                    continue
                for sink in endpoints[1:]:
                    if sink not in positions:
                        continue
                    x1, y1 = positions[endpoints[0]]
                    x2, y2 = positions[sink]
                    if abs(x2 - x1) > box_w * .7:
                        direction = 1 if x2 > x1 else -1
                        x1 += direction * box_w / 2
                        x2 -= direction * box_w / 2
                        y2 = y1 if abs(y2 - y1) < box_h / 2 else y2
                    else:
                        direction = 1 if y2 > y1 else -1
                        y1 += direction * box_h / 2
                        y2 -= direction * box_h / 2
                    pdf.setStrokeColor(HexColor("#86A1BF"))
                    pdf.setLineWidth(1.3)
                    pdf.line(x1, y1, x2, y2)
                    vector_x, vector_y = x2 - x1, y2 - y1
                    length = math.hypot(vector_x, vector_y)
                    if length > 2:
                        ux, uy = vector_x / length, vector_y / length
                        pdf.line(x2, y2, x2 - 8 * ux - 4 * uy, y2 - 8 * uy + 4 * ux)
                        pdf.line(x2, y2, x2 - 8 * ux + 4 * uy, y2 - 8 * uy - 4 * ux)
            for element in subset:
                cx, cy = positions[element.id]
                x, y = cx - box_w / 2, cy - box_h / 2
                pdf.setFillColor(HexColor("#FFFFFF"))
                pdf.setStrokeColor(blue)
                pdf.roundRect(x, y, box_w, box_h, 7, fill=1, stroke=1)
                label(x + 12, y + 52, element.name, 11)
                label(x + 12, y + 30, f"{len(element.ports)} Ports · {element.kind}", 8, gray)
                label(x + 12, y + 11, "Details öffnen ↗", 8, blue)
                link_box(x, y, box_w, box_h, "element-" + element.id)
            start_y = 145
            label(48, start_y, "Verbindungen (Quelle → Teilnehmer)", 10)
            for n, connection in enumerate([c for c in package.connections if any(e.element_id in positions for e in c.endpoints)][:5]):
                names = [name_by_id.get(e.element_id, e.element_id) for e in connection.endpoints]
                label(48, start_y - 22 - n * 18, f"{connection.name}: {' → '.join(names)}", 8, gray)
            pdf.showPage()
        for element in elements:
            pdf.bookmarkPage("element-" + element.id)
            pdf.addOutlineEntry(element.name, "element-" + element.id, level=2)
            header(element.name, "Architecture Element")
            pdf.linkAbsolute("Zur Domain", "domain-" + domain.id, Rect=(width - 180, height - 54, width - 38, height - 25))
            label(50, height - 120, f"Domain: {domain.name} · ID: {element.id}", 11)
            label(50, height - 148, element.description or "Keine Beschreibung hinterlegt", 10, gray)
            label(50, height - 190, "Ports", 13)
            for index, port in enumerate(element.ports[:22]):
                label(54, height - 220 - index * 22, f"{port.name} · {getattr(port, 'port_type', '')} · {getattr(port, 'pin_type', '')}", 9)
            functions=[f for f in hardware_functions if f.architecture_element_id==element.id]
            if functions:
                label(50, 58, f"{len(functions)} Funktions-Elemente · Funktionsdetails öffnen ↗", 9, blue)
                link_box(48, 49, 350, 24, 'function-'+functions[0].id)
            pdf.showPage()
    signal_names={s.id:s.name for s in package.signals}
    function_names={f.id:f.name for f in hardware_functions}
    requirement_names={r.id:r.identifier+' · '+r.title for r in package.requirements}
    for function in hardware_functions:
        pdf.bookmarkPage('function-'+function.id)
        pdf.addOutlineEntry('FE · '+function.name,'function-'+function.id,level=0)
        header(function.name,'Funktions-Element · abstrahierte Hardwarefunktion')
        cursor=height-116

        def paragraph(title,value):
            nonlocal cursor
            if cursor<90:
                pdf.showPage();header(function.name,'Funktions-Element · Fortsetzung');cursor=height-116
            pdf.setFont(font,11);pdf.setFillColor(navy);pdf.drawString(50,cursor,title);cursor-=24
            for raw_line in str(value or 'Noch offen').splitlines():
                words=raw_line.split();rows=[];line=''
                for word in words:
                    candidate=(line+' '+word).strip()
                    if line and pdfmetrics.stringWidth(candidate,font,10)>width-100:
                        rows.append(line);line=word
                    else:line=candidate
                rows.append(line)
                for line in rows:
                    # Split long source locators as well as ordinary prose.
                    chunks=[];chunk=''
                    for char in line:
                        if chunk and pdfmetrics.stringWidth(chunk+char,font,10)>width-100:
                            chunks.append(chunk);chunk=char
                        else:chunk+=char
                    chunks.append(chunk)
                    for chunk in chunks:
                        if cursor<62:
                            pdf.showPage();header(function.name,'Funktions-Element · Fortsetzung');cursor=height-116
                        pdf.setFont(font,10);pdf.setFillColor(gray);pdf.drawString(50,cursor,chunk);cursor-=17
            cursor-=15

        paragraph('Architekturbezug',name_by_id.get(function.architecture_element_id,'Noch nicht zugeordnet'))
        paragraph('Funktionsbeschreibung',function.description)
        paragraph('Funktionale Schnittstellen','\n'.join(signal_names.get(i,i) for i in function.interface_signal_ids))
        paragraph('Abhängigkeiten','\n'.join(function_names.get(i,i) for i in function.dependency_ids))
        paragraph('Requirements','\n'.join(requirement_names.get(i,i) for i in function.requirement_ids))
        paragraph('ECAD-Herkunft','\n'.join(v for v in (function.source_project,function.source_sheet,function.source_revision) if v))
        pdf.showPage()
    if package.requirements:
        for index, requirement in enumerate(package.requirements):
            if index % 8 == 0:
                if index:
                    pdf.showPage()
                pdf.bookmarkPage("requirements") if index == 0 else None
                if index == 0:
                    pdf.addOutlineEntry("Requirements", "requirements", level=0)
                header(package.project.name, "Requirements · Nachverfolgung")
                label(48, height - 112, "Identifier · Klassifizierung · Status · Quelle", 10)
            y = height - 168 - (index % 8) * 82
            pdf.bookmarkHorizontalAbsolute("requirement-" + requirement.id, y + 38)
            pdf.setFillColor(HexColor("#F2F6FB"))
            pdf.roundRect(46, y - 22, width - 92, 70, 7, fill=1, stroke=0)
            label(58, y + 24, f"{requirement.identifier} · {requirement.title}", 10)
            label(58, y + 4, shorten(requirement.text, width=150, placeholder="…"), 8, gray)
            label(58, y - 13, f"{requirement.classification.value} · {requirement.maturity.value} · Quelle: {requirement.source_locator or '—'}", 8, gray)
        pdf.showPage()
    references = [("Norm", item.designation + " · " + item.title, item.source_url) for item in package.standards]
    references += [("Technische Quelle", item.title, item.url) for item in package.technical_sources]
    references += [("Quelldokument", item.name, str(item.properties.get("url") or "")) for item in package.source_documents]
    if references:
        for index, (kind, title, url) in enumerate(references):
            if index % 24 == 0:
                if index:
                    pdf.showPage()
                if index == 0:
                    pdf.bookmarkPage("references")
                    pdf.addOutlineEntry("Normen und Quellen", "references", level=0)
                header(package.project.name, "Normen und Quellen")
            y = height - 120 - (index % 24) * 27
            label(48, y, f"{kind}: {title}", 9)
            if url.startswith(("https://", "http://")):
                label(width - 240, y, "Online-Quelle öffnen ↗", 8, blue)
                pdf.linkURL(url, (width - 250, y - 4, width - 48, y + 16), relative=0)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


ARCHITECTURE_LABELS={'system':'Systemarchitektur','hardware':'Hardwarearchitektur',
                     'mechanical':'Mechanikarchitektur','software':'Software-/Firmwarearchitektur'}


def export_architecture_pdf(package: ArchitecturePackage, revision: int=0, views=None) -> bytes:
    """Export chosen views, with independent pages, bookmarks and complete edge lists."""
    from pypdf import PdfWriter
    views=['hardware'] if views is None else list(ARCHITECTURE_LABELS) if views=='all' else [views] if isinstance(views,str) else list(views)
    if not views or set(views)-set(ARCHITECTURE_LABELS):raise ValueError('Mindestens eine gültige Architektur auswählen')
    writer=PdfWriter()
    for view in dict.fromkeys(views):
        raw=_export_hw_architecture_pdf(package,revision) if view=='hardware' else _export_discipline_pdf(package,revision,view)
        writer.append(io.BytesIO(raw),outline_item=ARCHITECTURE_LABELS[view])
    checksum=hashlib.sha256(json.dumps(package.export_dict(),ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    writer.add_metadata({'/Title':f'{package.project.name} · Architektur · Stand {revision}',
        '/Author':'ISD Suite','/Subject':f'SPOT SHA-256: {checksum}; '+', '.join(ARCHITECTURE_LABELS[v] for v in views)})
    output=io.BytesIO();writer.write(output);return output.getvalue()


def _export_discipline_pdf(package,revision,discipline):
    from pathlib import Path
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A3,landscape
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen.canvas import Canvas
    if discipline=='system':
        nodes=package.system_elements;relations=package.system_relations
        groups={d.id:d.name for d in package.system_domains}
    else:
        from .discipline_architecture import elements
        from types import SimpleNamespace
        functions = [f for f in package.function_elements if f.discipline == discipline]
        nodes=list(elements(package,discipline))+functions
        relations=[r for r in package.discipline_relations if r.discipline==discipline];groups={}
        for function in functions:
            if function.architecture_element_id:
                relations.append(SimpleNamespace(source_id=function.architecture_element_id,
                    target_id=function.id,name='Enthält FE',kind='contains',description=''))
            relations.extend(SimpleNamespace(source_id=function.id,target_id=identifier,
                name='FE-Abhängigkeit',kind='dependency',description='') for identifier in function.dependency_ids)
    width,normal_height=landscape(A3);height=max(normal_height,220+math.ceil(len(nodes)/3)*120)
    stream=io.BytesIO();pdf=Canvas(stream,pagesize=(width,height),pageCompression=1)
    font='Helvetica';path=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if path.exists():
        if 'ISDDejaVu' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('ISDDejaVu',str(path)))
        font='ISDDejaVu'
    navy=HexColor('#17365D');gray=HexColor('#52657B');teal=HexColor('#0F766E');title=ARCHITECTURE_LABELS[discipline]
    def lines(value,max_width,size=10):
        # Split even long identifiers, retaining every character.
        result=[];line=''
        for char in str(value):
            if char=='\n' or pdfmetrics.stringWidth(line+char,font,size)>max_width:
                result.append(line);line='' if char=='\n' else char
            else:line+=char
        if line:result.append(line)
        return result or ['']
    def text(x,y,value,size=10,color=navy):
        pdf.setFont(font,size);pdf.setFillColor(color);pdf.drawString(x,y,str(value))
    def header(section):
        pdf.setFillColor(navy);pdf.rect(0,height-78,width,78,fill=1,stroke=0)
        text(42,height-32,package.project.name+' · '+title,17,HexColor('#FFFFFF'))
        text(42,height-55,f'{section} · Revision {revision}',10,HexColor('#DFEBFA'))
        text(42,22,'ISD Suite · '+title+' · Seite '+str(pdf.getPageNumber()),8,gray)
    header('Architekturübersicht')
    pdf.bookmarkPage('overview-'+discipline);pdf.addOutlineEntry(title,'overview-'+discipline)
    text(42,height-106,f'{len(nodes)} Elemente · {len(relations)} Beziehungen',11)
    text(42,height-128,'Legende: Rahmen = Architekturelement; Pfeil = gerichtete Beziehung; Nummer = Eintrag im Beziehungsverzeichnis.',9,gray)
    positions={};box_w=(width-124)/3
    for i,node in enumerate(nodes):
        positions[node.id]=(42+(i%3)*(box_w+20),height-254-(i//3)*120)
    for i,relation in enumerate(relations):
        if relation.source_id not in positions or relation.target_id not in positions:continue
        sx,sy=positions[relation.source_id];tx,ty=positions[relation.target_id]
        x1,y1=sx+box_w/2,sy+40;x2,y2=tx+box_w/2,ty+40
        if abs(y2-y1)<5:
            direction=1 if x2>x1 else -1;x1+=direction*box_w/2;x2-=direction*box_w/2
        else:y1+=40 if y2>y1 else -40;y2+=-40 if y2>y1 else 40
        pdf.setStrokeColor(gray);pdf.setLineWidth(1.2);pdf.line(x1,y1,x2,y2)
        distance=math.hypot(x2-x1,y2-y1)
        if distance>1:
            ux,uy=(x2-x1)/distance,(y2-y1)/distance
            pdf.line(x2,y2,x2-8*ux+4*uy,y2-8*uy-4*ux);pdf.line(x2,y2,x2-8*ux-4*uy,y2-8*uy+4*ux)
        text((x1+x2)/2+4,(y1+y2)/2+4,str(i+1),9,teal)
    for node in nodes:
        x,y=positions[node.id]
        pdf.setFillColor(HexColor('#F0FDFA'));pdf.setStrokeColor(teal);pdf.roundRect(x,y,box_w,80,7,fill=1,stroke=1)
        for i,line in enumerate(lines(node.name,box_w-24,11)[:3]):text(x+12,y+59-i*14,line,11)
        label=groups.get(getattr(node,'domain_id',None),'Externes System' if getattr(node,'external',False) else
                        'Funktions Element' if type(node).__name__=='FunctionElement' else getattr(node,'kind','Systemelement'))
        text(x+12,y+14,label,9,gray)
        pdf.linkRect('',discipline+'-'+node.id,(x,y,x+box_w,y+80),thickness=0)
    if not nodes:text(42,height-180,'Noch keine Architekturelemente angelegt.',12,gray)
    pdf.showPage();height=normal_height;pdf.setPageSize((width,height))
    # No relationships or long descriptions are silently truncated: paginated lists.
    header('Beziehungen und Realisierungszuordnungen');y=height-110
    names={n.id:n.name for n in nodes}
    items=[]
    for i,r in enumerate(relations):items.append(f'{i+1}. {r.name} [{r.kind}]: {names[r.source_id]} → {names[r.target_id]}'+(' · '+r.description if r.description else ''))
    if discipline=='system':
        from .system_architecture import allocation_targets
        targets=allocation_targets(package)
        for a in package.architecture_allocations:
            obj=targets.get((a.target_kind,a.target_id));items.append(f'Zuordnung: {names.get(a.system_element_id,a.system_element_id)} → {obj.name if obj else "Objekt fehlt: "+a.target_id}')
    else:
        realizations=package.mechanical_components if discipline=='mechanical' else package.software_components
        realnames={r.id:r.name for r in realizations}
        for node in nodes:
            for rid in node.realization_ids:items.append(f'Realisierung: {node.name} → {realnames.get(rid,"Objekt fehlt: "+rid)}')
    for item in items or ['Noch keine Beziehungen oder Realisierungszuordnungen angelegt.']:
        for line in lines(item,width-84):
            if y<58:pdf.showPage();header('Beziehungen · Fortsetzung');y=height-110
            text(42,y,line);y-=15
        y-=12
    pdf.showPage()
    for node in nodes:
        pdf.bookmarkPage(discipline+'-'+node.id);pdf.addOutlineEntry(node.name,discipline+'-'+node.id,level=1)
        header(node.name);y=height-113
        fields=[('Element',node.name),('Beschreibung',node.description or 'Offen'),('Objektkennung',node.id)]
        fields.extend(('Anforderung',r.identifier+' · '+r.title) for r in package.requirements if r.id in node.requirement_ids)
        for scope,label in [('requirement_attributes','Anforderung'),('realization_attributes','Realisierung')]:
            definitions={d.key:d for d in package.property_definitions}
            fields.extend((label+' · '+definitions[k].label,json.dumps(v,ensure_ascii=False)) for k,v in getattr(node,scope).items() if v is not None and k in definitions)
        for label,value in fields:
            for line in lines(label+': '+value,width-84):
                if y<58:pdf.showPage();header(node.name+' · Fortsetzung');y=height-113
                text(42,y,line);y-=15
            y-=10
        pdf.showPage()
    pdf.save();return stream.getvalue()
