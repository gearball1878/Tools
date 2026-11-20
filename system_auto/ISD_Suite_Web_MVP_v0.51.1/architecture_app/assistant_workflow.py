from __future__ import annotations

import re
from enum import Enum


class AssistantRequestKind(str, Enum):
    """Supported execution paths of the conversational project assistant."""

    ASK = "ask"
    CHANGE = "change"
    ARCHITECTURE = "architecture"
    INTEGRATE = "integrate"


_ACTION_WORDS = re.compile(
    r"\b(?:leg(?:e|t)?|anlegen|erstell(?:e|en|t)?|erzeug(?:e|en|t)?|generier(?:e|en|t)?|"
    r"ableit(?:e|en|et)?|bau(?:e|en|t)?|mach(?:e|en|t)?|plan(?:e|en|t)?|entwirf|"
    r"entwickl(?:e|en|t)?|prepare|create|build|generate|derive|design)\b",
    re.IGNORECASE,
)
_ARCHITECTURE_WORDS = re.compile(
    r"\b(?:architektur(?:vorschlag|arbeitsstand)?|architecture|arbeitsstand|as[- ]?is|to[- ]?be|"
    r"dom[aä]nen?|architecture\s+elements?|architekturelemente?|topologie)\b",
    re.IGNORECASE,
)
_DOCUMENT_INITIAL_WORDS = re.compile(
    r"\b(?:dokumente?|quellen?|lastenheft|schaltplan|bom|netzliste)\b.*\b(?:initial|anf[aä]nglich|"
    r"erste[rsn]?|vorl[aä]ufig)\b|\b(?:initial|anf[aä]nglich|erste[rsn]?|vorl[aä]ufig)\b.*"
    r"\b(?:dokumente?|quellen?|lastenheft|schaltplan|bom|netzliste)\b",
    re.IGNORECASE | re.DOTALL,
)
_CHANGE_WORDS = re.compile(
    r"\b(?:[aä]nder(?:e|n|t)?|aktualisier(?:e|en|t)?|korrigier(?:e|en|t)?|setz(?:e|en|t)?|"
    r"benenn(?:e|en|t)?|verkn[uü]pf(?:e|en|t)?|weis(?:e|en|t)?\s+zu|erg[aä]nz(?:e|en|t)?|"
    r"entfern(?:e|en|t)?|l[oö]sch(?:e|en|t)?|update|change|rename|link|assign|remove|delete)\b",
    re.IGNORECASE,
)

_INTEGRATION_WORDS = re.compile(
    r"\b(?:extrahier(?:e|en|t)?|analysier(?:e|en|t)?|pr[uü]f(?:e|en|t)?|leit(?:e|en|et)?\s+ab)\b"
    r"[\s\S]{0,200}\b(?:einpfleg(?:e|en|t)?|pfleg(?:e|en|t)?[\s\S]{0,30}\bein|[uü]bernehm(?:e|en|t)?|integrier(?:e|en|t)?|"
    r"anleg(?:e|en|t)?|erg[aä]nz(?:e|en|t)?)\b|"
    r"\b(?:einpfleg(?:e|en|t)?|pfleg(?:e|en|t)?[\s\S]{0,30}\bein|[uü]bernehm(?:e|en|t)?|integrier(?:e|en|t)?)\b"
    r"[\s\S]{0,160}\b(?:signale?|interfaces?|schnittstellen?|bauteile?|komponenten?|requirements?|anforderungen?)\b",
    re.IGNORECASE,
)


def _normalize_request_text(prompt: str) -> str:
    text = (prompt or "").strip().casefold()
    # Common typing errors must not downgrade an explicit work order to a
    # read-only consultation. Keep this deliberately small and deterministic.
    replacements = {
        "eipfleg": "einpfleg",
        "einpleg": "einpfleg",
        "übernhem": "übernehm",
        "integir": "integrier",
        "inerface": "interface",
    }
    for typo, corrected in replacements.items():
        text = text.replace(typo, corrected)
    return text


