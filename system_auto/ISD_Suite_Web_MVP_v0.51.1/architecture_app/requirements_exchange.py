"""Explicit requirements interchange profiles; SPOT remains the authoritative model."""
from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from zipfile import ZipFile

from .models import ArchitecturePackage, EcadRequirement, RequirementLevel, RequirementOrigin, RequirementSourceKind, ProjectWorkflow, utc_now
from .requirements_layers import effective_layer


FIELDS = ("identifier", "external_id", "title", "text", "requirement_level",
          "specification_level", "source_kind", "origin", "classification", "category",
          "priority", "maturity", "acceptance_criteria", "rationale", "owner",
          "review_decision", "source_locator", "parent")
LABELS = ("Identifier", "External ID", "Title", "Text", "Requirement Layer",
          "Specification Level", "Source Kind", "Origin", "Classification", "Category",
          "Priority", "Status", "Acceptance Criteria", "Rationale", "Owner",
          "Review Decision", "Source Locator", "Parent Identifier")
ALIASES = {"id": "identifier", "requirement id": "identifier", "req id": "identifier",
           "requirement": "text", "description": "text", "name": "title",
           "external id": "external_id", "status": "maturity", "parent id": "parent",
           "parent identifier": "parent", "acceptance criteria": "acceptance_criteria"}
ALIASES.update({"layer": "requirement_level", "requirement layer": "requirement_level",
                "requirement level": "requirement_level",
                "v model layer": "requirement_level", "v-modell-ebene": "requirement_level",
                "anforderungsebene": "requirement_level", "source kind": "source_kind",
                "herkunft": "origin", "verantwortlich": "owner", "fundstelle": "source_locator"})
PROFILES = {"generic": "Neutral / ISD", "doors": "DOORS Next (Feldprofil)",
            "polarion": "Polarion (Feldprofil)", "jama": "Jama Connect (Feldprofil)"}
PROFILE_LABELS = {
    "doors": {"identifier": "Object Identifier", "title": "Object Heading", "text": "Object Text"},
    "polarion": {"identifier": "ID", "text": "Description"},
    "jama": {"external_id": "Global ID", "title": "Name", "text": "Description"},
}
ALIASES.update({"object identifier": "identifier", "object heading": "title", "object text": "text",
                "global id": "external_id", "description": "text"})
REQIF_NS = "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"


@dataclass(frozen=True)
class ImportPreview:
    rows: list[dict[str, str]]
    duplicates: list[str]
    issues: list[str]
    accepted_indices: tuple[int, ...]

    @property
    def new_count(self) -> int:
        return len(self.accepted_indices)


def _keys(row: dict[str, str]) -> set[str]:
    values = {str(row.get(name) or "").casefold() for name in ("external_id", "identifier")}
    values.discard("")
    if not values:
        values.add("content:" + (row.get("title", "") + "\n" + row.get("text", "")).casefold())
    return values


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _row(raw: dict[str, object], mapping: dict[str, str] | None = None) -> dict[str, str]:
    result = {name: "" for name in FIELDS}
    for key, value in raw.items():
        mapped = (mapping or {}).get(str(key)) or ALIASES.get(_normalized(str(key))) or _normalized(str(key)).replace(" ", "_")
        if mapped in result:
            result[mapped] = str(value or "").strip()
    return result


