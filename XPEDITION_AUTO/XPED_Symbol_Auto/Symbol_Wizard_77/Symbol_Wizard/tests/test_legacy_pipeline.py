from __future__ import annotations

from collections import Counter

from symbol_wizard.gui.legacy_pipeline.targets import CANONICAL_PATCH_TARGETS
from symbol_wizard.gui.legacy_updates import apply_legacy_updates


class _MainWindowStub:
    def __init__(self) -> None:
        pass

    def rebuild_scene(self) -> None:
        pass

    def refresh_properties(self) -> None:
        if getattr(self, "is_template_editor", False):
            raise AssertionError("Template editor must not use MainWindow.refresh_properties fallback")

    def scale_selected_grid(self) -> None:
        pass

    def scale_selected(self) -> None:
        pass

    def rotate_selected(self) -> None:
        pass

    def flip_selected_horizontal(self) -> None:
        pass

    def flip_selected_vertical(self) -> None:
        pass

    def group_selected_graphics(self) -> None:
        pass

    def ungroup_selected_graphics(self) -> None:
        pass

    def on_scene_selection_changed(self) -> None:
        pass


class _TemplateEditorDialogStub(_MainWindowStub):
    def __init__(self, parent) -> None:
        self.parent = parent
        self.is_template_editor = True

    def refresh_properties(self) -> None:
        self.template_base_refresh_called = True



class _GraphicItemStub:
    def mousePressEvent(self, *args, **kwargs) -> None:  # noqa: N802 - Qt naming
        pass


class _TextItemStub:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def mousePressEvent(self, *args, **kwargs) -> None:  # noqa: N802 - Qt naming
        pass


def test_structured_legacy_pipeline_applies_all_canonical_targets() -> None:
    globals_dict = {
        "MainWindow": _MainWindowStub,
        "TemplateEditorDialog": _TemplateEditorDialogStub,
        "GraphicItem": _GraphicItemStub,
        "TextItem": _TextItemStub,
    }

    applied = apply_legacy_updates(globals_dict)
    expected = Counter(class_name for class_name, _ in CANONICAL_PATCH_TARGETS)

    assert {name: len(attrs) for name, attrs in applied.items()} == dict(expected)
    assert len(CANONICAL_PATCH_TARGETS) == 158


def test_main_window_init_chain_does_not_call_template_editor_init() -> None:
    globals_dict = {
        "MainWindow": _MainWindowStub,
        "TemplateEditorDialog": _TemplateEditorDialogStub,
        "GraphicItem": _GraphicItemStub,
        "TextItem": _TextItemStub,
    }

    apply_legacy_updates(globals_dict)

    # Regression test for the structured pipeline: loop-body assignments from
    # the original patch stream must not be replayed a second time with the
    # TemplateEditorDialog __init__ closure and then copied onto MainWindow.
    _MainWindowStub()



def test_template_editor_refresh_fallback_uses_template_base_renderer() -> None:
    class MainForFallback:
        def refresh_properties(self) -> None:
            if getattr(self, "is_template_editor", False):
                raise AssertionError("Template editor must not use MainWindow.refresh_properties fallback")

    class TemplateForFallback(MainForFallback):
        def refresh_properties(self) -> None:
            self.template_base_refresh_called = True

    globals_dict = {
        "MainWindow": MainForFallback,
        "TemplateEditorDialog": TemplateForFallback,
        "GraphicItem": _GraphicItemStub,
        "TextItem": _TextItemStub,
    }

    apply_legacy_updates(globals_dict)

    dialog = object.__new__(TemplateForFallback)
    dialog.is_template_editor = True
    globals_dict["_compat_0413"](dialog)

    assert getattr(dialog, "template_base_refresh_called", False) is True


def test_template_editor_property_refresh_scheduler_uses_final_refresh() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    body_transform = root / "symbol_wizard" / "gui" / "legacy_pipeline" / "functions" / "body_transform.py"
    source = body_transform.read_text(encoding="utf-8")

    needle = (
        "if getattr(self, 'is_template_editor', False):\n"
        "                        self.refresh_properties()"
    )
    assert needle in source
    assert "try: _compat_0413(self)" not in source

