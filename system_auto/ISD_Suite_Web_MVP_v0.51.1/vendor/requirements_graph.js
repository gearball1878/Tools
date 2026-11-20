/* Relationship lines follow actual rendered cards, including filtered chains.
   The JSON and DOM IDs are generated from persisted project links by Python. */
(() => {
  if (window.__isdRequirementsGraphInstalled) return;
  window.__isdRequirementsGraphInstalled = true;
  const ns = 'http://www.w3.org/2000/svg';
  const resizeObservers = new Map();
  let pending = false;
  const schedule = () => {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => { pending = false; drawAll(); });
  };
  const createSvg = (tag) => document.createElementNS(ns, tag);

  function roundedRoute(points, radius = 6) {
    points = points.filter((p, i) => !i || p[0] !== points[i - 1][0] || p[1] !== points[i - 1][1]);
    let d = `M ${points[0][0]} ${points[0][1]}`;
    for (let i = 1; i < points.length - 1; i++) {
      const a = points[i-1], b = points[i], c = points[i+1];
      const ab = Math.hypot(b[0]-a[0], b[1]-a[1]), bc = Math.hypot(c[0]-b[0], c[1]-b[1]);
      const r = Math.min(radius, ab/2, bc/2);
      const before = [b[0]+(a[0]-b[0])*r/ab, b[1]+(a[1]-b[1])*r/ab];
      const after = [b[0]+(c[0]-b[0])*r/bc, b[1]+(c[1]-b[1])*r/bc];
      d += ` L ${before[0]} ${before[1]} Q ${b[0]} ${b[1]} ${after[0]} ${after[1]}`;
    }
    const last = points[points.length-1];
    return `${d} L ${last[0]} ${last[1]}`;
  }

  function drawAll() {
    for (const [node, observer] of resizeObservers)
      if (!node.isConnected) { observer.disconnect(); resizeObservers.delete(node); }
    document.querySelectorAll('.isd-trace-board').forEach(board => {
      const svg = board.querySelector('.isd-trace-links');
      const data = board.querySelector('.isd-trace-data');
      const viewport = board.closest('.isd-trace-viewport');
      if (!svg || !data || !viewport) return;
      let edges;
      try { edges = JSON.parse(data.textContent); } catch (_) { return; }
      if (!Array.isArray(edges)) return;
      const nodes = new Map([...board.querySelectorAll('[data-trace-key]')]
        .filter(item => item.getClientRects().length)
        .map(item => [item.dataset.traceKey, item]));
      const boardRect = board.getBoundingClientRect();
      const width = board.offsetWidth;
      const height = board.offsetHeight;
      if (!board.__isdResizeObserved) {
        board.__isdResizeObserved = true;
        const observer = new ResizeObserver(schedule);
        observer.observe(board);
        resizeObservers.set(board, observer);
      }
      if (!width || !height) return;
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
      svg.replaceChildren();
      const definitions = createSvg('defs');
      for (const [name, color] of [['req', '#3b74b9'], ['solution', '#0c8273'], ['component', '#b37928']]) {
        const marker = createSvg('marker');
        marker.setAttribute('id', `isd-arrow-${name}`);
        marker.setAttribute('markerUnits', 'userSpaceOnUse');
        marker.setAttribute('markerWidth', '5');
        marker.setAttribute('markerHeight', '4');
        marker.setAttribute('refX', '5');
        marker.setAttribute('refY', '2');
        marker.setAttribute('orient', 'auto');
        const head = createSvg('path');
        head.setAttribute('d', 'M 0 0 L 5 2 L 0 4 Z');
        head.setAttribute('fill', color);
        marker.append(head);
        definitions.append(marker);
      }
      svg.append(definitions);
      const outgoing = new Map(), incoming = new Map();
      for (const edge of edges) {
        if (!outgoing.has(edge[0])) outgoing.set(edge[0], []);
        if (!incoming.has(edge[1])) incoming.set(edge[1], []);
        outgoing.get(edge[0]).push(edge); incoming.get(edge[1]).push(edge);
      }
      let routeIndex = 0;
      for (const edge of edges) {
        const [from, to, relationType = '', relationId = ''] = edge;
        const source = nodes.get(from);
        const target = nodes.get(to);
        if (!source || !target) continue;
        const s = source.getBoundingClientRect();
        const t = target.getBoundingClientRect();
        const x1 = s.right - boardRect.left;
        const out = outgoing.get(from), into = incoming.get(to);
        const oi = out.indexOf(edge), ii = into.indexOf(edge);
        const y1 = s.top + s.height / 2 - boardRect.top + (oi-(out.length-1)/2)*Math.min(5,(s.height-18)/out.length);
        const x2 = t.left - boardRect.left;
        const y2 = t.top + t.height / 2 - boardRect.top + (ii-(into.length-1)/2)*Math.min(5,(t.height-18)/into.length);
        const exit = x1 + 18, entry = x2 - 18;
        const midpoint = (exit + entry)/2 + ((oi + ii)%5 - 2)*3;
        const crossesCard = [...nodes.values()].some(node => {
          if (node === source || node === target) return false;
          const r = node.getBoundingClientRect();
          return r.left-boardRect.left > exit && r.right-boardRect.left < entry;
        });
        const rail = height - 7 - (routeIndex++ % 3)*3;
        const points = crossesCard || x2 <= x1
          ? [[x1,y1],[exit,y1],[exit,rail],[entry,rail],[entry,y2],[x2,y2]]
          : [[x1,y1],[midpoint,y1],[midpoint,y2],[x2,y2]];
        const path = createSvg('path');
        path.setAttribute('d', roundedRoute(points));
        const kind = from.startsWith('trace_') && source.closest('.isd-trace-solution-lane')
          ? 'component' : target.closest('.isd-trace-solution-lane') ? 'solution' : 'req';
        path.setAttribute('class', `isd-trace-path is-${kind}` +
          (source.classList.contains('isd-v-focused') || target.classList.contains('isd-v-focused')
            ? ' isd-trace-path-selected' : ''));
        path.setAttribute('marker-end', `url(#isd-arrow-${kind})`);
        if (relationType === 'technical_interface') path.setAttribute('stroke-dasharray', '9 4');
        if (relationType === 'dependency') path.setAttribute('stroke-dasharray', '2 5');
        const title = createSvg('title');
        title.textContent = relationType + (relationId ? ' · Beziehung ansehen' : '');
        path.append(title);
        if (relationId) {
          path.classList.add('isd-trace-editable-edge');
          path.addEventListener('click', event => { event.stopPropagation(); emitEvent('isd-edge-view', relationId); });
        }
        path.dataset.from = from;
        path.dataset.to = to;
        svg.append(path);
      }
      if (!board.__isdObserved) {
        board.__isdObserved = true;
        viewport.addEventListener('scroll', () => { window.__isdTraceScrollX = viewport.scrollLeft; }, {passive:true});
        board.addEventListener('mouseover', event => {
          const node = event.target.closest('[data-trace-key]');
          if (node && board.contains(node)) highlight(board, node.dataset.traceKey);
        });
        board.addEventListener('mouseout', event => {
          if (!event.relatedTarget || !board.contains(event.relatedTarget.closest('[data-trace-key]')))
            highlight(board, null);
        });
        board.addEventListener('focusin', event => {
          const node = event.target.closest('[data-trace-key]');
          if (node) highlight(board, node.dataset.traceKey);
        });
        board.addEventListener('focusout', event => {
          if (!event.relatedTarget || !board.contains(event.relatedTarget.closest('[data-trace-key]')))
            highlight(board, null);
        });
        board.addEventListener('click', event => {
          if (event.target.closest('.isd-trace-card-title')) {
            if (window.innerWidth <= 1100)
              document.querySelector('.inspector')?.classList.add('isd-mobile-details-open');
            else if (board.closest('.workspace')?.classList.contains('isd-requirements-focus'))
              document.querySelector('.inspector')?.classList.add('isd-requirements-inspector-open');
          }
        });
        viewport.scrollLeft = window.__isdTraceScrollX || 0;
      }
    });
  }

  function highlight(board, key) {
    const paths = [...board.querySelectorAll('.isd-trace-path')];
    const related = new Set([key]);
    for (const path of paths)
      if (key && (path.dataset.from === key || path.dataset.to === key)) {
        related.add(path.dataset.from);
        related.add(path.dataset.to);
      }
    for (const node of board.querySelectorAll('[data-trace-key]')) {
      node.classList.toggle('isd-trace-dim', Boolean(key) && !related.has(node.dataset.traceKey));
      node.classList.toggle('isd-trace-active', Boolean(key) && related.has(node.dataset.traceKey));
    }
    for (const path of paths) {
      const active = Boolean(key) && (path.dataset.from === key || path.dataset.to === key);
      path.classList.toggle('isd-trace-dim', Boolean(key) && !active);
      path.classList.toggle('isd-trace-active', active);
    }
  }

  const start = () => {
    new MutationObserver(mutations => {
      if (mutations.some(m => !m.target.closest?.('.isd-trace-links'))) schedule();
    }).observe(document.body, {subtree:true, childList:true});
    window.addEventListener('resize', schedule);
    if (document.fonts?.ready) document.fonts.ready.then(schedule);
    schedule();
  };
  if (document.body) start();
  else document.addEventListener('DOMContentLoaded', start, {once:true});
})();
