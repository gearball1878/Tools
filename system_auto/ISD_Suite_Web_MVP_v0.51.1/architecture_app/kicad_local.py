"""Explicit local handoff from the ISD Suite server to KiCad."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile

from .kicad_connector import KiCadConnector, _safe_filename
from .models import ArchitecturePackage


def workstation_mode() -> str:
    """A centrally hosted ISD must not mistake its server for the browser's PC."""
    mode = os.environ.get("ISD_ECAD_WORKSTATION_MODE", "local").lower()
    return "central" if mode == "central" else "local"


def _settings_file() -> Path:
    base = Path(os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME") or
                (Path.home() / ".config"))
    return base / "ISD_Suite" / "ecad_workstation.json"


def save_workstation_program(program: str | Path) -> Path:
    if not str(program).strip():
        raise ValueError("Bitte einen KiCad-Programmpfad wählen")
    path = find_kicad(program)
    assert path is not None
    target = _settings_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps({"kicad": str(path)}, indent=2), encoding="utf-8")
    temporary.replace(target)
    return path


def _saved_program() -> Path | None:
    try:
        value = json.loads(_settings_file().read_text(encoding="utf-8")).get("kicad", "")
        candidate = Path(value).expanduser() if value else None
        return candidate if candidate and candidate.is_file() else None
    except (OSError, ValueError, TypeError):
        return None


def choose_workstation_path(kind: str) -> str:
    """Native Explorer/Finder dialog on the machine running ISD locally."""
    if workstation_mode() != "local":
        raise RuntimeError("Zentrale ISD benötigt einen installierten Arbeitsplatz-Connector")
    if kind not in {"directory", "program", "project"}:
        raise ValueError("Unbekannte Dateiauswahl")
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            if kind == "directory":
                return str(filedialog.askdirectory(parent=root, title="KiCad-Zielordner auswählen"))
            if kind == "project":
                return str(filedialog.askopenfilename(parent=root, title="KiCad-Projekt auswählen",
                          filetypes=[("KiCad-Projekt", "*.kicad_pro")]))
            if kind == "program":
                return str(filedialog.askopenfilename(parent=root, title="KiCad-Programm auswählen",
                          filetypes=[("KiCad-Programm", "kicad.exe kicad"), ("Alle Dateien", "*")]))
        finally:
            root.destroy()
    except Exception as error:
        raise RuntimeError("Lokaler Dateidialog ist nicht verfügbar") from error


def project_directory(package: ArchitecturePackage, parent: str | Path) -> Path:
    parent_path = Path(parent).expanduser().resolve()
    if not str(parent).strip():
        raise ValueError("Bitte einen Projektordner angeben")
    return parent_path / (_safe_filename(package.project.name) + "_" +
                          _safe_filename(package.project.id)[-12:])


def create_local_project(package: ArchitecturePackage, parent: str | Path,
                         connector: KiCadConnector | None = None,
                         executable: str | Path | None = None) -> Path:
    """Create a fresh project folder without touching existing KiCad work."""
    target = project_directory(package, parent)
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"KiCad-Projekt existiert bereits: {target}. Es wird nicht überschrieben.")
    target.parent.mkdir(parents=True, exist_ok=True)
    connector = connector or KiCadConnector()
    files, manifest = connector.generate(package)
    files["isd_kicad_bindings.json"] = json.dumps(manifest, ensure_ascii=False, indent=2)
    files["PRUEFUNG.txt"] = (
        "ISD Suite / KiCad-Verbindungsschaltplan\n"
        f"KiCad-Projekt: {manifest['root']}\n"
        "Alle .kicad_sch-Dateien und isd_kicad_bindings.json im selben Ordner behalten.\n"
        f"Layoutwarnungen: {len(manifest['layoutWarnings'])}\n"
        "Die Anfangsversion enthält keine physikalischen Bauteile.\n"
    )
    staging = Path(tempfile.mkdtemp(prefix=".isd_kicad_", dir=target.parent))
    try:
        for name, content in files.items():
            # The generator must only supply flat project filenames.
            if Path(name).name != name or name in {".", ".."}:
                raise ValueError(f"Ungültiger Projektdateiname: {name}")
            (staging / name).write_text(content, encoding="utf-8")
        validate_with_kicad_cli(staging / Path(manifest["root"]), executable)
        try:
            target.mkdir()  # Exclusive even if another process just made an empty folder.
        except FileExistsError as error:
            raise FileExistsError(f"KiCad-Projekt existiert bereits: {target}. Es wird nicht überschrieben.") from error
        try:
            for file in staging.iterdir():
                file.replace(target / file.name)
        except OSError:
            shutil.rmtree(target)
            raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return target / Path(manifest["root"]).with_suffix(".kicad_pro")