def _reqif_rows(data: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(data)
    definitions: dict[str, str] = {}
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].startswith("ATTRIBUTE-DEFINITION"):
            definitions[element.get("IDENTIFIER", "")] = element.get("LONG-NAME", "")
    rows = []
    rows_by_object: dict[str, dict[str, str]] = {}
    for obj in root.iter():
        if obj.tag.rsplit("}", 1)[-1] != "SPEC-OBJECT":
            continue
        raw = {"External ID": obj.get("IDENTIFIER", ""), "Title": obj.get("LONG-NAME", "")}
        for attr in obj.iter():
            if not attr.tag.rsplit("}", 1)[-1].startswith("ATTRIBUTE-VALUE"):
                continue
            ref = next((child.text or "" for child in attr.iter() if child.tag.rsplit("}", 1)[-1].endswith("-REF")), "")
            name = definitions.get(ref, ref)
            value = attr.get("THE-VALUE", "")
            if not value:
                node = next((child for child in attr.iter() if child.tag.rsplit("}", 1)[-1] == "THE-VALUE"), None)
                value = " ".join(node.itertext()).strip() if node is not None else ""
            if name:
                raw[name] = value
        parsed = _row(raw)
        rows.append(parsed)
        rows_by_object[obj.get("IDENTIFIER", "")] = parsed
    for hierarchy in root.iter():
        if hierarchy.tag.rsplit("}", 1)[-1] != "SPEC-HIERARCHY":
            continue
        own_ref = next((child.text or "" for child in hierarchy.iter()
                        if child.tag.rsplit("}", 1)[-1] == "SPEC-OBJECT-REF"), "")
        for child in hierarchy:
            if child.tag.rsplit("}", 1)[-1] != "CHILDREN":
                continue
            for nested in child:
                nested_ref = next((item.text or "" for item in nested.iter()
                                   if item.tag.rsplit("}", 1)[-1] == "SPEC-OBJECT-REF"), "")
                if own_ref in rows_by_object and nested_ref in rows_by_object:
                    rows_by_object[nested_ref]["parent"] = (
                        rows_by_object[own_ref]["identifier"] or rows_by_object[own_ref]["external_id"]
                    )
    return rows


def parse_requirements(data: bytes, filename: str, mapping: dict[str, str] | None = None) -> list[dict[str, str]]:
    suffix = filename.rsplit(".", 1)[-1].casefold()
    if suffix == "csv":
        content = data.decode("utf-8-sig")
        dialect = csv.Sniffer().sniff(content[:8192], delimiters=",;\t") if content.strip() else csv.excel
        rows = [_row(record, mapping) for record in csv.DictReader(io.StringIO(content), dialect=dialect)]
        for row in rows:
            for key, value in row.items():
                if value.startswith("'") and len(value) > 1 and value[1] in "=+-@'":
                    row[key] = value[1:]
        return rows
    if suffix == "reqif":
        return _reqif_rows(data)
    if suffix == "reqifz":
        with ZipFile(io.BytesIO(data)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".reqif")]
            if not names:
                raise ValueError("ReqIF-ZIP enthält keine .reqif-Datei.")
            return _reqif_rows(archive.read(names[0]))
    if suffix == "xlsx":
        from openpyxl import load_workbook
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        try:
            rows = workbook.active.iter_rows(values_only=True)
            headers = [str(value or "") for value in next(rows)]
            return [_row(dict(zip(headers, row)), mapping) for row in rows]
        finally:
            workbook.close()
    if suffix == "docx":
        from docx import Document
        document = Document(io.BytesIO(data))
        result = []
        for table in document.tables:
            if not table.rows:
                continue
            headers = [cell.text for cell in table.rows[0].cells]
            if len(headers) == 2 and _normalized(headers[0]) == "field" and _normalized(headers[1]) == "value":
                result.append(_row({row.cells[0].text: row.cells[1].text for row in table.rows[1:]}, mapping))
            else:
                result.extend(_row(dict(zip(headers, [cell.text for cell in row.cells])), mapping) for row in table.rows[1:])
        if not result:
            raise ValueError("Word-Import erwartet eine Tabelle mit Spaltenüberschriften.")
        return result
    raise ValueError("Unterstützt: .reqif, .reqifz, .csv, .xlsx und .docx.")


