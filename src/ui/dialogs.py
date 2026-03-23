from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox, 
                               QDoubleSpinBox, QCheckBox, QLabel, QListWidget, 
                               QHBoxLayout, QPushButton, QAbstractItemView)
from PySide6.QtCore import Qt

class RandomizationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("动态随机设置")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.min_val = QDoubleSpinBox()
        self.min_val.setRange(-10000, 10000)
        self.min_val.setValue(0.0)
        form.addRow("最小值:", self.min_val)
        
        self.max_val = QDoubleSpinBox()
        self.max_val.setRange(-10000, 10000)
        self.max_val.setValue(1.0)
        form.addRow("最大值:", self.max_val)
        
        self.interval = QDoubleSpinBox()
        self.interval.setRange(0.125, 64.0)
        self.interval.setValue(1.0)
        self.interval.setSingleStep(0.25)
        form.addRow("变化间隔 (拍):", self.interval)
        
        self.smooth = QCheckBox("平滑连续")
        self.smooth.setChecked(True)
        form.addRow(self.smooth)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        return {
            "min": self.min_val.value(),
            "max": self.max_val.value(),
            "interval": self.interval.value(),
            "smooth": self.smooth.isChecked()
        }

class SubordinateSelectionDialog(QDialog):
    def __init__(self, available_lasers, current_selection, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择附属光源")
        self.resize(500, 400)
        self.available = available_lasers
        self.selection = list(current_selection) # Copy
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Lists Layout
        lists_layout = QHBoxLayout()
        
        # Available
        v1 = QVBoxLayout()
        v1.addWidget(QLabel("可用光源:"))
        self.list_avail = QListWidget()
        self.list_avail.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.refresh_avail()
        v1.addWidget(self.list_avail)
        lists_layout.addLayout(v1)
        
        # Buttons (Middle)
        v_btns = QVBoxLayout()
        v_btns.addStretch()
        self.btn_add = QPushButton(">>")
        self.btn_add.clicked.connect(self.add_items)
        v_btns.addWidget(self.btn_add)
        self.btn_remove = QPushButton("<<")
        self.btn_remove.clicked.connect(self.remove_items)
        v_btns.addWidget(self.btn_remove)
        v_btns.addStretch()
        lists_layout.addLayout(v_btns)
        
        # Selected (Orderable)
        v2 = QVBoxLayout()
        v2.addWidget(QLabel("已选附属 (可拖拽排序):"))
        self.list_selected = QListWidget()
        self.list_selected.setDragDropMode(QAbstractItemView.InternalMove)
        self.refresh_selected()
        v2.addWidget(self.list_selected)
        lists_layout.addLayout(v2)
        
        main_layout.addLayout(lists_layout)
        
        # Dialog Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def refresh_avail(self):
        self.list_avail.clear()
        # Filter out items already in selection
        for name in self.available:
            if name not in self.selection:
                self.list_avail.addItem(name)
                
    def refresh_selected(self):
        self.list_selected.clear()
        for name in self.selection:
            self.list_selected.addItem(name)
            
    def add_items(self):
        items = self.list_avail.selectedItems()
        for item in items:
            self.selection.append(item.text())
        self.refresh_avail()
        self.refresh_selected()
        
    def remove_items(self):
        items = self.list_selected.selectedItems()
        for item in items:
            if item.text() in self.selection:
                self.selection.remove(item.text())
        self.refresh_avail()
        self.refresh_selected()
        
    def get_selection(self):
        items = []
        for i in range(self.list_selected.count()):
            items.append(self.list_selected.item(i).text())
        return items

class ExportSplitDialog(QDialog):
    def __init__(self, total_measures, parent=None):
        super().__init__(parent)
        self.setWindowTitle("导出设置")
        self.total_measures = total_measures
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.measures_per_file = QDoubleSpinBox()
        self.measures_per_file.setRange(1, 1000)
        self.measures_per_file.setValue(20.0)
        self.measures_per_file.setDecimals(0)
        form.addRow("每个文件包含小节数:", self.measures_per_file)
        
        self.lbl_info = QLabel(f"总小节数: {self.total_measures}")
        form.addRow(self.lbl_info)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def get_data(self):
        return int(self.measures_per_file.value())
