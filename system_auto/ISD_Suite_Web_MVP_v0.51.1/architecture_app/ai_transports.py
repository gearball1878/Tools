"""Native Claude and GitHub Copilot transports, with validated structured results."""
import asyncio
import json
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from types import SimpleNamespace


def request_json(url, key, payload=None):
    headers = {'x-api-key': key, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json'}
    request = urllib.request.Request(url, None if payload is None else json.dumps(payload).encode(), headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # Do not display server bodies: they can echo submitted secrets/documents.
        raise RuntimeError(f'Claude API: HTTP {error.code}. Zugang, Modell, Kontingent und Anfrageformat prüfen.') from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError('Claude API nicht erreichbar. Endpunkt und Netzwerk prüfen.') from None


def anthropic_models(config):
    found = set(); cursor = ''
    for _ in range(100):
        query = '?limit=100' + ('&after_id=' + urllib.parse.quote(cursor, safe='') if cursor else '')
        page = request_json(config.base_url + '/models' + query, config.api_key)
        found.update(item['id'] for item in page.get('data', []) if item.get('id'))
        if not page.get('has_more'): return sorted(found)
        next_cursor = page.get('last_id')
        if not next_cursor or next_cursor == cursor: raise RuntimeError('Ungültige Modell-Paginierung.')
        cursor = next_cursor
    raise RuntimeError('Modellliste überschreitet das Seitenlimit.')


def anthropic_content(content):
    if not isinstance(content, list): return str(content)
    result = []
    for item in content:
        if item.get('type') in {'text', 'input_text'}:
            result.append({'type':'text','text':item['text']})
        elif item.get('type') == 'input_file':
            data = item['file_data']; prefix = 'data:application/pdf;base64,'
            if not data.startswith(prefix): raise ValueError('Claude-Dateianalyse erwartet ein Base64-PDF.')
            result.append({'type':'document','source':{'type':'base64','media_type':'application/pdf','data':data[len(prefix):]}})
        else: raise ValueError('Dieser Inhaltstyp ist für Claude nicht freigegeben.')
    return result


def anthropic_structured(config, schema, system, content):
    response = request_json(config.base_url + '/messages', config.api_key, {
        'model':config.model, 'max_tokens':16384,
        'system':system + '\nReturn exactly one JSON object matching this schema:\n' + json.dumps(schema.model_json_schema()),
        'messages':[{'role':'user','content':anthropic_content(content)}],
    })
    usage = SimpleNamespace(**response.get('usage', {}))
    if response.get('stop_reason') not in {'end_turn', 'stop_sequence'}:
        raise RuntimeError('Claude-Ergebnis unvollständig oder abgelehnt; es wurde nichts übernommen.')
    text = ''.join(block.get('text','') for block in response.get('content',[]) if block.get('type') == 'text')
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip(), flags=re.I)
    return schema.model_validate_json(text), SimpleNamespace(usage=usage)


def chat_content(content):
    if not isinstance(content, list): return content
    converted = []
    for item in content:
        if item.get('type') in {'input_text','text'}: converted.append({'type':'text','text':item['text']})
        elif item.get('type') == 'image_url': converted.append(item)
        else:
            raise ValueError('Visuelle PDF-Analyse benötigt OpenAI oder Claude. Für diesen Provider Textanalyse verwenden.')
    return converted


def github_request(config, schema=None, system='', content=''):
    try:
        from copilot import CopilotClient
        from copilot.rpc import PermissionDecisionReject
    except ImportError:
        raise RuntimeError('GitHub Copilot benötigt das optionale Paket github-copilot-sdk und dessen Runtime. Siehe Verbindungshilfe.') from None
    if isinstance(content, list):
        raise ValueError('GitHub Copilot unterstützt hier Textanalyse. Für visuelle PDF-Analyse OpenAI oder Claude wählen.')
    async def execute():
        # Ephemeral SDK state prevents project context from becoming a cross-session store.
        with tempfile.TemporaryDirectory(prefix='isd-copilot-') as folder:
            async with CopilotClient(github_token=config.api_key, use_logged_in_user=False,
                                     mode='empty', base_directory=folder, working_directory=folder) as client:
                if schema is None:
                    models = await client.list_models()
                    return sorted({m.id if hasattr(m,'id') else m['id'] for m in models})
                async def deny(*args, **kwargs): return PermissionDecisionReject(feedback='ISD performs structured analysis without tools or file access.')
                async with await client.create_session(model=config.model, available_tools=[],
                    on_permission_request=deny, enable_session_store=False,
                    system_message={'mode':'replace','content':system}) as session:
                    response = await session.send_and_wait(str(content), response_schema=schema.model_json_schema(), timeout=120)
                    if response is None: raise RuntimeError('GitHub Copilot lieferte kein Ergebnis.')
                    return schema.model_validate_json(response.data.content)
    return asyncio.run(asyncio.wait_for(execute(), timeout=180))