def detected_columns(data: bytes, filename: str) -> list[str]:
    suffix = filename.rsplit(".", 1)[-1].casefold()
    if suffix == "csv":
        content = data.decode("utf-8-sig")
        dialect = csv.Sniffer().sniff(content[:8192], delimiters=",;\t")
        return list(csv.DictReader(io.StringIO(content), dialect=dialect).fieldnames or [])
    if suffix == "xlsx":
        from openpyxl import load_workbook
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        try:
            return [str(value or "") for value in next(workbook.active.iter_rows(values_only=True))]
        finally:
            workbook.close()
    if suffix == "docx":
        from docx import Document
        document = Document(io.BytesIO(data))
        return [cell.text for cell in document.tables[0].rows[0].cells] if document.tables else []
    if suffix in {"reqif", "reqifz"}:
        return ["ReqIF SPEC-OBJECT", "ReqIF ATTRIBUTE-DEFINITION"]
    return []


def preview_import(package: ArchitecturePackage, rows: list[dict[str, str]]) -> ImportPreview:
    existing = {key for req in package.requirements for key in _keys({
                "identifier": req.identifier, "external_id": req.external_id, "title": req.title, "text": req.text})}
    seen: set[str] = set()
    duplicates, issues = [], []
    accepted = []
    for index, row in enumerate(rows, 1):
        keys = _keys(row)
        if not row.get("text"):
            issues.append(f"Zeile {index}: Anforderungstext fehlt")
        elif keys & (existing | seen):
            duplicates.append(f"Zeile {index}: {', '.join(sorted(keys & (existing | seen)))}")
        else:
            accepted.append(index - 1)
        seen.update(keys)
    known = {key for req in package.requirements for key in (req.identifier, req.external_id) if key}
    known |= {key for row in rows for key in (row.get("identifier"), row.get("external_id")) if key}
    for index in list(accepted):
        missing = [key.strip() for key in rows[index].get("parent", "").split(";")
                   if key.strip() and key.strip() not in known]
        if missing:
            issues.append(f"Zeile {index + 1}: unbekannte Elternkennung(en): {', '.join(missing)}")
            accepted.remove(index)
    return ImportPreview(rows, duplicates, issues, tuple(accepted))


def apply_import(package: ArchitecturePackage, preview: ImportPreview, profile: str = "generic") -> int:
    if profile not in PROFILES:
        raise ValueError("Unbekanntes Austauschprofil")
    unresolved = [issue for issue in preview.issues if "unbekannte Elternkennung" in issue]
    if unresolved:
        raise ValueError("Import enthält offene Zuordnungsfehler: " + "; ".join(unresolved))
    existing = {key for req in package.requirements for key in _keys({
                "identifier": req.identifier, "external_id": req.external_id, "title": req.title, "text": req.text})}
    ids = {key: req.id for req in package.requirements
           for key in (req.identifier, req.external_id) if key}
    pending: list[tuple[EcadRequirement, str]] = []
    for index in preview.accepted_indices:
        row = preview.rows[index]
        keys = _keys(row)
        if not row.get("text") or keys & existing:
            continue
        existing.update(keys)
        identifier = row.get("identifier") or f"EXT-{len(package.requirements) + len(pending) + 1:04d}"
        if identifier in ids:
            identifier = f"EXT-{len(package.requirements) + len(pending) + 1:04d}"
        payload = {name: row[name] for name in FIELDS if name in row and row[name] and name in EcadRequirement.model_fields}
        payload.update(identifier=identifier, title=row.get("title") or identifier,
                       text=row["text"], external_id=row.get("external_id") or identifier)
        for field in ("classification", "category", "priority", "maturity",
                      "requirement_level", "specification_level", "source_kind", "origin"):
            if field in payload:
                allowed = {member.value.casefold(): member.value for member in EcadRequirement.model_fields[field].annotation}
                payload[field] = allowed.get(payload[field].casefold(), EcadRequirement.model_fields[field].default)
        if not row.get("requirement_level") and row.get("source_kind") == RequirementSourceKind.CUSTOMER_CONTRACT.value:
            payload["requirement_level"] = RequirementLevel.CUSTOMER
        payload.setdefault("origin", (RequirementOrigin.PRESCRIBED
                             if payload.get("source_kind") == RequirementSourceKind.CUSTOMER_CONTRACT
                             else RequirementOrigin.RECONSTRUCTED
                             if package.project.workflow_mode == ProjectWorkflow.REDESIGN
                             else RequirementOrigin.HYPOTHESIS
                             if package.project.workflow_mode == ProjectWorkflow.STUDY
                             else RequirementOrigin.DERIVED))
        requirement = EcadRequirement.model_validate(payload)
        requirement.properties["exchange"] = {"profile": profile, "externalId": row.get("external_id") or identifier}
        pending.append((requirement, row.get("parent", "")))
        ids[identifier] = requirement.id
    for requirement, parent in pending:
        requirement.parent_requirement_ids = list(dict.fromkeys(
            ids[key] for key in (piece.strip() for piece in parent.split(";"))
            if key in ids and ids[key] != requirement.id
        ))
    from copy import deepcopy
    from .requirement_graph import validate_graph
    candidate=deepcopy(package)
    candidate.requirements.extend(requirement for requirement,_ in pending)
    validate_graph(candidate)
    package.requirements.extend(requirement for requirement, _ in pending)
    return len(pending)


