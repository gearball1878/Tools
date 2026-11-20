from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisProfile:
    id: str
    label: str
    focus: str
    visual_pdf: bool = False
    existing_design: bool = False


ANALYSIS_PROFILES: tuple[AnalysisProfile, ...] = (
    AnalysisProfile("requirements", "Anforderungsdokument", "System- und Realisierungsrequirements"),
    AnalysisProfile("legacy_schematic", "Legacy-Schaltplan / As-Is-Design", "Blatthierarchie, Bauteile, Netze und AE-übergreifende Konnektivität", True, True),
    AnalysisProfile("bom", "Stückliste / BOM", "Partnummern, Varianten und Bestückungsstatus", existing_design=True),
    AnalysisProfile("netlist", "Netzliste / ECAD-Export", "Deterministische Connectivity und AE-Grenzen", existing_design=True),
    AnalysisProfile("datasheet", "Datenblatt / Application Note", "Bauteilfunktion, Grenzwerte und Interfaces"),
    AnalysisProfile("standard", "Norm / Standard", "Normative Anforderungen, Klauseln und Nachweise"),
    AnalysisProfile("software", "Bestehende Software / Firmware", "Komponenten, Versionen und Protokollschicht", existing_design=True),
    AnalysisProfile("technical", "Sonstige technische Quelle", "Dokumentspezifische technische Evidenz"),
)


def profile_options() -> dict[str, str]:
    return {item.id: item.label for item in ANALYSIS_PROFILES}


def get_analysis_profile(profile_id: str) -> AnalysisProfile:
    normalized = profile_id.strip().casefold()
    aliases = {
        "bestandsschaltplan / pdf": "legacy_schematic", "legacy-schaltplan / as-is-design": "legacy_schematic",
        "stückliste / bom": "bom", "netzliste / konnektivität": "netlist", "netzliste / ecad-export": "netlist",
        "norm / standard": "standard", "datenblatt": "datasheet", "application note / referenzdesign": "datasheet",
        "bestehende software-/firmwarebeschreibung": "software", "bestehende software / firmware": "software",
        "sonstige technische quelle": "technical",
    }
    resolved = aliases.get(normalized, profile_id)
    return next((item for item in ANALYSIS_PROFILES if item.id == resolved), ANALYSIS_PROFILES[0])


def suggest_analysis_profile(file_name: str, media_type: str = "") -> str:
    name = file_name.casefold()
    if any(token in name for token in ("schematic", "schaltplan", "circuit", "schema")):
        return "legacy_schematic"
    if any(token in name for token in ("bom", "stückliste", "stueckliste")) or name.endswith((".csv", ".tsv")):
        return "bom"
    if any(token in name for token in ("netlist", "connectivity")) or name.endswith(".net"):
        return "netlist"
    if any(token in name for token in ("datasheet", "datenblatt", "application_note", "appnote")):
        return "datasheet"
    if any(token in name for token in ("standard", "norm", "iso_", "iec_")):
        return "standard"
    return "requirements"
