from __future__ import annotations

from .architecture_compilation import compile_architecture_proposal, _compile_architecture_proposal_in_place
from .realization_service import synchronize_realization_architecture_attribute
from .interface_compilation import CompilationSummary, DOMAIN_COLORS, DEFAULT_ARCHITECTURE_CATALOG

from dataclasses import dataclass
from pathlib import Path
import re
import json

from .ai_provider import AIChangeProposalResult, AIConsultationResult, ArchitectureSynthesisResult, DocumentAnalysisResult
from .bus_content import BusContentTemplates
from .document_ingestion import ExtractedDocument
from .models import AIChangeItem, AIChangeItemStatus, AIChangeObjectType, AIChangeProposal, AnalysisComponentCandidate, AnalysisComponentNeedCandidate, AnalysisArchitectureDomainCandidate, AnalysisArchitectureElementCandidate, AnalysisArchitectureInterfaceCandidate, AnalysisInterfaceCandidate, AnalysisRequirementCandidate, AnalysisSoftwareComponentCandidate, AnalysisTechnicalRealizationCandidate, AnalysisVerificationCandidate, AnalysisStandardCandidate, ArchitecturePackage, ArchitectureProposal, AIReview, ComponentCandidateKind, ComponentDecisionType, ComponentLifecycle, ComponentRepresentation, ComponentVerification, ComponentRoleInRealization, ComponentRequirement, ConnectionType, DesignMaturity, DesignComponent, DocumentAnalysisRevision, DocumentAnalysisStage, DocumentAnalysisStatus, Direction, EcadRequirement, EngineeringConflictStatus, InterfaceMemberDefinition, InterfaceRequirement, ProjectInterfaceTemplate, ProjectWorkflow, ProposedDomain, ProposedElement, ProposedInterface, ProposalStatus, RequirementLink, RequirementCategory, RequirementClassification, RequirementDerivation, RequirementEcadRelevance, RequirementCoverageStatus, RequirementLevel, RequirementMaturity, RequirementOrigin, RequirementPriority, RequirementSolutionBinding, RequirementSourceKind, RequirementSpecificationLevel, RealizationComponentRole, RequirementRelation, RequirementStandardLink, RequirementTargetType, RequirementVerificationState, RealizationProvenance, SoftwareComponent, StandardReference, StandardApplicability, SubstitutionPolicy, SolutionVariant, SolutionVariantStatus, SignalType, SourceDocument, TechnicalSource, TechnicalRealization, TechnicalRealizationStatus, TestDefinitionStatus, TestExecutionStatus, VerificationCase, VerificationStatus, CandidateReviewStatus, utc_now
from .traceability import assessment_current, verification_status, canonical_kind, remove_deleted_references
from .requirement_graph import derivation_edges, allocation_edges, test_requirement_ids




REQUIREMENT_CLASSIFICATION_CODES = {
    RequirementClassification.SYSTEM: "SYS",
    RequirementClassification.HARDWARE: "HW",
    RequirementClassification.MECHANICS: "MEC",
    RequirementClassification.SOFTWARE: "SW",
    RequirementClassification.FIRMWARE: "FW",
}

REQUIREMENT_CATEGORY_CODES = {
    RequirementCategory.FUNCTION: "FUN",
    RequirementCategory.INTERFACE: "IF",
    RequirementCategory.DATA: "DAT",
    RequirementCategory.POWER: "PWR",
    RequirementCategory.CLOCK_RESET: "CLK",
    RequirementCategory.ANALOG: "ANA",
    RequirementCategory.CONTROL_STATUS: "CTRL",
    RequirementCategory.DIAGNOSTIC_TEST: "TST",
    RequirementCategory.PERFORMANCE: "PERF",
    RequirementCategory.SAFETY_REDUNDANCY: "SAFE",
    RequirementCategory.ENVIRONMENT: "ENV",
    RequirementCategory.INTEGRATION: "INT",
    RequirementCategory.RELIABILITY_AVAILABILITY: "RAM",
    RequirementCategory.SECURITY: "SEC",
    RequirementCategory.THERMAL: "THM",
    RequirementCategory.COMPLIANCE: "COMP",
    RequirementCategory.LIFECYCLE: "LIFE",
    RequirementCategory.SCHEMATIC: "SCH",
    RequirementCategory.UNCLASSIFIED: "GEN",
}


def requirement_identifier_prefix(
    classification: RequirementClassification,
    category: RequirementCategory,
) -> str:
    return f"{REQUIREMENT_CLASSIFICATION_CODES[classification]}-{REQUIREMENT_CATEGORY_CODES[category]}"


def next_requirement_identifier(
    package: ArchitecturePackage,
    classification: RequirementClassification,
    category: RequirementCategory,
) -> str:
    prefix = requirement_identifier_prefix(classification, category)
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$", re.IGNORECASE)
    numbers = [
        int(match.group(1))
        for requirement in package.requirements
        if (match := pattern.match(requirement.identifier.strip()))
    ]
    return f"{prefix}-{max(numbers, default=0) + 1:04d}"


def ensure_requirement_identifiers(package: ArchitecturePackage) -> bool:
    changed = False
    for requirement in package.requirements:
        if not requirement.identifier.strip():
            requirement.identifier = next_requirement_identifier(
                package,
                requirement.classification,
                requirement.category,
            )
            changed = True
    return changed


def next_verification_identifier(package: ArchitecturePackage) -> str:
    pattern = re.compile(r"^VER-(\d+)$", re.IGNORECASE)
    numbers = [
        int(match.group(1))
        for verification in package.verification_cases
        if (match := pattern.match(verification.identifier.strip()))
    ]
    return f"VER-{max(numbers, default=0) + 1:04d}"


def ensure_verification_identifiers(package: ArchitecturePackage) -> bool:
    changed = False
    for verification in package.verification_cases:
        if not verification.identifier.strip():
            verification.identifier = next_verification_identifier(package)
            changed = True
    return changed


def is_test_defined(verification: VerificationCase) -> bool:
    """Return true only for a usable, requirement-related test definition.

    Execution is deliberately irrelevant here: the question is whether a test has
    already been written, not whether it has been run or passed.
    """
    return bool(
        verification.execution_status != TestExecutionStatus.OBSOLETE
        and verification.definition_status in {
            TestDefinitionStatus.DEFINED,
            TestDefinitionStatus.APPROVED,
        }
        and verification.requirement_ids
        and verification.objective.strip()
        and verification.procedure.strip()
        and verification.expected_result.strip()
    )


def defined_test_requirement_ids(package: ArchitecturePackage) -> set[str]:
    return {
        requirement_id
        for verification in package.verification_cases
        if is_test_defined(verification)
        for requirement_id in test_requirement_ids(package,verification)
    }


@dataclass(frozen=True)
class RequirementTraceabilityStatus:
    requirement_id: str
    coverage: RequirementCoverageStatus
    verification: RequirementVerificationState
    derived_requirement_ids: tuple[str, ...] = ()
    realization_ids: tuple[str, ...] = ()
    target_count: int = 0
    covered_disciplines: tuple[RequirementClassification, ...] = ()
    missing_disciplines: tuple[RequirementClassification, ...] = ()
    open_conflict_count: int = 0

    @property
    def fulfilled(self) -> bool:
        return (
            self.coverage == RequirementCoverageStatus.COVERED
            and self.verification == RequirementVerificationState.PASSED
        )


def requirement_traceability_status(
    package: ArchitecturePackage,
    requirement: EcadRequirement,
    _visiting: set[str] | None = None,
    _memo: dict[str, RequirementTraceabilityStatus] | None = None,
) -> RequirementTraceabilityStatus:
    """Calculate realization and verification independently from review maturity."""
    memo = _memo if _memo is not None else {}
    cached = memo.get(requirement.id)
    if cached is not None:
        return cached
    visiting = set(_visiting or set())
    if requirement.id in visiting:
        return RequirementTraceabilityStatus(
            requirement.id,
            RequirementCoverageStatus.CONFLICT,
            RequirementVerificationState.NOT_DEFINED,
            open_conflict_count=1,
        )
    visiting.add(requirement.id)

    active_conflicts = [
        item for item in package.engineering_conflicts
        if requirement.id in item.requirement_ids
        and item.status in {
            EngineeringConflictStatus.OPEN,
            EngineeringConflictStatus.IN_REVIEW,
        }
    ]
    state = verification_status(package,requirement)
    verification = {
        'Failed':RequirementVerificationState.FAILED,'Blocked':RequirementVerificationState.BLOCKED,
        'Verified':RequirementVerificationState.PASSED,'Stale':RequirementVerificationState.STALE,
        'Test Defined':RequirementVerificationState.DEFINED,'No Test':RequirementVerificationState.NOT_DEFINED,
    }[state]
    derived_ids = {child for parent,child in derivation_edges(package) if parent==requirement.id}
    children = [
        item for item in package.requirements
        if item.id in derived_ids
        and item.maturity not in {RequirementMaturity.REJECTED, RequirementMaturity.OBSOLETE}
    ]
    direct_targets = {(canonical_kind(kind),oid) for rid,kind,oid in allocation_edges(package) if rid==requirement.id}
    realization_ids = {oid for kind,oid in direct_targets if kind=='Realization' and any(
        real.id==oid and real.status!=TechnicalRealizationStatus.REJECTED for real in package.technical_realizations)}
    child_results = [requirement_traceability_status(package, child, visiting, memo)
                     for child in children]
    covered_disciplines = tuple(sorted(
        ({item.classification for item in children if item.classification != RequirementClassification.SYSTEM}
         | {discipline for result in child_results for discipline in result.covered_disciplines}),
        key=lambda item: item.value,
    ))
    required_disciplines = {
        item for item in requirement.required_disciplines
        if item != RequirementClassification.SYSTEM
    }
    missing_disciplines = tuple(sorted(
        required_disciplines - set(covered_disciplines), key=lambda item: item.value
    ))

    successful_assessment = any(
        item.requirement_id == requirement.id and item.result == "Passed"
        and item.status == "Reviewed" and assessment_current(package, item)
        for item in package.fulfillment_assessments
    )
    if requirement.maturity in {RequirementMaturity.REJECTED, RequirementMaturity.OBSOLETE}:
        coverage = RequirementCoverageStatus.NOT_APPLICABLE
    elif active_conflicts:
        coverage = RequirementCoverageStatus.CONFLICT
    elif successful_assessment and not missing_disciplines and all(
        result.coverage == RequirementCoverageStatus.COVERED for result in child_results
    ):
        coverage = RequirementCoverageStatus.COVERED
    else:
        coverage = (
            RequirementCoverageStatus.PARTIAL
            if direct_targets or children
            else RequirementCoverageStatus.REALIZATION_GAP
        )

    result = RequirementTraceabilityStatus(
        requirement_id=requirement.id,
        coverage=coverage,
        verification=verification,
        derived_requirement_ids=tuple(sorted(derived_ids)),
        realization_ids=tuple(sorted(realization_ids)),
        target_count=len(direct_targets),
        covered_disciplines=covered_disciplines,
        missing_disciplines=missing_disciplines,
        open_conflict_count=len(active_conflicts),
    )
    memo[requirement.id] = result
    return result


def requirement_traceability_index(
    package: ArchitecturePackage,
) -> dict[str, RequirementTraceabilityStatus]:
    """Calculate every status once for responsive list and overview rendering."""
    memo: dict[str, RequirementTraceabilityStatus] = {}
    for requirement in package.requirements:
        requirement_traceability_status(package, requirement, _memo=memo)
    return memo