def _export_rows(package: ArchitecturePackage) -> list[dict[str, str]]:
    ids = {req.id: req.identifier for req in package.requirements}
    from .requirement_graph import derivation_edges
    edges=derivation_edges(package)
    return [{**{name: str((effective_layer(req).value if name == "requirement_level" else
                           getattr(req, name).value if hasattr(getattr(req, name), "value") else
                           getattr(req, name)) or "")
                for name in FIELDS if name != "parent"},
             "parent": "; ".join(ids.get(parent, parent) for parent in sorted(a for a,b in edges if b==req.id))}
            for req in package.requirements]


def exchange_limitations(package: ArchitecturePackage) -> list[str]:
    """Explicitly describe SPOT relationships absent from conventional tables."""
    omitted = (
        ("Normen- und Klauselverknüpfungen", package.requirement_standard_links),
        ("technische Realisierungen und Lösungsvarianten", package.technical_realizations),
        ("Architektur- und Komponentenverknüpfungen", package.requirement_links),
        ("Verifikationsfälle", package.verification_cases),
        ("Beobachtungen aus dem Bestand", package.observations),
        ("typisierte Fachbeziehungen", package.model_relations),
        ("bewertete Erfüllungen mit Kriterien und Belegen", package.fulfillment_assessments),
    )
    return [f"{len(values)} {label} verbleiben im SPOT-JSON und sind in diesem Export nicht vollständig abgebildet."
            for label, values in omitted if values]


