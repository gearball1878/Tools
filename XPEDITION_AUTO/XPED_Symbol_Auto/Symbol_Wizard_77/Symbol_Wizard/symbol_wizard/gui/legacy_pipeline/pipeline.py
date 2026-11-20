"""Shadow-class composition pipeline for active legacy functions.

This file is executed after ``legacy_pipeline/functions/*.py`` with temporary shadow classes
named ``MainWindow``, ``TemplateEditorDialog``, ``GraphicItem`` and
``TextItem``.  Direct runtime patching is isolated in the shadow layer;
``legacy_updates.py`` later copies only canonical targets to the real classes.
"""

from __future__ import annotations

_legacy_assign(MainWindow, 'dock_pins_to_body', _compat_1234)  # original patch line 412

_legacy_assign(MainWindow, '_body_group_capture_base', _compat_1233)  # original patch line 413

_legacy_assign(MainWindow, '_body_group_state', _compat_1232)  # original patch line 414

_legacy_assign(MainWindow, '_transform_unit_as_body_group', _compat_1240)  # original patch line 416

_legacy_assign_expr(MainWindow, 'rebuild_scene', lambda: _compat_1237(MainWindow.rebuild_scene))  # original patch line 419

_legacy_assign_expr(TemplateEditorDialog, 'rebuild_scene', lambda: _compat_1237(TemplateEditorDialog.rebuild_scene))  # original patch line 420

# original block lines 436-439
try:
    _compat_0052 = [x.value for x in OriginMode]
except Exception:
    _compat_0052 = ['center', 'bottom_left', 'bottom_right', 'top_left', 'top_right']

_legacy_assign(MainWindow, '_sync_imported_body_model_to_body_graphics', _compat_0334)  # original patch line 943

_legacy_assign(TemplateEditorDialog, '_sync_imported_body_model_to_body_graphics', _compat_0334)  # original patch line 943

_legacy_assign(MainWindow, '_body_graphics_bounds', _compat_0310)  # original patch line 944

_legacy_assign(TemplateEditorDialog, '_body_graphics_bounds', _compat_0310)  # original patch line 944

_legacy_assign(MainWindow, '_body_graphics', _compat_0309)  # original patch line 945

_legacy_assign(TemplateEditorDialog, '_body_graphics', _compat_0309)  # original patch line 945

_legacy_assign(MainWindow, 'shift_unit_geometry', _compat_0330)  # original patch line 946

_legacy_assign(TemplateEditorDialog, 'shift_unit_geometry', _compat_0330)  # original patch line 946

_legacy_assign(MainWindow, 'normalize_unit_origin', _compat_0324)  # original patch line 947

_legacy_assign(TemplateEditorDialog, 'normalize_unit_origin', _compat_0324)  # original patch line 947

_legacy_assign(MainWindow, 'normalize_symbol_origins_for_import', _compat_0323)  # original patch line 948

_legacy_assign(TemplateEditorDialog, 'normalize_symbol_origins_for_import', _compat_0323)  # original patch line 948

_legacy_assign(MainWindow, '_invalidate_body_group_transform_cache', _compat_0318)  # original patch line 949

_legacy_assign(TemplateEditorDialog, '_invalidate_body_group_transform_cache', _compat_0318)  # original patch line 949

_legacy_assign(MainWindow, '_body_group_capture_base', _compat_0313)  # original patch line 951

_legacy_assign(MainWindow, '_body_group_state', _compat_0311)  # original patch line 952

_legacy_assign(MainWindow, '_apply_body_group_matrix_from_base', _compat_0307)  # original patch line 953

_legacy_assign(TemplateEditorDialog, '_apply_body_group_matrix_from_base', _compat_0307)  # original patch line 953

_legacy_assign(MainWindow, '_transform_unit_as_body_group', _compat_0335)  # original patch line 954

_legacy_assign(MainWindow, 'reset_origin_to_selected_anchor', _compat_0326)  # original patch line 955

_legacy_assign(TemplateEditorDialog, 'reset_origin_to_selected_anchor', _compat_0326)  # original patch line 955

_legacy_assign(TemplateEditorDialog, 'set_body_visual_attr', _compat_0328)  # original patch line 956

_legacy_assign(MainWindow, 'color_body_model', _compat_0315)  # original patch line 957

_legacy_assign(TemplateEditorDialog, 'color_body_model', _compat_0315)  # original patch line 957

_legacy_assign(TemplateEditorDialog, 'load_selected_template', _compat_0320)  # original patch line 958

_legacy_assign_expr(MainWindow, 'rebuild_scene', lambda: _compat_0325(MainWindow.rebuild_scene))  # original patch line 959

_legacy_assign_expr(TemplateEditorDialog, 'rebuild_scene', lambda: _compat_0325(TemplateEditorDialog.rebuild_scene))  # original patch line 960

_legacy_assign(MainWindow, '_capture_selection_ids', _compat_0336)  # original patch line 991

_legacy_assign(MainWindow, '_unit_has_imported_body_artwork', _compat_0405)  # original patch line 1139

_legacy_assign(TemplateEditorDialog, '_unit_has_imported_body_artwork', _compat_0405)  # original patch line 1139

_legacy_assign(MainWindow, '_prepare_graphics_as_body', _compat_0400)  # original patch line 1140

_legacy_assign(TemplateEditorDialog, '_prepare_graphics_as_body', _compat_0400)  # original patch line 1140

_legacy_assign(MainWindow, 'rotate_selected', _compat_0402)  # original patch line 1142

_legacy_assign(MainWindow, 'flip_selected_horizontal', _compat_0398)  # original patch line 1143

_legacy_assign(MainWindow, 'flip_selected_vertical', _compat_0399)  # original patch line 1144

_legacy_assign(MainWindow, 'scale_selected', _compat_0403)  # original patch line 1145

_legacy_assign_expr(MainWindow, 'rebuild_scene', lambda: _compat_0401(MainWindow.rebuild_scene))  # original patch line 1146

_legacy_assign_expr(TemplateEditorDialog, 'rebuild_scene', lambda: _compat_0401(TemplateEditorDialog.rebuild_scene))  # original patch line 1147

_legacy_assign(MainWindow, '_transform_unit_as_body_group', _compat_0559)  # original patch line 1425

_legacy_assign(MainWindow, '_normalize_unit_body_anchor_to_symbol_origin', _compat_0553)  # original patch line 1426

_legacy_assign(TemplateEditorDialog, '_normalize_unit_body_anchor_to_symbol_origin', _compat_0553)  # original patch line 1426

