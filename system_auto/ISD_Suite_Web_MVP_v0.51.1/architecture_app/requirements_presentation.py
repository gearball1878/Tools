"""Shared requirement, source and component presentation labels."""
from __future__ import annotations
from typing import Any
from .models import ComponentLifecycle, ComponentRepresentation, EngineeringConflictResolution, EngineeringConflictStatus, EvidenceClaimStatus, RequirementCoverageStatus, RequirementLevel, RequirementSpecificationLevel, RequirementSolutionBinding, RequirementSourceKind, RequirementVerificationState, TechnicalSourceAccess, TechnicalSourceChannel, TechnicalSourceStatus, TechnicalSourceType
from .requirements_layers import LAYERS

COMPONENT_REPRESENTATION_LABELS = {
    ComponentRepresentation.LOGICAL.value: "Logische / generische Komponente",
    ComponentRepresentation.PHYSICAL.value: "Physikalisches, bestellbares Bauteil",
}

COMPONENT_LIFECYCLE_LABELS = {
    ComponentLifecycle.UNKNOWN.value: "Unbekannt",
    ComponentLifecycle.PRELIMINARY.value: "Vorläufig",
    ComponentLifecycle.ACTIVE.value: "Aktiv",
    ComponentLifecycle.NRND.value: "Nicht für Neuentwicklungen empfohlen",
    ComponentLifecycle.LAST_TIME_BUY.value: "Letzte Bestellmöglichkeit",
    ComponentLifecycle.OBSOLETE.value: "Abgekündigt",
}

SOURCE_TYPE_LABELS = {
    TechnicalSourceType.STANDARD_DOCUMENT.value: "Norm- / Standarddokument",
    TechnicalSourceType.DATASHEET.value: "Datenblatt",
    TechnicalSourceType.APPLICATION_NOTE.value: "Application Note",
    TechnicalSourceType.PRODUCT_PAGE.value: "Produktseite",
    TechnicalSourceType.USER_MANUAL.value: "Benutzerhandbuch",
    TechnicalSourceType.REFERENCE_DESIGN.value: "Referenzdesign",
    TechnicalSourceType.COMPLIANCE_DOCUMENT.value: "Konformitätsdokument",
    TechnicalSourceType.CAD_DATA.value: "CAD-/ECAD-Daten",
    TechnicalSourceType.TEST_REPORT.value: "Testbericht",
    TechnicalSourceType.BIBLIOGRAPHIC_REFERENCE.value: "Bibliografischer Nachweis",
    TechnicalSourceType.OTHER.value: "Sonstige Quelle",
}

def format_assistant_entry_for_copy(entry_type: str, entry: Any) -> str:
    """Create a complete, tool-neutral plain-text representation of one answer."""

    prompt = entry.guidance if entry_type == "architecture" else getattr(entry, "prompt", "")
    parts: list[str] = []
    if prompt:
        parts.append(f"Frage / Auftrag\n{prompt.strip()}")

    if entry_type in {"chat", "review"}:
        parts.append(f"Antwort\n{(entry.answer or '').strip()}")
        sections = (
            ("Befunde", entry.findings),
            ("Empfehlungen", entry.recommendations),
            ("Offene Fragen", entry.open_questions),
        )
        for title, values in sections:
            if values:
                parts.append(title + "\n" + "\n".join(f"- {value}" for value in values))
    elif entry_type == "change":
        parts.append(f"Auftrag\n{(entry.answer or entry.title).strip()}")
        if entry.changes:
            parts.append(
                "Vorgeschlagene Änderungen\n"
                + "\n".join(
                    f"- {item.object_type.value} {item.object_id} · {item.field_name}: "
                    f"{item.before_value or '—'} → {item.after_value}"
                    + (f" ({item.rationale})" if item.rationale else "")
                    for item in entry.changes
                )
            )
        if entry.open_questions:
            parts.append("Offene Fragen\n" + "\n".join(f"- {value}" for value in entry.open_questions))
    else:
        parts.append(
            f"Architekturauftrag\n{entry.name}\n"
            f"{len(entry.domains)} Domains · {len(entry.elements)} Architecture Elements · "
            f"{len(entry.interfaces)} Interfaces"
        )
        if entry.domains:
            parts.append("Domains\n" + "\n".join(f"- {item.name}" for item in entry.domains))
        if entry.elements:
            parts.append("Architecture Elements\n" + "\n".join(f"- {item.name}" for item in entry.elements))
        if entry.interfaces:
            parts.append("Interfaces\n" + "\n".join(f"- {item.name}" for item in entry.interfaces))
        if entry.assumptions:
            parts.append("Annahmen\n" + "\n".join(f"- {value}" for value in entry.assumptions))
        if entry.open_questions:
            parts.append("Offene Fragen\n" + "\n".join(f"- {value}" for value in entry.open_questions))
    return "\n\n".join(item for item in parts if item.strip()).strip()

