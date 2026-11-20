"""Chapter navigation and full-text search over the canonical user manual."""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
import unicodedata

MANUAL_PATH = Path(__file__).resolve().parents[1] / 'docs' / 'HANDBUCH_ISD_SUITE.md'
HELP_CHAPTERS = {
    'ai': '48. KI-Anbindungen',
    'xpedition': '47. Xpedition',
    'ecad': '42. KiCad-Projektanlage',
    'hardware_realizations': '43. Realisierung',
    'overview': '1. Orientierung', 'documents': '3. Quellen',
    'requirements': '4. Requirements', 'hardware': '6. Architektur',
    'mechanics': '7. Mechanik', 'software': '8. Software',
    'standards': '9. Normen', 'data': '12. Revisionen', 'attributes':'39. Objektattribute', 'hsi':'36. Disziplinübergreifende', 'requirement-navigation':'40. Requirements', 'consolidation':'41. Konsolidierung',
}


@dataclass(frozen=True)
class Chapter:
    id: str
    title: str
    level: int
    own_text: str
    content: str
    children: tuple['Chapter', ...] = ()


def chapters(markdown: str) -> list[Chapter]:
    lines = markdown.splitlines(keepends=True)
    headings = []
    fence = None
    for index, line in enumerate(lines):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            if fence is None:
                fence = marker[1][0]
            elif fence == marker[1][0]:
                fence = None
            continue
        match = re.match(r'^(#{1,4})\s+(.+?)\s*#*\s*$', line)
        if match and fence is None:
            headings.append((index, len(match[1]), match[2]))
    result = []
    used = set()
    for pos, (start, level, title) in enumerate(headings):
        normalized = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode()
        base = re.sub(r'[^a-z0-9]+', '-', normalized.lower()).strip('-') or 'kapitel'
        slug = base
        suffix = 2
        while slug in used:
            slug = f'{base}-{suffix}'
            suffix += 1
        used.add(slug)
        own_end = headings[pos + 1][0] if pos + 1 < len(headings) else len(lines)
        end = next((s for s, lev, _ in headings[pos + 1:] if lev <= level), len(lines))
        result.append(Chapter(slug, title, level, ''.join(lines[start:own_end]), ''.join(lines[start:end])))
    stack = []
    child_ids = {chapter.id: [] for chapter in result}
    for chapter in result:
        while stack and stack[-1].level >= chapter.level:
            stack.pop()
        if stack:
            child_ids[stack[-1].id].append(chapter.id)
        stack.append(chapter)
    rebuilt = {}
    for chapter in reversed(result):
        rebuilt[chapter.id] = replace(chapter, children=tuple(rebuilt[i] for i in child_ids[chapter.id]))
    return [rebuilt[chapter.id] for chapter in result]


@lru_cache(maxsize=4)
def _cached_handbook(path: str, mtime_ns: int, ctime_ns: int, size: int, inode: int) -> tuple[Chapter, ...]:
    return tuple(chapters(Path(path).read_text(encoding='utf-8')))


def load_handbook(path: Path | None = None) -> tuple[Chapter, ...]:
    """Reuse immutable chapters; a replaced or edited file invalidates the cache."""
    path = (path or MANUAL_PATH).resolve()
    stat = path.stat()
    return _cached_handbook(str(path), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino)


def search(items: list[Chapter], query: str) -> list[tuple[Chapter, str]]:
    terms = query.strip().split()
    if not terms:
        return []
    matches = []
    for chapter in items:
        text = re.sub(r'\s+', ' ', chapter.own_text).strip()
        if not all(term.casefold() in text.casefold() for term in terms):
            continue
        first = re.search(re.escape(terms[0]), text, re.IGNORECASE)
        offset = first.start() if first else 0
        start = max(0, offset - 65)
        end = min(len(text), offset + 180)
        matches.append((chapter, ('…' if start else '') + text[start:end] + ('…' if end < len(text) else '')))
    return matches


def highlight(text: str, query: str) -> str:
    terms = sorted(set(query.strip().split()), key=len, reverse=True)
    if not terms:
        return escape(text)
    expression = re.compile('|'.join(re.escape(term) for term in terms), re.IGNORECASE)
    pieces = []
    start = 0
    for match in expression.finditer(text):
        pieces.extend((escape(text[start:match.start()]), '<mark>', escape(match[0]), '</mark>'))
        start = match.end()
    pieces.append(escape(text[start:]))
    return ''.join(pieces)


