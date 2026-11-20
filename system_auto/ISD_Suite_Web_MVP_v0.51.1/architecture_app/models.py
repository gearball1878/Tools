from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import re
from secrets import token_bytes
from typing import Literal, Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


def new_id(prefix: str) -> str:
    """Create an opaque, stable SHA-256 ID from random input, never object content."""
    return sha256(prefix.encode("ascii") + b"\0" + token_bytes(32)).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Direction(str, Enum):
    IN = "in"
    OUT = "out"
    INOUT = "inout"
    PASSIVE = "passive"


class ConnectionType(str, Enum):
    NET = "Net"
    BUS = "Bus"


class SignalType(str, Enum):
    POWER = "Power"
    ANALOG = "Analog"
    DIGITAL = "Digital"
    CLOCK = "Clock"
    RESET = "Reset"
    CONTROL = "Control"
    STATUS = "Status"
    DIFFERENTIAL = "Differential"
    INTERFACE = "Interface"
    MEMORY = "Memory"


class EndpointRole(str, Enum):
    HOST = "Host"
    PARTICIPANT = "Participant"
    SOURCE = "Source"
    SINK = "Sink"


class ProjectWorkflow(str, Enum):
    MANUAL = "manual"
    REQUIREMENTS = "requirements"
    REDESIGN = "redesign"
    STUDY = "study"


class DesignMaturity(str, Enum):
    PROPOSAL = "Proposal"
    WORKING = "Working"
    CONFIRMED = "Confirmed"
    RELEASED = "Released"


class InterfaceClass(str, Enum):
    MECHANICAL = "MECH_IF"
    ELECTRONIC = "EHW_IF"
    SOFTWARE = "SW_IF"
    FIRMWARE = "FW_IF"


class MechanicalComponentKind(str, Enum):
    ASSEMBLY = "Assembly"
    ENCLOSURE = "Enclosure"
    COOLING = "Cooling"
    MOUNTING = "Mounting"
    CONNECTOR = "Connector Housing"
    CABLE = "Cable / Strain Relief"
    SEAL = "Seal"
    PCB = "PCB Mechanical Reference"
    OTHER = "Other"


class MechanicalConstraintKind(str, Enum):
    ENVELOPE = "Envelope"
    PCB_OUTLINE = "PCB Outline"
    KEEP_OUT = "Keep-out"
    HEIGHT_ZONE = "Height Zone"
    MOUNTING = "Mounting"
    CONNECTOR_POSITION = "Connector Position"
    THERMAL = "Thermal"
    ENVIRONMENT = "Environment"
    EMC_SHIELDING = "EMC / Shielding"
    MASS = "Mass"
    MATERIAL = "Material"
    SERVICE = "Service"
    OTHER = "Other"


class SoftwareDomain(str, Enum):
    SOFTWARE = "Software"
    FIRMWARE = "Firmware"
    HDL = "HDL / Programmable Logic"


class SoftwareComponentKind(str, Enum):
    APPLICATION = "Application"
    SERVICE = "Service"
    LIBRARY = "Library"
    DRIVER = "Driver"
    FIRMWARE_MODULE = "Firmware Module"
    BOOTLOADER = "Bootloader"
    STATE_MACHINE = "State Machine"
    TASK = "Task"
    HDL_BLOCK = "HDL Block"
    DATA_STORE = "Data Store"
    USER_INTERFACE = "User Interface"
    EXTERNAL_SYSTEM = "External System"
    PACKAGE = "Package"
    PLATFORM = "Platform"
    BUILD = "Build"
    FIRMWARE_IMAGE = "Firmware Image"
    OTHER = "Other"


class WorkItemStatus(str, Enum):
    BACKLOG = "Backlog"
    PLANNED = "Planned"
    IN_PROGRESS = "In Progress"
    IN_REVIEW = "In Review"
    DONE = "Done"
    BLOCKED = "Blocked"


class RequirementOrigin(str, Enum):
    DOCUMENT = "Document"
    DERIVED = "Derived"
    MANUAL = "Manual"
    AI_PROPOSAL = "AI Proposal"
    PRESCRIBED = "Prescribed"
    RECONSTRUCTED = "Reconstructed"
    HYPOTHESIS = "Hypothesis"


class RequirementSpecificationLevel(str, Enum):
    """Development contract level, independent from the technical classification."""

    CUSTOMER_SPECIFICATION = "Customer Specification"
    DESIGN_SPECIFICATION = "Design Specification"
    IMPLEMENTATION_CONSTRAINT = "Implementation Constraint"


class RequirementLevel(str, Enum):
    """Four V-model layers; former level values stay readable for old projects."""

    CUSTOMER = "Customer Requirement"
    SYSTEM = "System Requirement"
    TECHNICAL = "Technical Requirement"
    DISCIPLINE = "Discipline Requirement"
    # Historic SPOT exports used these values. They retain their original
    # semantics during a round trip and are displayed on the L4 branch.
    REALIZATION = "Realization Requirement"
    COMPONENT = "Component Requirement"


class RequirementSolutionBinding(str, Enum):
    SOLUTION_NEUTRAL = "Solution Neutral"
    DESIGN_CONSTRAINT = "Design Constraint"
    IMPLEMENTATION_MANDATE = "Implementation Mandate"


class RequirementSourceKind(str, Enum):
    CUSTOMER_CONTRACT = "Customer / Contract"
    STANDARD_REGULATION = "Standard / Regulation"
    ENGINEERING_DERIVATION = "Engineering Derivation"
    DESIGN_DECISION = "Design Decision"
    EXISTING_DESIGN = "Existing Design"
    INTERNAL_MANUAL = "Internal / Manual"


class RequirementCoverageStatus(str, Enum):
    NOT_APPLICABLE = "Not Applicable"
    REALIZATION_GAP = "Realization Gap"
    PARTIAL = "Partially Covered"
    COVERED = "Technically Covered"
    CONFLICT = "Conflict"


class RequirementVerificationState(str, Enum):
    NOT_DEFINED = "No Test Defined"
    DEFINED = "Test Defined"
    PASSED = "Verified"
    FAILED = "Verification Failed"
    BLOCKED = "Verification Blocked"
    STALE = 'Verification Stale'


class RequirementMaturity(str, Enum):
    DETECTED = "Detected"
    IN_REVIEW = "In Review"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    OBSOLETE = "Obsolete"


class RequirementCategory(str, Enum):
    FUNCTION = "Function"
    INTERFACE = "Interface"
    DATA = "Data Transfer"
    POWER = "Power"
    CLOCK_RESET = "Clock & Reset"
    ANALOG = "Analog"
    CONTROL_STATUS = "Control & Status"
    DIAGNOSTIC_TEST = "Diagnostic & Test"
    PERFORMANCE = "Performance"
    SAFETY_REDUNDANCY = "Safety & Redundancy"
    ENVIRONMENT = "Environment"
    INTEGRATION = "Physical Integration"
    RELIABILITY_AVAILABILITY = "Reliability & Availability"
    SECURITY = "Security"
    THERMAL = "Thermal"
    COMPLIANCE = "Compliance"
    LIFECYCLE = "Lifecycle & Service"
    SCHEMATIC = "Schematic"
    UNCLASSIFIED = "Unclassified"


class RequirementClassification(str, Enum):
    SYSTEM = "System"
    HARDWARE = "Hardware"
    MECHANICS = "Mechanik"
    SOFTWARE = "Software"
    FIRMWARE = "Firmware"


class RequirementEcadRelevance(str, Enum):
    NOT_APPLICABLE = 'Not Applicable'
    DIRECT = "Direct"
    DERIVED = "Derived"
    BACKLOG_ONLY = "Backlog Only"
    UNCLEAR = "Unclear"


class RequirementPriority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class RequirementRelation(str, Enum):
    ALLOCATED_TO = "Allocated To"
    SATISFIED_BY = "Satisfied By"
    CONSTRAINS = "Constrains"
    DEFINES_INTERFACE = "Defines Interface"
    MOTIVATES = "Motivates"
    VERIFIED_BY = "Verified By"


class RequirementTargetType(str, Enum):
    INTEGRATION_INTERFACE = 'IntegrationInterface'
    BUS_MEMBER = 'Signal'
    FUNCTION_ELEMENT = 'FunctionElement'
    DOMAIN = "Domain"
    ELEMENT = "ArchitectureElement"
    PORT = "Port"
    SIGNAL = "ArchitectureSignal"
    CONNECTION = "Connection"
    COMPONENT = "Component"
    INTERFACE = "InterfaceRequirement"
    MECHANICAL_COMPONENT = "MechanicalComponent"
    MECHANICAL_CONSTRAINT = "MechanicalConstraint"
    SOFTWARE_COMPONENT = "SoftwareComponent"
    SOFTWARE_WORK_ITEM = "SoftwareWorkItem"
    TECHNICAL_REALIZATION = "TechnicalRealization"
    VERIFICATION_CASE = "VerificationCase"
    SYSTEM_DOMAIN = 'SystemDomain'
    SYSTEM_ELEMENT = 'SystemElement'
    SYSTEM_RELATION = 'SystemRelation'
    MECHANICAL_ARCHITECTURE_ELEMENT = 'MechanicalArchitectureElement'
    SOFTWARE_ARCHITECTURE_ELEMENT = 'SoftwareArchitectureElement'
    DISCIPLINE_RELATION = 'DisciplineRelation'


class ComponentDecisionType(str, Enum):
    GENERIC = "Generic"
    PROPOSED = "Proposed"
    EXISTING = "Existing"
    SELECTED = "Selected"
    FIXED = "Fixed"