def synchronize_verification_status(verification: VerificationCase) -> None:
    """Keep the legacy status field useful for v5 consumers."""
    execution_mapping = {
        TestExecutionStatus.PASSED: VerificationStatus.PASSED,
        TestExecutionStatus.FAILED: VerificationStatus.FAILED,
        TestExecutionStatus.BLOCKED: VerificationStatus.BLOCKED,
        TestExecutionStatus.OBSOLETE: VerificationStatus.OBSOLETE,
    }
    if verification.execution_status in execution_mapping:
        verification.status = execution_mapping[verification.execution_status]
    elif verification.definition_status == TestDefinitionStatus.APPROVED:
        verification.status = VerificationStatus.READY
    elif verification.definition_status == TestDefinitionStatus.DEFINED:
        verification.status = VerificationStatus.DEFINED
    else:
        verification.status = VerificationStatus.PLANNED




def synchronize_all_realization_attributes(package: ArchitecturePackage) -> None:
    for realization in package.technical_realizations:
        synchronize_realization_architecture_attribute(package, realization)


def migrate_requirements_model(package: ArchitecturePackage) -> bool:
    changed = package.schema_version != "isd-suite/v3"
    package.schema_version = "isd-suite/v3"
    if not package.system_definition.core_idea.strip() and package.project.description.strip():
        package.system_definition.core_idea = package.project.description.strip()
        changed = True
    if "electronicsArchitectureMaturity" not in package.project.attributes:
        package.project.attributes["electronicsArchitectureMaturity"] = "Working"
        changed = True
    for requirement in package.requirements:
        if "specification_level" not in requirement.model_fields_set:
            requirement.specification_level = (
                RequirementSpecificationLevel.CUSTOMER_SPECIFICATION
                if requirement.origin == RequirementOrigin.DOCUMENT
                else RequirementSpecificationLevel.DESIGN_SPECIFICATION
            )
            changed = True
        if "requirement_level" not in requirement.model_fields_set:
            requirement.requirement_level = (
                RequirementLevel.CUSTOMER
                if requirement.specification_level == RequirementSpecificationLevel.CUSTOMER_SPECIFICATION
                else RequirementLevel.DISCIPLINE
            )
            changed = True
        if "solution_binding" not in requirement.model_fields_set:
            requirement.solution_binding = (
                RequirementSolutionBinding.DESIGN_CONSTRAINT
                if requirement.specification_level == RequirementSpecificationLevel.IMPLEMENTATION_CONSTRAINT
                else RequirementSolutionBinding.SOLUTION_NEUTRAL
            )
            changed = True
        if "source_kind" not in requirement.model_fields_set:
            requirement.source_kind = {
                RequirementOrigin.DOCUMENT: RequirementSourceKind.CUSTOMER_CONTRACT,
                RequirementOrigin.DERIVED: RequirementSourceKind.ENGINEERING_DERIVATION,
                RequirementOrigin.AI_PROPOSAL: RequirementSourceKind.ENGINEERING_DERIVATION,
            }.get(requirement.origin, RequirementSourceKind.INTERNAL_MANUAL)
            changed = True
    for verification in package.verification_cases:
        previous = verification.status
        synchronize_verification_status(verification)
        changed = changed or previous != verification.status
    synchronize_all_realization_attributes(package)
    return changed


@dataclass(frozen=True)
class AnalysisImportSummary:
    document_id: str
    stage: DocumentAnalysisStage
    requirement_count: int
    interface_count: int
    component_need_count: int
    component_count: int
    software_component_count: int
    standard_count: int
    realization_count: int
    verification_count: int
    open_questions: tuple[str, ...]


@dataclass(frozen=True)
class DocumentContextRecoverySummary:
    document_id: str
    file_name: str
    page_count: int | None
    character_count: int
    section_count: int


def validate_document_context_recovery(
    source: SourceDocument,
    extracted: ExtractedDocument,
) -> None:
    expected_checksum = source.checksum_sha256.strip().casefold()
    actual_checksum = extracted.checksum_sha256.strip().casefold()
    if not expected_checksum:
        raise ValueError(
            "Der Legacy-Dokumenteintrag besitzt keine Prüfsumme. Eine sichere automatische Zuordnung ist nicht möglich."
        )
    if expected_checksum != actual_checksum:
        raise ValueError(
            "Die ausgewählte Datei stimmt nicht mit dem ursprünglichen Quelldokument überein "
            f"(erwartet {expected_checksum[:12]}…, erhalten {actual_checksum[:12]}…)."
        )


def recover_document_context_metadata(
    package: ArchitecturePackage,
    document_id: str,
    extracted: ExtractedDocument,
    *,
    attachment_path: str,
    attachment_size: int,
    context_path: str,
    context_checksum_sha256: str,
) -> DocumentContextRecoverySummary:
    """Attach verified source bytes and extracted context without running an AI analysis."""
    source = next((item for item in package.source_documents if item.id == document_id), None)
    if source is None:
        raise ValueError("Das Quelldokument gehört nicht zu diesem Projekt.")
    validate_document_context_recovery(source, extracted)
    if not attachment_path or not context_path or not context_checksum_sha256:
        raise ValueError("Originaldokument und extrahierter Kontext müssen vollständig gespeichert sein.")

    recovered_at = utc_now()
    source.file_name = extracted.file_name
    source.media_type = extracted.media_type
    source.attachment_path = attachment_path
    source.attachment_size = attachment_size
    source.context_path = context_path
    source.context_checksum_sha256 = context_checksum_sha256
    source.context_section_count = len(extracted.sections)
    source.context_updated_at = recovered_at
    source.page_count = extracted.page_count
    source.character_count = extracted.character_count
    source.properties["contextRecovery"] = {
        "mode": "Verified source reattachment without AI",
        "recoveredAt": recovered_at,
        "sourceChecksumSha256": extracted.checksum_sha256.strip().casefold(),
        "analysisCreated": False,
    }
    return DocumentContextRecoverySummary(
        document_id=source.id,
        file_name=source.file_name,
        page_count=source.page_count,
        character_count=source.character_count,
        section_count=source.context_section_count,
    )


def link_legacy_requirements_to_document(
    package: ArchitecturePackage,
    document_id: str,
    requirement_ids: list[str],
) -> int:
    if not any(item.id == document_id for item in package.source_documents):
        raise ValueError("Das Quelldokument gehört nicht zu diesem Projekt.")
    selected_ids = set(requirement_ids)
    if not selected_ids:
        raise ValueError("Es wurden keine Requirements zur Quellenzuordnung ausgewählt.")
    targets = [item for item in package.requirements if item.id in selected_ids]
    if len(targets) != len(selected_ids):
        raise ValueError("Mindestens ein ausgewähltes Requirement gehört nicht zu diesem Projekt.")
    if any(item.source_document_id and item.source_document_id != document_id for item in targets):
        raise ValueError("Mindestens ein Requirement ist bereits einem anderen Quelldokument zugeordnet.")
    assigned_at = utc_now()
    for requirement in targets:
        requirement.source_document_id = document_id
        requirement.properties["legacySourceAssignment"] = {
            "assignedAt": assigned_at,
            "sourceDocumentId": document_id,
            "reviewConfirmed": True,
        }
    return len(targets)


def approve_legacy_document_requirements(
    package: ArchitecturePackage,
    document_id: str,
    requirement_ids: list[str],
) -> int:
    if not any(item.id == document_id for item in package.source_documents):
        raise ValueError("Das Quelldokument gehört nicht zu diesem Projekt.")
    selected_ids = set(requirement_ids)
    if not selected_ids:
        raise ValueError("Es wurden keine Requirements zur Freigabe ausgewählt.")
    targets = [item for item in package.requirements if item.id in selected_ids]
    if len(targets) != len(selected_ids):
        raise ValueError("Mindestens ein ausgewähltes Requirement gehört nicht zu diesem Projekt.")
    if any(item.source_document_id != document_id for item in targets):
        raise ValueError("Mindestens ein Requirement ist nicht mit diesem Quelldokument verknüpft.")
    if any(item.ecad_relevance == RequirementEcadRelevance.BACKLOG_ONLY for item in targets):
        raise ValueError("Backlog-Only-Requirements können nicht für die technische Ableitung freigegeben werden.")
    allowed_states = {RequirementMaturity.DETECTED, RequirementMaturity.IN_REVIEW}
    if any(item.maturity not in allowed_states for item in targets):
        raise ValueError("Mindestens ein Requirement besitzt keinen freigabefähigen Reifegrad.")
    approved_at = utc_now()
    for requirement in targets:
        requirement.maturity = RequirementMaturity.APPROVED
        requirement.properties["legacyApproval"] = {
            "approvedAt": approved_at,
            "sourceDocumentId": document_id,
            "reviewConfirmed": True,
        }
    return len(targets)


@dataclass(frozen=True)
class AnalysisCompilationSummary:
    requirement_count: int = 0
    interface_count: int = 0
    component_need_count: int = 0
    component_count: int = 0
    software_component_count: int = 0
    standard_count: int = 0
    realization_count: int = 0
    verification_count: int = 0
    architecture_proposal_count: int = 0
    architecture_domain_count: int = 0
    architecture_element_count: int = 0
    architecture_signal_count: int = 0




def interface_catalog_names(package: ArchitecturePackage, builtins: BusContentTemplates) -> list[str]:
    names = builtins.interface_templates()
    names.extend(item.name for item in package.interface_templates if not item.deprecated)
    return list(dict.fromkeys(names))


def clone_builtin_interface_template(
    builtins: BusContentTemplates,
    template_name: str,
    new_name: str | None = None,
) -> ProjectInterfaceTemplate:
    resolved = builtins.resolve_interface_template(template_name)
    if resolved is None:
        raise ValueError("Die Interfacevorlage wurde nicht gefunden.")
    name = (new_name or resolved.replace("_[Link/Port]", "").replace("[Link/Port]", "")).strip(" _")
    instance = builtins.named_interface_signals(resolved, "{interface}")
    return ProjectInterfaceTemplate(
        name=name,
        port_type=name,
        signal_type=SignalType.INTERFACE,
        connection_type=ConnectionType.BUS,
        aliases=[resolved],
        members=[
            InterfaceMemberDefinition(
                name_pattern=member_name,
                direction_from_host=Direction.INOUT,
                host_pin_type="BI",
                participant_pin_type="BI",
                active_low=member_name.endswith("#") or member_name.endswith("_N"),
            )
            for member_name in instance.signals
        ],
        properties={"clonedFrom": resolved},
    )


