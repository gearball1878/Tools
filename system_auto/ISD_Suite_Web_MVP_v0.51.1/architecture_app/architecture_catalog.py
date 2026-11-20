from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import ArchitecturePackage


class ArchitectureCatalog:
    """Controlled domain and AE-role vocabulary plus stable technical naming."""

    def __init__(self, catalog_path: str | Path):
        self.catalog_path = Path(catalog_path)
        self.data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        self._domain_types: dict[str, dict[str, Any]] = {}
        self._domain_families: dict[str, dict[str, Any]] = {}
        for family in self.data.get("domainFamilies", []):
            self._domain_families[family["id"]] = family
            for domain_type in family.get("types", []):
                enriched = dict(domain_type)
                enriched["familyId"] = family["id"]
                enriched["familyName"] = family["name"]
                enriched["typeAliases"] = list(domain_type.get("aliases", []))
                enriched["aliases"] = [
                    *family.get("aliases", []),
                    *domain_type.get("aliases", []),
                ]
                self._domain_types[domain_type["id"]] = enriched
        self._role_types = {
            item["id"]: item for item in self.data.get("aeRoleTypes", [])
        }

    @property
    def partition_rules(self) -> list[dict[str, str]]:
        return list(self.data.get("partitionRules", []))

    def domain_type_options(self) -> dict[str, str]:
        return {
            identifier: f"{item['familyName']} · {item['name']}"
            for identifier, item in self._domain_types.items()
        }

    def role_type_options(self) -> dict[str, str]:
        return {
            identifier: item["name"]
            for identifier, item in self._role_types.items()
        }

    def domain_type(self, identifier: str) -> dict[str, Any]:
        return self._domain_types.get(identifier) or self._domain_types["GEN.OTHER"]

    def role_type(self, identifier: str) -> dict[str, Any]:
        return self._role_types.get(identifier) or self._role_types["GEN.FUNCTION_BLOCK"]

    def normalize_domain_type_ids(
        self,
        values: list[str],
        primary: str,
    ) -> list[str]:
        """Keep only controlled Domain Type IDs, with the primary classification first."""
        normalized_primary = self.resolve_domain_type(primary)
        result = [normalized_primary]
        legacy = self.data.get("legacyTecDomainMap", {})
        for value in values:
            identifier = value if value in self._domain_types else legacy.get(value, "")
            if identifier in self._domain_types and identifier not in result:
                result.append(identifier)
        return result

    @staticmethod
    def _search_token(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()

    @classmethod
    def _score(cls, text: str, values: list[str]) -> int:
        haystack = f" {cls._search_token(text)} "
        score = 0
        for value in values:
            needle = cls._search_token(value)
            if not needle:
                continue
            if f" {needle} " in haystack:
                score = max(score, 100 + len(needle))
            elif needle in haystack:
                score = max(score, 10 + len(needle))
        return score

    def resolve_domain_type(self, *values: str) -> str:
        explicit = next((value for value in values if value in self._domain_types), None)
        if explicit:
            return explicit
        text = " ".join(str(value or "") for value in values)
        normalized_text = self._search_token(text)
        exact_catalog_match = next((
            identifier
            for identifier, item in self._domain_types.items()
            if normalized_text in {
                self._search_token(item["id"]),
                self._search_token(item["token"]),
                self._search_token(item["name"]),
                *(self._search_token(value) for value in item.get("typeAliases", [])),
            }
        ), None)
        if exact_catalog_match:
            return exact_catalog_match
        legacy = self.data.get("legacyTecDomainMap", {})
        for alias, identifier in legacy.items():
            if self._score(text, [alias]) >= 100 and identifier in self._domain_types:
                return identifier
        ranked = sorted(
            (
                self._score(text, [item["id"], item["token"], item["name"], *item.get("aliases", [])]),
                identifier,
            )
            for identifier, item in self._domain_types.items()
        )
        return ranked[-1][1] if ranked and ranked[-1][0] > 0 else "GEN.OTHER"

    def resolve_role_type(self, *values: str) -> str:
        explicit = next((value for value in values if value in self._role_types), None)
        if explicit:
            return explicit
        text = " ".join(str(value or "") for value in values)
        ranked = sorted(
            (
                self._score(text, [item["id"], item["token"], item["name"], *item.get("aliases", [])]),
                identifier,
            )
            for identifier, item in self._role_types.items()
        )
        return ranked[-1][1] if ranked and ranked[-1][0] > 0 else "GEN.FUNCTION_BLOCK"

    @staticmethod
    def _technical_token(value: str) -> str:
        token = re.sub(r"[^A-Z0-9]+", "_", str(value or "").upper()).strip("_")
        return re.sub(r"_+", "_", token) or "OTHER"

    @staticmethod
    def _used_numbers(package: ArchitecturePackage, prefix: str) -> set[int]:
        pattern = re.compile(rf"^{prefix}_(\d+)_")
        names = (
            [domain.technical_name for domain in package.domains]
            if prefix == "DOM"
            else [element.technical_name for domain in package.domains for element in domain.elements]
        )
        return {
            int(match.group(1))
            for name in names
            if name and (match := pattern.match(name))
        }

    def _next_number(self, package: ArchitecturePackage, kind: str) -> int:
        prefix = "DOM" if kind == "domain" else "AE"
        counters = package.project.properties.setdefault("architectureNamingCounters", {})
        if not isinstance(counters, dict):
            counters = {}
            package.project.properties["architectureNamingCounters"] = counters
        start = int(self.data.get("naming", {}).get("sequenceStart", 10))
        step = int(self.data.get("naming", {}).get("sequenceStep", 10))
        used = self._used_numbers(package, prefix)
        number = max(start, int(counters.get(prefix, 0) or 0) + step)
        while number in used:
            number += step
        counters[prefix] = number
        return number

    def allocate_domain_name(
        self,
        package: ArchitecturePackage,
        domain_type_id: str,
        qualifier: str = "",
    ) -> str:
        token = self.domain_type(domain_type_id)["token"]
        suffix = f"_{self._technical_token(qualifier)}" if qualifier.strip() else ""
        return f"DOM_{self._next_number(package, 'domain'):03d}_{token}{suffix}"

    def allocate_element_name(
        self,
        package: ArchitecturePackage,
        role_type_id: str,
        qualifier: str = "",
    ) -> str:
        token = self.role_type(role_type_id)["token"]
        suffix = f"_{self._technical_token(qualifier)}" if qualifier.strip() else ""
        return f"AE_{self._next_number(package, 'element'):03d}_{token}{suffix}"

    def migrate_package(self, package: ArchitecturePackage) -> bool:
        changed = False
        for domain in package.domains:
            resolved_type = self.resolve_domain_type(
                *(
                    [domain.name, domain.description]
                    if domain.domain_type_id == "GEN.OTHER"
                    else [domain.domain_type_id, domain.name, domain.description]
                ),
            )
            if domain.domain_type_id not in self._domain_types or (
                domain.domain_type_id == "GEN.OTHER" and resolved_type != "GEN.OTHER"
            ):
                domain.domain_type_id = resolved_type
                changed = True
            normalized_domain_ids = self.normalize_domain_type_ids(
                domain.technical_domain_ids, domain.domain_type_id
            )
            if domain.technical_domain_ids != normalized_domain_ids:
                domain.technical_domain_ids = normalized_domain_ids
                changed = True
            if not domain.technical_name:
                domain.technical_name = self.allocate_domain_name(package, domain.domain_type_id)
                changed = True
            for element in domain.elements:
                resolved_role = self.resolve_role_type(
                    *(
                        [element.name, element.description]
                        if element.role_type_id == "GEN.FUNCTION_BLOCK"
                        else [element.role_type_id, element.name, element.description]
                    ),
                )
                if element.role_type_id not in self._role_types or (
                    element.role_type_id == "GEN.FUNCTION_BLOCK"
                    and resolved_role != "GEN.FUNCTION_BLOCK"
                ):
                    element.role_type_id = resolved_role
                    changed = True
                normalized_element_ids = self.normalize_domain_type_ids(
                    element.technical_domain_ids, domain.domain_type_id
                )
                if element.technical_domain_ids != normalized_element_ids:
                    element.technical_domain_ids = normalized_element_ids
                    changed = True
                if not element.technical_name:
                    element.technical_name = self.allocate_element_name(package, element.role_type_id)
                    changed = True
        return changed

    def ai_context(self) -> dict[str, Any]:
        return {
            "domainTypes": [
                {
                    "id": identifier,
                    "token": item["token"],
                    "name": item["name"],
                    "familyId": item["familyId"],
                }
                for identifier, item in self._domain_types.items()
            ],
            "architectureElementRoleTypes": [
                {"id": identifier, "token": item["token"], "name": item["name"]}
                for identifier, item in self._role_types.items()
            ],
            "partitionRules": self.partition_rules,
            "naming": self.data.get("naming", {}),
        }
