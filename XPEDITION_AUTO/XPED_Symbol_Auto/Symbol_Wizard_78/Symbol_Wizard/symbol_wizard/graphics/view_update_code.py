"""Canonical update source extracted from `view.py`.

Executed on temporary shadow classes by `view_updates.apply_*_updates`;
real classes receive only final canonical methods.
"""

from __future__ import annotations

try:
    from symbol_wizard.gui.selection_filter import selection_filter_kind_for_item as _selection_filter_kind_for_item, is_selection_enabled_for_item as _is_selection_enabled_for_item
except Exception:
    _selection_filter_kind_for_item = None
    _is_selection_enabled_for_item = None

# -----------------------------------------------------------------------------
# Liebherr v114: deterministic multi-select group interaction
# -----------------------------------------------------------------------------
# Replaces all previous runtime group-drag layers with one clean path:
# - Rubberband/Select All can select BODY, PIN, TEXT and GRAPHIC together.
# - A single transparent group frame is drawn for multi-selection.
# - Drag inside that frame moves the selected objects as one group.
# - During drag, items are preview-moved only; model data is committed once on release.
# - No property/tree/table rebuilds are triggered during mouse movement.
try:
    from PySide6.QtCore import QRectF as _compat_0008, QPointF as _compat_0007, Qt as _compat_0010, QTimer as _compat_0009, QElapsedTimer as _compat_0004
    from PySide6.QtGui import QPen as _compat_0006, QColor as _compat_0002, QBrush as _compat_0001, QCursor as _compat_0003
    from PySide6.QtWidgets import QGraphicsView as _compat_0005
except Exception:
    pass


def _compat_0103(event):
    try:
        return event.position().toPoint()
    except Exception:
        return event.pos()


def _compat_0110(it):
    try:
        return it.data(0)
    except Exception:
        return None


def _compat_0104(kind, item=None):
    # Legacy-equivalent mapping: return 'ATTRIBUTES' if kind in ('ATTR_REF_DES', 'ATTR_BODY') else kind
    if item is not None and _selection_filter_kind_for_item is not None:
        try:
            return _selection_filter_kind_for_item(item)
        except Exception:
            pass
    if kind == 'BODY_GRAPHIC':
        return 'BODY'
    if kind in ('ATTR_REF_DES', 'ATTR_BODY'):
        return 'ATTRIBUTES'
    return kind


def _compat_0108(it):
    try:
        return _compat_0110(it) in ('BODY', 'PIN', 'TEXT', 'ATTR_REF_DES', 'ATTR_BODY', 'GRAPHIC') and getattr(it, 'model', None) is not None
    except Exception:
        return False


def _compat_0123(view):
    try:
        return [it for it in view.scene().selectedItems() if _compat_0108(it)]
    except Exception:
        return []


def _compat_0109(it):
    try:
        return it.mapToScene(it.shape()).boundingRect()
    except Exception:
        try:
            return it.sceneBoundingRect()
        except Exception:
            return _compat_0008()


def _compat_0124(view):
    r = _compat_0008()
    for it in _compat_0123(view):
        ir = _compat_0109(it)
        if ir.isNull():
            continue
        r = ir if r.isNull() else r.united(ir)
    return r


def _compat_0107(view):
    r = _compat_0124(view)
    if r.isNull():
        return r
    try:
        m = max(12.0, float(getattr(view.window, 'grid_px', 50.0) or 50.0) * 0.18)
    except Exception:
        m = 12.0
    return r.adjusted(-m, -m, m, m)


def _compat_0122(view):
    out = []
    try:
        enabled = getattr(view.window, 'selection_enabled', {}) or {}
        for it in view.scene().items():
            if not _compat_0108(it):
                continue
            if _is_selection_enabled_for_item is not None:
                try:
                    if _is_selection_enabled_for_item(it, enabled):
                        out.append(it)
                    continue
                except Exception:
                    pass
            fk = _compat_0104(_compat_0110(it), it)
            if fk in ('BODY', 'PIN', 'TEXT', 'ATTRIBUTES', 'GRAPHIC') and enabled.get(fk, True):
                out.append(it)
    except Exception:
        pass
    return out


def _compat_0125(view, scene_dx, scene_dy):
    try:
        g = float(getattr(view.window, 'grid_px', 50.0) or 50.0)
        dxg = float(scene_dx) / g
        dyg = -float(scene_dy) / g
        if hasattr(view.window, 'snap_grid_value'):
            dxg = view.window.snap_grid_value(dxg)
            dyg = view.window.snap_grid_value(dyg)
        return dxg, dyg
    except Exception:
        return 0.0, 0.0


def _compat_0106(view, dxg, dyg):
    try:
        g = float(getattr(view.window, 'grid_px', 50.0) or 50.0)
        return _compat_0007(dxg * g, -dyg * g)
    except Exception:
        return _compat_0007(0, 0)


def _compat_0096(items):
    state = []
    seen = set()
    for it in items:
        try:
            m = getattr(it, 'model', None)
            if m is None or id(m) in seen:
                continue
            seen.add(id(m))
            rec = {
                'item': it,
                'item_pos': it.pos(),
                'model': m,
                'kind': _compat_0110(it),
                'x': float(getattr(m, 'x', 0.0) or 0.0),
                'y': float(getattr(m, 'y', 0.0) or 0.0),
            }
            if rec['kind'] == 'PIN':
                rec['label_x'] = getattr(m, 'label_x', None)
                rec['label_y'] = getattr(m, 'label_y', None)
                rec['number_x'] = getattr(m, 'number_x', None)
                rec['number_y'] = getattr(m, 'number_y', None)
                rec['attrs'] = [(tm, float(getattr(tm, 'x', 0.0) or 0.0), float(getattr(tm, 'y', 0.0) or 0.0)) for tm in (getattr(m, 'attribute_texts', {}) or {}).values()]
            state.append(rec)
        except Exception:
            pass
    return state


def _compat_0084(view, delta):
    # Visual-only movement: suppress model writes triggered by QGraphicsItem::itemChange.
    try:
        view.window._group_drag_visual_only = True
        for rec in getattr(view, '_compat_0100', []) or []:
            it = rec.get('item')
            if it is not None:
                it.setPos(rec.get('item_pos', it.pos()) + delta)
    finally:
        try:
            view.window._group_drag_visual_only = False
        except Exception:
            pass


def _compat_0097(state, dxg, dyg):
    for rec in state:
        try:
            m = rec['model']
            m.x = rec['x'] + dxg
            m.y = rec['y'] + dyg
            if rec.get('kind') == 'PIN':
                try:
                    m.auto_dock = False
                except Exception:
                    pass
                if rec.get('label_x') is not None and rec.get('label_y') is not None:
                    m.label_x = float(rec['label_x']) + dxg
                    m.label_y = float(rec['label_y']) + dyg
                if rec.get('number_x') is not None and rec.get('number_y') is not None:
                    m.number_x = float(rec['number_x']) + dxg
                    m.number_y = float(rec['number_y']) + dyg
                for tm, x, y in rec.get('attrs', []):
                    try:
                        tm.x = x + dxg
                        tm.y = y + dyg
                    except Exception:
                        pass
        except Exception:
            pass