def test_legacy_pipeline_is_shadow_only_and_domain_split() -> None:
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    pipeline_path = root / "symbol_wizard" / "gui" / "legacy_pipeline" / "pipeline.py"
    functions_dir = root / "symbol_wizard" / "gui" / "legacy_pipeline" / "functions"
    pipeline_tree = ast.parse(pipeline_path.read_text(encoding="utf-8"))
    patched_classes = {"MainWindow", "TemplateEditorDialog", "GraphicItem", "TextItem"}

    direct_assignments = []
    for node in ast.walk(pipeline_tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    if target.value.id in patched_classes:
                        direct_assignments.append((target.value.id, target.attr, node.lineno))

    assert direct_assignments == []
    assert functions_dir.is_dir()
    assert not (root / "symbol_wizard" / "gui" / "legacy_updates_active_code.py").exists()
    assert not (root / "symbol_wizard" / "gui" / "legacy_pipeline" / "definitions.py").exists()


def test_graphics_items_core_file_has_no_direct_item_monkey_patches() -> None:
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    items_path = root / "symbol_wizard" / "graphics" / "items.py"
    tree = ast.parse(items_path.read_text(encoding="utf-8"))
    patched_classes = {"TransformMixin", "BodyItem", "PinItem", "TextItem", "GraphicItem"}
    direct_assignments = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    if target.value.id in patched_classes:
                        direct_assignments.append((target.value.id, target.attr, node.lineno))

    assert direct_assignments == []
    assert (root / "symbol_wizard" / "graphics" / "item_updates.py").exists()
    assert (root / "symbol_wizard" / "graphics" / "item_update_code.py").exists()


def test_graphics_scene_and_view_core_files_have_no_direct_class_monkey_patches() -> None:
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    checks = [
        (root / "symbol_wizard" / "graphics" / "scene.py", {"SymbolScene"}),
        (root / "symbol_wizard" / "graphics" / "view.py", {"SymbolView"}),
    ]
    for path, patched_classes in checks:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        direct_assignments = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                        if target.value.id in patched_classes:
                            direct_assignments.append((target.value.id, target.attr, node.lineno))
        assert direct_assignments == []

    assert not (root / "symbol_wizard" / "graphics" / "scene_updates.py").exists()
    assert not (root / "symbol_wizard" / "graphics" / "scene_update_code.py").exists()
    assert (root / "symbol_wizard" / "graphics" / "view_updates.py").exists()


def test_item_update_code_does_not_patch_symbol_view_directly() -> None:
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    path = root / "symbol_wizard" / "graphics" / "item_update_code.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    direct_symbol_view_assignments = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    if target.value.id in {"SymbolView", "_LH124_SymbolView"}:
                        direct_symbol_view_assignments.append((target.value.id, target.attr, node.lineno))

    assert direct_symbol_view_assignments == []


def test_canonical_runtime_targets_do_not_expose_patch_names() -> None:
    for class_name, attr_name in CANONICAL_PATCH_TARGETS:
        assert not attr_name.startswith(("_lh", "_sw", "_v")), (class_name, attr_name)


def test_template_editor_property_panel_refresh_uses_safe_clear_and_empty_repair() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    template_editor = root / "symbol_wizard" / "gui" / "legacy_pipeline" / "functions" / "template_editor.py"
    dialogs = root / "symbol_wizard" / "gui" / "_main_window_dialogs.py"
    source = template_editor.read_text(encoding="utf-8")
    dialog_source = dialogs.read_text(encoding="utf-8")

    assert "def _template_editor_clear_form_safely" in source
    assert "_template_editor_render_empty_panel_if_needed(self)" in source
    assert "_template_property_refresh_active" in source
    assert "self.clear_properties()" in dialog_source

    # All form clearing in the active template-editor compatibility layer should
    # go through the safe clear helper so stale spinbox/combo callbacks cannot
    # recursively clear the panel while it is being rebuilt.
    remaining_remove_rows = [
        line for line in source.splitlines()
        if "removeRow(0)" in line and "form.removeRow(0)" not in line.strip().split("#", 1)[0]
    ]
    assert remaining_remove_rows == []


def test_split_part_navigation_is_native_and_robust_for_legacy_split_flags() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    main_window = (root / "symbol_wizard" / "gui" / "main_window.py").read_text(encoding="utf-8")
    properties = (root / "symbol_wizard" / "gui" / "legacy_pipeline" / "functions" / "properties_style.py").read_text(encoding="utf-8")
    ui_actions = (root / "symbol_wizard" / "gui" / "legacy_pipeline" / "functions" / "ui_actions.py").read_text(encoding="utf-8")

    assert "def build_active_navigation_toolbar" in main_window
    assert "def step_active_split_part" in main_window
    assert "def is_split_symbol_model" in main_window
    assert "or len(units) > 1" in main_window
    assert "or len(units) > 1" in properties
    assert "build_active_navigation_toolbar" in ui_actions
    assert "self.addToolBar('Active Split Part')" not in ui_actions


def test_active_split_part_navigation_is_native_not_duplicate_legacy_toolbar() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    main_window = (root / "symbol_wizard" / "gui" / "main_window.py").read_text(encoding="utf-8")
    ui_actions = (root / "symbol_wizard" / "gui" / "legacy_pipeline" / "functions" / "ui_actions.py").read_text(encoding="utf-8")

    assert "def build_active_navigation_toolbar" in main_window
    assert "def step_active_split_part" in main_window
    assert "active_split_part_combo.currentIndexChanged.connect(self.set_active_split_part_from_combo_index)" in main_window
    assert "build_active_navigation_toolbar" in ui_actions
    assert "addToolBar('Active Symbol')" not in ui_actions
    assert "addToolBar('Active Split Part')" not in ui_actions


def test_split_predicate_accepts_legacy_inconsistent_split_models() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "symbol_wizard" / "gui" / "legacy_pipeline" / "functions" / "properties_style.py").read_text(encoding="utf-8")

    assert "is_split_symbol_model" in source
    assert "or bool(getattr(self.symbol, 'is_split', False))" in source
    assert "or len(units) > 1" in source