def is_engineering_integration_request(prompt: str) -> bool:
    return bool(_INTEGRATION_WORDS.search(_normalize_request_text(prompt)))


def resolve_assistant_document_ids(
    prompt: str,
    documents: list[dict[str, str]],
    explicit_ids: list[str] | None = None,
    current_document_id: str = "",
    whole_project: bool = False,
    integration_request: bool = False,
) -> list[str]:
    """Resolve useful document context without relying on a UI selection."""
    valid_ids = {item.get("id", "") for item in documents}
    resolved = [value for value in (explicit_ids or []) if value in valid_ids]
    if current_document_id in valid_ids and current_document_id not in resolved:
        resolved.append(current_document_id)
    folded = (prompt or "").casefold()
    for item in documents:
        document_id = item.get("id", "")
        names = (item.get("name", ""), item.get("file_name", ""))
        if document_id and any(value and value.casefold() in folded for value in names):
            if document_id not in resolved:
                resolved.append(document_id)
    if (whole_project or integration_request) and not resolved:
        preferred = [
            item.get("id", "") for item in documents
            if item.get("context_available") == "true"
            and item.get("profile", "") in {"legacy_schematic", "netlist", "bom", "requirements"}
        ]
        resolved.extend(value for value in preferred if value)
        if not resolved:
            resolved.extend(
                item.get("id", "") for item in documents
                if item.get("id") and item.get("context_available") == "true"
            )
    return list(dict.fromkeys(resolved))


def classify_assistant_request(prompt: str, requested_mode: str = "auto") -> AssistantRequestKind:
    """Resolve a prompt to an existing safe assistant execution path.

    The explicit modes are authoritative. Automatic mode only interprets clear
    engineering commands; ambiguous conversational input remains a question.
    """

    mode = (requested_mode or "auto").strip().casefold()
    text = _normalize_request_text(prompt)
    no_apply=bool(re.search(r'\b(?:noch\s+)?(?:nichts|nicht|keine)\s+(?:[\wäöüß-]+\s+){0,3}(?:ändern|aendern|übernehm\w*|anwenden|implementier\w*|einpfleg\w*|anleg\w*)\b|\b(?:nur\s+(?:analysier\w*|prüf\w*|pruef\w*|antwort\w*)|ohne\s+(?:änderung\w*|übernahme))\b',text))
    if no_apply and mode!=AssistantRequestKind.ASK.value:
        if re.search(r'\b(?:vorschlag|vorschläge|entwurf|änderungsvorschlag)\b',text):return AssistantRequestKind.CHANGE
        return AssistantRequestKind.ASK
    if mode == AssistantRequestKind.ASK.value:
        return AssistantRequestKind.ASK
    if mode == AssistantRequestKind.CHANGE.value:
        return AssistantRequestKind.CHANGE
    if mode == AssistantRequestKind.ARCHITECTURE.value:
        return AssistantRequestKind.ARCHITECTURE
    if mode == AssistantRequestKind.INTEGRATE.value:
        return AssistantRequestKind.INTEGRATE

    if re.match(r'^(?:wie|warum|weshalb|welche|was|wo|wann|wieso)\b',text):return AssistantRequestKind.ASK
    if is_engineering_integration_request(text):
        return AssistantRequestKind.INTEGRATE
    has_action = bool(_ACTION_WORDS.search(text))
    architecture_request = bool(_ARCHITECTURE_WORDS.search(text)) and has_action
    implicit_initial_architecture = has_action and bool(_DOCUMENT_INITIAL_WORDS.search(text))
    if architecture_request or implicit_initial_architecture:
        return AssistantRequestKind.ARCHITECTURE
    if _CHANGE_WORDS.search(text):
        return AssistantRequestKind.CHANGE
    if mode == "order":
        # An explicit work order must never silently degrade into a non-binding answer.
        return AssistantRequestKind.CHANGE
    return AssistantRequestKind.ASK
