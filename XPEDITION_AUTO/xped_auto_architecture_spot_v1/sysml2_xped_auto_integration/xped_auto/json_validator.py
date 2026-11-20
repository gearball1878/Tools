from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError


DEFAULT_SCHEMA_PATH = Path(__file__).with_name("arch_export_format_json_schema.json")


class ArchitectureJSONValidationError(ValueError):
    """Raised before architecture data is handed to the Xpedition COM layer."""


class JSONValidator:
    """Validate the one supported SysML architecture SPOT contract.

    Handoff boundary: GUI/writer output enters here. Only successfully validated
    data may be converted to :class:`ArchitectureModel` and consumed by
    ``ArchJsonReader``/``auto_schem``.
    """

    def __init__(self, schema_path: str | Path = DEFAULT_SCHEMA_PATH) -> None:
        self.schema_path = Path(schema_path)
        try:
            self.schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(self.schema)
        except (OSError, json.JSONDecodeError, SchemaError) as exc:
            raise ArchitectureJSONValidationError(
                f"Architecture schema cannot be loaded from {self.schema_path}: {exc}"
            ) from exc
        # FormatChecker makes Back Annotation timestamps part of the actual
        # SPOT contract instead of treating "date-time" as documentation only.
        self._validator = Draft202012Validator(self.schema, format_checker=FormatChecker())

    def validate_data(self, data: Any, *, source: str = "in-memory architecture") -> None:
        if not isinstance(data, dict):
            raise ArchitectureJSONValidationError(
                f"Invalid architecture JSON ({source}): the SPOT root must be a JSON object."
            )
        errors = sorted(self._validator.iter_errors(data), key=lambda item: list(item.absolute_path))
        if not errors:
            return
        details = []
        for error in errors:
            location = "$"
            for part in error.absolute_path:
                location += f"[{part}]" if isinstance(part, int) else f".{part}"
            details.append(f"{location}: {error.message}")
        raise ArchitectureJSONValidationError(
            f"Invalid architecture JSON ({source}):\n" + "\n".join(f"- {item}" for item in details)
        )

    def load_and_validate(self, path: str | Path) -> dict[str, Any]:
        source = Path(path)
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ArchitectureJSONValidationError(f"Cannot read architecture JSON {source}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ArchitectureJSONValidationError(
                f"Architecture JSON {source} is not valid JSON: line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc
        self.validate_data(data, source=str(source))
        return data

    # Compatibility-shaped convenience for callers that only need a boolean.
    def is_valid(self, data: Any) -> bool:
        try:
            self.validate_data(data)
        except ArchitectureJSONValidationError:
            return False
        return True
