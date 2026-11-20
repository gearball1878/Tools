"""Stable, project-wide reference allocation for future physical components."""
from __future__ import annotations

import re


def allocate_reference(registry: dict, object_id: str, prefix: str,
                       domain_id: str, element_id: str) -> str:
    """Allocate once per component; a move only changes its owner metadata."""
    prefix = prefix.strip().upper()
    if not re.fullmatch(r"[A-Z]+", prefix) or not object_id.strip():
        raise ValueError("Referenz benötigt Objektkennung und Buchstabenpräfix")
    assignments = registry.setdefault("assignments", {})
    counters = registry.setdefault("next", {})
    existing = assignments.get(object_id)
    if existing:
        if existing["prefix"] != prefix:
            raise ValueError("Präfixwechsel einer vergebenen Referenz muss geprüft werden")
        existing.update(domainId=domain_id, elementId=element_id)
        return existing["reference"]
    used = {entry["reference"] for entry in assignments.values()}
    next_number = max(1, int(counters.get(prefix, 1)))
    while f"{prefix}{next_number}" in used:
        next_number += 1
    reference = f"{prefix}{next_number}"
    assignments[object_id] = {"reference": reference, "prefix": prefix,
                              "domainId": domain_id, "elementId": element_id}
    counters[prefix] = next_number + 1
    return reference
