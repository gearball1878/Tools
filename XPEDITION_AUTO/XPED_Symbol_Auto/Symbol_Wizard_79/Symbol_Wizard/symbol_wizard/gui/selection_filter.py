"""Canvas selection filter helpers shared by Symbol Wizard and Template Editor.

The UI exposes plain text and generated/attribute text as separate filters, but
both are rendered by TextItem.  Keep the mapping in one place so per-item
selectability, rubber-band selection and Select All stay consistent.
"""

from __future__ import annotations

from typing import Any, Mapping

SELECTION_FILTER_KEYS = ('BODY', 'PIN', 'TEXT', 'ATTRIBUTES', 'GRAPHIC')
SELECTION_MODE_ITEMS = ('ALL', 'BODY', 'PIN', 'PLAIN TEXT', 'ATTRIBUTES', 'GRAPHIC', 'Custom')
TEXT_ATTRIBUTE_ITEM_KINDS = ('ATTR_REF_DES', 'ATTR_BODY')
SELECTABLE_ITEM_KINDS = ('BODY', 'PIN', 'TEXT', 'ATTR_REF_DES', 'ATTR_BODY', 'GRAPHIC', 'BODY_GRAPHIC')

_MODE_ALIASES = {
    'PLAIN TEXT': 'TEXT',
    'PLAINTEXT': 'TEXT',
    'TEXT PLAIN': 'TEXT',
    'ATTRIBUTE': 'ATTRIBUTES',
    'ATTR': 'ATTRIBUTES',
    'ATTRS': 'ATTRIBUTES',
}


def default_selection_enabled() -> dict[str, bool]:
    return {key: True for key in SELECTION_FILTER_KEYS}


def normalize_selection_mode(mode: Any) -> str:
    raw = str(mode or 'ALL').strip()
    upper = raw.upper().replace('_', ' ').replace('-', ' ')
    if upper == 'CUSTOM':
        return 'Custom'
    return _MODE_ALIASES.get(upper, upper)


def is_attribute_text_kind(item_kind: Any, model: Any | None = None) -> bool:
    return item_kind in TEXT_ATTRIBUTE_ITEM_KINDS or bool(getattr(model, '_is_attribute_text', False))


def selection_filter_kind(item_kind: Any, model: Any | None = None) -> str | None:
    """Return the public selection-filter key for a canvas item kind.

    ``TEXT`` is plain user text unless the model carries ``_is_attribute_text``.
    ``ATTR_*`` values and attribute-backed text models map to ``ATTRIBUTES``.
    """
    if item_kind == 'BODY_GRAPHIC':
        return 'BODY'
    if item_kind in TEXT_ATTRIBUTE_ITEM_KINDS:
        return 'ATTRIBUTES'
    if item_kind == 'TEXT':
        return 'ATTRIBUTES' if bool(getattr(model, '_is_attribute_text', False)) else 'TEXT'
    if item_kind in ('BODY', 'PIN', 'GRAPHIC'):
        return str(item_kind)
    return None


def selection_filter_kind_for_item(item: Any) -> str | None:
    try:
        kind = item.data(0)
    except Exception:
        kind = None
    return selection_filter_kind(kind, getattr(item, 'model', None))


def normalize_selection_enabled(enabled: Mapping[str, Any] | None) -> dict[str, bool]:
    """Return a complete filter map, migrating older TEXT-only states.

    Older saved/runtime states did not have an ATTRIBUTES key. In that case,
    attributes follow the old TEXT state until the user actively chooses the new
    Attributes filter.
    """
    source = dict(enabled or {})
    text_default = bool(source.get('TEXT', True))
    normalized = default_selection_enabled()
    for key in SELECTION_FILTER_KEYS:
        if key in source:
            normalized[key] = bool(source[key])
    if 'ATTRIBUTES' not in source:
        normalized['ATTRIBUTES'] = text_default
    return normalized


def selection_flags_for_mode(mode: Any) -> dict[str, bool]:
    mode = normalize_selection_mode(mode)
    if mode == 'ALL':
        return default_selection_enabled()
    return {key: key == mode for key in SELECTION_FILTER_KEYS}


def is_selection_kind_enabled(enabled: Mapping[str, Any] | None, filter_kind: str | None) -> bool:
    if filter_kind not in SELECTION_FILTER_KEYS:
        return False
    normalized = normalize_selection_enabled(dict(enabled or {}))
    return bool(normalized.get(filter_kind, True))


def is_selection_enabled_for_item(item: Any, enabled: Mapping[str, Any] | None) -> bool:
    return is_selection_kind_enabled(enabled, selection_filter_kind_for_item(item))
