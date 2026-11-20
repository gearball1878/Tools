from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Callable


DEFAULT_PROGID = "ViewDraw.Application"


@dataclass(frozen=True)
class XpeditionInstallation:
    """A usable Xpedition Designer COM registration."""

    progid: str
    clsid: str
    server_path: Path | None = None
    display_name: str = "Xpedition Designer"

    @property
    def label(self) -> str:
        if self.server_path:
            return f"{self.display_name} ({self.server_path.parent})"
        return self.display_name


def _server_executable(command: str | None) -> Path | None:
    """Extract the registered COM server path without executing it."""
    if not command:
        return None
    expanded = os.path.expandvars(command.strip())
    quoted = re.match(r'^"([^"]+)"', expanded)
    if quoted:
        return Path(quoted.group(1))
    match = re.match(r"^(.+?\.(?:exe|dll))(?=\s|$)", expanded, re.IGNORECASE)
    return Path(match.group(1).strip()) if match else None


def _installation_from_registry(
    progid: str,
    read_default: Callable[[str], str | None],
    path_exists: Callable[[Path], bool] = Path.exists,
) -> XpeditionInstallation | None:
    """Resolve one registry view; kept pure so detection can be unit-tested."""
    resolved_progid = read_default(f"{progid}\\CurVer") or progid
    clsid = read_default(f"{resolved_progid}\\CLSID") or read_default(f"{progid}\\CLSID")
    if not clsid:
        return None

    server_command = (
        read_default(f"CLSID\\{clsid}\\LocalServer32")
        or read_default(f"CLSID\\{clsid}\\InprocServer32")
    )
    if not server_command:
        return None
    server_path = _server_executable(server_command)
    if server_path is not None and not path_exists(server_path):
        # A stale COM registration is not a usable installation.
        return None

    display_name = (
        read_default(f"CLSID\\{clsid}")
        or read_default(resolved_progid)
        or "Xpedition Designer"
    )
    return XpeditionInstallation(resolved_progid, clsid, server_path, display_name)


def discover_xpedition_installations() -> list[XpeditionInstallation]:
    """Find usable Xpedition COM registrations without starting Xpedition."""
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []

    views = [0]
    for flag_name in ("KEY_WOW64_64KEY", "KEY_WOW64_32KEY"):
        flag = getattr(winreg, flag_name, 0)
        if flag and flag not in views:
            views.append(flag)

    found: list[XpeditionInstallation] = []
    seen: set[tuple[str, str]] = set()
    for view in views:
        def read_default(key: str, *, _view: int = view) -> str | None:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CLASSES_ROOT,
                    key,
                    0,
                    winreg.KEY_READ | _view,
                ) as handle:
                    value, _kind = winreg.QueryValueEx(handle, None)
                    return str(value).strip() or None
            except OSError:
                return None

        installation = _installation_from_registry(DEFAULT_PROGID, read_default)
        if installation:
            key = (installation.progid.lower(), installation.clsid.lower())
            if key not in seen:
                seen.add(key)
                found.append(installation)
    return found


def xpedition_unavailable_reason(installations: list[XpeditionInstallation]) -> str | None:
    if os.name != "nt":
        return "Forward Annotation requires Windows and Xpedition Designer."
    if not installations:
        return "No usable Xpedition Designer COM installation was found."
    try:
        import win32com.client  # noqa: F401
        import comtypes  # noqa: F401
    except ImportError:
        return "Xpedition was found, but the Python COM dependencies are missing."
    return None