class RealizationProvenance(str, Enum):
    MANUAL = "Manual"
    PROPOSED = "Proposed"
    OBSERVED = "Observed"
    MANDATED = "Mandated"
    DERIVED = "Derived"


class SubstitutionPolicy(str, Enum):
    ALLOWED = "Allowed"
    APPROVAL_REQUIRED = "Approval Required"
    PROHIBITED = "Prohibited"


class ComponentVerification(str, Enum):
    UNVERIFIED = "Unverified"
    TO_REVIEW = "To Review"
    VERIFIED = "Verified"
    REJECTED = "Rejected"
    OBSOLETE = "Obsolete"


class ComponentRepresentation(str, Enum):
    LOGICAL = "Logical"
    PHYSICAL = "Physical"


class ComponentLifecycle(str, Enum):
    UNKNOWN = "Unknown"
    PRELIMINARY = "Preliminary"
    ACTIVE = "Active"
    NRND = "Not Recommended for New Designs"
    LAST_TIME_BUY = "Last Time Buy"
    OBSOLETE = "Obsolete"


class TechnicalSourceType(str, Enum):
    STANDARD_DOCUMENT = "Standard Document"
    DATASHEET = "Datasheet"
    APPLICATION_NOTE = "Application Note"
    PRODUCT_PAGE = "Product Page"
    USER_MANUAL = "User Manual"
    REFERENCE_DESIGN = "Reference Design"
    COMPLIANCE_DOCUMENT = "Compliance Document"
    CAD_DATA = "CAD Data"
    TEST_REPORT = "Test Report"
    BIBLIOGRAPHIC_REFERENCE = "Bibliographic Reference"
    OTHER = "Other"


class TechnicalSourceChannel(str, Enum):
    PLM = 'PLM'
    ERP = 'ERP'
    DMS = 'DMS'
    WEB_LINK = "Web Link"
    FILE_UPLOAD = "File Upload"
    STANDARDS_ORGANIZATION = "Standards Organization"
    LICENSE_PORTAL = "Standards / License Portal"
    MANUFACTURER_PORTAL = "Manufacturer Portal"
    DISTRIBUTOR = "Distributor"
    COMPONENT_DATABASE = "Component Database"
    API = "API"
    CONNECTOR = "Connector"
    INTERNAL_REPOSITORY = "Internal Repository"
    OTHER = "Other"


class TechnicalSourceAccess(str, Enum):
    PUBLIC = "Public"
    LOGIN_REQUIRED = "Login Required"
    LICENSED = "Licensed"
    NDA_RESTRICTED = "NDA / Restricted"
    INTERNAL = "Internal"


class TechnicalSourceStatus(str, Enum):
    CANDIDATE = "Candidate"
    AVAILABLE = "Available"
    VERIFIED = "Verified"
    SUPERSEDED = "Superseded"
    UNAVAILABLE = "Unavailable"


class TechnicalSourceOwner(str, Enum):
    STANDARD = "Standard"
    COMPONENT = "Component"
    INTERFACE = "InterfaceRequirement"


class EvidenceClaimStatus(str, Enum):
    UNASSESSED = "Unassessed"
    MANUFACTURER_CLAIM = "Manufacturer Claim"
    REVIEWED = "Reviewed"
    DESIGN_VERIFIED = "Design Verified"
    REJECTED = "Rejected"


class ProposalStatus(str, Enum):
    DRAFT = "Draft"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"


class AIReviewStatus(str, Enum):
    DRAFT = "Draft"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"


class DocumentAnalysisStatus(str, Enum):
    IMPORTED = "Imported"
    QUEUED = "Queued"
    EXTRACTING = "Extracting"
    ANALYZING = "Analyzing"
    REVIEW_READY = "Review Ready"
    PARTIALLY_ACCEPTED = "Partially Accepted"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    ANALYZED = "Analyzed"
    FAILED = "Failed"


class DocumentAnalysisStage(str, Enum):
    REQUIREMENTS = "Requirements"
    TECHNICAL_DERIVATION = "Technical Derivation"


class CandidateReviewStatus(str, Enum):
    OPEN = "Open"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"


class ComponentCandidateKind(str, Enum):
    LOGICAL_ROLE = "Logical Role"
    A_PART = "A-Part"


class ComponentRoleInRealization(str, Enum):
    A_PART = "A-Part"
    B_PART = "B-Part"


class TechnicalRealizationStatus(str, Enum):
    DRAFT = "Draft"
    IN_REVIEW = "In Review"
    SELECTED = "Selected"
    REJECTED = "Rejected"


class SolutionVariantStatus(str, Enum):
    CANDIDATE = "Candidate"
    PREFERRED = "Preferred"
    SELECTED = "Selected"
    REJECTED = "Rejected"


class AIChangeObjectType(str, Enum):
    DOMAIN = 'Domain'
    ARCHITECTURE_ELEMENT = 'ArchitectureElement'
    INTEGRATION_INTERFACE = 'IntegrationInterface'
    FUNCTION_ELEMENT = 'FunctionElement'
    SYSTEM_ELEMENT = 'SystemElement'
    MECHANICAL_ELEMENT = 'MechanicalArchitectureElement'
    SOFTWARE_ELEMENT = 'SoftwareArchitectureElement'
    SIGNAL = 'ArchitectureSignal'
    PORT = 'InterfacePort'
    REALIZATION = 'TechnicalRealization'
    REQUIREMENT = "Requirement"
    COMPONENT = "Component"
    STANDARD = "Standard"
    PROJECT = "Project"


class AIChangeItemStatus(str, Enum):
    OPEN = "Open"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    APPLIED = "Applied"


class StandardApplicability(str, Enum):
    CANDIDATE = "Candidate"
    APPLICABLE = "Applicable"
    MANDATORY = "Mandatory"
    NOT_APPLICABLE = "Not Applicable"
    SUPERSEDED = "Superseded"


class VerificationMethod(str, Enum):
    TEST = "Test"
    ANALYSIS = "Analysis"
    INSPECTION = "Inspection"
    DEMONSTRATION = "Demonstration"


class VerificationStatus(str, Enum):
    PLANNED = "Planned"
    DEFINED = "Defined"
    READY = "Ready"
    PASSED = "Passed"
    FAILED = "Failed"
    BLOCKED = "Blocked"
    OBSOLETE = "Obsolete"


class TestDefinitionStatus(str, Enum):
    DRAFT = "Draft"
    DEFINED = "Defined"
    APPROVED = "Approved"


class TestExecutionStatus(str, Enum):
    NOT_RUN = "Not Run"
    PASSED = "Passed"
    FAILED = "Failed"
    BLOCKED = "Blocked"
    OBSOLETE = "Obsolete"


class EngineeringConflictStatus(str, Enum):
    OPEN = "Open"
    IN_REVIEW = "In Review"
    RESOLVED = "Resolved"
    ACCEPTED_DEVIATION = "Accepted Deviation"


class EngineeringConflictResolution(str, Enum):
    UNDECIDED = "Undecided"
    CHANGE_REQUIREMENT = "Change Requirement"
    CHANGE_SOLUTION = "Change Solution"
    CHANGE_CONSTRAINT = "Change Constraint"
    ACCEPT_DEVIATION = "Accept Deviation"
    REJECT_REQUIREMENT = "Reject Requirement"


from .property_schema import PropertyDefinition, initialize_object, synchronize_schema
from .netclasses import NetClassDefinition, default_netclasses, adopt_netclasses


class ArchitectureAttributes(BaseModel):
    """Two engineering spaces sharing the object's single immutable identity.

    Legacy attributes/properties stay separate and lossless for connector compatibility.
    """
    requirement_attributes: dict[str, Any] = Field(default_factory=dict, alias="requirementAttributes")
    realization_attributes: dict[str, Any] = Field(default_factory=dict, alias="realizationAttributes")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @model_validator(mode="after")
    def initialize_properties(self):
        return initialize_object(self)


class SystemDomain(ArchitectureAttributes):
    id: str = Field(default_factory=lambda: new_id("sdom"))
    name: str
    description: str = ""
    color: str = "#2563EB"
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class SystemElement(ArchitectureAttributes):
    kind: Literal["Systemteil","Funktion","Schnittstelle"] = "Systemteil"
    id: str = Field(default_factory=lambda: new_id("se"))
    name: str
    domain_id: str | None = None
    description: str = ""
    external: bool = False
    requirement_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class SystemRelation(ArchitectureAttributes):
    id: str = Field(default_factory=lambda: new_id("srel"))
    name: str
    source_id: str
    target_id: str
    kind: Literal["Information", "Energie", "Material", "Abhängigkeit"] = "Information"
    description: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class ArchitectureAllocation(BaseModel):
    id: str = Field(default_factory=lambda: new_id("alloc"))
    system_element_id: str
    target_id: str
    target_kind: Literal["hw_element", "hw_realization", "mechanical", "software", "mechanical_element", "software_element"]
    description: str = ""