_legacy_assign(MainWindow, '_transform_unit_as_body_group', _compat_0645)  # original patch line 1685

_legacy_assign(MainWindow, 'rotate_selected', _compat_0685)  # original patch line 1780

_legacy_assign(MainWindow, 'flip_selected_horizontal', _compat_0683)  # original patch line 1781

_legacy_assign(MainWindow, 'flip_selected_vertical', _compat_0684)  # original patch line 1782

_legacy_assign(MainWindow, 'scale_selected', _compat_0686)  # original patch line 1783

_legacy_assign(MainWindow, 'flip_selected_horizontal', _compat_0708)  # original patch line 1858

_legacy_assign(MainWindow, 'flip_selected_vertical', _compat_0709)  # original patch line 1859

_compat_0715 = _legacy_capture(MainWindow, 'apply_item_selectability')  # original capture line 1920

_compat_0714 = _legacy_capture(MainWindow, '_apply_selection_filter_to_scene')  # original capture line 1949

_compat_0716 = _legacy_capture(MainWindow, 'refresh_properties')  # original capture line 2007

_legacy_assign(MainWindow, 'apply_item_selectability', _compat_0710)  # original patch line 2053

_legacy_assign(MainWindow, '_apply_selection_filter_to_scene', _compat_0711)  # original patch line 2054

_legacy_assign(MainWindow, 'refresh_properties', _compat_0717)  # original patch line 2056

_compat_0076 = _legacy_capture(MainWindow, '_transform_unit_as_body_group')  # original capture line 2285

_compat_0075 = _legacy_capture(GraphicItem, 'mousePressEvent')  # original capture line 2309

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_0080)  # original patch line 2338

_legacy_assign(MainWindow, '_transform_unit_as_body_group', _compat_0083)  # original patch line 2339



_legacy_assign(GraphicItem, 'mousePressEvent', _compat_0072)  # original patch line 2342

_compat_0991 = _legacy_capture(MainWindow, '_transform_unit_as_body_group')  # original capture line 2654

_compat_0990 = _legacy_capture(MainWindow, 'scale_selected_grid')  # original capture line 2673

_legacy_assign(MainWindow, '_transform_unit_as_body_group', _compat_1001)  # original patch line 2792

_legacy_assign(MainWindow, 'scale_selected_grid', _compat_0997)  # original patch line 2793

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_0995)  # original patch line 2794

_legacy_assign(MainWindow, 'apply_line_defaults', _compat_0981)  # original patch line 2795

_legacy_assign(MainWindow, 'set_body_visual_attr', _compat_0998)  # original patch line 2796

_legacy_assign(MainWindow, 'apply_color_to_selected', _compat_0980)  # original patch line 2797

_compat_0347 = _legacy_capture(MainWindow, '_transform_unit_as_body_group')  # original capture line 3084

_compat_0346 = _legacy_capture(MainWindow, 'scale_selected_grid')  # original capture line 3088

_legacy_assign_expr(MainWindow, '_body_owned_graphics', lambda: lambda self, body=None: _compat_0338(self, self.current_unit))  # original patch line 3093

_legacy_assign_expr(TemplateEditorDialog, '_body_owned_graphics', lambda: lambda self, body=None: _compat_0338(self, self.current_unit))  # original patch line 3093

_legacy_assign(MainWindow, '_transform_unit_as_body_group', _compat_0356)  # original patch line 3096

_legacy_assign(MainWindow, 'scale_selected_grid', _compat_0353)  # original patch line 3097

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_0352)  # original patch line 3098

_legacy_assign(MainWindow, 'clear_canvas', _compat_0341)  # original patch line 3099

_legacy_assign(TemplateEditorDialog, 'clear_canvas', _compat_0341)  # original patch line 3099

_legacy_assign(MainWindow, '_transform_unit_as_body_group', _compat_0365)  # original patch line 3326

_legacy_assign(MainWindow, 'scale_selected_grid', _compat_0363)  # original patch line 3327

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_0362)  # original patch line 3328

_legacy_assign(MainWindow, '_transform_unit_as_body_group', _compat_0373)  # original patch line 3550

_legacy_assign(MainWindow, 'scale_selected_grid', _compat_0370)  # original patch line 3551

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_0369)  # original patch line 3552

_compat_0378 = _legacy_capture(MainWindow, 'rotate_selected')  # original capture line 3691

_compat_0376 = _legacy_capture(MainWindow, 'flip_selected_horizontal')  # original capture line 3692

_compat_0377 = _legacy_capture(MainWindow, 'flip_selected_vertical')  # original capture line 3693

_legacy_assign(MainWindow, 'rotate_selected', _compat_0383)  # original patch line 3885

_legacy_assign(MainWindow, 'flip_selected_horizontal', _compat_0374)  # original patch line 3886

_legacy_assign(MainWindow, 'flip_selected_vertical', _compat_0375)  # original patch line 3887

_legacy_assign(MainWindow, 'scale_selected_grid', _compat_0385)  # original patch line 3888

_legacy_assign(MainWindow, 'scale_selected', _compat_0384)  # original patch line 3889

# original block lines 3900-3900
_compat_0051 = '<Multiple>'

_compat_0396 = _legacy_capture(MainWindow, 'on_scene_selection_changed')  # original capture line 3995

_compat_0395 = _legacy_capture(MainWindow, 'apply_line_defaults')  # original capture line 4017

_legacy_assign(MainWindow, 'on_scene_selection_changed', _compat_0394)  # original patch line 4099

_legacy_assign(MainWindow, 'apply_line_defaults', _compat_0389)  # original patch line 4100

_compat_0411 = _legacy_capture(MainWindow, 'refresh_properties')  # original capture line 4131

_legacy_assign(MainWindow, 'refresh_properties', _compat_0413)  # original patch line 4321

_legacy_assign(TemplateEditorDialog, 'refresh_properties', _compat_0413)  # original patch line 4321

_legacy_assign(MainWindow, '_dbl', _compat_0409)  # original patch line 4322

_legacy_assign(TemplateEditorDialog, '_dbl', _compat_0409)  # original patch line 4322

_legacy_assign(MainWindow, '_combo', _compat_0408)  # original patch line 4323

_legacy_assign(TemplateEditorDialog, '_combo', _compat_0408)  # original patch line 4323

_legacy_assign(MainWindow, '_check', _compat_0407)  # original patch line 4324

_legacy_assign(TemplateEditorDialog, '_check', _compat_0407)  # original patch line 4324

_legacy_assign(MainWindow, '_set', _compat_0417)  # original patch line 4325