def add_document_analysis(
    package: ArchitecturePackage,
    document: ExtractedDocument,
    analysis: DocumentAnalysisResult,
    provider: str,
    model: str,
    analysis_prompt: str = "",
    stage: DocumentAnalysisStage = DocumentAnalysisStage.REQUIREMENTS,
) -> AnalysisImportSummary:
    source = next(
        (item for item in package.source_documents if item.checksum_sha256 == document.checksum_sha256),
        None,
    )
    if source is None:
        source = SourceDocument(
            name=Path(document.file_name).stem,
            file_name=document.file_name,
            media_type=document.media_type,
            checksum_sha256=document.checksum_sha256,
            page_count=document.page_count,
            character_count=document.character_count,
        )
        package.source_documents.append(source)

    existing_revisions = [item.revision_number for item in package.document_analyses if item.document_id == source.id]
    revision_number = max(existing_revisions, default=0) + 1
    requirement_key_map = {
        item.candidate_key: f"REQ:{item.candidate_key}" for item in analysis.requirements
    }
    component_need_key_map = {
        item.candidate_key: f"NEED:{item.candidate_key}" for item in analysis.component_needs
    }
    interface_key_map = {
        item.candidate_key: f"IF:{item.candidate_key}" for item in analysis.interfaces
    }
    standard_key_map = {
        item.candidate_key: f"STD:{item.candidate_key}" for item in analysis.standards
    }
    component_key_map = {
        item.candidate_key: f"CMP:{item.candidate_key}" for item in analysis.components
    }
    software_component_key_map = {
        item.candidate_key: f"SWCMP:{item.candidate_key}" for item in analysis.software_components
    }
    realization_key_map = {
        item.candidate_key: f"REAL:{item.candidate_key}" for item in analysis.technical_realizations
    }
    architecture_domain_key_map = {
        item.candidate_key: f"ADOM:{item.candidate_key}" for item in analysis.architecture_domains
    }
    architecture_element_key_map = {
        item.candidate_key: f"AEL:{item.candidate_key}" for item in analysis.architecture_elements
    }
    architecture_interface_key_map = {
        item.candidate_key: f"AIF:{item.candidate_key}" for item in analysis.architecture_interfaces
    }
    existing_requirement_refs = {
        reference: requirement.id
        for requirement in package.requirements
        for reference in (requirement.id, requirement.identifier)
        if reference
    }
    existing_need_refs = {item.id: item.id for item in package.component_requirements}
    existing_interface_refs = {item.id: item.id for item in package.interface_requirements}
    existing_component_refs = {item.id: item.id for item in package.components}
    existing_software_component_refs = {item.id: item.id for item in package.software_components}
    existing_standard_refs = {item.id: item.id for item in package.standards}
    existing_realization_refs = {item.id: item.id for item in package.technical_realizations}

    def requirement_reference(value: str) -> str:
        if value in requirement_key_map:
            return requirement_key_map[value]
        if value in existing_requirement_refs:
            return existing_requirement_refs[value]
        return f"REQ:{value}"

    def object_reference(
        value: str,
        candidate_map: dict[str, str],
        existing_map: dict[str, str],
        prefix: str,
    ) -> str:
        if value in candidate_map:
            return candidate_map[value]
        if value in existing_map:
            return existing_map[value]
        return f"{prefix}:{value}"

    def fresh_candidate_values(candidate: object) -> dict[str, object]:
        values = candidate.model_dump(mode="json")
        values.pop("id", None)
        values["review_status"] = CandidateReviewStatus.OPEN.value
        values["committed_object_id"] = None
        return values
    requirement_candidates = []
    for candidate in analysis.requirements:
        values = fresh_candidate_values(candidate)
        values["candidate_key"] = requirement_key_map[candidate.candidate_key]
        values["derived_from_keys"] = [
            requirement_reference(item) for item in candidate.derived_from_keys
        ]
        requirement_candidates.append(AnalysisRequirementCandidate.model_validate(values))
    interface_candidates = []
    for candidate in analysis.interfaces:
        values = fresh_candidate_values(candidate)
        values["candidate_key"] = interface_key_map[candidate.candidate_key]
        values["requirement_keys"] = [
            requirement_reference(item) for item in candidate.requirement_keys
        ]
        values["standard_keys"] = [
            object_reference(item, standard_key_map, existing_standard_refs, "STD")
            for item in candidate.standard_keys
        ]
        interface_candidates.append(AnalysisInterfaceCandidate.model_validate(values))
    component_need_candidates = []
    for candidate in analysis.component_needs:
        values = fresh_candidate_values(candidate)
        values["candidate_key"] = component_need_key_map[candidate.candidate_key]
        values["requirement_keys"] = [
            requirement_reference(item) for item in candidate.requirement_keys
        ]
        component_need_candidates.append(AnalysisComponentNeedCandidate.model_validate(values))
    component_candidates = []
    for candidate in analysis.components:
        values = fresh_candidate_values(candidate)
        values["candidate_key"] = component_key_map[candidate.candidate_key]
        if candidate.manufacturer_part_number.strip():
            values["candidate_kind"] = ComponentCandidateKind.A_PART.value
        values["requirement_keys"] = [
            requirement_reference(item) for item in candidate.requirement_keys
        ]
        values["component_need_keys"] = [
            object_reference(item, component_need_key_map, existing_need_refs, "NEED")
            for item in candidate.component_need_keys
        ]
        values["interface_keys"] = [
            object_reference(item, interface_key_map, existing_interface_refs, "IF")
            for item in candidate.interface_keys
        ]
        values["alternative_component_keys"] = [
            object_reference(item, component_key_map, existing_component_refs, "CMP")
            for item in candidate.alternative_component_keys
        ]
        component_candidates.append(AnalysisComponentCandidate.model_validate(values))
    software_component_candidates = []
    for candidate in analysis.software_components:
        values = fresh_candidate_values(candidate)
        values["candidate_key"] = software_component_key_map[candidate.candidate_key]
        values["requirement_keys"] = [
            requirement_reference(item) for item in candidate.requirement_keys
        ]
        values["interface_keys"] = [
            object_reference(item, interface_key_map, existing_interface_refs, "IF")
            for item in candidate.interface_keys
        ]
        software_component_candidates.append(
            AnalysisSoftwareComponentCandidate.model_validate(values)
        )
    standard_candidates = []
    for candidate in analysis.standards:
        values = fresh_candidate_values(candidate)
        values["candidate_key"] = standard_key_map[candidate.candidate_key]
        values["requirement_keys"] = [
            requirement_reference(item) for item in candidate.requirement_keys
        ]
        standard_candidates.append(AnalysisStandardCandidate.model_validate(values))
    realization_candidates = []
    for candidate in analysis.technical_realizations:
        values = fresh_candidate_values(candidate)
        values["candidate_key"] = realization_key_map[candidate.candidate_key]
        values["requirement_keys"] = [
            requirement_reference(item) for item in candidate.requirement_keys
        ]
        variants: list[dict[str, object]] = []
        for variant in candidate.variants:
            variant_values = variant.model_dump(mode="json")
            variant_values.pop("id", None)
            variant_values["candidate_key"] = f"RVAR:{candidate.candidate_key}:{variant.candidate_key}"
            variant_values["a_part_component_key"] = component_key_map.get(
                variant.a_part_component_key,
                existing_component_refs.get(variant.a_part_component_key, variant.a_part_component_key),
            )
            variant_values["b_part_component_keys"] = [
                object_reference(item, component_key_map, existing_component_refs, "CMP")
                for item in variant.b_part_component_keys
            ]
            variant_values["core_component_keys"] = [
                object_reference(item, component_key_map, existing_component_refs, "CMP")
                for item in variant.core_component_keys
            ]
            variant_values["software_component_keys"] = [
                object_reference(
                    item,
                    software_component_key_map,
                    existing_software_component_refs,
                    "SWCMP",
                )
                for item in variant.software_component_keys
            ]
            variant_values["interface_keys"] = [
                object_reference(item, interface_key_map, existing_interface_refs, "IF")
                for item in variant.interface_keys
            ]
            variant_values["standard_keys"] = [
                object_reference(item, standard_key_map, existing_standard_refs, "STD")
                for item in variant.standard_keys
            ]
            variants.append(variant_values)
        values["variants"] = variants
        realization_candidates.append(AnalysisTechnicalRealizationCandidate.model_validate(values))
    verification_candidates = []
    for candidate in analysis.verification_cases:
        values = fresh_candidate_values(candidate)
        values["candidate_key"] = f"TEST:{candidate.candidate_key}"
        values["requirement_keys"] = [
            requirement_reference(item) for item in candidate.requirement_keys
        ]
        verification_candidates.append(AnalysisVerificationCandidate.model_validate(values))

    architecture_domains = [
        AnalysisArchitectureDomainCandidate(
            candidate_key=architecture_domain_key_map[item.candidate_key],
            name=item.name,
            domain_type_id=item.domain_type_id,
            technical_domain_ids=list(item.technical_domain_ids),
            partition_rationale=item.partition_rationale,
            description=item.description,
            requirement_keys=[requirement_reference(value) for value in item.requirement_keys],
        )
        for item in analysis.architecture_domains
    ]
    architecture_elements = [
        AnalysisArchitectureElementCandidate(
            candidate_key=architecture_element_key_map[item.candidate_key],
            domain_key=architecture_domain_key_map.get(item.domain_key, item.domain_key),
            name=item.name,
            role_type_id=item.role_type_id,
            technical_domain_ids=list(item.technical_domain_ids),
            partition_rationale=item.partition_rationale,
            description=item.description,
            requirement_keys=[requirement_reference(value) for value in item.requirement_keys],
            component_keys=[
                object_reference(value, component_key_map, existing_component_refs, "CMP")
                for value in item.component_keys
            ],
            technical_realization_keys=[
                object_reference(value, realization_key_map, existing_realization_refs, "REAL")
                for value in item.technical_realization_keys
            ],
        )
        for item in analysis.architecture_elements
    ]
    architecture_interfaces = [
        AnalysisArchitectureInterfaceCandidate(
            candidate_key=architecture_interface_key_map[item.candidate_key],
            name=item.name,
            signal_type=item.signal_type,
            port_type=item.port_type,
            connection_type=item.connection_type,
            interface_template=item.interface_template,
            catalog_family=item.catalog_family,
            technical_domain=item.technical_domain,
            additional_info=item.additional_info,
            voltage_frequency=item.voltage_frequency,
            active_low=item.active_low,
            differential=item.differential,
            host_element_key=architecture_element_key_map.get(
                item.host_element_key or "", item.host_element_key
            ),
            participant_element_keys=[
                architecture_element_key_map.get(value, value)
                for value in item.participant_element_keys
            ],
            requirement_keys=[requirement_reference(value) for value in item.requirement_keys],
            observed_signal_names=list(item.observed_signal_names),
            source_locator=item.source_locator,
            connection_evidence=item.connection_evidence,
            direction_confidence=item.direction_confidence,
            topology_confidence=item.topology_confidence,
            excluded_internal_signal_count=item.excluded_internal_signal_count,
            rationale=item.rationale,
        )
        for item in analysis.architecture_interfaces
    ]

    staged = DocumentAnalysisRevision(
        document_id=source.id,
        revision_number=revision_number,
        stage=stage,
        provider=provider,
        model=model,
        prompt=analysis_prompt.strip(),
        status=DocumentAnalysisStatus.REVIEW_READY,
        system_core_idea=analysis.system_core_idea.strip(),
        system_boundary=analysis.system_boundary.strip(),
        primary_flow=analysis.primary_flow.strip(),
        operating_locations=list(dict.fromkeys(analysis.operating_locations)),
        operating_scenarios=list(dict.fromkeys(analysis.operating_scenarios)),
        external_systems=list(dict.fromkeys(analysis.external_systems)),
        exclusions=list(dict.fromkeys(analysis.exclusions)),
        assumptions=list(dict.fromkeys(analysis.assumptions)),
        requirements=requirement_candidates,
        interfaces=interface_candidates,
        component_needs=component_need_candidates,
        components=component_candidates,
        software_components=software_component_candidates,
        standards=standard_candidates,
        technical_realizations=realization_candidates,
        verification_cases=verification_candidates,
        architecture_name=analysis.architecture_name.strip(),
        architecture_domains=architecture_domains,
        architecture_elements=architecture_elements,
        architecture_interfaces=architecture_interfaces,
        sheet_inventory=[item.model_copy(deep=True) for item in analysis.sheet_inventory],
        internal_nets=[item.model_copy(deep=True) for item in analysis.internal_nets],
        architecture_open_questions=list(analysis.architecture_open_questions),
        architecture_assumptions=list(analysis.architecture_assumptions),
        open_questions=list(analysis.open_questions),
        conflicts=list(analysis.conflicts),
    )
    package.document_analyses.append(staged)
    source.analysis_provider = provider
    source.analysis_model = model
    source.analysis_prompt = analysis_prompt.strip()
    source.analysis_status = DocumentAnalysisStatus.REVIEW_READY
    source.analysis_completed_at = staged.completed_at
    source.analysis_error = ""
    source.active_analysis_id = staged.id
    source.open_questions = list(staged.open_questions)
    system_definition = package.system_definition
    for field_name in ("core_idea", "system_boundary", "primary_flow"):
        analysis_field = "system_core_idea" if field_name == "core_idea" else field_name
        value = str(getattr(analysis, analysis_field) or "").strip()
        if value and not str(getattr(system_definition, field_name) or "").strip():
            setattr(system_definition, field_name, value)
    for field_name in (
        "operating_locations", "operating_scenarios", "external_systems",
        "exclusions", "assumptions",
    ):
        current_values = list(getattr(system_definition, field_name))
        known = {item.casefold() for item in current_values}
        for value in getattr(analysis, field_name):
            normalized = str(value).strip()
            if normalized and normalized.casefold() not in known:
                current_values.append(normalized)
                known.add(normalized.casefold())
        setattr(system_definition, field_name, current_values)
    source_ids = list(system_definition.properties.get("sourceDocumentIds", []))
    if source.id not in source_ids:
        source_ids.append(source.id)
    system_definition.properties["sourceDocumentIds"] = source_ids
    if package.project.workflow_mode == ProjectWorkflow.MANUAL:
        package.project.workflow_mode = ProjectWorkflow.REQUIREMENTS
    package.schema_version = "isd-suite/v3"
    return AnalysisImportSummary(
        document_id=source.id,
        stage=stage,
        requirement_count=len(staged.requirements),
        interface_count=len(staged.interfaces),
        component_need_count=len(staged.component_needs),
        component_count=len(staged.components),
        software_component_count=len(staged.software_components),
        standard_count=len(staged.standards),
        realization_count=len(staged.technical_realizations),
        verification_count=len(staged.verification_cases),
        open_questions=tuple(analysis.open_questions),
    )