class MechanicalArchitectureElement(ArchitectureAttributes):
    id: str = Field(default_factory=lambda: new_id('mae'))
    name: str
    description: str = ''
    kind: Literal['Baugruppe','Gehäuse','Träger','Kühlung','Befestigung','Schnittstelle','Sonstiges'] = 'Baugruppe'
    parent_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    realization_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class SoftwareArchitectureElement(ArchitectureAttributes):
    id: str = Field(default_factory=lambda: new_id('swae'))
    name: str
    description: str = ''
    kind: Literal['Modul','Dienst','Komponente','Treiber','Firmwaremodul','Datenspeicher','Sonstiges'] = 'Modul'
    parent_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    realization_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class DisciplineRelation(ArchitectureAttributes):
    id: str = Field(default_factory=lambda: new_id('drel'))
    name: str
    description: str = ''
    discipline: Literal['mechanical','software']
    source_id: str
    target_id: str
    kind: str
    requirement_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class SignalEndpoint(BaseModel):
    element_id: str
    pin_type: str = "BI"
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class Signal(ArchitectureAttributes):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = Field(default_factory=lambda: new_id("sig"))
    name: str
    direction: Direction = Direction.INOUT
    pin_type: str = "BI"
    active_low: bool = False
    template_member_key: str = Field(default="", alias="templateMemberKey")
    description: str = ""
    source: SignalEndpoint | None = None
    sinks: list[SignalEndpoint] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class ArchitectureSignal(ArchitectureAttributes):
    """Architecture-level SPOT object with tool-neutral member signals."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = Field(default_factory=lambda: new_id("asig"))
    name: str
    signal_type: SignalType = SignalType.DIGITAL
    port_type: str = ""
    interface_definition_id: str | None = None
    interface_definition_version: int | None = None
    interface_kind: str | None = Field(default=None, alias="interfaceKind")
    instance_index: int | None = Field(default=None, alias="instanceIndex")
    catalog_family: str = Field(default="", alias="catalogFamily")
    catalog_template: str = Field(default="", alias="catalogTemplate")
    catalog_status: str = Field(default="Unbound", alias="catalogStatus")
    observed_names: list[str] = Field(default_factory=list, alias="observedNames")
    connection_type: ConnectionType = ConnectionType.NET
    source: SignalEndpoint | None = None
    sinks: list[SignalEndpoint] = Field(default_factory=list)
    bus_contents: list[Signal] = Field(
        default_factory=list,
        validation_alias=AliasChoices("members", "bus_contents", "busContents"),
        serialization_alias="members",
    )
    description: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class InterfacePort(ArchitectureAttributes):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = Field(default_factory=lambda: new_id("prt"))
    name: str
    port_type: str = "Generic Interface"
    role: str = ""
    connection_type: ConnectionType = ConnectionType.BUS
    interface_definition_id: str | None = Field(default=None, alias="interfaceDefinitionId")
    interface_definition_version: int | None = Field(default=None, alias="interfaceDefinitionVersion")
    interface_link_id: str | None = Field(default=None, alias="interfaceLinkId")
    implementation_binding: dict[str, Any] = Field(default_factory=dict, alias="implementationBinding")
    side: str = "Auto"
    description: str = ""
    signals: list[Signal] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, value: Any) -> str:
        legacy_roles = {
            "controller": "Host", "source": "Host",
            "peripheral": "Participant", "sink": "Participant", "peer": "Participant", "teilnehmer":"Participant",
        }
        normalized = str(value or "")
        if not normalized:return ""
        return legacy_roles.get(normalized.casefold(), normalized if normalized in {"Host", "Participant"} else "")


class ArchitectureElement(ArchitectureAttributes):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = Field(default_factory=lambda: new_id("ae"))
    name: str
    technical_name: str = Field(default="", alias="technicalName")
    role_type_id: str = Field(default="GEN.FUNCTION_BLOCK", alias="roleTypeId")
    technical_domain_ids: list[str] = Field(default_factory=list, alias="technicalDomainIds")
    kind: str = "ArchitectureElement"
    description: str = ""
    ports: list[InterfacePort] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("Der Name des Architecture Elements darf nicht leer sein")
        return normalized

    @field_validator("technical_name")
    @classmethod
    def validate_technical_name(cls, value: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized and not re.fullmatch(r"AE_[0-9]{3,}_[A-Z0-9_]+", normalized):
            raise ValueError("Der technische AE-Name muss AE_<NNN>_<ROLE> entsprechen")
        return normalized


class Domain(ArchitectureAttributes):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = Field(default_factory=lambda: new_id("dom"))
    name: str
    technical_name: str = Field(default="", alias="technicalName")
    domain_type_id: str = Field(default="GEN.OTHER", alias="domainTypeId")
    technical_domain_ids: list[str] = Field(default_factory=list, alias="technicalDomainIds")
    color: str = "#2563EB"
    description: str = ""
    elements: list[ArchitectureElement] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("Der Domainname darf nicht leer sein")
        return normalized

    @field_validator("technical_name")
    @classmethod
    def validate_technical_name(cls, value: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized and not re.fullmatch(r"DOM_[0-9]{3,}_[A-Z0-9_]+", normalized):
            raise ValueError("Der technische Domainname muss DOM_<NNN>_<TYPE> entsprechen")
        return normalized


class ConnectionEndpoint(BaseModel):
    element_id: str
    port_id: str
    role: EndpointRole | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class Connection(ArchitectureAttributes):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = Field(default_factory=lambda: new_id("con"))
    name: str
    connection_type: ConnectionType = ConnectionType.BUS
    signal_id: str | None = None
    interface_definition_id: str | None = Field(default=None, alias="interfaceDefinitionId")
    interface_definition_version: int | None = Field(default=None, alias="interfaceDefinitionVersion")
    interface_link_id: str | None = Field(default=None, alias="interfaceLinkId")
    endpoints: list[ConnectionEndpoint] = Field(default_factory=list)
    description: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_endpoint_roles(self) -> "Connection":
        for index, endpoint in enumerate(self.endpoints):
            if self.signal_id:
                endpoint.role = EndpointRole.SOURCE if index == 0 else EndpointRole.SINK
            else:
                endpoint.role = EndpointRole.HOST if index == 0 else EndpointRole.PARTICIPANT
        return self


class ProjectInfo(BaseModel):
    id: str = Field(default_factory=lambda: new_id("project"))
    name: str = "Neue Architektur"
    workflow_mode: ProjectWorkflow = ProjectWorkflow.MANUAL
    profile_history: list[dict[str, str]] = Field(default_factory=list)
    description: str = ""
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class SystemDefinition(ArchitectureAttributes):
    """Shared system context used by requirements analysis and all development spaces."""

    core_idea: str = ""
    system_boundary: str = ""
    primary_flow: str = ""
    operating_locations: list[str] = Field(default_factory=list)
    operating_scenarios: list[str] = Field(default_factory=list)
    external_systems: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    maturity: DesignMaturity = DesignMaturity.PROPOSAL
    reviewed_at: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class MechanicalComponent(ArchitectureAttributes):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: new_id("mcomp"))
    name: str
    kind: MechanicalComponentKind = MechanicalComponentKind.OTHER
    maturity: DesignMaturity = DesignMaturity.WORKING
    parent_component_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    material: str = ""
    dimensions: str = ""
    mass: str = ""
    protection_rating: str = ""
    cooling_method: str = ""
    power_dissipation: str = ""
    temperature_range: str = ""
    part_number: str = ""
    manufacturer: str = ""
    revision: str = ""
    cad_reference: str = ""
    cad_revision: str = ""
    plm_reference: str = ""
    alternative_component_ids: list[str] = Field(default_factory=list)
    analysis_references: list[str] = Field(default_factory=list)
    pcb_constraints: dict[str, str] = Field(default_factory=dict)
    parameters: dict[str, str] = Field(default_factory=dict)
    description: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class MechanicalConstraint(ArchitectureAttributes):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: new_id("mcon"))
    name: str
    kind: MechanicalConstraintKind = MechanicalConstraintKind.OTHER
    statement: str = ""
    value: str = ""
    unit: str = ""
    maturity: DesignMaturity = DesignMaturity.WORKING
    mechanical_component_id: str | None = None
    architecture_element_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    rationale: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class SoftwareComponent(ArchitectureAttributes):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: new_id("swcomp"))
    name: str
    domain: SoftwareDomain = SoftwareDomain.SOFTWARE
    kind: SoftwareComponentKind = SoftwareComponentKind.OTHER
    maturity: DesignMaturity = DesignMaturity.WORKING
    requirement_ids: list[str] = Field(default_factory=list)
    interface_requirement_ids: list[str] = Field(default_factory=list)
    deployment_element_id: str | None = None
    parent_component_id: str | None = None
    runtime: str = ""
    repository_url: str = ""
    code_path: str = ""
    commit: str = ""
    package_id: str = ""
    artifact_url: str = ""
    build_id: str = ""
    dependency_ids: list[str] = Field(default_factory=list)
    included_component_ids: list[str] = Field(default_factory=list)
    configuration: dict[str, str] = Field(default_factory=dict)
    version: str = ""
    provenance: RealizationProvenance = RealizationProvenance.MANUAL
    substitution_policy: SubstitutionPolicy = SubstitutionPolicy.ALLOWED
    mandated_by_requirement_ids: list[str] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    description: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class SoftwareWorkItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: new_id("switem"))
    title: str
    domain: SoftwareDomain = SoftwareDomain.SOFTWARE
    status: WorkItemStatus = WorkItemStatus.BACKLOG
    priority: RequirementPriority = RequirementPriority.MEDIUM
    requirement_ids: list[str] = Field(default_factory=list)
    component_ids: list[str] = Field(default_factory=list)
    verification_case_ids: list[str] = Field(default_factory=list)
    description: str = ""
    acceptance_criteria: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class SourceDocument(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: new_id("doc"))
    name: str
    file_name: str = ""
    media_type: str = "application/octet-stream"
    checksum_sha256: str
    attachment_path: str = ""
    attachment_size: int = 0
    context_path: str = ""
    context_checksum_sha256: str = ""
    context_section_count: int = 0
    context_updated_at: str | None = None
    imported_at: str = Field(default_factory=utc_now)
    page_count: int | None = None
    character_count: int = 0
    analysis_provider: str = ""
    analysis_model: str = ""
    analysis_status: DocumentAnalysisStatus = DocumentAnalysisStatus.ANALYZED
    analysis_prompt: str = ""
    analysis_completed_at: str = Field(default_factory=utc_now)
    analysis_error: str = ""
    active_analysis_id: str | None = None
    open_questions: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class EcadRequirement(ArchitectureAttributes):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: new_id("req"))
    identifier: str = ""
    external_id: str = ""
    title: str
    text: str
    classification: RequirementClassification = RequirementClassification.SYSTEM
    category: RequirementCategory = RequirementCategory.UNCLASSIFIED
    priority: RequirementPriority = RequirementPriority.MEDIUM
    origin: RequirementOrigin = RequirementOrigin.MANUAL
    specification_level: RequirementSpecificationLevel = RequirementSpecificationLevel.DESIGN_SPECIFICATION
    requirement_level: RequirementLevel = RequirementLevel.SYSTEM
    solution_binding: RequirementSolutionBinding = RequirementSolutionBinding.SOLUTION_NEUTRAL
    source_kind: RequirementSourceKind = RequirementSourceKind.INTERNAL_MANUAL
    maturity: RequirementMaturity = RequirementMaturity.IN_REVIEW
    ecad_relevance: RequirementEcadRelevance = RequirementEcadRelevance.DIRECT
    source_document_id: str | None = None
    source_locator: str = ""
    source_excerpt: str = ""
    parent_requirement_ids: list[str] = Field(default_factory=list)
    required_disciplines: list[RequirementClassification] = Field(default_factory=list)
    satisfaction_strategy: str = ""
    direct_satisfaction_justification: str = ""
    owner: str = ""
    review_decision: str = ""
    customer_decision: Literal['Open','Accepted','Rejected'] = 'Open'
    observation_ids: list[str] = Field(default_factory=list)
    change_authority: str = ""
    standards_required: bool = False
    standard_hints: list[str] = Field(default_factory=list)
    standard_gap_note: str = ""
    rationale: str = ""
    acceptance_criteria: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class AnalysisRequirementCandidate(BaseModel):
    id: str = Field(default_factory=lambda: new_id("areq"))
    candidate_key: str
    external_id: str = ""
    title: str
    text: str
    classification: RequirementClassification = RequirementClassification.SYSTEM
    category: RequirementCategory = RequirementCategory.UNCLASSIFIED
    priority: RequirementPriority = RequirementPriority.MEDIUM
    specification_level: RequirementSpecificationLevel = RequirementSpecificationLevel.CUSTOMER_SPECIFICATION
    requirement_level: RequirementLevel = RequirementLevel.SYSTEM
    solution_binding: RequirementSolutionBinding = RequirementSolutionBinding.SOLUTION_NEUTRAL
    source_kind: RequirementSourceKind = RequirementSourceKind.CUSTOMER_CONTRACT
    ecad_relevance: RequirementEcadRelevance = RequirementEcadRelevance.DIRECT
    source_locator: str = ""
    source_excerpt: str = ""
    explicit: bool = True
    derived_from_keys: list[str] = Field(default_factory=list)
    required_disciplines: list[RequirementClassification] = Field(default_factory=list)
    satisfaction_strategy: str = ""
    direct_satisfaction_justification: str = ""
    standards_required: bool = False
    standard_hints: list[str] = Field(default_factory=list)
    rationale: str = ""
    acceptance_criteria: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    review_status: CandidateReviewStatus = CandidateReviewStatus.OPEN
    review_comment: str = ""
    committed_object_id: str | None = None


class AnalysisInterfaceCandidate(BaseModel):
    id: str = Field(default_factory=lambda: new_id("aif"))
    candidate_key: str
    name: str
    interface_class: InterfaceClass = InterfaceClass.ELECTRONIC
    family: str = "Interface"
    protocol: str = ""
    port_type: str = "Generic Interface"
    signal_type: SignalType = SignalType.INTERFACE
    connection_type: ConnectionType = ConnectionType.BUS
    interface_template: str = ""
    host_role: str = ""
    participant_roles: list[str] = Field(default_factory=list)
    topology: str = "Point-to-point"
    data_rate: str = ""
    voltage: str = ""
    isolation: str = ""
    safety_redundancy: str = ""
    medium_connector: str = ""
    provider: str = ""
    consumer: str = ""
    physical_properties: dict[str, str] = Field(default_factory=dict)
    protocol_properties: dict[str, str] = Field(default_factory=dict)
    linked_layer_keys: list[str] = Field(default_factory=list)
    requirement_keys: list[str] = Field(default_factory=list)
    standard_keys: list[str] = Field(default_factory=list)
    source_locator: str = ""
    source_excerpt: str = ""
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    review_status: CandidateReviewStatus = CandidateReviewStatus.OPEN
    review_comment: str = ""
    committed_object_id: str | None = None


class AnalysisComponentNeedCandidate(BaseModel):
    id: str = Field(default_factory=lambda: new_id("acn"))
    candidate_key: str
    name: str
    component_role: str = ""
    criteria: dict[str, str] = Field(default_factory=dict)
    requirement_keys: list[str] = Field(default_factory=list)
    source_locator: str = ""
    source_excerpt: str = ""
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    review_status: CandidateReviewStatus = CandidateReviewStatus.OPEN
    review_comment: str = ""
    committed_object_id: str | None = None


class AnalysisTechnicalSourceCandidate(BaseModel):
    candidate_key: str
    title: str
    source_type: TechnicalSourceType = TechnicalSourceType.DATASHEET
    channel: TechnicalSourceChannel = TechnicalSourceChannel.WEB_LINK
    provider: str = ''
    external_reference: str = ''
    url: str = ''
    revision: str = ''
    document_date: str = ''
    evidence_locator: str = ''
    notes: str = ''


class AnalysisComponentCandidate(BaseModel):
    id: str = Field(default_factory=lambda: new_id("acmp"))
    candidate_key: str
    name: str
    candidate_kind: ComponentCandidateKind = ComponentCandidateKind.LOGICAL_ROLE
    component_type: str = "Generic Component"
    manufacturer: str = ""
    manufacturer_part_number: str = ""
    legacy_ecad_reference: str = ""
    representation: ComponentRepresentation = ComponentRepresentation.LOGICAL
    lifecycle: ComponentLifecycle = ComponentLifecycle.UNKNOWN
    package_name: str = ""
    supplier: str = ""
    supplier_part_number: str = ""
    quantity: int = 1
    decision_type: ComponentDecisionType = ComponentDecisionType.PROPOSED
    provenance: RealizationProvenance = RealizationProvenance.PROPOSED
    substitution_policy: SubstitutionPolicy = SubstitutionPolicy.ALLOWED
    requirement_keys: list[str] = Field(default_factory=list)
    component_need_keys: list[str] = Field(default_factory=list)
    interface_keys: list[str] = Field(default_factory=list)
    interface_hints: list[str] = Field(default_factory=list)
    system_defining: bool | None = None
    system_defining_reason: str = ''
    part_revision: str = ''
    alternative_component_keys: list[str] = Field(default_factory=list)
    technical_sources: list[AnalysisTechnicalSourceCandidate] = Field(default_factory=list)
    source_locator: str = ""
    source_excerpt: str = ""
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    review_status: CandidateReviewStatus = CandidateReviewStatus.OPEN
    review_comment: str = ""
    committed_object_id: str | None = None


class AnalysisSoftwareComponentCandidate(BaseModel):
    id: str = Field(default_factory=lambda: new_id("aswcmp"))
    candidate_key: str
    name: str
    domain: SoftwareDomain = SoftwareDomain.FIRMWARE
    kind: SoftwareComponentKind = SoftwareComponentKind.OTHER
    version: str = ""
    runtime: str = ""
    provenance: RealizationProvenance = RealizationProvenance.PROPOSED
    substitution_policy: SubstitutionPolicy = SubstitutionPolicy.ALLOWED
    requirement_keys: list[str] = Field(default_factory=list)
    interface_keys: list[str] = Field(default_factory=list)
    source_locator: str = ""
    source_excerpt: str = ""
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    review_status: CandidateReviewStatus = CandidateReviewStatus.OPEN
    review_comment: str = ""
    committed_object_id: str | None = None


class AnalysisArchitectureDomainCandidate(BaseModel):
    candidate_key: str
    name: str
    domain_type_id: str = "GEN.OTHER"
    technical_domain_ids: list[str] = Field(default_factory=list)
    partition_rationale: str = ""
    description: str = ""
    requirement_keys: list[str] = Field(default_factory=list)


class AnalysisArchitectureElementCandidate(BaseModel):
    candidate_key: str
    domain_key: str
    name: str
    role_type_id: str = "GEN.FUNCTION_BLOCK"
    technical_domain_ids: list[str] = Field(default_factory=list)
    partition_rationale: str = ""
    description: str = ""
    requirement_keys: list[str] = Field(default_factory=list)
    component_keys: list[str] = Field(default_factory=list)
    technical_realization_keys: list[str] = Field(default_factory=list)


class AnalysisArchitectureInterfaceCandidate(BaseModel):
    candidate_key: str
    name: str
    signal_type: SignalType = SignalType.INTERFACE
    port_type: str = "Generic Interface"
    connection_type: ConnectionType = ConnectionType.BUS
    interface_template: str = ""
    catalog_family: str = "Interface"
    technical_domain: str = "Other"
    additional_info: str = "Signal"
    voltage_frequency: str = ""
    active_low: bool = False
    differential: bool = False
    host_element_key: str | None = None
    participant_element_keys: list[str] = Field(default_factory=list)
    requirement_keys: list[str] = Field(default_factory=list)
    observed_signal_names: list[str] = Field(default_factory=list)
    source_locator: str = ""
    connection_evidence: str = ""
    direction_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    topology_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    excluded_internal_signal_count: int = Field(default=0, ge=0)
    rationale: str = ""
    review_status: CandidateReviewStatus = CandidateReviewStatus.OPEN
    review_comment: str = ""


class AnalysisSheetCandidate(BaseModel):
    sheet_name: str
    source_locator: str = ""
    function: str = ""
    hierarchy_path: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class AnalysisInternalNetCandidate(BaseModel):
    observed_name: str
    architecture_element_key: str = ""
    source_locator: str = ""
    purpose: str = ""
    exclusion_rationale: str = "AE-internes Implementierungsnetz"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    review_status: CandidateReviewStatus = CandidateReviewStatus.OPEN
    review_comment: str = ""


class AnalysisStandardCandidate(BaseModel):
    id: str = Field(default_factory=lambda: new_id("astd"))
    candidate_key: str
    designation: str
    title: str = ""
    edition: str = ""
    organization: str = ""
    clauses: list[str] = Field(default_factory=list)
    requirement_keys: list[str] = Field(default_factory=list)
    source_locator: str = ""
    source_excerpt: str = ""
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    review_status: CandidateReviewStatus = CandidateReviewStatus.OPEN
    review_comment: str = ""
    committed_object_id: str | None = None


class AnalysisRealizationVariantCandidate(BaseModel):
    id: str = Field(default_factory=lambda: new_id("arvar"))
    candidate_key: str
    name: str
    status: SolutionVariantStatus = SolutionVariantStatus.CANDIDATE
    a_part_component_key: str = ""
    core_component_keys: list[str] = Field(default_factory=list)
    b_part_component_keys: list[str] = Field(default_factory=list)
    software_component_keys: list[str] = Field(default_factory=list)
    interface_keys: list[str] = Field(default_factory=list)
    standard_keys: list[str] = Field(default_factory=list)
    technical_parameters: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    rationale: str = ""


class AnalysisTechnicalRealizationCandidate(BaseModel):
    id: str = Field(default_factory=lambda: new_id("areal"))
    candidate_key: str
    name: str
    generic_function: str = ""
    requirement_keys: list[str] = Field(default_factory=list)
    architecture_element_hint: str = ""
    variants: list[AnalysisRealizationVariantCandidate] = Field(default_factory=list)
    source_locator: str = ""
    source_excerpt: str = ""
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    review_status: CandidateReviewStatus = CandidateReviewStatus.OPEN
    review_comment: str = ""
    committed_object_id: str | None = None


class AnalysisVerificationCandidate(BaseModel):
    id: str = Field(default_factory=lambda: new_id("avcase"))
    candidate_key: str
    title: str
    method: VerificationMethod = VerificationMethod.TEST
    requirement_keys: list[str] = Field(default_factory=list)
    objective: str = ""
    procedure: str = ""
    expected_result: str = ""
    source_locator: str = ""
    source_excerpt: str = ""
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    review_status: CandidateReviewStatus = CandidateReviewStatus.OPEN
    review_comment: str = ""
    committed_object_id: str | None = None


class DocumentAnalysisRevision(BaseModel):
    id: str = Field(default_factory=lambda: new_id("dan"))
    document_id: str
    revision_number: int = 1
    stage: DocumentAnalysisStage = DocumentAnalysisStage.REQUIREMENTS
    provider: str = ""
    model: str = ""
    prompt: str = ""
    status: DocumentAnalysisStatus = DocumentAnalysisStatus.REVIEW_READY
    created_at: str = Field(default_factory=utc_now)
    completed_at: str = Field(default_factory=utc_now)
    system_core_idea: str = ""
    system_boundary: str = ""
    primary_flow: str = ""
    operating_locations: list[str] = Field(default_factory=list)
    operating_scenarios: list[str] = Field(default_factory=list)
    external_systems: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    requirements: list[AnalysisRequirementCandidate] = Field(default_factory=list)
    interfaces: list[AnalysisInterfaceCandidate] = Field(default_factory=list)
    component_needs: list[AnalysisComponentNeedCandidate] = Field(default_factory=list)
    components: list[AnalysisComponentCandidate] = Field(default_factory=list)
    software_components: list[AnalysisSoftwareComponentCandidate] = Field(default_factory=list)
    standards: list[AnalysisStandardCandidate] = Field(default_factory=list)
    technical_realizations: list[AnalysisTechnicalRealizationCandidate] = Field(default_factory=list)
    verification_cases: list[AnalysisVerificationCandidate] = Field(default_factory=list)
    architecture_name: str = ""
    architecture_domains: list[AnalysisArchitectureDomainCandidate] = Field(default_factory=list)
    architecture_elements: list[AnalysisArchitectureElementCandidate] = Field(default_factory=list)
    architecture_interfaces: list[AnalysisArchitectureInterfaceCandidate] = Field(default_factory=list)
    sheet_inventory: list[AnalysisSheetCandidate] = Field(default_factory=list)
    internal_nets: list[AnalysisInternalNetCandidate] = Field(default_factory=list)
    architecture_open_questions: list[str] = Field(default_factory=list)
    architecture_assumptions: list[str] = Field(default_factory=list)
    architecture_proposal_id: str | None = None
    open_questions: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    review_comment: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class StandardReference(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: new_id("std"))
    designation: str
    title: str = ""
    edition: str = ""
    organization: str = ""
    language: str = ""
    applicability: StandardApplicability = StandardApplicability.CANDIDATE
    publication_status: str = ""
    effective_date: str = ""
    supersedes: list[str] = Field(default_factory=list)
    superseded_by: list[str] = Field(default_factory=list)
    external_identifier: str = ""
    access_class: TechnicalSourceAccess = TechnicalSourceAccess.PUBLIC
    last_checked_at: str | None = None
    description: str = ""
    source_url: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class RequirementStandardLink(BaseModel):
    id: str = Field(default_factory=lambda: new_id("stdlink"))
    requirement_id: str
    standard_id: str
    clause: str = ""
    rationale: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class RequirementDerivation(BaseModel):
    id: str = Field(default_factory=lambda: new_id("rderive"))
    source_requirement_id: str
    derived_requirement_id: str
    rationale: str = ""
    approved: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class Observation(BaseModel):
    """An As-Is fact or study result; it is never implicitly a requirement."""
    id: str = Field(default_factory=lambda: new_id("obs"))
    kind: str = "Component"
    title: str
    description: str = ""
    source_document_id: str | None = None
    source_locator: str = ""
    target_type: str = ""
    target_id: str = ""
    created_at: str = Field(default_factory=utc_now)


class ModelRelation(BaseModel):
    """Explicit typed edge between stable project objects."""
    id: str = Field(default_factory=lambda: new_id("rel"))
    kind: str
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    direction: str = "source_to_target"
    role: str = ""
    rationale: str = ""
    source_document_id: str | None = None
    source_locator: str = ""
    status: str = "Proposed"
    history: list[dict[str, str]] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now)


class FulfillmentAssessment(BaseModel):
    id: str = Field(default_factory=lambda: new_id("fulfill"))
    requirement_id: str
    realization_id: str
    variant_id: str | None = None
    criteria_results: dict[str, str] = Field(default_factory=dict)
    result: str = "Draft"  # Draft, Passed, Failed
    rationale: str = ""
    evidence_reference: str = ""
    status: str = "Draft"  # Draft, Reviewed, Stale
    assessed_at: str = Field(default_factory=utc_now)
    reviewed_revisions: dict[str, str] = Field(default_factory=dict)


class VerificationCase(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: new_id("vcase"))
    identifier: str = ""
    title: str
    method: VerificationMethod = VerificationMethod.TEST
    status: VerificationStatus = VerificationStatus.PLANNED
    definition_status: TestDefinitionStatus = TestDefinitionStatus.DRAFT
    execution_status: TestExecutionStatus = TestExecutionStatus.NOT_RUN
    requirement_ids: list[str] = Field(default_factory=list)
    objective: str = ""
    procedure: str = ""
    expected_result: str = ""
    evidence_reference: str = ""
    actual_result: str = ""
    verified_revision: str = ""
    configuration_reference: str = ""
    executed_at: str | None = None
    reviewed_revisions: dict[str, str] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_status(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        result = dict(value)
        legacy = str(result.get("status", VerificationStatus.PLANNED.value))
        definitions = {
            VerificationStatus.PLANNED.value: TestDefinitionStatus.DRAFT.value,
            VerificationStatus.DEFINED.value: TestDefinitionStatus.DEFINED.value,
            VerificationStatus.READY.value: TestDefinitionStatus.APPROVED.value,
            VerificationStatus.PASSED.value: TestDefinitionStatus.APPROVED.value,
            VerificationStatus.FAILED.value: TestDefinitionStatus.APPROVED.value,
            VerificationStatus.BLOCKED.value: TestDefinitionStatus.APPROVED.value,
            VerificationStatus.OBSOLETE.value: TestDefinitionStatus.APPROVED.value,
        }
        executions = {
            VerificationStatus.PASSED.value: TestExecutionStatus.PASSED.value,
            VerificationStatus.FAILED.value: TestExecutionStatus.FAILED.value,
            VerificationStatus.BLOCKED.value: TestExecutionStatus.BLOCKED.value,
            VerificationStatus.OBSOLETE.value: TestExecutionStatus.OBSOLETE.value,
        }
        result.setdefault("definition_status", definitions.get(legacy, TestDefinitionStatus.DRAFT.value))
        result.setdefault("execution_status", executions.get(legacy, TestExecutionStatus.NOT_RUN.value))
        return result


class RequirementLink(BaseModel):
    id: str = Field(default_factory=lambda: new_id("rlink"))
    requirement_id: str
    target_type: RequirementTargetType
    target_id: str
    relation: RequirementRelation = RequirementRelation.ALLOCATED_TO
    rationale: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class EngineeringConflict(BaseModel):
    """Controlled discrepancy between a requirement and its technical implementation."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: new_id("conflict"))
    title: str
    description: str = ""
    requirement_ids: list[str] = Field(default_factory=list)
    target_type: RequirementTargetType | None = None
    target_id: str | None = None
    cause: str = ""
    impact: str = ""
    status: EngineeringConflictStatus = EngineeringConflictStatus.OPEN
    resolution: EngineeringConflictResolution = EngineeringConflictResolution.UNDECIDED
    resolution_note: str = ""
    created_at: str = Field(default_factory=utc_now)
    resolved_at: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class ComponentStandardClaim(BaseModel):
    """A revision-specific part qualification, separate from system verification."""
    standard_id: str
    result: Literal['Offen','Erfüllt','Teilweise erfüllt','Nicht erfüllt'] = 'Offen'
    scope: str = ''
    evidence_source_ids: list[str] = Field(default_factory=list)
    rationale: str = ''
    reviewed_part_fingerprint: str = ''
    reviewed_source_fingerprints: dict[str,str] = Field(default_factory=dict)
    reviewed_standard_fingerprint: str = ''