_legacy_assign(MainWindow, '_set_attr_vis', _compat_0416)  # original patch line 4326

_legacy_assign(MainWindow, '_set_attr_val', _compat_0415)  # original patch line 4327

_legacy_assign(MainWindow, 'transform_props', _compat_0419)  # original patch line 4424

_legacy_assign(TemplateEditorDialog, 'transform_props', _compat_0419)  # original patch line 4424

_compat_0421 = _legacy_capture(MainWindow, 'rotate_selected')  # original capture line 4437

_legacy_assign(MainWindow, 'rotate_selected', _compat_0422)  # original patch line 4500

_compat_0429 = _legacy_capture(MainWindow, 'scale_selected_grid')  # original capture line 4512

_compat_0428 = _legacy_capture(MainWindow, 'scale_selected')  # original capture line 4513

_legacy_assign(MainWindow, 'scale_selected', _compat_0431)  # original patch line 4666

_legacy_assign(MainWindow, 'scale_selected_grid', _compat_0432)  # original patch line 4667

_compat_0442 = _legacy_capture(MainWindow, 'scale_selected_grid')  # original capture line 4688

_compat_0441 = _legacy_capture(MainWindow, 'scale_selected')  # original capture line 4689

_legacy_assign(MainWindow, 'scale_selected', _compat_0446)  # original patch line 4960

_legacy_assign(MainWindow, 'scale_selected_grid', _compat_0447)  # original patch line 4961

_compat_0443 = _legacy_capture(MainWindow, '_toolbar')  # original capture line 4970

_legacy_assign(MainWindow, '_toolbar', _compat_0451)  # original patch line 4979

_compat_0471 = _legacy_capture(MainWindow, 'scale_selected_grid')  # original capture line 4995

_compat_0470 = _legacy_capture(MainWindow, 'scale_selected')  # original capture line 4996

_legacy_assign(MainWindow, 'scale_selected', _compat_0473)  # original patch line 5350

_legacy_assign(MainWindow, 'scale_selected_grid', _compat_0474)  # original patch line 5351

_compat_0469 = _legacy_capture(MainWindow, '_menus')  # original capture line 5354

_legacy_assign(MainWindow, '_menus', _compat_0467)  # original patch line 5358

_compat_0489 = _legacy_capture(MainWindow, 'scale_selected_grid')  # original capture line 5683

_compat_0488 = _legacy_capture(MainWindow, 'scale_selected')  # original capture line 5684

# original block lines 5716-5731
try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _legacy_assign(_cls, 'scale_selected_grid', _compat_0492)
        _legacy_assign(_cls, 'scale_selected', _compat_0491)
        _legacy_assign(_cls, 'group_selected_graphics', _compat_0484)
        _legacy_assign(_cls, 'ungroup_selected_graphics', _compat_0496)
        _old_init = _legacy_capture(_cls, '__init__')
        def _new_init(self, *args, __old_init=_old_init, **kwargs):
            __old_init(self, *args, **kwargs)
            try:
                _compat_0486(self)
            except Exception:
                pass
        _legacy_assign(_cls, '__init__', _new_init)
except Exception:
    pass







_compat_0515 = _legacy_capture(MainWindow, 'scale_selected_grid')  # original capture line 5745

_compat_0514 = _legacy_capture(MainWindow, 'scale_selected')  # original capture line 5746

# original block lines 6085-6100
try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _legacy_assign(_cls, 'scale_selected_grid', _compat_0517)
        _legacy_assign(_cls, 'scale_selected', _compat_0516)
        _legacy_assign(_cls, 'group_selected_graphics', _compat_0509)
        _legacy_assign(_cls, 'ungroup_selected_graphics', _compat_0521)
        _old_init = _legacy_capture(_cls, '__init__')
        def _compat_0513(self, *args, __old_init=_old_init, **kwargs):
            __old_init(self, *args, **kwargs)
            try:
                _compat_0511(self)
            except Exception:
                pass
        _legacy_assign(_cls, '__init__', _compat_0513)
except Exception:
    pass







_compat_0541 = _legacy_capture(MainWindow, 'scale_selected_grid')  # original capture line 6107

_compat_0540 = _legacy_capture(MainWindow, 'scale_selected')  # original capture line 6108

_compat_0539 = _legacy_capture(MainWindow, 'refresh_properties')  # original capture line 6109

_compat_0538 = _legacy_capture(MainWindow, 'on_scene_selection_changed')  # original capture line 6110

_legacy_assign(MainWindow, 'scale_selected_grid', _compat_0544)  # original patch line 6435

_legacy_assign(MainWindow, 'scale_selected', _compat_0543)  # original patch line 6436

_legacy_assign(MainWindow, 'refresh_properties', _compat_0542)  # original patch line 6439

_legacy_assign(TemplateEditorDialog, 'refresh_properties', _compat_0542)  # original patch line 6439

_legacy_assign(MainWindow, 'on_scene_selection_changed', _compat_0537)  # original patch line 6441

_compat_0583 = _legacy_capture(MainWindow, 'rotate_selected')  # original capture line 6455

_compat_0580 = _legacy_capture(MainWindow, 'flip_selected_horizontal')  # original capture line 6456

_compat_0581 = _legacy_capture(MainWindow, 'flip_selected_vertical')  # original capture line 6457

_compat_0584 = _legacy_capture(MainWindow, 'scale_selected_grid')  # original capture line 6458

_compat_0582 = _legacy_capture(MainWindow, '__init__')  # original capture line 6459

# original block lines 6956-6973
try:
    for _cls in (MainWindow, TemplateEditorDialog):
        _legacy_assign(_cls, 'scale_selected_grid', _compat_0587)
        _legacy_assign(_cls, 'rotate_selected', _compat_0586)
        _legacy_assign(_cls, 'flip_selected_horizontal', _compat_0564)
        _legacy_assign(_cls, 'flip_selected_vertical', _compat_0565)
        _legacy_assign(_cls, 'group_selected_graphics', _compat_0570)
        _legacy_assign(_cls, 'ungroup_selected_graphics', _compat_0597)
        if hasattr(_cls, 'on_scene_selection_changed'):
            _legacy_assign(_cls, 'on_scene_selection_changed', _compat_0578)
    if _compat_0582 is not None:
        def _compat_0572(self, *args, __old_init=_compat_0582, **kwargs):
            __old_init(self, *args, **kwargs)
            try: _compat_0573(self)
            except Exception: pass
        _legacy_assign(MainWindow, '__init__', _compat_0572)