def _compat_0102(view, pos=None):
    try:
        if not getattr(view, '_compat_0098', False):
            return False
        if pos is None:
            pos = view.viewport().mapFromGlobal(_compat_0003.pos())
        vp = view.viewport().rect()
        edge = 42
        max_step = 7
        dx = dy = 0
        if pos.x() < vp.left() + edge:
            dx = -max(1, int((vp.left() + edge - pos.x()) / edge * max_step))
        elif pos.x() > vp.right() - edge:
            dx = max(1, int((pos.x() - (vp.right() - edge)) / edge * max_step))
        if pos.y() < vp.top() + edge:
            dy = -max(1, int((vp.top() + edge - pos.y()) / edge * max_step))
        elif pos.y() > vp.bottom() - edge:
            dy = max(1, int((pos.y() - (vp.bottom() - edge)) / edge * max_step))
        changed = False
        if dx:
            b = view.horizontalScrollBar(); old = b.value(); b.setValue(old + dx); changed = changed or b.value() != old
        if dy:
            b = view.verticalScrollBar(); old = b.value(); b.setValue(old + dy); changed = changed or b.value() != old
        return changed
    except Exception:
        return False


_compat_0088 = SymbolView.mousePressEvent
_compat_0087 = getattr(SymbolView, 'mouseMoveEvent', None)
_compat_0089 = getattr(SymbolView, 'mouseReleaseEvent', None)


def _compat_0129(self, scene, window):
    # Call the original class initializer only, not old runtime patch layers.
    SymbolView.__bases__[0].__init__(self, scene)
    self.window = window
    self.setRenderHint(QPainter.Antialiasing)
    self.setCacheMode(_compat_0005.CacheNone)
    self.setViewportUpdateMode(_compat_0005.BoundingRectViewportUpdate)
    self.setDragMode(_compat_0005.RubberBandDrag)
    self.setRubberBandSelectionMode(_compat_0010.IntersectsItemShape)
    self.setTransformationAnchor(_compat_0005.AnchorUnderMouse)
    self.setResizeAnchor(_compat_0005.AnchorUnderMouse)
    self.setFocusPolicy(_compat_0010.StrongFocus)
    self._compat_0098 = False
    self._compat_0100 = []
    self._compat_0099 = None
    self._compat_0111 = (0.0, 0.0)
    self._compat_0112 = _compat_0007(0, 0)
    self._compat_0113 = None
    try:
        self._compat_0121 = _compat_0009(self)
        self._compat_0121.setInterval(60)
        self._compat_0121.timeout.connect(lambda v=self: (_compat_0102(v), v.viewport().update() if getattr(v, '_compat_0098', False) else None))
    except Exception:
        self._compat_0121 = None
    try:
        self.rubberBandChanged.connect(self._rubber_band_changed)
    except Exception:
        pass


def _compat_0120(self, viewport_rect, from_scene, to_scene):
    try:
        if not viewport_rect.isNull():
            return
        rect = _compat_0008(from_scene, to_scene).normalized()
        if not rect.isValid() or rect.width() <= 0 or rect.height() <= 0:
            return
        self.scene().blockSignals(True)
        try:
            selectable = _compat_0122(self)
            selected = []
            for it in selectable:
                hit = _compat_0109(it)
                ok = rect.intersects(hit)
                it.setSelected(ok)
                if ok:
                    selected.append(it)
        finally:
            self.scene().blockSignals(False)
        self.scene().invalidate(rect.adjusted(-20, -20, 20, 20))
        self.viewport().update()
        try:
            self.window.schedule_property_refresh()
        except Exception:
            pass
    except Exception:
        pass


def _compat_0101(self, painter, rect):
    try:
        items = _compat_0123(self)
        if len(items) < 2:
            return
        r = _compat_0124(self)
        if r.isNull() or r.width() <= 0 or r.height() <= 0:
            return
        painter.save()
        pen = _compat_0006(_compat_0002(25, 25, 25), 0, _compat_0010.DashLine)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(_compat_0001(_compat_0010.NoBrush))
        painter.drawRect(r)
        # Small unfilled corner markers.  No opaque fill, so the selected objects stay visible.
        s = 8.0
        for x in (r.left(), r.right()):
            for y in (r.top(), r.bottom()):
                painter.drawRect(_compat_0008(x - s/2, y - s/2, s, s))
        painter.restore()
    except Exception:
        pass


def _compat_0115(self, event):
    try:
        pos = _compat_0103(event)
        if event.button() == _compat_0010.LeftButton and getattr(self.window, 'draw_tool', None) == DrawTool.SELECT.value:
            selected = _compat_0123(self)
            if len(selected) > 1 and _compat_0107(self).contains(self.mapToScene(pos)):
                try:
                    self.window.push_undo_state()
                except Exception:
                    pass
                self._compat_0098 = True
                self._compat_0099 = self.mapToScene(pos)
                self._compat_0100 = _compat_0096(selected)
                self._compat_0111 = (0.0, 0.0)
                self._compat_0112 = _compat_0007(0, 0)
                self._compat_0113 = pos
                try:
                    self.setRenderHint(QPainter.Antialiasing, False)
                    self.setCursor(_compat_0010.SizeAllCursor)
                except Exception:
                    pass
                t = getattr(self, '_compat_0121', None)
                if t is not None and not t.isActive():
                    t.start()
                event.accept()
                return
    except Exception:
        pass
    return _compat_0088(self, event)


def _compat_0114(self, event):
    if getattr(self, '_compat_0098', False):
        try:
            pos = _compat_0103(event)
            cur = self.mapToScene(pos)
            dxg, dyg = _compat_0125(self, cur.x() - self._compat_0099.x(), cur.y() - self._compat_0099.y())
            if (dxg, dyg) != getattr(self, '_compat_0111', None):
                scene_delta = _compat_0106(self, dxg, dyg)
                self._compat_0111 = (dxg, dyg)
                self._compat_0112 = scene_delta
                _compat_0084(self, scene_delta)
            self._compat_0113 = pos
            _compat_0102(self, pos)
            self.viewport().update()
            event.accept()
            return
        except Exception:
            pass
    if _compat_0087 is not None:
        return _compat_0087(self, event)
    return _compat_0005.mouseMoveEvent(self, event)


def _compat_0116(self, event):
    if getattr(self, '_compat_0098', False):
        try:
            t = getattr(self, '_compat_0121', None)
            if t is not None and t.isActive():
                t.stop()
        except Exception:
            pass
        state = list(getattr(self, '_compat_0100', []) or [])
        dxg, dyg = getattr(self, '_compat_0111', (0.0, 0.0))
        self._compat_0098 = False
        self._compat_0100 = []
        self._compat_0099 = None
        try:
            self.setRenderHint(QPainter.Antialiasing, True)
            self.unsetCursor()
        except Exception:
            pass
        # Restore preview positions; then write the model delta exactly once.
        try:
            self.window._group_drag_visual_only = True
            for rec in state:
                try:
                    rec['item'].setPos(rec['item_pos'])
                except Exception:
                    pass
        finally:
            try:
                self.window._group_drag_visual_only = False
            except Exception:
                pass
        _compat_0097(state, dxg, dyg)
        try:
            self.window._selection_restore_ids = {id(rec['model']) for rec in state}
            self.window.update_current_unit_canvas_positions()
            self.window.schedule_property_refresh()
            self.scene().update()
            self.viewport().update()
        except Exception:
            pass
        event.accept()
        return
    if _compat_0089 is not None:
        return _compat_0089(self, event)
    return _compat_0005.mouseReleaseEvent(self, event)