class DesignComponent(ArchitectureAttributes):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: new_id("cmp"))
    name: str
    component_type: str = "Generic Component"
    manufacturer: str = ""
    manufacturer_part_number: str = ""
    legacy_ecad_reference: str = ""
    representation: ComponentRepresentation = ComponentRepresentation.LOGICAL
    lifecycle: ComponentLifecycle = ComponentLifecycle.UNKNOWN
    package_name: str = ""
    supplier: str = ""
    supplier_part_number: str = ""
    quantity: int = 1
    decision_type: ComponentDecisionType = ComponentDecisionType.PROPOSED
    provenance: RealizationProvenance = RealizationProvenance.MANUAL
    substitution_policy: SubstitutionPolicy = SubstitutionPolicy.ALLOWED
    verification: ComponentVerification = ComponentVerification.UNVERIFIED
    source_document_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    mandated_by_requirement_ids: list[str] = Field(default_factory=list)
    component_requirement_ids: list[str] = Field(default_factory=list)
    interface_requirement_ids: list[str] = Field(default_factory=list)
    interface_hints: list[str] = Field(default_factory=list)
    qualification: dict[str, str] = Field(default_factory=dict)
    system_defining: bool | None = None
    system_defining_reason: str = ''
    part_revision: str = ''
    alternative_component_ids: list[str] = Field(default_factory=list)
    standard_claims: list[ComponentStandardClaim] = Field(default_factory=list)
    rationale: str = ""
    description: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class ComponentRequirement(BaseModel):
    """Approved technical selection criteria for a logical role or A-Part."""

    id: str = Field(default_factory=lambda: new_id("cneed"))
    name: str
    component_role: str = ""
    criteria: dict[str, str] = Field(default_factory=dict)
    requirement_ids: list[str] = Field(default_factory=list)
    source_document_id: str | None = None
    rationale: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class InterfaceRequirement(ArchitectureAttributes):
    """Approved early interface inventory before concrete AE allocation."""

    id: str = Field(default_factory=lambda: new_id("ifreq"))
    name: str
    interface_class: InterfaceClass = InterfaceClass.ELECTRONIC
    family: str = "Interface"
    protocol: str = ""
    port_type: str = "Generic Interface"
    signal_type: SignalType = SignalType.INTERFACE
    connection_type: ConnectionType = ConnectionType.BUS
    interface_template: str = ""
    host_role: str = ""
    participant_roles: list[str] = Field(default_factory=list)
    topology: str = "Point-to-point"
    data_rate: str = ""
    voltage: str = ""
    isolation: str = ""
    safety_redundancy: str = ""
    medium_connector: str = ""
    provider: str = ""
    consumer: str = ""
    physical_properties: dict[str, str] = Field(default_factory=dict)
    protocol_properties: dict[str, str] = Field(default_factory=dict)
    linked_layer_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    component_ids: list[str] = Field(default_factory=list)
    standard_ids: list[str] = Field(default_factory=list)
    standards_required: bool = False
    maturity: RequirementMaturity = RequirementMaturity.IN_REVIEW
    source_document_id: str | None = None
    rationale: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class TechnicalSource(BaseModel):
    """Reference or locally stored evidence for one standard or component."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: new_id("tsrc"))
    owner_type: TechnicalSourceOwner
    owner_id: str
    title: str
    source_type: TechnicalSourceType = TechnicalSourceType.OTHER
    channel: TechnicalSourceChannel = TechnicalSourceChannel.WEB_LINK
    provider: str = ""
    external_reference: str = ""
    url: str = ""
    access: TechnicalSourceAccess = TechnicalSourceAccess.PUBLIC
    status: TechnicalSourceStatus = TechnicalSourceStatus.CANDIDATE
    attachment_file_name: str = ""
    attachment_media_type: str = ""
    attachment_path: str = ""
    attachment_size: int = 0
    checksum_sha256: str = ""
    revision: str = ""
    document_date: str = ''
    release_status: str = ''
    extracted_content: str = ''
    evidence_locator: str = ""
    claim_status: EvidenceClaimStatus = EvidenceClaimStatus.UNASSESSED
    requirement_ids: list[str] = Field(default_factory=list)
    interface_requirement_ids: list[str] = Field(default_factory=list)
    referenced_standard_ids: list[str] = Field(default_factory=list)
    notes: str = ""
    created_at: str = Field(default_factory=utc_now)
    last_checked_at: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class ComponentAllocation(BaseModel):
    id: str = Field(default_factory=lambda: new_id("calloc"))
    component_id: str
    element_id: str
    role: str = "Realizes"
    quantity: int = 1
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class RealizationComponentRole(BaseModel):
    component_id: str
    role: ComponentRoleInRealization
    purpose: str = ""
    quantity: int = Field(default=1, ge=1)


class FunctionElement(ArchitectureAttributes):
    """Abstract discipline function, shared by architecture and realization views."""
    id: str = Field(default_factory=lambda: new_id('fe'))
    discipline: Literal['hardware','software','mechanical'] = 'hardware'
    realization_ids: list[str] = Field(default_factory=list)
    interface_requirement_ids: list[str] = Field(default_factory=list)
    name: str
    description: str = ''
    architecture_element_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    dependency_ids: list[str] = Field(default_factory=list)
    interface_signal_ids: list[str] = Field(default_factory=list)
    source_block_uuid: str = ''
    source_project: str = ''
    source_sheet: str = ''
    source_revision: str = ''
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class IntegrationInterface(ArchitectureAttributes):
    """Explicit cross-discipline contract, with references to existing objects."""
    id: str = Field(default_factory=lambda: new_id('integration'))
    kind: Literal['HSI','HW-Mechanik'] = 'HSI'
    name: str
    description: str = ''
    hardware_element_ids: list[str] = Field(default_factory=list)
    signal_ids: list[str] = Field(default_factory=list)
    component_ids: list[str] = Field(default_factory=list)
    software_element_ids: list[str] = Field(default_factory=list)
    software_component_ids: list[str] = Field(default_factory=list)
    software_interface_ids: list[str] = Field(default_factory=list)
    mechanical_element_ids: list[str] = Field(default_factory=list)
    mechanical_component_ids: list[str] = Field(default_factory=list)
    mechanical_interface_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    configuration: dict[str, str] = Field(default_factory=dict)
    revision: str = ''
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class TechnicalValue(BaseModel):
    """Concrete value owned by a realization, with reproducible measurement context."""
    id: str = Field(default_factory=lambda: new_id('value'))
    owner_id: str
    target_id: str | None = None
    key: str
    value: Any
    unit: str = ''
    conditions: dict[str, str] = Field(default_factory=dict)
    origin: Literal['Explizite Designangabe','Berechnet','Simuliert','Gemessen'] = 'Explizite Designangabe'
    variant_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    revision: str = ''
    rationale: str = ''


class SolutionVariant(BaseModel):
    id: str = Field(default_factory=lambda: new_id("rvar"))
    name: str
    status: SolutionVariantStatus = SolutionVariantStatus.CANDIDATE
    component_roles: list[RealizationComponentRole] = Field(default_factory=list)
    software_component_ids: list[str] = Field(default_factory=list)
    mechanical_component_ids: list[str] = Field(default_factory=list)
    architecture_element_ids: list[str] = Field(default_factory=list)
    interface_requirement_ids: list[str] = Field(default_factory=list)
    standard_ids: list[str] = Field(default_factory=list)
    technical_parameters: dict[str, str] = Field(default_factory=dict)
    evidence_source_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    rationale: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class TechnicalRealization(ArchitectureAttributes):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: new_id("real"))
    name: str
    generic_function: str = ""
    requirement_ids: list[str] = Field(default_factory=list)
    architecture_element_id: str | None = None
    function_element_id: str | None = None
    status: TechnicalRealizationStatus = TechnicalRealizationStatus.DRAFT
    provenance: RealizationProvenance = RealizationProvenance.MANUAL
    variants: list[SolutionVariant] = Field(default_factory=list)
    selected_variant_id: str | None = None
    source_document_id: str | None = None
    rationale: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class InterfaceMemberDefinition(BaseModel):
    name_pattern: str
    direction_from_host: Direction = Direction.INOUT
    host_pin_type: str = "BI"
    participant_pin_type: str = "BI"
    active_low: bool = False
    required: bool = True
    description: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class ProjectInterfaceTemplate(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: new_id("ifdef"))
    name: str
    version: int = 1
    family: str = "Interface"
    port_type: str = "Generic Interface"
    signal_type: SignalType = SignalType.INTERFACE
    connection_type: ConnectionType = ConnectionType.BUS
    aliases: list[str] = Field(default_factory=list)
    members: list[InterfaceMemberDefinition] = Field(default_factory=list)
    description: str = ""
    deprecated: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class InterfaceDefinition(BaseModel):
    """Versioned, tool-neutral interface definition used by links and ports."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    name: str
    version: int = 1
    family: str = "Interface"
    port_type: str = Field(default="Generic Interface", alias="portType")
    source: str = ""
    aliases: list[str] = Field(default_factory=list)
    members: list[InterfaceMemberDefinition] = Field(default_factory=list)
    description: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_signals(cls, value: Any) -> Any:
        if not isinstance(value, dict) or value.get("members"):
            return value
        legacy_signals = value.get("signals")
        if isinstance(legacy_signals, list):
            migrated = dict(value)
            migrated["members"] = [
                {
                    "name_pattern": str(item),
                    "properties": {"migratedFrom": "signals"},
                }
                for item in legacy_signals
                if str(item).strip()
            ]
            return migrated
        return value