except Exception:
    pass









# original block lines 6978-6981
try:
    from PySide6.QtWidgets import QGraphicsItem as _compat_0068
except Exception:
    _compat_0068 = None

_compat_1009 = _legacy_capture(MainWindow, 'flip_selected_horizontal')  # original capture line 7000

_compat_1010 = _legacy_capture(MainWindow, 'flip_selected_vertical')  # original capture line 7001

_compat_1006 = _legacy_capture(GraphicItem, 'flip_horizontal')  # original capture line 7048

_compat_1007 = _legacy_capture(GraphicItem, 'flip_vertical')  # original capture line 7049

_legacy_assign(GraphicItem, 'flip_horizontal', _compat_1004)  # original patch line 7060

_legacy_assign(GraphicItem, 'flip_vertical', _compat_1005)  # original patch line 7061

_compat_1008 = _legacy_capture(TextItem, '__init__')  # original capture line 7068

_legacy_assign(TextItem, '__init__', _compat_1012)  # original patch line 7080

_legacy_assign(MainWindow, 'flip_selected_horizontal', _compat_1002)  # original patch line 7085

_legacy_assign(MainWindow, 'flip_selected_vertical', _compat_1003)  # original patch line 7086

_compat_1015 = _legacy_capture(MainWindow, '_body_group_capture_base')  # original capture line 7101

_compat_1016 = _legacy_capture(MainWindow, '_body_group_state')  # original capture line 7106

_compat_1018 = _legacy_capture(MainWindow, 'scale_current_unit_children_from_body_resize')  # original capture line 7111

_legacy_assign(MainWindow, '_body_group_capture_base', _compat_1013)  # original patch line 7158

_legacy_assign(MainWindow, '_body_group_state', _compat_1014)  # original patch line 7159

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_1021)  # original patch line 7160

_compat_1017 = _legacy_capture(MainWindow, 'rebuild_scene')  # original capture line 7170

_legacy_assign(MainWindow, 'rebuild_scene', _compat_1020)  # original patch line 7179

_compat_1019 = _legacy_capture(TemplateEditorDialog, 'rebuild_scene')  # original capture line 7181

_legacy_assign(TemplateEditorDialog, 'rebuild_scene', _compat_1023)  # original patch line 7190

_legacy_assign(MainWindow, 'move_current_unit_group', _compat_1026)  # original patch line 7232

_legacy_assign(TemplateEditorDialog, 'move_current_unit_group', _compat_1026)  # original patch line 7234

_compat_1027 = _legacy_capture(MainWindow, '_body_group_capture_base')  # original capture line 7240

_legacy_assign(MainWindow, '_body_group_capture_base', _compat_1024)  # original patch line 7249

_legacy_assign(TemplateEditorDialog, '_body_group_capture_base', _compat_1024)  # original patch line 7251

_compat_1028 = _legacy_capture(MainWindow, '_body_group_state')  # original capture line 7256

_legacy_assign(MainWindow, '_body_group_state', _compat_1025)  # original patch line 7265

_legacy_assign(TemplateEditorDialog, '_body_group_state', _compat_1025)  # original patch line 7267

_compat_1029 = _legacy_capture(MainWindow, 'scale_current_unit_children_from_body_resize')  # original capture line 7272

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_1030)  # original patch line 7284

_legacy_assign(MainWindow, 'select_model_after_rebuild', _compat_1031)  # original patch line 7304

_legacy_assign(TemplateEditorDialog, 'select_model_after_rebuild', _compat_1031)  # original patch line 7306

_compat_1036 = _legacy_capture(MainWindow, 'on_scene_selection_changed')  # original capture line 7336

_legacy_assign(MainWindow, 'on_scene_selection_changed', _compat_1034)  # original patch line 7363

_compat_1038 = _legacy_capture(TextItem, 'mousePressEvent')  # original capture line 7409

_legacy_assign(TextItem, 'mousePressEvent', _compat_1041)  # original patch line 7422

_legacy_assign(TextItem, 'scale_by', _compat_1042)  # original patch line 7444

_compat_1035 = _legacy_capture(MainWindow, '_capture_selection_ids')  # original capture line 7450

_legacy_assign(MainWindow, '_capture_selection_ids', _compat_1032)  # original patch line 7459

_compat_1037 = _legacy_capture(TemplateEditorDialog, '_capture_selection_ids')  # original capture line 7461

_legacy_assign(TemplateEditorDialog, '_capture_selection_ids', _compat_1040)  # original patch line 7470

_compat_1053 = _legacy_capture(MainWindow, 'rebuild_scene')  # original capture line 7540

_legacy_assign(MainWindow, 'rebuild_scene', _compat_1059)  # original patch line 7550

_compat_1054 = _legacy_capture(TemplateEditorDialog, 'rebuild_scene')  # original capture line 7556

_legacy_assign(TemplateEditorDialog, 'rebuild_scene', _compat_1065)  # original patch line 7566

_compat_1058 = _legacy_capture(TextItem, 'mousePressEvent')  # original capture line 7573

_legacy_assign(TextItem, 'mousePressEvent', _compat_1066)  # original patch line 7599

_compat_1052 = _legacy_capture(MainWindow, 'on_scene_selection_changed')  # original capture line 7626

_legacy_assign(MainWindow, 'on_scene_selection_changed', _compat_1049)  # original patch line 7630

_compat_1055 = _legacy_capture(MainWindow, 'rotate_selected')  # original capture line 7700

_compat_1050 = _legacy_capture(MainWindow, 'flip_selected_horizontal')  # original capture line 7701

_compat_1051 = _legacy_capture(MainWindow, 'flip_selected_vertical')  # original capture line 7702

_compat_1056 = _legacy_capture(MainWindow, 'scale_selected_grid')  # original capture line 7703

_compat_1057 = _legacy_capture(MainWindow, 'scale_selected')  # original capture line 7704

_legacy_assign(MainWindow, 'rotate_selected', _compat_1061)  # original patch line 7762

_legacy_assign(MainWindow, 'flip_selected_horizontal', _compat_1046)  # original patch line 7763

_legacy_assign(MainWindow, 'flip_selected_vertical', _compat_1047)  # original patch line 7764

_legacy_assign(MainWindow, 'scale_selected', _compat_1062)  # original patch line 7766

_compat_1069 = _legacy_capture(MainWindow, 'push_undo_state')  # original capture line 7851

_legacy_assign(MainWindow, 'push_undo_state', _compat_1071)  # original patch line 7856