def export_requirements(package: ArchitecturePackage, format_name: str, profile: str = "generic") -> bytes:
    if profile not in PROFILES:
        raise ValueError("Unbekanntes Austauschprofil")
    rows = _export_rows(package)
    labels = tuple(PROFILE_LABELS.get(profile, {}).get(name, label) for name, label in zip(FIELDS, LABELS))
    if format_name == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(labels)
        def safe_cell(value: str) -> str:
            return "'" + value if value.startswith(("=", "+", "-", "@", "'")) else value
        writer.writerows([safe_cell(row[name]) for name in FIELDS] for row in rows)
        return ("\ufeff" + stream.getvalue()).encode("utf-8")
    if format_name == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Requirements"
        sheet.append(labels)
        for row in rows:
            sheet.append([row[name] for name in FIELDS])
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.data_type = "s"
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="17365D")
        for col in sheet.columns:
            sheet.column_dimensions[col[0].column_letter].width = min(75, max(18, max(len(str(cell.value or "")) for cell in col) + 2))
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()
    if format_name == "docx":
        from docx import Document
        from docx.shared import RGBColor
        from docx.oxml.ns import qn
        document = Document()
        title_style = document.styles["Title"]
        title_style.font.color.rgb = RGBColor(0, 0, 0)
        properties = title_style.element.get_or_add_pPr()
        border = properties.find(qn("w:pBdr"))
        if border is not None:
            properties.remove(border)
        document.add_heading("Requirements " + package.project.name, 0)
        document.add_paragraph("Austauschprofil: " + PROFILES[profile])
        for row in rows:
            document.add_heading(row["identifier"] + " · " + row["title"], level=2)
            table = document.add_table(rows=1, cols=2)
            table.style = "Light Shading Accent 1"
            table.rows[0].cells[0].text = "Field"
            table.rows[0].cells[1].text = "Value"
            for name, label in zip(FIELDS, labels):
                cells = table.add_row().cells
                cells[0].text = label
                cells[1].text = row[name]
        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue()
    if format_name == "pdf":
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import simpleSplit
        from reportlab.pdfgen.canvas import Canvas
        buffer = io.BytesIO()
        pdf = Canvas(buffer, pagesize=A4)
        pdf.setTitle("Requirements " + package.project.name)
        w, h = A4
        y = h - 48
        pdf.setFont("Helvetica-Bold", 15)
        pdf.drawString(45, y, "Requirements · " + package.project.name[:50])
        y -= 30
        pdf.setFont("Helvetica", 9)
        pdf.drawString(45, y, "Profil: " + PROFILES[profile] + " · Review-Kopie · SPOT-JSON ist führend")
        y -= 35
        for index, row in enumerate(rows):
            lines = simpleSplit(row["text"], "Helvetica", 9, w - 95)
            needed = 58 + len(lines) * 13
            if y < needed + 40:
                pdf.showPage()
                y = h - 48
            pdf.bookmarkHorizontalAbsolute("req-" + str(index), y)
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(45, y, (row["identifier"] + " · " + row["title"])[:92])
            y -= 18
            pdf.setFont("Helvetica", 8)
            pdf.drawString(45, y, " · ".join((row["classification"], row["priority"], row["maturity"]))[:110])
            y -= 18
            pdf.setFont("Helvetica", 9)
            for line in lines:
                pdf.drawString(45, y, line)
                y -= 13
            y -= 20
        pdf.save()
        return buffer.getvalue()
    if format_name == "reqif":
        return _export_reqif(package, rows, profile)
    raise ValueError("Unbekanntes Exportformat")