class ProposedDomain(BaseModel):
    candidate_id: str
    name: str
    domain_type_id: str = "GEN.OTHER"
    technical_domain_ids: list[str] = Field(default_factory=list)
    partition_rationale: str = ""
    description: str = ""
    requirement_ids: list[str] = Field(default_factory=list)
    selected_for_execution: bool = True


class ProposedElement(BaseModel):
    candidate_id: str
    domain_candidate_id: str
    name: str
    role_type_id: str = "GEN.FUNCTION_BLOCK"
    technical_domain_ids: list[str] = Field(default_factory=list)
    partition_rationale: str = ""
    description: str = ""
    requirement_ids: list[str] = Field(default_factory=list)
    component_ids: list[str] = Field(default_factory=list)
    technical_realization_ids: list[str] = Field(default_factory=list)
    selected_for_execution: bool = True


class ProposedDisciplineElement(BaseModel):
    discipline: Literal['hardware','software','mechanical'] = 'hardware'
    candidate_id: str
    name: str
    description: str = ''
    requirement_ids: list[str] = Field(default_factory=list)
    parent_candidate_id: str = ''
    architecture_element_candidate_id: str = ''
    realization_ids: list[str] = Field(default_factory=list)
    selected_for_execution: bool = True


class ProposedInterface(BaseModel):
    candidate_id: str
    name: str
    signal_type: SignalType = SignalType.INTERFACE
    port_type: str = "Generic Interface"
    connection_type: ConnectionType = ConnectionType.BUS
    interface_template: str = ""
    catalog_family: str = "Interface"
    technical_domain: str = "Other"
    additional_info: str = "Signal"
    voltage_frequency: str = ""
    active_low: bool = False
    differential: bool = False
    host_element_candidate_id: str | None = None
    participant_element_candidate_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    observed_signal_names: list[str] = Field(default_factory=list)
    source_locator: str = ""
    connection_evidence: str = ""
    direction_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    topology_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    excluded_internal_signal_count: int = Field(default=0, ge=0)
    rationale: str = ""
    selected_for_execution: bool = True