_compat_1070 = _legacy_capture(TemplateEditorDialog, 'push_undo_state')  # original capture line 7862

_legacy_assign(TemplateEditorDialog, 'push_undo_state', _compat_1073)  # original patch line 7867

_compat_1207 = _legacy_capture(MainWindow, 'rebuild_scene')  # original capture line 8338

_compat_1208 = _legacy_capture(MainWindow, 'refresh_properties')  # original capture line 8342

_compat_1209 = _legacy_capture(MainWindow, 'rotate_selected')  # original capture line 8347

_compat_1205 = _legacy_capture(MainWindow, 'flip_selected_horizontal')  # original capture line 8348

_compat_1206 = _legacy_capture(MainWindow, 'flip_selected_vertical')  # original capture line 8349

_legacy_assign(MainWindow, 'rebuild_scene', _compat_1210)  # original patch line 8523

_legacy_assign(MainWindow, 'rotate_selected', _compat_1214)  # original patch line 8527

_legacy_assign(MainWindow, 'flip_selected_horizontal', _compat_1197)  # original patch line 8528

_legacy_assign(MainWindow, 'flip_selected_vertical', _compat_1198)  # original patch line 8529

_legacy_assign(MainWindow, 'refresh_properties', _compat_1211)  # original patch line 8530

_compat_1204 = _legacy_capture(MainWindow, '__init__')  # original capture line 8531

_legacy_assign(MainWindow, '__init__', _compat_1202)  # original patch line 8541

_compat_1218 = _legacy_capture(MainWindow, '__init__')  # original capture line 8826

_legacy_assign(MainWindow, '__init__', _compat_1217)  # original patch line 8831

_compat_1221 = _legacy_capture(MainWindow, '__init__')  # original capture line 9196

_legacy_assign(MainWindow, '__init__', _compat_1220)  # original patch line 9201

_legacy_assign(MainWindow, 'group_selected_graphics', _compat_1224)  # original patch line 9331

_legacy_assign(MainWindow, 'ungroup_selected_graphics', _compat_1224)  # original patch line 9332

_compat_1226 = _legacy_capture(MainWindow, '__init__')  # original capture line 9337

_legacy_assign(MainWindow, '__init__', _compat_1225)  # original patch line 9344

_compat_1078 = _legacy_capture(MainWindow, '_transform_unit_as_body_group')  # original capture line 9540

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_1080)  # original patch line 9586

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_1084)  # original patch line 9843

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_1093)  # original patch line 10128

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_1098)  # original patch line 10349

_legacy_assign(MainWindow, 'dock_pins_to_body', _compat_1095)  # original patch line 10350

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_1110)  # original patch line 10689

_legacy_assign(MainWindow, 'dock_pins_to_body', _compat_1105)  # original patch line 10691

_legacy_assign(MainWindow, '_snapshot_body_resize_state', _compat_1126)  # original patch line 10994

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_1124)  # original patch line 10995

_legacy_assign(MainWindow, 'dock_pins_to_body', _compat_1120)  # original patch line 10997

_legacy_assign(TemplateEditorDialog, '_snapshot_body_resize_state', _compat_1126)  # original patch line 10999

_legacy_assign(TemplateEditorDialog, '_transform_unit_as_body_group', _compat_1127)  # original patch line 11001

_compat_1131 = _legacy_capture(MainWindow, 'load_template_unit')  # original capture line 11066

_legacy_assign(MainWindow, 'load_template_unit', _compat_1129)  # original patch line 11086

_compat_1132 = _legacy_capture(MainWindow, 'rebuild_scene')  # original capture line 11094

_legacy_assign(MainWindow, 'rebuild_scene', _compat_1133)  # original patch line 11126

_legacy_assign(TemplateEditorDialog, 'clear_properties', _compat_1144)  # original patch line 11266

_legacy_assign(TemplateEditorDialog, 'refresh_properties', _compat_1145)  # original patch line 11267

_compat_1140 = _legacy_capture(MainWindow, 'set_pin_attr')  # original capture line 11412

_legacy_assign(MainWindow, 'add_pin', _compat_1134)  # original patch line 11431

_legacy_assign(MainWindow, 'dock_pins_to_body', _compat_1137)  # original patch line 11432

_legacy_assign(MainWindow, 'set_pin_attr', _compat_1141)  # original patch line 11433

_compat_1152 = _legacy_capture(MainWindow, '__init__')  # original capture line 11453

_compat_1153 = _legacy_capture(MainWindow, 'rotate_selected')  # original capture line 11457

_compat_1150 = _legacy_capture(MainWindow, 'flip_selected_horizontal')  # original capture line 11461

_compat_1151 = _legacy_capture(MainWindow, 'flip_selected_vertical')  # original capture line 11465

_legacy_assign(MainWindow, '__init__', _compat_1149)  # original patch line 11637

_legacy_assign(MainWindow, '_selected_body_active', _compat_1156)  # original patch line 11638

_legacy_assign(MainWindow, 'rotate_selected', _compat_1155)  # original patch line 11639

_legacy_assign(MainWindow, 'flip_selected_horizontal', _compat_1147)  # original patch line 11640

_legacy_assign(MainWindow, 'flip_selected_vertical', _compat_1148)  # original patch line 11641

_compat_1166 = _legacy_capture(MainWindow, 'scale_selected')  # original capture line 11654

_legacy_assign(MainWindow, 'scale_selected', _compat_1169)  # original patch line 11842

_compat_1175 = _legacy_capture(MainWindow, 'scale_current_unit_children_from_body_resize')  # original capture line 11865

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_1177)  # original patch line 12071

_compat_1191 = _legacy_capture(MainWindow, 'scale_current_unit_children_from_body_resize')  # original capture line 12083

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_1193)  # original patch line 12282

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_0728)  # original patch line 12661


_legacy_assign(MainWindow, '_transform_unit_as_body_group', _compat_0734)  # original patch line 12666

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_0749)  # original patch line 12972


_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_0764)  # original patch line 13279

_legacy_assign(MainWindow, '_set_body_width_grid', _compat_0768)  # original patch line 13280

_legacy_assign(MainWindow, '_set_body_height_grid', _compat_0767)  # original patch line 13281

_legacy_assign(MainWindow, 'scale_selected_grid', _compat_0766)  # original patch line 13282


_compat_0746 = _legacy_capture(MainWindow, 'load_template_unit')  # original capture line 13432

_legacy_assign(MainWindow, 'load_template_unit', _compat_0742)  # original patch line 13443

_compat_0745 = _legacy_capture(MainWindow, 'load_split_template_units')  # original capture line 13449