SOURCE_CHANNEL_LABELS = {
    TechnicalSourceChannel.PLM.value:'PLM-System',
    TechnicalSourceChannel.ERP.value:'ERP-System',
    TechnicalSourceChannel.DMS.value:'Dokumentenmanagement (DMS)',
    TechnicalSourceChannel.WEB_LINK.value: "Weblink",
    TechnicalSourceChannel.FILE_UPLOAD.value: "Lokaler Dokument-Upload",
    TechnicalSourceChannel.STANDARDS_ORGANIZATION.value: "Normungsorganisation",
    TechnicalSourceChannel.LICENSE_PORTAL.value: "Normen- / Lizenzportal",
    TechnicalSourceChannel.MANUFACTURER_PORTAL.value: "Herstellerportal",
    TechnicalSourceChannel.DISTRIBUTOR.value: "Distributor",
    TechnicalSourceChannel.COMPONENT_DATABASE.value: "Bauteildatenbank",
    TechnicalSourceChannel.API.value: "API",
    TechnicalSourceChannel.CONNECTOR.value: "Konfigurierter Connector",
    TechnicalSourceChannel.INTERNAL_REPOSITORY.value: "Internes DMS / PLM / Repository",
    TechnicalSourceChannel.OTHER.value: "Anderer Kanal",
}

SOURCE_ACCESS_LABELS = {
    TechnicalSourceAccess.PUBLIC.value: "Öffentlich",
    TechnicalSourceAccess.LOGIN_REQUIRED.value: "Anmeldung erforderlich",
    TechnicalSourceAccess.LICENSED.value: "Lizenzpflichtig",
    TechnicalSourceAccess.NDA_RESTRICTED.value: "NDA / eingeschränkt",
    TechnicalSourceAccess.INTERNAL.value: "Intern",
}

SOURCE_STATUS_LABELS = {
    TechnicalSourceStatus.CANDIDATE.value: "Kandidat",
    TechnicalSourceStatus.AVAILABLE.value: "Verfügbar",
    TechnicalSourceStatus.VERIFIED.value: "Geprüft",
    TechnicalSourceStatus.SUPERSEDED.value: "Ersetzt",
    TechnicalSourceStatus.UNAVAILABLE.value: "Nicht verfügbar",
}

CLAIM_STATUS_LABELS = {
    EvidenceClaimStatus.UNASSESSED.value: "Noch nicht bewertet",
    EvidenceClaimStatus.MANUFACTURER_CLAIM.value: "Herstellerangabe",
    EvidenceClaimStatus.REVIEWED.value: "Quelle fachlich geprüft",
    EvidenceClaimStatus.DESIGN_VERIFIED.value: "Im eigenen Design nachgewiesen",
    EvidenceClaimStatus.REJECTED.value: "Nachweis verworfen",
}

SPECIFICATION_LEVEL_LABELS = {
    RequirementSpecificationLevel.CUSTOMER_SPECIFICATION.value: "Lastenheft / Auftraggeberanforderung",
    RequirementSpecificationLevel.DESIGN_SPECIFICATION.value: "Pflichtenheft / technische Ableitung",
    RequirementSpecificationLevel.IMPLEMENTATION_CONSTRAINT.value: "Implementierungsrandbedingung",
}

