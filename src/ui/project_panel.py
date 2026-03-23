from PySide6.QtWidgets import QWidget, QFormLayout, QDoubleSpinBox, QComboBox, QGroupBox, QVBoxLayout, QSpinBox
from PySide6.QtCore import Signal
from core.models import Project
from core.commands import ProjectSettingsCommand

class ProjectPanel(QWidget):
    settings_changed = Signal()

    def __init__(self, project: Project, parent=None, main_window=None):
        super().__init__(parent)
        self.project = project
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        group = QGroupBox("工程设置")
        form = QFormLayout()
        
        self.bpm_spin = QDoubleSpinBox()
        self.bpm_spin.setRange(10.0, 400.0)
        self.bpm_spin.setValue(self.project.bpm)
        self.bpm_spin.valueChanged.connect(self.on_bpm_changed)
        form.addRow("BPM:", self.bpm_spin)
        
        self.ts_combo = QComboBox()
        self.ts_combo.addItems(["4/4", "3/4", "6/8", "5/4", "7/8"]) # Common ones
        self.ts_combo.setEditable(True)
        self.ts_combo.setCurrentText(self.project.time_signature)
        self.ts_combo.currentTextChanged.connect(self.on_ts_changed)
        form.addRow("拍号:", self.ts_combo)

        self.len_spin = QSpinBox()
        self.len_spin.setRange(1, 9999)
        self.len_spin.setValue(self.project.total_measures)
        self.len_spin.valueChanged.connect(self.on_len_changed)
        form.addRow("长度(小节):", self.len_spin)
        
        group.setLayout(form)
        layout.addWidget(group)
        layout.addStretch()

    def on_bpm_changed(self, value):
        if self.project.bpm == value: return
        if self.main_window:
            cmd = ProjectSettingsCommand(self.project, "bpm", self.project.bpm, value, "修改 BPM", self.main_window)
            self.main_window.undo_stack.push(cmd)
        else:
            self.project.bpm = value
        self.settings_changed.emit()

    def on_ts_changed(self, value):
        if self.project.time_signature == value: return
        
        if self.main_window:
            self.main_window.undo_stack.beginMacro("修改拍号")
            cmd = ProjectSettingsCommand(self.project, "time_signature", self.project.time_signature, value, "修改拍号", self.main_window)
            self.main_window.undo_stack.push(cmd)
            
            try:
                # Parse numerator from "3/4", "6/8" etc.
                numerator = int(value.split('/')[0])
                if self.project.beats_per_bar != numerator:
                    cmd2 = ProjectSettingsCommand(self.project, "beats_per_bar", self.project.beats_per_bar, numerator, "修改每小节拍数", self.main_window)
                    self.main_window.undo_stack.push(cmd2)
            except (ValueError, IndexError):
                pass
            
            self.main_window.undo_stack.endMacro()
        else:
            self.project.time_signature = value
            try:
                numerator = int(value.split('/')[0])
                self.project.beats_per_bar = numerator
            except (ValueError, IndexError):
                pass
                
        self.settings_changed.emit()

    def on_len_changed(self, value):
        if self.project.total_measures == value: return
        if self.main_window:
            cmd = ProjectSettingsCommand(self.project, "total_measures", self.project.total_measures, value, "修改工程长度", self.main_window)
            self.main_window.undo_stack.push(cmd)
        else:
            self.project.total_measures = value
        self.settings_changed.emit()

    def set_project(self, project: Project):
        self.project = project
        
        # Block signals to prevent feedback loops during update
        self.bpm_spin.blockSignals(True)
        self.ts_combo.blockSignals(True)
        self.len_spin.blockSignals(True)
        
        self.bpm_spin.setValue(self.project.bpm)
        self.ts_combo.setCurrentText(self.project.time_signature)
        self.len_spin.setValue(self.project.total_measures)
        
        self.bpm_spin.blockSignals(False)
        self.ts_combo.blockSignals(False)
        self.len_spin.blockSignals(False)
