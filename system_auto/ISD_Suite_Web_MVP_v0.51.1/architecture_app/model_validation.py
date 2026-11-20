"""Cross-object SPOT integrity checks at the Pydantic model boundary.

Imported by the model validator only after model types have been initialized.
"""
from __future__ import annotations
from .models import ArchitecturePackage, EndpointRole, InterfacePort, RequirementTargetType, TechnicalRealizationStatus, TechnicalSourceOwner


def validate_package_references(package: "ArchitecturePackage") -> "ArchitecturePackage":
    ids: set[str] = {package.project.id}
    system_ids = {item.id for item in package.system_elements}
    system_domain_ids = {item.id for item in package.system_domains}
    system_names: set[str] = set()
    for item in [*package.system_domains, *package.system_elements, *package.system_relations, *package.architecture_allocations]:
        if item.id in ids:
            raise ValueError(f"Doppelte ID: {item.id}")
        ids.add(item.id)
    for item in [*package.system_domains, *package.system_elements]:
        key = item.name.strip().casefold()
        if not key or key in system_names:
            raise ValueError("Systemobjekte benötigen eindeutige, nicht leere Namen")
        system_names.add(key)
    for item in package.system_elements:
        if item.domain_id and item.domain_id not in system_domain_ids:
            raise ValueError("Systemelement verweist auf eine unbekannte Domäne")
        if set(item.requirement_ids) - {r.id for r in package.requirements}:
            raise ValueError("Systemelement verweist auf eine unbekannte Anforderung")
    for item in package.system_relations:
        if item.source_id not in system_ids or item.target_id not in system_ids:
            raise ValueError("Systemschnittstelle verweist auf ein unbekanntes Systemelement")
    from .discipline_architecture import validate_discipline_architecture
    validate_discipline_architecture(package, ids)
    allocation_keys = set()
    for item in package.architecture_allocations:
        if item.system_element_id not in system_ids:
            raise ValueError("Realisierungszuordnung verweist auf ein unbekanntes Systemelement")
        key = (item.system_element_id, item.target_kind, item.target_id)
        if key in allocation_keys:
            raise ValueError("Doppelte Realisierungszuordnung")
        allocation_keys.add(key)
    hierarchy_names: dict[str, str] = {}
    technical_names: dict[str, str] = {}
    port_owners: dict[str, str] = {}
    ports_by_id: dict[str, InterfacePort] = {}
    element_ids: set[str] = set()
    for domain in package.domains:
        domain_name_key = domain.name.casefold()
        if domain_name_key in hierarchy_names:
            raise ValueError(f"Name ist nicht eindeutig: {domain.name}")
        hierarchy_names[domain_name_key] = domain.id
        if domain.technical_name:
            if domain.technical_name in technical_names:
                raise ValueError(f"Technischer Name ist nicht eindeutig: {domain.technical_name}")
            technical_names[domain.technical_name] = domain.id
        if domain.id in ids:
            raise ValueError(f"Doppelte ID: {domain.id}")
        ids.add(domain.id)
        for element in domain.elements:
            element_name_key = element.name.casefold()
            if element_name_key in hierarchy_names:
                raise ValueError(f"Name ist nicht eindeutig: {element.name}")
            hierarchy_names[element_name_key] = element.id
            if element.technical_name:
                if element.technical_name in technical_names:
                    raise ValueError(f"Technischer Name ist nicht eindeutig: {element.technical_name}")
                technical_names[element.technical_name] = element.id
            if element.id in ids:
                raise ValueError(f"Doppelte ID: {element.id}")
            ids.add(element.id)
            element_ids.add(element.id)
            for port in element.ports:
                if port.id in ids:
                    raise ValueError(f"Doppelte ID: {port.id}")
                ids.add(port.id)
                port_owners[port.id] = element.id
                ports_by_id[port.id] = port
                for signal in port.signals:
                    if signal.id in ids:
                        raise ValueError(f"Doppelte ID: {signal.id}")
                    ids.add(signal.id)
    for connection in package.connections:
        if connection.id in ids:
            raise ValueError(f"Doppelte ID: {connection.id}")
        ids.add(connection.id)
        if len(connection.endpoints) < 2:
            raise ValueError(f"Verbindung {connection.name} benötigt mindestens zwei Endpunkte")
        for index, endpoint in enumerate(connection.endpoints):
            if endpoint.element_id not in element_ids:
                raise ValueError(f"Unbekanntes Architecture Element: {endpoint.element_id}")
            if port_owners.get(endpoint.port_id) != endpoint.element_id:
                raise ValueError(f"Port {endpoint.port_id} gehört nicht zu {endpoint.element_id}")
            expected_role = (EndpointRole.SOURCE if index == 0 else EndpointRole.SINK) if connection.signal_id else (EndpointRole.HOST if index == 0 else EndpointRole.PARTICIPANT)
            endpoint.role = expected_role
            ports_by_id[endpoint.port_id].role = "Host" if index == 0 else "Participant"
    signal_names: set[str] = set()
    for signal in package.signals:
        if signal.id in ids:
            raise ValueError(f"Doppelte ID: {signal.id}")
        ids.add(signal.id)
        key = signal.name.casefold()
        if key in signal_names:
            raise ValueError(f"Signalname ist nicht eindeutig: {signal.name}")
        signal_names.add(key)
        if signal.source and signal.source.element_id not in element_ids:
            raise ValueError(f"Signal {signal.name} referenziert unbekannte Quelle")
        sink_ids = [sink.element_id for sink in signal.sinks]
        if any(element_id not in element_ids for element_id in sink_ids):
            raise ValueError(f"Signal {signal.name} referenziert unbekannte Senke")
        if signal.source and signal.source.element_id in sink_ids:
            raise ValueError(f"Signal {signal.name}: Quelle darf nicht gleichzeitig Senke sein")
        if len(set(sink_ids)) != len(sink_ids):
            raise ValueError(f"Signal {signal.name} enthält doppelte Senken")
        for member in signal.bus_contents:
            if member.id in ids:
                raise ValueError(f"Doppelte ID: {member.id}")
            ids.add(member.id)
    architecture_signal_ids = {signal.id for signal in package.signals}
    interface_definition_ids = {
        item.id for item in package.interface_definitions
    } | {
        item.id for item in package.interface_templates
    }
    architecture_signals_by_id = {signal.id: signal for signal in package.signals}
    for domain in package.domains:
        for element in domain.elements:
            for port in element.ports:
                if port.interface_link_id:
                    linked_signal = architecture_signals_by_id.get(port.interface_link_id)
                    if linked_signal is None:
                        raise ValueError(f"Port {port.name} referenziert einen unbekannten Architektur-Link")
                    if (
                        port.interface_definition_id
                        and linked_signal.interface_definition_id
                        and port.interface_definition_id != linked_signal.interface_definition_id
                    ):
                        raise ValueError(f"Port {port.name} verwendet eine andere Interfacevorlage als sein Link")
                if (
                    port.interface_definition_id
                    and port.interface_definition_id not in interface_definition_ids
                ):
                    raise ValueError(f"Port {port.name} referenziert eine unbekannte Interfacevorlage")
    for signal in package.signals:
        if (
            signal.interface_definition_id
            and signal.interface_definition_id not in interface_definition_ids
        ):
            raise ValueError(f"Link {signal.name} referenziert eine unbekannte Interfacevorlage")
    for connection in package.connections:
        if connection.signal_id and connection.signal_id not in architecture_signal_ids:
            raise ValueError(f"Verbindung {connection.name} referenziert unbekanntes Signal")
        if connection.interface_link_id and connection.interface_link_id != connection.signal_id:
            raise ValueError(f"Verbindung {connection.name} besitzt eine inkonsistente Link-Referenz")
        if (
            connection.interface_definition_id
            and connection.interface_definition_id not in interface_definition_ids
        ):
            raise ValueError(f"Verbindung {connection.name} referenziert eine unbekannte Interfacevorlage")
    for domain in package.domains:
        for element in domain.elements:
            for port in element.ports:
                for signal in port.signals:
                    endpoint_ids = ([signal.source.element_id] if signal.source else []) + [sink.element_id for sink in signal.sinks]
                    unknown = [element_id for element_id in endpoint_ids if element_id not in element_ids]
                    if unknown:
                        raise ValueError(f"Signal {signal.name} referenziert unbekanntes Architecture Element: {unknown[0]}")
                    if signal.source and signal.source.element_id in {sink.element_id for sink in signal.sinks}:
                        raise ValueError(f"Signal {signal.name}: Quelle darf nicht gleichzeitig Senke sein")
                    if len({sink.element_id for sink in signal.sinks}) != len(signal.sinks):
                        raise ValueError(f"Signal {signal.name} enthält doppelte Senken")

    source_document_ids: set[str] = set()
    document_checksums: set[str] = set()
    for document in package.source_documents:
        if document.id in ids:
            raise ValueError(f"Doppelte ID: {document.id}")
        ids.add(document.id)
        source_document_ids.add(document.id)
        checksum = document.checksum_sha256.casefold()
        if checksum in document_checksums:
            raise ValueError("Dasselbe Quelldokument ist mehrfach enthalten")
        document_checksums.add(checksum)

    analysis_ids: set[str] = set()
    for analysis in package.document_analyses:
        if analysis.id in ids:
            raise ValueError(f"Doppelte ID: {analysis.id}")
        ids.add(analysis.id)
        analysis_ids.add(analysis.id)
        if analysis.document_id not in source_document_ids:
            raise ValueError("Dokumentanalyse referenziert ein unbekanntes Quelldokument")
        candidate_ids = [
            *(item.id for item in analysis.requirements),
            *(item.id for item in analysis.interfaces),
            *(item.id for item in analysis.component_needs),
            *(item.id for item in analysis.components),
            *(item.id for item in analysis.software_components),
            *(item.id for item in analysis.standards),
            *(item.id for item in analysis.technical_realizations),
            *(variant.id for item in analysis.technical_realizations for variant in item.variants),
            *(item.id for item in analysis.verification_cases),
        ]
        if len(candidate_ids) != len(set(candidate_ids)) or any(item in ids for item in candidate_ids):
            raise ValueError("Doppelte Kandidaten-ID in einer Dokumentanalyse")
        ids.update(candidate_ids)
        candidate_keys = [
            *(item.candidate_key for item in analysis.requirements),
            *(item.candidate_key for item in analysis.interfaces),
            *(item.candidate_key for item in analysis.component_needs),
            *(item.candidate_key for item in analysis.components),
            *(item.candidate_key for item in analysis.software_components),
            *(item.candidate_key for item in analysis.standards),
            *(item.candidate_key for item in analysis.technical_realizations),
            *(variant.candidate_key for item in analysis.technical_realizations for variant in item.variants),
            *(item.candidate_key for item in analysis.verification_cases),
        ]
        if len(candidate_keys) != len({item.casefold() for item in candidate_keys}):
            raise ValueError("Doppelter Kandidatenschlüssel in einer Dokumentanalyse")
        architecture_keys = [
            *(item.candidate_key for item in analysis.architecture_domains),
            *(item.candidate_key for item in analysis.architecture_elements),
            *(item.candidate_key for item in analysis.architecture_interfaces),
        ]
        if len(architecture_keys) != len({item.casefold() for item in architecture_keys}):
            raise ValueError("Doppelter Architekturschlüssel in einer Dokumentanalyse")
    for document in package.source_documents:
        if document.active_analysis_id and document.active_analysis_id not in analysis_ids:
            raise ValueError("Quelldokument referenziert eine unbekannte aktive Analyse")

    requirement_ids: set[str] = set()
    external_requirement_ids: set[str] = set()
    requirement_identifiers: set[str] = set()
    for requirement in package.requirements:
        if requirement.id in ids:
            raise ValueError(f"Doppelte ID: {requirement.id}")
        ids.add(requirement.id)
        requirement_ids.add(requirement.id)
        identifier = requirement.identifier.strip().casefold()
        if identifier:
            if identifier in requirement_identifiers:
                raise ValueError(f"Doppelte interne Requirement-ID: {requirement.identifier}")
            requirement_identifiers.add(identifier)
        external_id = requirement.external_id.strip().casefold()
        if external_id:
            if external_id in external_requirement_ids:
                raise ValueError(f"Doppelte externe Requirement-ID: {requirement.external_id}")
            external_requirement_ids.add(external_id)
        if requirement.source_document_id and requirement.source_document_id not in source_document_ids:
            raise ValueError(f"Requirement {requirement.id} referenziert ein unbekanntes Quelldokument")
    for requirement in package.requirements:
        unknown_parents = [item for item in requirement.parent_requirement_ids if item not in requirement_ids]
        if unknown_parents:
            raise ValueError(f"Requirement {requirement.id} referenziert ein unbekanntes Parent Requirement")
        if len(requirement.required_disciplines) != len(set(requirement.required_disciplines)):
            raise ValueError(f"Requirement {requirement.id} enthält doppelte Disziplinzuordnungen")

    derivation_pairs: set[tuple[str, str]] = set()
    for derivation in package.requirement_derivations:
        if derivation.id in ids:
            raise ValueError(f"Doppelte ID: {derivation.id}")
        ids.add(derivation.id)
        pair = (derivation.source_requirement_id, derivation.derived_requirement_id)
        if pair in derivation_pairs:
            raise ValueError("Doppelte Requirement-Ableitung")
        derivation_pairs.add(pair)
        if derivation.source_requirement_id not in requirement_ids or derivation.derived_requirement_id not in requirement_ids:
            raise ValueError("Requirement-Ableitung referenziert ein unbekanntes Requirement")
        if derivation.source_requirement_id == derivation.derived_requirement_id:
            raise ValueError("Ein Requirement kann nicht aus sich selbst abgeleitet werden")

    standard_ids: set[str] = set()
    standard_designations: set[str] = set()
    for standard in package.standards:
        if standard.id in ids:
            raise ValueError(f"Doppelte ID: {standard.id}")
        ids.add(standard.id)
        standard_ids.add(standard.id)
        designation = standard.designation.strip().casefold()
        if not designation:
            raise ValueError("Die Bezeichnung einer Norm darf nicht leer sein")
        if designation in standard_designations:
            raise ValueError(f"Doppelte Norm- oder Standardbezeichnung: {standard.designation}")
        standard_designations.add(designation)

    standard_link_pairs: set[tuple[str, str, str]] = set()
    for link in package.requirement_standard_links:
        if link.id in ids:
            raise ValueError(f"Doppelte ID: {link.id}")
        ids.add(link.id)
        if link.requirement_id not in requirement_ids or link.standard_id not in standard_ids:
            raise ValueError("Normenbezug referenziert ein unbekanntes Objekt")
        pair = (link.requirement_id, link.standard_id, link.clause.casefold())
        if pair in standard_link_pairs:
            raise ValueError("Doppelter Normenbezug eines Requirements")
        standard_link_pairs.add(pair)

    verification_identifiers: set[str] = set()
    verification_case_ids: set[str] = set()
    for verification in package.verification_cases:
        if verification.id in ids:
            raise ValueError(f"Doppelte ID: {verification.id}")
        ids.add(verification.id)
        verification_case_ids.add(verification.id)
        identifier = verification.identifier.strip().casefold()
        if identifier:
            if identifier in verification_identifiers:
                raise ValueError(f"Doppelte Verifikations-ID: {verification.identifier}")
            verification_identifiers.add(identifier)
        if not verification.requirement_ids:
            raise ValueError(f"Verifikationsfall {verification.title} deckt kein Requirement ab")
        if len(set(verification.requirement_ids)) != len(verification.requirement_ids):
            raise ValueError(f"Verifikationsfall {verification.title} enthält doppelte Requirements")
        if any(item not in requirement_ids for item in verification.requirement_ids):
            raise ValueError(f"Verifikationsfall {verification.title} referenziert ein unbekanntes Requirement")

    component_ids: set[str] = set()
    for component in package.components:
        if component.id in ids:
            raise ValueError(f"Doppelte ID: {component.id}")
        ids.add(component.id)
        component_ids.add(component.id)
        if component.source_document_id and component.source_document_id not in source_document_ids:
            raise ValueError(f"Komponente {component.name} referenziert ein unbekanntes Quelldokument")
        if any(item not in requirement_ids for item in component.requirement_ids):
            raise ValueError(f"Komponente {component.name} referenziert ein unbekanntes Requirement")
        if any(item not in requirement_ids for item in component.mandated_by_requirement_ids):
            raise ValueError(f"Komponente {component.name} referenziert eine unbekannte Implementierungsvorgabe")

    component_requirement_ids: set[str] = set()
    for component_requirement in package.component_requirements:
        if component_requirement.id in ids:
            raise ValueError(f"Doppelte ID: {component_requirement.id}")
        ids.add(component_requirement.id)
        component_requirement_ids.add(component_requirement.id)
        if component_requirement.source_document_id and component_requirement.source_document_id not in source_document_ids:
            raise ValueError("Komponentenanforderung referenziert ein unbekanntes Quelldokument")
        if any(item not in requirement_ids for item in component_requirement.requirement_ids):
            raise ValueError("Komponentenanforderung referenziert ein unbekanntes Requirement")
    for component in package.components:
        if any(item not in component_requirement_ids for item in component.component_requirement_ids):
            raise ValueError(f"Komponente {component.name} referenziert eine unbekannte Komponentenanforderung")

    interface_requirement_ids: set[str] = set()
    for interface_requirement in package.interface_requirements:
        if interface_requirement.id in ids:
            raise ValueError(f"Doppelte ID: {interface_requirement.id}")
        ids.add(interface_requirement.id)
        interface_requirement_ids.add(interface_requirement.id)
        if interface_requirement.source_document_id and interface_requirement.source_document_id not in source_document_ids:
            raise ValueError("Interface-Anforderung referenziert ein unbekanntes Quelldokument")
        if any(item not in requirement_ids for item in interface_requirement.requirement_ids):
            raise ValueError("Interface-Anforderung referenziert ein unbekanntes Requirement")
        if any(item not in component_ids for item in interface_requirement.component_ids):
            raise ValueError("Interface-Anforderung referenziert eine unbekannte Komponente")
        if any(item not in standard_ids for item in interface_requirement.standard_ids):
            raise ValueError("Interface-Anforderung referenziert eine unbekannte Norm")
    for interface_requirement in package.interface_requirements:
        if any(item not in interface_requirement_ids for item in interface_requirement.linked_layer_ids):
            raise ValueError("Interface-Anforderung referenziert einen unbekannten gekoppelten Layer")
        if interface_requirement.id in interface_requirement.linked_layer_ids:
            raise ValueError("Ein Interface kann nicht mit sich selbst gekoppelt werden")

    for component in package.components:
        if any(item not in interface_requirement_ids for item in component.interface_requirement_ids):
            raise ValueError(f"Komponente {component.name} referenziert eine unbekannte Interface-Anforderung")

    mechanical_component_ids: set[str] = set()
    for component in package.mechanical_components:
        if component.id in ids:
            raise ValueError(f"Doppelte ID: {component.id}")
        ids.add(component.id)
        mechanical_component_ids.add(component.id)
        if any(item not in requirement_ids for item in component.requirement_ids):
            raise ValueError(f"Mechanikkomponente {component.name} referenziert ein unbekanntes Requirement")
        if any(item not in source_document_ids for item in component.source_document_ids):
            raise ValueError(f"Mechanikkomponente {component.name} referenziert ein unbekanntes Quelldokument")
    for component in package.mechanical_components:
        if component.parent_component_id and component.parent_component_id not in mechanical_component_ids:
            raise ValueError(f"Mechanikkomponente {component.name} referenziert eine unbekannte Baugruppe")
        if component.parent_component_id == component.id:
            raise ValueError("Eine Mechanikkomponente kann nicht ihr eigener Parent sein")

    mechanical_constraint_ids: set[str] = set()
    for constraint in package.mechanical_constraints:
        if constraint.id in ids:
            raise ValueError(f"Doppelte ID: {constraint.id}")
        ids.add(constraint.id)
        mechanical_constraint_ids.add(constraint.id)
        if constraint.mechanical_component_id and constraint.mechanical_component_id not in mechanical_component_ids:
            raise ValueError(f"Mechanische Randbedingung {constraint.name} referenziert eine unbekannte Komponente")
        if constraint.architecture_element_id and constraint.architecture_element_id not in element_ids:
            raise ValueError(f"Mechanische Randbedingung {constraint.name} referenziert ein unbekanntes Architecture Element")
        if any(item not in requirement_ids for item in constraint.requirement_ids):
            raise ValueError(f"Mechanische Randbedingung {constraint.name} referenziert ein unbekanntes Requirement")
        if any(item not in source_document_ids for item in constraint.source_document_ids):
            raise ValueError(f"Mechanische Randbedingung {constraint.name} referenziert ein unbekanntes Quelldokument")

    software_component_ids: set[str] = set()
    for component in package.software_components:
        if component.id in ids:
            raise ValueError(f"Doppelte ID: {component.id}")
        ids.add(component.id)
        software_component_ids.add(component.id)
        if any(item not in requirement_ids for item in component.requirement_ids):
            raise ValueError(f"Softwarekomponente {component.name} referenziert ein unbekanntes Requirement")
        if any(item not in interface_requirement_ids for item in component.interface_requirement_ids):
            raise ValueError(f"Softwarekomponente {component.name} referenziert ein unbekanntes Interface")
        if component.deployment_element_id and component.deployment_element_id not in element_ids:
            raise ValueError(f"Softwarekomponente {component.name} referenziert ein unbekanntes Deployment-Ziel")
        if any(item not in requirement_ids for item in component.mandated_by_requirement_ids):
            raise ValueError(f"Softwarekomponente {component.name} referenziert eine unbekannte Implementierungsvorgabe")
        if any(item not in source_document_ids for item in component.source_document_ids):
            raise ValueError(f"Softwarekomponente {component.name} referenziert ein unbekanntes Quelldokument")
    for component in package.software_components:
        if component.parent_component_id and component.parent_component_id not in software_component_ids:
            raise ValueError(f"Softwarekomponente {component.name} referenziert einen unbekannten Parent")
        if component.parent_component_id == component.id:
            raise ValueError("Eine Softwarekomponente kann nicht ihr eigener Parent sein")

    software_work_item_ids: set[str] = set()
    for work_item in package.software_work_items:
        if work_item.id in ids:
            raise ValueError(f"Doppelte ID: {work_item.id}")
        ids.add(work_item.id)
        software_work_item_ids.add(work_item.id)
        if any(item not in requirement_ids for item in work_item.requirement_ids):
            raise ValueError(f"Software-Arbeitspaket {work_item.title} referenziert ein unbekanntes Requirement")
        if any(item not in software_component_ids for item in work_item.component_ids):
            raise ValueError(f"Software-Arbeitspaket {work_item.title} referenziert eine unbekannte Softwarekomponente")
        if any(item not in verification_case_ids for item in work_item.verification_case_ids):
            raise ValueError(f"Software-Arbeitspaket {work_item.title} referenziert einen unbekannten Test")

    technical_source_ids: set[str] = set()
    for source in package.technical_sources:
        if source.id in ids:
            raise ValueError(f"Doppelte ID: {source.id}")
        ids.add(source.id)
        technical_source_ids.add(source.id)
        if not source.title.strip():
            raise ValueError("Der Titel einer technischen Quelle darf nicht leer sein")
        if source.owner_type == TechnicalSourceOwner.COMPONENT:
            if source.owner_id not in component_ids:
                raise ValueError("Technische Quelle referenziert eine unbekannte Komponente")
        elif source.owner_type == TechnicalSourceOwner.STANDARD and source.owner_id not in standard_ids:
            raise ValueError("Technische Quelle referenziert eine unbekannte Norm")
        elif source.owner_type == TechnicalSourceOwner.INTERFACE and source.owner_id not in interface_requirement_ids:
            raise ValueError("Technische Quelle referenziert eine unbekannte Interface-Anforderung")
        if any(item not in requirement_ids for item in source.requirement_ids):
            raise ValueError("Technische Quelle referenziert ein unbekanntes Requirement")
        if any(item not in interface_requirement_ids for item in source.interface_requirement_ids):
            raise ValueError("Technische Quelle referenziert eine unbekannte Interface-Anforderung")
        if any(item not in standard_ids for item in source.referenced_standard_ids):
            raise ValueError("Technische Quelle referenziert eine unbekannte Norm")
        if not (source.url.strip() or source.external_reference.strip() or source.attachment_path.strip()):
            raise ValueError("Technische Quelle benötigt URL, externe Referenz oder Dokument")
        if source.attachment_path and not (
            source.attachment_file_name.strip() and source.checksum_sha256.strip()
        ):
            raise ValueError("Ein hinterlegtes Dokument benötigt Dateiname und Prüfsumme")

    realization_ids: set[str] = set()
    function_element_ids={f.id for f in package.function_elements}
    if len(function_element_ids)!=len(package.function_elements):raise ValueError('Doppelte FE-ID')
    for fe in package.function_elements:
        if fe.id in ids:raise ValueError('Doppelte FE-ID')
        ids.add(fe.id)
        if not fe.name.strip():raise ValueError('FE-Name fehlt')
        parent_ids={'hardware':element_ids,'software':{e.id for e in package.software_architecture_elements},'mechanical':{e.id for e in package.mechanical_architecture_elements}}[fe.discipline]
        if fe.architecture_element_id and fe.architecture_element_id not in parent_ids:raise ValueError('FE verweist auf unbekanntes AE seiner Disziplin')
        from .integration import validate_function_element
        validate_function_element(package,fe)
        if fe.discipline!='hardware' and any(r.function_element_id==fe.id for r in package.technical_realizations):raise ValueError('HW-Realisierung benötigt ein Hardware-FE')
        if any(i not in requirement_ids for i in fe.requirement_ids):raise ValueError('FE verweist auf unbekanntes Requirement')
        if any(i not in function_element_ids or i==fe.id for i in fe.dependency_ids):raise ValueError('Ungültige FE-Abhängigkeit')
        if any(i not in {s.id for s in package.signals} for i in fe.interface_signal_ids):raise ValueError('FE verweist auf unbekanntes Interface')
    for component in package.components:
        if any(i not in component_ids or i==component.id for i in component.alternative_component_ids):raise ValueError('Ungültiges Alternativbauteil')
        for claim in component.standard_claims:
            if claim.standard_id not in standard_ids:raise ValueError('Bauteilqualifikation verweist auf unbekannte Norm')
            if any(i not in technical_source_ids for i in claim.evidence_source_ids):raise ValueError('Qualifikationsquelle fehlt')
            if any(next(s for s in package.technical_sources if s.id==i).owner_id!=component.id for i in claim.evidence_source_ids):raise ValueError('Qualifikationsquelle gehört zu einem anderen Bauteil')
    for realization in package.technical_realizations:
        if realization.id in ids:
            raise ValueError(f"Doppelte ID: {realization.id}")
        ids.add(realization.id)
        realization_ids.add(realization.id)
        if realization.function_element_id and realization.function_element_id not in function_element_ids:raise ValueError('Realisierung verweist auf unbekanntes FE')
        if not realization.requirement_ids and not realization.function_element_id:
            raise ValueError(f"Technische Realisierung {realization.name} benötigt mindestens ein Requirement")
        if len(set(realization.requirement_ids)) != len(realization.requirement_ids):
            raise ValueError(f"Technische Realisierung {realization.name} enthält doppelte Requirements")
        if any(item not in requirement_ids for item in realization.requirement_ids):
            raise ValueError(f"Technische Realisierung {realization.name} referenziert ein unbekanntes Requirement")
        if realization.architecture_element_id and realization.architecture_element_id not in element_ids:
            raise ValueError(f"Technische Realisierung {realization.name} referenziert ein unbekanntes Architecture Element")
        if realization.source_document_id and realization.source_document_id not in source_document_ids:
            raise ValueError(f"Technische Realisierung {realization.name} referenziert ein unbekanntes Quelldokument")
        variant_ids = {item.id for item in realization.variants}
        if len(variant_ids) != len(realization.variants) or any(item in ids for item in variant_ids):
            raise ValueError(f"Technische Realisierung {realization.name} enthält doppelte Varianten-IDs")
        ids.update(variant_ids)
        if realization.selected_variant_id and realization.selected_variant_id not in variant_ids:
            raise ValueError(f"Technische Realisierung {realization.name} referenziert eine unbekannte ausgewählte Variante")
        if realization.status == TechnicalRealizationStatus.SELECTED and not realization.selected_variant_id:
            raise ValueError(f"Ausgewählte technische Realisierung {realization.name} benötigt eine ausgewählte Variante")
        for variant in realization.variants:
            role_pairs = [(item.component_id, item.role) for item in variant.component_roles]
            if len(role_pairs) != len(set(role_pairs)):
                raise ValueError(f"Variante {variant.name} enthält doppelte Komponentenrollen")
            if len({item.component_id for item in variant.component_roles})!=len(variant.component_roles):
                raise ValueError(f"Variante {variant.name} enthält widersprüchliche Komponentenrollen")
            if any(item.component_id not in component_ids for item in variant.component_roles):
                raise ValueError(f"Variante {variant.name} referenziert eine unbekannte Komponente")
            if any(item not in software_component_ids for item in variant.software_component_ids):
                raise ValueError(f"Variante {variant.name} referenziert eine unbekannte Softwarekomponente")
            if any(item not in mechanical_component_ids for item in variant.mechanical_component_ids):
                raise ValueError(f"Variante {variant.name} referenziert eine unbekannte Mechanikkomponente")
            if any(item not in element_ids for item in variant.architecture_element_ids):
                raise ValueError(f"Variante {variant.name} referenziert ein unbekanntes Architecture Element")
            if any(item not in interface_requirement_ids for item in variant.interface_requirement_ids):
                raise ValueError(f"Variante {variant.name} referenziert ein unbekanntes Interface")
            if any(item not in standard_ids for item in variant.standard_ids):
                raise ValueError(f"Variante {variant.name} referenziert eine unbekannte Norm")
            if any(item not in technical_source_ids for item in variant.evidence_source_ids):
                raise ValueError(f"Variante {variant.name} referenziert eine unbekannte technische Quelle")

    interface_template_ids: set[str] = set()
    interface_template_names: set[str] = set()
    for definition in package.interface_templates:
        if definition.id in ids:
            raise ValueError(f"Doppelte ID: {definition.id}")
        ids.add(definition.id)
        interface_template_ids.add(definition.id)
        name = definition.name.strip().casefold()
        if not name:
            raise ValueError("Der Name einer Interfacevorlage darf nicht leer sein")
        if name in interface_template_names:
            raise ValueError(f"Doppelter Name einer Interfacevorlage: {definition.name}")
        interface_template_names.add(name)
        member_names = [item.name_pattern.strip().casefold() for item in definition.members]
        if not member_names or any(not item for item in member_names):
            raise ValueError(f"Interfacevorlage {definition.name} benötigt gültige Mitgliedssignale")
        if len(set(member_names)) != len(member_names):
            raise ValueError(f"Interfacevorlage {definition.name} enthält doppelte Mitgliedssignale")

    from .integration import validate_integrations
    validate_integrations(package,ids)
    target_ids = set(ids)
    target_type_ids = {
        RequirementTargetType.INTEGRATION_INTERFACE:{i.id for i in package.integration_interfaces},
        RequirementTargetType.BUS_MEMBER:{m.id for s in package.signals for m in s.bus_contents},
        RequirementTargetType.SYSTEM_DOMAIN: {o.id for o in package.system_domains},
        RequirementTargetType.SYSTEM_ELEMENT: {o.id for o in package.system_elements},
        RequirementTargetType.SYSTEM_RELATION: {o.id for o in package.system_relations},
        RequirementTargetType.MECHANICAL_ARCHITECTURE_ELEMENT: {o.id for o in package.mechanical_architecture_elements},
        RequirementTargetType.SOFTWARE_ARCHITECTURE_ELEMENT: {o.id for o in package.software_architecture_elements},
        RequirementTargetType.DISCIPLINE_RELATION: {o.id for o in package.discipline_relations},
        RequirementTargetType.DOMAIN: {domain.id for domain in package.domains},
        RequirementTargetType.ELEMENT: set(element_ids),
        RequirementTargetType.PORT: {port.id for domain in package.domains for element in domain.elements for port in element.ports},
        RequirementTargetType.SIGNAL: set(architecture_signal_ids),
        RequirementTargetType.CONNECTION: {connection.id for connection in package.connections},
        RequirementTargetType.COMPONENT: set(component_ids),
        RequirementTargetType.INTERFACE: set(interface_requirement_ids),
        RequirementTargetType.MECHANICAL_COMPONENT: set(mechanical_component_ids),
        RequirementTargetType.MECHANICAL_CONSTRAINT: set(mechanical_constraint_ids),
        RequirementTargetType.SOFTWARE_COMPONENT: set(software_component_ids),
        RequirementTargetType.SOFTWARE_WORK_ITEM: set(software_work_item_ids),
        RequirementTargetType.TECHNICAL_REALIZATION: set(realization_ids),
        RequirementTargetType.FUNCTION_ELEMENT: set(function_element_ids),
        RequirementTargetType.VERIFICATION_CASE: set(verification_case_ids),
    }
    link_pairs: set[tuple[str, str, str]] = set()
    for link in package.requirement_links:
        if link.id in target_ids:
            raise ValueError(f"Doppelte ID: {link.id}")
        target_ids.add(link.id)
        if link.requirement_id not in requirement_ids:
            raise ValueError("Requirement Link referenziert ein unbekanntes Requirement")
        if link.target_id not in target_type_ids[link.target_type]:
            raise ValueError("Requirement Link referenziert ein unbekanntes Zielobjekt")
        pair = (link.requirement_id, link.target_type.value, link.target_id)
        if pair in link_pairs:
            raise ValueError("Doppelte Requirement-Zuordnung")
        link_pairs.add(pair)

    for conflict in package.engineering_conflicts:
        if conflict.id in target_ids:
            raise ValueError(f"Doppelte ID: {conflict.id}")
        target_ids.add(conflict.id)
        if not conflict.requirement_ids:
            raise ValueError(f"Konflikt {conflict.title} benötigt mindestens ein Requirement")
        if len(set(conflict.requirement_ids)) != len(conflict.requirement_ids):
            raise ValueError(f"Konflikt {conflict.title} enthält doppelte Requirements")
        if any(item not in requirement_ids for item in conflict.requirement_ids):
            raise ValueError(f"Konflikt {conflict.title} referenziert ein unbekanntes Requirement")
        if bool(conflict.target_type) != bool(conflict.target_id):
            raise ValueError(f"Konflikt {conflict.title} benötigt Zieltyp und Ziel-ID gemeinsam")
        if conflict.target_type and conflict.target_id not in target_type_ids[conflict.target_type]:
            raise ValueError(f"Konflikt {conflict.title} referenziert ein unbekanntes Zielobjekt")

    for allocation in package.component_allocations:
        if allocation.id in target_ids:
            raise ValueError(f"Doppelte ID: {allocation.id}")
        target_ids.add(allocation.id)
        if allocation.component_id not in component_ids or allocation.element_id not in element_ids:
            raise ValueError("Komponentenzuordnung referenziert ein unbekanntes Objekt")

    for proposal in package.architecture_proposals:
        if proposal.id in target_ids:
            raise ValueError(f"Doppelte ID: {proposal.id}")
        target_ids.add(proposal.id)
        domain_candidates = {item.candidate_id for item in proposal.domains}
        element_candidates = {item.candidate_id for item in proposal.elements}
        interface_candidates = {item.candidate_id for item in proposal.interfaces}
        all_candidates = [
            *(item.candidate_id for item in proposal.domains),
            *(item.candidate_id for item in proposal.elements),
            *(item.candidate_id for item in proposal.interfaces),
            *(item.candidate_id for field in ('system_elements','mechanical_elements','software_elements','function_elements') for item in getattr(proposal,field)),
        ]
        if (
            len(domain_candidates) != len(proposal.domains)
            or len(element_candidates) != len(proposal.elements)
            or len(interface_candidates) != len(proposal.interfaces)
            or len(set(all_candidates)) != len(all_candidates)
        ):
            raise ValueError("Doppelte Kandidaten-ID im Architekturvorschlag")
        for field in ('system_elements','mechanical_elements','software_elements','function_elements'):
            group=getattr(proposal,field)
            available={item.candidate_id for item in group}
            for item in group:
                if not item.name.strip():raise ValueError('Facharchitektur-Kandidat benötigt einen Namen')
                if any(i not in requirement_ids for i in item.requirement_ids):raise ValueError('Facharchitektur-Kandidat verweist auf unbekannte Anforderung')
                if item.parent_candidate_id and (item.parent_candidate_id not in available or item.parent_candidate_id==item.candidate_id):raise ValueError('Ungültiger Parent im Facharchitekturvorschlag')
        if any(item.domain_candidate_id not in domain_candidates for item in proposal.elements):
            raise ValueError("Architekturvorschlag referenziert eine unbekannte Domain")
        for domain in proposal.domains:
            if any(item not in requirement_ids for item in domain.requirement_ids):
                raise ValueError("Architekturvorschlag referenziert ein unbekanntes Requirement")
        for element in proposal.elements:
            if any(item not in requirement_ids for item in element.requirement_ids):
                raise ValueError("Architekturvorschlag referenziert ein unbekanntes Requirement")
            if any(item not in component_ids for item in element.component_ids):
                raise ValueError("Architekturvorschlag referenziert eine unbekannte Komponente")
            if any(item not in realization_ids for item in element.technical_realization_ids):
                raise ValueError("Architekturvorschlag referenziert eine unbekannte technische Realisierung")
        for interface in proposal.interfaces:
            endpoint_ids = ([interface.host_element_candidate_id] if interface.host_element_candidate_id else []) + interface.participant_element_candidate_ids
            if any(item not in element_candidates for item in endpoint_ids):
                raise ValueError("Architekturvorschlag referenziert ein unbekanntes Architecture Element")
            if interface.host_element_candidate_id in interface.participant_element_candidate_ids:
                raise ValueError("Ein vorgeschlagenes AE kann nicht gleichzeitig Host und Teilnehmer sein")
            if len(set(interface.participant_element_candidate_ids)) != len(interface.participant_element_candidate_ids):
                raise ValueError("Architekturvorschlag enthält doppelte Teilnehmer")
            if any(item not in requirement_ids for item in interface.requirement_ids):
                raise ValueError("Architekturvorschlag referenziert ein unbekanntes Requirement")
    for review in package.ai_reviews:
        if review.id in target_ids:
            raise ValueError(f"Doppelte ID: {review.id}")
        target_ids.add(review.id)
    for change_proposal in package.ai_change_proposals:
        if change_proposal.id in target_ids:
            raise ValueError(f"Doppelte ID: {change_proposal.id}")
        target_ids.add(change_proposal.id)
        change_ids = [item.id for item in change_proposal.changes]
        if len(change_ids) != len(set(change_ids)) or any(item in target_ids for item in change_ids):
            raise ValueError("Doppelte Änderungs-ID in einem KI-Vorschlag")
        target_ids.update(change_ids)
    # Validate new graph edges during every import and revision restore, not
    # only when they are created through the UI.
    from .traceability import validate_relation
    extra_ids = [item.id for item in package.observations]
    extra_ids += [item.id for item in package.model_relations]
    extra_ids += [item.id for item in package.fulfillment_assessments]
    if len(extra_ids) != len(set(extra_ids)) or any(item in target_ids for item in extra_ids):
        raise ValueError("Doppelte ID in Beobachtungen, Beziehungen oder Erfüllungsbewertungen")
    for relation in package.model_relations:
        validate_relation(package, relation)
    from .requirement_graph import validate_graph
    validate_graph(package)
    observation_ids = {item.id for item in package.observations}
    for req in package.requirements:
        if any(item not in observation_ids for item in req.observation_ids):
            raise ValueError("Requirement referenziert unbekannten Bestandsbefund")
    for assessment in package.fulfillment_assessments:
        if assessment.requirement_id not in requirement_ids:
            raise ValueError("Erfüllungsbewertung referenziert unbekanntes Requirement")
        if assessment.realization_id not in {item.id for item in package.technical_realizations}:
            raise ValueError("Erfüllungsbewertung referenziert unbekannte Realisierung")
    return package