def _accepted_uncommitted(items: list[object]) -> list[object]:
    return [
        item for item in items
        if getattr(item, "review_status", None) == CandidateReviewStatus.ACCEPTED
        and not getattr(item, "committed_object_id", None)
    ]


def compile_document_analysis(
    package: ArchitecturePackage,
    analysis_id: str,
    builtins: BusContentTemplates | None = None,
) -> AnalysisCompilationSummary:
    """Publish only explicitly accepted candidates as one validated transaction."""
    working = package.model_copy(deep=True)
    analysis = working.find_document_analysis(analysis_id)
    if analysis is None:
        raise ValueError("Die Dokumentanalyse gehört nicht zu diesem Projekt.")
    source = next((item for item in working.source_documents if item.id == analysis.document_id), None)
    if source is None:
        raise ValueError("Das Quelldokument der Analyse ist nicht mehr vorhanden.")

    key_to_requirement_id = {
        reference: requirement.id
        for requirement in working.requirements
        for reference in (requirement.id, requirement.identifier)
        if reference
    }
    key_to_requirement_id.update({
        item.candidate_key: item.committed_object_id
        for item in analysis.requirements
        if item.committed_object_id
    })
    existing_external = {item.external_id.casefold() for item in working.requirements if item.external_id}
    created_requirements = 0
    for index, candidate in enumerate(_accepted_uncommitted(analysis.requirements), start=1):
        external = candidate.external_id.strip()
        if external and external.casefold() in existing_external:
            external = ""
        if external:
            existing_external.add(external.casefold())
        requirement = EcadRequirement(
            identifier=next_requirement_identifier(working, candidate.classification, candidate.category),
            external_id=external,
            title=candidate.title.strip() or f"Requirement {index}",
            text=candidate.text.strip(),
            classification=candidate.classification,
            category=candidate.category,
            priority=candidate.priority,
            specification_level=(
                candidate.specification_level
                if candidate.explicit
                else RequirementSpecificationLevel.DESIGN_SPECIFICATION
            ),
            ecad_relevance=candidate.ecad_relevance,
            requirement_level=(
                RequirementLevel.CUSTOMER
                if candidate.explicit and candidate.source_kind == RequirementSourceKind.CUSTOMER_CONTRACT
                and candidate.specification_level == RequirementSpecificationLevel.CUSTOMER_SPECIFICATION
                and candidate.requirement_level == RequirementLevel.SYSTEM
                else RequirementLevel.DISCIPLINE
                if candidate.requirement_level == RequirementLevel.REALIZATION
                else candidate.requirement_level
            ),
            solution_binding=candidate.solution_binding,
            source_kind=candidate.source_kind,
            origin=RequirementOrigin.DOCUMENT if candidate.explicit else RequirementOrigin.AI_PROPOSAL,
            maturity=(
                RequirementMaturity.DETECTED
                if analysis.stage == DocumentAnalysisStage.REQUIREMENTS
                else RequirementMaturity.IN_REVIEW
            ),
            source_document_id=source.id,
            source_locator=candidate.source_locator,
            source_excerpt=candidate.source_excerpt,
            required_disciplines=list(dict.fromkeys(candidate.required_disciplines)),
            satisfaction_strategy=candidate.satisfaction_strategy,
            direct_satisfaction_justification=candidate.direct_satisfaction_justification,
            standards_required=candidate.standards_required,
            standard_hints=list(candidate.standard_hints),
            rationale=candidate.rationale,
            acceptance_criteria=candidate.acceptance_criteria,
            properties={
                "analysisId": analysis.id,
                "analysisCandidateKey": candidate.candidate_key,
                "explicitInSource": candidate.explicit,
                "confidence": candidate.confidence,
            },
        )
        working.requirements.append(requirement)
        candidate.committed_object_id = requirement.id
        key_to_requirement_id[candidate.candidate_key] = requirement.id
        created_requirements += 1

    for candidate in analysis.requirements:
        target_id = candidate.committed_object_id
        if not target_id:
            continue
        for source_key in candidate.derived_from_keys:
            source_id = key_to_requirement_id.get(source_key)
            if not source_id or source_id == target_id:
                continue
            if not any(
                item.source_requirement_id == source_id and item.derived_requirement_id == target_id
                for item in working.requirement_derivations
            ):
                working.requirement_derivations.append(RequirementDerivation(
                    source_requirement_id=source_id,
                    derived_requirement_id=target_id,
                    rationale=candidate.rationale,
                    approved=False,
                ))
            target_requirement = next(
                (item for item in working.requirements if item.id == target_id),
                None,
            )
            if target_requirement and source_id not in target_requirement.parent_requirement_ids:
                target_requirement.parent_requirement_ids.append(source_id)

    created_needs = 0
    key_to_need_id = {item.id: item.id for item in working.component_requirements}
    key_to_need_id.update({
        item.candidate_key: item.committed_object_id
        for item in analysis.component_needs
        if item.committed_object_id
    })
    for candidate in _accepted_uncommitted(analysis.component_needs):
        need = ComponentRequirement(
            name=candidate.name.strip() or "Technische Komponentenanforderung",
            component_role=candidate.component_role,
            criteria=dict(candidate.criteria),
            requirement_ids=[
                key_to_requirement_id[item] for item in candidate.requirement_keys if item in key_to_requirement_id
            ],
            source_document_id=source.id,
            rationale=candidate.rationale,
            properties={"analysisId": analysis.id, "analysisCandidateKey": candidate.candidate_key},
        )
        working.component_requirements.append(need)
        candidate.committed_object_id = need.id
        key_to_need_id[candidate.candidate_key] = need.id
        created_needs += 1

    created_interfaces = 0
    key_to_interface_id = {item.id: item.id for item in working.interface_requirements}
    key_to_interface_id.update({
        item.candidate_key: item.committed_object_id
        for item in analysis.interfaces
        if item.committed_object_id
    })
    for candidate in _accepted_uncommitted(analysis.interfaces):
        interface = InterfaceRequirement(
            name=candidate.name.strip() or "Interface",
            interface_class=candidate.interface_class,
            family=candidate.family,
            protocol=candidate.protocol,
            port_type=candidate.port_type,
            signal_type=candidate.signal_type,
            connection_type=candidate.connection_type,
            interface_template=candidate.interface_template,
            host_role=candidate.host_role,
            participant_roles=list(candidate.participant_roles),
            topology=candidate.topology,
            data_rate=candidate.data_rate,
            voltage=candidate.voltage,
            isolation=candidate.isolation,
            safety_redundancy=candidate.safety_redundancy,
            medium_connector=candidate.medium_connector,
            provider=candidate.provider,
            consumer=candidate.consumer,
            physical_properties=dict(candidate.physical_properties),
            protocol_properties=dict(candidate.protocol_properties),
            requirement_ids=[
                key_to_requirement_id[item] for item in candidate.requirement_keys if item in key_to_requirement_id
            ],
            source_document_id=source.id,
            rationale=candidate.rationale,
            standards_required=bool(candidate.standard_keys),
            properties={"analysisId": analysis.id, "analysisCandidateKey": candidate.candidate_key},
        )
        working.interface_requirements.append(interface)
        candidate.committed_object_id = interface.id
        key_to_interface_id[candidate.candidate_key] = interface.id
        created_interfaces += 1
        for requirement_id in dict.fromkeys(interface.requirement_ids):
            working.requirement_links.append(RequirementLink(
                requirement_id=requirement_id,
                target_type=RequirementTargetType.INTERFACE,
                target_id=interface.id,
                relation=RequirementRelation.DEFINES_INTERFACE,
            ))
    for candidate in analysis.interfaces:
        if not candidate.committed_object_id:
            continue
        interface = next(
            (item for item in working.interface_requirements if item.id == candidate.committed_object_id),
            None,
        )
        if interface is None:
            continue
        interface.linked_layer_ids = list(dict.fromkeys(
            key_to_interface_id[item]
            for item in candidate.linked_layer_keys
            if item in key_to_interface_id and key_to_interface_id[item] != interface.id
        ))

    created_components = 0
    key_to_component_id = {item.id: item.id for item in working.components}
    key_to_component_id.update({
        item.candidate_key: item.committed_object_id
        for item in analysis.components
        if item.committed_object_id
    })
    for candidate in _accepted_uncommitted(analysis.components):
        requirement_ids = [
            key_to_requirement_id[item] for item in candidate.requirement_keys if item in key_to_requirement_id
        ]
        component = DesignComponent(
            name=candidate.name.strip() or "Komponentenkandidat",
            component_type=candidate.component_type,
            manufacturer=candidate.manufacturer,
            manufacturer_part_number=candidate.manufacturer_part_number,
            legacy_ecad_reference=candidate.legacy_ecad_reference,
            representation=(
                ComponentRepresentation.PHYSICAL
                if candidate.candidate_kind == ComponentCandidateKind.A_PART
                or candidate.manufacturer_part_number.strip()
                else candidate.representation
            ),
            lifecycle=candidate.lifecycle,
            package_name=candidate.package_name,
            supplier=candidate.supplier,
            supplier_part_number=candidate.supplier_part_number,
            quantity=max(1, candidate.quantity),
            decision_type=candidate.decision_type,
            provenance=candidate.provenance,
            substitution_policy=candidate.substitution_policy,
            verification=ComponentVerification.TO_REVIEW,
            source_document_id=source.id,
            requirement_ids=requirement_ids,
            mandated_by_requirement_ids=(
                requirement_ids
                if candidate.provenance == RealizationProvenance.MANDATED
                else []
            ),
            component_requirement_ids=[
                key_to_need_id[item] for item in candidate.component_need_keys if item in key_to_need_id
            ],
            interface_requirement_ids=[
                key_to_interface_id[item] for item in candidate.interface_keys if item in key_to_interface_id
            ],
            interface_hints=list(candidate.interface_hints),
            system_defining=candidate.system_defining,
            system_defining_reason=candidate.system_defining_reason,
            part_revision=candidate.part_revision,
            rationale=candidate.rationale,
            properties={"analysisId": analysis.id, "analysisCandidateKey": candidate.candidate_key},
        )
        working.components.append(component)
        for interface_id in component.interface_requirement_ids:
            linked_interface = next(
                (item for item in working.interface_requirements if item.id == interface_id),
                None,
            )
            if linked_interface and component.id not in linked_interface.component_ids:
                linked_interface.component_ids.append(component.id)
        candidate.committed_object_id = component.id
        key_to_component_id[candidate.candidate_key] = component.id
        created_components += 1
        for requirement_id in dict.fromkeys(requirement_ids):
            working.requirement_links.append(RequirementLink(
                requirement_id=requirement_id,
                target_type=RequirementTargetType.COMPONENT,
                target_id=component.id,
                relation=RequirementRelation.SATISFIED_BY,
            ))

    created_software_components = 0
    key_to_software_component_id = {item.id: item.id for item in working.software_components}
    key_to_software_component_id.update({
        item.candidate_key: item.committed_object_id
        for item in analysis.software_components
        if item.committed_object_id
    })
    for candidate in _accepted_uncommitted(analysis.software_components):
        requirement_ids = list(dict.fromkeys(
            key_to_requirement_id[item]
            for item in candidate.requirement_keys if item in key_to_requirement_id
        ))
        software_component = SoftwareComponent(
            name=candidate.name.strip() or "Software-/Firmwarekomponente",
            domain=candidate.domain,
            kind=candidate.kind,
            maturity=DesignMaturity.WORKING,
            requirement_ids=requirement_ids,
            interface_requirement_ids=list(dict.fromkeys(
                key_to_interface_id[item]
                for item in candidate.interface_keys if item in key_to_interface_id
            )),
            runtime=candidate.runtime,
            version=candidate.version,
            provenance=candidate.provenance,
            substitution_policy=candidate.substitution_policy,
            mandated_by_requirement_ids=(
                requirement_ids
                if candidate.provenance == RealizationProvenance.MANDATED
                else []
            ),
            source_document_ids=[source.id],
            description=candidate.rationale,
            properties={
                "analysisId": analysis.id,
                "analysisCandidateKey": candidate.candidate_key,
                "sourceLocator": candidate.source_locator,
                "confidence": candidate.confidence,
            },
        )
        working.software_components.append(software_component)
        candidate.committed_object_id = software_component.id
        key_to_software_component_id[candidate.candidate_key] = software_component.id
        created_software_components += 1
        for requirement_id in dict.fromkeys(requirement_ids):
            working.requirement_links.append(RequirementLink(
                requirement_id=requirement_id,
                target_type=RequirementTargetType.SOFTWARE_COMPONENT,
                target_id=software_component.id,
                relation=RequirementRelation.SATISFIED_BY,
            ))

    created_standards = 0
    key_to_standard_id = {item.id: item.id for item in working.standards}
    key_to_standard_id.update({
        item.candidate_key: item.committed_object_id
        for item in analysis.standards
        if item.committed_object_id
    })
    for candidate in _accepted_uncommitted(analysis.standards):
        standard = next(
            (item for item in working.standards if item.designation.casefold() == candidate.designation.casefold() and item.edition.casefold()==candidate.edition.casefold()),
            None,
        )
        if standard is None:
            standard = StandardReference(
                designation=candidate.designation.strip(),
                title=candidate.title,
                edition=candidate.edition,
                organization=candidate.organization,
                description=candidate.rationale,
                properties={"analysisId": analysis.id, "analysisCandidateKey": candidate.candidate_key},
            )
            working.standards.append(standard)
            created_standards += 1
        candidate.committed_object_id = standard.id
        key_to_standard_id[candidate.candidate_key] = standard.id
        clauses = candidate.clauses or [""]
        for requirement_key in candidate.requirement_keys:
            requirement_id = key_to_requirement_id.get(requirement_key)
            if not requirement_id:
                continue
            for clause in clauses:
                if not any(
                    item.requirement_id == requirement_id
                    and item.standard_id == standard.id
                    and item.clause.casefold() == clause.casefold()
                    for item in working.requirement_standard_links
                ):
                    working.requirement_standard_links.append(RequirementStandardLink(
                        requirement_id=requirement_id,
                        standard_id=standard.id,
                        clause=clause,
                        rationale=candidate.rationale,
                    ))

    for candidate in analysis.interfaces:
        if not candidate.committed_object_id:
            continue
        linked_interface = next(
            (item for item in working.interface_requirements if item.id == candidate.committed_object_id),
            None,
        )
        if linked_interface is None:
            continue
        linked_interface.standard_ids = list(dict.fromkeys([
            *linked_interface.standard_ids,
            *(key_to_standard_id[item] for item in candidate.standard_keys if item in key_to_standard_id),
        ]))

    created_realizations = 0
    from .models import TechnicalSource,TechnicalSourceOwner
    for candidate in analysis.components:
        component=working.find_component(candidate.committed_object_id or '')
        if component is None:continue
        component.alternative_component_ids=list(dict.fromkeys(component.alternative_component_ids+[key_to_component_id[k] for k in candidate.alternative_component_keys if k in key_to_component_id and key_to_component_id[k]!=component.id]))
        for item in candidate.technical_sources:
            if not (item.url or item.external_reference):continue
            if any(s.owner_id==component.id and s.url==item.url and s.external_reference==item.external_reference and s.revision==item.revision for s in working.technical_sources):continue
            working.technical_sources.append(TechnicalSource(owner_type=TechnicalSourceOwner.COMPONENT,owner_id=component.id,title=item.title,source_type=item.source_type,channel=item.channel,provider=item.provider,external_reference=item.external_reference,url=item.url,revision=item.revision,document_date=item.document_date,evidence_locator=item.evidence_locator,notes=item.notes))
    for candidate in _accepted_uncommitted(analysis.technical_realizations):
        variants: list[SolutionVariant] = []
        for proposed in candidate.variants:
            component_roles: list[RealizationComponentRole] = []
            core_keys=list(dict.fromkeys(([proposed.a_part_component_key] if proposed.a_part_component_key else [])+proposed.core_component_keys))
            core_ids={key_to_component_id[k] for k in core_keys if k in key_to_component_id}
            for a_part_id in core_ids:
                component_roles.append(RealizationComponentRole(
                    component_id=a_part_id,
                    role=ComponentRoleInRealization.A_PART,
                    purpose="Designentscheidende Kernkomponente",
                ))
            for key in proposed.b_part_component_keys:
                component_id = key_to_component_id.get(key)
                if component_id and component_id not in core_ids:
                    component_roles.append(RealizationComponentRole(
                        component_id=component_id,
                        role=ComponentRoleInRealization.B_PART,
                        purpose="Erforderliche unterstützende Komponente",
                    ))
            variants.append(SolutionVariant(
                name=proposed.name.strip() or "Lösungsvariante",
                status=proposed.status,
                component_roles=component_roles,
                interface_requirement_ids=list(dict.fromkeys(
                    key_to_interface_id[item]
                    for item in proposed.interface_keys if item in key_to_interface_id
                )),
                standard_ids=list(dict.fromkeys(
                    key_to_standard_id[item]
                    for item in proposed.standard_keys if item in key_to_standard_id
                )),
                software_component_ids=list(dict.fromkeys(
                    key_to_software_component_id[item]
                    for item in proposed.software_component_keys
                    if item in key_to_software_component_id
                )),
                technical_parameters=dict(proposed.technical_parameters),
                assumptions=list(proposed.assumptions),
                open_questions=list(proposed.open_questions),
                rationale=proposed.rationale,
                properties={"analysisVariantCandidateKey": proposed.candidate_key},
            ))
        selected_variant = next(
            (item for item in variants if item.status == SolutionVariantStatus.SELECTED),
            None,
        )
        realization = TechnicalRealization(
            name=candidate.name.strip() or "Technische Realisierung",
            generic_function=candidate.generic_function,
            requirement_ids=list(dict.fromkeys(
                key_to_requirement_id[item]
                for item in candidate.requirement_keys if item in key_to_requirement_id
            )),
            status=(
                TechnicalRealizationStatus.SELECTED
                if selected_variant else TechnicalRealizationStatus.IN_REVIEW
            ),
            provenance=(
                RealizationProvenance.OBSERVED
                if working.project.workflow_mode == ProjectWorkflow.REDESIGN
                else RealizationProvenance.DERIVED
            ),
            variants=variants,
            selected_variant_id=selected_variant.id if selected_variant else None,
            source_document_id=source.id,
            rationale=candidate.rationale,
            attributes={"architectureElementHint": candidate.architecture_element_hint},
            properties={"analysisId": analysis.id, "analysisCandidateKey": candidate.candidate_key},
        )
        if not realization.requirement_ids:
            continue
        working.technical_realizations.append(realization)
        candidate.committed_object_id = realization.id
        created_realizations += 1
        for requirement_id in dict.fromkeys(realization.requirement_ids):
            working.requirement_links.append(RequirementLink(
                requirement_id=requirement_id,
                target_type=RequirementTargetType.TECHNICAL_REALIZATION,
                target_id=realization.id,
                relation=RequirementRelation.SATISFIED_BY,
            ))

    created_verifications = 0
    for candidate in _accepted_uncommitted(analysis.verification_cases):
        requirement_ids = list(dict.fromkeys(
            key_to_requirement_id[item]
            for item in candidate.requirement_keys if item in key_to_requirement_id
        ))
        if not requirement_ids:
            continue
        complete = bool(
            candidate.objective.strip()
            and candidate.procedure.strip()
            and candidate.expected_result.strip()
        )
        verification = VerificationCase(
            identifier=next_verification_identifier(working),
            title=candidate.title.strip() or "Requirement-Testdefinition",
            method=candidate.method,
            definition_status=(
                TestDefinitionStatus.DEFINED if complete else TestDefinitionStatus.DRAFT
            ),
            execution_status=TestExecutionStatus.NOT_RUN,
            requirement_ids=requirement_ids,
            objective=candidate.objective,
            procedure=candidate.procedure,
            expected_result=candidate.expected_result,
            properties={
                "analysisId": analysis.id,
                "analysisCandidateKey": candidate.candidate_key,
                "rationale": candidate.rationale,
            },
        )
        synchronize_verification_status(verification)
        working.verification_cases.append(verification)
        candidate.committed_object_id = verification.id
        created_verifications += 1
        for requirement_id in dict.fromkeys(requirement_ids):
            working.requirement_links.append(RequirementLink(
                requirement_id=requirement_id,
                target_type=RequirementTargetType.VERIFICATION_CASE,
                target_id=verification.id,
                relation=RequirementRelation.VERIFIED_BY,
            ))

    created_architecture_proposals = 0
    created_architecture_domains = 0
    created_architecture_elements = 0
    created_architecture_signals = 0
    if (
        analysis.architecture_domains
        or analysis.architecture_elements
        or analysis.architecture_interfaces
    ) and not analysis.architecture_proposal_id:
        proposal = ArchitectureProposal(
            name=analysis.architecture_name.strip() or f"As-Is-Arbeitsarchitektur · {source.name}",
            provider=analysis.provider,
            model=analysis.model,
            guidance="Aus Dokumentanalyse abgeleitete, vorläufige Arbeitsarchitektur.",
            domains=[
                ProposedDomain(
                    candidate_id=item.candidate_key,
                    name=item.name,
                    domain_type_id=item.domain_type_id,
                    technical_domain_ids=list(item.technical_domain_ids),
                    partition_rationale=item.partition_rationale,
                    description=item.description,
                    requirement_ids=list(dict.fromkeys(
                        key_to_requirement_id[key]
                        for key in item.requirement_keys if key in key_to_requirement_id
                    )),
                )
                for item in analysis.architecture_domains
            ],
            elements=[
                ProposedElement(
                    candidate_id=item.candidate_key,
                    domain_candidate_id=item.domain_key,
                    name=item.name,
                    role_type_id=item.role_type_id,
                    technical_domain_ids=list(item.technical_domain_ids),
                    partition_rationale=item.partition_rationale,
                    description=item.description,
                    requirement_ids=list(dict.fromkeys(
                        key_to_requirement_id[key]
                        for key in item.requirement_keys if key in key_to_requirement_id
                    )),
                    component_ids=list(dict.fromkeys(
                        key_to_component_id[key]
                        for key in item.component_keys if key in key_to_component_id
                    )),
                    technical_realization_ids=list(dict.fromkeys(
                        realization.committed_object_id
                        for realization in analysis.technical_realizations
                        if realization.candidate_key in item.technical_realization_keys
                        and realization.committed_object_id
                    )),
                )
                for item in analysis.architecture_elements
            ],
            interfaces=[
                ProposedInterface(
                    candidate_id=item.candidate_key,
                    name=item.name,
                    signal_type=item.signal_type,
                    port_type=item.port_type,
                    connection_type=item.connection_type,
                    interface_template=item.interface_template,
                    catalog_family=item.catalog_family,
                    technical_domain=item.technical_domain,
                    additional_info=item.additional_info,
                    voltage_frequency=item.voltage_frequency,
                    active_low=item.active_low,
                    differential=item.differential,
                    host_element_candidate_id=item.host_element_key,
                    participant_element_candidate_ids=list(item.participant_element_keys),
                    requirement_ids=list(dict.fromkeys(
                        key_to_requirement_id[key]
                        for key in item.requirement_keys if key in key_to_requirement_id
                    )),
                    observed_signal_names=list(item.observed_signal_names),
                    source_locator=item.source_locator,
                    connection_evidence=item.connection_evidence,
                    direction_confidence=item.direction_confidence,
                    topology_confidence=item.topology_confidence,
                    excluded_internal_signal_count=item.excluded_internal_signal_count,
                    rationale=item.rationale,
                )
                for item in analysis.architecture_interfaces
            ],
            open_questions=list(analysis.architecture_open_questions),
            assumptions=list(analysis.architecture_assumptions),
            properties={
                "analysisId": analysis.id,
                "sourceDocumentId": source.id,
                "designState": (
                    "As-Is"
                    if working.project.workflow_mode == ProjectWorkflow.REDESIGN
                    else "Working"
                ),
                "provenance": (
                    "Observed"
                    if working.project.workflow_mode == ProjectWorkflow.REDESIGN
                    else "Derived"
                ),
            },
        )
        working.architecture_proposals.append(proposal)
        analysis.architecture_proposal_id = proposal.id
        created_architecture_proposals = 1
        if working.project.workflow_mode == ProjectWorkflow.REDESIGN and builtins is not None:
            unresolved_bindings: list[dict[str, str]] = []
            for candidate in proposal.interfaces:
                family = (candidate.catalog_family or "Interface").strip().title()
                if family in {"Control", "Status", "Analog", "Power"} and not builtins.is_catalog_binding(
                    family, candidate.interface_template
                ):
                    candidate.selected_for_execution = False
                    reason = (
                        f"{family}-Template „{candidate.interface_template or 'offen'}“ ist nicht "
                        "generierbar; der Befund bleibt zur Katalogzuordnung erhalten."
                    )
                    unresolved_bindings.append({
                        "candidateId": candidate.candidate_id,
                        "name": candidate.name,
                        "family": family,
                        "template": candidate.interface_template,
                        "reason": reason,
                    })
                    proposal.open_questions.append(
                        f"Template-Zuordnung offen für „{candidate.name}“: {reason}"
                    )
            if unresolved_bindings:
                proposal.properties["unresolvedCatalogBindings"] = unresolved_bindings
            compilation = _compile_architecture_proposal_in_place(working, proposal, builtins)
            created_architecture_domains = compilation.domain_count
            created_architecture_elements = compilation.element_count
            created_architecture_signals = compilation.signal_count

    all_candidates = [
        *analysis.requirements,
        *analysis.interfaces,
        *analysis.component_needs,
        *analysis.components,
        *analysis.software_components,
        *analysis.standards,
        *analysis.technical_realizations,
        *analysis.verification_cases,
    ]
    open_count = sum(item.review_status == CandidateReviewStatus.OPEN for item in all_candidates)
    accepted_count = sum(item.review_status == CandidateReviewStatus.ACCEPTED for item in all_candidates)
    if open_count:
        analysis.status = (
            DocumentAnalysisStatus.PARTIALLY_ACCEPTED
            if accepted_count else DocumentAnalysisStatus.REVIEW_READY
        )
    elif accepted_count:
        analysis.status = DocumentAnalysisStatus.ACCEPTED
    else:
        analysis.status = DocumentAnalysisStatus.REJECTED
    source.analysis_status = analysis.status
    working.schema_version = "isd-suite/v3"
    validated = ArchitecturePackage.model_validate(working.export_dict())
    for field_name in ArchitecturePackage.model_fields:
        setattr(package, field_name, getattr(validated, field_name))
    package.__pydantic_extra__ = validated.__pydantic_extra__
    return AnalysisCompilationSummary(
        requirement_count=created_requirements,
        interface_count=created_interfaces,
        component_need_count=created_needs,
        component_count=created_components,
        software_component_count=created_software_components,
        standard_count=created_standards,
        realization_count=created_realizations,
        verification_count=created_verifications,
        architecture_proposal_count=created_architecture_proposals,
        architecture_domain_count=created_architecture_domains,
        architecture_element_count=created_architecture_elements,
        architecture_signal_count=created_architecture_signals,
    )