def find_kicad(executable: str | Path | None = None) -> Path | None:
    if executable and str(executable).strip():
        candidate = Path(executable).expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"KiCad-Programm nicht gefunden: {candidate}")
        if candidate.name.lower() not in {"kicad", "kicad.exe"}:
            raise ValueError("Bitte das KiCad-Projektmanagerprogramm kicad.exe auswählen")
        return candidate
    candidates = []
    for name in ("kicad", "kicad.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    for env in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if base:
            candidates.extend((Path(base) / "KiCad").glob("*/bin/kicad.exe"))
    candidates.extend(Path("/Applications").glob("KiCad*/KiCad.app/Contents/MacOS/kicad"))
    saved = _saved_program()
    if saved:
        candidates.append(saved)
    candidates = list(dict.fromkeys(p.resolve() for p in candidates if p.is_file()))
    def version(path):
        # Numeric comparison: 10.0 > 9.0, 10.10 > 10.2.
        versions = re.findall(r"(?:^|[/\\])(?:KiCad[- ]*)?(\d+(?:\.\d+)*)(?:[/\\]|$)", str(path), re.I)
        if versions:
            return tuple(int(v) for v in versions[-1].split('.'))
        try:
            result = subprocess.run([str(path), '--version'], capture_output=True, text=True, timeout=3)
            match = re.search(r"\b(\d+\.\d+(?:\.\d+)*)", result.stdout + result.stderr)
            if match:
                return tuple(int(v) for v in match.group(1).split('.'))
        except (OSError, subprocess.TimeoutExpired):
            pass
        return (0,)
    return max(candidates, key=lambda path: (version(path), str(path)), default=None)


def validate_with_kicad_cli(schematic: str | Path,
                            executable: str | Path | None = None) -> bool:
    """Load the complete hierarchy with KiCad when its CLI is installed."""
    gui = find_kicad(executable) if executable else find_kicad()
    siblings = [gui.with_name(name) for name in ("kicad-cli.exe", "kicad-cli")] if gui else []
    cli = next((candidate for candidate in siblings if candidate.is_file()), None) or shutil.which("kicad-cli")
    if not cli:
        return False
    root = Path(schematic)
    output = root.with_suffix(".validation.net")
    try:
        try:
            result = subprocess.run([str(cli), "sch", "export", "netlist", "-o", str(output), str(root)],
                                    cwd=str(root.parent), capture_output=True, text=True, timeout=90)
        except subprocess.TimeoutExpired as error:
            raise ValueError("Zeitüberschreitung bei der KiCad-Projektprüfung") from error
        if result.returncode:
            detail = (result.stderr or result.stdout or "Unbekannter KiCad-Fehler").strip()
            raise ValueError(f"KiCad kann den erzeugten Schaltplan nicht laden: {detail[:1000]}")
        return True
    finally:
        output.unlink(missing_ok=True)


def open_in_kicad(project_file: str | Path, executable: str | Path | None = None) -> None:
    program = find_kicad(executable)
    if program is None:
        raise FileNotFoundError("KiCad wurde auf dem ISD-Suite-Rechner nicht gefunden")
    project = Path(project_file).resolve()
    if not project.is_file() or project.suffix != ".kicad_pro":
        raise FileNotFoundError(f"KiCad-Projektdatei nicht gefunden: {project}")
    subprocess.Popen([str(program), str(project)], cwd=str(project.parent))