class ArchitectureProposal(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: new_id("proposal"))
    name: str = "Initial architecture proposal"
    system_elements: list[ProposedDisciplineElement] = Field(default_factory=list)
    mechanical_elements: list[ProposedDisciplineElement] = Field(default_factory=list)
    software_elements: list[ProposedDisciplineElement] = Field(default_factory=list)
    function_elements: list[ProposedDisciplineElement] = Field(default_factory=list)
    status: ProposalStatus = ProposalStatus.DRAFT
    created_at: str = Field(default_factory=utc_now)
    provider: str = ""
    model: str = ""
    guidance: str = ""
    review_comment: str = ""
    reviewed_at: str | None = None
    domains: list[ProposedDomain] = Field(default_factory=list)
    elements: list[ProposedElement] = Field(default_factory=list)
    interfaces: list[ProposedInterface] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class AIReview(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: new_id("aireview"))
    title: str
    prompt: str
    answer: str = ""
    findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    status: AIReviewStatus = AIReviewStatus.DRAFT
    provider: str = ""
    model: str = ""
    created_at: str = Field(default_factory=utc_now)
    review_comment: str = ""
    reviewed_at: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class AIChangeItem(BaseModel):
    id: str = Field(default_factory=lambda: new_id("aichg"))
    object_type: AIChangeObjectType
    object_id: str
    field_name: str
    before_value: str = ""
    after_value: str
    rationale: str = ""
    status: AIChangeItemStatus = AIChangeItemStatus.OPEN