def _export_reqif(package: ArchitecturePackage, rows: list[dict[str, str]], profile: str) -> bytes:
    from .requirement_graph import derivation_edges
    parents={req.id:sorted(a for a,b in derivation_edges(package) if b==req.id) for req in package.requirements}
    ET.register_namespace("", REQIF_NS)
    q = lambda name: f"{{{REQIF_NS}}}{name}"
    changed = utc_now()
    root = ET.Element(q("REQ-IF"))
    header = ET.SubElement(ET.SubElement(root, q("THE-HEADER")), q("REQ-IF-HEADER"),
                           {"IDENTIFIER": "isd-header-" + package.project.id})
    for tag, value in (("CREATION-TIME", utc_now()), ("REQ-IF-TOOL-ID", "ISD Suite"),
                       ("REQ-IF-VERSION", "1.0"), ("SOURCE-TOOL-ID", "ISD Suite"),
                       ("TITLE", package.project.name)):
        ET.SubElement(header, q(tag)).text = value
    core = ET.SubElement(ET.SubElement(root, q("CORE-CONTENT")), q("REQ-IF-CONTENT"))
    dtype = ET.SubElement(ET.SubElement(core, q("DATATYPES")), q("DATATYPE-DEFINITION-STRING"),
                          {"IDENTIFIER": "isd-string", "LONG-NAME": "String", "MAX-LENGTH": "1000000", "LAST-CHANGE": changed})
    types = ET.SubElement(core, q("SPEC-TYPES"))
    spec_type = ET.SubElement(types, q("SPEC-OBJECT-TYPE"), {"IDENTIFIER": "isd-requirement", "LONG-NAME": "Requirement", "LAST-CHANGE": changed})
    ET.SubElement(types, q("SPECIFICATION-TYPE"), {"IDENTIFIER": "isd-specification-type", "LONG-NAME": "Specification", "LAST-CHANGE": changed})
    attrs = ET.SubElement(spec_type, q("SPEC-ATTRIBUTES"))
    labels = tuple(PROFILE_LABELS.get(profile, {}).get(name, label) for name, label in zip(FIELDS, LABELS))
    for name, label in zip(FIELDS, labels):
        definition = ET.SubElement(attrs, q("ATTRIBUTE-DEFINITION-STRING"),
                                   {"IDENTIFIER": "isd-" + name, "LONG-NAME": label, "LAST-CHANGE": changed})
        ET.SubElement(ET.SubElement(definition, q("TYPE")), q("DATATYPE-DEFINITION-STRING-REF")).text = dtype.get("IDENTIFIER")
    objects = ET.SubElement(core, q("SPEC-OBJECTS"))
    specification = ET.SubElement(ET.SubElement(core, q("SPECIFICATIONS")), q("SPECIFICATION"),
                                  {"IDENTIFIER": "isd-spec", "LONG-NAME": package.project.name, "LAST-CHANGE": changed})
    ET.SubElement(ET.SubElement(specification, q("TYPE")), q("SPECIFICATION-TYPE-REF")).text = "isd-specification-type"
    children = ET.SubElement(specification, q("CHILDREN"))
    hierarchy_by_req: dict[str, ET.Element] = {}
    for req, row in zip(package.requirements, rows):
        obj = ET.SubElement(objects, q("SPEC-OBJECT"), {"IDENTIFIER": "isd-" + req.id, "LONG-NAME": req.title, "LAST-CHANGE": changed})
        ET.SubElement(ET.SubElement(obj, q("TYPE")), q("SPEC-OBJECT-TYPE-REF")).text = "isd-requirement"
        values = ET.SubElement(obj, q("VALUES"))
        for name in FIELDS:
            attr = ET.SubElement(values, q("ATTRIBUTE-VALUE-STRING"), {"THE-VALUE": row[name]})
            ET.SubElement(ET.SubElement(attr, q("DEFINITION")), q("ATTRIBUTE-DEFINITION-STRING-REF")).text = "isd-" + name
        hierarchy = ET.Element(q("SPEC-HIERARCHY"), {"IDENTIFIER": "isd-h-" + req.id, "LAST-CHANGE": changed})
        ET.SubElement(ET.SubElement(hierarchy, q("OBJECT")), q("SPEC-OBJECT-REF")).text = "isd-" + req.id
        hierarchy_by_req[req.id] = hierarchy
    for req in package.requirements:
        parent_id = next((parent for parent in parents[req.id] if parent in hierarchy_by_req), None)
        if parent_id == req.id:
            parent_id = None
        if parent_id:
            # Avoid a cyclic export if the editable source hierarchy is inconsistent.
            visited = {req.id}
            cursor = parent_id
            while cursor and cursor not in visited:
                visited.add(cursor)
                parent = next((item for item in package.requirements if item.id == cursor), None)
                cursor = next(iter(parents.get(cursor,[])), None) if parent else None
            if cursor in visited:
                parent_id = None
        if parent_id:
            nested = hierarchy_by_req[parent_id].find(q("CHILDREN"))
            if nested is None:
                nested = ET.SubElement(hierarchy_by_req[parent_id], q("CHILDREN"))
            nested.append(hierarchy_by_req[req.id])
        else:
            children.append(hierarchy_by_req[req.id])
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