def test_multi_pin_edit_uses_model_refs_not_deleted_qgraphics_items() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    main_window = (root / "symbol_wizard" / "gui" / "main_window.py").read_text(encoding="utf-8")
    pin_grid = (root / "symbol_wizard" / "gui" / "legacy_pipeline" / "functions" / "pin_grid.py").read_text(encoding="utf-8")
    template_editor = (root / "symbol_wizard" / "gui" / "legacy_pipeline" / "functions" / "template_editor.py").read_text(encoding="utf-8")

    assert "def _pin_model_from_object" in main_window
    assert "def _pin_models_from_objects" in main_window
    assert "RuntimeError" in main_window
    assert "models=tuple(pin_models)" in main_window
    assert "pin_items = tuple(self._pin_models_from_objects" in pin_grid
    assert "def _compat_pin_models_from_objects" in template_editor
    assert "tuple(pins), attr, value" in template_editor


def test_enter_commits_property_editors_and_body_drag_has_undo_safeguard() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    dialogs = (root / "symbol_wizard" / "gui" / "_main_window_dialogs.py").read_text(encoding="utf-8")
    main_window = (root / "symbol_wizard" / "gui" / "main_window.py").read_text(encoding="utf-8")
    item_updates = (root / "symbol_wizard" / "graphics" / "item_update_code.py").read_text(encoding="utf-8")
    body_transform = (root / "symbol_wizard" / "gui" / "legacy_pipeline" / "functions" / "body_transform.py").read_text(encoding="utf-8")

    assert "Return /\n    Enter finish property editing" in dialogs
    assert "QTimer.singleShot(0, obj.clearFocus)" in dialogs
    assert "def _commit_line_edit" in main_window
    assert "editor.clearFocus()" in main_window
    assert "_canonical_body_mouse_press_with_undo" in item_updates
    assert "win.push_undo_state()" in item_updates
    assert "self.view.setFocus(Qt.OtherFocusReason)" in body_transform