_legacy_assign(MainWindow, 'load_split_template_units', _compat_0741)  # original patch line 13463

_compat_0772 = _legacy_capture(MainWindow, '_ribbon')  # original capture line 13610

_legacy_assign(MainWindow, '_ribbon', _compat_0773)  # original patch line 13622

# original block lines 13635-13635
_compat_0053 = 0.1  # model grid units = 0.010" when grid_inch is 0.100"

_compat_0785 = _legacy_capture(MainWindow, 'add_pin')  # original capture line 13797

_compat_0786 = _legacy_capture(MainWindow, 'dock_pins_to_body')  # original capture line 13813

_compat_0793 = _legacy_capture(MainWindow, 'set_pin_attr')  # original capture line 13825

_compat_0792 = _legacy_capture(MainWindow, 'scale_current_unit_children_from_body_resize')  # original capture line 13842

_compat_0789 = _legacy_capture(MainWindow, 'load_template_unit')  # original capture line 13857

_compat_0788 = _legacy_capture(MainWindow, 'load_split_template_units')  # original capture line 13872

_compat_0787 = _legacy_capture(MainWindow, 'import_mentor_symbol')  # original capture line 13888

_legacy_assign(MainWindow, 'add_pin', _compat_0774)  # original patch line 13909

_legacy_assign(MainWindow, 'dock_pins_to_body', _compat_0776)  # original patch line 13910

_legacy_assign(MainWindow, 'set_pin_attr', _compat_0796)  # original patch line 13911

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_0795)  # original patch line 13912

_legacy_assign(MainWindow, 'load_template_unit', _compat_0780)  # original patch line 13913

_legacy_assign(MainWindow, 'load_split_template_units', _compat_0779)  # original patch line 13914

_legacy_assign(MainWindow, 'import_mentor_symbol', _compat_0778)  # original patch line 13915

_legacy_assign(TemplateEditorDialog, 'add_pin', _compat_0774)  # original patch line 13923

_legacy_assign(TemplateEditorDialog, 'dock_pins_to_body', _compat_0776)  # original patch line 13924

# original block lines 13936-13945
_compat_0054 = {
    'IN': (0, 80, 220),
    'OUT': (220, 0, 0),
    'BIDI': (160, 0, 180),
    'BI': (160, 0, 180),
    'POWER': (230, 120, 0),
    'GROUND': (0, 150, 0),
    'ANALOG': (0, 150, 170),
    'PASSIVE': (0, 0, 0),
}

_compat_0811 = _legacy_capture(MainWindow, 'set_pin_attr')  # original capture line 13973

_compat_0809 = _legacy_capture(MainWindow, '_commit_pin_table_value')  # original capture line 13995

_compat_0812 = _legacy_capture(MainWindow, 'set_selected_pins_attr')  # original capture line 14024

_compat_0808 = _legacy_capture(MainWindow, 'add_pin')  # original capture line 14045

_compat_0810 = _legacy_capture(MainWindow, 'import_pinmux_csv')  # original capture line 14065

_legacy_assign(MainWindow, 'set_pin_attr', _compat_0813)  # original patch line 14083

_legacy_assign(MainWindow, '_commit_pin_table_value', _compat_0805)  # original patch line 14084

_legacy_assign(MainWindow, 'set_selected_pins_attr', _compat_0814)  # original patch line 14085

_legacy_assign(MainWindow, 'add_pin', _compat_0802)  # original patch line 14086

_legacy_assign(MainWindow, 'import_pinmux_csv', _compat_0806)  # original patch line 14087

# original block lines 14104-14104
_compat_0055 = 1e-6

_legacy_assign(MainWindow, 'pin_grid_step', property(lambda self: _compat_0821(self)))  # original patch line 14191

_legacy_assign(MainWindow, 'pin_grid_px', property(lambda self: _compat_0820(self)))  # original patch line 14192

_legacy_assign(MainWindow, 'snap_pin_value', _compat_0838)  # original patch line 14193

_legacy_assign(MainWindow, 'snap_pin_point', _compat_0836)  # original patch line 14194

_legacy_assign(MainWindow, 'snap_pin_model', _compat_0835)  # original patch line 14195

_legacy_assign(MainWindow, 'snap_unit_pins', _compat_0837)  # original patch line 14196

_compat_0826 = _legacy_capture(MainWindow, 'scale_current_unit_children_from_body_resize')  # original capture line 14202

_legacy_assign(MainWindow, 'scale_current_unit_children_from_body_resize', _compat_0831)  # original patch line 14288

_compat_0828 = _legacy_capture(MainWindow, 'set_pin_attr')  # original capture line 14294

_legacy_assign(MainWindow, 'set_pin_attr', _compat_0834)  # original patch line 14312

_compat_0824 = _legacy_capture(MainWindow, 'add_pin')  # original capture line 14318

_legacy_assign(MainWindow, 'add_pin', _compat_0815)  # original patch line 14341

_compat_0827 = _legacy_capture(MainWindow, 'schedule_property_refresh')  # original capture line 14347

_legacy_assign(MainWindow, 'notify_canvas_model_changed', _compat_0819)  # original patch line 14431

_legacy_assign_expr(TemplateEditorDialog, 'pin_grid_step', lambda: MainWindow.pin_grid_step)  # original patch line 14439

_legacy_assign_expr(TemplateEditorDialog, 'pin_grid_px', lambda: MainWindow.pin_grid_px)  # original patch line 14440

_legacy_assign(TemplateEditorDialog, 'snap_pin_value', _compat_0838)  # original patch line 14441

_legacy_assign(TemplateEditorDialog, 'snap_pin_point', _compat_0836)  # original patch line 14442

_legacy_assign(TemplateEditorDialog, 'snap_pin_model', _compat_0835)  # original patch line 14443

_legacy_assign(TemplateEditorDialog, 'snap_unit_pins', _compat_0837)  # original patch line 14444

_legacy_assign(TemplateEditorDialog, 'scale_current_unit_children_from_body_resize', _compat_0831)  # original patch line 14445

_legacy_assign(MainWindow, 'notify_canvas_model_changed', _compat_0841)  # original patch line 14473

_compat_0843 = _legacy_capture(MainWindow, 'live_refresh')  # original capture line 14478

_legacy_assign(MainWindow, 'live_refresh', _compat_0840)  # original patch line 14506

_legacy_assign(MainWindow, 'select_all_canvas', _compat_0847)  # original patch line 14634

_compat_0208 = _legacy_capture(MainWindow, '_ribbon')  # original capture line 14695

