"""Stable SHA-256 display keys without changing existing project references."""
from __future__ import annotations

from hashlib import sha256
import re


_SHA256_HEX = re.compile(r"[0-9a-fA-F]{64}\Z")


def sha_identity(reference_id: str) -> str:
    """Present old and new IDs uniformly; hash the immutable ID, not mutable data."""
    if _SHA256_HEX.fullmatch(reference_id):
        return reference_id.lower()
    return sha256(b"ISD Suite object reference v1\0" + reference_id.encode("utf-8")).hexdigest()


def show_sha_identity(reference_id: str, *, project: bool = False,
                      show_reference: bool = True) -> None:
    from nicegui import ui
    label = "SHA-256-Projektkennung" if project else "SHA-256-Objektkennung"
    with ui.column().classes("w-full gap-1"):
        ui.label(f"{label} (nicht bearbeitbar)").classes("text-xs text-slate-600")
        ui.label(sha_identity(reference_id)).classes(
            "w-full rounded border bg-slate-50 px-2 py-2 font-mono text-xs break-all select-text"
        ).tooltip("Stabil aus der internen Referenz-ID berechnet; keine Prüfsumme des bearbeitbaren Inhalts.")
        if show_reference:
            with ui.expansion("Interne Referenz-ID", value=False).classes("w-full"):
                ui.input("Referenz-ID (nicht bearbeitbar)", value=reference_id).props(
                    "readonly outlined dense"
                ).classes("w-full font-mono")