try:
    SymbolView.__init__ = _compat_0129
    SymbolView._rubber_band_changed = _compat_0120
    SymbolView.drawForeground = _compat_0101
    SymbolView.mousePressEvent = _compat_0115
    SymbolView.mouseMoveEvent = _compat_0114
    SymbolView.mouseReleaseEvent = _compat_0116
except Exception:
    pass

# -----------------------------------------------------------------------------
# Liebherr v115: QGraphicsItemGroup based multi-selection drag
# -----------------------------------------------------------------------------
# The previous implementation preview-moved every selected item on every mouse
# move.  That is visually correct but too slow for large symbols.  This final
# layer uses a temporary QGraphicsItemGroup as one lightweight preview object.
# Model data is still written exactly once on mouse release.
try:
    from PySide6.QtWidgets import QGraphicsItem as _compat_0011
except Exception:
    pass

_compat_0141 = SymbolView.mousePressEvent
_compat_0140 = SymbolView.mouseMoveEvent
_compat_0142 = SymbolView.mouseReleaseEvent
_compat_0139 = SymbolView.drawForeground


def _compat_0131(view):
    try:
        return [it for it in view.scene().selectedItems() if _compat_0108(it)]
    except Exception:
        return []


def _compat_0150(items):
    r = _compat_0008()
    for it in items:
        try:
            ir = _compat_0109(it)
            if not ir.isNull():
                r = ir if r.isNull() else r.united(ir)
        except Exception:
            pass
    return r


def _compat_0144(view):
    try:
        group = getattr(view, '_compat_0133', None)
        if group is not None:
            return group.sceneBoundingRect()
    except Exception:
        pass
    return _compat_0150(_compat_0131(view))


def _compat_0143(view):
    r = _compat_0144(view)
    if r.isNull():
        return r
    try:
        # Make the frame itself and the inner area comfortably grabbable.
        g = float(getattr(view.window, 'grid_px', 50.0) or 50.0)
        margin = max(18.0, g * 0.30)
    except Exception:
        margin = 18.0
    return r.adjusted(-margin, -margin, margin, margin)


def _compat_0130(view, pos):
    selected = _compat_0131(view)
    if len(selected) < 2:
        return False
    scene_pos = view.mapToScene(pos)
    if not _compat_0143(view).contains(scene_pos):
        return False

    try:
        view.window.push_undo_state()
    except Exception:
        pass

    state = _compat_0096(selected)
    if not state:
        return False

    scene = view.scene()
    group = None
    try:
        scene.blockSignals(True)
        # Create one temporary group for fast preview movement.  The children keep
        # their local geometry; only the parent group moves while dragging.
        group = scene.createItemGroup(selected)
        group.setFlag(_compat_0011.ItemIsSelectable, False)
        group.setFlag(_compat_0011.ItemIsMovable, False)
        group.setZValue(max([getattr(it, 'zValue', lambda: 0)() for it in selected] + [0]) + 1000)
    finally:
        try:
            scene.blockSignals(False)
        except Exception:
            pass

    view._compat_0132 = True
    view._compat_0098 = True
    view._compat_0133 = group
    view._compat_0136 = state
    view._compat_0135 = scene_pos
    view._compat_0134 = group.pos() if group is not None else _compat_0007(0, 0)
    view._compat_0145 = (0.0, 0.0)
    view._compat_0146 = pos
    try:
        view.setRenderHint(QPainter.Antialiasing, False)
        view.setViewportUpdateMode(_compat_0005.SmartViewportUpdate)
        view.setCursor(_compat_0010.SizeAllCursor)
    except Exception:
        pass
    try:
        t = getattr(view, '_compat_0121', None)
        if t is not None and not t.isActive():
            t.start()
    except Exception:
        pass
    view.viewport().update()
    return True


def _compat_0151(view, pos):
    try:
        cur = view.mapToScene(pos)
        dxg, dyg = _compat_0125(view, cur.x() - view._compat_0135.x(), cur.y() - view._compat_0135.y())
        if (dxg, dyg) != getattr(view, '_compat_0145', None):
            delta = _compat_0106(view, dxg, dyg)
            group = getattr(view, '_compat_0133', None)
            if group is not None:
                group.setPos(view._compat_0134 + delta)
            view._compat_0145 = (dxg, dyg)
        view._compat_0146 = pos
        _compat_0102(view, pos)
        view.viewport().update()
        return True
    except Exception:
        return False


def _compat_0138(view):
    state = list(getattr(view, '_compat_0136', []) or [])
    dxg, dyg = getattr(view, '_compat_0145', (0.0, 0.0))
    group = getattr(view, '_compat_0133', None)
    scene = view.scene()

    try:
        t = getattr(view, '_compat_0121', None)
        if t is not None and t.isActive():
            t.stop()
    except Exception:
        pass

    view._compat_0132 = False
    view._compat_0098 = False
    view._compat_0133 = None
    view._compat_0136 = []
    view._compat_0135 = None

    try:
        scene.blockSignals(True)
        if group is not None:
            # Reset preview group to original scene position before ungrouping.
            try:
                group.setPos(getattr(view, '_compat_0134', _compat_0007(0, 0)))
            except Exception:
                pass
            scene.destroyItemGroup(group)
    finally:
        try:
            scene.blockSignals(False)
        except Exception:
            pass

    _compat_0097(state, dxg, dyg)

    try:
        view.setRenderHint(QPainter.Antialiasing, True)
        view.setViewportUpdateMode(_compat_0005.BoundingRectViewportUpdate)
        view.unsetCursor()
    except Exception:
        pass

    try:
        view.window._selection_restore_ids = {id(rec['model']) for rec in state}
        view.window.update_current_unit_canvas_positions()
        # Restore child selection after temporary grouping destroyed it.
        wanted = set(view.window._selection_restore_ids)
        for it in scene.items():
            m = getattr(it, 'model', None)
            if m is not None and id(m) in wanted:
                it.setSelected(True)
        view.window.schedule_property_refresh()
        scene.update()
        view.viewport().update()
    except Exception:
        pass


def _compat_0148(self, event):
    try:
        pos = _compat_0103(event)
        if event.button() == _compat_0010.LeftButton and getattr(self.window, 'draw_tool', None) == DrawTool.SELECT.value:
            if _compat_0130(self, pos):
                event.accept()
                return
    except Exception:
        pass
    return _compat_0141(self, event)


def _compat_0147(self, event):
    if getattr(self, '_compat_0132', False):
        pos = _compat_0103(event)
        _compat_0151(self, pos)
        event.accept()
        return
    return _compat_0140(self, event)


def _compat_0149(self, event):
    if getattr(self, '_compat_0132', False):
        _compat_0138(self)
        event.accept()
        return
    return _compat_0142(self, event)


def _compat_0137(self, painter, rect):
    try:
        # When dragging, draw the frame around the temporary group.  Otherwise draw
        # it around the selected canvas items.  The frame is outline-only.
        if getattr(self, '_compat_0132', False):
            r = _compat_0144(self)
        else:
            items = _compat_0131(self)
            if len(items) < 2:
                return
            r = _compat_0150(items)
        if r.isNull() or r.width() <= 0 or r.height() <= 0:
            return
        painter.save()
        pen = _compat_0006(_compat_0002(25, 25, 25), 0, _compat_0010.DashLine)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(_compat_0001(_compat_0010.NoBrush))
        painter.drawRect(r)
        s = 8.0
        for x in (r.left(), r.right()):
            for y in (r.top(), r.bottom()):
                painter.drawRect(_compat_0008(x - s/2, y - s/2, s, s))
        painter.restore()
    except Exception:
        try:
            return _compat_0139(self, painter, rect)
        except Exception:
            pass