_legacy_assign(MainWindow, '_ribbon', _compat_0212)  # original patch line 14711

_legacy_assign(MainWindow, 'rebuild_unit_tabs', _compat_0211)  # original patch line 14744

_compat_0207 = _legacy_capture(MainWindow, 'rebuild_symbol_tabs')  # original capture line 14749

_legacy_assign(MainWindow, 'rebuild_symbol_tabs', _compat_0210)  # original patch line 14753

_compat_0206 = _legacy_capture(MainWindow, 'rebuild_all')  # original capture line 14758

_legacy_assign(MainWindow, 'rebuild_all', _compat_0209)  # original patch line 14768

_legacy_assign(MainWindow, 'schedule_property_refresh', _compat_0214)  # original patch line 14785

_legacy_assign(MainWindow, 'notify_canvas_model_changed', _compat_0199)  # original patch line 14807

_compat_0242 = _legacy_capture(MainWindow, '_ribbon')  # original capture line 14914

_legacy_assign(MainWindow, '_ribbon', _compat_0247)  # original patch line 14942

_legacy_assign(MainWindow, 'add_unit', _compat_0220)  # original patch line 14968

_legacy_assign(MainWindow, 'rebuild_workspace', _compat_0245)  # original patch line 15007

_compat_0239 = _legacy_capture(MainWindow, 'rebuild_all')  # original capture line 15012

_legacy_assign(MainWindow, 'rebuild_all', _compat_0243)  # original patch line 15029

_compat_0240 = _legacy_capture(MainWindow, 'rebuild_unit_tabs')  # original capture line 15034

_legacy_assign(MainWindow, 'rebuild_unit_tabs', _compat_0244)  # original patch line 15041

_legacy_assign(MainWindow, 'change_unit', _compat_0229)  # original patch line 15056

_compat_0238 = _legacy_capture(MainWindow, 'notify_canvas_model_changed')  # original capture line 15083

_legacy_assign(MainWindow, 'notify_canvas_model_changed', _compat_0233)  # original patch line 15093

_compat_0241 = _legacy_capture(MainWindow, 'refresh_properties')  # original capture line 15098

_legacy_assign(MainWindow, 'refresh_properties', _compat_0246)  # original patch line 15103

_legacy_assign(MainWindow, '_sync_edit_grid_combo_to_symbol', _compat_0304)  # original patch line 15135

_compat_0300 = _legacy_capture(MainWindow, 'set_edit_grid')  # original capture line 15140

_legacy_assign(MainWindow, 'set_edit_grid', _compat_0301)  # original patch line 15150

_compat_0877 = _legacy_capture(TemplateEditorDialog, 'refresh_properties')  # original capture line 15487

_legacy_assign(MainWindow, 'add_graphic', _compat_0848)  # original patch line 15532

_legacy_assign(MainWindow, 'set_selected_graphics_style', _compat_0882)  # original patch line 15533

_legacy_assign(MainWindow, 'set_selected_graphics_attr', _compat_0881)  # original patch line 15534

_legacy_assign(TemplateEditorDialog, 'add_graphic', _compat_0848)  # original patch line 15536

_legacy_assign(TemplateEditorDialog, '_template_graphic_bounds', _compat_0885)  # original patch line 15537

_legacy_assign(TemplateEditorDialog, '_set_selected_graphics_style', _compat_0882)  # original patch line 15538

_legacy_assign(TemplateEditorDialog, '_set_selected_graphics_attr', _compat_0881)  # original patch line 15539

_legacy_assign(TemplateEditorDialog, 'color_selected_graphics', _compat_0851)  # original patch line 15540

_legacy_assign(TemplateEditorDialog, 'align_graphic_objects', _compat_0849)  # original patch line 15541

_legacy_assign(TemplateEditorDialog, 'distribute_graphic_objects', _compat_0855)  # original patch line 15542

_legacy_assign(TemplateEditorDialog, 'refresh_properties', _compat_0884)  # original patch line 15543

_compat_0873 = _legacy_capture(MainWindow, 'load_template_unit')  # original capture line 15579

_compat_0872 = _legacy_capture(MainWindow, 'load_split_template_units')  # original capture line 15599

_legacy_assign(MainWindow, 'load_template_unit', _compat_0865)  # original patch line 15613

_legacy_assign(MainWindow, 'load_split_template_units', _compat_0864)  # original patch line 15614

# original block lines 15621-15621
_compat_0067 = ['0.100"', '0.050"', '0.025"', '0.010"', '0.005"', '0.003"']

_compat_0892 = _legacy_capture(TemplateEditorDialog, 'refresh_properties')  # original capture line 15719

_legacy_assign(TemplateEditorDialog, '_sync_template_grid_combo_to_unit', _compat_0893)  # original patch line 15755

_legacy_assign(TemplateEditorDialog, 'refresh_properties', _compat_0894)  # original patch line 15756

_legacy_assign(TemplateEditorDialog, '_set', _compat_0903)  # original patch line 15987

_legacy_assign(TemplateEditorDialog, '_set_graphic_shape_and_refresh', _compat_0906)  # original patch line 15988

_legacy_assign(TemplateEditorDialog, '_set_text_item_attr', _compat_0909)  # original patch line 15989

_legacy_assign(TemplateEditorDialog, '_set_selected_pins_attr', _compat_0908)  # original patch line 15990

_legacy_assign(TemplateEditorDialog, '_set_selected_graphics_style', _compat_0899)  # original patch line 15991

_legacy_assign(TemplateEditorDialog, '_set_selected_graphics_attr', _compat_0898)  # original patch line 15992

_legacy_assign(TemplateEditorDialog, '_set_pin_side', _compat_0907)  # original patch line 15993

_legacy_assign(TemplateEditorDialog, 'color_model', _compat_0900)  # original patch line 15994

_legacy_assign(TemplateEditorDialog, 'color_text_item', _compat_0902)  # original patch line 15995

_legacy_assign(TemplateEditorDialog, 'color_selected_text', _compat_0901)  # original patch line 15996

_legacy_assign(TemplateEditorDialog, '_set_body_width_grid', _compat_0905)  # original patch line 15997

_legacy_assign(TemplateEditorDialog, '_set_body_height_grid', _compat_0904)  # original patch line 15998

_compat_0910 = _legacy_capture(TemplateEditorDialog, 'refresh_properties')  # original capture line 16109

_compat_0911 = _legacy_capture(TemplateEditorDialog, 'schedule_property_refresh')  # original capture line 16134