def compile_detected_document_analysis(
    package: ArchitecturePackage,
    analysis_id: str,
    builtins: BusContentTemplates | None = None,
) -> AnalysisCompilationSummary:
    """Expose AI findings directly in their owning workspaces.

    The analysis revision remains the immutable document-centric evidence view.
    Requirements enter the Requirements tree as ``Detected`` and technical
    objects keep their own review state.  Exact findings from a re-analysis are
    linked to their existing project objects instead of being duplicated.
    """
    analysis = package.find_document_analysis(analysis_id)
    if analysis is None:
        raise ValueError("Die Dokumentanalyse gehört nicht zu diesem Projekt.")

    def normalized(value: str) -> str:
        return " ".join(value.casefold().split())

    for candidate in analysis.requirements:
        if candidate.committed_object_id:
            continue
        existing = next((
            item for item in package.requirements
            if item.source_document_id == analysis.document_id
            and (
                bool(candidate.external_id.strip())
                and normalized(item.external_id) == normalized(candidate.external_id)
                or (
                    normalized(item.title) == normalized(candidate.title)
                    and normalized(item.text) == normalized(candidate.text)
                )
            )
        ), None)
        if existing:
            candidate.committed_object_id = existing.id

    for candidate in analysis.interfaces:
        if not candidate.committed_object_id:
            existing = next((
                item for item in package.interface_requirements
                if item.source_document_id == analysis.document_id
                and item.interface_class == candidate.interface_class
                and normalized(item.name) == normalized(candidate.name)
            ), None)
            if existing:
                candidate.committed_object_id = existing.id

    for candidate in analysis.components:
        if not candidate.committed_object_id:
            existing = next((
                item for item in package.components
                if item.source_document_id == analysis.document_id
                and (
                    bool(candidate.manufacturer_part_number.strip())
                    and normalized(item.manufacturer_part_number) == normalized(candidate.manufacturer_part_number)
                    or normalized(item.name) == normalized(candidate.name)
                )
            ), None)
            if existing:
                candidate.committed_object_id = existing.id

    for candidate in analysis.software_components:
        if not candidate.committed_object_id:
            existing = next((
                item for item in package.software_components
                if analysis.document_id in item.source_document_ids
                and normalized(item.name) == normalized(candidate.name)
                and normalized(item.version) == normalized(candidate.version)
            ), None)
            if existing:
                candidate.committed_object_id = existing.id

    for candidate in analysis.standards:
        if not candidate.committed_object_id:
            existing = next((
                item for item in package.standards
                if normalized(item.designation) == normalized(candidate.designation) and normalized(item.edition)==normalized(candidate.edition)
            ), None)
            if existing:
                candidate.committed_object_id = existing.id

    for candidate in analysis.component_needs:
        if not candidate.committed_object_id:
            existing = next((
                item for item in package.component_requirements
                if normalized(item.name) == normalized(candidate.name)
                and normalized(item.component_role) == normalized(candidate.component_role)
            ), None)
            if existing:
                candidate.committed_object_id = existing.id

    for candidate in analysis.technical_realizations:
        if not candidate.committed_object_id:
            existing = next((
                item for item in package.technical_realizations
                if item.source_document_id == analysis.document_id
                and normalized(item.name) == normalized(candidate.name)
            ), None)
            if existing:
                candidate.committed_object_id = existing.id

    for candidate in analysis.verification_cases:
        if not candidate.committed_object_id:
            existing = next((
                item for item in package.verification_cases
                if normalized(item.title) == normalized(candidate.title)
            ), None)
            if existing:
                candidate.committed_object_id = existing.id

    for group in (
        analysis.requirements,
        analysis.interfaces,
        analysis.component_needs,
        analysis.components,
        analysis.software_components,
        analysis.standards,
        analysis.technical_realizations,
        analysis.verification_cases,
    ):
        for candidate in group:
            if candidate.review_status == CandidateReviewStatus.OPEN:
                candidate.review_status = CandidateReviewStatus.ACCEPTED

    summary = compile_document_analysis(package, analysis_id, builtins)
    compiled_analysis = package.find_document_analysis(analysis_id)
    if compiled_analysis:
        compiled_analysis.status = DocumentAnalysisStatus.ANALYZED
    source = next(
        (item for item in package.source_documents if item.id == analysis.document_id),
        None,
    )
    if source:
        source.analysis_status = DocumentAnalysisStatus.ANALYZED
    return summary