try:
    SymbolView.mousePressEvent = _compat_0148
    SymbolView.mouseMoveEvent = _compat_0147
    SymbolView.mouseReleaseEvent = _compat_0149
    SymbolView.drawForeground = _compat_0137
except Exception:
    pass

# -----------------------------------------------------------------------------
# Liebherr v116: final unified multi-select behavior
# -----------------------------------------------------------------------------
# Fixes:
# - Ctrl+A must always select all canvas objects when the view is active, even if
#   a text item has focus.
# - Multi-selection must stay a logical group after every operation: one shared
#   transparent frame, no individual item frames.
# - LMB drag inside the shared frame moves the group with a lightweight visual
#   preview and commits the model delta once on release.
# - No temporary QGraphicsItemGroup is used here; reparenting many items was too
#   expensive and also changed the selection state in confusing ways.
try:
    from PySide6.QtCore import QRectF as _compat_0019, QPointF as _compat_0018, Qt as _compat_0023, QTimer as _compat_0022
    from PySide6.QtGui import QPen as _compat_0017, QColor as _compat_0013, QBrush as _compat_0012, QPainter as _compat_0016, QCursor as _compat_0014
    from PySide6.QtWidgets import QGraphicsView as _compat_0015
except Exception:
    pass

_compat_0154 = SymbolView.mousePressEvent
_compat_0153 = SymbolView.mouseMoveEvent
_compat_0155 = SymbolView.mouseReleaseEvent
_compat_0152 = SymbolView.keyPressEvent


def _compat_0172(it):
    try:
        return it.data(0)
    except Exception:
        return None


def _compat_0170(it):
    try:
        return _compat_0172(it) in ('BODY', 'PIN', 'TEXT', 'ATTR_REF_DES', 'ATTR_BODY', 'GRAPHIC') and getattr(it, 'model', None) is not None
    except Exception:
        return False


def _compat_0186(view):
    try:
        return [it for it in view.scene().selectedItems() if _compat_0170(it)]
    except Exception:
        return []


def _compat_0184(it):
    try:
        r = it.mapToScene(it.shape()).boundingRect()
        if r.isValid() and not r.isNull():
            return r
    except Exception:
        pass
    try:
        return it.sceneBoundingRect()
    except Exception:
        return _compat_0019()


def _compat_0169(view):
    r = _compat_0019()
    for it in _compat_0186(view):
        try:
            ir = _compat_0184(it)
            if ir.isNull():
                continue
            r = ir if r.isNull() else r.united(ir)
        except Exception:
            pass
    return r


def _compat_0168(view):
    r = _compat_0169(view)
    if r.isNull():
        return r
    try:
        g = float(getattr(view.window, 'grid_px', 50.0) or 50.0)
        margin = max(20.0, g * 0.30)
    except Exception:
        margin = 20.0
    return r.adjusted(-margin, -margin, margin, margin)


def _compat_0165(event):
    try:
        return event.position().toPoint()
    except Exception:
        return event.pos()


def _compat_0158(items):
    state = []
    seen = set()
    for it in items:
        try:
            m = getattr(it, 'model', None)
            if m is None or id(m) in seen:
                continue
            seen.add(id(m))
            rec = {
                'item': it,
                'model': m,
                'kind': _compat_0172(it),
                'item_pos': it.pos(),
                'x': float(getattr(m, 'x', 0.0) or 0.0),
                'y': float(getattr(m, 'y', 0.0) or 0.0),
            }
            if rec['kind'] == 'PIN':
                rec['label_x'] = getattr(m, 'label_x', None)
                rec['label_y'] = getattr(m, 'label_y', None)
                rec['number_x'] = getattr(m, 'number_x', None)
                rec['number_y'] = getattr(m, 'number_y', None)
                rec['attrs'] = [(tm, float(getattr(tm, 'x', 0.0) or 0.0), float(getattr(tm, 'y', 0.0) or 0.0)) for tm in (getattr(m, 'attribute_texts', {}) or {}).values()]
            state.append(rec)
        except Exception:
            pass
    return state


def _compat_0188(view, scene_dx, scene_dy):
    try:
        g = float(getattr(view.window, 'grid_px', 50.0) or 50.0)
        dxg = float(scene_dx) / g
        dyg = -float(scene_dy) / g
        if hasattr(view.window, 'snap_grid_value'):
            dxg = view.window.snap_grid_value(dxg)
            dyg = view.window.snap_grid_value(dyg)
        return dxg, dyg
    except Exception:
        return 0.0, 0.0


def _compat_0167(view, dxg, dyg):
    try:
        g = float(getattr(view.window, 'grid_px', 50.0) or 50.0)
        return _compat_0018(float(dxg) * g, -float(dyg) * g)
    except Exception:
        return _compat_0018(0, 0)


def _compat_0187(view, scene_delta):
    try:
        view.window._group_drag_visual_only = True
    except Exception:
        pass
    try:
        for rec in getattr(view, '_compat_0162', []) or []:
            it = rec.get('item')
            if it is not None:
                it.setPos(rec.get('item_pos', it.pos()) + scene_delta)
    finally:
        try:
            view.window._group_drag_visual_only = False
        except Exception:
            pass


def _compat_0159(state, dxg, dyg):
    for rec in state:
        try:
            m = rec['model']
            m.x = rec['x'] + dxg
            m.y = rec['y'] + dyg
            if rec.get('kind') == 'PIN':
                try:
                    m.auto_dock = False
                except Exception:
                    pass
                if rec.get('label_x') is not None and rec.get('label_y') is not None:
                    m.label_x = float(rec['label_x']) + dxg
                    m.label_y = float(rec['label_y']) + dyg
                if rec.get('number_x') is not None and rec.get('number_y') is not None:
                    m.number_x = float(rec['number_x']) + dxg
                    m.number_y = float(rec['number_y']) + dyg
                for tm, x, y in rec.get('attrs', []):
                    try:
                        tm.x = x + dxg
                        tm.y = y + dyg
                    except Exception:
                        pass
        except Exception:
            pass


def _compat_0164(view, pos=None):
    try:
        if not getattr(view, '_compat_0160', False):
            return False
        if pos is None:
            pos = view.viewport().mapFromGlobal(_compat_0014.pos())
        vp = view.viewport().rect()
        edge = 54
        max_step = 5
        dx = dy = 0
        if pos.x() < vp.left() + edge:
            dx = -max(1, int((vp.left() + edge - pos.x()) / edge * max_step))
        elif pos.x() > vp.right() - edge:
            dx = max(1, int((pos.x() - (vp.right() - edge)) / edge * max_step))
        if pos.y() < vp.top() + edge:
            dy = -max(1, int((vp.top() + edge - pos.y()) / edge * max_step))
        elif pos.y() > vp.bottom() - edge:
            dy = max(1, int((pos.y() - (vp.bottom() - edge)) / edge * max_step))
        changed = False
        if dx:
            b = view.horizontalScrollBar(); old = b.value(); b.setValue(old + dx); changed = changed or b.value() != old
        if dy:
            b = view.verticalScrollBar(); old = b.value(); b.setValue(old + dy); changed = changed or b.value() != old
        return changed
    except Exception:
        return False


