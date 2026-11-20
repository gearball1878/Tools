from __future__ import annotations

import asyncio
from hashlib import sha256
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .ai_provider import OpenAIRequirementProvider, local_requirement_scan
from .analysis_profiles import get_analysis_profile
from .architecture_catalog import ArchitectureCatalog
from .attachment_store import delete_attachment, read_attachment, store_attachment
from .bus_content import BusContentTemplates
from .document_ingestion import deserialize_document_context, extract_document, serialize_document_context
from .models import ArchitecturePackage, DocumentAnalysisStage, ProjectWorkflow, new_id, utc_now
from .repository import AIDocumentJob, ArchitectureRepository, VersionConflict
from .requirements_service import add_document_analysis, compile_detected_document_analysis


JOB_STATUS_LABELS = {
    "Preparing": "Wird eingelesen",
    "Ready": "Bereit zur Analyse",
    "Queued": "Wartet auf Analyse",
    "Running": "Wird analysiert",
    "ReviewReady": "In Requirements verfügbar",
    "Failed": "Fehlgeschlagen",
    "Cancelled": "Entfernt",
}


class DocumentAnalysisQueue:
    """Browser-independent, durable document-analysis worker."""

    def __init__(
        self,
        repository: ArchitectureRepository,
        provider: OpenAIRequirementProvider,
        builtins: BusContentTemplates | None = None,
        architecture_catalog: ArchitectureCatalog | None = None,
    ):
        self.repository = repository
        self.provider = provider
        self.builtins = builtins
        self.architecture_catalog = architecture_catalog
        self._worker_task: asyncio.Task[None] | None = None
        self._upload_tasks: set[asyncio.Task[AIDocumentJob]] = set()
        self._preparation_tasks: set[asyncio.Task[None]] = set()
        self._recovered = False

    @staticmethod
    def new_batch_id() -> str:
        return new_id("aibatch")

    def ensure_started(self) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        if not self._recovered:
            self.repository.requeue_interrupted_ai_document_jobs()
            self._recovered = True
            for job in self.repository.list_ai_document_jobs_by_status(["Preparing"]):
                self._schedule_preparation(job.id)
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(
                self._worker_loop(), name="ecad-document-analysis-worker"
            )

    async def submit_upload(
        self,
        project_id: str,
        batch_id: str,
        file_name: str,
        content: bytes,
        media_type: str,
        document_type: str,
    ) -> AIDocumentJob:
        task = asyncio.create_task(
            self._persist_upload(
                project_id,
                batch_id,
                file_name,
                content,
                media_type,
                document_type,
            ),
            name=f"persist-upload-{uuid4().hex}",
        )
        self._upload_tasks.add(task)
        task.add_done_callback(self._upload_tasks.discard)
        return await asyncio.shield(task)

    async def _persist_upload(
        self,
        project_id: str,
        batch_id: str,
        file_name: str,
        content: bytes,
        media_type: str,
        document_type: str,
    ) -> AIDocumentJob:
        job_id = new_id("aijob")
        stored = await asyncio.to_thread(
            store_attachment,
            project_id,
            job_id,
            file_name,
            content,
            media_type,
        )
        job = self.repository.create_ai_document_job(
            project_id=project_id,
            batch_id=batch_id,
            file_name=file_name,
            display_name=Path(file_name).stem,
            media_type=stored.media_type,
            document_type=document_type,
            attachment_path=stored.relative_path,
            checksum_sha256=stored.checksum_sha256,
            job_id=job_id,
        )
        self._schedule_preparation(job.id)
        self.ensure_started()
        return job

    def _schedule_preparation(self, job_id: str) -> None:
        if any(task.get_name() == f"prepare-{job_id}" and not task.done() for task in self._preparation_tasks):
            return
        task = asyncio.create_task(self._prepare_job(job_id), name=f"prepare-{job_id}")
        self._preparation_tasks.add(task)
        task.add_done_callback(self._preparation_tasks.discard)

    async def _prepare_job(self, job_id: str) -> None:
        try:
            job = self.repository.get_ai_document_job(job_id)
            content = await asyncio.to_thread(
                read_attachment, job.project_id, job.attachment_path
            )
            extracted = await asyncio.to_thread(
                extract_document, content, job.file_name, job.media_type
            )
            context_bytes = serialize_document_context(extracted)
            stored_context = await asyncio.to_thread(
                store_attachment,
                job.project_id,
                job.id,
                f"{job.file_name}.ecad-context.json",
                context_bytes,
                "application/json",
            )
            page_text = f"{extracted.page_count} Seiten · " if extracted.page_count else ""
            self.repository.update_ai_document_job(
                job.id,
                status="Ready",
                context_path=stored_context.relative_path,
                page_count=extracted.page_count,
                character_count=extracted.character_count,
                detail=(
                    f"{page_text}{extracted.character_count:,} Zeichen extrahiert. "
                    "Dokumentangaben können geprüft und ergänzt werden."
                ),
            )
        except Exception as error:
            try:
                self.repository.update_ai_document_job(
                    job_id,
                    status="Failed",
                    detail=f"Einlesen fehlgeschlagen: {error}",
                    completed_at=utc_now(),
                )
            except KeyError:
                pass

    def queue_batch(
        self,
        project_id: str,
        batch_id: str,
        job_ids: list[str],
        use_ai: bool,
        common_guidance: str,
    ) -> int:
        if use_ai and not self.provider.is_ready:
            raise ValueError("Für diese Analyse ist kein KI-Zugang konfiguriert.")
        queued = self.repository.queue_ai_document_jobs(
            project_id,
            batch_id,
            job_ids,
            use_ai,
            common_guidance.strip(),
        )
        self.ensure_started()
        return queued

    def retry_preparation(self, job_id: str) -> None:
        job = self.repository.get_ai_document_job(job_id)
        if job.status != "Failed" or job.context_path:
            return
        self.repository.update_ai_document_job(
            job_id,
            status="Preparing",
            detail="Dokument wird erneut serverseitig eingelesen.",
            completed_at=None,
        )
        self._schedule_preparation(job_id)

    def delete_job(self, project_id: str, job_id: str) -> None:
        job = self.repository.get_ai_document_job(job_id)
        self.repository.delete_ai_document_job(project_id, job_id)
        for path in (job.attachment_path, job.context_path):
            if path:
                try:
                    delete_attachment(project_id, path)
                except (FileNotFoundError, ValueError):
                    pass

    async def _worker_loop(self) -> None:
        while True:
            job = self.repository.claim_next_ai_document_job()
            if job is None:
                await asyncio.sleep(0.75)
                continue
            await self._process_job(job)

    def _guidance(self, job: AIDocumentJob, workflow: ProjectWorkflow) -> str:
        sections: list[str] = []
        sections.append(f"Project workflow: {workflow.value}")
        if workflow == ProjectWorkflow.REDESIGN:
            sections.append(
                "Redesign: Bestehende Bauteile, Software/Firmware, Netze und Schnittstellen "
                "als beobachteten As-Is-Stand erfassen und daraus eine vorläufige "
                "Arbeitsarchitektur ableiten. Unsicherheiten ausdrücklich markieren."
            )
        if job.common_guidance.strip():
            sections.append(f"Gemeinsamer Analyseauftrag:\n{job.common_guidance.strip()}")
        sections.append(f"Vom Benutzer angegebene Dokumentart: {job.document_type}")
        if job.document_context.strip():
            sections.append(f"Rolle und Kontext dieses Dokuments:\n{job.document_context.strip()}")
        if job.analysis_instructions.strip():
            sections.append(
                f"Dokumentspezifischer Analyseauftrag:\n{job.analysis_instructions.strip()}"
            )
        if self.builtins is not None:
            sections.append(
                "Verbindlicher Katalog für elektronische Interfaces und Einzelsignale. "
                "catalog_family und interface_template müssen exakt daraus übernommen werden; "
                "endgültige Link-, Port- und Signalnamen erzeugt der Compiler:\n"
                + json.dumps(
                    self.builtins.ai_catalog_context(),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        if self.architecture_catalog is not None:
            sections.append(
                "Kontrollierter Architektur-Katalog und verbindliche Aufteilungsregeln. "
                "domain_type_id und role_type_id müssen exakt aus diesem Katalog stammen. "
                "Jedes AE besitzt genau eine Parent-Domain, darf aber mehrere technische "
                "Klassifizierungen tragen. Display-Namen bleiben fachlich lesbar; stabile "
                "ECAD-Keys erzeugt erst der Compiler:\n"
                + json.dumps(
                    self.architecture_catalog.ai_context(),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        sections.append(
            "Instanznamen nicht frei erzeugen. Die ISD Suite bildet Interfaces automatisch als "
            "<Interface>_Link_<Nummer>. Architekturports tragen den Namen des angeschlossenen "
            "Netzes oder Busses; *_Port_* bleibt Funktionsblock-Schnittstellen im ECAD vorbehalten. Einzelsignale werden nach "
            "ihrer Control-, Status-, Analog- oder Power-Vorlage benannt; deren Architekturports "
            "übernehmen den Signalnamen exakt 1:1. Die fachliche Verwendung ausschließlich als "
            "Beschreibung oder rationale angeben."
        )
        return "\n\n".join(sections)

    async def _process_job(self, job: AIDocumentJob) -> None:
        try:
            context_bytes = await asyncio.to_thread(
                read_attachment, job.project_id, job.context_path
            )
            extracted = deserialize_document_context(context_bytes)
            workflow_package, _ = self.repository.load_project(job.project_id)
            guidance = self._guidance(job, workflow_package.project.workflow_mode)
            source_bytes = await asyncio.to_thread(
                read_attachment, job.project_id, job.attachment_path
            )
            profile = get_analysis_profile(job.document_type)
            if job.use_ai:
                if not self.provider.is_ready:
                    raise RuntimeError(
                        "Der KI-Zugang ist nicht verfügbar. Der Auftrag bleibt erneut startbar."
                    )
                analysis = await asyncio.to_thread(
                    self.provider.analyze_document,
                    extracted,
                    guidance,
                    source_bytes,
                    profile.id,
                )
                provider_name = self.provider.display_name
                model_name = self.provider.model_name
            else:
                analysis = await asyncio.to_thread(local_requirement_scan, extracted)
                provider_name, model_name = "Lokale Regelanalyse", "deterministisch"

            attachment_size = len(source_bytes)
            summary = None
            for attempt in range(5):
                package, version = self.repository.load_project(job.project_id)
                summary = add_document_analysis(
                    package,
                    extracted,
                    analysis,
                    provider_name,
                    model_name,
                    guidance,
                    DocumentAnalysisStage.REQUIREMENTS,
                )
                active_analysis = max(
                    (
                        item for item in package.document_analyses
                        if item.document_id == summary.document_id
                    ),
                    key=lambda item: item.revision_number,
                )
                compiled = compile_detected_document_analysis(
                    package, active_analysis.id, self.builtins
                )
                source = next(
                    item for item in package.source_documents if item.id == summary.document_id
                )
                source.name = job.display_name.strip() or Path(job.file_name).stem
                source.properties.update({
                    "documentType": profile.label,
                    "analysisProfile": profile.id,
                    "analysisProfileFocus": profile.focus,
                    "visualPdfAnalysis": bool(
                        profile.visual_pdf
                        and extracted.media_type == "application/pdf"
                        and job.use_ai
                        and self.provider.config.provider == "openai"
                    ),
                    "analysisPipeline": (
                        "visual-evidence+document-consolidation"
                        if profile.visual_pdf and extracted.media_type == "application/pdf" and job.use_ai
                        else "structured-text"
                    ),
                    "documentContext": job.document_context.strip(),
                    "documentAnalysisInstructions": job.analysis_instructions.strip(),
                    "analysisJobId": job.id,
                })
                source.attachment_path = job.attachment_path
                source.attachment_size = attachment_size
                source.context_path = job.context_path
                source.context_checksum_sha256 = sha256(context_bytes).hexdigest()
                source.context_section_count = len(extracted.sections)
                source.context_updated_at = utc_now()
                try:
                    self.repository.save_project(
                        ArchitecturePackage.model_validate(package.export_dict()), version
                    )
                    break
                except VersionConflict:
                    if attempt == 4:
                        raise
                    await asyncio.sleep(0.15)
            if summary is None:
                raise RuntimeError("Das Analyseergebnis konnte nicht erzeugt werden.")
            self.repository.update_ai_document_job(
                job.id,
                status="ReviewReady",
                provider=provider_name,
                model=model_name,
                result_document_id=summary.document_id,
                detail=(
                    f"{compiled.requirement_count} neue Requirements im Prüfstatus · "
                    f"{summary.interface_count} explizit genannte Interfaces · "
                    f"{summary.component_count} fest vorgegebene A-Parts · "
                    f"{summary.software_component_count} Software-/Firmwarekomponenten · "
                    f"{summary.standard_count} Normhinweise · "
                    f"{compiled.architecture_element_count} As-Is-Architekturelemente · "
                    f"{len(summary.open_questions)} offene Fragen"
                ),
                completed_at=utc_now(),
            )
        except Exception as error:
            try:
                self.repository.update_ai_document_job(
                    job.id,
                    status="Failed",
                    detail=str(error),
                    completed_at=utc_now(),
                )
            except KeyError:
                pass

    def batch_summary(self, project_id: str, batch_id: str) -> dict[str, Any]:
        jobs = self.repository.list_ai_document_jobs(project_id, batch_id)
        return {
            "jobs": jobs,
            "total": len(jobs),
            "processed": sum(job.status in {"ReviewReady", "Failed"} for job in jobs),
            "succeeded": sum(job.status == "ReviewReady" for job in jobs),
            "failed": sum(job.status == "Failed" for job in jobs),
            "running": any(job.status in {"Preparing", "Queued", "Running"} for job in jobs),
        }

    async def shutdown(self) -> None:
        tasks: list[asyncio.Task[Any]] = [
            task for task in self._upload_tasks if not task.done()
        ]
        tasks.extend(task for task in self._preparation_tasks if not task.done())
        if self._worker_task is not None and not self._worker_task.done():
            tasks.append(self._worker_task)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._worker_task = None