def create_architecture_proposal(
    package: ArchitecturePackage,
    result: ArchitectureSynthesisResult,
    provider: str,
    model: str,
    guidance: str = "",
) -> ArchitectureProposal:
    proposal = ArchitectureProposal(
        name=result.name,
        provider=provider,
        model=model,
        guidance=guidance.strip(),
        domains=result.domains,
        elements=result.elements,
        interfaces=result.interfaces,
        system_elements=result.system_elements,
        mechanical_elements=result.mechanical_elements,
        software_elements=result.software_elements,
        function_elements=result.function_elements,
        open_questions=result.open_questions,
        assumptions=result.assumptions,
    )
    preview = package.model_copy(deep=True)
    preview.architecture_proposals.append(proposal.model_copy(deep=True))
    ArchitecturePackage.model_validate(preview.export_dict())
    package.architecture_proposals.append(proposal)
    return proposal


def create_ai_review(
    package: ArchitecturePackage,
    result: AIConsultationResult,
    prompt: str,
    provider: str,
    model: str,
) -> AIReview:
    review = AIReview(
        title=result.title.strip() or "KI-Projektanalyse",
        prompt=prompt.strip(),
        answer=result.answer.strip(),
        findings=result.findings,
        recommendations=result.recommendations,
        open_questions=result.open_questions,
        provider=provider,
        model=model,
    )
    preview = package.model_copy(deep=True)
    preview.ai_reviews.append(review.model_copy(deep=True))
    ArchitecturePackage.model_validate(preview.export_dict())
    package.ai_reviews.append(review)
    return review


