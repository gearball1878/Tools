(function () {
  'use strict';

  const SVG_NS = 'http://www.w3.org/2000/svg';

  function decodePayload(value) {
    const bytes = Uint8Array.from(atob(value), character => character.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function rgba(hex, alpha) {
    const normalized = /^#[0-9a-f]{6}$/i.test(hex || '') ? hex.slice(1) : '2563eb';
    const red = parseInt(normalized.slice(0, 2), 16);
    const green = parseInt(normalized.slice(2, 4), 16);
    const blue = parseInt(normalized.slice(4, 6), 16);
    return `rgba(${red},${green},${blue},${alpha})`;
  }

  function shorten(value, maximum) {
    const text = String(value ?? '');
    return text.length <= maximum ? text : `${text.slice(0, Math.max(1, maximum - 1))}…`;
  }

  function roundedPath(points, radius = 7) {
    if (!points.length) return '';
    if (points.length === 1) return `M${points[0].x},${points[0].y}`;
    let path = `M${points[0].x},${points[0].y}`;
    for (let index = 1; index < points.length - 1; index += 1) {
      const previous = points[index - 1];
      const current = points[index];
      const next = points[index + 1];
      const incoming = Math.hypot(current.x - previous.x, current.y - previous.y);
      const outgoing = Math.hypot(next.x - current.x, next.y - current.y);
      const offset = Math.min(radius, incoming / 2, outgoing / 2);
      const before = {
        x: current.x - ((current.x - previous.x) / incoming) * offset,
        y: current.y - ((current.y - previous.y) / incoming) * offset,
      };
      const after = {
        x: current.x + ((next.x - current.x) / outgoing) * offset,
        y: current.y + ((next.y - current.y) / outgoing) * offset,
      };
      path += ` L${before.x},${before.y} Q${current.x},${current.y} ${after.x},${after.y}`;
    }
    const last = points[points.length - 1];
    return `${path} L${last.x},${last.y}`;
  }

  function deduplicatePoints(points) {
    return points.filter((point, index) => index === 0 || point.x !== points[index - 1].x || point.y !== points[index - 1].y);
  }

  function enforceLeftTargetApproach(points, connection, collected, margin) {
    if (points.length < 2) return points;
    const end = points[points.length - 1];
    const targets = connection.sinkPortIds
      .map(portId => collected.portPositions.get(portId))
      .filter(Boolean)
      .map(port => ({x: port.centerX + margin, y: port.centerY + margin}));
    if (!targets.length) return points;
    const target = targets.reduce((best, candidate) => {
      const distance = Math.abs(candidate.x - end.x) + Math.abs(candidate.y - end.y);
      return !best || distance < best.distance ? {point: candidate, distance} : best;
    }, null);
    // ELK may end a section at the port border instead of its visual centre.
    if (!target || target.distance > 16) return points;

    const entryLength = 46;
    const approachX = target.point.x - entryLength;
    const body = points.slice(0, -1);
    const anchor = body[body.length - 1];
    const laneX = Math.min(anchor.x, approachX);
    return deduplicatePoints([
      ...body,
      {x: laneX, y: anchor.y},
      {x: laneX, y: target.point.y},
      {x: approachX, y: target.point.y},
      target.point,
    ]);
  }

  function selectAttributes(id, type, selectable = true) {
    if (!selectable) return `data-object-id="${escapeHtml(id)}"`;
    return `data-object-id="${escapeHtml(id)}" onclick="xpedCanvasSelect(event,'${escapeHtml(id)}','${type}')"`;
  }

  function toggleControl(id, type, x, y, collapsed) {
    const symbol = collapsed ? '+' : '−';
    const title = collapsed ? 'Im Canvas aufklappen' : 'Im Canvas einklappen';
    return `<g class="canvas-toggle" transform="translate(${x},${y})" onclick="xpedCanvasToggle(event,'${escapeHtml(id)}','${type}')">
      <title>${title}</title><rect width="22" height="22" rx="6" fill="#fff" stroke="#b9c8d7"/>
      <text x="11" y="16" text-anchor="middle" fill="#27445f" font-size="17" font-weight="750">${symbol}</text>
    </g>`;
  }

  function collectLayout(layout) {
    const nodes = [];
    const nodePositions = new Map([[layout.id, {x: 0, y: 0}]]);
    const portPositions = new Map();
    const edges = [];

    function visit(node, parentX, parentY, isRoot = false) {
      const x = isRoot ? 0 : parentX + (node.x || 0);
      const y = isRoot ? 0 : parentY + (node.y || 0);
      nodePositions.set(node.id, {x, y});
      if (!isRoot) nodes.push({...node, absoluteX: x, absoluteY: y});
      for (const port of node.ports || []) {
        portPositions.set(port.id, {
          ...port,
          x: x + (port.x || 0),
          y: y + (port.y || 0),
          centerX: x + (port.x || 0) + (port.width || 0) / 2,
          centerY: y + (port.y || 0) + (port.height || 0) / 2,
          nodeId: node.id,
        });
      }
      for (const edge of node.edges || []) edges.push(edge);
      for (const child of node.children || []) visit(child, x, y);
    }
    visit(layout, 0, 0, true);
    return {nodes, nodePositions, portPositions, edges};
  }

  function renderSvg(layout, meta) {
    const collected = collectLayout(layout);
    const margin = 52;
    const width = Math.max(720, Math.ceil(layout.width || 720) + margin * 2);
    const height = Math.max(440, Math.ceil(layout.height || 440) + margin * 2);
    const selected = meta.selectedId;
    const assignment = meta.assignment || {active: false};
    const selectedClass = id => id === selected || meta.connections[id]?.signalId === selected
      ? ' selected-object' : '';
    const edgeToConnection = new Map();
    for (const [connectionId, connection] of Object.entries(meta.connections)) {
      for (const edgeId of connection.edgeIds) edgeToConnection.set(edgeId, connectionId);
    }
    const connectionRoutes = new Map();

    for (const edge of collected.edges) {
      const connectionId = edgeToConnection.get(edge.id);
      if (!connectionId) continue;
      const containerOffset = collected.nodePositions.get(edge.container || layout.id) || {x: 0, y: 0};
      for (const section of edge.sections || []) {
        const points = [section.startPoint, ...(section.bendPoints || []), section.endPoint]
          .map(point => ({x: point.x + containerOffset.x + margin, y: point.y + containerOffset.y + margin}));
        if (!connectionRoutes.has(connectionId)) connectionRoutes.set(connectionId, []);
        connectionRoutes.get(connectionId).push({points, junctionPoints: section.junctionPoints || []});
      }
    }

    let svg = `<svg class="${assignment.active ? 'assignment-mode' : ''}" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="Automatisch angeordnete Architektur" onclick="xpedCanvasClear(event)">`;
    svg += `<defs>
      <filter id="elk-shadow"><feDropShadow dx="0" dy="4" stdDeviation="5" flood-opacity=".10"/></filter>
      <marker id="elk-arrow" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="context-stroke"/></marker>
    </defs>`;
    svg += `<g transform="translate(${margin},${margin})">`;

    for (const node of collected.nodes) {
      const domain = meta.domains[node.id];
      if (!domain) continue;
      const color = domain.color || '#2563EB';
      svg += `<g class="canvas-object domain-object${selectedClass(node.id)}" ${selectAttributes(node.id, 'domain')}>`;
      svg += `<title>${escapeHtml(domain.name)}</title>`;
      svg += `<rect class="domain-surface" x="${node.absoluteX}" y="${node.absoluteY}" width="${node.width}" height="${node.height}" rx="16" fill="${rgba(color, .055)}" stroke="${rgba(color, .42)}" stroke-width="1.5"/>`;
      svg += `<rect x="${node.absoluteX}" y="${node.absoluteY}" width="6" height="${node.height}" rx="3" fill="${color}"/>`;
      svg += `<text class="domain-name" x="${node.absoluteX + 22}" y="${node.absoluteY + 31}" fill="#15283f" font-size="17" font-weight="750">${escapeHtml(shorten(domain.name, 30))}</text>`;
      svg += toggleControl(node.id, 'domain', node.absoluteX + node.width - 88, node.absoluteY + 12, domain.collapsed);
      svg += `<text x="${node.absoluteX + node.width - 18}" y="${node.absoluteY + 29}" fill="${color}" font-size="11" font-weight="700" text-anchor="end">DOMAIN</text>`;
      if (domain.collapsed) {
        const summary = `${domain.elementCount || 0} AE · ${domain.incomingCount || 0} ein · ${domain.outgoingCount || 0} aus · ${domain.internalCount || 0} intern`;
        svg += `<text class="domain-summary" x="${node.absoluteX + 22}" y="${node.absoluteY + 58}">${escapeHtml(summary)}</text>`;
      }
      svg += `</g>`;
    }
    svg += `</g>`;

    for (const [connectionId, routes] of connectionRoutes.entries()) {
      const connection = meta.connections[connectionId];
      const isBus = connection.connectionType === 'Bus';
      const isAggregate = connection.connectionType === 'Aggregate';
      const lineWidth = isBus ? 4.2 : 2.4;
      const color = connection.color || (isBus ? '#48637f' : '#6b7f94');
      const connectionClass = `${connection.selectable === false ? '' : 'canvas-object '}${isAggregate ? 'aggregate-connection ' : ''}connection-object${selectedClass(connectionId)}`;
      svg += `<g class="${connectionClass}" data-signal-id="${escapeHtml(connection.signalId || '')}" ${selectAttributes(connectionId, 'connection', connection.selectable !== false)}>`;
      svg += `<title>${escapeHtml(connection.name)} · ${escapeHtml(connection.connectionType)} · ${connection.sinkCount ?? connection.sinkPortIds.length} Teilnehmer</title>`;
      const normalizedRoutes = routes.map(route => enforceLeftTargetApproach(route.points, connection, collected, margin));
      for (const normalizedPoints of normalizedRoutes) {
        const path = roundedPath(normalizedPoints);
        svg += `<path class="connection-hit" d="${path}" fill="none" stroke="transparent" stroke-width="18"/>`;
        if (isBus) {
          svg += `<path class="connection-line-back" d="${path}" fill="none" stroke="${color}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>`;
        }
        svg += `<path class="connection-line" d="${path}" fill="none" stroke="${color}" stroke-width="${lineWidth}" stroke-linecap="round" stroke-linejoin="round" marker-end="url(#elk-arrow)"/>`;
      }
      if (normalizedRoutes.length > 1) {
        const pointCounts = new Map();
        for (const points of normalizedRoutes) {
          for (const point of points.slice(1, -1)) {
            const key = `${Math.round(point.x)},${Math.round(point.y)}`;
            pointCounts.set(key, (pointCounts.get(key) || 0) + 1);
          }
        }
        for (const [key, count] of pointCounts.entries()) {
          if (count < 2) continue;
          const [x, y] = key.split(',').map(Number);
          svg += `<circle class="connection-junction" cx="${x}" cy="${y}" r="5" fill="${color}"/>`;
        }
        const source = collected.portPositions.get(connection.sourcePortId);
        if (source) svg += `<circle cx="${source.centerX + margin}" cy="${source.centerY + margin}" r="4.5" fill="${color}"/>`;
      }
      svg += `</g>`;
    }

    svg += `<g transform="translate(${margin},${margin})">`;
    for (const node of collected.nodes) {
      const element = meta.elements[node.id];
      if (!element) continue;
      const color = element.color || '#2563EB';
      const assignmentClass = node.id === assignment.hostElementId
        ? ' assignment-host'
        : (assignment.participantElementIds || []).includes(node.id) ? ' assignment-participant' : '';
      svg += `<g class="canvas-object element-object${selectedClass(node.id)}${assignmentClass}" ${selectAttributes(node.id, 'element')}>`;
      svg += `<title>${escapeHtml(element.name)}</title>`;
      svg += `<rect class="element-surface" x="${node.absoluteX}" y="${node.absoluteY}" width="${node.width}" height="${node.height}" rx="12" fill="#fff" stroke="#cbd7e4" filter="url(#elk-shadow)"/>`;
      svg += `<rect x="${node.absoluteX}" y="${node.absoluteY}" width="5" height="${node.height}" rx="2.5" fill="${color}"/>`;
      svg += `<text class="element-name" x="${node.absoluteX + 18}" y="${node.absoluteY + 27}" fill="#132238" font-size="15" font-weight="750">${escapeHtml(shorten(element.name, 27))}</text>`;
      svg += toggleControl(node.id, 'element', node.absoluteX + node.width - 34, node.absoluteY + 11, element.collapsed);
      svg += `<text class="element-kind" x="${node.absoluteX + 18}" y="${node.absoluteY + 47}" fill="#748399" font-size="11.5">${escapeHtml(element.kind)}</text>`;
      if (element.collapsed) {
        const summary = `${element.portCount || 0} Ports · ${element.inputCount || 0} ein · ${element.outputCount || 0} aus`;
        svg += `<text class="element-summary" x="${node.absoluteX + 18}" y="${node.absoluteY + 68}" fill="#60758c" font-size="11.5" font-weight="650">${escapeHtml(summary)}</text>`;
      }
      if (assignmentClass) {
        const assignmentText = assignmentClass.includes('host') ? 'HOST' : 'TEILNEHMER';
        const assignmentColor = assignmentClass.includes('host') ? '#7c3aed' : '#0f9f77';
        svg += `<text class="assignment-badge" x="${node.absoluteX + 18}" y="${node.absoluteY + node.height - 14}" fill="${assignmentColor}">${assignmentText}</text>`;
      }
      svg += `</g>`;
    }

    for (const [portId, position] of collected.portPositions.entries()) {
      const port = meta.ports[portId];
      if (!port) continue;
      const nodePosition = collected.nodePositions.get(position.nodeId);
      const node = collected.nodes.find(item => item.id === position.nodeId);
      if (!nodePosition || !node) continue;
      const right = port.side === 'Right';
      const visibleName = shorten(port.name, 17);
      const labelWidth = Math.max(76, Math.min(126, visibleName.length * 6.7 + 22));
      const labelX = right ? node.absoluteX + node.width - labelWidth - 12 : node.absoluteX + 12;
      const textX = right ? node.absoluteX + node.width - 20 : node.absoluteX + 20;
      const anchor = right ? 'end' : 'start';
      const centerY = position.centerY;
      const targetId = port.targetId || portId;
      const targetType = port.targetType || 'port';
      const portSelectable = port.selectable !== false;
      svg += `<g class="${portSelectable ? 'canvas-object ' : ''}port-object${selectedClass(targetId)}" ${selectAttributes(targetId, targetType, portSelectable)}>`;
      svg += `<title>${escapeHtml(port.name)} · ${escapeHtml(port.role)} · ${escapeHtml(port.portType)}</title>`;
      svg += `<rect class="port-surface" x="${labelX}" y="${centerY - 12}" width="${labelWidth}" height="24" rx="6" fill="#f0f5fa" stroke="#d7e1eb"/>`;
      svg += `<circle class="port-circle" cx="${position.centerX}" cy="${centerY}" r="6" fill="#fff" stroke="${port.color}" stroke-width="2.5"/>`;
      svg += `<text class="port-label" x="${textX}" y="${centerY + 4}" fill="#34485f" font-size="11.5" font-weight="650" text-anchor="${anchor}">${escapeHtml(visibleName)}</text></g>`;
    }
    svg += `</g></svg>`;
    return svg;
  }

  function renderMiniMap(layout, meta) {
    const collected = collectLayout(layout);
    const width = Math.max(1, layout.width || 1);
    const height = Math.max(1, layout.height || 1);
    let result = `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true">`;
    for (const node of collected.nodes) {
      const domain = meta.domains[node.id];
      if (!domain) continue;
      result += `<rect x="${node.absoluteX}" y="${node.absoluteY}" width="${node.width}" height="${node.height}" rx="10" fill="${rgba(domain.color, .13)}" stroke="${domain.color}" stroke-width="4"/>`;
    }
    return `${result}</svg>`;
  }

  async function renderCanvas(root) {
    if (root.dataset.elkStarted === 'true') return;
    root.dataset.elkStarted = 'true';
    try {
      if (typeof window.ELK !== 'function') throw new Error('ELK.js wurde nicht geladen.');
      const payload = decodePayload(root.dataset.elkPayload);
      window.xpedElkInstance ||= new window.ELK();
      window.ecadElkLayoutCache ||= new Map();
      let layout = window.ecadElkLayoutCache.get(payload.layoutKey);
      if (!layout) {
        layout = await window.xpedElkInstance.layout(payload.graph);
        window.ecadElkLayoutCache.set(payload.layoutKey, layout);
        while (window.ecadElkLayoutCache.size > 12) {
          window.ecadElkLayoutCache.delete(window.ecadElkLayoutCache.keys().next().value);
        }
      }
      root.innerHTML = renderSvg(layout, payload.meta);
      const minimap = root.closest('.xped-interactive-canvas')?.querySelector('.canvas-minimap');
      if (minimap) minimap.innerHTML = `<span class="canvas-minimap-title">ÜBERSICHT</span>${renderMiniMap(layout, payload.meta)}`;
      if (payload.meta.selectedId) window.xpedHighlightCanvas(payload.meta.selectedId);
      const fitButton = root.closest('.xped-interactive-canvas')?.querySelector('.canvas-tools button:nth-child(3)');
      if (fitButton && window.xpedCanvasFit) setTimeout(() => {
        if (!root.isConnected) return;
        if (payload.meta.ports[payload.meta.selectedId] &&
            window.xpedCanvasFocusPort?.(root, payload.meta.selectedId)) return;
        window.xpedCanvasFit(fitButton);
      }, 20);
    } catch (error) {
      root.innerHTML = `<div class="elk-error"><strong>Auto-Layout fehlgeschlagen</strong><br>${escapeHtml(error.message || error)}</div>`;
    }
  }

  function scan() {
    document.querySelectorAll('.elk-canvas[data-elk-payload]').forEach(renderCanvas);
  }

  window.xpedCanvasSelect = function (event, id, type) {
    event.stopPropagation();
    window.xpedHighlightCanvas(id);
    event.currentTarget.closest('.xped-interactive-canvas')
      .dispatchEvent(new CustomEvent('xped_select', {detail: {id, type}, bubbles: true}));
  };

  window.xpedCanvasToggle = function (event, id, type) {
    event.stopPropagation();
    event.currentTarget.closest('.xped-interactive-canvas')
      .dispatchEvent(new CustomEvent('xped_toggle', {detail: {id, type}, bubbles: true}));
  };

  window.xpedCanvasClear = function (event) {
    if (event.target.closest('.canvas-object') || event.target.closest('.canvas-toggle')) return;
    event.currentTarget.closest('.xped-interactive-canvas')
      .dispatchEvent(new CustomEvent('xped_clear_selection', {detail: {}, bubbles: true}));
  };

  window.xpedCanvasAssignmentDone = function (button) {
    button.closest('.xped-interactive-canvas')
      .dispatchEvent(new CustomEvent('xped_assignment_done', {detail: {}, bubbles: true}));
  };

  window.xpedHighlightCanvas = function (id) {
    document.querySelectorAll('.xped-interactive-canvas').forEach(canvas => {
      const objects = [...canvas.querySelectorAll('.canvas-object')];
      const isSelected = object => object.dataset.objectId === id ||
        Boolean(id && object.dataset.signalId === id);
      const connectionFocus = objects.some(object => isSelected(object) && object.classList.contains('connection-object'));
      canvas.classList.toggle('connection-focus', connectionFocus);
      for (const object of objects) {
        const selected = isSelected(object);
        object.classList.toggle('selected-object', selected);
        object.classList.toggle('dimmed-connection', connectionFocus && object.classList.contains('connection-object') && !selected);
      }
    });
  };

  window.xpedCanvasFocusPort = function (root, portId) {
    const canvas = root.closest('.xped-interactive-canvas');
    const viewport = canvas?.querySelector('.canvas-viewport');
    const target = [...root.querySelectorAll('.port-object[data-object-id]')]
      .find(object => object.dataset.objectId === portId);
    const scaleButton = canvas?.querySelector('.canvas-tools button');
    if (!viewport || !target || !scaleButton || !window.xpedCanvasScale) return false;
    const scale = Math.min(1.6, Math.max(1.1,
      Math.min(viewport.clientWidth / 700, viewport.clientHeight / 420)));
    window.xpedCanvasScale(scaleButton, scale);
    const portRect = target.getBoundingClientRect();
    const viewRect = viewport.getBoundingClientRect();
    viewport.scrollTo({
      left: viewport.scrollLeft + portRect.left - viewRect.left +
        (portRect.width - viewRect.width) / 2,
      top: viewport.scrollTop + portRect.top - viewRect.top +
        (portRect.height - viewRect.height) / 2,
      behavior: 'smooth',
    });
    return true;
  };

  window.xpedCanvasRelayout = function (button) {
    const root = button.closest('.xped-interactive-canvas')?.querySelector('.elk-canvas[data-elk-payload]');
    if (!root) return;
    try {
      const payload = decodePayload(root.dataset.elkPayload);
      window.ecadElkLayoutCache?.delete(payload.layoutKey);
    } catch (_) {
      // Rendering below reports malformed payloads consistently.
    }
    root.dataset.elkStarted = 'false';
    root.innerHTML = '<div class="elk-loading">Architektur wird neu angeordnet …</div>';
    renderCanvas(root);
  };

  new MutationObserver(scan).observe(document.documentElement, {childList: true, subtree: true});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', scan);
  else scan();
})();
