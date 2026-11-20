from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .ai_provider import AIProviderConfig, OpenAIRequirementProvider
from .repository import ArchitectureRepository


_PROFILE_SETTING = "ai_provider_profile"
_SERVICE_NAME = "ISD Suite"
_LEGACY_SERVICE_NAMES = ("ECAD System Suite",)
_ACCOUNT_NAME = "AI API Key"


@dataclass(frozen=True)
class CredentialStatus:
    available: bool
    configured: bool
    detail: str = ""


class AICredentialStore:
    """Store only the secret in the operating system credential backend."""

    def __init__(self, repository: ArchitectureRepository, keyring_module: Any | None = None):
        self.repository = repository
        self._keyring_module = keyring_module

    def _keyring(self) -> Any:
        if self._keyring_module is not None:
            return self._keyring_module
        try:
            import keyring
        except ImportError as error:
            raise RuntimeError("Das Python-Paket keyring ist nicht installiert.") from error
        return keyring

    def status(self) -> CredentialStatus:
        try:
            keyring = self._keyring()
            backend = keyring.get_keyring()
            priority = float(getattr(backend, "priority", 0) or 0)
            if priority <= 0:
                return CredentialStatus(False, False, "Kein sicherer Credential-Backend verfügbar.")
            configured = any(
                keyring.get_password(service_name, _ACCOUNT_NAME)
                for service_name in (_SERVICE_NAME, *_LEGACY_SERVICE_NAMES)
            )
            return CredentialStatus(True, configured)
        except Exception as error:
            return CredentialStatus(False, False, str(error))

    def save(
        self,
        provider: str,
        model: str,
        api_key: str,
        base_url: str | None,
        context_profile: str = "economy",
    ) -> AIProviderConfig:
        secret = api_key.strip()
        if not secret:
            raise ValueError("Für die dauerhafte Ablage ist ein API-Key erforderlich.")
        config = AIProviderConfig(
            provider=provider.strip().casefold() or "openai",
            model=model.strip(),
            api_key=secret,
            base_url=(base_url or "").strip() or None,
            context_profile=context_profile,
        )
        keyring = self._keyring()
        keyring.set_password(_SERVICE_NAME, _ACCOUNT_NAME, secret)
        self.repository.set_app_setting(
            _PROFILE_SETTING,
            json.dumps({
                "provider": config.provider,
                "model": config.model,
                "baseUrl": config.base_url,
                "contextProfile": config.context_profile,
            }, ensure_ascii=False),
        )
        return config

    def load(self) -> AIProviderConfig | None:
        raw_profile = self.repository.get_app_setting(_PROFILE_SETTING)
        if not raw_profile:
            return None
        try:
            profile = json.loads(raw_profile)
            keyring = self._keyring()
            secret = keyring.get_password(_SERVICE_NAME, _ACCOUNT_NAME)
            if not secret:
                secret = next((
                    keyring.get_password(service_name, _ACCOUNT_NAME)
                    for service_name in _LEGACY_SERVICE_NAMES
                    if keyring.get_password(service_name, _ACCOUNT_NAME)
                ), None)
                if secret:
                    keyring.set_password(_SERVICE_NAME, _ACCOUNT_NAME, secret)
            if not secret:
                return None
            return AIProviderConfig(
                provider=str(profile.get("provider") or "openai"),
                model=str(profile.get("model") or "gpt-5.6"),
                api_key=str(secret),
                base_url=str(profile.get("baseUrl") or "").strip() or None,
                context_profile=str(profile.get("contextProfile") or "economy"),
            )
        except Exception:
            return None

    def delete(self) -> None:
        try:
            self._keyring().delete_password(_SERVICE_NAME, _ACCOUNT_NAME)
        except Exception:
            pass
        for service_name in _LEGACY_SERVICE_NAMES:
            try:
                self._keyring().delete_password(service_name, _ACCOUNT_NAME)
            except Exception:
                pass
        self.repository.delete_app_setting(_PROFILE_SETTING)

    def configure_provider(self, provider: OpenAIRequirementProvider) -> bool:
        config = self.load()
        if config is None:
            return False
        provider.configure_persistent(config)
        return True