_AI_CHANGE_FIELDS: dict[AIChangeObjectType, dict[str, type | None]] = {
    AIChangeObjectType.REQUIREMENT: {
        "title": None,
        "text": None,
        "classification": RequirementClassification,
        "category": RequirementCategory,
        "requirement_level": RequirementLevel,
        "solution_binding": RequirementSolutionBinding,
        "source_kind": RequirementSourceKind,
        "priority": RequirementPriority,
        "maturity": RequirementMaturity,
        "ecad_relevance": RequirementEcadRelevance,
        "rationale": None,
        "acceptance_criteria": None,
        "satisfaction_strategy": None,
        "direct_satisfaction_justification": None,
        "owner": None,
        "change_authority": None,
    },
    AIChangeObjectType.COMPONENT: {
        "name": None,
        "component_type": None,
        "decision_type": ComponentDecisionType,
        "provenance": RealizationProvenance,
        "substitution_policy": SubstitutionPolicy,
        "verification": ComponentVerification,
        "lifecycle": ComponentLifecycle,
        "rationale": None,
        "description": None,
    },
    AIChangeObjectType.STANDARD: {
        "title": None,
        "edition": None,
        "organization": None,
        "applicability": StandardApplicability,
        "description": None,
        "publication_status": None,
    },
    AIChangeObjectType.PROJECT: {"description": None},
}


def _change_target(package: ArchitecturePackage, object_type: AIChangeObjectType, object_id: str) -> object | None:
    from .traceability import project_objects,canonical_kind
    match=project_objects(package).get(canonical_kind(object_type.value),{}).get(object_id)
    if match is not None:return match
    if object_type == AIChangeObjectType.REQUIREMENT:
        return package.find_requirement(object_id)
    if object_type == AIChangeObjectType.COMPONENT:
        return package.find_component(object_id)
    if object_type == AIChangeObjectType.STANDARD:
        return package.find_standard(object_id)
    if object_type == AIChangeObjectType.PROJECT and object_id == package.project.id:
        return package.project
    return None


def _scalar_text(value: object) -> str:
    if isinstance(value,(dict,list,bool)):return json.dumps(value,ensure_ascii=False,sort_keys=True)
    return str(getattr(value, "value", value) or "")


for _kind in (AIChangeObjectType.DOMAIN,AIChangeObjectType.ARCHITECTURE_ELEMENT,AIChangeObjectType.FUNCTION_ELEMENT,
              AIChangeObjectType.INTEGRATION_INTERFACE,AIChangeObjectType.SYSTEM_ELEMENT,AIChangeObjectType.MECHANICAL_ELEMENT,AIChangeObjectType.SOFTWARE_ELEMENT,
              AIChangeObjectType.SIGNAL,AIChangeObjectType.PORT):
    _AI_CHANGE_FIELDS[_kind]={'name':None,'description':None}
_AI_CHANGE_FIELDS[AIChangeObjectType.FUNCTION_ELEMENT].update(dependency_ids=json.loads,interface_signal_ids=json.loads,interface_requirement_ids=json.loads,realization_ids=json.loads)
from .integration import REFERENCE_COLLECTIONS
_AI_CHANGE_FIELDS[AIChangeObjectType.INTEGRATION_INTERFACE].update({key:json.loads for key in REFERENCE_COLLECTIONS})
_AI_CHANGE_FIELDS[AIChangeObjectType.INTEGRATION_INTERFACE].update(configuration=json.loads,revision=None)
_AI_CHANGE_FIELDS[AIChangeObjectType.REALIZATION]={'name':None,'generic_function':None,'rationale':None}
_AI_CHANGE_FIELDS[AIChangeObjectType.COMPONENT].update(manufacturer=None,manufacturer_part_number=None,package_name=None,
    part_revision=None,system_defining=json.loads,system_defining_reason=None,alternative_component_ids=json.loads)
_AI_CHANGE_FIELDS[AIChangeObjectType.COMPONENT].pop('verification',None)

def _ai_field_rule(package,target,object_type,field):
    if '.' in field:
        scope,key=field.split('.',1)
        if scope not in {'requirement_attributes','realization_attributes'}:raise ValueError('Attributraum nicht unterstützt')
        from .property_schema import applicable
        definition=next((d for d in applicable(package.property_definitions,target,scope) if d.key==key and not d.readonly),None)
        if definition is None:raise ValueError('Attribut ist geschützt oder passt nicht zum Objekt')
        return json.loads,definition
    rules=_AI_CHANGE_FIELDS.get(object_type,{})
    if field not in rules:raise ValueError('Feld wird nicht unterstützt')
    return rules[field],None

def _ai_field_value(target,field):
    if '.' in field:
        scope,key=field.split('.',1);return getattr(target,scope).get(key)
    return getattr(target,field)


def create_ai_change_proposal(
    package: ArchitecturePackage,
    result: AIChangeProposalResult,
    prompt: str,
    context_scope: str,
    provider: str,
    model: str,
    selected_object_id: str = '',
) -> AIChangeProposal:
    # Earlier callers did not pass the selection separately. An unambiguous
    # single-object result still identifies that selection without widening it.
    if context_scope == 'Aktuelles Objekt' and not selected_object_id:
        target_ids = {item.object_id for item in result.changes}
        if len(target_ids) == 1:
            selected_object_id = next(iter(target_ids))
    proposal = AIChangeProposal(
        title=result.title.strip() or "KI-Änderungsvorschlag",
        prompt=prompt.strip(),
        answer=result.answer.strip(),
        context_scope=context_scope,
        selected_object_id=selected_object_id,
        provider=provider,
        model=model,
        open_questions=list(result.open_questions),
    )
    for suggestion in result.changes:
        target = _change_target(package, suggestion.object_type, suggestion.object_id)
        try:
            if target is None:raise ValueError('Zielobjekt fehlt')
            if context_scope=='Aktuelles Objekt' and suggestion.object_id!=selected_object_id:raise ValueError('Änderung liegt außerhalb des ausgewählten Objekts')
            converter,definition=_ai_field_rule(package,target,suggestion.object_type,suggestion.field_name)
            if converter:converter(suggestion.after_value)
        except (ValueError,TypeError) as error:
            proposal.open_questions.append(
                f"Nicht unterstützte Änderung: {suggestion.object_type.value} {suggestion.object_id} / {suggestion.field_name}: {error}"
            )
            continue
        before = _scalar_text(_ai_field_value(target, suggestion.field_name))
        after = suggestion.after_value.strip()
        if before == after:
            continue
        proposal.changes.append(AIChangeItem(
            object_type=suggestion.object_type,
            object_id=suggestion.object_id,
            field_name=suggestion.field_name,
            before_value=before,
            after_value=after,
            rationale=suggestion.rationale,
        ))
    package.ai_change_proposals.append(proposal)
    ArchitecturePackage.model_validate(package.export_dict())
    return proposal


def apply_ai_change_proposal(package: ArchitecturePackage, proposal_id: str) -> int:
    working = package.model_copy(deep=True)
    proposal = working.find_ai_change_proposal(proposal_id)
    if proposal is None or proposal.status != ProposalStatus.DRAFT:
        raise ValueError("Der KI-Änderungsvorschlag ist nicht mehr offen.")
    accepted = [item for item in proposal.changes if item.status == AIChangeItemStatus.ACCEPTED]
    if not accepted:
        raise ValueError("Es wurde noch keine Einzeländerung angenommen.")
    for change in accepted:
        target = _change_target(working, change.object_type, change.object_id)
        if target is None:
            raise ValueError(f"Das Zielobjekt {change.object_id} ist nicht mehr vorhanden.")
        if proposal.context_scope=='Aktuelles Objekt' and change.object_id!=proposal.selected_object_id:raise ValueError('Änderung außerhalb des Objektkontexts')
        current = _scalar_text(_ai_field_value(target,change.field_name))
        if current != change.before_value:
            raise ValueError(
                f"Das Feld {change.field_name} von {change.object_id} wurde seit dem Vorschlag geändert."
            )
        converter,definition = _ai_field_rule(working,target,change.object_type,change.field_name)
        value = converter(change.after_value) if converter else change.after_value
        if definition is not None:
            from .requirement_profiles import validate_selection
            validate_selection(definition,target,working,value)
            scope,key=change.field_name.split('.',1);getattr(target,scope)[key]=value
        else:setattr(target,change.field_name,value)
        change.status = AIChangeItemStatus.APPLIED
    from .requirement_profiles import category_options
    changed_profiles={c.object_id for c in accepted if c.object_type==AIChangeObjectType.REQUIREMENT and c.field_name in {'classification','category'}}
    for identifier in changed_profiles:
        requirement=working.find_requirement(identifier)
        if requirement.category.value not in category_options(requirement.classification):
            raise ValueError('Die Requirement-Kategorie passt nicht zur Disziplin.')
    proposal.status = ProposalStatus.ACCEPTED
    proposal.reviewed_at = utc_now()
    validated = ArchitecturePackage.model_validate(working.export_dict())
    for field_name in ArchitecturePackage.model_fields:
        setattr(package, field_name, getattr(validated, field_name))
    package.__pydantic_extra__ = validated.__pydantic_extra__
    return len(accepted)
