class AIChangeProposal(BaseModel):
    id: str = Field(default_factory=lambda: new_id("aicset"))
    title: str = "KI-Änderungsvorschlag"
    prompt: str
    answer: str = ""
    context_scope: str = "Projekt"
    selected_object_id: str = ''
    provider: str = ""
    model: str = ""
    created_at: str = Field(default_factory=utc_now)
    status: ProposalStatus = ProposalStatus.DRAFT
    changes: list[AIChangeItem] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    review_comment: str = ""
    reviewed_at: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class ArchitecturePackage(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    property_definitions: list[PropertyDefinition] = Field(default_factory=list, alias="propertyDefinitions")
    net_classes: list[NetClassDefinition] = Field(default_factory=default_netclasses, alias="netClasses")
    schema_version: str = Field(default="isd-suite/v3", alias="schemaVersion")
    project: ProjectInfo = Field(default_factory=ProjectInfo)
    system_domains: list[SystemDomain] = Field(default_factory=list, alias="systemDomains")
    system_elements: list[SystemElement] = Field(default_factory=list, alias="systemElements")
    system_relations: list[SystemRelation] = Field(default_factory=list, alias="systemRelations")
    mechanical_architecture_elements: list[MechanicalArchitectureElement] = Field(default_factory=list, alias='mechanicalArchitectureElements')
    software_architecture_elements: list[SoftwareArchitectureElement] = Field(default_factory=list, alias='softwareArchitectureElements')
    discipline_relations: list[DisciplineRelation] = Field(default_factory=list, alias='disciplineRelations')
    architecture_allocations: list[ArchitectureAllocation] = Field(default_factory=list, alias="architectureAllocations")
    system_definition: SystemDefinition = Field(default_factory=SystemDefinition, alias="systemDefinition")
    interface_definitions: list[InterfaceDefinition] = Field(default_factory=list, alias="interfaceDefinitions")
    interface_templates: list[ProjectInterfaceTemplate] = Field(default_factory=list, alias="interfaceTemplates")
    source_documents: list[SourceDocument] = Field(default_factory=list, alias="sourceDocuments")
    document_analyses: list[DocumentAnalysisRevision] = Field(default_factory=list, alias="documentAnalyses")
    requirements: list[EcadRequirement] = Field(default_factory=list)
    requirement_links: list[RequirementLink] = Field(default_factory=list, alias="requirementLinks")
    requirement_derivations: list[RequirementDerivation] = Field(default_factory=list, alias="requirementDerivations")
    observations: list[Observation] = Field(default_factory=list)
    model_relations: list[ModelRelation] = Field(default_factory=list, alias="modelRelations")
    fulfillment_assessments: list[FulfillmentAssessment] = Field(default_factory=list, alias="fulfillmentAssessments")
    engineering_conflicts: list[EngineeringConflict] = Field(default_factory=list, alias="engineeringConflicts")
    standards: list[StandardReference] = Field(default_factory=list)
    requirement_standard_links: list[RequirementStandardLink] = Field(default_factory=list, alias="requirementStandardLinks")
    verification_cases: list[VerificationCase] = Field(default_factory=list, alias="verificationCases")
    components: list[DesignComponent] = Field(default_factory=list)
    component_requirements: list[ComponentRequirement] = Field(default_factory=list, alias="componentRequirements")
    interface_requirements: list[InterfaceRequirement] = Field(default_factory=list, alias="interfaceRequirements")
    technical_sources: list[TechnicalSource] = Field(default_factory=list, alias="technicalSources")
    technical_realizations: list[TechnicalRealization] = Field(default_factory=list, alias="technicalRealizations")
    integration_interfaces: list[IntegrationInterface] = Field(default_factory=list, alias='integrationInterfaces')
    technical_values: list[TechnicalValue] = Field(default_factory=list, alias='technicalValues')
    function_elements: list[FunctionElement] = Field(default_factory=list, alias='functionElements')
    mechanical_components: list[MechanicalComponent] = Field(default_factory=list, alias="mechanicalComponents")
    mechanical_constraints: list[MechanicalConstraint] = Field(default_factory=list, alias="mechanicalConstraints")
    software_components: list[SoftwareComponent] = Field(default_factory=list, alias="softwareComponents")
    software_work_items: list[SoftwareWorkItem] = Field(default_factory=list, alias="softwareWorkItems")
    component_allocations: list[ComponentAllocation] = Field(default_factory=list, alias="componentAllocations")
    architecture_proposals: list[ArchitectureProposal] = Field(default_factory=list, alias="architectureProposals")
    ai_reviews: list[AIReview] = Field(default_factory=list, alias="aiReviews")
    ai_change_proposals: list[AIChangeProposal] = Field(default_factory=list, alias="aiChangeProposals")
    signals: list[ArchitectureSignal] = Field(default_factory=list)
    domains: list[Domain] = Field(default_factory=list)
    connections: list[Connection] = Field(default_factory=list)
    layout: dict[str, Any] = Field(default_factory=lambda: {"views": {}, "nodePositions": {}})
    xpedition: dict[str, Any] = Field(default_factory=lambda: {"configuration": {}, "synchronization": {}})
    properties: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def recover_legacy_interface_definitions(cls, value: Any) -> Any:
        """Make legacy interface references loadable before the integrated migration runs.

        Older project revisions could store an ``interfaceDefinitionId`` on a
        link, port or connection without embedding the corresponding
        definition.  v3 validates these references strictly, but the normal
        template migration only runs after the repository has constructed the
        package.  A minimal review placeholder closes that bootstrap gap and
        is enriched from the built-in or project template during preparation.
        """
        if not isinstance(value, dict):
            return value
        document = dict(value)
        raw_definitions = document.get("interfaceDefinitions", document.get("interface_definitions", []))
        definitions = list(raw_definitions) if isinstance(raw_definitions, list) else []
        raw_templates = document.get("interfaceTemplates", document.get("interface_templates", []))
        templates = raw_templates if isinstance(raw_templates, list) else []

        def object_value(item: Any, camel: str, snake: str, default: Any = None) -> Any:
            if not isinstance(item, dict):
                return default
            return item.get(camel, item.get(snake, default))

        known_ids = {
            str(item.get("id"))
            for item in [*definitions, *templates]
            if isinstance(item, dict) and item.get("id")
        }
        references: dict[str, str] = {}

        def remember(item: Any) -> None:
            reference = object_value(item, "interfaceDefinitionId", "interface_definition_id")
            if not reference:
                return
            identifier = str(reference)
            port_type = object_value(item, "portType", "port_type", "")
            references.setdefault(identifier, str(port_type or identifier))

        for signal in document.get("signals", []) or []:
            remember(signal)
        for connection in document.get("connections", []) or []:
            remember(connection)
        for domain in document.get("domains", []) or []:
            if not isinstance(domain, dict):
                continue
            for element in domain.get("elements", []) or []:
                if not isinstance(element, dict):
                    continue
                for port in element.get("ports", []) or []:
                    remember(port)

        for identifier, port_type in references.items():
            if identifier in known_ids:
                continue
            definitions.append({
                "id": identifier,
                "name": identifier,
                "version": 1,
                "family": "Interface",
                "portType": port_type,
                "source": "LegacyReference",
                "description": "Automatisch wiederhergestellte Referenz; Interfacevorlage prüfen.",
                "members": [],
                "properties": {
                    "interfaceTemplateUnresolved": True,
                    "migrationStatus": "To Review",
                },
            })
            known_ids.add(identifier)
        document["interfaceDefinitions"] = definitions
        return document

    @model_validator(mode="after")
    def validate_property_catalog(self) -> "ArchitecturePackage":
        synchronize_schema(self)
        adopt_netclasses(self)
        return self

    @model_validator(mode="after")
    def validate_references(self) -> "ArchitecturePackage":
        from .model_validation import validate_package_references
        return validate_package_references(self)

    def find_domain(self, object_id: str) -> Domain | None:
        return next((d for d in self.domains if d.id == object_id), None)

    def find_element(self, object_id: str) -> tuple[Domain, ArchitectureElement] | None:
        for domain in self.domains:
            for element in domain.elements:
                if element.id == object_id:
                    return domain, element
        return None

    def find_port(self, object_id: str) -> tuple[Domain, ArchitectureElement, InterfacePort] | None:
        for domain in self.domains:
            for element in domain.elements:
                for port in element.ports:
                    if port.id == object_id:
                        return domain, element, port
        return None

    def find_signal(self, object_id: str) -> tuple[Domain, ArchitectureElement, InterfacePort, Signal] | None:
        for domain in self.domains:
            for element in domain.elements:
                for port in element.ports:
                    for signal in port.signals:
                        if signal.id == object_id:
                            return domain, element, port, signal
        return None

    def find_architecture_signal(self, object_id: str) -> ArchitectureSignal | None:
        return next((signal for signal in self.signals if signal.id == object_id), None)

    def find_requirement(self, object_id: str) -> EcadRequirement | None:
        return next((item for item in self.requirements if item.id == object_id), None)

    def find_component(self, object_id: str) -> DesignComponent | None:
        return next((item for item in self.components if item.id == object_id), None)

    def find_technical_source(self, object_id: str) -> TechnicalSource | None:
        return next((item for item in self.technical_sources if item.id == object_id), None)

    def find_technical_realization(self, object_id: str) -> TechnicalRealization | None:
        return next((item for item in self.technical_realizations if item.id == object_id), None)

    def find_interface_requirement(self, object_id: str) -> InterfaceRequirement | None:
        return next((item for item in self.interface_requirements if item.id == object_id), None)

    def find_mechanical_component(self, object_id: str) -> MechanicalComponent | None:
        return next((item for item in self.mechanical_components if item.id == object_id), None)

    def find_mechanical_constraint(self, object_id: str) -> MechanicalConstraint | None:
        return next((item for item in self.mechanical_constraints if item.id == object_id), None)

    def find_software_component(self, object_id: str) -> SoftwareComponent | None:
        return next((item for item in self.software_components if item.id == object_id), None)

    def find_software_work_item(self, object_id: str) -> SoftwareWorkItem | None:
        return next((item for item in self.software_work_items if item.id == object_id), None)

    def find_standard(self, object_id: str) -> StandardReference | None:
        return next((item for item in self.standards if item.id == object_id), None)

    def find_verification_case(self, object_id: str) -> VerificationCase | None:
        return next((item for item in self.verification_cases if item.id == object_id), None)

    def find_architecture_proposal(self, object_id: str) -> ArchitectureProposal | None:
        return next((item for item in self.architecture_proposals if item.id == object_id), None)

    def find_ai_review(self, object_id: str) -> AIReview | None:
        return next((item for item in self.ai_reviews if item.id == object_id), None)

    def find_document_analysis(self, object_id: str) -> DocumentAnalysisRevision | None:
        return next((item for item in self.document_analyses if item.id == object_id), None)

    def find_ai_change_proposal(self, object_id: str) -> AIChangeProposal | None:
        return next((item for item in self.ai_change_proposals if item.id == object_id), None)

    def find_engineering_conflict(self, object_id: str) -> EngineeringConflict | None:
        return next((item for item in self.engineering_conflicts if item.id == object_id), None)

    def touch(self) -> None:
        self.project.updated_at = utc_now()

    def export_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True)


