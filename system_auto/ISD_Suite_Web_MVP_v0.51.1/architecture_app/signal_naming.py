"""Conservative naming rules for architecture signals and imported topology.

Only adjacent, identical underscore-delimited terms are collapsed. The IDs and
topology references remain unchanged; old labels are kept as traceable metadata.
"""
from __future__ import annotations

from .models import ArchitecturePackage, ArchitectureSignal, Signal


def concise_signal_name(name: str) -> str:
    tokens = name.split('_')
    result: list[str] = []
    for token in tokens:
        if token and result and token.casefold() == result[-1].casefold():
            continue
        result.append(token)
    return '_'.join(result)


def normalize_generated_signal(signal: ArchitectureSignal) -> list[tuple[str, str]]:
    """Normalize a new signal and members, preserving original spellings as evidence."""
    member_names = [concise_signal_name(member.name).casefold() for member in signal.bus_contents]
    if len(member_names) != len(set(member_names)):
        raise ValueError(
            f"Die bereinigten Mitgliedssignalnamen in {signal.name!r} wären nicht eindeutig."
        )
    changes: list[tuple[str, str]] = []
    for target in (signal, *signal.bus_contents):
        original = target.name
        normalized = concise_signal_name(original)
        if normalized != original:
            target.name = normalized
            changes.append((original, normalized))
            if isinstance(target, ArchitectureSignal):
                target.observed_names = list(dict.fromkeys([*target.observed_names, original]))
            else:
                target.properties.setdefault('originalGeneratedName', original)
    return changes


def normalize_architecture_names(package: ArchitecturePackage) -> list[tuple[str, str]]:
    """Clean imported/saved names, including the ports and connections they label.

    Reserve already concise signal names first: two *different* electrical nets
    must never be merged just because both shorten to the same display name.
    This routine is idempotent and safe to run before topology synchronization.
    """
    changes: list[tuple[str, str]] = []

    def normalize_members(members: list[Signal]) -> None:
        reserved = {
            member.name.casefold() for member in members
            if concise_signal_name(member.name) == member.name
        }
        for member in members:
            original = member.name
            base = concise_signal_name(original)
            if base == original:
                continue
            candidate = base
            suffix = 2
            while candidate.casefold() in reserved:
                candidate = f"{base}_{suffix}"
                suffix += 1
            member.properties.setdefault("originalNameBeforeNormalization", original)
            member.name = candidate
            changes.append((original, candidate))
            reserved.add(candidate.casefold())

    concise_reserved = {
        signal.name.casefold() for signal in package.signals
        if concise_signal_name(signal.name) == signal.name
    }
    signal_changes: dict[str, tuple[str, str]] = {}
    for signal in package.signals:
        original = signal.name
        base = concise_signal_name(original)
        if base != original:
            candidate = base
            suffix = 2
            while candidate.casefold() in concise_reserved:
                candidate = f"{base}_{suffix}"
                suffix += 1
            signal.name = candidate
            signal.observed_names = list(dict.fromkeys([*signal.observed_names, original]))
            signal_changes[signal.id] = (original, candidate)
            changes.append((original, candidate))
            concise_reserved.add(candidate.casefold())

        normalize_members(signal.bus_contents)

    for domain in package.domains:
        for element in domain.elements:
            for port in element.ports:
                manual = port.properties.get("manualPortName")
                if isinstance(manual, str):
                    cleaned_manual = concise_signal_name(manual)
                    if cleaned_manual != manual:
                        port.properties.setdefault("originalManualPortNameBeforeNormalization", manual)
                        port.properties["manualPortName"] = cleaned_manual
                        changes.append((manual, cleaned_manual))
                linked = signal_changes.get(port.interface_link_id or "")
                original = port.name
                cleaned = linked[1] if linked and original.casefold() == linked[0].casefold() else concise_signal_name(original)
                if cleaned != original:
                    port.properties.setdefault("originalNameBeforeNormalization", original)
                    port.name = cleaned
                    changes.append((original, cleaned))
                normalize_members(port.signals)

    for connection in package.connections:
        linked = signal_changes.get(connection.signal_id or "")
        original = connection.name
        cleaned = linked[1] if linked and original.casefold() == linked[0].casefold() else concise_signal_name(original)
        if cleaned != original:
            connection.properties.setdefault("originalNameBeforeNormalization", original)
            connection.name = cleaned
            changes.append((original, cleaned))
    return changes
