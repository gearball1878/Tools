"""Toolbar, menu, ribbon and initialization helpers.

Executed in the shared ``main_window.py`` global namespace by ``legacy_updates.apply_legacy_updates``.
"""

from __future__ import annotations

def _compat_0451(self):
    _compat_0443(self)
    try:
        tb = self.addToolBar('Graphic Group')
        b = QPushButton('Group Graphics'); b.clicked.connect(self.group_selected_graphics); tb.addWidget(b)
        b = QPushButton('Ungroup'); b.clicked.connect(self.ungroup_selected_graphics); tb.addWidget(b)
    except Exception:
        pass

def _compat_0467(self):
    _compat_0469(self)
    _compat_0452(self)

def _compat_0486(self):
    if getattr(self, '_compat_0485', False):
        return
    self._compat_0485 = True
    try:
        edit_menu = None
        for act in self.menuBar().actions():
            if str(act.text()).replace('&', '').lower() == 'edit':
                edit_menu = act.menu()
                break
        if edit_menu is None:
            edit_menu = self.menuBar().addMenu('&Edit')
        edit_menu.addSeparator()
        a_group = QAction('Group Graphics', self)
        a_group.setShortcut(QKeySequence('Ctrl+G'))
        a_group.triggered.connect(self.group_selected_graphics)
        edit_menu.addAction(a_group)
        self.addAction(a_group)
        a_ungroup = QAction('Ungroup Graphics', self)
        a_ungroup.setShortcut(QKeySequence('Ctrl+Shift+G'))
        a_ungroup.triggered.connect(self.ungroup_selected_graphics)
        edit_menu.addAction(a_ungroup)
        self.addAction(a_ungroup)
    except Exception:
        pass
    try:
        tb = self.addToolBar('Graphic Group')
        btn = QPushButton('Group Graphics')
        btn.setToolTip('Ausgewählte Grafikobjekte gruppieren (Ctrl+G)')
        btn.clicked.connect(self.group_selected_graphics)
        tb.addWidget(btn)
        btn = QPushButton('Ungroup')
        btn.setToolTip('Grafikgruppe aufheben (Ctrl+Shift+G)')
        btn.clicked.connect(self.ungroup_selected_graphics)
        tb.addWidget(btn)
    except Exception:
        pass

def _compat_0511(self):
    if getattr(self, '_compat_0510', False):
        return
    self._compat_0510 = True
    try:
        edit_menu = None
        for act in self.menuBar().actions():
            if str(act.text()).replace('&', '').lower() == 'edit':
                edit_menu = act.menu()
                break
        if edit_menu is None:
            edit_menu = self.menuBar().addMenu('&Edit')
        edit_menu.addSeparator()
        a_group = QAction('Group Graphics', self)
        a_group.setShortcut(QKeySequence('Ctrl+G'))
        a_group.triggered.connect(self.group_selected_graphics)
        edit_menu.addAction(a_group)
        self.addAction(a_group)
        a_ungroup = QAction('Ungroup Graphics', self)
        a_ungroup.setShortcut(QKeySequence('Ctrl+Shift+G'))
        a_ungroup.triggered.connect(self.ungroup_selected_graphics)
        edit_menu.addAction(a_ungroup)
        self.addAction(a_ungroup)
    except Exception:
        pass
    try:
        tb = self.addToolBar('Graphic Group')
        btn = QPushButton('Group Graphics')
        btn.setToolTip('Ausgewählte eingefügte Grafikobjekte gruppieren (Ctrl+G)')
        btn.clicked.connect(self.group_selected_graphics)
        tb.addWidget(btn)
        btn = QPushButton('Ungroup Graphics')
        btn.setToolTip('Grafikgruppe aufheben (Ctrl+Shift+G)')
        btn.clicked.connect(self.ungroup_selected_graphics)
        tb.addWidget(btn)
    except Exception:
        pass

def _compat_0573(self):
    if getattr(self, '_compat_0571', False):
        return
    self._compat_0571 = True
    _compat_0585(self)
    try:
        tb = self.addToolBar('Graphic Group')
        btn = QPushButton('Group Graphics')
        btn.setToolTip('Ausgewählte Grafikobjekte gruppieren (Ctrl+G)')
        btn.clicked.connect(self.group_selected_graphics)
        tb.addWidget(btn)
        btn = QPushButton('Ungroup Graphics')
        btn.setToolTip('Grafikgruppe aufheben (Ctrl+Shift+G)')
        btn.clicked.connect(self.ungroup_selected_graphics)
        tb.addWidget(btn)
    except Exception:
        pass

def _compat_0212(self):
    _compat_0208(self)
    try:
        if hasattr(self, 'build_active_navigation_toolbar'):
            self.build_active_navigation_toolbar()
    except Exception:
        pass

def _compat_0247(self):
    _compat_0242(self)
    try:
        if hasattr(self, 'build_active_navigation_toolbar'):
            self.build_active_navigation_toolbar()
    except Exception:
        pass

def _compat_1154(self):
    """Remove the temporary Info button from the top Draw Tools ribbon."""
    try:
        for tb in self.findChildren(QToolBar):
            try:
                if str(tb.windowTitle() or '') != 'Draw Tools':
                    continue
                for act in list(tb.actions()):
                    w = tb.widgetForAction(act)
                    text = ''
                    try:
                        text = str(w.text()) if w is not None and hasattr(w, 'text') else str(act.text() or '')
                    except Exception:
                        text = str(act.text() or '')
                    if text.strip() == 'Info':
                        tb.removeAction(act)
                        try:
                            if w is not None:
                                w.deleteLater()
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass

def _compat_1149(self, *args, **kwargs):
    if _compat_1152 is not None:
        _compat_1152(self, *args, **kwargs)
    try:
        _compat_1154(self)
    except Exception:
        pass

def _compat_0773(self, *args, **kwargs):
    result = _compat_0772(self, *args, **kwargs) if _compat_0772 is not None else None
    _compat_0771(self)
    return result

def _compat_1202(self, *a, **kw):
    _compat_1204(self, *a, **kw)
    try: _compat_1212(self)
    except Exception: pass
    try:
        tb = self.addToolBar('Graphic Group')
        b = QPushButton('Group Graphics'); b.clicked.connect(self.group_selected_graphics); tb.addWidget(b)
        b = QPushButton('Ungroup Graphics'); b.clicked.connect(self.ungroup_selected_graphics); tb.addWidget(b)
    except Exception: pass

def _compat_1217(self, *a, **kw):
    _compat_1218(self, *a, **kw)
    try: _compat_1219(self)
    except Exception: pass

def _compat_1220(self, *a, **kw):
    _compat_1221(self, *a, **kw)
    try: _compat_1222(self)
    except Exception: pass

def _compat_1225(self, *args, **kwargs):
    _compat_1226(self, *args, **kwargs)
    try:
        _compat_1227(self)
    except Exception:
        pass
