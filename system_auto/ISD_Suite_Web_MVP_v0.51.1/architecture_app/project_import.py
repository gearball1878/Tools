"""Project profile selection for JSON imports; shared by the UI and repository."""
from __future__ import annotations

from .models import ArchitecturePackage, ProjectWorkflow

WORKFLOW_LABELS = {
    ProjectWorkflow.MANUAL.value: 'Direkt mit HW-/ECAD-Architektur beginnen',
    ProjectWorkflow.REQUIREMENTS.value: 'Integrierte Systementwicklung mit Requirements',
    ProjectWorkflow.REDESIGN.value: 'Redesign eines bestehenden Systems',
    ProjectWorkflow.STUDY.value: 'Architekturstudie / Prototyp',
}


def select_import_workflow(package: ArchitecturePackage, workflow: ProjectWorkflow) -> None:
    """Apply an explicit user choice without rewriting requirements or source evidence."""
    if not isinstance(workflow, ProjectWorkflow):
        raise ValueError('Vor dem Import einen Projekttyp auswählen.')
    package.project.workflow_mode = workflow
    if workflow != ProjectWorkflow.MANUAL:
        package.schema_version = 'isd-suite/v3'
