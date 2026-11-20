"""Single ordered preparation pass for saved and imported project packages.

Old data conversion stays at model/repository boundaries; this routine brings a
validated package to the current catalog and topology representation. Keep the
order explicit, and make each operation safe to repeat on an opened project.
"""
from __future__ import annotations

from .architecture_catalog import ArchitectureCatalog
from .bus_content import BusContentTemplates
from .models import ArchitecturePackage
from .signal_naming import normalize_architecture_names
from .requirements_service import ensure_requirement_identifiers, ensure_verification_identifiers, migrate_requirements_model
from .topology import migrate_interface_link_model, migrate_legacy_signal_catalog, migrate_signal_template_bindings, synchronize_all_topologies


def prepare_package(
    package: ArchitecturePackage,
    templates: BusContentTemplates,
    catalog: ArchitectureCatalog,
) -> None:
    """Run all current-format preparation in one deterministic location."""
    migrate_legacy_signal_catalog(package)
    normalize_architecture_names(package)
    migrate_interface_link_model(package, templates)
    migrate_signal_template_bindings(package, templates)
    synchronize_all_topologies(package, templates)
    catalog.migrate_package(package)
    ensure_requirement_identifiers(package)
    ensure_verification_identifiers(package)
    migrate_requirements_model(package)
    from .function_migration import migrate_function_elements
    from .property_schema import synchronize_schema
    migrate_function_elements(package)
    synchronize_schema(package)