def test_flip_operations_keep_text_readable_and_move_only_anchors() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    items = (root / "symbol_wizard" / "graphics" / "items.py").read_text(encoding="utf-8")
    body_transform = (root / "symbol_wizard" / "gui" / "legacy_pipeline" / "functions" / "body_transform.py").read_text(encoding="utf-8")
    pipeline = (root / "symbol_wizard" / "gui" / "legacy_pipeline" / "pipeline.py").read_text(encoding="utf-8")

    assert "Text is never mirrored" in items
    assert "sx, sy, rot = abs(f('scale_x', 1.0)), abs(f('scale_y', 1.0))" in items
    assert "Negative\n                # scale values are a mirror transform" in items
    assert "model.scale_x = -before_x" not in body_transform
    assert "model.scale_y = -before_y" not in body_transform
    assert "_canonical_flip_with_text_anchor_only" in body_transform
    assert "_canonical_flip_with_text_anchor_only" in pipeline


def test_split_pin_manager_bulk_edit_can_change_pin_type() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    dialogs = (root / "symbol_wizard" / "gui" / "_main_window_dialogs.py").read_text(encoding="utf-8")

    assert "self.pin_type_edit_combo.addItems(['Unchanged'] + [x.value for x in PinType])" in dialogs
    assert "function_row.addWidget(QLabel('Pin Type'))" in dialogs
    assert "def _pin_type_edit_value" in dialogs
    assert "def _sync_pin_type_metadata" in dialogs
    assert "pin.attributes['PINTYPE'] = ptype" in dialogs
    assert "pin.pin_type = pin_type_value" in dialogs
    assert "if not values and not function_change and not pin_type_change" in dialogs


def test_selection_filter_distinguishes_plain_text_from_attributes() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    helper = (root / "symbol_wizard" / "gui" / "selection_filter.py").read_text(encoding="utf-8")
    main_window = (root / "symbol_wizard" / "gui" / "main_window.py").read_text(encoding="utf-8")
    dialogs = (root / "symbol_wizard" / "gui" / "_main_window_dialogs.py").read_text(encoding="utf-8")
    view_updates = (root / "symbol_wizard" / "graphics" / "view_update_code.py").read_text(encoding="utf-8")
    selection_grouping = (root / "symbol_wizard" / "gui" / "legacy_pipeline" / "functions" / "selection_grouping.py").read_text(encoding="utf-8")
    template_editor = (root / "symbol_wizard" / "gui" / "legacy_pipeline" / "functions" / "template_editor.py").read_text(encoding="utf-8")

    assert "'ATTRIBUTES'" in helper
    assert "selection_filter_kind" in main_window
    assert "SELECTION_MODE_ITEMS" in main_window
    assert "selection_filter_kind" in dialogs
    assert "SELECTION_MODE_ITEMS" in dialogs
    assert "Selection filter v2: plain text / attributes" in view_updates
    assert "selection_filter_kind_for_item(item)" in selection_grouping
    assert "return selection_filter_kind(kind)" in template_editor


def test_canvas_selection_autoscroll_is_installed_in_final_view_pipeline() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    view_updates = (root / "symbol_wizard" / "graphics" / "view_update_code.py").read_text(encoding="utf-8")

    assert "canvas auto-scroll while rubber-band selecting" in view_updates
    assert "_selection_autoscroll_timer" in view_updates
    assert "def _sel_edge_scroll" in view_updates
    assert "SymbolView.mouseMoveEvent = _sel_move" in view_updates
    assert "SymbolView.mouseReleaseEvent = _sel_release" in view_updates


def test_none_template_available_for_single_and_split_creation() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "symbol_wizard" / "gui" / "main_window.py").read_text(encoding="utf-8")

    assert "keys.append('<NONE>')" in source
    assert "return [self._blank_template_unit('SplitPart_1'), self._blank_template_unit('SplitPart_2')]" in source
    assert "self.symbol.units.append(self._blank_template_unit(name))" in source