def demo_package(name: str = "Architecture Demo") -> ArchitecturePackage:
    controller = ArchitectureElement(
        name="Processing Unit",
        kind="Controller",
    )
    peripheral = ArchitectureElement(
        name="Sensor Interface",
        kind="Peripheral",
    )
    architecture_signal = ArchitectureSignal(
        name="SPI_1",
        signal_type=SignalType.INTERFACE,
        connection_type=ConnectionType.BUS,
        source=SignalEndpoint(element_id=controller.id, pin_type="BI"),
        sinks=[SignalEndpoint(element_id=peripheral.id, pin_type="BI")],
        bus_contents=[
            Signal(name="SPI_1_CLK", direction=Direction.OUT, pin_type="OUT"),
            Signal(name="SPI_1_MOSI", direction=Direction.OUT, pin_type="OUT"),
            Signal(name="SPI_1_MISO", direction=Direction.IN, pin_type="IN"),
            Signal(name="SPI_1_CS_N", direction=Direction.OUT, pin_type="OUT", active_low=True),
        ],
        properties={"busContentName": "SPI_1", "generatedBy": "Demo"},
    )
    source_port = InterfacePort(
        name="SPI_1", port_type="Interface", role="Host", side="Right", connection_type=ConnectionType.BUS,
        properties={"architectureSignalId": architecture_signal.id, "generatedBy": "SignalTopology", "topologyRole": "Source"},
    )
    sink_port = InterfacePort(
        name="SPI_1", port_type="Interface", role="Participant", side="Left", connection_type=ConnectionType.BUS,
        properties={"architectureSignalId": architecture_signal.id, "generatedBy": "SignalTopology", "topologyRole": "Sink"},
    )
    controller.ports.append(source_port)
    peripheral.ports.append(sink_port)
    processing = Domain(name="Processing", color="#2563EB", elements=[controller])
    io = Domain(name="Communication", color="#0F9F77", elements=[peripheral])
    connection = Connection(
        name="SPI_1", connection_type=ConnectionType.BUS, signal_id=architecture_signal.id,
        endpoints=[
            ConnectionEndpoint(element_id=controller.id, port_id=source_port.id, role=EndpointRole.SOURCE),
            ConnectionEndpoint(element_id=peripheral.id, port_id=sink_port.id, role=EndpointRole.SINK),
        ],
    )
    return ArchitecturePackage(project=ProjectInfo(name=name), signals=[architecture_signal], domains=[processing, io], connections=[connection])
