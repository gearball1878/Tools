"""Provider capabilities and contextual setup instructions (no secrets)."""
from dataclasses import dataclass

@dataclass(frozen=True)
class ProviderSpec:
    label: str
    endpoint: str
    models: tuple[str, ...]
    env_key: str
    help: str
    docs: str
    secret_required: bool = True

PROVIDERS = {
    'openai': ProviderSpec('OpenAI', '', ('gpt-6.1-sol','gpt-6-astra','gpt-6-luna'), 'OPENAI_API_KEY',
        'API-Key in der OpenAI Platform erzeugen, API-Abrechnung aktivieren. Ein ChatGPT-Abonnement ersetzt keinen API-Zugang.', 'https://platform.openai.com/docs'),
    'anthropic': ProviderSpec('Anthropic · Claude', 'https://api.anthropic.com/v1', ('claude-sonnet-5-5','claude-opus-5-5','claude-haiku-5-5'), 'ANTHROPIC_API_KEY',
        'Claude Console: API-Key erzeugen und API-Budget freigeben. Claude-Chat-Abonnement und API-Zugang unterscheiden sich. Native Messages API, einschließlich PDF-Inhalt.', 'https://platform.claude.com/docs/en/api/overview'),
    'gemini': ProviderSpec('Google · Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai', ('gemini-3.8-flash','gemini-3.5-flash-lite','gemini-3.1-pro-preview'), 'GEMINI_API_KEY',
        'API-Key in Google AI Studio erzeugen; Projekt, Kontingent und API-Abrechnung prüfen. Diese Anbindung nutzt die Gemini OpenAI-Kompatibilität, nicht Vertex AI.', 'https://ai.google.dev/gemini-api/docs/openai'),
    'xai': ProviderSpec('xAI · Grok', 'https://api.x.ai/v1', ('grok-4.7',), 'XAI_API_KEY',
        'API-Key in der xAI Console anlegen und API-Guthaben bzw. Budget prüfen. Grok in X ist kein API-Key.', 'https://docs.x.ai/overview'),
    'ollama': ProviderSpec('Ollama · lokal', 'http://127.0.0.1:11434/v1', (), 'OLLAMA_API_KEY',
        'Ollama installieren und starten. Modell mit ollama pull <Modell> laden; danach Modelle über API laden. localhost bezeichnet den ISD-Server, nicht den Browser-Rechner. Lokal ist kein Key erforderlich.', 'https://docs.ollama.com/api/openai-compatibility', False),
    'mistral': ProviderSpec('Mistral AI', 'https://api.mistral.ai/v1', ('mistral-small-2603','mistral-medium-3-5','mistral-large-4'), 'MISTRAL_API_KEY',
        'In Mistral La Plateforme einen API-Key und API-Abrechnung einrichten; verfügbare Modelle laden.', 'https://docs.mistral.ai/api/endpoint/models'),
    'deepseek': ProviderSpec('DeepSeek', 'https://api.deepseek.com', ('deepseek-flash','deepseek-v4-pro'), 'DEEPSEEK_API_KEY',
        'API-Key und Guthaben auf der DeepSeek API Platform einrichten; verfügbares Textmodell laden.', 'https://api-docs.deepseek.com/api/list-models/'),
    'groq': ProviderSpec('Groq', 'https://api.groq.com/openai/v1', ('openai/gpt-oss-120b','openai/gpt-oss-20b'), 'GROQ_API_KEY',
        'API-Key in der Groq Console erzeugen. Kontingent und Modellzugriff prüfen.', 'https://console.groq.com/docs/openai'),
    'openrouter': ProviderSpec('OpenRouter', 'https://openrouter.ai/api/v1', ('openai/gpt-6.1-sol','openai/gpt-6-astra'), 'OPENROUTER_API_KEY',
        'OpenRouter-Key und Budget anlegen. Modell-ID inklusive Anbieterpräfix wählen; JSON-Unterstützung hängt vom ausgewählten Modell ab.', 'https://openrouter.ai/docs/api_reference/overview'),
    'github_copilot': ProviderSpec('GitHub Copilot · SDK', '', ('auto',), 'GH_TOKEN',
        'Optionales Paket installieren: pip install github-copilot-sdk; anschließend python -m copilot download-runtime. GitHub-Copilot-Zugang und ein dafür zugelassenes Token verwenden. Die SDK-Anbindung hat keine HTTP Base URL. Werkzeuge und Dateizugriffe sind deaktiviert. GitHub Models ist ein separater, inzwischen eingestellter Dienst.', 'https://github.com/github/copilot-sdk/tree/main/python'),
    'copilot': ProviderSpec('Microsoft 365 Copilot · Graph Preview', '', ('Microsoft 365 Copilot',), 'MICROSOFT_GRAPH_TOKEN',
        'Microsoft-365-Copilot-Lizenz, Entra-App und delegiertes Microsoft-Graph-Zugriffstoken mit den aktuell dokumentierten Chat-API-Berechtigungen benötigen. Token nur in der Sitzung verwenden und bei Ablauf erneuern. Das Modell wird vom Dienst gewählt.', 'https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/ai-services/chat/overview'),
    'compatible': ProviderSpec('Eigener OpenAI-kompatibler Endpunkt', '', (), 'ISD_SUITE_AI_API_KEY',
        'Vollständige Base URL einschließlich API-Prefix eintragen. Endpunkt muss Chat Completions, JSON-Modus und nach Möglichkeit GET /models unterstützen. Exakte Modell-ID kann manuell eingetragen werden.', 'https://platform.openai.com/docs/api-reference/chat', False),
}

def provider_spec(identifier: str) -> ProviderSpec:
    return PROVIDERS['compatible' if identifier == 'local' else identifier]

def endpoint_for(identifier: str, override: str | None) -> str | None:
    return (override or provider_spec(identifier).endpoint).strip().rstrip('/') or None


def model_options(identifier: str, *extra: list[str] | tuple[str, ...]) -> list[str]:
    """Keep documented presets visible alongside account and saved model IDs."""
    values = [*provider_spec(identifier).models]
    for collection in extra:
        values.extend(value for value in collection if isinstance(value, str) and value.strip())
    return list(dict.fromkeys(values))