REQUIREMENT_LEVEL_LABELS = {
    RequirementLevel.CUSTOMER.value: "L1 · Kunden-/Lastenheftanforderung",
    RequirementLevel.SYSTEM.value: "Systemanforderung",
    RequirementLevel.TECHNICAL.value: "L3 · Technische Anforderung",
    RequirementLevel.DISCIPLINE.value: "L4 · Disziplinanforderung",
    RequirementLevel.REALIZATION.value: "Realisierungsanforderung",
    RequirementLevel.COMPONENT.value: "Komponentenanforderung",
}

LAYER_CHOICE_LABELS = {
    layer.value: f"{number} · {title}" for number, title, layer in LAYERS
}

SOLUTION_BINDING_LABELS = {
    RequirementSolutionBinding.SOLUTION_NEUTRAL.value: "Lösungsneutral",
    RequirementSolutionBinding.DESIGN_CONSTRAINT.value: "Designvorgabe / Randbedingung",
    RequirementSolutionBinding.IMPLEMENTATION_MANDATE.value: "Verbindliche konkrete Umsetzung",
}

SOURCE_KIND_LABELS = {
    RequirementSourceKind.CUSTOMER_CONTRACT.value: "Kunde / Vertrag",
    RequirementSourceKind.STANDARD_REGULATION.value: "Norm / Regulierung",
    RequirementSourceKind.ENGINEERING_DERIVATION.value: "Technische Ableitung",
    RequirementSourceKind.DESIGN_DECISION.value: "Designentscheidung",
    RequirementSourceKind.EXISTING_DESIGN.value: "Bestehendes Design",
    RequirementSourceKind.INTERNAL_MANUAL.value: "Intern / manuell",
}

COVERAGE_LABELS = {
    RequirementCoverageStatus.NOT_APPLICABLE.value: "Nicht anwendbar",
    RequirementCoverageStatus.REALIZATION_GAP.value: "Realisierungslücke",
    RequirementCoverageStatus.PARTIAL.value: "Ableitung / Zuordnung vorhanden · Bewertung offen",
    RequirementCoverageStatus.COVERED.value: "Technisch erfüllt · bewertet",
    RequirementCoverageStatus.CONFLICT.value: "Konflikt",
}

VERIFICATION_STATE_LABELS = {
    RequirementVerificationState.STALE.value: 'Nachweis erneut prüfen',
    RequirementVerificationState.NOT_DEFINED.value: "Kein Test definiert",
    RequirementVerificationState.DEFINED.value: "Test definiert",
    RequirementVerificationState.PASSED.value: "Verifiziert",
    RequirementVerificationState.FAILED.value: "Verifikation fehlgeschlagen",
    RequirementVerificationState.BLOCKED.value: "Verifikation blockiert",
}

CONFLICT_STATUS_LABELS = {
    EngineeringConflictStatus.OPEN.value: "Offen",
    EngineeringConflictStatus.IN_REVIEW.value: "In Klärung",
    EngineeringConflictStatus.RESOLVED.value: "Gelöst",
    EngineeringConflictStatus.ACCEPTED_DEVIATION.value: "Abweichung akzeptiert",
}

CONFLICT_RESOLUTION_LABELS = {
    EngineeringConflictResolution.UNDECIDED.value: "Noch nicht entschieden",
    EngineeringConflictResolution.CHANGE_REQUIREMENT.value: "Requirement ändern",
    EngineeringConflictResolution.CHANGE_SOLUTION.value: "Technische Lösung ändern",
    EngineeringConflictResolution.CHANGE_CONSTRAINT.value: "Randbedingung ändern",
    EngineeringConflictResolution.ACCEPT_DEVIATION.value: "Abweichung akzeptieren",
    EngineeringConflictResolution.REJECT_REQUIREMENT.value: "Requirement verwerfen",
}

MAX_AI_DOCUMENT_CONTEXT_CHARACTERS = 120_000

MAX_AI_CHARACTERS_PER_DOCUMENT = 50_000

MAX_DOCUMENT_PREVIEW_CHARACTERS = 120_000