def delete_requirement(package: ArchitecturePackage, requirement_id: str) -> None:
    requirement = package.find_requirement(requirement_id)
    if requirement is None:
        raise KeyError(requirement_id)
    previous_verification_ids={v.id for v in package.verification_cases}
    package.requirements.remove(requirement)
    for element in [*package.system_elements,*package.mechanical_architecture_elements,*package.software_architecture_elements,*package.discipline_relations,*package.function_elements]:
        element.requirement_ids = [rid for rid in element.requirement_ids if rid != requirement_id]
    package.requirement_links = [item for item in package.requirement_links if item.requirement_id != requirement_id]
    package.requirement_standard_links = [
        item for item in package.requirement_standard_links if item.requirement_id != requirement_id
    ]
    package.requirement_derivations = [
        item for item in package.requirement_derivations
        if item.source_requirement_id != requirement_id and item.derived_requirement_id != requirement_id
    ]
    for conflict in package.engineering_conflicts:
        conflict.requirement_ids = [
            item for item in conflict.requirement_ids if item != requirement_id
        ]
    package.engineering_conflicts = [
        conflict for conflict in package.engineering_conflicts if conflict.requirement_ids
    ]
    for verification in package.verification_cases:
        verification.requirement_ids = sorted(test_requirement_ids(package,verification)-{requirement_id})
    package.verification_cases = [
        verification for verification in package.verification_cases if verification.requirement_ids
    ]
    for item in package.requirements:
        item.parent_requirement_ids = [value for value in item.parent_requirement_ids if value != requirement_id]
    for component in package.components:
        component.requirement_ids = [value for value in component.requirement_ids if value != requirement_id]
        component.mandated_by_requirement_ids = [
            value for value in component.mandated_by_requirement_ids
            if value != requirement_id
        ]
    for component_requirement in package.component_requirements:
        component_requirement.requirement_ids = [
            value for value in component_requirement.requirement_ids if value != requirement_id
        ]
    for interface_requirement in package.interface_requirements:
        interface_requirement.requirement_ids = [
            value for value in interface_requirement.requirement_ids if value != requirement_id
        ]
    for component in package.mechanical_components:
        component.requirement_ids = [value for value in component.requirement_ids if value != requirement_id]
    for constraint in package.mechanical_constraints:
        constraint.requirement_ids = [value for value in constraint.requirement_ids if value != requirement_id]
    for component in package.software_components:
        component.requirement_ids = [value for value in component.requirement_ids if value != requirement_id]
        component.mandated_by_requirement_ids = [
            value for value in component.mandated_by_requirement_ids
            if value != requirement_id
        ]
    for work_item in package.software_work_items:
        work_item.requirement_ids = [value for value in work_item.requirement_ids if value != requirement_id]
    for source in package.technical_sources:
        source.requirement_ids = [value for value in source.requirement_ids if value != requirement_id]
    removed_realization_ids: set[str] = set()
    for realization in package.technical_realizations:
        realization.requirement_ids = [value for value in realization.requirement_ids if value != requirement_id]
        if not realization.requirement_ids and not realization.function_element_id:
            removed_realization_ids.add(realization.id)
            realization.architecture_element_id = None
            synchronize_realization_architecture_attribute(package, realization)
    package.technical_realizations = [
        realization for realization in package.technical_realizations if realization.requirement_ids or realization.function_element_id
    ]
    for proposal in package.architecture_proposals:
        for domain in proposal.domains:
            domain.requirement_ids = [value for value in domain.requirement_ids if value != requirement_id]
        for element in proposal.elements:
            element.requirement_ids = [value for value in element.requirement_ids if value != requirement_id]
            element.technical_realization_ids = [
                value for value in element.technical_realization_ids
                if value not in removed_realization_ids
            ]
        for interface in proposal.interfaces:
            interface.requirement_ids = [value for value in interface.requirement_ids if value != requirement_id]
        for field in ('system_elements','mechanical_elements','software_elements','function_elements'):
            for element in getattr(proposal,field):
                element.requirement_ids=[i for i in element.requirement_ids if i!=requirement_id]
    removed_verifications=previous_verification_ids-{v.id for v in package.verification_cases}
    remove_deleted_references(package,{requirement_id,*removed_realization_ids,*removed_verifications})


def delete_component(package: ArchitecturePackage, component_id: str) -> None:
    component = package.find_component(component_id)
    if component is None:
        raise KeyError(component_id)
    package.components.remove(component)
    for item in package.components:
        item.alternative_component_ids = [i for i in item.alternative_component_ids if i != component_id]
    remove_deleted_references(package,{component_id})
    removed_source_ids = {
        item.id for item in package.technical_sources
        if item.owner_type.value == "Component" and item.owner_id == component_id
    }
    package.technical_sources = [
        item for item in package.technical_sources
        if not (item.owner_type.value == "Component" and item.owner_id == component_id)
    ]
    package.component_allocations = [item for item in package.component_allocations if item.component_id != component_id]
    package.requirement_links = [
        item for item in package.requirement_links
        if not (item.target_type == RequirementTargetType.COMPONENT and item.target_id == component_id)
    ]
    for conflict in package.engineering_conflicts:
        if conflict.target_type == RequirementTargetType.COMPONENT and conflict.target_id == component_id:
            conflict.target_type = None
            conflict.target_id = None
    for interface_requirement in package.interface_requirements:
        interface_requirement.component_ids = [
            value for value in interface_requirement.component_ids if value != component_id
        ]
    for proposal in package.architecture_proposals:
        for element in proposal.elements:
            element.component_ids = [value for value in element.component_ids if value != component_id]
    for realization in package.technical_realizations:
        for variant in realization.variants:
            variant.component_roles = [
                item for item in variant.component_roles if item.component_id != component_id
            ]
            variant.evidence_source_ids = [
                item for item in variant.evidence_source_ids if item not in removed_source_ids
            ]
        synchronize_realization_architecture_attribute(package, realization)


def delete_standard(package: ArchitecturePackage, standard_id: str) -> None:
    standard = package.find_standard(standard_id)
    if standard is None:
        raise KeyError(standard_id)
    package.standards.remove(standard)
    for component in package.components:
        component.standard_claims = [c for c in component.standard_claims if c.standard_id != standard_id]
    remove_deleted_references(package,{standard_id})
    removed_source_ids = {
        item.id for item in package.technical_sources
        if item.owner_type.value == "Standard" and item.owner_id == standard_id
    }
    package.technical_sources = [
        item for item in package.technical_sources
        if not (item.owner_type.value == "Standard" and item.owner_id == standard_id)
    ]
    package.requirement_standard_links = [
        item for item in package.requirement_standard_links if item.standard_id != standard_id
    ]
    for interface_requirement in package.interface_requirements:
        interface_requirement.standard_ids = [
            value for value in interface_requirement.standard_ids if value != standard_id
        ]
    for source in package.technical_sources:
        source.referenced_standard_ids = [
            value for value in source.referenced_standard_ids if value != standard_id
        ]
    for realization in package.technical_realizations:
        for variant in realization.variants:
            variant.standard_ids = [value for value in variant.standard_ids if value != standard_id]
            variant.evidence_source_ids = [
                item for item in variant.evidence_source_ids if item not in removed_source_ids
            ]


def delete_interface_requirement(package: ArchitecturePackage, interface_id: str) -> None:
    interface = next((item for item in package.interface_requirements if item.id == interface_id), None)
    if interface is None:
        raise KeyError(interface_id)
    package.interface_requirements.remove(interface)
    remove_deleted_references(package,{interface_id})
    package.requirement_links = [
        item for item in package.requirement_links
        if not (item.target_type == RequirementTargetType.INTERFACE and item.target_id == interface_id)
    ]
    for conflict in package.engineering_conflicts:
        if conflict.target_type == RequirementTargetType.INTERFACE and conflict.target_id == interface_id:
            conflict.target_type = None
            conflict.target_id = None
    removed_source_ids = {
        item.id for item in package.technical_sources
        if item.owner_type.value == "InterfaceRequirement" and item.owner_id == interface_id
    }
    package.technical_sources = [
        item for item in package.technical_sources
        if not (
            item.owner_type.value == "InterfaceRequirement"
            and item.owner_id == interface_id
        )
    ]
    for component in package.components:
        component.interface_requirement_ids = [
            value for value in component.interface_requirement_ids if value != interface_id
        ]
    for interface_requirement in package.interface_requirements:
        interface_requirement.linked_layer_ids = [
            value for value in interface_requirement.linked_layer_ids if value != interface_id
        ]
    for component in package.software_components:
        component.interface_requirement_ids = [
            value for value in component.interface_requirement_ids if value != interface_id
        ]
    for source in package.technical_sources:
        source.interface_requirement_ids = [
            value for value in source.interface_requirement_ids if value != interface_id
        ]
    for realization in package.technical_realizations:
        for variant in realization.variants:
            variant.interface_requirement_ids = [
                value for value in variant.interface_requirement_ids if value != interface_id
            ]
            variant.evidence_source_ids = [
                item for item in variant.evidence_source_ids if item not in removed_source_ids
            ]


def delete_technical_source(package: ArchitecturePackage, source_id: str) -> TechnicalSource:
    source = package.find_technical_source(source_id)
    if source is None:
        raise KeyError(source_id)
    package.technical_sources.remove(source)
    for component in package.components:
        for claim in component.standard_claims:
            claim.evidence_source_ids = [i for i in claim.evidence_source_ids if i != source_id]
    remove_deleted_references(package, {source_id})
    for realization in package.technical_realizations:
        for variant in realization.variants:
            variant.evidence_source_ids = [
                value for value in variant.evidence_source_ids if value != source_id
            ]
    return source


def delete_technical_realization(package: ArchitecturePackage, realization_id: str) -> None:
    realization = package.find_technical_realization(realization_id)
    if realization is None:
        raise KeyError(realization_id)
    realization.architecture_element_id = None
    synchronize_realization_architecture_attribute(package, realization)
    package.technical_realizations.remove(realization)
    remove_deleted_references(package,{realization_id})
    package.requirement_links = [
        item for item in package.requirement_links
        if not (
            item.target_type == RequirementTargetType.TECHNICAL_REALIZATION
            and item.target_id == realization_id
        )
    ]
    for proposal in package.architecture_proposals:
        for element in proposal.elements:
            element.technical_realization_ids = [
                item for item in element.technical_realization_ids if item != realization_id
            ]


def delete_verification_case(package: ArchitecturePackage, verification_id: str) -> None:
    verification = package.find_verification_case(verification_id)
    if verification is None:
        raise KeyError(verification_id)
    package.verification_cases.remove(verification)
    remove_deleted_references(package,{verification_id})
    package.requirement_links = [
        item for item in package.requirement_links
        if not (
            item.target_type == RequirementTargetType.VERIFICATION_CASE
            and item.target_id == verification_id
        )
    ]

# Public service entry points retained across module consolidation.
__all__ = ['AnalysisCompilationSummary', 'AnalysisImportSummary', 'CompilationSummary', 'DEFAULT_ARCHITECTURE_CATALOG', 'DOMAIN_COLORS', 'DocumentContextRecoverySummary', 'RequirementTraceabilityStatus', 'add_document_analysis', 'apply_ai_change_proposal', 'approve_legacy_document_requirements', 'clone_builtin_interface_template', 'compile_architecture_proposal', 'compile_detected_document_analysis', 'compile_document_analysis', 'create_ai_change_proposal', 'create_ai_review', 'create_architecture_proposal', 'defined_test_requirement_ids', 'delete_component', 'delete_interface_requirement', 'delete_requirement', 'delete_standard', 'delete_technical_realization', 'delete_technical_source', 'delete_verification_case', 'ensure_requirement_identifiers', 'ensure_verification_identifiers', 'interface_catalog_names', 'is_test_defined', 'link_legacy_requirements_to_document', 'migrate_requirements_model', 'next_requirement_identifier', 'next_verification_identifier', 'recover_document_context_metadata', 'requirement_identifier_prefix', 'requirement_traceability_index', 'requirement_traceability_status', 'synchronize_all_realization_attributes', 'synchronize_realization_architecture_attribute', 'synchronize_verification_status', 'validate_document_context_recovery']
