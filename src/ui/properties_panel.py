from PySide6.QtWidgets import (QWidget, QFormLayout, QLineEdit, QComboBox, 
                               QGroupBox, QVBoxLayout, QScrollArea, QMenu, QPushButton, QHBoxLayout, QCheckBox, QMessageBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator, QAction
from core.models import LaserSource
from .dialogs import SubordinateSelectionDialog
from core.commands import PropertyChangeCommand, ListPropertyChangeCommand, BatchCommand
import math

class ValidatedLineEdit(QLineEdit):
    value_changed = Signal(float, float) # old_val, new_val
    create_automation = Signal(str) # param_name
    create_random = Signal(str) # param_name

    def __init__(self, param_name, min_val=-float('inf'), max_val=float('inf'), parent=None):
        super().__init__(parent)
        self.param_name = param_name
        self.min_val = min_val
        self.max_val = max_val
        self.last_valid_value = 0.0
        
        # Validator (Allow float input)
        validator = QDoubleValidator()
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.setValidator(validator)
        
        self.editingFinished.connect(self.validate_and_emit)

    def setValue(self, val):
        self.last_valid_value = val
        self.setText(f"{val:.3f}".rstrip('0').rstrip('.'))

    def value(self):
        return self.last_valid_value

    def validate_and_emit(self):
        text = self.text()
        try:
            val = float(text)
            if self.min_val <= val <= self.max_val:
                if val != self.last_valid_value:
                    old_val = self.last_valid_value
                    self.last_valid_value = val
                    self.value_changed.emit(old_val, val)
            else:
                # Out of range, revert
                self.setValue(self.last_valid_value)
        except ValueError:
            # Invalid format, revert
            self.setValue(self.last_valid_value)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        
        # Translate Standard Actions
        # Since createStandardContextMenu returns a populated menu, we iterate and check text or standard actions?
        # Actually easier to clear and rebuild, or just modify text if possible.
        # But QLineEdit standard menu items are internal.
        # Let's try to find them by text or shortcut, or just clear and add ours + standard wrapper calls.
        
        # Strategy: Clear and rebuild manually calling standard slots
        menu.clear()
        
        act_undo = menu.addAction("撤销")
        act_undo.triggered.connect(self.undo)
        act_undo.setEnabled(self.isUndoAvailable())
        
        act_redo = menu.addAction("重做")
        act_redo.triggered.connect(self.redo)
        act_redo.setEnabled(self.isRedoAvailable())
        
        menu.addSeparator()
        
        act_cut = menu.addAction("剪切")
        act_cut.triggered.connect(self.cut)
        act_cut.setEnabled(self.hasSelectedText())
        
        act_copy = menu.addAction("复制")
        act_copy.triggered.connect(self.copy)
        act_copy.setEnabled(self.hasSelectedText())
        
        act_paste = menu.addAction("粘贴")
        act_paste.triggered.connect(self.paste)
        # Check if clipboard has text? Keep simple.
        
        act_del = menu.addAction("删除")
        act_del.triggered.connect(self.del_)
        act_del.setEnabled(self.hasSelectedText())
        
        menu.addSeparator()
        
        act_sel_all = menu.addAction("全选")
        act_sel_all.triggered.connect(self.selectAll)
        
        menu.addSeparator()
        
        # Custom Actions
        act_auto = menu.addAction("创建自动化轨道包络")
        act_auto.triggered.connect(lambda: self.create_automation.emit(self.param_name))
        
        # act_rand = menu.addAction("动态随机")
        # act_rand.triggered.connect(lambda: self.create_random.emit(self.param_name))
        
        menu.exec(event.globalPos())

class ContextComboBox(QComboBox):
    create_automation = Signal(str) # param_name

    def __init__(self, param_name, parent=None):
        super().__init__(parent)
        self.param_name = param_name

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        
        act_auto = menu.addAction("创建自动化轨道包络")
        act_auto.triggered.connect(lambda: self.create_automation.emit(self.param_name))
        
        menu.exec(event.globalPos())

class PropertiesPanel(QWidget):
    source_changed = Signal()
    # Relay signals from inputs to main window
    request_automation = Signal(str, str) # source_name, param_name
    request_random = Signal(str, str) # source_name, param_name

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.current_source = None
        self.project = None
        self.is_updating = False
        self.offset_inputs = []
        self.offset_mode_toggles = []
        self.init_ui()

    def set_project(self, project):
        self.project = project

    def set_source(self, source):
        self.current_source = source
        if not source:
            self.container.setEnabled(False)
            return
            
        self.is_updating = True
        self.container.setEnabled(True)
        
        self.refresh_values()
        
        self.is_updating = False

    def refresh_values(self):
        if not self.current_source: return
        
        self.is_updating = True
        source = self.current_source
        
        self.name_edit.setText(source.name)
        self.type_combo.setCurrentIndex(source.type)
        
        # Master State
        self.master_switch.setChecked(source.is_master)
        self.update_master_ui_state()
        
        p = source.params
        self.pos_x.setValue(p[0])
        self.pos_y.setValue(p[1])
        self.pos_z.setValue(p[2])
        
        self.dir_x.setValue(p[3])
        self.dir_y.setValue(p[4])
        self.dir_z.setValue(p[5])
        
        self.color_r.setValue(self.to_ui_color(p[6]))
        self.color_g.setValue(self.to_ui_color(p[7]))
        self.color_b.setValue(self.to_ui_color(p[8]))
        
        self.brightness.setValue(p[9])
        self.thickness.setValue(p[10])
        self.divergence.setValue(self.to_ui_angle(p[11]))
        self.attenuation.setValue(p[12])
        
        px, py, pz, pw = p[13], p[14], p[15], p[16]

        self.param_x.setValue(px)
        self.param_y.setValue(py)
        self.param_z.setValue(pz)
        self.param_w.setValue(pw)
        
        # Update Labels
        self.update_param_labels(source.type)
        
        # Offsets
        op = source.offset_params
        self.off_pos_x.setValue(op[0])
        self.off_pos_y.setValue(op[1])
        self.off_pos_z.setValue(op[2])
        
        self.off_dir_x.setValue(op[3])
        self.off_dir_y.setValue(op[4])
        self.off_dir_z.setValue(op[5])
        
        self.off_color_r.setValue(self.to_ui_color(op[6]))
        self.off_color_g.setValue(self.to_ui_color(op[7]))
        self.off_color_b.setValue(self.to_ui_color(op[8]))
        
        self.off_brightness.setValue(op[9])
        self.off_thickness.setValue(op[10])
        self.off_divergence.setValue(self.to_ui_angle(op[11]))
        self.off_attenuation.setValue(op[12])
        
        opx, opy, opz, opw = op[13], op[14], op[15], op[16]
            
        self.off_param_x.setValue(opx)
        self.off_param_y.setValue(opy)
        self.off_param_z.setValue(opz)
        self.off_param_w.setValue(opw)
        
        # Local Up
        self.local_up_x.setValue(p[17])
        self.local_up_y.setValue(p[18])
        self.local_up_z.setValue(p[19])
        
        self.off_local_up_x.setValue(op[17])
        self.off_local_up_y.setValue(op[18])
        self.off_local_up_z.setValue(op[19])
        
        # Offset Modes
        omp = source.offset_mode_params
        # We iterate our stored toggles and set them
        for toggle in self.offset_mode_toggles:
            idx = toggle.property("offset_idx")
            if idx is not None and idx < len(omp):
                toggle.setChecked(omp[idx] > 0.5)

        self.is_updating = False

    def to_ui_color(self, val):
        return val * 255.0

    def from_ui_color(self, val):
        return val / 255.0

    def to_ui_angle(self, val):
        return math.degrees(val)

    def from_ui_angle(self, val):
        return math.radians(val)

    def add_param_row(self, layout, label_text, param_name, min_v, max_v, offset_idx=None):
        input_widget = self.create_input(param_name, min_v, max_v)
        if offset_idx is not None:
            input_widget.setProperty("param_idx", offset_idx)
        
        offset_widget = None
        mode_toggle = None
        if offset_idx is not None:
            # Create offset input
            offset_param_name = "offset_" + param_name
            offset_widget = self.create_input(offset_param_name, -1000, 1000)
            offset_widget.setPlaceholderText("Offset")
            offset_widget.setFixedWidth(60) # Compact
            
            # Tag it with index to find it later
            offset_widget.setProperty("offset_idx", offset_idx)
            self.offset_inputs.append(offset_widget)
            
            # Create Offset Mode Toggle
            mode_toggle = QCheckBox()
            mode_toggle.setToolTip("切换偏移模式: 关=叠加到自身参数, 开=叠加到主控参数")
            mode_toggle.setProperty("offset_idx", offset_idx)
            mode_toggle.toggled.connect(self.on_offset_mode_changed)
            
            # Context Menu for Automation
            mode_toggle.setContextMenuPolicy(Qt.CustomContextMenu)
            mode_toggle.customContextMenuRequested.connect(lambda pos, name=param_name: self.on_mode_toggle_context_menu(pos, name, mode_toggle))
            
            self.offset_mode_toggles.append(mode_toggle)

            h_layout = QHBoxLayout()
            h_layout.addWidget(input_widget)
            h_layout.addWidget(offset_widget)
            h_layout.addWidget(mode_toggle)
            layout.addRow(label_text, h_layout)
        else:
            layout.addRow(label_text, input_widget)
            
        return input_widget, offset_widget

    def create_input(self, param_name, min_val, max_val):
        le = ValidatedLineEdit(param_name, min_val, max_val)
        le.value_changed.connect(self.on_val_changed)
        le.create_automation.connect(self.on_create_automation)
        le.create_random.connect(self.on_create_random)
        return le

    def init_ui(self):
        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        
        self.container = QWidget()
        self.container.setEnabled(False) # Default to disabled
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(10)
        
        # --- Common Properties ---
        self.group_common = QGroupBox("基本属性")
        self.form_common = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self.on_name_changed)
        self.form_common.addRow("名称:", self.name_edit)
        
        self.type_combo = ContextComboBox("type")
        self.type_combo.addItems(["0: 光束(Single Beam)", "1: 扇形(Fan)", "2: 图案(Pattern)", "3: 粒子(Particle)", "4: 实扇形(Solid Fan)"])
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        self.type_combo.create_automation.connect(self.on_create_automation)
        self.form_common.addRow("类型:", self.type_combo)
        
        self.group_common.setLayout(self.form_common)
        self.layout.addWidget(self.group_common)

        # --- Master/Slave Control ---
        self.group_master = QGroupBox("主控/附属 (Master/Slave)")
        self.form_master = QFormLayout()
        
        self.master_switch = QCheckBox("设为主控光源")
        self.master_switch.toggled.connect(self.on_master_toggled)
        # Context menu for automation
        self.master_switch.setContextMenuPolicy(Qt.CustomContextMenu)
        self.master_switch.customContextMenuRequested.connect(self.on_master_context_menu)
        self.form_master.addRow(self.master_switch)
        
        self.btn_subordinates = QPushButton("选择附属光源...")
        self.btn_subordinates.clicked.connect(self.on_select_subordinates)
        self.btn_subordinates.setEnabled(False)
        self.form_master.addRow(self.btn_subordinates)
        
        self.group_master.setLayout(self.form_master)
        self.layout.addWidget(self.group_master)
        
        # --- Transform ---
        self.group_trans = QGroupBox("变换 (Transform)")
        self.form_trans = QFormLayout()
        
        self.pos_x, self.off_pos_x = self.add_param_row(self.form_trans, "位置 X:", "pos.x", -10000, 10000, 0)
        self.pos_y, self.off_pos_y = self.add_param_row(self.form_trans, "位置 Y:", "pos.y", -10000, 10000, 1)
        self.pos_z, self.off_pos_z = self.add_param_row(self.form_trans, "位置 Z:", "pos.z", -10000, 10000, 2)
        
        self.dir_x, self.off_dir_x = self.add_param_row(self.form_trans, "方向 X:", "dir.x", -1, 1, 3)
        self.dir_y, self.off_dir_y = self.add_param_row(self.form_trans, "方向 Y:", "dir.y", -1, 1, 4)
        self.dir_z, self.off_dir_z = self.add_param_row(self.form_trans, "方向 Z:", "dir.z", -1, 1, 5)
        
        self.group_trans.setLayout(self.form_trans)
        self.layout.addWidget(self.group_trans)
        
        # --- Appearance ---
        self.group_app = QGroupBox("外观 (Appearance)")
        self.form_app = QFormLayout()
        
        self.color_r, self.off_color_r = self.add_param_row(self.form_app, "颜色 R:", "color.r", 0, 255, 6)
        self.color_g, self.off_color_g = self.add_param_row(self.form_app, "颜色 G:", "color.g", 0, 255, 7)
        self.color_b, self.off_color_b = self.add_param_row(self.form_app, "颜色 B:", "color.b", 0, 255, 8)
        
        self.brightness, self.off_brightness = self.add_param_row(self.form_app, "亮度:", "brightness", 0, 1, 9)
        self.thickness, self.off_thickness = self.add_param_row(self.form_app, "粗细/缩放:", "thickness", 0, 10, 10)
        self.divergence, self.off_divergence = self.add_param_row(self.form_app, "发散角:", "divergence", 0, 180, 11)
        self.attenuation, self.off_attenuation = self.add_param_row(self.form_app, "衰减:", "attenuation", 0, 10, 12)
        
        self.group_app.setLayout(self.form_app)
        self.layout.addWidget(self.group_app)
        
        # --- Params ---
        self.group_params = QGroupBox("参数 (Params)")
        self.form_params = QFormLayout()
        
        self.param_x, self.off_param_x = self.add_param_row(self.form_params, "Param X:", "params.x", -1000, 1000, 13)
        self.param_y, self.off_param_y = self.add_param_row(self.form_params, "Param Y:", "params.y", -1000, 1000, 14)
        self.param_z, self.off_param_z = self.add_param_row(self.form_params, "Param Z:", "params.z", -1000, 1000, 15)
        self.param_w, self.off_param_w = self.add_param_row(self.form_params, "Param W:", "params.w", -1000, 1000, 16)
        
        # Local Up (New)
        self.local_up_x, self.off_local_up_x = self.add_param_row(self.form_params, "Local Up X:", "localUp.x", -1.0, 1.0, 17)
        self.local_up_y, self.off_local_up_y = self.add_param_row(self.form_params, "Local Up Y:", "localUp.y", -1.0, 1.0, 18)
        self.local_up_z, self.off_local_up_z = self.add_param_row(self.form_params, "Local Up Z:", "localUp.z", -1.0, 1.0, 19)
        
        self.group_params.setLayout(self.form_params)
        self.layout.addWidget(self.group_params)

        self.layout.addStretch()
        self.scroll.setWidget(self.container)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.addWidget(self.scroll)

    def on_master_context_menu(self, pos):
        menu = QMenu(self)
        act_auto = menu.addAction("创建自动化轨道包络")
        act_auto.triggered.connect(lambda: self.request_automation.emit(self.current_source.name, "is_master"))
        menu.exec(self.master_switch.mapToGlobal(pos))

    def on_master_toggled(self, checked):
        if self.is_updating or not self.current_source: return
        if self.main_window:
            cmd = PropertyChangeCommand(self.current_source, "is_master", not checked, checked, "切换主控开关", self.main_window)
            self.main_window.undo_stack.push(cmd)
        else:
            self.current_source.is_master = checked
            self.update_master_ui_state()
            self.source_changed.emit()

    def update_master_ui_state(self):
        is_master = self.master_switch.isChecked()
        self.btn_subordinates.setEnabled(is_master)
        for w in self.offset_inputs:
            w.setVisible(is_master)
        for t in self.offset_mode_toggles:
            t.setVisible(is_master)

    def on_mode_toggle_context_menu(self, pos, param_name, widget):
        menu = QMenu(self)
        act_auto = menu.addAction("创建自动化轨道包络")
        # auto param name: "offset_mode_" + param_name
        full_param_name = "offset_mode_" + param_name
        act_auto.triggered.connect(lambda: self.request_automation.emit(self.current_source.name, full_param_name))
        menu.exec(widget.mapToGlobal(pos))

    def on_offset_mode_changed(self, checked):
        if self.is_updating or not self.current_source: return
        sender = self.sender()
        offset_idx = sender.property("offset_idx")
        if offset_idx is not None:
            val = 1.0 if checked else 0.0
            old_val = self.current_source.offset_mode_params[offset_idx]
            if val != old_val:
                if self.main_window:
                    cmd = ListPropertyChangeCommand(self.current_source.offset_mode_params, offset_idx, old_val, val, "切换偏移模式", self.main_window)
                    self.main_window.undo_stack.push(cmd)
                else:
                    self.current_source.offset_mode_params[offset_idx] = val
                    self.source_changed.emit()

    def on_select_subordinates(self):
        if not self.current_source or not self.project: return
        
        # Filter available: Not current, Not attached to others
        available = []
        for l in self.project.lasers:
            if l.name == self.current_source.name: continue
            
            # Check if attached to someone else (and that someone is not us)
            # Actually we just check l.master_id. 
            # If l.master_id is set and != self.current_source.name, it's taken.
            # If l.master_id == self.current_source.name, it's already ours (should be in selection list, not available list?)
            # Wait, dialog takes (Available, Selected).
            # Selected are those currently subordinate to us.
            # Available are those free (master_id == "").
            
            if l.master_id and l.master_id != self.current_source.name:
                continue # Attached to someone else
                
            available.append(l.name)
            
        current_subs = self.current_source.subordinate_ids
        
        dialog = SubordinateSelectionDialog(available, current_subs, self)
        if dialog.exec():
            new_subs = dialog.get_selection()
            if new_subs == current_subs: return
            
            if self.main_window:
                commands = []
                # 1. Unlink old
                for sub_name in current_subs:
                    if sub_name not in new_subs:
                        for l in self.project.lasers:
                            if l.name == sub_name:
                                commands.append(PropertyChangeCommand(l, "master_id", l.master_id, "", f"解除 {sub_name} 附属", self.main_window))
                                break
                # 2. Link new
                for sub_name in new_subs:
                    if sub_name not in current_subs:
                        for l in self.project.lasers:
                            if l.name == sub_name:
                                commands.append(PropertyChangeCommand(l, "master_id", l.master_id, self.current_source.name, f"添加 {sub_name} 附属", self.main_window))
                                break
                
                commands.append(PropertyChangeCommand(self.current_source, "subordinate_ids", list(current_subs), list(new_subs), "更新附属列表", self.main_window))
                batch = BatchCommand(commands, "修改附属光源", self.main_window)
                self.main_window.undo_stack.push(batch)
            else:
                # Update Logic
                # 1. Unlink old subordinates that are removed
                for sub_name in current_subs:
                    if sub_name not in new_subs:
                        # Find laser object
                        for l in self.project.lasers:
                            if l.name == sub_name:
                                l.master_id = ""
                                break
                                
                # 2. Link new subordinates
                for sub_name in new_subs:
                    for l in self.project.lasers:
                        if l.name == sub_name:
                            l.master_id = self.current_source.name
                            break
                            
                self.current_source.subordinate_ids = new_subs
                self.source_changed.emit()

    def on_name_changed(self):
        if self.is_updating or not self.current_source: return
        new_name = self.name_edit.text()
        if new_name == self.current_source.name: return
        if self.main_window:
            cmd = PropertyChangeCommand(self.current_source, "name", self.current_source.name, new_name, "修改光源名称", self.main_window)
            self.main_window.undo_stack.push(cmd)
        else:
            self.current_source.name = new_name
            self.source_changed.emit()

    def on_type_changed(self, idx):
        if self.is_updating or not self.current_source: return
        if idx == self.current_source.type: return
        if self.main_window:
            cmd = PropertyChangeCommand(self.current_source, "type", self.current_source.type, idx, "修改光源类型", self.main_window)
            self.main_window.undo_stack.push(cmd)
        else:
            self.current_source.type = idx
            self.update_param_labels(idx)
            self.source_changed.emit()

    def update_param_labels(self, idx):
        # Default Labels
        l_x, l_y, l_z, l_w = "Param X:", "Param Y:", "Param Z:", "Param W:"
        
        if idx == 0: # Single Beam
            l_x, l_y, l_z, l_w = "未使用:", "未使用:", "未使用:", "Effect ID:"
        elif idx == 1: # Fan
            l_x, l_y, l_z, l_w = "光束数量:", "扩散角度:", "相位偏移:", "Effect ID:"
        elif idx == 2: # Pattern
            l_x, l_y, l_z, l_w = "形状 ID:", "旋转角度:", "填充/参数:", "Effect ID:"
        elif idx == 3: # Particle
            l_x, l_y, l_z, l_w = "种子:", "扩散:", "速度:", "Effect ID:"
        elif idx == 4: # Solid Fan
            l_x, l_y, l_z, l_w = "未使用:", "扩散角度:", "偏移角度:", "Effect ID:"
            
        # Helper to set label text in FormLayout
        # We need to access the label widget of the row.
        # The layout.itemAt(row, QFormLayout.LabelRole).widget().setText(...)
        # But we used addRow(str, widget) so the label is created internally.
        # Actually we used add_param_row which uses addRow(label_text, h_layout)
        # So we can iterate the layout or store references to labels.
        # But we didn't store references.
        # However, we can update the "tooltips" or placeholders?
        # Or better: We iterate the form layout rows.
        
        # Accessing form layout items is tricky if we don't have pointers.
        # Let's use a simpler approach: 
        # In add_param_row, we passed 'label_text'.
        # We can find the label by iterating.
        
        # Actually, self.param_x is the input widget.
        # We can find its parent (h_layout), then find the label associated with that layout in the form layout?
        # Too complex.
        
        # Alternative: We can just set tooltips on the inputs.
        self.param_x.setToolTip(l_x)
        self.param_y.setToolTip(l_y)
        self.param_z.setToolTip(l_z)
        self.param_w.setToolTip(l_w)
        
        # But user wants visible labels.
        # Let's try to update the labels in the layout.
        # We know the indices of rows in self.form_params.
        # Row 0: param_x, Row 1: param_y, ...
        
        def set_row_label(layout, row, text):
            item = layout.itemAt(row, QFormLayout.LabelRole)
            if item and item.widget():
                item.widget().setText(text)
                
        set_row_label(self.form_params, 0, l_x)
        set_row_label(self.form_params, 1, l_y)
        set_row_label(self.form_params, 2, l_z)
        set_row_label(self.form_params, 3, l_w)

    def on_create_automation(self, param_name):
        if self.current_source:
            self.request_automation.emit(self.current_source.name, param_name)

    def on_create_random(self, param_name):
        if self.current_source:
            self.request_random.emit(self.current_source.name, param_name)

    def on_val_changed(self, old_val, new_val):
        if self.is_updating or not self.current_source: return
        
        sender = self.sender()
        
        # Check if it's an offset input
        offset_idx = sender.property("offset_idx")
        param_idx = sender.property("param_idx")
        
        if offset_idx is not None:
            final_new = new_val
            final_old = old_val
            # Apply conversions matching main params
            if offset_idx in [6, 7, 8]: # Color
                final_new = self.from_ui_color(new_val)
                final_old = self.from_ui_color(old_val)
            elif offset_idx == 11: # Divergence
                final_new = self.from_ui_angle(new_val)
                final_old = self.from_ui_angle(old_val)
            
            if self.main_window:
                cmd = ListPropertyChangeCommand(self.current_source.offset_params, offset_idx, final_old, final_new, f"修改 {sender.param_name}", self.main_window)
                self.main_window.undo_stack.push(cmd)
            else:
                self.current_source.offset_params[offset_idx] = final_new
                self.source_changed.emit()
            return

        if param_idx is not None:
            final_new = new_val
            final_old = old_val
            if param_idx in [6, 7, 8]:
                final_new = self.from_ui_color(new_val)
                final_old = self.from_ui_color(old_val)
            elif param_idx == 11:
                final_new = self.from_ui_angle(new_val)
                final_old = self.from_ui_angle(old_val)
                
            if self.main_window:
                cmd = ListPropertyChangeCommand(self.current_source.params, param_idx, final_old, final_new, f"修改 {sender.param_name}", self.main_window)
                self.main_window.undo_stack.push(cmd)
            else:
                self.current_source.params[param_idx] = final_new
                self.source_changed.emit()
            return
