"""Provider-aware configuration, discovery, diagnostics and connection help."""
from typing import Callable
from nicegui import ui, run
from .ai_catalog import PROVIDERS, provider_spec, endpoint_for, model_options
from . import __version__

def open_ai_configuration(ai_provider, credential_store, refresh: Callable = lambda: None, on_changed: Callable | None = None):
    if on_changed is not None and not callable(on_changed):
        on_changed = None
    current = ai_provider.config
    current_provider = current.provider
    current_model = current.model
    current_base_url = current.base_url
    with ui.dialog() as dialog, ui.card().classes("w-[620px] max-w-[95vw] max-h-[92vh] overflow-auto p-6 gap-4"):
        with ui.row().classes("w-full items-center gap-3"):
            ui.icon("key", size="30px", color="primary")
            with ui.column().classes("gap-0 grow"):
                ui.label("KI-Zugang konfigurieren").classes("text-xl font-bold")
                ui.label(f"ISD Suite v{__version__}").classes("text-xs text-slate-500")
                ui.label("Wahlweise für den laufenden Prozess oder sicher im Betriebssystem speichern.").classes("text-sm text-slate-600")
        ui.label(
            "Der Browser speichert den API-Key nicht. Bei dauerhafter Ablage schreibt ausschließlich der lokale "
            "ISD-Server den Schlüssel in den Credential Manager des Betriebssystems. Im Projekt-JSON, in "
            "Revisionen und in SQLite wird kein API-Key abgelegt."
        ).classes("text-sm text-blue-900 bg-blue-50 border border-blue-200 rounded-lg p-3")
        credential_status = credential_store.status()
        storage_mode = ui.radio(
            {
                "session": "Nur laufender Anwendungsprozess",
                "credential": "Credential Manager des Betriebssystems",
            },
            value=(
                "credential"
                if ai_provider.configuration_source == "Credential Manager"
                else "session"
            ),
        ).props("inline").classes("w-full")
        if not credential_status.available:
            ui.label(
                "Credential Manager derzeit nicht verfügbar: "
                f"{credential_status.detail or 'kein sicherer Backend erkannt'}"
            ).classes("text-xs text-amber-800")
        provider = ui.select(
            {key: spec.label for key, spec in PROVIDERS.items()},
            value=current_provider if current_provider in PROVIDERS else "compatible",
            label="Provider",
        ).classes("w-full")
        with ui.row().classes("w-full items-end gap-2"):
            model = ui.select(model_options(provider.value, [current_model]), value=current_model or None, label="API-Modell", with_input=True).classes("grow")
            async def discover_models() -> None:
                if provider.value == "copilot":
                    ui.notify("Microsoft 365 Copilot wählt das Modell selbst; keine Modellauswahl per Chat API.", type="info")
                    return
                try:
                    requested_provider = provider.value
                    requested_endpoint = (base_url.value or "").strip() or None
                    entered = (api_key.value or "").strip()
                    if not entered and provider_spec(requested_provider).secret_required and (
                        requested_provider != current_provider or
                        endpoint_for(requested_provider, requested_endpoint) != endpoint_for(current_provider, current_base_url)
                    ):
                        raise ValueError("Beim Providerwechsel zuerst dessen API-Key eingeben.")
                    available = await run.io_bound(
                        ai_provider.available_models, entered, requested_endpoint, requested_provider,
                    )
                    if provider.value != requested_provider or ((base_url.value or "").strip() or None) != requested_endpoint:
                        return
                    options = model_options(requested_provider, available, [model.value])
                    selected = model.value if model.value in options else (options[0] if options else None)
                    model.set_options(options, value=selected)
                    ui.notify(f"{len(available)} Modelle über die API gefunden", type="positive")
                except Exception as error:
                    ui.notify("Modellliste nicht verfügbar. Zugang, Endpunkt, Kontingent oder lokale Installation prüfen. "
                              + (str(error) if type(error) is ValueError else type(error).__name__), type="warning")
            ui.button("API-Modelle laden", icon="refresh", on_click=discover_models).props("outline").tooltip("Modelle über API laden")
        manual_model = ui.input("Alternativer Modellname (optional)", placeholder="Exakte Modell-ID eingeben").classes("w-full")
        context_profile = ui.select({"economy": "Sparsam · relevanter Kontext", "full": "Vollständiger Kontext"},
                                    value=current.context_profile, label="KI-Kontextprofil").classes("w-full")
        api_key = ui.input(
            "API-Key bzw. delegiertes Microsoft-Graph-Zugriffstoken",
            password=True,
            password_toggle_button=True,
            placeholder=(
                "Leer lassen, um den bereits hinterlegten Schlüssel weiterzuverwenden"
                if credential_status.configured else "API-Key eingeben"
            ),
        ).classes("w-full")
        base_url = ui.input(
            "API Base URL",
            value=endpoint_for(provider.value, current_base_url) or "",
            placeholder="z. B. http://127.0.0.1:11434/v1",
        ).classes("w-full")
        @ui.refreshable
        def connection_help():
            spec = provider_spec(provider.value)
            ui.label(spec.help).classes("text-sm text-blue-900 bg-blue-50 rounded p-3")
            ui.link("Verbindungshilfe des Anbieters", spec.docs, new_tab=True)
            ui.link("ISD-Handbuch · KI-Anbindungen", "/isd-suite-tooldokumentation?chapter=48. KI-Anbindungen", new_tab=True)
            ui.label("Die Vorschläge bleiben im Dropdown sichtbar. API-Modelle laden ergänzt den Katalog; Zugriff mit Verbindung testen prüfen. "
                     "Verbindung testen führt eine kleine, gegebenenfalls kostenpflichtige Modellanfrage ohne Projektinhalt aus.").classes("text-xs text-slate-600")
        connection_help()

        def provider_changed():
            spec = provider_spec(provider.value)
            api_key.set_value("")
            base_url.set_value(spec.endpoint)
            manual_model.set_value("")
            model.set_options(model_options(provider.value), value=spec.models[0] if spec.models else None)
            base_url.set_enabled(provider.value not in {'openai','copilot','github_copilot'})
            model.set_enabled(provider.value != 'copilot')
            manual_model.set_enabled(provider.value != 'copilot')
            connection_help.refresh()
        provider.on_value_change(lambda _: provider_changed())
        base_url.set_enabled(provider.value not in {'openai','copilot','github_copilot'})
        model.set_enabled(provider.value != 'copilot')
        manual_model.set_enabled(provider.value != 'copilot')

        def draft_provider():
            from .ai_provider import OpenAIRequirementProvider
            candidate = OpenAIRequirementProvider()
            entered = (api_key.value or '').strip()
            same = provider.value == current_provider and endpoint_for(provider.value, base_url.value) == endpoint_for(current_provider, current_base_url)
            candidate.configure_session(provider.value,
                'Microsoft 365 Copilot' if provider.value == 'copilot' else (manual_model.value or model.value or ''),
                entered or (current.api_key if same else ''), (base_url.value or '').strip() or None,
                context_profile.value)
            return candidate

        async def test_connection():
            try:
                candidate = draft_provider()
                result = await run.io_bound(candidate.test_connection)
                ui.notify(result, type='positive')
            except Exception as error:
                ui.notify('Verbindungstest fehlgeschlagen: ' + (str(error) if type(error) is ValueError else type(error).__name__), type='warning')
        ui.button('Verbindung testen', icon='network_check', on_click=test_connection).props('outline no-caps')
        if ai_provider.is_ready:
            ui.label(
                f"Aktuell konfiguriert: {ai_provider.display_name} · {ai_provider.model_name} · "
                f"Quelle: {ai_provider.configuration_source}"
            ).classes("text-sm text-emerald-800")
        ui.separator()
        usage = ai_provider.usage
        ui.label("Verbrauch der laufenden ISD-Sitzung").classes("text-sm font-bold")
        with ui.row().classes("w-full gap-2"):
            for value, label in [
                (usage.request_count, "Requests"),
                (usage.input_tokens, "Input-Tokens"),
                (usage.output_tokens, "Output-Tokens"),
                (usage.total_tokens, "Gesamt-Tokens"),
            ]:
                with ui.card().classes("grow p-2 gap-0 border"):
                    ui.label(f"{value:,}".replace(",", ".")).classes("font-bold")
                    ui.label(label).classes("text-xs text-slate-500")
        ui.label("Die Zähler gelten für den aktuellen Provider in der ISD-Sitzung. Kontostand und Budget "
                 "beim Anbieter prüfen. GitHub / Microsoft Copilot liefern hier keine vollständigen Tokenzahlen.").classes("text-xs text-slate-600")

        def apply_configuration() -> None:
            provider_id = provider.value or "openai"
            selected_mode = storage_mode.value or "session"
            if provider_id == "copilot":
                if selected_mode == "credential":
                    ui.notify("Copilot-Zugriffstoken nur für die laufende Sitzung verwenden.", type="warning")
                    return
            try:
                candidate = draft_provider()
                config = candidate.config
                if selected_mode == "credential":
                    persistent = credential_store.save(
                        provider=config.provider, model=config.model, api_key=config.api_key,
                        base_url=config.base_url, context_profile=config.context_profile)
                    ai_provider.configure_persistent(persistent)
                else:
                    ai_provider.configure_session(config.provider, config.model, config.api_key,
                                                  config.base_url, config.context_profile)
            except (RuntimeError, ValueError) as error:
                ui.notify(str(error), type="warning")
                return
            dialog.close()
            if on_changed:
                on_changed()
            refresh()
            ui.notify(
                "KI-Zugang sicher im Credential Manager gespeichert"
                if selected_mode == "credential"
                else "KI-Konfiguration für den laufenden Anwendungsprozess übernommen",
                type="positive",
            )

        def reset_configuration() -> None:
            ai_provider.reset_session()
            dialog.close()
            if on_changed:
                on_changed()
            refresh()
            ui.notify("Sitzungskonfiguration verworfen", type="info")

        def delete_credentials() -> None:
            credential_store.delete()
            ai_provider.clear_persistent()
            dialog.close()
            if on_changed:
                on_changed()
            refresh()
            ui.notify("Gespeicherter KI-Zugang aus dem Credential Manager entfernt", type="info")

        with ui.row().classes("w-full justify-between"):
            with ui.row().classes("gap-1"):
                ui.button("Sitzung zurücksetzen", icon="restart_alt", on_click=reset_configuration).props("flat no-caps")
                if credential_status.configured:
                    ui.button(
                        "Gespeicherten Zugang löschen",
                        icon="key_off",
                        on_click=delete_credentials,
                    ).props("flat no-caps color=negative")
            with ui.row().classes("gap-2"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")
                ui.button("Zugang übernehmen", icon="key", on_click=apply_configuration).props("no-caps")
    dialog.open()