def _compat_0163(self, painter, rect):
    # One shared transparent frame for multi-selection.  No fill.
    try:
        items = _compat_0186(self)
        if len(items) < 2:
            return
        r = _compat_0169(self)
        if r.isNull() or r.width() <= 0 or r.height() <= 0:
            return
        painter.save()
        pen = _compat_0017(_compat_0013(25, 25, 25), 0, _compat_0023.DashLine)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(_compat_0012(_compat_0023.NoBrush))
        painter.drawRect(r)
        s = 8.0
        for x in (r.left(), r.right()):
            for y in (r.top(), r.bottom()):
                painter.drawRect(_compat_0019(x - s / 2, y - s / 2, s, s))
        painter.restore()
    except Exception:
        pass


def _compat_0156(view, pos):
    items = _compat_0186(view)
    if len(items) < 2:
        return False
    if not _compat_0168(view).contains(view.mapToScene(pos)):
        return False
    try:
        view.window.push_undo_state()
    except Exception:
        pass
    state = _compat_0158(items)
    if not state:
        return False
    view._compat_0160 = True
    view._compat_0162 = state
    view._compat_0161 = view.mapToScene(pos)
    view._compat_0173 = (0.0, 0.0)
    view._compat_0174 = pos
    try:
        view.setRenderHint(_compat_0016.Antialiasing, False)
        view.setViewportUpdateMode(_compat_0015.SmartViewportUpdate)
        view.setCursor(_compat_0023.SizeAllCursor)
    except Exception:
        pass
    try:
        if not hasattr(view, '_compat_0185') or view._compat_0185 is None:
            view._compat_0185 = _compat_0022(view)
            view._compat_0185.setInterval(70)
            view._compat_0185.timeout.connect(lambda v=view: (_compat_0164(v), v.viewport().update() if getattr(v, '_compat_0160', False) else None))
        if not view._compat_0185.isActive():
            view._compat_0185.start()
    except Exception:
        pass
    view.viewport().update()
    return True


def _compat_0176(self, event):
    try:
        pos = _compat_0165(event)
        if event.button() == _compat_0023.LeftButton and getattr(self.window, 'draw_tool', None) == DrawTool.SELECT.value:
            if _compat_0156(self, pos):
                event.accept()
                return
    except Exception:
        pass
    return _compat_0154(self, event)


def _compat_0175(self, event):
    if getattr(self, '_compat_0160', False):
        try:
            pos = _compat_0165(event)
            cur = self.mapToScene(pos)
            dxg, dyg = _compat_0188(self, cur.x() - self._compat_0161.x(), cur.y() - self._compat_0161.y())
            if (dxg, dyg) != getattr(self, '_compat_0173', None):
                _compat_0187(self, _compat_0167(self, dxg, dyg))
                self._compat_0173 = (dxg, dyg)
            self._compat_0174 = pos
            _compat_0164(self, pos)
            self.viewport().update()
            event.accept()
            return
        except Exception:
            pass
    return _compat_0153(self, event)


def _compat_0177(self, event):
    if getattr(self, '_compat_0160', False):
        state = list(getattr(self, '_compat_0162', []) or [])
        dxg, dyg = getattr(self, '_compat_0173', (0.0, 0.0))
        self._compat_0160 = False
        self._compat_0162 = []
        self._compat_0161 = None
        try:
            t = getattr(self, '_compat_0185', None)
            if t is not None and t.isActive():
                t.stop()
        except Exception:
            pass
        # Reset visual preview, commit once, then refresh positions once.
        try:
            self.window._group_drag_visual_only = True
            for rec in state:
                try:
                    rec['item'].setPos(rec['item_pos'])
                except Exception:
                    pass
        finally:
            try:
                self.window._group_drag_visual_only = False
            except Exception:
                pass
        _compat_0159(state, dxg, dyg)
        try:
            self.setRenderHint(_compat_0016.Antialiasing, True)
            self.setViewportUpdateMode(_compat_0015.BoundingRectViewportUpdate)
            self.unsetCursor()
        except Exception:
            pass
        try:
            wanted = {id(rec['model']) for rec in state}
            self.window._selection_restore_ids = wanted
            self.window.update_current_unit_canvas_positions()
            # Explicitly keep the same multi-selection active and grouped.
            for it in self.scene().items():
                m = getattr(it, 'model', None)
                if m is not None and id(m) in wanted:
                    it.setSelected(True)
            self.window.schedule_property_refresh()
            self.scene().update()
            self.viewport().update()
        except Exception:
            pass
        event.accept()
        return
    return _compat_0155(self, event)


def _compat_0171(self, event):
    # Ctrl+A is a canvas command, even if a text item has focus.  This prevents
    # QGraphicsTextItem from selecting only its plain text content.
    try:
        if (event.modifiers() & _compat_0023.ControlModifier) and event.key() == _compat_0023.Key_A:
            self.window.set_tool(DrawTool.SELECT.value)
            self.window.select_all_canvas()
            event.accept()
            return
    except Exception:
        pass
    return _compat_0152(self, event)

try:
    SymbolView.drawForeground = _compat_0163
    SymbolView.mousePressEvent = _compat_0176
    SymbolView.mouseMoveEvent = _compat_0175
    SymbolView.mouseReleaseEvent = _compat_0177
    SymbolView.keyPressEvent = _compat_0171
except Exception:
    pass


# -----------------------------------------------------------------------------
# Liebherr v120: final interaction/performance tuning
# -----------------------------------------------------------------------------
# The previous multi-select versions were still expensive on large symbols.  This
# layer keeps selection deterministic and prevents heavy sync during group drag.
try:
    from PySide6.QtCore import Qt as _compat_0036, QRectF as _compat_0032, QPointF as _compat_0031, QTimer as _compat_0035
    from PySide6.QtGui import QPen as _compat_0030, QColor as _compat_0025, QBrush as _compat_0024, QPainter as _compat_0029
    from PySide6.QtWidgets import QGraphicsView as _compat_0027
except Exception:
    pass


def _compat_0191(view):
    try:
        enabled = getattr(view.window, 'selection_enabled', {}) or {}
        for it in view.scene().items():
            try:
                kind = it.data(0)
                if kind not in ('BODY','PIN','TEXT','ATTR_REF_DES','ATTR_BODY','GRAPHIC'):
                    continue
                if getattr(it, 'model', None) is None:
                    continue
                if _is_selection_enabled_for_item is not None:
                    try:
                        if _is_selection_enabled_for_item(it, enabled):
                            yield it
                        continue
                    except Exception:
                        pass
                fk = 'ATTRIBUTES' if kind in ('ATTR_REF_DES','ATTR_BODY') else kind
                if fk in ('BODY','PIN','TEXT','ATTRIBUTES','GRAPHIC') and enabled.get(fk, True):
                    yield it
            except Exception:
                continue
    except Exception:
        return


def _compat_0215(view):
    try:
        return [i for i in view.scene().selectedItems() if i.data(0) in ('BODY','PIN','TEXT','ATTR_REF_DES','ATTR_BODY','GRAPHIC') and getattr(i, 'model', None) is not None]
    except Exception:
        return []