_legacy_assign(TemplateEditorDialog, 'refresh_properties', _compat_0914)  # original patch line 16160

_legacy_assign(TemplateEditorDialog, 'schedule_property_refresh', _compat_0916)  # original patch line 16161

_compat_0918 = _legacy_capture(TemplateEditorDialog, 'refresh_properties')  # original capture line 16230

_compat_0919 = _legacy_capture(TemplateEditorDialog, 'schedule_property_refresh')  # original capture line 16262

_legacy_assign(TemplateEditorDialog, 'refresh_properties', _compat_0922)  # original patch line 16283

_legacy_assign(TemplateEditorDialog, 'schedule_property_refresh', _compat_0923)  # original patch line 16285

_legacy_assign(TemplateEditorDialog, 'on_scene_selection_changed', _compat_0931)  # original patch line 16623

_legacy_assign(TemplateEditorDialog, 'select_all_canvas', _compat_0938)  # original patch line 16624

_legacy_assign(TemplateEditorDialog, '_selected_body_active', _compat_0939)  # original patch line 16625

_legacy_assign(TemplateEditorDialog, 'rotate_selected', _compat_0935)  # original patch line 16626

_legacy_assign(TemplateEditorDialog, 'flip_selected_horizontal', _compat_0927)  # original patch line 16627

_legacy_assign(TemplateEditorDialog, 'flip_selected_vertical', _compat_0928)  # original patch line 16628

_legacy_assign(TemplateEditorDialog, 'scale_selected_grid', _compat_0937)  # original patch line 16629

_legacy_assign(TemplateEditorDialog, 'scale_selected', _compat_0936)  # original patch line 16630

_compat_0949 = _legacy_capture(TemplateEditorDialog, 'refresh_properties')  # original capture line 16830

_compat_0952 = _legacy_capture(TemplateEditorDialog, '_set_selected_pins_attr')  # original capture line 16877

_compat_0953 = _legacy_capture(TemplateEditorDialog, '_set_selected_text_attr')  # original capture line 16889

_compat_0951 = _legacy_capture(TemplateEditorDialog, '_set_selected_graphics_style')  # original capture line 16901

_compat_0950 = _legacy_capture(TemplateEditorDialog, '_set_selected_graphics_attr')  # original capture line 16913

_compat_0946 = _legacy_capture(TemplateEditorDialog, 'color_selected_text')  # original capture line 16925

_compat_0945 = _legacy_capture(TemplateEditorDialog, 'color_selected_pins')  # original capture line 16937

_compat_0944 = _legacy_capture(TemplateEditorDialog, 'color_selected_graphics')  # original capture line 16949

_compat_0943 = _legacy_capture(TemplateEditorDialog, 'align_text_objects')  # original capture line 16961

_compat_0948 = _legacy_capture(TemplateEditorDialog, 'distribute_text_objects')  # original capture line 16973

_compat_0942 = _legacy_capture(TemplateEditorDialog, 'align_graphic_objects')  # original capture line 16985

_compat_0947 = _legacy_capture(TemplateEditorDialog, 'distribute_graphic_objects')  # original capture line 16997

_legacy_assign(TemplateEditorDialog, 'refresh_properties', _compat_0973)  # original patch line 17010

_legacy_assign(TemplateEditorDialog, '_set_selected_pins_attr', _compat_0978)  # original patch line 17011

_legacy_assign(TemplateEditorDialog, '_set_selected_text_attr', _compat_0979)  # original patch line 17012

_legacy_assign(TemplateEditorDialog, '_set_selected_graphics_style', _compat_0977)  # original patch line 17013

_legacy_assign(TemplateEditorDialog, '_set_selected_graphics_attr', _compat_0976)  # original patch line 17014

_legacy_assign(TemplateEditorDialog, 'color_selected_text', _compat_0965)  # original patch line 17015

_legacy_assign(TemplateEditorDialog, 'color_selected_pins', _compat_0964)  # original patch line 17016

_legacy_assign(TemplateEditorDialog, 'color_selected_graphics', _compat_0963)  # original patch line 17017

_legacy_assign(TemplateEditorDialog, 'align_text_objects', _compat_0958)  # original patch line 17018

_legacy_assign(TemplateEditorDialog, 'distribute_text_objects', _compat_0969)  # original patch line 17019

_legacy_assign(TemplateEditorDialog, 'align_graphic_objects', _compat_0957)  # original patch line 17020

_legacy_assign(TemplateEditorDialog, 'distribute_graphic_objects', _compat_0968)  # original patch line 17021

# Final canonical flip wrappers: text/attribute glyphs must never be
# mirrored.  The historical transform pipeline moves their grid anchors; these
# wrappers normalize text scale so only the anchor moves and the glyphs remain
# readable.
_canonical_previous_main_flip_horizontal = _legacy_capture(MainWindow, 'flip_selected_horizontal')
_canonical_previous_main_flip_vertical = _legacy_capture(MainWindow, 'flip_selected_vertical')
_canonical_previous_template_flip_horizontal = _legacy_capture(TemplateEditorDialog, 'flip_selected_horizontal')
_canonical_previous_template_flip_vertical = _legacy_capture(TemplateEditorDialog, 'flip_selected_vertical')


def _canonical_main_flip_selected_horizontal(self, *args, **kwargs):
    return _canonical_flip_with_text_anchor_only(self, _canonical_previous_main_flip_horizontal, 'horizontal', *args, **kwargs)


def _canonical_main_flip_selected_vertical(self, *args, **kwargs):
    return _canonical_flip_with_text_anchor_only(self, _canonical_previous_main_flip_vertical, 'vertical', *args, **kwargs)


def _canonical_template_flip_selected_horizontal(self, *args, **kwargs):
    return _canonical_flip_with_text_anchor_only(self, _canonical_previous_template_flip_horizontal, 'horizontal', *args, **kwargs)


def _canonical_template_flip_selected_vertical(self, *args, **kwargs):
    return _canonical_flip_with_text_anchor_only(self, _canonical_previous_template_flip_vertical, 'vertical', *args, **kwargs)


_legacy_assign(MainWindow, 'flip_selected_horizontal', _canonical_main_flip_selected_horizontal)
_legacy_assign(MainWindow, 'flip_selected_vertical', _canonical_main_flip_selected_vertical)
_legacy_assign(TemplateEditorDialog, 'flip_selected_horizontal', _canonical_template_flip_selected_horizontal)
_legacy_assign(TemplateEditorDialog, 'flip_selected_vertical', _canonical_template_flip_selected_vertical)

