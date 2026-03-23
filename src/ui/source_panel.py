from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QListWidget, QListWidgetItem, QMenu, QMessageBox)
from PySide6.QtCore import Qt, Signal
from core.models import Project, LaserSource
import copy

class SourcePanel(QWidget):
    selection_changed = Signal(object) # Emits LaserSource object
    source_list_changed = Signal() # Emits when list structure changes

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Toolbar
        btn_layout = QHBoxLayout()
        self.btn_new = QPushButton("新建")
        self.btn_copy = QPushButton("复制")
        self.btn_del = QPushButton("删除")
        
        btn_layout.addWidget(self.btn_new)
        btn_layout.addWidget(self.btn_copy)
        btn_layout.addWidget(self.btn_del)
        layout.addLayout(btn_layout)
        
        # List
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self.on_selection_changed)
        layout.addWidget(self.list_widget)
        
        # Signals
        self.btn_new.clicked.connect(self.create_source)
        self.btn_copy.clicked.connect(self.copy_source)
        self.btn_del.clicked.connect(self.delete_source)
        
        self.refresh_list()

    def on_selection_changed(self, row):
        if row >= 0 and row < len(self.project.lasers):
            self.selection_changed.emit(self.project.lasers[row])
        else:
            self.selection_changed.emit(None)

    def refresh_list(self):
        current_row = self.list_widget.currentRow()
        self.list_widget.clear()
        for laser in self.project.lasers:
            item = QListWidgetItem(laser.name)
            self.list_widget.addItem(item)
        
        if current_row >= 0 and current_row < self.list_widget.count():
            self.list_widget.setCurrentRow(current_row)

    def create_source(self):
        name = f"Laser {len(self.project.lasers) + 1}"
        source = LaserSource(name=name, type=0)
        self.project.lasers.append(source)
        self.refresh_list()
        self.source_list_changed.emit()

    def copy_source(self):
        row = self.list_widget.currentRow()
        if row < 0: return
        
        src = self.project.lasers[row]
        new_src = copy.deepcopy(src)
        new_src.name = f"{src.name}_Copy"
        self.project.lasers.append(new_src)
        self.refresh_list()
        self.source_list_changed.emit()

    def delete_source(self):
        row = self.list_widget.currentRow()
        if row < 0: return
        
        # Confirm
        reply = QMessageBox.question(self, "确认删除", "确定要删除选中的光源吗？", 
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.project.lasers.pop(row)
            self.refresh_list()
            self.source_list_changed.emit()

    def set_project(self, project: Project):
        self.project = project
        self.refresh_list()