def _compat_0194(it):
    try:
        return it.mapToScene(it.shape()).boundingRect()
    except Exception:
        try:
            return it.sceneBoundingRect()
        except Exception:
            return _compat_0032()


def _compat_0216(view):
    r = _compat_0032()
    for it in _compat_0215(view):
        ir = _compat_0194(it)
        if ir.isNull():
            continue
        r = ir if r.isNull() else r.united(ir)
    return r

# Replace rubberband with an intersects-shape selection that works for ALL.
def _compat_0213(self, viewport_rect, from_scene, to_scene):
    try:
        if not viewport_rect.isNull():
            return
        rect = _compat_0032(from_scene, to_scene).normalized()
        if not rect.isValid() or rect.width() <= 1 or rect.height() <= 1:
            return
        self.scene().blockSignals(True)
        try:
            for it in list(_compat_0191(self)):
                it.setSelected(rect.intersects(_compat_0194(it)))
        finally:
            self.scene().blockSignals(False)
        self.viewport().update()
        try:
            self.window.schedule_property_refresh()
        except Exception:
            pass
    except Exception:
        pass

# Draw one clean shared frame for multi-selection; leave scene format guide untouched.
def _compat_0192(self, painter, rect):
    try:
        # First draw the scene foreground manually because replacing view foreground can hide it on some Qt styles.
        try:
            self.scene().drawForeground(painter, rect)
        except Exception:
            pass
        items = _compat_0215(self)
        if len(items) < 2:
            return
        r = _compat_0216(self)
        if r.isNull() or r.width() <= 0 or r.height() <= 0:
            return
        painter.save()
        pen = _compat_0030(_compat_0025(30, 30, 30), 0, _compat_0036.DashLine)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(_compat_0024(_compat_0036.NoBrush))
        painter.drawRect(r)
        s = 9.0
        for x in (r.left(), r.right()):
            for y in (r.top(), r.bottom()):
                painter.drawRect(_compat_0032(x - s/2, y - s/2, s, s))
        painter.restore()
    except Exception:
        pass

# Faster view initialization.  SmartViewportUpdate plus no antialias during drag is
# a better tradeoff for big FPGA symbols than FullViewportUpdate.
try:
    _compat_0202 = SymbolView.__init__
    def _compat_0193(self, scene, window):
        _compat_0202(self, scene, window)
        try:
            self.setViewportUpdateMode(_compat_0027.SmartViewportUpdate)
            self.setOptimizationFlag(_compat_0027.DontSavePainterState, True)
            self.setOptimizationFlag(_compat_0027.DontAdjustForAntialiasing, True)
            self.setRubberBandSelectionMode(_compat_0036.IntersectsItemShape)
            self._compat_0200 = False
        except Exception:
            pass
    SymbolView.__init__ = _compat_0193
except Exception:
    pass

# Keep the last existing mouse handlers, but suspend heavy sync during group drag.
try:
    _compat_0204 = SymbolView.mousePressEvent
    _compat_0203 = SymbolView.mouseMoveEvent
    _compat_0205 = SymbolView.mouseReleaseEvent
    def _compat_0196(self, event):
        try:
            if event.button() == _compat_0036.LeftButton and len(_compat_0215(self)) > 1:
                p = self.mapToScene(event.position().toPoint() if hasattr(event, 'position') else event.pos())
                r = _compat_0216(self).adjusted(-18, -18, 18, 18)
                if r.contains(p):
                    self.window._suspend_heavy_canvas_sync = True
                    try:
                        self.setRenderHint(_compat_0029.Antialiasing, False)
                    except Exception:
                        pass
        except Exception:
            pass
        return _compat_0204(self, event)
    def _compat_0195(self, event):
        ret = _compat_0203(self, event)
        # Coalesce viewport repaint requests during drag.
        try:
            if getattr(self.window, '_suspend_heavy_canvas_sync', False) and not getattr(self, '_compat_0200', False):
                self._compat_0200 = True
                _compat_0035.singleShot(16, lambda v=self: (setattr(v, '_compat_0200', False), v.viewport().update()))
        except Exception:
            pass
        return ret
    def _compat_0197(self, event):
        try:
            self.window._suspend_heavy_canvas_sync = False
        except Exception:
            pass
        try:
            self.setRenderHint(_compat_0029.Antialiasing, True)
        except Exception:
            pass
        ret = _compat_0205(self, event)
        try:
            self.viewport().update()
        except Exception:
            pass
        return ret
    SymbolView.mousePressEvent = _compat_0196
    SymbolView.mouseMoveEvent = _compat_0195
    SymbolView.mouseReleaseEvent = _compat_0197
except Exception:
    pass

try:
    SymbolView._rubber_band_changed = _compat_0213
    SymbolView.drawForeground = _compat_0192
except Exception:
    pass


# -----------------------------------------------------------------------------
# Liebherr v125: drag-drawn graphic primitives
# -----------------------------------------------------------------------------
# The old graphic tools created fixed 2-grid primitives on mouse press.  This
# final view layer turns Line/Rect/Ellipse into press-drag-release tools with a
# live preview while keeping PIN/TEXT and selection behavior untouched.
try:
    from PySide6.QtCore import Qt as _compat_0066, QPointF as _compat_0064, QRectF as _compat_0065, QLineF as _compat_0062
    from PySide6.QtGui import QPen as _compat_0063, QColor as _compat_0057, QBrush as _compat_0056
    from PySide6.QtWidgets import (
        QGraphicsView as _compat_0061,
        QGraphicsLineItem as _compat_0059,
        QGraphicsRectItem as _compat_0060,
        QGraphicsEllipseItem as _compat_0058,
    )
except Exception:
    pass


def _compat_0856(event):
    try:
        return event.position().toPoint()
    except Exception:
        return event.pos()


def _compat_0862(tool):
    return tool in (DrawTool.LINE.value, DrawTool.RECT.value, DrawTool.ELLIPSE.value)


def _compat_0880(win, p):
    return (win.scene_to_grid_x(p.x()), win.scene_to_grid_y(p.y()))


def _compat_0863(win, x, y):
    try:
        return _compat_0064(float(x) * win.grid_px, -float(y) * win.grid_px)
    except Exception:
        return _compat_0064()


def _compat_0878():
    pen = _compat_0063(_compat_0057(40, 120, 220), 0, _compat_0066.DashLine)
    pen.setCosmetic(True)
    return pen


def _compat_0866(tool, scene_pos):
    if tool == DrawTool.LINE.value:
        item = _compat_0059(_compat_0062(scene_pos, scene_pos))
    elif tool == DrawTool.ELLIPSE.value:
        item = _compat_0058(_compat_0065(scene_pos, scene_pos).normalized())
    else:
        item = _compat_0060(_compat_0065(scene_pos, scene_pos).normalized())
    item.setPen(_compat_0878())
    item.setBrush(_compat_0056(_compat_0066.NoBrush))
    item.setZValue(1000000)
    try:
        item.setAcceptedMouseButtons(_compat_0066.NoButton)
    except Exception:
        pass
    return item


def _compat_0887(view, scene_pos):
    state = getattr(view, '_compat_0859', None)
    if not state:
        return
    tool = state.get('tool')
    start_scene = state.get('start_scene')
    item = state.get('item')
    if item is None or start_scene is None:
        return
    if tool == DrawTool.LINE.value:
        try:
            item.setLine(_compat_0062(start_scene, scene_pos))
        except Exception:
            pass
    else:
        rect = _compat_0065(start_scene, scene_pos).normalized()
        try:
            item.setRect(rect)
        except Exception:
            pass
    try:
        view.viewport().update()
    except Exception:
        pass


