"""Atomic architecture proposal compilation, independent from document analysis."""
from __future__ import annotations
from .architecture_catalog import ArchitectureCatalog
from .bus_content import BusContentTemplates
from .signal_naming import concise_signal_name, normalize_generated_signal
from .models import ArchitectureElement, ArchitecturePackage, ArchitectureProposal, ArchitectureSignal, ComponentAllocation, ConnectionType, Direction, Domain, ProjectWorkflow, ProposalStatus, RequirementTargetType, Signal, SignalEndpoint, SignalType
from .topology import next_interface_index, synchronize_signal_topology
from .interface_compilation import DOMAIN_COLORS, DEFAULT_ARCHITECTURE_CATALOG, CompilationSummary, _unique_hierarchy_name, _project_template, _members_for_interface, _interface_metadata, _add_requirement_links
from .realization_service import synchronize_realization_architecture_attribute

def _compile_architecture_proposal_in_place(
    package: ArchitecturePackage,
    proposal: ArchitectureProposal,
    builtins: BusContentTemplates,
    architecture_catalog: ArchitectureCatalog | None = None,
) -> CompilationSummary:
    catalog = architecture_catalog or DEFAULT_ARCHITECTURE_CATALOG
    if proposal.status != ProposalStatus.DRAFT:
        raise ValueError("Nur ein offener Architekturvorschlag kann übernommen werden.")
    domain_map: dict[str, Domain] = {}
    element_map: dict[str, ArchitectureElement] = {}
    created_domains = 0
    created_elements = 0
    created_signals = 0
    created_allocations = 0
    initial_domain_count = len(package.domains)

    selected_domains = [item for item in proposal.domains if item.selected_for_execution]
    selected_domain_ids = {item.candidate_id for item in selected_domains}
    selected_elements = [
        item for item in proposal.elements
        if item.selected_for_execution and item.domain_candidate_id in selected_domain_ids
    ]
    selected_element_ids = {item.candidate_id for item in selected_elements}
    selected_interfaces = [item for item in proposal.interfaces if item.selected_for_execution]
    if not selected_domains and not any(c.selected_for_execution for field in ('system_elements','mechanical_elements','software_elements','function_elements') for c in getattr(proposal,field)):
        raise ValueError("Wähle mindestens eine Domain für den Architektur-Arbeitsstand aus.")

    for index, candidate in enumerate(selected_domains):
        existing_domain = next(
            (item for item in package.domains if item.id == candidate.candidate_id), None
        )
        if existing_domain is not None:
            domain_map[candidate.candidate_id] = existing_domain
            _add_requirement_links(
                package, candidate.requirement_ids, RequirementTargetType.DOMAIN, existing_domain.id
            )
            continue
        domain_type_id = catalog.resolve_domain_type(
            candidate.domain_type_id, candidate.name, candidate.description
        )
        domain = Domain(
            name=_unique_hierarchy_name(package, candidate.name),
            technical_name=catalog.allocate_domain_name(package, domain_type_id),
            domain_type_id=domain_type_id,
            technical_domain_ids=catalog.normalize_domain_type_ids(
                candidate.technical_domain_ids, domain_type_id,
            ),
            color=DOMAIN_COLORS[(initial_domain_count + index) % len(DOMAIN_COLORS)],
            description=candidate.description,
            properties={
                "generatedBy": "RequirementsArchitectureCompiler",
                "proposalId": proposal.id,
                "designState": proposal.properties.get("designState", "Working"),
                "sourceDocumentId": proposal.properties.get("sourceDocumentId", ""),
                "partitionRationale": candidate.partition_rationale,
            },
        )
        package.domains.append(domain)
        domain_map[candidate.candidate_id] = domain
        _add_requirement_links(package, candidate.requirement_ids, RequirementTargetType.DOMAIN, domain.id)
        created_domains += 1

    for candidate in selected_elements:
        domain = domain_map[candidate.domain_candidate_id]
        existing_element_match = package.find_element(candidate.candidate_id)
        if existing_element_match is not None:
            _, existing_element = existing_element_match
            element_map[candidate.candidate_id] = existing_element
            _add_requirement_links(
                package, candidate.requirement_ids, RequirementTargetType.ELEMENT, existing_element.id
            )
            for component_id in candidate.component_ids:
                if package.find_component(component_id) and not any(
                    item.component_id == component_id and item.element_id == existing_element.id
                    for item in package.component_allocations
                ):
                    package.component_allocations.append(ComponentAllocation(
                        component_id=component_id,
                        element_id=existing_element.id,
                    ))
                    created_allocations += 1
            for realization_id in candidate.technical_realization_ids:
                realization = package.find_technical_realization(realization_id)
                if realization is not None:
                    realization.architecture_element_id = existing_element.id
                    synchronize_realization_architecture_attribute(package, realization)
            continue
        role_type_id = catalog.resolve_role_type(
            candidate.role_type_id, candidate.name, candidate.description
        )
        element = ArchitectureElement(
            name=_unique_hierarchy_name(package, candidate.name),
            technical_name=catalog.allocate_element_name(package, role_type_id),
            role_type_id=role_type_id,
            technical_domain_ids=catalog.normalize_domain_type_ids(
                candidate.technical_domain_ids, domain.domain_type_id,
            ),
            description=candidate.description,
            properties={
                "generatedBy": "RequirementsArchitectureCompiler",
                "proposalId": proposal.id,
                "designState": proposal.properties.get("designState", "Working"),
                "sourceDocumentId": proposal.properties.get("sourceDocumentId", ""),
                "partitionRationale": candidate.partition_rationale,
            },
        )
        domain.elements.append(element)
        element_map[candidate.candidate_id] = element
        _add_requirement_links(package, candidate.requirement_ids, RequirementTargetType.ELEMENT, element.id)
        for component_id in candidate.component_ids:
            if package.find_component(component_id) and not any(
                item.component_id == component_id and item.element_id == element.id
                for item in package.component_allocations
            ):
                package.component_allocations.append(ComponentAllocation(
                    component_id=component_id,
                    element_id=element.id,
                ))
                created_allocations += 1
        for realization_id in candidate.technical_realization_ids:
            realization = package.find_technical_realization(realization_id)
            if realization is None:
                continue
            realization.architecture_element_id = element.id
            synchronize_realization_architecture_attribute(package, realization)
            selected_variant = next(
                (item for item in realization.variants if item.id == realization.selected_variant_id),
                None,
            )
            if selected_variant:
                for component_role in selected_variant.component_roles:
                    if not any(
                        item.component_id == component_role.component_id and item.element_id == element.id
                        for item in package.component_allocations
                    ):
                        package.component_allocations.append(ComponentAllocation(
                            component_id=component_role.component_id,
                            element_id=element.id,
                            role=component_role.role.value,
                            quantity=component_role.quantity,
                            properties={"technicalRealizationId": realization.id},
                        ))
                        created_allocations += 1
        created_elements += 1

    for candidate in selected_interfaces:
        family = (candidate.catalog_family or "Interface").strip().title()
        if family not in set(builtins.families()):
            raise ValueError(
                f"Verbindungsvorschlag „{candidate.name}“ verwendet die unbekannte Katalogfamilie „{family}“."
            )
        host = element_map.get(candidate.host_element_candidate_id or "")
        participants = [
            element_map[item]
            for item in candidate.participant_element_candidate_ids
            if item in selected_element_ids and item in element_map
        ]
        evidence_properties = {
            "generatedBy": "RequirementsArchitectureCompiler",
            "proposalId": proposal.id,
            "semanticProposalName": candidate.name,
            "designState": proposal.properties.get("designState", "Working"),
            "sourceDocumentId": proposal.properties.get("sourceDocumentId", ""),
            "sourceLocator": candidate.source_locator,
            "connectionEvidence": candidate.connection_evidence,
            "directionConfidence": candidate.direction_confidence,
            "topologyConfidence": candidate.topology_confidence,
            "excludedInternalSignalCount": candidate.excluded_internal_signal_count,
            "architectureScope": "BetweenArchitectureElements",
        }

        if family in {"Control", "Status", "Analog", "Power"}:
            resolved_template = builtins.resolve_signal_template(
                family, candidate.interface_template
            )
            if resolved_template is None:
                raise ValueError(
                    f"Einzel-Signal „{candidate.name}“ benötigt ein gültiges {family}-Template "
                    "aus Interface_Template_File.json."
                )
            technical_domain = next((
                item for item in builtins.domains()
                if item.casefold() == candidate.technical_domain.strip().casefold()
            ), "Other")
            instances = builtins.architecture_signal_instances(
                family=family,
                template_name=resolved_template,
                technical_domain=technical_domain,
                additional_info=candidate.additional_info,
                voltage_frequency=candidate.voltage_frequency,
                active_low=candidate.active_low,
                differential=candidate.differential,
            )
            type_map = {
                "Control": SignalType.CONTROL,
                "Status": SignalType.STATUS,
                "Analog": SignalType.DIFFERENTIAL if candidate.differential else SignalType.ANALOG,
                "Power": SignalType.POWER,
            }
            existing_by_name = {item.name.casefold(): item for item in package.signals}
            proposed_host_id = host.id if host else None
            proposed_participant_ids = {item.id for item in participants}
            incompatible_collisions: list[ArchitectureSignal] = []
            for instance in instances:
                for raw_name in instance.signals:
                    generated_name = concise_signal_name(raw_name)
                    existing = existing_by_name.get(generated_name.casefold())
                    if existing is None:
                        continue
                    existing_host_id = existing.source.element_id if existing.source else None
                    existing_participant_ids = {item.element_id for item in existing.sinks}
                    if (
                        existing_host_id != proposed_host_id
                        or existing_participant_ids != proposed_participant_ids
                    ):
                        incompatible_collisions.append(existing)
            if incompatible_collisions:
                candidate.selected_for_execution = False
                conflict_names = sorted({item.name for item in incompatible_collisions})
                conflict = {
                    "candidateId": candidate.candidate_id,
                    "candidateName": candidate.name,
                    "signalNames": conflict_names,
                    "reason": "Identischer technischer Signalname mit abweichender AE-Topologie",
                }
                proposal.properties.setdefault("signalNameConflicts", []).append(conflict)
                proposal.open_questions.append(
                    f"Signalkollision für „{candidate.name}“: {', '.join(conflict_names)} "
                    "existiert mit einer anderen Quelle oder anderen Teilnehmern."
                )
                continue
            for instance in instances:
                for raw_name in instance.signals:
                    generated_name = concise_signal_name(raw_name)
                    existing = existing_by_name.get(generated_name.casefold())
                    if existing is not None:
                        existing.observed_names = list(dict.fromkeys([
                            *existing.observed_names, *candidate.observed_signal_names,
                            *([raw_name] if raw_name != generated_name else []),
                        ]))
                        evidence = existing.properties.setdefault("additionalEvidence", [])
                        new_evidence = {
                            "proposalId": proposal.id,
                            "sourceDocumentId": proposal.properties.get("sourceDocumentId", ""),
                            "sourceLocator": candidate.source_locator,
                            "connectionEvidence": candidate.connection_evidence,
                            "semanticProposalName": candidate.name,
                        }
                        if new_evidence not in evidence:
                            evidence.append(new_evidence)
                        _add_requirement_links(
                            package, candidate.requirement_ids,
                            RequirementTargetType.SIGNAL, existing.id,
                        )
                        proposal.properties.setdefault("reusedArchitectureSignals", []).append({
                            "candidateId": candidate.candidate_id,
                            "signalId": existing.id,
                            "signalName": existing.name,
                        })
                        continue
                    member = Signal(
                        name=generated_name,
                        direction=Direction.INOUT,
                        pin_type="BI",
                        active_low=candidate.active_low or "#" in generated_name,
                        template_member_key=resolved_template,
                        description=candidate.rationale,
                        properties={
                            "family": family,
                            "template": resolved_template,
                            "sourceLocator": candidate.source_locator,
                        },
                    )
                    signal = ArchitectureSignal(
                        name=generated_name,
                        signal_type=type_map[family],
                        port_type=(
                            candidate.port_type.strip()
                            if candidate.port_type.strip()
                            and candidate.port_type.casefold() != "generic interface"
                            else resolved_template
                        ),
                        catalog_family=family,
                        catalog_template=resolved_template,
                        catalog_status="Bound",
                        observed_names=list(dict.fromkeys([*candidate.observed_signal_names, raw_name] if raw_name != generated_name else candidate.observed_signal_names)),
                        connection_type=ConnectionType.NET,
                        source=SignalEndpoint(element_id=host.id, pin_type="BI") if host else None,
                        sinks=[SignalEndpoint(element_id=item.id, pin_type="BI") for item in participants],
                        bus_contents=[member],
                        description=candidate.rationale or candidate.name,
                        properties={
                            **evidence_properties,
                            "template": resolved_template,
                            "family": family,
                            "technicalDomain": technical_domain,
                            "additionalInfo": candidate.additional_info,
                            "voltageFrequency": candidate.voltage_frequency,
                            "portNamingRule": "SignalName1to1",
                            "portSignalsMaterialized": False,
                        },
                    )
                    normalize_generated_signal(signal)
                    package.signals.append(signal)
                    synchronize_signal_topology(package, signal, builtins)
                    _add_requirement_links(
                        package, candidate.requirement_ids,
                        RequirementTargetType.SIGNAL, signal.id,
                    )
                    existing_by_name[generated_name.casefold()] = signal
                    created_signals += 1
            continue

        if family == "Memory":
            memory_template = next((
                subtechnology
                for technology in builtins.memory_technologies()
                for subtechnology in builtins.memory_subtechnologies(technology)
                if subtechnology.casefold() == candidate.interface_template.strip().casefold()
            ), None)
            memory_technology = next((
                technology for technology in builtins.memory_technologies()
                if memory_template in builtins.memory_subtechnologies(technology)
            ), None)
            if memory_template is None or memory_technology is None:
                raise ValueError(
                    f"Memory-Verbindung „{candidate.name}“ benötigt ein gültiges Memory-Template "
                    "aus Interface_Template_File.json."
                )
            technical_domain = next((
                item for item in builtins.domains()
                if item.casefold() == candidate.technical_domain.strip().casefold()
            ), "Other")
            instance = builtins.memory_instances(
                memory_technology,
                memory_template,
                technical_domain,
                candidate.additional_info or "Host",
                amount=1,
            )[0]
            if any(item.name.casefold() == instance.name.casefold() for item in package.signals):
                raise ValueError(
                    f"Der katalogisierte Memory-Bus „{instance.name}“ existiert bereits. "
                    "Passe Domäne oder Host-Kennung des Vorschlags an."
                )
            members = [
                Signal(
                    name=name,
                    direction=Direction.INOUT,
                    pin_type="BI",
                    template_member_key=name.rsplit("_", 1)[-1],
                    properties={"family": "Memory", "template": memory_template},
                )
                for name in instance.signals
            ]
            signal = ArchitectureSignal(
                name=instance.name,
                signal_type=SignalType.MEMORY,
                port_type=(
                    candidate.port_type.strip()
                    if candidate.port_type.strip()
                    and candidate.port_type.casefold() != "generic interface"
                    else memory_template
                ),
                catalog_family="Memory",
                catalog_template=memory_template,
                catalog_status="Bound",
                observed_names=list(dict.fromkeys(candidate.observed_signal_names)),
                connection_type=ConnectionType.BUS,
                source=SignalEndpoint(element_id=host.id, pin_type="BI") if host else None,
                sinks=[SignalEndpoint(element_id=item.id, pin_type="BI") for item in participants],
                bus_contents=members,
                description=candidate.rationale or candidate.name,
                properties={
                    **evidence_properties,
                    "template": memory_template,
                    "family": "Memory",
                    "memoryTechnology": memory_technology,
                    "technicalDomain": technical_domain,
                    "hostToken": candidate.additional_info or "Host",
                    "portSignalsMaterialized": False,
                },
            )
            normalize_generated_signal(signal)
            package.signals.append(signal)
            synchronize_signal_topology(package, signal, builtins)
            _add_requirement_links(
                package, candidate.requirement_ids,
                RequirementTargetType.SIGNAL, signal.id,
            )
            created_signals += 1
            continue

        template_candidates = [
            candidate.interface_template,
            candidate.port_type,
            candidate.name,
        ]
        project_template = next((
            template for value in template_candidates
            if (template := _project_template(package, value)) is not None
        ), None)
        builtin_template = next((
            resolved for value in template_candidates
            if (resolved := builtins.resolve_interface_template(value)) is not None
        ), None)
        if project_template:
            definition_pattern = project_template.name
            selected_template_value = project_template.id
        elif builtin_template:
            definition_pattern = builtin_template
            selected_template_value = builtin_template
        else:
            raise ValueError(
                f"Bus/Interface „{candidate.name}“ benötigt ein gültiges Template aus "
                "Interface_Template_File.json oder dem Projektkatalog."
            )
        instance_index = next_interface_index(
            package, builtins, definition_pattern, "Link",
        )
        signal_name = builtins.canonical_instance_name(
            definition_pattern, "Link", instance_index,
        )
        members, definition_id, definition_version, unresolved = _members_for_interface(
            package, builtins, selected_template_value, signal_name
        )
        port_type, signal_type, connection_type = _interface_metadata(
            package,
            builtins,
            selected_template_value,
            candidate.port_type,
            candidate.signal_type,
            candidate.connection_type,
        )
        signal = ArchitectureSignal(
            name=signal_name,
            signal_type=signal_type,
            port_type=port_type,
            interface_definition_id=definition_id,
            interface_definition_version=definition_version,
            interface_kind="Link",
            instance_index=instance_index,
            catalog_family=family,
            catalog_template=(project_template.name if project_template else builtin_template or ""),
            catalog_status="Bound",
            observed_names=list(dict.fromkeys(candidate.observed_signal_names)),
            connection_type=connection_type,
            source=SignalEndpoint(element_id=host.id, pin_type="BI") if host else None,
            sinks=[SignalEndpoint(element_id=item.id, pin_type="BI") for item in participants],
            bus_contents=members,
            description=candidate.rationale or candidate.name,
            properties={
                **evidence_properties,
                "interfaceTemplateUnresolved": unresolved,
                "namingPattern": definition_pattern,
                "portSignalsMaterialized": False,
            },
        )
        normalize_generated_signal(signal)
        package.signals.append(signal)
        synchronize_signal_topology(package, signal, builtins)
        _add_requirement_links(package, candidate.requirement_ids, RequirementTargetType.SIGNAL, signal.id)
        created_signals += 1

    from .models import SystemElement,MechanicalArchitectureElement,SoftwareArchitectureElement,FunctionElement
    discipline_counts={}
    architecture_candidates=dict(element_map)
    for field,collection,cls,target_type in (
        ('system_elements','system_elements',SystemElement,RequirementTargetType.SYSTEM_ELEMENT),
        ('mechanical_elements','mechanical_architecture_elements',MechanicalArchitectureElement,RequirementTargetType.MECHANICAL_ARCHITECTURE_ELEMENT),
        ('software_elements','software_architecture_elements',SoftwareArchitectureElement,RequirementTargetType.SOFTWARE_ARCHITECTURE_ELEMENT),
        ('function_elements','function_elements',FunctionElement,RequirementTargetType.FUNCTION_ELEMENT)):
        group=getattr(package,collection);mapping={o.id:o for o in group};created=[]
        for item in getattr(proposal,field):
            if not item.selected_for_execution:continue
            if any(i not in {r.id for r in package.requirements} for i in item.requirement_ids):raise ValueError('Facharchitektur verweist auf unbekannte Anforderung')
            obj=mapping.get(item.candidate_id)
            if obj is None:
                matches=[o for o in group if o.name.casefold()==item.name.casefold() and (cls is not FunctionElement or o.discipline==item.discipline)]
                if len(matches)>1:raise ValueError('Mehrdeutiger vorhandener Architekturbezug')
                obj=matches[0] if matches else None
            if obj is not None:mapping[item.candidate_id]=obj
            if obj is None:
                data={'name':item.name,'description':item.description,'requirement_ids':item.requirement_ids,'properties':{'proposalId':proposal.id,'generatedBy':'RequirementsArchitectureCompiler'}}
                if cls is FunctionElement:
                    data['discipline']=item.discipline
                    data['realization_ids']=item.realization_ids
                    ae=architecture_candidates.get(item.architecture_element_candidate_id)
                    data['architecture_element_id']=ae.id if ae else item.architecture_element_candidate_id or None
                if cls in {MechanicalArchitectureElement,SoftwareArchitectureElement}:data['realization_ids']=item.realization_ids
                obj=cls(**data);group.append(obj);created.append((item,obj));mapping[item.candidate_id]=obj
            _add_requirement_links(package,item.requirement_ids,target_type,obj.id)
            architecture_candidates[item.candidate_id]=obj
        for item,obj in created:
            if cls in {MechanicalArchitectureElement,SoftwareArchitectureElement} and item.parent_candidate_id:
                if item.parent_candidate_id not in mapping:raise ValueError('Übergeordnetes Facharchitekturelement wurde nicht ausgewählt')
                obj.parent_id=mapping[item.parent_candidate_id].id
            if cls is FunctionElement and obj.discipline=='hardware':
                for rid in item.realization_ids:
                    realization=package.find_technical_realization(rid)
                    if realization is None:raise ValueError('FE verweist auf unbekannte Realisierung')
                    realization.function_element_id=obj.id
        discipline_counts[field]=len(created)
    proposal.status = ProposalStatus.ACCEPTED
    proposal.properties["executionSelection"] = {
        "domains": [item.candidate_id for item in selected_domains],
        "elements": [item.candidate_id for item in selected_elements],
        "interfaces": [item.candidate_id for item in selected_interfaces],
        **{field:[item.candidate_id for item in getattr(proposal,field) if item.selected_for_execution] for field in discipline_counts if getattr(proposal,field)},
    }
    if package.project.workflow_mode == ProjectWorkflow.MANUAL:
        package.project.workflow_mode = ProjectWorkflow.REQUIREMENTS
    package.schema_version = "isd-suite/v3"
    return CompilationSummary(created_domains, created_elements, created_signals, created_allocations,
        *(discipline_counts.get(field,0) for field in ('system_elements','mechanical_elements','software_elements','function_elements')))


def compile_architecture_proposal(
    package: ArchitecturePackage,
    proposal: ArchitectureProposal,
    builtins: BusContentTemplates,
    architecture_catalog: ArchitectureCatalog | None = None,
) -> CompilationSummary:
    """Compile on a deep copy and publish only a completely valid package."""
    from .architecture_scope import validate_review_scope
    validate_review_scope(package,proposal)
    working = package.model_copy(deep=True)
    working_proposal = working.find_architecture_proposal(proposal.id)
    if working_proposal is None:
        raise ValueError("Der Architekturvorschlag gehört nicht zu diesem Projekt.")
    summary = _compile_architecture_proposal_in_place(
        working, working_proposal, builtins, architecture_catalog
    )
    validated = ArchitecturePackage.model_validate(working.export_dict())
    for field_name in ArchitecturePackage.model_fields:
        setattr(package, field_name, getattr(validated, field_name))
    package.__pydantic_extra__ = validated.__pydantic_extra__
    proposal.status = ProposalStatus.ACCEPTED
    return summary