def highlighted_markdown(content: str, query: str) -> str:
    """Highlight rendered text, without touching URLs, tags or code syntax."""
    import markdown2
    rendered = markdown2.markdown(content, extras=['tables', 'fenced-code-blocks'])
    class Highlighter(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.output = []
        def handle_starttag(self, tag, attrs):
            self.output.append(self.get_starttag_text())
        def handle_endtag(self, tag):
            self.output.append(f'</{tag}>')
        def handle_startendtag(self, tag, attrs):
            self.output.append(self.get_starttag_text())
        def handle_data(self, data):
            self.output.append(highlight(data, query))
    parser = Highlighter()
    parser.feed(str(rendered))
    return ''.join(parser.output)


def render_handbook(initial_chapter: str = '', initial_query: str = '') -> None:
    from nicegui import ui
    try:
        items = load_handbook()
    except OSError as error:
        ui.label(f'Das Handbuch konnte nicht geladen werden: {error}').classes('text-red-700')
        return
    if not items:
        ui.label('Das Handbuch enthält noch keine Kapitel.')
        return
    prefix = HELP_CHAPTERS.get(initial_chapter, initial_chapter)
    first = next((c for c in items if c.level == 2), items[0])
    selected = next((c for c in items if c.id == initial_chapter or prefix and c.title.startswith(prefix)), first)
    state = {'chapter': selected.id, 'query': initial_query}
    by_id = {c.id: c for c in items}

    ui.add_css('''
        .isd-handbook { display:flex; width:100%; min-height:0; gap:20px; }
        .isd-handbook-nav { width:320px; min-width:260px; max-height:78vh; overflow:auto; background:white; border:1px solid #d5e0ec; border-radius:10px; padding:14px; }
        .isd-handbook-reader { flex:1; min-width:0; max-height:78vh; overflow:auto; padding:26px; background:white; border:1px solid #d5e0ec; border-radius:10px; line-height:1.65; }
        .isd-handbook-reader h1 { font-size:26px; color:#0d3768; }
        .isd-handbook-reader h2 { font-size:22px; color:#0b4f9c; margin-top:25px; }
        .isd-handbook-reader h3 { font-size:18px; margin-top:22px; }
        .isd-handbook-reader p,.isd-handbook-reader table,.isd-handbook-reader ul,.isd-handbook-reader ol { margin:12px 0; }
        .isd-handbook-reader ul { list-style:disc; padding-left:24px; }
        .isd-handbook-reader ol { list-style:decimal; padding-left:24px; }
        .isd-handbook-reader table { display:block; overflow:auto; border-collapse:collapse; }
        .isd-handbook-reader td,.isd-handbook-reader th { border:1px solid #d8e2ed; padding:8px; }
        .isd-handbook-reader th { background:#edf4fb; }
        .isd-handbook mark { background:#fef08a; color:inherit; }
        @media(max-width:800px) { .isd-handbook { flex-direction:column; } .isd-handbook-nav { width:100%; max-height:32vh; } .isd-handbook-reader { max-height:55vh; padding:18px; } }
    ''')
    def choose(identifier):
        if identifier not in by_id:
            return
        state['chapter'] = identifier
        reader.refresh()
    @ui.refreshable
    def reader():
        chapter = by_id[state['chapter']]
        position = items.index(chapter)
        with ui.row().classes('w-full items-center justify-between border-b pb-2'):
            ui.label(chapter.title).classes('text-sm font-semibold grow')
            ui.link('Kapitel-Link', f'{"/isd-suite-tooldokumentation"}?chapter={chapter.id}').props('target=_blank')
        ui.html(highlighted_markdown(chapter.content, state['query'])).classes('w-full')
        with ui.row().classes('w-full justify-between border-t pt-3'):
            if position:
                ui.button('Vorheriges Kapitel', icon='chevron_left', on_click=lambda: choose(items[position-1].id)).props('flat no-caps')
            if position+1 < len(items):
                ui.button('Nächstes Kapitel', icon='chevron_right', on_click=lambda: choose(items[position+1].id)).props('flat no-caps')
    @ui.refreshable
    def results():
        if state['query'].strip():
            matches = search(items, state['query'])
            ui.label(f'{len(matches)} Kapitel mit Treffern').classes('text-xs text-slate-600')
            for chapter, snippet in matches:
                ui.button(chapter.title, on_click=lambda _, c=chapter: choose(c.id)).props('flat no-caps align=left').classes('w-full')
                ui.html(highlight(snippet, state['query'])).classes('text-xs text-slate-600 mb-3')
        else:
            def node(chapter):
                return {'id': chapter.id, 'label': chapter.title, 'children': [node(c) for c in chapter.children]}
            roots = [c for c in items if not any(c in p.children for p in items)]
            tree = ui.tree([node(c) for c in roots], on_select=lambda e: choose(e.value)).classes('w-full').mark('handbook-chapters')
            tree.expand([c.id for c in roots])
            tree.selected = state['chapter']
    def query_changed(event):
        state['query'] = event.value or ''
        results.refresh()
        reader.refresh()
    with ui.row().classes('isd-handbook'):
        with ui.column().classes('isd-handbook-nav'):
            ui.input('Handbuch durchsuchen', value=initial_query, on_change=query_changed).props('clearable debounce=250').classes('w-full').mark('handbook-search')
            ui.label('Suche in allen Kapiteln').classes('text-xs text-slate-500')
            results()
        with ui.column().classes('isd-handbook-reader').mark('handbook-reader'):
            reader()