def _compat_0879(view):
    state = getattr(view, '_compat_0859', None)
    item = (state or {}).get('item')
    if item is not None:
        try:
            view.scene().removeItem(item)
        except Exception:
            pass
    try:
        view._compat_0859 = None
    except Exception:
        pass
    try:
        if state and state.get('drag_mode') is not None:
            view.setDragMode(state.get('drag_mode'))
    except Exception:
        pass


def _compat_0852(view, scene_pos):
    state = getattr(view, '_compat_0859', None)
    if not state:
        return False
    tool = state.get('tool')
    start_grid = state.get('start_grid')
    try:
        end_grid = _compat_0880(view.window, scene_pos)
    except Exception:
        end_grid = start_grid
    _compat_0879(view)
    if not start_grid or not end_grid:
        return False
    sx, sy = start_grid
    ex, ey = end_grid
    try:
        if tool == DrawTool.LINE.value:
            view.window.add_graphic(tool, sx, sy, ex - sx, sy - ey)
        else:
            x = min(sx, ex)
            y = max(sy, ey)
            w = abs(ex - sx)
            h = abs(sy - ey)
            if w < 1e-9 and h < 1e-9:
                view.window.add_graphic(tool, sx, sy)
            else:
                view.window.add_graphic(tool, x, y, w, h)
        return True
    except TypeError:
        try:
            view.window.add_graphic(tool, sx, sy)
            return True
        except Exception:
            return False
    except Exception:
        return False


def _compat_0857(view, event):
    """Finish an active BODY group drag when the release lands on the view.

    The old item update layer patched ``SymbolView.mouseReleaseEvent`` directly
    from ``item_update_code.py``.  Keeping this hook in the view event pipeline
    makes ownership explicit and avoids a cross-module monkey patch.
    """
    try:
        import symbol_wizard.graphics.items as items_mod
    except Exception:
        items_mod = None
    try:
        scene = view.scene()
        if scene is None:
            return False
        for item in list(scene.items()):
            if not getattr(item, '_compat_0269', False):
                continue
            try:
                pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
                if items_mod is not None and hasattr(items_mod, '_compat_0305'):
                    items_mod._compat_0305(item, view.mapToScene(pos))
            except Exception:
                pass
            try:
                if items_mod is not None and hasattr(items_mod, '_compat_0303'):
                    items_mod._compat_0303(item)
            except Exception:
                pass
            try:
                if items_mod is not None and hasattr(items_mod, '_compat_0281'):
                    items_mod._compat_0281(item, event=None, cancel=False)
            except Exception:
                pass
            event.accept()
            return True
    except Exception:
        pass
    return False


try:
    _compat_0875 = SymbolView.mousePressEvent
    _compat_0874 = SymbolView.mouseMoveEvent
    _compat_0876 = SymbolView.mouseReleaseEvent

    def _compat_0869(self, event):
        try:
            tool = getattr(self.window, 'draw_tool', DrawTool.SELECT.value)
            if event.button() == _compat_0066.LeftButton and _compat_0862(tool):
                vp = _compat_0856(event)
                scene_pos = self.mapToScene(vp)
                gx, gy = _compat_0880(self.window, scene_pos)
                snapped = _compat_0863(self.window, gx, gy)
                item = _compat_0866(tool, snapped)
                self.scene().addItem(item)
                self._compat_0859 = {
                    'tool': tool,
                    'start_grid': (gx, gy),
                    'start_scene': snapped,
                    'item': item,
                    'drag_mode': self.dragMode(),
                }
                self.setDragMode(_compat_0061.NoDrag)
                event.accept()
                return
        except Exception:
            pass
        return _compat_0875(self, event)

    def _compat_0868(self, event):
        try:
            if getattr(self, '_compat_0859', None):
                scene_pos = self.mapToScene(_compat_0856(event))
                gx, gy = _compat_0880(self.window, scene_pos)
                _compat_0887(self, _compat_0863(self.window, gx, gy))
                event.accept()
                return
        except Exception:
            pass
        return _compat_0874(self, event)

    def _compat_0870(self, event):
        try:
            if _compat_0857(self, event):
                return
        except Exception:
            pass
        try:
            if getattr(self, '_compat_0859', None):
                if event.button() == _compat_0066.LeftButton:
                    scene_pos = self.mapToScene(_compat_0856(event))
                    _compat_0852(self, scene_pos)
                else:
                    _compat_0879(self)
                event.accept()
                return
        except Exception:
            try:
                _compat_0879(self)
            except Exception:
                pass
        return _compat_0876(self, event)

    SymbolView.mousePressEvent = _compat_0869
    SymbolView.mouseMoveEvent = _compat_0868
    SymbolView.mouseReleaseEvent = _compat_0870
except Exception:
    pass



# -----------------------------------------------------------------------------
# Selection filter v2: plain text / attributes and canvas auto-scroll while rubber-band selecting
# -----------------------------------------------------------------------------
# The selectable dropdown distinguishes plain TEXT from ATTRIBUTES. Rubber-band
# selection and auto-scroll use the same filter helper as MainWindow and the
# Template Editor.
try:
    from PySide6.QtCore import Qt as _sel_qt, QTimer as _sel_timer, QRectF as _sel_rect
    from PySide6.QtGui import QCursor as _sel_cursor
    from PySide6.QtWidgets import QApplication as _sel_app, QGraphicsItem as _sel_gitem
    from symbol_wizard.models.document import DrawTool as _sel_drawtool
    from symbol_wizard.gui.selection_filter import (
        SELECTION_FILTER_KEYS as _sel_filter_keys,
        is_selection_enabled_for_item as _sel_item_enabled,
        selection_filter_kind_for_item as _sel_filter_for_item,
    )
except Exception:
    _sel_filter_keys = ('BODY', 'PIN', 'TEXT', 'ATTRIBUTES', 'GRAPHIC')
    def _sel_filter_for_item(item):
        try:
            kind = item.data(0)
            if kind in ('ATTR_REF_DES', 'ATTR_BODY'):
                return 'ATTRIBUTES'
            if kind in ('BODY', 'PIN', 'TEXT', 'GRAPHIC'):
                return kind
        except Exception:
            pass
        return None
    def _sel_item_enabled(item, enabled):
        bucket = _sel_filter_for_item(item)
        return bucket in _sel_filter_keys and bool((enabled or {}).get(bucket, True))


def _sel_event_pos(event):
    try:
        return event.position().toPoint()
    except Exception:
        return event.pos()


def _sel_item_rect(item):
    try:
        return item.mapToScene(item.shape()).boundingRect()
    except Exception:
        try:
            return item.mapToScene(item.boundingRect()).boundingRect()
        except Exception:
            try:
                return item.sceneBoundingRect()
            except Exception:
                return _sel_rect()


