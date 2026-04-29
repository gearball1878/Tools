from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow, QMenu, QMessageBox,
    QPushButton, QSpinBox, QSplitter, QTabWidget, QTextEdit, QTreeWidget, QAbstractItemView,
    QTreeWidgetItem, QVBoxLayout, QWidget, QDialog, QDialogButtonBox, QTableWidget, QTableWidgetItem
)

from .model import ArchitectureModel, ArchitectureLevel, PortType, ConnectionType, NetReferenceDirection, PortSide, PowerDirection
from .exporters import SysML2Exporter, DrawioExporter, BusContentsIniExporter
from .bus_content import BusContentTemplates


class PortEditDialog(QDialog):
    def __init__(self, parent=None, port_type: str = "In", side: str = "Auto", power_direction: str = "PowerIn"):
        super().__init__(parent)
        self.setWindowTitle("Edit Port")
        self.port_type_combo = QComboBox()
        self.port_type_combo.addItems([p.value for p in PortType])
        self.port_type_combo.setCurrentText(port_type)

        self.side_combo = QComboBox()
        self.side_combo.addItems([s.value for s in PortSide])
        self.side_combo.setCurrentText(side)

        self.power_direction_combo = QComboBox()
        self.power_direction_combo.addItems([d.value for d in PowerDirection])
        self.power_direction_combo.setCurrentText(power_direction)

        form = QFormLayout()
        form.addRow("Port type", self.port_type_combo)
        form.addRow("Side override", self.side_combo)
        form.addRow("Power direction", self.power_direction_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)


class ArchitectureBuilderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.model = ArchitectureModel()
        self.selected_block_context: str | None = None
        self.templates = BusContentTemplates(Path(__file__).resolve().parents[1] / "Interface_Template_File.json")

        self.setWindowTitle("SysML2 Architecture Builder + Bus Content Wizard")
        self.resize(1700, 980)

        self.name_edit = QLineEdit(self.model.name)
        self.host_checkbox = QCheckBox("Selected block is Host (unique per visible hierarchy level)")
        self.host_checkbox.stateChanged.connect(self.set_selected_block_host)

        # Shared/manual controls
        self.port_name_edit = QLineEdit()
        self.port_type_combo = QComboBox(); self.port_type_combo.addItems([p.value for p in PortType])
        self.port_side_combo = QComboBox(); self.port_side_combo.addItems([s.value for s in PortSide])
        self.power_direction_combo = QComboBox(); self.power_direction_combo.addItems([d.value for d in PowerDirection])
        self.connection_name_edit = QLineEdit()
        self.connection_type_combo = QComboBox(); self.connection_type_combo.addItems([c.value for c in ConnectionType])
        self.net_ref_direction_combo = QComboBox(); self.net_ref_direction_combo.addItems([d.value for d in NetReferenceDirection])

        # Wizard controls
        self.net_family_combo = QComboBox(); self.net_family_combo.addItems(self.templates.families()); self.net_family_combo.currentTextChanged.connect(self.update_template_controls)
        self.interface_template_combo = QComboBox(); self.interface_template_combo.currentTextChanged.connect(self.on_primary_template_changed)
        self.signal_template_combo = QComboBox()
        self.domain_combo = QComboBox(); self.domain_combo.addItems(self.templates.domains())
        self.subtype_combo = QComboBox(); self.config_combo = QComboBox()
        self.additional_info_edit = QLineEdit(); self.additional_info_edit.setPlaceholderText("Additional info / device / source / sink")
        self.voltage_edit = QLineEdit(); self.voltage_edit.setPlaceholderText("Voltage or frequency, e.g. 1V8, 3V3, 25MHz")
        self.active_low_checkbox = QCheckBox("Active Low")
        self.differential_checkbox = QCheckBox("Differential")
        self.differential_checkbox.setChecked(True)
        self.power_out_checkbox = QCheckBox("Power Out")
        self.propagate_to_parent_checkbox = QCheckBox("Propagate to parent/domain level")
        self.propagate_to_parent_checkbox.setToolTip("If checked, this net/bus reference is shown on collapsed higher hierarchy pages such as 01_Domains.")
        self.bidirectional_side_combo = QComboBox(); self.bidirectional_side_combo.addItems([PortSide.AUTO.value, PortSide.LEFT.value, PortSide.RIGHT.value])
        self.analog_side_combo = QComboBox(); self.analog_side_combo.addItems([PortSide.AUTO.value, PortSide.LEFT.value, PortSide.RIGHT.value])
        self.link_or_port_combo = QComboBox(); self.link_or_port_combo.addItems(["Link", "Port"])
        self.interface_amount_spin = QSpinBox(); self.interface_amount_spin.setMinimum(1); self.interface_amount_spin.setMaximum(99)
        self.interface_start_spin = QSpinBox(); self.interface_start_spin.setMinimum(1); self.interface_start_spin.setMaximum(999); self.interface_start_spin.setValue(1)

        self.net_name_preview = QLineEdit(); self.net_name_preview.setReadOnly(True)
        self.signal_preview = QTextEdit(); self.signal_preview.setReadOnly(True); self.signal_preview.setMinimumHeight(120)

        self.context_label = QLabel("Selected context: <none>")
        self.block_tree = QTreeWidget(); self.block_tree.setHeaderLabels(["Block / Port", "Type / Level", "ID"])
        self.block_tree.itemSelectionChanged.connect(self.on_tree_selection_changed)
        self.block_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.block_tree.setContextMenuPolicy(Qt.CustomContextMenu); self.block_tree.customContextMenuRequested.connect(self.open_block_tree_menu)
        self.port_list = QListWidget()
        self.port_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.port_list.setContextMenuPolicy(Qt.CustomContextMenu); self.port_list.customContextMenuRequested.connect(self.open_port_menu)
        self.net_ref_list = QListWidget(); self.net_ref_list.setContextMenuPolicy(Qt.CustomContextMenu); self.net_ref_list.customContextMenuRequested.connect(self.open_net_menu)
        self.connection_list = QListWidget()
        self.preview = QTextEdit(); self.preview.setReadOnly(True)

        for w in [
            self.net_family_combo, self.interface_template_combo, self.signal_template_combo,
            self.domain_combo, self.subtype_combo, self.config_combo, self.additional_info_edit,
            self.voltage_edit, self.active_low_checkbox, self.differential_checkbox,
            self.power_out_checkbox, self.propagate_to_parent_checkbox, self.link_or_port_combo, self.interface_amount_spin,
            self.interface_start_spin
        ]:
            for sig in ["currentTextChanged", "textChanged", "stateChanged", "valueChanged"]:
                try:
                    getattr(w, sig).connect(self.update_net_name_preview)
                    break
                except Exception:
                    pass

        self._build_ui()
        self.update_template_controls()
        self.refresh_all()

    def _build_ui(self):
        add_domain = QPushButton("Add Domain")
        add_element = QPushButton("Add Architecture Element")
        remove_block = QPushButton("Remove Block")
        create_interfaces = QPushButton("Create Wizard Net/Bus Interfaces")
        save_json = QPushButton("Save JSON")
        load_json = QPushButton("Load JSON")
        export_sysml = QPushButton("Export SysML2")
        build_drawio = QPushButton("Build draw.io + JSON/SysML2/INI")

        add_domain.clicked.connect(self.add_domain)
        add_element.clicked.connect(self.add_arch_element)
        remove_block.clicked.connect(self.remove_selected_block)
        create_interfaces.clicked.connect(self.create_interfaces_from_template)
        save_json.clicked.connect(self.save_json)
        load_json.clicked.connect(self.load_json)
        export_sysml.clicked.connect(self.export_sysml)
        build_drawio.clicked.connect(self.build_drawio)

        top_form = QFormLayout()
        top_form.addRow("Architecture name", self.name_edit)
        top_form.addRow(self.host_checkbox)
        top_form.addRow(self.context_label)

        wizard_form = QFormLayout()
        wizard_form.addRow("Net / Bus family", self.net_family_combo)
        wizard_form.addRow("Bus / Template / Technology", self.interface_template_combo)
        wizard_form.addRow("Signal template", self.signal_template_combo)
        wizard_form.addRow("Domain", self.domain_combo)
        wizard_form.addRow("Subtype / Memory Subtech", self.subtype_combo)
        wizard_form.addRow("Configuration", self.config_combo)
        wizard_form.addRow("Additional info", self.additional_info_edit)
        wizard_form.addRow("Voltage / frequency", self.voltage_edit)
        wizard_form.addRow(self.active_low_checkbox)
        wizard_form.addRow(self.differential_checkbox)
        wizard_form.addRow(self.power_out_checkbox)
        wizard_form.addRow(self.propagate_to_parent_checkbox)
        wizard_form.addRow("Bidi Interface/Memory side", self.bidirectional_side_combo)
        wizard_form.addRow("Analog side", self.analog_side_combo)
        wizard_form.addRow("Link or Port naming", self.link_or_port_combo)
        wizard_form.addRow("Start index", self.interface_start_spin)
        wizard_form.addRow("Amount", self.interface_amount_spin)
        wizard_form.addRow("Net/Port name preview", self.net_name_preview)
        wizard_form.addRow("Wizard signal preview", self.signal_preview)

        wizard_buttons = QHBoxLayout()
        for b in [create_interfaces, save_json, load_json, export_sysml, build_drawio]:
            wizard_buttons.addWidget(b)

        wizard_tab = QWidget()
        wizard_layout = QVBoxLayout()
        wizard_layout.addLayout(top_form)
        wizard_layout.addLayout(wizard_form)
        wizard_layout.addLayout(wizard_buttons)
        wizard_tab.setLayout(wizard_layout)

        # Manual fallback tab
        add_port = QPushButton("Add Manual Port")
        set_port_type = QPushButton("Set selected Port Type/Side")
        add_connection = QPushButton("Add Manual Connection")
        add_net_ref = QPushButton("Add Manual Net/Bus Ref")
        add_port.clicked.connect(self.add_port)
        set_port_type.clicked.connect(self.set_selected_port_type)
        add_connection.clicked.connect(self.add_connection)
        add_net_ref.clicked.connect(self.add_net_reference_with_port)

        manual_form = QFormLayout()
        manual_form.addRow("Manual name", self.port_name_edit)
        manual_form.addRow("Manual port type", self.port_type_combo)
        manual_form.addRow("Manual side override", self.port_side_combo)
        manual_form.addRow("Power direction", self.power_direction_combo)
        manual_form.addRow("Manual connection/ref type", self.connection_type_combo)
        manual_form.addRow("Manual ref direction", self.net_ref_direction_combo)

        manual_buttons = QHBoxLayout()
        for b in [add_port, set_port_type, add_connection, add_net_ref]:
            manual_buttons.addWidget(b)

        manual_tab = QWidget()
        manual_layout = QVBoxLayout()
        manual_layout.addLayout(manual_form)
        manual_layout.addLayout(manual_buttons)
        manual_layout.addWidget(QLabel("Manual creation is intended as a fallback for special cases. Wizard-generated ports/nets are the primary workflow."))
        manual_tab.setLayout(manual_layout)

        left_tabs = QTabWidget()
        left_tabs.addTab(wizard_tab, "Wizard Creation")
        left_tabs.addTab(manual_tab, "Manual Fallback")

        block_port_tab = QWidget()
        block_port_layout = QVBoxLayout()
        block_port_layout.addWidget(QLabel("Block hierarchy"))
        block_port_layout.addWidget(self.block_tree)
        block_port_layout.addWidget(QLabel("Ports on selected block"))
        block_port_layout.addWidget(self.port_list)
        block_port_tab.setLayout(block_port_layout)

        net_connection_tab = QWidget()
        net_connection_layout = QVBoxLayout()
        net_connection_layout.addWidget(QLabel("Net/Bus References"))
        net_connection_layout.addWidget(self.net_ref_list)
        net_connection_layout.addWidget(QLabel("Point-to-point Connections"))
        net_connection_layout.addWidget(self.connection_list)
        net_connection_tab.setLayout(net_connection_layout)

        reference_overview_tab = QWidget()
        reference_overview_layout = QVBoxLayout()
        reference_overview_layout.addWidget(QLabel("Global Net/Bus Reference Overview"))
        self.reference_filter_edit = QLineEdit()
        self.reference_filter_edit.setPlaceholderText("Filter references, netId, refId, type, or connected location...")
        self.reference_filter_edit.textChanged.connect(self.refresh_reference_overview)
        reference_overview_layout.addWidget(self.reference_filter_edit)
        self.reference_overview_table = QTableWidget()
        self.reference_overview_table.setColumnCount(4)
        self.reference_overview_table.setHorizontalHeaderLabels(["Reference / Net", "Net ID / Ref ID", "Connection Type", "Connected locations"])
        reference_overview_layout.addWidget(self.reference_overview_table)
        reference_overview_tab.setLayout(reference_overview_layout)

        right_tabs = QTabWidget()
        right_tabs.addTab(block_port_tab, "Blocks / Ports")
        right_tabs.addTab(net_connection_tab, "Nets / Connections")
        right_tabs.addTab(reference_overview_tab, "Reference Overview")
        right_tabs.addTab(self.preview, "SysML2 Preview")

        splitter = QSplitter()
        splitter.addWidget(left_tabs)
        splitter.addWidget(right_tabs)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        root = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(splitter)
        root.setLayout(layout)
        self.setCentralWidget(root)

    # ---------- template behavior ----------

    def on_primary_template_changed(self):
        if self.net_family_combo.currentText() == "Memory":
            self.subtype_combo.blockSignals(True)
            self.subtype_combo.clear()
            self.subtype_combo.addItems(self.templates.memory_subtechnologies(self.interface_template_combo.currentText()))
            self.subtype_combo.blockSignals(False)
        self.update_net_name_preview()

    def update_template_controls(self):
        family = self.net_family_combo.currentText()
        for combo in [self.interface_template_combo, self.signal_template_combo, self.subtype_combo, self.config_combo]:
            combo.blockSignals(True)
            combo.clear()

        if family == "Interface":
            self.interface_template_combo.addItems(self.templates.interface_templates())
        elif family == "Control":
            self.interface_template_combo.addItems(self.templates.bus_templates_for_family("Control"))
            self.signal_template_combo.addItems(self.templates.control_signal_templates())
        elif family == "Status":
            self.interface_template_combo.addItems(self.templates.bus_templates_for_family("Status"))
            self.signal_template_combo.addItems(self.templates.status_signal_templates())
        elif family == "Analog":
            self.interface_template_combo.addItems(self.templates.analog_bus_templates())
            self.signal_template_combo.addItems(self.templates.analog_signal_templates())
        elif family == "Power":
            self.interface_template_combo.addItems(self.templates.bus_templates_for_family("Power"))
            self.signal_template_combo.addItems(self.templates.voltage_signal_templates())
        elif family == "Memory":
            techs = self.templates.memory_technologies()
            self.interface_template_combo.addItems(techs)
            if techs:
                self.subtype_combo.addItems(self.templates.memory_subtechnologies(techs[0]))
            self.config_combo.addItems([""] + self.templates.memory_configurations())

        for combo in [self.interface_template_combo, self.signal_template_combo, self.subtype_combo, self.config_combo]:
            combo.blockSignals(False)

        self.update_allowed_option_checkboxes()
        self.on_primary_template_changed()

    def update_allowed_option_checkboxes(self):
        family = self.net_family_combo.currentText()
        self.active_low_checkbox.setEnabled(family in {"Control", "Status"})
        self.differential_checkbox.setEnabled(family == "Analog")
        self.power_out_checkbox.setEnabled(family == "Power")

        if family not in {"Control", "Status"}:
            self.active_low_checkbox.setChecked(False)
        if family != "Analog":
            self.differential_checkbox.setChecked(False)
        elif family == "Analog" and not self.differential_checkbox.isChecked():
            self.differential_checkbox.setChecked(True)
        if family != "Power":
            self.power_out_checkbox.setChecked(False)

    def preview_instances(self, amount=1):
        family = self.net_family_combo.currentText()
        if family == "Interface":
            return self.templates.generate_interfaces(
                self.interface_template_combo.currentText(),
                self.interface_start_spin.value(),
                amount,
                self.link_or_port_combo.currentText(),
            )
        if family in {"Control", "Status"}:
            return [self.templates.control_status_instance(
                family,
                self.interface_template_combo.currentText(),
                self.signal_template_combo.currentText(),
                self.additional_info_edit.text().strip() or "INFO",
                self.voltage_edit.text().strip(),
                self.active_low_checkbox.isChecked(),
            )]
        if family == "Analog":
            return [self.templates.analog_instance(
                self.interface_template_combo.currentText(),
                self.signal_template_combo.currentText(),
                self.domain_combo.currentText(),
                self.additional_info_edit.text().strip() or "INFO",
                self.differential_checkbox.isChecked(),
                self.voltage_edit.text().strip(),
            )]
        if family == "Power":
            return [self.templates.power_instance(
                self.signal_template_combo.currentText(),
                self.domain_combo.currentText(),
                self.additional_info_edit.text().strip() or "INFO",
                self.voltage_edit.text().strip() or "0V",
            )]
        if family == "Memory":
            return self.templates.memory_instances(
                self.interface_template_combo.currentText(),
                self.subtype_combo.currentText(),
                self.domain_combo.currentText(),
                self.additional_info_edit.text().strip() or "HOST",
                amount,
                self.config_combo.currentText(),
            )
        return []

    def architecture_port_net_name(self, inst) -> str:
        """Architectural port/net naming rule:
        - Interface, Memory: use bus/interface name.
        - Power, Control, Status, Analog: use the generated signal/net name.
        """
        family = self.net_family_combo.currentText()
        if family in {"Interface", "Memory"}:
            return inst.name
        return inst.signals[0] if inst.signals else inst.name

    def update_net_name_preview(self):
        try:
            instances = self.preview_instances(self.interface_amount_spin.value())
            self.net_name_preview.setText(self.architecture_port_net_name(instances[0]) if instances else "")
            lines = []
            for inst in instances:
                arch_name = self.architecture_port_net_name(inst)
                lines.append(f"Port/Net: {arch_name}\nBus: {inst.name}\nSignals:\n  " + "\n  ".join(inst.signals))
            self.signal_preview.setPlainText("\n\n".join(lines))
        except Exception as exc:
            self.net_name_preview.setText("")
            self.signal_preview.setPlainText(f"Preview error: {exc}")

    # ---------- refresh / selection ----------

    def refresh_all(self):
        self.model.name = self.name_edit.text().strip() or "Generic_Architecture"
        self.refresh_tree()
        self.refresh_lists()
        self.refresh_reference_overview()
        self.update_preview()
        self.update_context_label()
        self.update_net_name_preview()

    def refresh_tree(self):
        self.block_tree.clear()
        for block in self.model.blocks:
            self._add_block_item(None, block, block.name)
        self.block_tree.expandAll()

    def _add_block_item(self, parent_item, block, path):
        host = " [HOST]" if getattr(block, "is_host", False) else ""
        item = QTreeWidgetItem([block.name + host, block.level.value, block.id])
        item.setData(0, Qt.UserRole, {"kind": "block", "path": path})
        if parent_item is None:
            self.block_tree.addTopLevelItem(item)
        else:
            parent_item.addChild(item)
        for port in block.ports:
            p_item = QTreeWidgetItem([f"port: {port.name}", port.port_type.value, port.id])
            p_item.setData(0, Qt.UserRole, {"kind": "port", "path": path, "port": port.name})
            item.addChild(p_item)
        for child in block.children:
            self._add_block_item(item, child, f"{path}.{child.name}")

    def refresh_lists(self):
        self.port_list.clear()
        block = self.model.find_block(self.selected_block_context) if self.selected_block_context else None
        if block:
            for port in block.ports:
                side = port.attributes.get("sideOverride", "Auto")
                pwr = port.attributes.get("powerDirection", "")
                prop = "propagate" if port.attributes.get("propagateToParent", False) else "local"
                self.port_list.addItem(f"{port.name} [{port.port_type.value}] {prop} side={side} {pwr}  {port.id}")

        self.connection_list.clear()
        for con in self.model.connections:
            self.connection_list.addItem(f"{con.name} [{con.connection_type.value}] netId={con.net_id}")

        self.net_ref_list.clear()
        for ref in self.model.net_references:
            sigs = ref.attributes.get("signals", [])
            prop = "propagate" if ref.attributes.get("propagateToParent", False) else "local"
            self.net_ref_list.addItem(f"{ref.name} [{ref.reference_type.value}/{ref.direction.value}] {prop} netId={ref.net_id} signals={len(sigs)}")

    def update_context_label(self):
        self.context_label.setText(f"Selected context: {self.selected_block_context or '<none>'}")

    def on_tree_selection_changed(self):
        data = self.selected_tree_data()
        if data and data["kind"] in {"block", "port"}:
            self.selected_block_context = data["path"]
        block = self.model.find_block(self.selected_block_context) if self.selected_block_context else None
        if block:
            self.host_checkbox.blockSignals(True)
            self.host_checkbox.setChecked(getattr(block, "is_host", False))
            self.host_checkbox.blockSignals(False)
        self.refresh_lists()
        self.update_context_label()
        self.update_preview()

    def selected_tree_items_data(self):
        items = self.block_tree.selectedItems()
        return [item.data(0, Qt.UserRole) for item in items if item and item.data(0, Qt.UserRole)]

    def selected_tree_data(self):
        item = self.block_tree.currentItem()
        return item.data(0, Qt.UserRole) if item else None

    def selected_port(self):
        data = self.selected_tree_data()
        if data and data["kind"] == "port":
            return data["path"], data["port"]
        return None

    def selected_ports_from_port_list(self):
        if not self.selected_block_context:
            return []
        block = self.model.find_block(self.selected_block_context)
        if not block:
            return []
        rows = sorted({idx.row() for idx in self.port_list.selectedIndexes()})
        return [(self.selected_block_context, block.ports[row].name) for row in rows if 0 <= row < len(block.ports)]

    def selected_port_from_port_list(self):
        ports = self.selected_ports_from_port_list()
        if ports:
            return ports[0]
        return None

    def target_block_path(self):
        return self.selected_block_context


    def _is_bottom_up_path(self, block_path: str) -> bool:
        # Bottom-up propagation only makes sense for child hierarchy levels.
        # Level1 domains have no parent architecture sheet to propagate from.
        return "." in block_path

    def selected_ports_from_tree(self):
        result = []
        for data in self.selected_tree_items_data():
            if data.get("kind") == "port":
                result.append((data["path"], data["port"]))
        return result

    def selected_net_reference_rows(self):
        rows = sorted({idx.row() for idx in self.net_ref_list.selectedIndexes()})
        if not rows:
            row = self.net_ref_list.currentRow()
            if row >= 0:
                rows = [row]
        return [r for r in rows if 0 <= r < len(self.model.net_references)]

    def _set_propagation_for_ports(self, ports, propagate: bool):
        if not ports:
            self.warn("Select one or more ports.")
            return

        skipped = []
        changed = 0
        try:
            for block_path, port_name in dict.fromkeys(ports):
                if not self._is_bottom_up_path(block_path):
                    skipped.append(f"{block_path}.{port_name}")
                    continue
                self.model.set_port_propagation(block_path, port_name, propagate)
                changed += 1

            self.refresh_all()
            if skipped and not changed:
                self.warn("Propagation is bottom-up only. Select ports below a domain, e.g. architecture-element ports.")
            elif skipped:
                self.warn("Some selected ports were skipped because propagation is bottom-up only.")
        except Exception as exc:
            self.error(exc)

    def _set_propagation_for_selected_ports(self, propagate: bool):
        ports = []
        ports.extend(self.selected_ports_from_tree())
        ports.extend(self.selected_ports_from_port_list())
        self._set_propagation_for_ports(ports, propagate)

    def enable_selected_port_propagation(self):
        self._set_propagation_for_selected_ports(True)

    def disable_selected_port_propagation(self):
        self._set_propagation_for_selected_ports(False)

    def set_selected_net_reference_propagation(self, propagate: bool):
        rows = self.selected_net_reference_rows()
        if not rows:
            self.warn("Select one or more net references.")
            return

        skipped = []
        changed = 0
        try:
            for row in rows:
                ref = self.model.net_references[row]
                if not self._is_bottom_up_path(ref.end.block_path):
                    skipped.append(ref.name)
                    continue
                self.model.set_net_reference_propagation(ref.id, propagate)
                changed += 1

            self.refresh_all()
            if skipped and not changed:
                self.warn("Propagation is bottom-up only. Select signals below a domain, e.g. architecture-element signals.")
            elif skipped:
                self.warn("Some selected signals were skipped because propagation is bottom-up only.")
        except Exception as exc:
            self.error(exc)

    def enable_selected_net_reference_propagation(self):
        self.set_selected_net_reference_propagation(True)

    def disable_selected_net_reference_propagation(self):
        self.set_selected_net_reference_propagation(False)


    # ---------- context menus ----------

    def open_block_tree_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("Add Domain", self.add_domain)
        menu.addAction("Add Architecture Element", self.add_arch_element)
        menu.addAction("Rename selected Block/Port", self.rename_selected_tree_item)
        menu.addAction("Move selected Block/Port to...", self.move_selected_tree_items)
        menu.addAction("Edit selected Port Type/Side", self.edit_selected_port_dialog)
        menu.addSeparator()
        menu.addAction("Enable Propagate to parent/domain", self.enable_selected_port_propagation)
        menu.addAction("Disable Propagate to parent/domain", self.disable_selected_port_propagation)
        menu.addSeparator()
        menu.addAction("Delete selected Block(s)/Port(s)", self.delete_selected_tree_item)
        menu.exec(self.block_tree.viewport().mapToGlobal(pos))

    def open_port_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("Edit Port Type/Side", self.edit_port_list_port_dialog)
        menu.addAction("Copy selected Port(s)", self.copy_selected_ports)
        menu.addAction("Copy/connect selected Port(s) to block...", self.copy_selected_ports_to_block)
        menu.addSeparator()
        menu.addAction("Enable Propagate to parent/domain", self.enable_selected_port_propagation)
        menu.addAction("Disable Propagate to parent/domain", self.disable_selected_port_propagation)
        menu.addSeparator()
        menu.addAction("Remove selected Port(s)", self.remove_selected_port)
        menu.exec(self.port_list.viewport().mapToGlobal(pos))

    def open_net_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("Rename selected Net Ref", self.rename_selected_net_reference)
        menu.addAction("Enable Propagate to parent/domain", self.enable_selected_net_reference_propagation)
        menu.addAction("Disable Propagate to parent/domain", self.disable_selected_net_reference_propagation)
        menu.addAction("Remove selected Net Ref(s)", self.remove_selected_net_reference)
        menu.exec(self.net_ref_list.viewport().mapToGlobal(pos))

    # ---------- block / port ops ----------

    def set_selected_block_host(self):
        path = self.target_block_path()
        if not path:
            return
        try:
            self.model.set_block_host(path, self.host_checkbox.isChecked())
            self.refresh_all()
        except Exception as exc:
            self.error(exc)

    def add_domain(self):
        name, ok = QInputDialog.getText(self, "Add Domain", "Domain name:")
        if ok and name.strip():
            try:
                self.model.add_domain(name.strip())
                self.selected_block_context = name.strip()
                self.refresh_all()
            except Exception as exc:
                self.error(exc)

    def add_arch_element(self):
        path = self.target_block_path()
        if not path:
            self.warn("Select a domain first.")
            return
        block = self.model.find_block(path)
        if not block or block.level != ArchitectureLevel.DOMAIN:
            self.warn("Architecture elements can only be added below a domain.")
            return
        name, ok = QInputDialog.getText(self, "Add Architecture Element", "Element name:")
        if ok and name.strip():
            try:
                self.model.add_arch_element(path, name.strip())
                self.selected_block_context = f"{path}.{name.strip()}"
                self.refresh_all()
            except Exception as exc:
                self.error(exc)

    def rename_selected_tree_item(self):
        data = self.selected_tree_data()
        if not data:
            return
        if data["kind"] == "block":
            name, ok = QInputDialog.getText(self, "Rename Block", "New name:", text=data["path"].split(".")[-1])
            if ok and name.strip():
                self.selected_block_context = self.model.rename_block(data["path"], name.strip())
        elif data["kind"] == "port":
            name, ok = QInputDialog.getText(self, "Rename Port", "New name:", text=data["port"])
            if ok and name.strip():
                self.model.rename_port(data["path"], data["port"], name.strip())
        self.refresh_all()

    def delete_selected_tree_item(self):
        items = self.selected_tree_items_data()
        if not items:
            return

        # Delete ports first, then blocks deepest-first to avoid dangling paths.
        port_items = [d for d in items if d["kind"] == "port"]
        block_items = sorted([d for d in items if d["kind"] == "block"], key=lambda d: d["path"].count("."), reverse=True)

        for data in port_items:
            self.model.delete_port_with_references(data["path"], data["port"])

        for data in block_items:
            self.model.remove_block(data["path"])
            if self.selected_block_context and (
                self.selected_block_context == data["path"]
                or self.selected_block_context.startswith(data["path"] + ".")
            ):
                self.selected_block_context = None

        self.refresh_all()

    def remove_selected_block(self):
        items = self.selected_tree_items_data()
        blocks = sorted([d for d in items if d["kind"] == "block"], key=lambda d: d["path"].count("."), reverse=True)
        if not blocks:
            self.warn("Select one or more blocks to remove.")
            return
        for data in blocks:
            self.model.remove_block(data["path"])
            if self.selected_block_context and (
                self.selected_block_context == data["path"]
                or self.selected_block_context.startswith(data["path"] + ".")
            ):
                self.selected_block_context = None
        self.refresh_all()

    def add_port(self):
        path = self.target_block_path()
        if not path:
            self.warn("Select a block first.")
            return
        block = self.model.find_block(path)
        name = self.port_name_edit.text().strip()
        if not name:
            name, ok = QInputDialog.getText(self, "Add Port", "Port name:")
            if not ok or not name.strip():
                return
        try:
            attrs = {"sideOverride": self.port_side_combo.currentText()}
            if PortType(self.port_type_combo.currentText()) == PortType.POWER:
                attrs["powerDirection"] = self.power_direction_combo.currentText()
            block.add_port(name.strip(), PortType(self.port_type_combo.currentText()), attrs)
            self.port_name_edit.clear()
            self.refresh_all()
        except Exception as exc:
            self.error(exc)

    def remove_selected_port(self):
        selected = []
        tree_port = self.selected_port()
        if tree_port:
            selected.append(tree_port)
        selected.extend(self.selected_ports_from_port_list())

        # Unique
        selected = list(dict.fromkeys(selected))
        if not selected:
            self.warn("Select one or more ports.")
            return

        for block_path, port_name in selected:
            self.model.delete_port_with_references(block_path, port_name)
        self.refresh_all()

    def set_selected_port_type(self):
        selected = self.selected_port() or self.selected_port_from_port_list()
        if not selected:
            self.warn("Select a port.")
            return
        block_path, port_name = selected
        try:
            self.model.set_port_type(block_path, port_name, PortType(self.port_type_combo.currentText()))
            self.model.set_port_side(block_path, port_name, PortSide(self.port_side_combo.currentText()))
            if PortType(self.port_type_combo.currentText()) == PortType.POWER:
                self.model.set_power_direction(block_path, port_name, PowerDirection(self.power_direction_combo.currentText()))
            self.refresh_all()
        except Exception as exc:
            self.error(exc)

    def edit_selected_port_dialog(self):
        selected = self.selected_port()
        if not selected:
            self.warn("Select a port in the block tree.")
            return
        self._edit_port_dialog(*selected)

    def edit_port_list_port_dialog(self):
        selected = self.selected_port_from_port_list()
        if not selected:
            self.warn("Select a port in the port list.")
            return
        self._edit_port_dialog(*selected)

    def _edit_port_dialog(self, block_path, port_name):
        try:
            port = self.model.require_port(block_path, port_name)
            dlg = PortEditDialog(
                self,
                port.port_type.value,
                port.attributes.get("sideOverride", "Auto"),
                port.attributes.get("powerDirection", "PowerIn"),
            )
            if dlg.exec() == QDialog.Accepted:
                self.model.set_port_type(block_path, port_name, PortType(dlg.port_type_combo.currentText()))
                self.model.set_port_side(block_path, port_name, PortSide(dlg.side_combo.currentText()))
                if PortType(dlg.port_type_combo.currentText()) == PortType.POWER:
                    self.model.set_power_direction(block_path, port_name, PowerDirection(dlg.power_direction_combo.currentText()))
                self.refresh_all()
        except Exception as exc:
            self.error(exc)

    # ---------- net/bus creation ----------

    def add_net_reference_with_port(self):
        path = self.target_block_path()
        if not path:
            self.warn("Select a block first.")
            return
        name = self.port_name_edit.text().strip() or self.net_name_preview.text().strip()
        if not name:
            return
        try:
            attrs = {"manual": True, "family": "manual", "sideOverride": self.port_side_combo.currentText(), "propagateToParent": self.propagate_to_parent_checkbox.isChecked()}
            if PortType(self.port_type_combo.currentText()) == PortType.POWER:
                attrs["powerDirection"] = self.power_direction_combo.currentText()
            self.model.add_interface_reference(
                path, name.strip(), ConnectionType(self.connection_type_combo.currentText()),
                NetReferenceDirection(self.net_ref_direction_combo.currentText()), [],
                PortType(self.port_type_combo.currentText()), attrs,
            )
            self.port_name_edit.clear()
            self.refresh_all()
        except Exception as exc:
            self.error(exc)

    def create_interfaces_from_template(self):
        path = self.target_block_path()
        if not path:
            self.warn("Select a domain or architecture element first.")
            return
        try:
            family = self.net_family_combo.currentText()
            direction = self.default_direction_for_family(family)
            instances = self.preview_instances(self.interface_amount_spin.value())
            duplicates = []
            for inst in instances:
                arch_name = self.architecture_port_net_name(inst)
                if self.model.has_net_reference_on_block(path, arch_name):
                    duplicates.append(arch_name)
            if duplicates:
                raise ValueError("Bus/net already exists on this hierarchy level: " + ", ".join(duplicates))

            for inst in instances:
                arch_name = self.architecture_port_net_name(inst)
                conn_type = ConnectionType.BUS if len(inst.signals) > 1 or family in {"Interface", "Memory"} else ConnectionType.NET
                extra = {
                    "family": inst.family,
                    "template": inst.template_name,
                    "instanceIndex": inst.index,
                    "bcLine": inst.bc_line,
                    "busContentName": inst.name,
                    "propagateToParent": self.propagate_to_parent_checkbox.isChecked(),
                }
                if family in {"Interface", "Memory"} and self.bidirectional_side_combo.currentText() != "Auto":
                    extra["sideOverride"] = self.bidirectional_side_combo.currentText()
                if family == "Analog" and self.analog_side_combo.currentText() != "Auto":
                    extra["sideOverride"] = self.analog_side_combo.currentText()
                if family == "Power":
                    extra["powerDirection"] = PowerDirection.OUT.value if self.power_out_checkbox.isChecked() else PowerDirection.IN.value
                self.model.add_interface_reference(path, arch_name, conn_type, direction, inst.signals, None, extra)

            if family == "Interface":
                self.interface_start_spin.setValue(1)
            self.refresh_all()
        except Exception as exc:
            self.error(exc)

    def architecture_port_net_name(self, inst) -> str:
        family = self.net_family_combo.currentText()
        if family in {"Interface", "Memory"}:
            return inst.name
        return inst.signals[0] if inst.signals else inst.name

    def default_direction_for_family(self, family):
        block = self.model.find_block(self.target_block_path()) if self.target_block_path() else None
        is_host = bool(block and block.is_host)
        if family in {"Interface", "Memory", "Analog"}:
            return NetReferenceDirection.BIDI
        if family == "Control":
            return NetReferenceDirection.OUT if is_host else NetReferenceDirection.IN
        if family == "Status":
            return NetReferenceDirection.IN if is_host else NetReferenceDirection.OUT
        if family == "Power":
            return NetReferenceDirection.OUT if self.power_out_checkbox.isChecked() else NetReferenceDirection.IN
        return NetReferenceDirection(self.net_ref_direction_combo.currentText())

    def add_connection(self):
        ports = self.get_all_port_paths()
        if len(ports) < 2:
            self.warn("At least two ports are required.")
            return
        src, ok = QInputDialog.getItem(self, "Source Port", "Source:", ports, 0, False)
        if not ok:
            return
        dst, ok = QInputDialog.getItem(self, "Target Port", "Target:", ports, 0, False)
        if not ok:
            return
        name = self.connection_name_edit.text().strip()
        if not name:
            name, ok = QInputDialog.getText(self, "Connection Name", "Connection name:")
            if not ok or not name.strip():
                return
        src_block, src_port = src.rsplit(".", 1)
        dst_block, dst_port = dst.rsplit(".", 1)
        try:
            self.model.add_connection(name.strip(), ConnectionType(self.connection_type_combo.currentText()), src_block, src_port, dst_block, dst_port)
            self.connection_name_edit.clear()
            self.refresh_all()
        except Exception as exc:
            self.error(exc)

    def remove_selected_connection(self):
        row = self.connection_list.currentRow()
        if row >= 0:
            self.model.remove_connection(self.model.connections[row].id)
            self.refresh_all()

    def remove_selected_net_reference(self):
        rows = self.selected_net_reference_rows()
        if not rows:
            self.warn("Select one or more net references.")
            return
        for row in sorted(rows, reverse=True):
            self.model.remove_net_reference(self.model.net_references[row].id)
        self.refresh_all()

    def rename_selected_net_reference(self):
        rows = self.selected_net_reference_rows()
        if not rows:
            self.warn("Select a net reference.")
            return
        if len(rows) > 1:
            self.warn("Please select only one net reference to rename.")
            return
        row = rows[0]
        ref = self.model.net_references[row]
        name, ok = QInputDialog.getText(self, "Rename Net Reference", "New name:", text=ref.name)
        if ok and name.strip():
            self.model.rename_net_reference(ref.id, name.strip())
            self.refresh_all()

    def get_all_port_paths(self):
        return [f"{path}.{port.name}" for block, path in self.model.walk_blocks() for port in block.ports]

    def refresh_reference_overview(self):
        if not hasattr(self, "reference_overview_table"):
            return

        filter_text = ""
        if hasattr(self, "reference_filter_edit"):
            filter_text = self.reference_filter_edit.text().strip().lower()

        groups = {}
        for ref in self.model.net_references:
            entry = groups.setdefault(ref.name, {
                "net_id": ref.net_id,
                "ref_id": ref.id,
                "connection_type": ref.reference_type.value,
                "locations": [],
            })
            entry["locations"].append(f"{ref.end.block_path}.{ref.end.port_name}")

        rows = []
        for name, data in sorted(groups.items()):
            location_text = "\n".join(sorted(data["locations"]))
            searchable = f"{name} {data['net_id']} {data['ref_id']} {data['connection_type']} {location_text}".lower()
            if filter_text and filter_text not in searchable:
                continue
            rows.append((name, data, location_text))

        self.reference_overview_table.setRowCount(len(rows))
        for row, (name, data, location_text) in enumerate(rows):
            self.reference_overview_table.setItem(row, 0, QTableWidgetItem(name))
            self.reference_overview_table.setItem(row, 1, QTableWidgetItem(f"{data['net_id']} / {data['ref_id']}"))
            self.reference_overview_table.setItem(row, 2, QTableWidgetItem(data["connection_type"]))
            self.reference_overview_table.setItem(row, 3, QTableWidgetItem(location_text))
        self.reference_overview_table.resizeColumnsToContents()
        self.reference_overview_table.resizeRowsToContents()

    def move_selected_tree_items(self):
        items = self.selected_tree_items_data()
        if not items:
            self.warn("Select one or more blocks or ports to move.")
            return
        block_items = [d for d in items if d.get("kind") == "block"]
        port_items = [d for d in items if d.get("kind") == "port"]
        try:
            if block_items and port_items:
                self.warn("Move either blocks or ports, not both at once.")
                return
            if block_items:
                domains = [path for block, path in self.model.walk_blocks() if block.level == ArchitectureLevel.DOMAIN]
                target, ok = QInputDialog.getItem(self, "Move block(s)", "Target domain:", domains, 0, False)
                if not ok:
                    return
                for data in sorted(block_items, key=lambda d: d["path"].count("."), reverse=True):
                    if "." not in data["path"]:
                        self.warn("Domain blocks cannot be moved below another object.")
                        continue
                    self.model.move_block(data["path"], target)
                self.selected_block_context = target
                self.refresh_all()
                return
            if port_items:
                targets = [path for block, path in self.model.walk_blocks()]
                target, ok = QInputDialog.getItem(self, "Move port(s)", "Target block:", targets, 0, False)
                if not ok:
                    return
                for data in port_items:
                    self.model.move_port(data["path"], data["port"], target)
                self.selected_block_context = target
                self.refresh_all()
        except Exception as exc:
            self.error(exc)

    def copy_selected_ports(self):
        ports = []
        ports.extend(self.selected_ports_from_tree())
        ports.extend(self.selected_ports_from_port_list())
        ports = list(dict.fromkeys(ports))
        if not ports:
            self.warn("Select one or more ports to copy.")
            return
        try:
            for block_path, port_name in ports:
                self.model.copy_port(block_path, port_name)
            self.refresh_all()
        except Exception as exc:
            self.error(exc)

    def copy_selected_net_references(self):
        rows = self.selected_net_reference_rows()
        if not rows:
            self.warn("Select one or more net references to copy.")
            return
        try:
            for row in rows:
                self.model.copy_net_reference(self.model.net_references[row].id)
            self.refresh_all()
        except Exception as exc:
            self.error(exc)


    def _select_target_block(self, title: str):
        targets = [path for block, path in self.model.walk_blocks()]
        if not targets:
            self.warn("No target block available.")
            return None
        target, ok = QInputDialog.getItem(self, title, "Target block:", targets, 0, False)
        return target if ok else None

    def copy_selected_ports_to_block(self):
        ports = []
        ports.extend(self.selected_ports_from_tree())
        ports.extend(self.selected_ports_from_port_list())
        ports = list(dict.fromkeys(ports))
        if not ports:
            self.warn("Select one or more ports to copy/connect.")
            return

        target = self._select_target_block("Copy/connect port(s)")
        if not target:
            return

        try:
            for block_path, port_name in ports:
                self.model.copy_port_to_block(block_path, port_name, target, preserve_name=True)
            self.selected_block_context = target
            self.refresh_all()
        except Exception as exc:
            self.error(exc)

    def copy_selected_net_references_to_block(self):
        rows = self.selected_net_reference_rows()
        if not rows:
            self.warn("Select one or more net references to copy/connect.")
            return

        target = self._select_target_block("Copy/connect net reference(s)")
        if not target:
            return

        try:
            for row in rows:
                self.model.copy_net_reference_to_block(self.model.net_references[row].id, target, preserve_name=True)
            self.selected_block_context = target
            self.refresh_all()
        except Exception as exc:
            self.error(exc)


    # ---------- files / preview ----------

    def output_base(self, selected_path=None):
        name = re.sub(r"[^A-Za-z0-9_]+", "_", self.model.name.strip() or "architecture")
        if selected_path:
            p = Path(selected_path)
            return p.with_name(name)
        return Path(name)

    def save_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save JSON", f"{self.output_base().name}.json", "JSON (*.json)")
        if path:
            self.model.name = self.name_edit.text().strip() or "Generic_Architecture"
            self.model.save_json(path)

    def load_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load JSON", "", "JSON (*.json)")
        if path:
            try:
                self.model = ArchitectureModel.load_json(path)
                self.name_edit.setText(self.model.name)
                self.selected_block_context = None
                self.refresh_all()
            except Exception as exc:
                self.error(exc)

    def export_sysml(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export SysML2", f"{self.output_base().name}.sysml", "SysML (*.sysml)")
        if path:
            try:
                SysML2Exporter(self.model).save(path)
                self.update_preview()
            except Exception as exc:
                self.error(exc)

    def build_drawio(self):
        path, _ = QFileDialog.getSaveFileName(self, "Build draw.io", f"{self.output_base().name}.drawio", "draw.io (*.drawio)")
        if path:
            try:
                self.model.name = self.name_edit.text().strip() or "Generic_Architecture"
                base = Path(path).with_suffix("")
                DrawioExporter(self.model).save(base.with_suffix(".drawio"))
                self.model.save_json(base.with_suffix(".json"))
                SysML2Exporter(self.model).save(base.with_suffix(".sysml"))
                BusContentsIniExporter(self.model).save(base.with_name("busconts.ini"))
                QMessageBox.information(self, "Build complete", "draw.io, JSON, SysML2 and busconts.ini were written.")
            except Exception as exc:
                self.error(exc)

    def update_preview(self):
        self.model.name = self.name_edit.text().strip() or "Generic_Architecture"
        try:
            self.preview.setPlainText(SysML2Exporter(self.model).export_text())
        except Exception as exc:
            self.preview.setPlainText(f"Validation / export preview error:\n{exc}")

    def warn(self, text):
        QMessageBox.warning(self, "Warning", text)

    def error(self, exc):
        QMessageBox.critical(self, "Error", str(exc))


def run_gui():
    app = QApplication([])
    win = ArchitectureBuilderWindow()
    win.show()
    app.exec()