def _sel_apply_rubber_selection(view, viewport_pos=None):
    try:
        anchor = getattr(view, '_selection_anchor_scene', None)
        if anchor is None:
            return False
        if viewport_pos is None:
            viewport_pos = getattr(view, '_selection_last_pos', None)
        if viewport_pos is None:
            viewport_pos = view.viewport().mapFromGlobal(_sel_cursor.pos())
        rect = _sel_rect(anchor, view.mapToScene(viewport_pos)).normalized()
        if not rect.isValid() or rect.width() <= 1 or rect.height() <= 1:
            return False
        scene = view.scene()
        enabled = getattr(view.window, 'selection_enabled', {}) or {}
        scene.blockSignals(True)
        try:
            for item in list(scene.items()):
                bucket = _sel_filter_for_item(item)
                if bucket not in _sel_filter_keys or getattr(item, 'model', None) is None:
                    continue
                if _sel_item_enabled(item, enabled):
                    item.setSelected(rect.intersects(_sel_item_rect(item)))
                else:
                    item.setSelected(False)
        finally:
            try:
                scene.blockSignals(False)
            except Exception:
                pass
        try:
            view.window.schedule_property_refresh()
        except Exception:
            pass
        try:
            view.viewport().update()
        except Exception:
            pass
        return True
    except Exception:
        return False


def _sel_stop(view):
    try:
        view._selection_autoscroll_active = False
        view._selection_anchor_scene = None
        view._selection_last_pos = None
        timer = getattr(view, '_selection_autoscroll_timer', None)
        if timer is not None and timer.isActive():
            timer.stop()
    except Exception:
        pass


def _sel_edge_scroll(view, viewport_pos=None):
    try:
        if not getattr(view, '_selection_autoscroll_active', False):
            return False
        try:
            if not (_sel_app.mouseButtons() & _sel_qt.LeftButton):
                _sel_stop(view)
                return False
        except Exception:
            pass
        if viewport_pos is None:
            viewport_pos = getattr(view, '_selection_last_pos', None)
        if viewport_pos is None:
            viewport_pos = view.viewport().mapFromGlobal(_sel_cursor.pos())
        view._selection_last_pos = viewport_pos
        vp = view.viewport().rect()
        edge = 48
        max_step = 24
        dx = dy = 0
        if viewport_pos.x() < vp.left() + edge:
            dx = -max(1, int((vp.left() + edge - viewport_pos.x()) / edge * max_step))
        elif viewport_pos.x() > vp.right() - edge:
            dx = max(1, int((viewport_pos.x() - (vp.right() - edge)) / edge * max_step))
        if viewport_pos.y() < vp.top() + edge:
            dy = -max(1, int((vp.top() + edge - viewport_pos.y()) / edge * max_step))
        elif viewport_pos.y() > vp.bottom() - edge:
            dy = max(1, int((viewport_pos.y() - (vp.bottom() - edge)) / edge * max_step))
        changed = False
        if dx:
            bar = view.horizontalScrollBar(); old = bar.value(); bar.setValue(old + dx); changed = changed or bar.value() != old
        if dy:
            bar = view.verticalScrollBar(); old = bar.value(); bar.setValue(old + dy); changed = changed or bar.value() != old
        if changed:
            _sel_apply_rubber_selection(view, viewport_pos)
            try:
                view.scene().invalidate(view.mapToScene(view.viewport().rect()).boundingRect())
            except Exception:
                pass
        return changed
    except Exception:
        return False


def _sel_timer_for(view):
    timer = getattr(view, '_selection_autoscroll_timer', None)
    if timer is None:
        try:
            timer = _sel_timer(view)
            timer.setInterval(30)
            timer.timeout.connect(lambda v=view: _sel_edge_scroll(v))
            view._selection_autoscroll_timer = timer
        except Exception:
            timer = None
    return timer


def _sel_start_allowed(view, event, pos):
    try:
        if event.button() != _sel_qt.LeftButton:
            return False
        if getattr(view.window, 'draw_tool', None) != _sel_drawtool.SELECT.value:
            return False
        item = view.itemAt(pos)
        if item is None:
            return True
        try:
            return not bool(item.flags() & _sel_gitem.ItemIsSelectable)
        except Exception:
            return False
    except Exception:
        return False


try:
    _sel_prev_init = SymbolView.__init__
    _sel_prev_press = SymbolView.mousePressEvent
    _sel_prev_move = SymbolView.mouseMoveEvent
    _sel_prev_release = SymbolView.mouseReleaseEvent
    _sel_prev_rubber = SymbolView._rubber_band_changed

    def _sel_init(self, scene, window):
        _sel_prev_init(self, scene, window)
        self._selection_autoscroll_active = False
        self._selection_anchor_scene = None
        self._selection_last_pos = None
        timer = _sel_timer_for(self)
        if timer is not None:
            timer.stop()

    def _sel_press(self, event):
        start = False
        pos = None
        try:
            pos = _sel_event_pos(event)
            start = _sel_start_allowed(self, event, pos)
        except Exception:
            start = False
        result = _sel_prev_press(self, event)
        try:
            if start and not getattr(self, '_compat_0098', False) and not getattr(self, '_compat_0859', None):
                self._selection_autoscroll_active = True
                self._selection_anchor_scene = self.mapToScene(pos)
                self._selection_last_pos = pos
                timer = _sel_timer_for(self)
                if timer is not None and not timer.isActive():
                    timer.start()
            else:
                _sel_stop(self)
        except Exception:
            pass
        return result

    def _sel_move(self, event):
        try:
            if getattr(self, '_selection_autoscroll_active', False):
                self._selection_last_pos = _sel_event_pos(event)
        except Exception:
            pass
        result = _sel_prev_move(self, event)
        try:
            if getattr(self, '_selection_autoscroll_active', False):
                _sel_edge_scroll(self, getattr(self, '_selection_last_pos', None))
                _sel_apply_rubber_selection(self, getattr(self, '_selection_last_pos', None))
        except Exception:
            pass
        return result

    def _sel_release(self, event):
        try:
            if getattr(self, '_selection_autoscroll_active', False):
                self._selection_last_pos = _sel_event_pos(event)
                _sel_apply_rubber_selection(self, self._selection_last_pos)
        except Exception:
            pass
        _sel_stop(self)
        return _sel_prev_release(self, event)

    def _sel_rubber_band_changed(self, viewport_rect, from_scene, to_scene):
        try:
            if not viewport_rect.isNull():
                return _sel_prev_rubber(self, viewport_rect, from_scene, to_scene)
            rect = _sel_rect(from_scene, to_scene).normalized()
            if not rect.isValid() or rect.width() <= 1 or rect.height() <= 1:
                return
            scene = self.scene()
            enabled = getattr(self.window, 'selection_enabled', {}) or {}
            scene.blockSignals(True)
            try:
                for item in list(scene.items()):
                    bucket = _sel_filter_for_item(item)
                    if bucket not in _sel_filter_keys or getattr(item, 'model', None) is None:
                        continue
                    if _sel_item_enabled(item, enabled):
                        item.setSelected(rect.intersects(_sel_item_rect(item)))
                    else:
                        item.setSelected(False)
            finally:
                try:
                    scene.blockSignals(False)
                except Exception:
                    pass
            try:
                self.window.schedule_property_refresh()
            except Exception:
                pass
            self.viewport().update()
        except Exception:
            try:
                return _sel_prev_rubber(self, viewport_rect, from_scene, to_scene)
            except Exception:
                pass

    SymbolView.__init__ = _sel_init
    SymbolView.mousePressEvent = _sel_press
    SymbolView.mouseMoveEvent = _sel_move
    SymbolView.mouseReleaseEvent = _sel_release
    SymbolView._rubber_band_changed = _sel_rubber_band_changed
except Exception:
    pass
