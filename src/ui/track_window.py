from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
                               QLabel, QPushButton, QSplitter, QFrame, QMenu,
                               QGraphicsView, QGraphicsScene, QGraphicsItem, 
                               QGraphicsRectItem, QGraphicsTextItem, QApplication,
                               QGraphicsPathItem, QInputDialog, QDialog, QDoubleSpinBox, QDialogButtonBox, QFormLayout,
                               QGraphicsLineItem)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QSize, QMimeData, QTimer, QEvent
from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, QWheelEvent, QMouseEvent, 
                           QPainterPath, QDragEnterEvent, QDropEvent, QIcon, QLinearGradient,
                           QPolygonF)

from core.models import Project, Track, Sequence, Keyframe, CurveType
from core.commands import PropertyChangeCommand, AddItemCommand, RemoveItemCommand, ReplaceItemCommand, KeyframeMoveCommand, SequenceMoveCommand, SequenceResizeCommand, BatchCommand
import os
import wave
import struct
import math
import hashlib

def generate_laser_color(name):
    if not name:
        return QColor("#2b2b2b")
    # Use MD5 to get a deterministic hash
    hash_val = int(hashlib.md5(name.encode('utf-8')).hexdigest(), 16)
    hue = (hash_val % 360) / 360.0
    # Dark theme: Low Value (0.15-0.25), Moderate Saturation (0.3-0.5)
    # To make it distinct but dark.
    sat = 0.5 + ((hash_val % 100) / 500.0) # 0.3 - 0.5
    val = 0.25 + ((hash_val % 50) / 500.0) # 0.15 - 0.25
    return QColor.fromHsvF(hue, sat, val)

def get_param_color(param):
    """Get color for a parameter type (Lighter version for Dark Theme)"""
    real_param = param
    if param.startswith("offset_mode_"):
        real_param = param[12:]
    elif param.startswith("offset_"):
        real_param = param[7:]
        
    if "pos" in real_param: return "#A5D6A7" # Light Green
    elif "dir" in real_param: return "#90CAF9" # Light Blue
    elif "color" in real_param: return "#EF9A9A" # Light Red
    elif "brightness" in real_param: return "#FFF59D" # Light Yellow
    elif "thickness" in real_param: return "#FFCC80" # Light Orange
    elif "divergence" in real_param: return "#CE93D8" # Light Purple
    elif "attenuation" in real_param: return "#D7CCC8" # Light Brown
    elif "params" in real_param: return "#80DEEA" # Light Cyan
    elif "localUp" in real_param: return "#FFF59D" # Light Yellow (Same as Brightness or similar) -> Maybe Teal? "#80CBC4"
    elif "is_master" in real_param: return "#FFAB91" # Light Deep Orange
    
    return "#EEEEEE" # Default Light Grey

class TrackHeaderWidget(QWidget):
    """Single Track Header UI"""
    delete_requested = Signal()
    collapse_requested = Signal(str) # Emits laser name
    expand_requested = Signal(str) # Emits laser name

    def __init__(self, track: Track, is_group_header=False, laser_name="", parent=None, main_window=None):
        super().__init__(parent)
        self.track = track
        self.is_group_header = is_group_header
        self.laser_name = laser_name
        self.main_window = main_window
        
        self.setFixedHeight(track.height)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Icon / Menu Button
        self.btn_icon = QPushButton("G" if is_group_header else ("P" if track.track_type == "param" else "A"))
        self.btn_icon.setFixedSize(24, 24)
        
        if is_group_header:
             self.btn_icon.setStyleSheet("background-color: #7E57C2; color: white; border-radius: 4px;")
        elif track.track_type == "audio":
             self.btn_icon.setStyleSheet("background-color: #4CAF50; color: white; border-radius: 4px;")
        else:
             # Remove blue block, use transparent/dark background
             self.btn_icon.setStyleSheet("background-color: #444; color: #ddd; border-radius: 4px;")
        layout.addWidget(self.btn_icon)
        
        # Name
        if is_group_header:
            self.lbl_name = QLabel(laser_name)
            self.lbl_name.setStyleSheet("color: #ddd; font-weight: bold; font-size: 14px;")
            layout.addWidget(self.lbl_name)
        elif track.track_type == "param":
            # Determine display info
            display_name, text_color = self.get_param_display_info(track.target_param)
            
            # Use HBox for Laser Name + Param Name (Side by Side)
            name_layout = QHBoxLayout()
            name_layout.setSpacing(5)
            name_layout.setContentsMargins(0, 0, 0, 0)
            
            # Laser Name (Subtitle)
            lbl_laser = QLabel(track.target_laser)
            lbl_laser.setStyleSheet("color: #AAA; font-size: 14px;") # Lighter grey, bigger font
            name_layout.addWidget(lbl_laser)
            
            # Param Name (Title)
            self.lbl_name = QLabel(display_name)
            self.lbl_name.setStyleSheet(f"color: {text_color}; font-weight: bold; font-size: 15px;") # Bigger font
            name_layout.addWidget(self.lbl_name)
            
            layout.addLayout(name_layout)
        else:
            self.lbl_name = QLabel(track.name)
            self.lbl_name.setStyleSheet("color: #ddd; font-weight: bold; font-size: 14px;")
            layout.addWidget(self.lbl_name)
        
        layout.addStretch()
        
        # Enable Toggle (Only for individual tracks)
        if not is_group_header:
            self.btn_enable = QPushButton("On" if track.enabled else "Off")
            self.btn_enable.setCheckable(True)
            self.btn_enable.setChecked(track.enabled)
            self.btn_enable.setFixedSize(30, 20)
            self.btn_enable.clicked.connect(self.toggle_enable)
            self.btn_enable.setStyleSheet("""
                QPushButton { background-color: #444; border: none; color: #aaa; }
                QPushButton:checked { background-color: #00AA00; color: white; }
            """)
            layout.addWidget(self.btn_enable)
        
        # Styling
        bg_color = QColor("#333") # Default for group
        if not is_group_header:
            bg_color = generate_laser_color(track.target_laser)
            if track.track_type == "audio":
                bg_color = QColor("#2b2b2b")
            
        self.setStyleSheet(f"background-color: {bg_color.name()}; border-bottom: 1px solid #111;")

    def mouseDoubleClickEvent(self, event):
        if self.is_group_header:
            self.expand_requested.emit(self.laser_name)
        super().mouseDoubleClickEvent(event)

    def get_param_display_info(self, param):
        prefix = ""
        real_param = param
        
        if param.startswith("offset_mode_"):
            prefix = "模式: "
            real_param = param[12:]
        elif param.startswith("offset_"):
            prefix = "偏移: "
            real_param = param[7:]
            
        # Map
        map_dict = {
            "pos.x": "位置 X", "pos.y": "位置 Y", "pos.z": "位置 Z",
            "dir.x": "方向 X", "dir.y": "方向 Y", "dir.z": "方向 Z",
            "color.r": "颜色 R", "color.g": "颜色 G", "color.b": "颜色 B",
            "brightness": "亮度", "thickness": "粗细", "divergence": "发散角",
            "attenuation": "衰减",
            "params.x": "Param X", "params.y": "Param Y", "params.z": "Param Z", "params.w": "Param W",
            "localUp.x": "旋转轴 X", "localUp.y": "旋转轴 Y", "localUp.z": "旋转轴 Z",
            "is_master": "主控开关",
            "type": "类型"
        }
        
        name = map_dict.get(real_param, real_param)
        final_name = prefix + name
        
        # Color
        color = get_param_color(param)
        
        return final_name, color


    def toggle_enable(self, checked):
        if self.main_window:
            from core.commands import PropertyChangeCommand
            cmd = PropertyChangeCommand(self.track, "enabled", not checked, checked, "切换轨道启用状态", self.main_window)
            self.main_window.undo_stack.push(cmd)
        else:
            self.track.enabled = checked
            self.btn_enable.setText("On" if checked else "Off")
            p = self.parent()
            while p:
                if isinstance(p, TrackWindow):
                    p.data_changed.emit()
                    break
                p = p.parent()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        
        if self.is_group_header:
            act_expand = menu.addAction("展开轨道")
            act_expand.triggered.connect(lambda: self.expand_requested.emit(self.laser_name))
        else:
            act_rename = menu.addAction("重命名")
            act_rename.triggered.connect(self.rename_track)
            
            if self.track.track_type == "param":
                act_range = menu.addAction("设置参数范围")
                act_range.triggered.connect(self.set_range)
                
                # Collapse Option
                act_collapse = menu.addAction("折叠相同光源轨道")
                act_collapse.triggered.connect(lambda: self.collapse_requested.emit(self.track.target_laser))
            
            menu.addSeparator()
            act_del = menu.addAction("删除")
            act_del.triggered.connect(self.delete_requested.emit)
            
        menu.exec(event.globalPos())

    def rename_track(self):
        name, ok = QInputDialog.getText(self, "重命名轨道", "新名称:", text=self.track.name)
        if ok and name and name != self.track.name:
            if self.main_window:
                cmd = PropertyChangeCommand(self.track, "name", self.track.name, name, f"重命名轨道 {self.track.name}", self.main_window)
                self.main_window.undo_stack.push(cmd)
            else:
                self.track.name = name
                self.lbl_name.setText(name)
                p = self.parent()
                while p:
                    if isinstance(p, TrackWindow):
                        p.data_changed.emit()
                        break
                    p = p.parent()
            
    def set_range(self):
        dlg = RangeDialog(self.track.min_val, self.track.max_val, self)
        if dlg.exec():
            min_v, max_v = dlg.get_values()
            if min_v == self.track.min_val and max_v == self.track.max_val: return
            
            if self.main_window:
                cmd1 = PropertyChangeCommand(self.track, "min_val", self.track.min_val, min_v, "修改范围下限", self.main_window)
                cmd2 = PropertyChangeCommand(self.track, "max_val", self.track.max_val, max_v, "修改范围上限", self.main_window)
                batch = BatchCommand([cmd1, cmd2], f"修改轨道 {self.track.name} 范围", self.main_window)
                self.main_window.undo_stack.push(batch)
            else:
                self.track.min_val = min_v
                self.track.max_val = max_v
                p = self.parent()
                while p:
                    if isinstance(p, TrackWindow):
                        p.refresh_tracks()
                        if hasattr(p, 'data_changed'):
                            p.data_changed.emit()
                        break
                    p = p.parent()

class RangeDialog(QDialog):
    def __init__(self, min_v, max_v, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置参数范围")
        layout = QFormLayout(self)
        self.spin_min = QDoubleSpinBox()
        self.spin_min.setRange(-99999, 99999)
        self.spin_min.setValue(min_v)
        self.spin_max = QDoubleSpinBox()
        self.spin_max.setRange(-99999, 99999)
        self.spin_max.setValue(max_v)
        layout.addRow("最小值:", self.spin_min)
        layout.addRow("最大值:", self.spin_max)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
    def get_values(self):
        return self.spin_min.value(), self.spin_max.value()

class StyledInputDialog(QDialog):
    def __init__(self, title, label, value, min_val, max_val, decimals=4, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        
        layout = QVBoxLayout(self)
        
        lbl = QLabel(label)
        layout.addWidget(lbl)
        
        self.spin = QDoubleSpinBox()
        self.spin.setRange(min_val, max_val)
        self.spin.setDecimals(decimals)
        self.spin.setValue(value)
        layout.addWidget(self.spin)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
        # Simple styling to match dark theme if not inherited
        # Assuming parent is window or has stylesheet, but explicitly:
        self.setStyleSheet("""
            QDialog { background-color: #333; color: #ddd; }
            QLabel { color: #ddd; }
            QDoubleSpinBox { background-color: #222; color: #ddd; border: 1px solid #555; padding: 2px; }
            QPushButton { background-color: #444; color: #ddd; border: 1px solid #555; padding: 4px 8px; }
            QPushButton:hover { background-color: #555; }
        """)

    def get_value(self):
        return self.spin.value()

class KeyframeItem(QGraphicsItem):
    def __init__(self, keyframe: Keyframe, track: Track, pixels_per_beat, parent=None):
        super().__init__(parent)
        self.keyframe = keyframe
        self.track = track
        self.pixels_per_beat = pixels_per_beat
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        
        self.drag_start_time = keyframe.time
        self.drag_start_val = keyframe.value
        
        self.radius = 4
        self.update_pos()
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_time = self.keyframe.time
            self.drag_start_val = self.keyframe.value
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton and hasattr(self, 'drag_start_time'):
            new_time = self.keyframe.time
            new_val = self.keyframe.value
            if abs(new_time - self.drag_start_time) > 0.001 or abs(new_val - self.drag_start_val) > 0.001:
                main_window = None
                if self.scene() and hasattr(self.scene(), 'main_window'):
                    main_window = self.scene().main_window
                if main_window:
                    self.keyframe.time = self.drag_start_time
                    self.keyframe.value = self.drag_start_val
                    cmd = KeyframeMoveCommand(self.keyframe, self.drag_start_time, self.drag_start_val, new_time, new_val, "移动关键帧", main_window)
                    main_window.undo_stack.push(cmd)
            self.drag_start_time = self.keyframe.time
            self.drag_start_val = self.keyframe.value
        
    def boundingRect(self):
        # Slightly larger rect for better hit testing
        # Increase even more for Start/End anchors?
        base_radius = self.radius + 2
        
        # Check if start/end without expensive lookups if possible?
        # Just use larger rect for all for now, to be safe and responsive.
        # User asked for "Start and End anchor range larger".
        # Let's check if it is start/end
        try:
            if self.track.keyframes:
                if self.keyframe == self.track.keyframes[0] or self.keyframe == self.track.keyframes[-1]:
                     base_radius += 4 # Extra padding
        except:
            pass
            
        return QRectF(-base_radius, -base_radius, base_radius*2, base_radius*2)
        
    def paint(self, painter, option, widget=None):
        painter.setBrush(QBrush(QColor(255, 255, 0)) if self.isSelected() else QBrush(QColor(200, 200, 200)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(0,0), self.radius, self.radius)
        
    def hoverEnterEvent(self, event):
        self.setCursor(Qt.PointingHandCursor)
        self.radius = 6
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(Qt.ArrowCursor)
        self.radius = 4
        self.update()
        super().hoverLeaveEvent(event)

    def update_pos(self):
        x = self.keyframe.time * self.pixels_per_beat
        
        normalized = 0.0
        r = self.track.max_val - self.track.min_val
        if r != 0:
            normalized = (self.keyframe.value - self.track.min_val) / r
        
        normalized = max(0.0, min(1.0, normalized))
        
        y = self.track.height - (normalized * self.track.height)
        self.setPos(x, y)
        
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            if hasattr(self.scene(), 'data_changed'):
                self.scene().data_changed.emit()
            new_pos = value
            x = new_pos.x()
            y = new_pos.y()
            
            # Snap Logic
            if hasattr(self.scene(), 'snap_granularity'):
                snap_beats = self.scene().snap_granularity
                snap_pixels = snap_beats * self.pixels_per_beat
                if snap_pixels > 1:
                    x = round(x / snap_pixels) * snap_pixels

            # Constraints
            if y < 0: y = 0
            if y > self.track.height: y = self.track.height
            
            # Time Constraints
            try:
                if self.keyframe in self.track.keyframes:
                    idx = self.track.keyframes.index(self.keyframe)
                    is_start = (idx == 0)
                    is_end = (idx == len(self.track.keyframes) - 1)
                    
                    if is_start:
                        x = 0 
                    elif is_end:
                        # End anchor can be moved horizontally? 
                        # User requirement: "Start and End anchor cannot be dragged horizontally"
                        # But previous logic allowed it for end?
                        # User: "开始锚点和结束锚点不可横向拖拽" -> Start/End Locked horizontally.
                        # So x is fixed to current time.
                        x = self.keyframe.time * self.pixels_per_beat
                    else:
                        prev_time = self.track.keyframes[idx-1].time
                        next_time = self.track.keyframes[idx+1].time
                        
                        min_x = prev_time * self.pixels_per_beat + 1
                        max_x = next_time * self.pixels_per_beat - 1
                        
                        if x < min_x: x = min_x
                        if x > max_x: x = max_x
            except ValueError:
                pass

            new_pos.setX(x)
            new_pos.setY(y)
            
            # Update Model
            self.keyframe.time = x / self.pixels_per_beat
            
            normalized = (self.track.height - y) / self.track.height
            r = self.track.max_val - self.track.min_val
            self.keyframe.value = self.track.min_val + (normalized * r)
            
            if self.parentItem() and hasattr(self.parentItem(), 'update_curve'):
                 self.parentItem().update_curve()
                 
            return new_pos
            
        return super().itemChange(change, value)

    def contextMenuEvent(self, event):
        # Find view to use as parent for styling
        view = None
        if self.scene() and self.scene().views():
            view = self.scene().views()[0]
            
        menu = QMenu(view) if view else QMenu()
        
        # Determine if we can set curve (if we have a previous keyframe)
        idx = -1
        try:
            idx = self.track.keyframes.index(self.keyframe)
        except ValueError:
            pass
            
        # Curve Type Menu (Affects segment ending at this keyframe, so modifies prev_kf)
        # Requirement: "Start anchor disabled".
        # If idx == 0, we are Start Anchor. We have no previous segment.
        if idx > 0:
            prev_kf = self.track.keyframes[idx-1]
            curve_menu = menu.addMenu("曲线类型")
            
            def add_curve_action(name, ctype):
                act = curve_menu.addAction(name)
                act.setCheckable(True)
                act.setChecked(prev_kf.curve_type == ctype)
                def set_curve():
                    if view and hasattr(view.scene(), 'main_window') and view.scene().main_window:
                        main_window = view.scene().main_window
                        cmd = PropertyChangeCommand(prev_kf, "curve_type", prev_kf.curve_type, ctype, "修改曲线类型", main_window)
                        main_window.undo_stack.push(cmd)
                    else:
                        prev_kf.curve_type = ctype
                        if self.parentItem() and hasattr(self.parentItem(), 'update_curve'):
                             self.parentItem().update_curve()
                        if self.scene() and hasattr(self.scene(), 'data_changed'):
                            self.scene().data_changed.emit()
                act.triggered.connect(set_curve)
                
            add_curve_action("平滑 Smooth", CurveType.SMOOTH)
            add_curve_action("保持 Hold", CurveType.HOLD)
            add_curve_action("单曲线 Single Curve", CurveType.SINGLE_CURVE)
            add_curve_action("梯度 Stairs", CurveType.STAIRS)
            add_curve_action("平滑梯度 Smooth Stairs", CurveType.SMOOTH_STAIRS)
            add_curve_action("脉冲波 Pulse", CurveType.PULSE)
            add_curve_action("三角波 Wave", CurveType.WAVE)
            
        # Value Actions
        act_val = menu.addAction("输入参数值...")
        act_val.triggered.connect(self.input_value)
        
        act_copy = menu.addAction("复制参数值")
        act_copy.triggered.connect(self.copy_value)
        
        act_paste = menu.addAction("粘贴参数值")
        act_paste.triggered.connect(self.paste_value)
        
        menu.addSeparator()
        
        act_del = menu.addAction("删除锚点")
        act_del.triggered.connect(self.delete_self)
        
        if idx == 0 or idx == len(self.track.keyframes) - 1:
            act_del.setEnabled(False)
        if len(self.track.keyframes) <= 2:
            act_del.setEnabled(False)
            
        menu.exec(event.screenPos())

    def input_value(self):
        # Find view for parenting
        view = None
        if self.scene() and self.scene().views():
            view = self.scene().views()[0]

        dlg = StyledInputDialog("输入值", "参数值:", self.keyframe.value, self.track.min_val, self.track.max_val, 4, parent=view)
        if dlg.exec():
            val = dlg.get_value()
            if val == self.keyframe.value: return
            main_window = view.scene().main_window if view and hasattr(view.scene(), 'main_window') else None
            if main_window:
                cmd = PropertyChangeCommand(self.keyframe, "value", self.keyframe.value, val, "输入关键帧值", main_window)
                main_window.undo_stack.push(cmd)
            else:
                self.keyframe.value = val
                self.update_pos()
                if self.parentItem() and hasattr(self.parentItem(), 'update_curve'):
                    self.parentItem().update_curve()
                if self.scene() and hasattr(self.scene(), 'data_changed'):
                    self.scene().data_changed.emit()

    def mouseDoubleClickEvent(self, event):
        self.input_value()
        event.accept()

    def copy_value(self):
        QApplication.clipboard().setText(str(self.keyframe.value))
        
    def paste_value(self):
        text = QApplication.clipboard().text()
        try:
            val = float(text)
            val = max(self.track.min_val, min(self.track.max_val, val))
            if val == self.keyframe.value: return
            
            main_window = self.scene().main_window if self.scene() and hasattr(self.scene(), 'main_window') else None
            if main_window:
                cmd = PropertyChangeCommand(self.keyframe, "value", self.keyframe.value, val, "粘贴关键帧值", main_window)
                main_window.undo_stack.push(cmd)
            else:
                self.keyframe.value = val
                self.update_pos()
                if self.parentItem() and hasattr(self.parentItem(), 'update_curve'):
                    self.parentItem().update_curve()
        except ValueError:
            pass


    def delete_self(self):
        if self.keyframe in self.track.keyframes:
            idx = self.track.keyframes.index(self.keyframe)
            
            main_window = self.scene().main_window if self.scene() and hasattr(self.scene(), 'main_window') else None
            
            if main_window:
                commands = []
                if idx > 0 and idx < len(self.track.keyframes) - 1:
                    prev_kf = self.track.keyframes[idx-1]
                    commands.append(PropertyChangeCommand(prev_kf, "curve_type", prev_kf.curve_type, self.keyframe.curve_type, "", main_window))
                    commands.append(PropertyChangeCommand(prev_kf, "tension", prev_kf.tension, self.keyframe.tension, "", main_window))
                
                commands.append(RemoveItemCommand(self.track.keyframes, idx, self.keyframe, "删除关键帧", main_window))
                batch = BatchCommand(commands, "删除关键帧", main_window)
                main_window.undo_stack.push(batch)
            else:
                # Transfer curve properties to previous keyframe if applicable
                if idx > 0 and idx < len(self.track.keyframes) - 1:
                    prev_kf = self.track.keyframes[idx-1]
                    prev_kf.curve_type = self.keyframe.curve_type
                    prev_kf.tension = self.keyframe.tension
    
                self.track.keyframes.remove(self.keyframe)
                
                # Capture parent before removing from scene to ensure update_curve works
                parent = self.parentItem()
                
                if self.scene():
                    self.scene().removeItem(self)
                    if hasattr(self.scene(), 'data_changed'):
                        self.scene().data_changed.emit()
                    
                # Force full curve update
                if parent and hasattr(parent, 'update_curve'):
                    parent.update_curve()
                    
                # Remove from parent's list if possible (cleanup)
                if parent and hasattr(parent, 'keyframe_items'):
                    if self in parent.keyframe_items:
                        parent.keyframe_items.remove(self)

class TensionHandleItem(QGraphicsItem):
    """Handle for adjusting tension between two keyframes"""
    def __init__(self, keyframe: Keyframe, next_keyframe: Keyframe, track: Track, p1: QPointF, p2: QPointF, parent=None):
        super().__init__(parent)
        self.keyframe = keyframe # The keyframe that holds the tension value
        self.next_keyframe = next_keyframe
        self.track = track
        self.p1 = p1
        self.p2 = p2
        
        self.radius = 3
        # Enable drag interaction as per user request
        # Fix: Disable ItemIsMovable to keep handle visually fixed, handle mouse manually
        self.setFlag(QGraphicsItem.ItemIsMovable, False) 
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, False) # No need since position is fixed
        self.setAcceptHoverEvents(True)
        self.setVisible(False) # Hidden by default
        
        # Calculate initial position based on tension
        self.update_pos_from_tension()

    def update_pos_from_tension(self):
        # Tension defines the control point height relative to midpoint
        # We visualize tension as a vertical offset from the linear segment midpoint
        
        mid_x = (self.p1.x() + self.p2.x()) / 2
        mid_y = (self.p1.y() + self.p2.y()) / 2
        
        # Per requirement: "拖拽张力控制点不改变其位置，保持在两个锚点的中点位置即可"
        # So we simply place it at midpoint. The curve visualization shows the tension.
        
        self.setPos(mid_x, mid_y)

    def contextMenuEvent(self, event):
        # Find view for parenting
        view = None
        if self.scene() and self.scene().views():
            view = self.scene().views()[0]
            
        menu = QMenu(view) if view else QMenu()
        
        act_input = menu.addAction("输入张力值")
        act_input.triggered.connect(self.input_value)
        
        act_copy = menu.addAction("复制值")
        act_copy.triggered.connect(self.copy_value)
        
        act_paste = menu.addAction("粘贴值")
        act_paste.triggered.connect(self.paste_value)
        
        menu.exec(event.screenPos())

    def input_value(self):
        # Find view for parenting
        view = None
        if self.scene() and self.scene().views():
            view = self.scene().views()[0]

        # Use -1.0 to 1.0 as the universal tension range for UI
        dlg = StyledInputDialog("输入张力值", "张力 (-1.0 ~ 1.0):", self.keyframe.tension, -1.0, 1.0, 4, parent=view)
        if dlg.exec():
            val = dlg.get_value()
            if val == self.keyframe.tension: return
            main_window = self.scene().main_window if self.scene() and hasattr(self.scene(), 'main_window') else None
            if main_window:
                cmd = PropertyChangeCommand(self.keyframe, "tension", self.keyframe.tension, val, "输入张力值", main_window)
                main_window.undo_stack.push(cmd)
            else:
                self.keyframe.tension = val
                self.update_pos_from_tension()
                if self.parentItem() and hasattr(self.parentItem(), 'update_curve'):
                    self.parentItem().update_curve()
                if self.scene() and hasattr(self.scene(), 'data_changed'):
                    self.scene().data_changed.emit()

    def mouseDoubleClickEvent(self, event):
        self.input_value()
        event.accept()

    def copy_value(self):
        QApplication.clipboard().setText(str(self.keyframe.tension))

    def paste_value(self):
        text = QApplication.clipboard().text()
        try:
            val = float(text)
            val = max(-1.0, min(1.0, val)) # Clamp to valid range
            if val == self.keyframe.tension: return
            main_window = self.scene().main_window if self.scene() and hasattr(self.scene(), 'main_window') else None
            if main_window:
                cmd = PropertyChangeCommand(self.keyframe, "tension", self.keyframe.tension, val, "粘贴张力值", main_window)
                main_window.undo_stack.push(cmd)
            else:
                self.keyframe.tension = val
                self.update_pos_from_tension()
                if self.parentItem() and hasattr(self.parentItem(), 'update_curve'):
                    self.parentItem().update_curve()
        except ValueError:
            pass

    def mousePressEvent(self, event):
        # Consume event to prevent insertion in parent
        # Fix: Deselect all other items to prevent them from moving with this handle
        if self.scene():
            self.scene().clearSelection()
            
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.last_mouse_y = event.scenePos().y()
            self.start_tension = self.keyframe.tension
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if hasattr(self, 'is_dragging') and self.is_dragging:
            current_y = event.scenePos().y()
            diff_y = current_y - self.last_mouse_y
            
            # Sensitivity: Track height / 2 = Full range (approx)
            scale = self.track.height / 2.0
            if scale == 0: scale = 1.0
            
            # Move Up (Negative Diff) -> Increase Tension (Curve Up)
            # So tension change = -diff / scale
            delta_tension = -diff_y / scale
            
            new_tension = self.start_tension + delta_tension
            new_tension = max(-1.0, min(1.0, new_tension))
            
            if new_tension != self.keyframe.tension:
                self.keyframe.tension = new_tension
                # Don't update position (keep at center), but update curve
                if self.parentItem() and hasattr(self.parentItem(), 'update_curve'):
                    self.parentItem().update_curve(dragging_handle=self)
            
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            
            main_window = self.scene().main_window if self.scene() and hasattr(self.scene(), 'main_window') else None
            if main_window and hasattr(self, 'start_tension'):
                new_tension = self.keyframe.tension
                if abs(new_tension - self.start_tension) > 0.001:
                    self.keyframe.tension = self.start_tension
                    cmd = PropertyChangeCommand(self.keyframe, "tension", self.start_tension, new_tension, "调整张力", main_window)
                    main_window.undo_stack.push(cmd)
            
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def boundingRect(self):
        return QRectF(-self.radius-2, -self.radius-2, self.radius*2+4, self.radius*2+4)

    def paint(self, painter, option, widget=None):
        painter.setBrush(QBrush(QColor(100, 200, 255)))
        painter.setPen(Qt.NoPen)
        # Draw Diamond
        path = QPainterPath()
        path.moveTo(0, -self.radius)
        path.lineTo(self.radius, 0)
        path.lineTo(0, self.radius)
        path.lineTo(-self.radius, 0)
        path.closeSubpath()
        painter.drawPath(path)

    def hoverEnterEvent(self, event):
        self.setCursor(Qt.PointingHandCursor)
        self.radius = 5
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(Qt.ArrowCursor)
        self.radius = 3
        self.update()
        super().hoverLeaveEvent(event)
        
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            if hasattr(self.scene(), 'data_changed'):
                self.scene().data_changed.emit()
            new_pos = value
            
            # Lock X to midpoint (Vertical drag only)
            mid_x = (self.p1.x() + self.p2.x()) / 2
            new_pos.setX(mid_x)
            
            # Calculate new tension
            mid_y = (self.p1.y() + self.p2.y()) / 2
            y_diff = new_pos.y() - mid_y
            
            scale = self.track.height / 2.0
            if scale == 0: scale = 1
            
            # Inverse of offset_y = -tension * scale
            # tension = -offset_y / scale
            new_tension = -y_diff / scale
            
            # Clamp -1 to 1
            new_tension = max(-1.0, min(1.0, new_tension))
            self.keyframe.tension = new_tension
            
            # Also clamp the visual position to the valid range
            clamped_offset_y = -new_tension * scale
            new_pos.setY(mid_y + clamped_offset_y)
            
            # Update Parent Curve
            if self.parentItem() and hasattr(self.parentItem(), 'update_curve'):
                 # Pass source=self to avoid recreating THIS handle while dragging it
                 self.parentItem().update_curve(dragging_handle=self)
            
            return new_pos
            
        return super().itemChange(change, value)

class ResizeHandle(QGraphicsRectItem):
    """Handle for resizing/cropping sequences"""
    def __init__(self, parent, is_left=True):
        super().__init__(parent)
        self.is_left = is_left
        self.parent_item = parent
        self.setWidth(6)
        self.setCursor(Qt.SizeHorCursor)
        self.setBrush(QBrush(QColor(255, 255, 255, 100)))
        self.setPen(Qt.NoPen)
        self.setFlag(QGraphicsItem.ItemIsMovable, False) # We handle mouse events manually or allow move but restricted
        
    def setWidth(self, width):
        self.setRect(0, 0, width, self.parent_item.rect().height())
        if not self.is_left:
            self.setPos(self.parent_item.rect().width() - width, 0)
        else:
            self.setPos(0, 0)

    def mousePressEvent(self, event):
        self.start_x = event.scenePos().x()
        self.start_rect = self.parent_item.rect()
        self.start_pos = self.parent_item.pos()
        self.start_seq_start = self.parent_item.sequence.start_time
        self.start_seq_dur = self.parent_item.sequence.duration
        self.start_seq_offset = self.parent_item.sequence.audio_offset
        event.accept()

    def mouseMoveEvent(self, event):
        diff = event.scenePos().x() - self.start_x
        ppb = self.parent_item.pixels_per_beat
        beat_diff = diff / ppb
        
        # Snap logic could apply here too, but smooth resize is often preferred. 
        # User asked for snap dragging, maybe resize too? Let's apply snap to beat_diff if close?
        # For now, continuous resize is standard for cropping.
        
        if self.is_left:
            # Moving left handle:
            # 1. Start time changes (+beat_diff)
            # 2. Duration changes (-beat_diff)
            # 3. Audio Offset changes (+beat_diff) (if audio)
            
            new_start = self.start_seq_start + beat_diff
            new_dur = self.start_seq_dur - beat_diff
            
            # Limits
            if new_dur < 0.1: # Minimum duration
                new_start = self.start_seq_start + self.start_seq_dur - 0.1
                new_dur = 0.1
            if new_start < 0:
                new_start = 0
                new_dur = self.start_seq_dur + self.start_seq_start # Correct duration for start=0
            
            # Apply
            self.parent_item.sequence.start_time = new_start
            self.parent_item.sequence.duration = new_dur
            self.parent_item.sequence.audio_offset = max(0, self.start_seq_offset + (new_start - self.start_seq_start))
            
        else:
            # Moving right handle:
            # 1. Duration changes (+beat_diff)
            new_dur = self.start_seq_dur + beat_diff
            if new_dur < 0.1:
                new_dur = 0.1
            self.parent_item.sequence.duration = new_dur
            
        self.parent_item.update_geometry()
        event.accept()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        
        main_window = None
        if self.parent_item and self.parent_item.scene() and hasattr(self.parent_item.scene(), 'main_window'):
            main_window = self.parent_item.scene().main_window
            
        if main_window and hasattr(self, 'start_seq_start'):
            new_start = self.parent_item.sequence.start_time
            new_dur = self.parent_item.sequence.duration
            new_offset = self.parent_item.sequence.audio_offset
            
            if abs(new_start - self.start_seq_start) > 0.001 or abs(new_dur - self.start_seq_dur) > 0.001 or abs(new_offset - self.start_seq_offset) > 0.001:
                # Restore old and push command
                self.parent_item.sequence.start_time = self.start_seq_start
                self.parent_item.sequence.duration = self.start_seq_dur
                self.parent_item.sequence.audio_offset = self.start_seq_offset
                
                cmd = SequenceResizeCommand(self.parent_item.sequence, self.start_seq_start, self.start_seq_dur, self.start_seq_offset, 
                                          new_start, new_dur, new_offset, "缩放片段", main_window)
                main_window.undo_stack.push(cmd)

class BaseSequenceItem(QGraphicsRectItem):
    """Base class for sequence items with shared logic"""
    def __init__(self, sequence: Sequence, track_height, pixels_per_beat, parent=None):
        super().__init__(parent)
        self.sequence = sequence
        self.pixels_per_beat = pixels_per_beat
        self.track_height = track_height
        self.snap_granularity = 1.0 # Default
        
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        
        self.drag_start_time = sequence.start_time

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_time = self.sequence.start_time
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton and hasattr(self, 'drag_start_time'):
            new_start = self.sequence.start_time
            if abs(new_start - self.drag_start_time) > 0.001:
                # Find main_window
                main_window = None
                if self.scene() and hasattr(self.scene(), 'main_window'):
                    main_window = self.scene().main_window
                if main_window:
                    # Restore old and push command
                    self.sequence.start_time = self.drag_start_time
                    cmd = SequenceMoveCommand(self.sequence, self.drag_start_time, new_start, "移动片段", main_window)
                    main_window.undo_stack.push(cmd)
            self.drag_start_time = self.sequence.start_time
        
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            if hasattr(self.scene(), 'data_changed'):
                self.scene().data_changed.emit()
            new_pos = value
            
            # 1. Vertical Lock (Y must be 0 relative to parent lane/track)
            # However, if we are in a scene directly (not nested in a lane item that moves), we need to check parent.
            # In current design, items are children of TrackLaneItem (which is at y=0 relative to itself? No, lane is at y=track_y)
            # Actually, SequenceItem is child of TrackLaneItem. So pos.y() should be 0 (or 1 for margin).
            new_pos.setY(1) # Lock to row y=1
            
            # 2. Horizontal Snap
            x = new_pos.x()
            snap_pixels = self.pixels_per_beat * self.snap_granularity
            if snap_pixels > 0:
                x = round(x / snap_pixels) * snap_pixels
            
            # 3. Bounds (>= 0)
            if x < 0:
                x = 0
            
            new_pos.setX(x)
            
            # 4. Update Model (Critical for "Reset Bug")
            # We update the model immediately so if the view refreshes, it reads the new value.
            self.sequence.start_time = x / self.pixels_per_beat
            
            return new_pos
            
        return super().itemChange(change, value)

    def update_geometry(self):
        x = self.sequence.start_time * self.pixels_per_beat
        w = self.sequence.duration * self.pixels_per_beat
        self.setRect(0, 0, w, self.track_height - 1)
        self.setPos(x, 1)

class SequenceItem(BaseSequenceItem):
    """Visual representation of a Param Sequence"""
    HEADER_HEIGHT = 24

    def __init__(self, sequence: Sequence, track_height, pixels_per_beat, parent=None):
        super().__init__(sequence, track_height, pixels_per_beat, parent)
        self.update_geometry()
        
    def paint(self, painter, option, widget=None):
        # Clip Background
        rect = self.rect()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(60, 60, 70, 150))) # Semi-transparent background
        painter.drawRect(rect)
        
        # Header Background
        header_rect = QRectF(rect.x(), rect.y(), rect.width(), self.HEADER_HEIGHT)
        
        # Header Gradient
        grad = QLinearGradient(header_rect.topLeft(), header_rect.bottomLeft())
        grad.setColorAt(0, QColor(90, 90, 100))
        grad.setColorAt(1, QColor(70, 70, 80))
        painter.setBrush(grad)
        painter.drawRect(header_rect)
        
        # Header Border
        painter.setPen(QPen(QColor(100, 100, 110), 1))
        painter.drawLine(header_rect.bottomLeft(), header_rect.bottomRight())
        
        # Clip Border
        painter.setPen(QPen(QColor(80, 80, 90), 1))
        painter.drawRect(rect)
        
        # Text & Icon in Header
        painter.setPen(Qt.white)
        font = painter.font()
        font.setPixelSize(11)
        painter.setFont(font)
        
        # Simple Circle Icon
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(Qt.white, 1.5))
        painter.drawEllipse(rect.x() + 6, rect.y() + 6, 10, 10)
        painter.drawPoint(rect.x() + 11, rect.y() + 8) 
        painter.drawLine(rect.x() + 11, rect.y() + 11, rect.x() + 14, rect.y() + 14)
        
        painter.setPen(Qt.white)
        display_text = "Sequence"
        painter.drawText(rect.x() + 24, rect.y() + 16, display_text)
        
        # Draw Curve
        if self.sequence.keyframes:
            self.draw_curve(painter, rect)

    def draw_curve(self, painter, rect):
        path = QPainterPath()
        w = rect.width()
        h = rect.height() - self.HEADER_HEIGHT
        y_offset = self.HEADER_HEIGHT
        
        # Value 0..1 -> h..0 (relative to y_offset)
        
        first = True
        for kf in self.sequence.keyframes:
            kx = (kf.time / self.sequence.duration) * w
            val = kf.value
            val = max(0.0, min(1.0, val))
            ky = y_offset + h - (val * h)
            
            if first:
                path.moveTo(kx, ky)
                first = False
            else:
                path.lineTo(kx, ky)
                
            # Draw Anchor Point
            painter.setBrush(QColor(200, 200, 200))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(kx, ky), 3, 3)
        
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(255, 150, 150), 2))
        painter.drawPath(path)

class AudioSequenceItem(BaseSequenceItem):
    """Visual representation of an Audio Clip"""
    
    # ADJUST THIS VALUE FOR WAVEFORM PRECISION (Higher = More detailed but slower)
    WAVEFORM_RESOLUTION = 3000
    
    def __init__(self, sequence: Sequence, track_height, pixels_per_beat, bpm=120.0, parent=None):
        self.bpm = bpm
        super().__init__(sequence, track_height, pixels_per_beat, parent)
        
        self.setBrush(QBrush(QColor(40, 80, 40)))
        
        # Resize Handles
        self.handle_left = ResizeHandle(self, is_left=True)
        self.handle_right = ResizeHandle(self, is_left=False)
        
        self.waveform_polygon = QPolygonF()
        self.generate_waveform()
        self.update_geometry()

    def update_geometry(self):
        super().update_geometry()
        # Update handles
        if hasattr(self, 'handle_left'):
            self.handle_left.setWidth(6)
            self.handle_right.setWidth(6)
        
        # If pixels_per_beat changed significantly, we might want to regenerate waveform
        # but for performance, we might just scale the existing polygon in paint.
        # However, if we zoom in a lot, we need more detail.
        # For now, let's regenerate if we don't have one.
        if self.waveform_polygon.isEmpty():
             self.generate_waveform()

    def generate_waveform(self):
        if not self.sequence.audio_file or not os.path.exists(self.sequence.audio_file):
            return
            
        try:
            with wave.open(self.sequence.audio_file, 'rb') as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                n_frames = wf.getnframes()
                
                # We want to generate a visual waveform.
                # We can't draw every sample.
                # Let's target ~100 points per visual beat for high detail, or based on pixel width.
                # Total beats duration of file:
                total_seconds = n_frames / framerate
                total_beats = (total_seconds * self.bpm) / 60.0
                
                # Current Pixel Width of the WHOLE file (not just the sequence crop)
                total_pixels = total_beats * self.pixels_per_beat
                
                # Limit resolution to avoid massive memory usage
                # If total_pixels is huge, we step
                samples_per_pixel = n_frames / max(1, total_pixels)
                
                # Read data
                # For large files, reading all at once is bad.
                # But for typical track usage (3-5 mins), it's ~30-50MB for wav. Manageable.
                # Let's try reading all for simplicity, or chunk.
                
                # Optimization: Read only what we need? 
                # But we might scroll/zoom.
                # Let's bin the data.
                
                # Determine step size (frames to skip)
                # We want e.g. 1 point per pixel.
                step = int(samples_per_pixel)
                if step < 1: step = 1
                
                dtype = None
                if sampwidth == 1: dtype = 'B' # unsigned char
                elif sampwidth == 2: dtype = 'h' # short
                elif sampwidth == 4: dtype = 'i' # int
                
                if not dtype:
                    return # Unsupported bit depth
                
                # Max Samples to process (limit to ~20000 points for UI responsiveness)
                target_points = self.WAVEFORM_RESOLUTION
                if total_pixels > target_points:
                    step = int(n_frames / target_points)
                
                self.waveform_polygon = QPolygonF()
                
                # Read chunks
                wf.rewind()
                
                # We will just take the max amplitude in each chunk
                frames_to_read = n_frames
                raw_data = wf.readframes(frames_to_read)
                
                total_samples = len(raw_data) // sampwidth
                
                # We only process channel 0 for mono visualization
                # Stride = n_channels
                
                points = []
                
                # Python loop is slow for millions of points. 
                # We need a faster way or just very coarse approximation.
                # Let's take a sample every 'step' frames.
                
                mid_y = self.track_height / 2.0
                max_amp = pow(2, 8 * sampwidth - 1)
                scale_y = (self.track_height * 0.45) / max_amp
                
                import struct
                
                iter_step = step * n_channels * sampwidth
                
                # Base X in beats
                # We map frame_index -> beat -> pixel
                
                # We'll create a simplified polygon: (time_in_beats, amplitude_normalized)
                # Later paint will map this to x,y
                
                for i in range(0, len(raw_data), iter_step):
                    # Safety check
                    if i + sampwidth > len(raw_data): break
                    
                    sample_bytes = raw_data[i:i+sampwidth]
                    val = struct.unpack(f"<{dtype}", sample_bytes)[0]
                    
                    # If 8-bit, it's unsigned 0-255, center is 128
                    if sampwidth == 1:
                        val = val - 128
                        
                    # Frame index
                    frame_idx = i // (n_channels * sampwidth)
                    time_sec = frame_idx / framerate
                    time_beat = (time_sec * self.bpm) / 60.0
                    
                    points.append(QPointF(time_beat, val * scale_y))
                
                self.waveform_points = points
                
        except Exception as e:
            print(f"Waveform generation failed: {e}")

    def paint(self, painter, option, widget=None):
        rect = self.rect()
        
        # Background
        painter.setPen(QPen(QColor(60, 100, 60), 1))
        painter.setBrush(QBrush(QColor(30, 60, 30)))
        painter.drawRoundedRect(rect, 4, 4)
        
        # Clip to rect
        painter.setClipRect(rect)
        
        # Draw Waveform
        if hasattr(self, 'waveform_points') and self.waveform_points:
            painter.setPen(QPen(QColor(120, 200, 120), 1))
            painter.setBrush(Qt.NoBrush)
            
            mid_y = rect.center().y()
            
            # Transform points to current view
            # point.x is time in beats.
            # We need to map: 
            #   audio_file_time = point.x
            #   sequence_local_time = audio_file_time - self.sequence.audio_offset
            #   if sequence_local_time < 0 or > duration: skip
            #   pixel_x = rect.x() + (sequence_local_time * self.pixels_per_beat)
            
            path = QPainterPath()
            first = True
            
            offset = self.sequence.audio_offset
            dur = self.sequence.duration
            
            start_x = rect.x()
            
            # Optimization: Only draw points within visible range?
            # For now draw all that fit in duration
            
            for pt in self.waveform_points:
                beat_time = pt.x()
                
                # Check if inside the cropped region
                if beat_time < offset: continue
                if beat_time > offset + dur: break
                
                rel_time = beat_time - offset
                px = start_x + (rel_time * self.pixels_per_beat)
                py = mid_y - pt.y()
                
                if first:
                    path.moveTo(px, py)
                    first = False
                else:
                    path.lineTo(px, py)
            
            painter.drawPath(path)

        # Draw Text
        painter.setPen(Qt.white)
        painter.drawText(rect.adjusted(10, 5, -5, -5), Qt.AlignLeft | Qt.AlignTop, 
                        os.path.basename(self.sequence.audio_file))


class TrackLaneItem(QGraphicsRectItem):
    """Container for a Track's timeline content"""
    def __init__(self, track: Track, width, pixels_per_beat, snap_granularity, bpm=120.0, parent=None):
        super().__init__(parent)
        self.track = track
        self.pixels_per_beat = pixels_per_beat
        self.snap_granularity = snap_granularity
        self.bpm = bpm
        self.setRect(0, 0, width, track.height)
        
        # Calculate Background Color
        bg_color = generate_laser_color(track.target_laser)
        # Darken it for background
        self.bg_color = QColor.fromHsv(bg_color.hue(), int(bg_color.saturation() * 0.6), 60)
        self.setBrush(QBrush(self.bg_color))
        self.setPen(Qt.NoPen)
        self.border_pen = QPen(QColor("#000"), 2)
        
        self.setAcceptHoverEvents(True)
        
        self.curve_item = None
        self.handles = [] # List of TensionHandleItem
        self.keyframe_items = [] # Keep references to prevent GC issues
        
        if track.track_type == "audio":
            # Add Sequences
            for seq in track.sequences:
                item = AudioSequenceItem(seq, track.height, pixels_per_beat, self.bpm, self)
                item.snap_granularity = snap_granularity
        else:
            # Param Track
            self.curve_item = QGraphicsPathItem(self)
            
            # Use param color for curve
            color_hex = get_param_color(track.target_param)
            self.curve_item.setPen(QPen(QColor(color_hex), 2))
            
            for kf in track.keyframes:
                kfi = KeyframeItem(kf, track, pixels_per_beat, self)
                self.keyframe_items.append(kfi)
            
            self.update_curve()

    def paint(self, painter, option, widget):
        # Draw background via brush
        super().paint(painter, option, widget)
        
        # --- Draw Grid (on top of background, below content) ---
        rect = self.rect()
        
        # Use exposed rect from option to optimize
        exposed = option.exposedRect
        left = max(0, int(exposed.left()))
        right = int(exposed.right()) + 1
        
        start_beat = max(0, int(left / self.pixels_per_beat))
        end_beat = int(right / self.pixels_per_beat) + 1
        
        # We need to access project settings for beats_per_bar
        # Assuming we can get it via self.scene().project if added to scene
        beats_per_bar = 4
        if self.scene() and hasattr(self.scene(), 'project'):
            beats_per_bar = self.scene().project.beats_per_bar
            
        pen_bar = QPen(QColor(80, 80, 80, 100), 1) # Transparent grid
        pen_beat = QPen(QColor(80, 80, 80, 80), 1)
        bar_bg_color = QColor(0, 0, 0, 30)
        
        for i in range(start_beat, end_beat + 1):
            x = i * self.pixels_per_beat
            
            if i % beats_per_bar == 0:
                painter.setPen(pen_bar)
                bar_idx = i // beats_per_bar
                if bar_idx % 2 == 1:
                    bar_w = beats_per_bar * self.pixels_per_beat
                    # Darken alternate bars slightly for contrast
                    painter.fillRect(QRectF(x, rect.top(), bar_w, rect.height()), bar_bg_color)
            else:
                painter.setPen(pen_beat)
                
            painter.drawLine(x, rect.top(), x, rect.bottom())

        # Draw Bottom Border
        painter.setPen(self.border_pen)
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

    def update_curve(self, dragging_handle=None):
        if self.track.track_type != "param" or not self.curve_item:
            return
            
        # Prevent recursion if itemChange calls update_curve
        if getattr(self, '_is_updating_curve', False):
            return
            
        self._is_updating_curve = True
        try:
            # Recreate handles if keyframes changed (count mismatch) or if requested
            # Ideally we reuse handles but recreating is safer for sync
            # Unless dragging a handle
            
            # We need to map keyframes to handles. 
            # N keyframes -> N-1 handles.
            
            kfs = self.track.keyframes
            if not kfs:
                self.curve_item.setPath(QPainterPath())
                return
                
            path = QPainterPath()
            
            # Clear old handles if not dragging
            # If dragging, we want to keep the dragged handle alive
            
            # Strategy:
            # 1. Update Path
            # 2. Update/Create Handles
            
            first = True
            prev_x = 0
            prev_y = 0
            prev_kf = None
            
            new_handles = []
            
            for i, kf in enumerate(kfs):
                x = kf.time * self.pixels_per_beat
                
                normalized = 0.0
                r = self.track.max_val - self.track.min_val
                if r != 0:
                    normalized = (kf.value - self.track.min_val) / r
                normalized = max(0.0, min(1.0, normalized))
                y = self.track.height - (normalized * self.track.height)
                
                if first:
                    path.moveTo(x, y)
                    first = False
                else:
                    # Draw Curve from prev_kf to kf using sampling
                    # This replaces the fixed Quadratic Bezier to support all CurveTypes accurately
                    
                    x_start = prev_x
                    x_end = x
                    y_start = prev_y
                    y_end = y
                    
                    # Calculate Control Point / Handle Position (Visual Only)
                    mid_x = (x_start + x_end) / 2
                    mid_y = (y_start + y_end) / 2
                    scale = self.track.height / 2.0
                    offset_y = -prev_kf.tension * scale
                    
                    # Update Path by sampling
                    # Step size: 2 pixels for performance, 1 for quality. 
                    # 2 is usually fine.
                    step = 2.0
                    if x_end - x_start > step:
                        cur_x = x_start + step
                        while cur_x < x_end:
                            t = (cur_x - x_start) / (x_end - x_start)
                            
                            # Calculate value using model logic
                            val = self.track.calculate_value(prev_kf, kf, t)
                            
                            # Map value to Y
                            normalized = 0.0
                            r = self.track.max_val - self.track.min_val
                            if r != 0:
                                normalized = (val - self.track.min_val) / r
                            normalized = max(0.0, min(1.0, normalized))
                            cur_y = self.track.height - (normalized * self.track.height)
                            
                            path.lineTo(cur_x, cur_y)
                            cur_x += step
                            
                    # Connect to final point
                    path.lineTo(x, y)
                    
                    # Handle Management
                    # Check if we already have a handle for this segment
                    # We can try to match by keyframe object
                    
                    # To simplify: We can remove all non-dragged handles and recreate.
                    # Or update existing ones.
                    
                    found_handle = None
                    for h in self.handles:
                        if h.keyframe == prev_kf and h.next_keyframe == kf:
                            found_handle = h
                            break
                    
                    if found_handle:
                        if found_handle != dragging_handle:
                            # Update pos
                            found_handle.p1 = QPointF(prev_x, prev_y)
                            found_handle.p2 = QPointF(x, y)
                            found_handle.update_pos_from_tension()
                        new_handles.append(found_handle)
                        if found_handle in self.handles:
                            self.handles.remove(found_handle) # Move to new list
                    else:
                        # Create new
                        h = TensionHandleItem(prev_kf, kf, self.track, QPointF(prev_x, prev_y), QPointF(x, y), self)
                        new_handles.append(h)

                prev_x = x
                prev_y = y
                prev_kf = kf
                    
            self.curve_item.setPath(path)
            
            # Remove remaining old handles (that weren't reused)
            for h in self.handles:
                if h != dragging_handle:
                    if self.scene():
                        self.scene().removeItem(h)
            
            self.handles = new_handles
        
        finally:
            self._is_updating_curve = False

    def hoverMoveEvent(self, event):
        pos = event.pos()
        # Find which segment we are close to
        # Distance to curve?
        
        # Simple proximity check:
        # Find segment by time
        x = pos.x()
        time = x / self.pixels_per_beat
        
        kfs = self.track.keyframes
        for i in range(len(kfs) - 1):
            kf1 = kfs[i]
            kf2 = kfs[i+1]
            
            if kf1.time <= time <= kf2.time:
                # We are in this segment
                # Check vertical distance to curve?
                # For now, just show the handle for this segment
                
                # Find handle
                for h in self.handles:
                    if h.keyframe == kf1:
                        if not h.isVisible():
                            h.setVisible(True)
                    else:
                        # Hide others?
                        # Maybe keep them hidden unless hovered?
                        # User: "Only mouse in current ... show"
                        if h.isVisible() and not h.isUnderMouse():
                             h.setVisible(False)
                break
        else:
             # Not in any segment (before start or after end?)
             for h in self.handles:
                 if h.isVisible() and not h.isUnderMouse():
                     h.setVisible(False)
                     
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if self.track.track_type == "param" and event.button() == Qt.LeftButton:
            # Check if we hit existing items (handled by children)
            # QGraphicsItem handles this if we call super(), but if children accepted, we don't get it?
            # Actually, if child accepts, parent doesn't get mousePressEvent usually.
            # But we need to be sure we are not clicking on a handle or keyframe.
            # If we are here, it means no child accepted the event (or we are the bottom).
            # KeyframeItem and TensionHandleItem should accept event.
            
            # Double check using scene().items() to be robust against hit test nuances
            if self.scene():
                items = self.scene().items(event.scenePos())
                for item in items:
                    if isinstance(item, (KeyframeItem, TensionHandleItem)):
                        return # Hit an item, do not insert
            
            pos = event.pos()
            x = pos.x()
            time = x / self.pixels_per_beat
            
            # Snap time
            snap_pixels = self.pixels_per_beat * self.snap_granularity
            if snap_pixels > 1:
                x = round(x / snap_pixels) * snap_pixels
                time = x / self.pixels_per_beat
            
            kfs = self.track.keyframes
            insert_idx = -1
            
            # Check for collision with existing keyframes (don't insert duplicate time)
            for kf in kfs:
                if abs(kf.time - time) < 0.001:
                    return # Exists
            
            for i in range(len(kfs) - 1):
                if kfs[i].time <= time <= kfs[i+1].time:
                    insert_idx = i + 1
                    break
            
            if insert_idx != -1:
                # Remove original adjacent anchors (as per user requirement)
                # "移除原先相邻的锚点" -> This likely means breaking the existing segment.
                # However, if we interpret literally "remove anchors", we would lose data.
                # But since user said "re-connect them with new anchor", it implies the *connection* logic changes.
                # Actually, simply inserting a point splits the segment, effectively "removing" the old direct connection.
                # But maybe user wants to RESET the tension of adjacent segments?
                # Or literally remove the adjacent keyframes?
                # "Remove original adjacent anchors AND THEN re-connect THEM with new anchor"
                # If I remove A and B, I have nothing to connect to C.
                # So "them" must refer to the *outer* neighbors? (Prev-Prev and Next-Next?)
                # If I have A-B-C-D. I click between B and C. Insert X.
                # Remove B and C? Then connect A-X-D?
                # That seems drastic.
                # Given the crash context, maybe I should stick to safe insertion.
                # But the prompt says "Remove original adjacent anchors".
                # Let's assume they mean "Remove the Tension Handle" (which represents the connection logic).
                # My code already does this by recreating handles.
                
                # Wait, "remove original adjacent anchors" might mean: 
                # If I click near a line segment, maybe there are *existing* anchors I should delete?
                # "Mouse left click ... insert new anchor ... remove original adjacent anchors"
                # Maybe it means: If I am close to an existing anchor, replace it?
                # But I already check `abs(kf.time - time) < 0.001`.
                
                # Let's proceed with standard insertion which naturally "breaks" the old segment.
                # And ensure tension is reset or handled.
                
                y = pos.y()
                normalized = (self.track.height - y) / self.track.height
                r = self.track.max_val - self.track.min_val
                val = self.track.min_val + (normalized * r)
                
                kf = Keyframe(time, val)
                
                main_window = self.scene().main_window if self.scene() and hasattr(self.scene(), 'main_window') else None
                if main_window:
                    from core.commands import InsertItemCommand
                    cmd = InsertItemCommand(self.track.keyframes, insert_idx, kf, "添加关键帧", main_window)
                    main_window.undo_stack.push(cmd)
                else:
                    self.track.keyframes.insert(insert_idx, kf)
                    KeyframeItem(kf, self.track, self.pixels_per_beat, self)
                    self.update_curve()
                    if self.scene() and hasattr(self.scene(), 'data_changed'):
                        self.scene().data_changed.emit()
                event.accept()
                return
                
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Disable double click insert since we moved to single click
        super().mouseDoubleClickEvent(event)
            
class GroupTrackLaneItem(QGraphicsRectItem):
    """Container for multiple tracks' curves superimposed"""
    def __init__(self, tracks: list[Track], width, pixels_per_beat, snap_granularity, parent=None):
        super().__init__(parent)
        self.tracks = tracks
        self.height = tracks[0].height if tracks else 60
        self.setRect(0, 0, width, self.height)
        
        # Group Background Color
        self.setBrush(QBrush(QColor(40, 30, 50)))
        self.setPen(Qt.NoPen)
        self.border_pen = QPen(QColor("#000"), 2)
        
        # Previously we superimposed all curves here, but user requested removal due to performance.
        # So we leave it empty (just background).
        
    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        # Draw Bottom Border
        painter.setPen(self.border_pen)
        rect = self.rect()
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

class PlayheadItem(QGraphicsLineItem):
    def __init__(self, height, parent=None):
        super().__init__(parent)
        self.setPen(QPen(QColor(255, 50, 50), 2))
        self.setLine(0, 0, 0, height)
        self.setZValue(1000) # On top
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, False)

class TimelineScene(QGraphicsScene):
    data_changed = Signal()

    def __init__(self, project: Project, parent=None, main_window=None):
        super().__init__(parent)
        self.project = project
        self.main_window = main_window
        self.pixels_per_beat = 40.0
        self.total_beats = 1000 
        self.snap_granularity = 1.0
        
        self.setBackgroundBrush(QBrush(QColor(20, 20, 20)))
        self.track_items = []
        
        self.playhead = PlayheadItem(1000)
        self.addItem(self.playhead)
        
        self.refresh()
        
    def set_playhead_pos(self, beat):
        x = beat * self.pixels_per_beat
        self.playhead.setPos(x, 0)

    def drawBackground(self, painter, rect):
        # Draw Grid
        left = int(rect.left())
        right = int(rect.right())
        
        start_beat = max(0, int(left / self.pixels_per_beat))
        end_beat = int(right / self.pixels_per_beat) + 1
        
        beats_per_bar = self.project.beats_per_bar
        
        # Pre-create pens
        pen_bar = QPen(QColor(80, 80, 80), 1.5)
        pen_beat = QPen(QColor(50, 50, 50), 1)
        bar_bg_color = QColor(0, 0, 0, 30)
        
        for i in range(start_beat, end_beat + 1):
            x = i * self.pixels_per_beat
            
            if i % beats_per_bar == 0:
                painter.setPen(pen_bar)
                bar_idx = i // beats_per_bar
                if bar_idx % 2 == 1:
                    bar_w = beats_per_bar * self.pixels_per_beat
                    # Darken alternate bars slightly for contrast
                    painter.fillRect(QRectF(x, rect.top(), bar_w, rect.height()), bar_bg_color)
            else:
                painter.setPen(pen_beat)
                
            painter.drawLine(x, rect.top(), x, rect.bottom())

    def refresh(self, folded_groups=None):
        if folded_groups is None:
            folded_groups = set()
            
        self.clear()
        self.track_items = []
        
        total_beats = self.project.total_measures * self.project.beats_per_bar
        width = total_beats * self.pixels_per_beat
        
        y = 0
        
        # We need to mirror the logic in refresh_tracks to maintain alignment
        rendered_groups = set()
        
        for track in self.project.tracks:
            if track.track_type == "audio":
                continue
                
            laser_name = track.target_laser
            if laser_name in folded_groups:
                if laser_name not in rendered_groups:
                    # Collect all tracks for this laser
                    group_tracks = [t for t in self.project.tracks if t.target_laser == laser_name and t.track_type == "param"]
                    
                    lane = GroupTrackLaneItem(group_tracks, width, self.pixels_per_beat, self.snap_granularity)
                    lane.setPos(0, y)
                    self.addItem(lane)
                    
                    y += lane.height
                    rendered_groups.add(laser_name)
            else:
                lane = TrackLaneItem(track, width, self.pixels_per_beat, self.snap_granularity, self.project.bpm)
                lane.setPos(0, y)
                self.addItem(lane)
                self.track_items.append(lane)
                y += track.height
            
        scene_height = max(y, 100)
        self.setSceneRect(0, 0, width, scene_height)
        
        # Re-add Playhead
        self.playhead = PlayheadItem(scene_height)
        self.addItem(self.playhead)
        
        self.update() # Force scene update for background



class AudioTimelineScene(QGraphicsScene):
    data_changed = Signal()

    def __init__(self, project: Project, parent=None, main_window=None):
        super().__init__(parent)
        self.project = project
        self.main_window = main_window
        self.pixels_per_beat = 40.0
        self.total_beats = 1000
        self.snap_granularity = 1.0
        self.setBackgroundBrush(QBrush(QColor(25, 25, 25)))
        
        self.playhead = PlayheadItem(100)
        self.addItem(self.playhead)
        
        self.refresh()
        
    def set_playhead_pos(self, beat):
        x = beat * self.pixels_per_beat
        self.playhead.setPos(x, 0)

    def drawBackground(self, painter, rect):
        left = int(rect.left())
        right = int(rect.right())
        start_beat = max(0, int(left / self.pixels_per_beat))
        end_beat = int(right / self.pixels_per_beat) + 1
        beats_per_bar = self.project.beats_per_bar
        
        pen_bar = QPen(QColor(80, 80, 80), 1)
        
        for i in range(start_beat, end_beat + 1):
            x = i * self.pixels_per_beat
            if i % beats_per_bar == 0:
                painter.setPen(pen_bar)
                painter.drawLine(x, rect.top(), x, rect.bottom())

    def refresh(self):
        self.clear()
        total_beats = self.project.total_measures * self.project.beats_per_bar
        width = total_beats * self.pixels_per_beat
        y = 0
        
        audio_tracks = [t for t in self.project.tracks if t.track_type == "audio"]
        
        for track in audio_tracks:
            lane = TrackLaneItem(track, width, self.pixels_per_beat, self.snap_granularity, self.project.bpm)
            lane.setPos(0, y)
            self.addItem(lane)
            y += track.height
            
        scene_height = max(y, 120) # Match default track height
        self.setSceneRect(0, 0, width, scene_height)
        
        # Re-add Playhead
        self.playhead = PlayheadItem(scene_height)
        self.addItem(self.playhead)
        
        self.update() # Force scene update for background

class RulerWidget(QWidget):
    """Top Ruler with Playhead"""
    seek_requested = Signal(float) # Emits beat
    
    def __init__(self, project: Project, pixels_per_beat, parent=None):
        super().__init__(parent)
        self.project = project
        self.pixels_per_beat = pixels_per_beat
        self.offset_x = 0
        self.playhead_beat = 0.0
        self.snap_granularity = 1.0 # Beats
        self.setFixedHeight(30)
        self.setStyleSheet("background-color: #222; border-bottom: 1px solid #555;")
        self.setMouseTracking(True)
        
    def set_playhead_pos(self, beat):
        self.playhead_beat = beat
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(Qt.lightGray)
        painter.setFont(QApplication.font())
        
        start_beat = self.offset_x / self.pixels_per_beat
        end_beat = (self.offset_x + self.width()) / self.pixels_per_beat
        beats_per_bar = self.project.beats_per_bar
        
        pen_bar = QColor(200, 200, 200)
        pen_beat = QColor(100, 100, 100)
        
        beat = int(start_beat)
        while beat <= end_beat + 1:
            x = (beat * self.pixels_per_beat) - self.offset_x
            
            is_bar_start = (beat % beats_per_bar == 0)
            
            if is_bar_start:
                height = 15
                bar_num = (beat // beats_per_bar) + 1 
                painter.setPen(pen_bar)
                painter.drawLine(int(x), 30, int(x), 30 - height)
                painter.drawText(int(x) + 4, 18, str(bar_num))
            else:
                height = 5
                painter.setPen(pen_beat)
                painter.drawLine(int(x), 30, int(x), 30 - height)
                
            beat += 1
            
        # Draw Playhead
        ph_x = (self.playhead_beat * self.pixels_per_beat) - self.offset_x
        if 0 <= ph_x <= self.width():
            # Triangle Head
            painter.setBrush(QColor(255, 50, 50))
            painter.setPen(Qt.NoPen)
            # Simpler shape
            painter.drawPolygon(QPolygonF([
                QPointF(ph_x - 6, 0),
                QPointF(ph_x + 6, 0),
                QPointF(ph_x, 10),
                QPointF(ph_x - 6, 0)
            ]))
            painter.setPen(QPen(QColor(255, 50, 50), 1))
            painter.drawLine(ph_x, 0, ph_x, 30)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.handle_mouse_seek(event)
            
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.handle_mouse_seek(event)
            
    def handle_mouse_seek(self, event):
        x = event.pos().x() + self.offset_x
        beat = x / self.pixels_per_beat
        
        # Snapping
        if event.modifiers() & Qt.ShiftModifier:
            # Shift to disable snap? Or default snap?
            # User said "drag has snap granularity".
            # Let's apply snap by default or if NOT shift?
            # Usually Shift implies "Fine".
            pass
        else:
            # Snap
            snap_val = self.snap_granularity
            if snap_val > 0:
                beat = round(beat / snap_val) * snap_val
                
        beat = max(0, beat)
        self.seek_requested.emit(beat)
        self.set_playhead_pos(beat) # Immediate local update for responsiveness

class TrackWindow(QWidget):
    seek_requested = Signal(float)
    audio_added = Signal(str) # Emits file path
    track_deleted = Signal(str) # Emits track name
    data_changed = Signal()

    def __init__(self, project: Project, parent=None, main_window=None):
        super().__init__(parent)
        self.project = project
        self.main_window = main_window
        self.pixels_per_beat = 40.0
        self.snap_granularity = 1.0 # Default 1 beat
        self.setAcceptDrops(True)
        self.folded_groups = set() # Set of laser names that are folded
        
        self.init_ui()
        
        # Connect Ruler
        self.ruler.seek_requested.connect(self.seek_requested)
        
        # Init fix
        QTimer.singleShot(100, self.init_scroll_pos)

    def set_playhead_pos(self, beat):
        self.timeline_scene.set_playhead_pos(beat)
        self.audio_scene.set_playhead_pos(beat)
        self.ruler.set_playhead_pos(beat)
        
        # Auto Scroll / Follow Playhead
        x = beat * self.pixels_per_beat
        view = self.timeline_view
        val = view.horizontalScrollBar().value()
        page_step = view.viewport().width()
        
        # If playhead is out of view, scroll to it
        if x < val:
            view.horizontalScrollBar().setValue(int(x - 20))
        elif x > val + page_step:
            # Scroll to keep it visible, maybe center it or show next page
            view.horizontalScrollBar().setValue(int(x - page_step + 100))

    def init_scroll_pos(self):
        self.timeline_view.horizontalScrollBar().setValue(0)
        self.audio_view.horizontalScrollBar().setValue(0)

    def set_project(self, project: Project):
        self.project = project
        if hasattr(self, 'ruler'):
            self.ruler.project = project
            self.ruler.update()
            
        if hasattr(self, 'timeline_scene'):
            self.timeline_scene.project = project
            
        if hasattr(self, 'audio_scene'):
            self.audio_scene.project = project
            
        self.init_scroll_pos()
        self.set_playhead_pos(0)
        self.refresh_tracks()
        self.update_settings()

    def set_snap_granularity(self, value):
        self.snap_granularity = value
        self.timeline_scene.snap_granularity = value
        self.audio_scene.snap_granularity = value
        self.refresh_tracks()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- Top Section: Ruler ---
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0,0,0,0)
        top_layout.setSpacing(0)
        
        self.corner_widget = QWidget()
        self.corner_widget.setFixedWidth(100)
        self.corner_widget.setStyleSheet("background-color: #333; border-right: 1px solid #111; border-bottom: 1px solid #111;")
        top_layout.addWidget(self.corner_widget)
        
        self.ruler = RulerWidget(self.project, self.pixels_per_beat)
        top_layout.addWidget(self.ruler)
        main_layout.addLayout(top_layout)
        
        # --- Middle Section: Splitter ---
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #111; }")
        
        # --- Left Side ---
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0,0,0,0)
        left_layout.setSpacing(0)
        
        self.audio_header_container = QWidget()
        self.audio_header_layout = QVBoxLayout(self.audio_header_container)
        self.audio_header_layout.setContentsMargins(0,0,0,0)
        self.audio_header_layout.setSpacing(0)
        left_layout.addWidget(self.audio_header_container)
        
        self.header_scroll = QScrollArea()
        self.header_scroll.setWidgetResizable(True)
        # Force horizontal scrollbar to reserve space, matching timeline view
        self.header_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.header_scroll.horizontalScrollBar().setEnabled(False)
        self.header_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff) 
        self.header_scroll.setStyleSheet("background-color: #2b2b2b; border: none;")
        
        self.track_header_container = QWidget()
        self.track_header_layout = QVBoxLayout(self.track_header_container)
        self.track_header_layout.setContentsMargins(0,0,0,0)
        self.track_header_layout.setSpacing(0)
        self.track_header_layout.addStretch() 
        
        self.header_scroll.setWidget(self.track_header_container)
        left_layout.addWidget(self.header_scroll)
        
        self.splitter.addWidget(left_container)
        
        # --- Right Side ---
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0,0,0,0)
        right_layout.setSpacing(0)
        
        self.audio_view = QGraphicsView()
        self.audio_scene = AudioTimelineScene(self.project, main_window=self.main_window)
        self.audio_scene.data_changed.connect(self.data_changed)
        self.audio_view.setScene(self.audio_scene)
        self.audio_view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.audio_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff) 
        self.audio_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.audio_view.setFixedHeight(60)
        self.audio_view.setStyleSheet("border: none; border-bottom: 1px solid #444;")
        right_layout.addWidget(self.audio_view)
        
        self.timeline_view = QGraphicsView()
        self.timeline_scene = TimelineScene(self.project, main_window=self.main_window)
        self.timeline_scene.data_changed.connect(self.data_changed)
        self.timeline_view.setScene(self.timeline_scene)
        self.timeline_view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.timeline_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.timeline_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.timeline_view.setStyleSheet("border: none;")
        right_layout.addWidget(self.timeline_view)
        
        self.splitter.addWidget(right_container)
        self.splitter.setSizes([100, 900])
        main_layout.addWidget(self.splitter)
        
        # --- Sync Logic ---
        self.timeline_view.horizontalScrollBar().valueChanged.connect(self.on_horizontal_scroll)
        
        # Sync Vertical Scroll (Bidirectional)
        self.timeline_view.verticalScrollBar().valueChanged.connect(
            self.header_scroll.verticalScrollBar().setValue
        )
        self.header_scroll.verticalScrollBar().valueChanged.connect(
            self.timeline_view.verticalScrollBar().setValue
        )
        
        self.splitter.splitterMoved.connect(self.on_splitter_moved)
        
        # Install event filters for custom wheel handling
        self.timeline_view.viewport().installEventFilter(self)
        self.audio_view.viewport().installEventFilter(self)
        self.header_scroll.viewport().installEventFilter(self)
        
        self.refresh_tracks()
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.splitter.sizes():
            self.corner_widget.setFixedWidth(self.splitter.sizes()[0])
            
    def showEvent(self, event):
        super().showEvent(event)
        if self.splitter.sizes():
            self.corner_widget.setFixedWidth(self.splitter.sizes()[0])

    def on_horizontal_scroll(self, value):
        self.ruler.offset_x = value
        self.ruler.update()
        self.audio_view.horizontalScrollBar().setValue(value)

    def on_splitter_moved(self, pos, index):
        self.corner_widget.setFixedWidth(pos)

    def update_settings(self):
        self.ruler.update()
        self.timeline_scene.refresh()
        self.audio_scene.refresh()
        
        # Force repaint of views to ensure background grid updates immediately
        if hasattr(self, 'timeline_view'):
            self.timeline_view.viewport().update()
        if hasattr(self, 'audio_view'):
            self.audio_view.viewport().update()

    def refresh_tracks(self):
        # Prevent updates if project is not valid
        if not self.project:
            return

        while self.audio_header_layout.count():
            item = self.audio_header_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        while self.track_header_layout.count() > 1:
            item = self.track_header_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        audio_height = 0
        
        # Helper to group param tracks by laser
        # We need to maintain order of tracks as much as possible?
        # If we group, we should probably render group header where the first track of that group appears?
        # Or just iterate lasers?
        # Tracks are list in project.tracks.
        
        # If we iterate project.tracks linearly:
        # If track is param and its laser is folded:
        #   Check if we already rendered the group header for this laser.
        #   If no, render group header.
        #   If yes, skip.
        
        rendered_groups = set()
        
        for track in self.project.tracks:
            if track.track_type == "audio":
                hw = TrackHeaderWidget(track, main_window=self.main_window)
                hw.delete_requested.connect(lambda t=track: self.delete_track(t))
                self.audio_header_layout.addWidget(hw)
                audio_height += track.height
            else:
                laser_name = track.target_laser
                if laser_name in self.folded_groups:
                    if laser_name not in rendered_groups:
                        # Render Group Header
                        # Create a dummy track object or just pass None and use special mode
                        # But TrackHeaderWidget expects a track for height.
                        # Use current track for height ref?
                        hw = TrackHeaderWidget(track, is_group_header=True, laser_name=laser_name, main_window=self.main_window)
                        hw.expand_requested.connect(self.expand_group)
                        self.track_header_layout.insertWidget(self.track_header_layout.count()-1, hw)
                        rendered_groups.add(laser_name)
                else:
                    # Normal
                    hw = TrackHeaderWidget(track, main_window=self.main_window)
                    hw.delete_requested.connect(lambda t=track: self.delete_track(t))
                    hw.collapse_requested.connect(self.collapse_group)
                    self.track_header_layout.insertWidget(self.track_header_layout.count()-1, hw)
        
        # Ensure Audio View visibility and height matches exactly
        if audio_height == 0:
            self.audio_view.hide()
            self.audio_header_container.hide()
        else:
            self.audio_view.show()
            self.audio_header_container.show()
            self.audio_view.setFixedHeight(audio_height)
            self.audio_header_container.setFixedHeight(audio_height)
            
        self.timeline_scene.refresh(self.folded_groups)
        self.audio_scene.refresh()
        
        # Force layout update to ensure alignment
        QApplication.processEvents()
        if self.splitter.sizes():
             self.corner_widget.setFixedWidth(self.splitter.sizes()[0])

    def collapse_group(self, laser_name):
        if self.main_window:
            from core.commands import SetPropertyCommand
            cmd = SetPropertyCommand(self, "folded_groups", "add_folded_group", "remove_folded_group", laser_name, f"折叠轨道组 {laser_name}", self.main_window)
            self.main_window.undo_stack.push(cmd)
        else:
            self.add_folded_group(laser_name)
            
    def expand_group(self, laser_name):
        if self.main_window:
            from core.commands import SetPropertyCommand
            cmd = SetPropertyCommand(self, "folded_groups", "remove_folded_group", "add_folded_group", laser_name, f"展开轨道组 {laser_name}", self.main_window)
            self.main_window.undo_stack.push(cmd)
        else:
            self.remove_folded_group(laser_name)

    def add_folded_group(self, laser_name):
        self.folded_groups.add(laser_name)
        self.refresh_tracks()
        
    def remove_folded_group(self, laser_name):
        if laser_name in self.folded_groups:
            self.folded_groups.remove(laser_name)
            self.refresh_tracks()

    def delete_track(self, track):
        if track in self.project.tracks:
            idx = self.project.tracks.index(track)
            if self.main_window:
                cmd = RemoveItemCommand(self.project.tracks, idx, track, f"删除轨道 {track.name}", self.main_window)
                self.main_window.undo_stack.push(cmd)
            else:
                self.project.tracks.remove(track)
                self.track_deleted.emit(track.name)
                self.data_changed.emit()
                self.refresh_tracks()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if not urls:
            return
            
        file_path = urls[0].toLocalFile()
        if not file_path:
            return
            
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.mp3', '.wav', '.ogg', '.flac']:
            self.add_audio_track(file_path)
            event.acceptProposedAction()

    def add_audio_track(self, file_path):
        audio_track = None
        for t in self.project.tracks:
            if t.track_type == "audio":
                audio_track = t
                break
        
        # Calculate duration in beats
        duration_beats = 100.0 # Fallback
        try:
            with wave.open(file_path, 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration_sec = frames / rate
                duration_beats = (duration_sec * self.project.bpm) / 60.0
        except Exception:
            pass
            
        seq = Sequence(start_time=0, duration=duration_beats, audio_file=file_path) 
        
        if self.main_window:
            commands = []
            if not audio_track:
                audio_track = Track(name="Audio", track_type="audio", height=120)
                from core.commands import InsertItemCommand
                commands.append(InsertItemCommand(self.project.tracks, 0, audio_track, "添加音频轨道", self.main_window))
            commands.append(AddItemCommand(audio_track.sequences, seq, "添加音频片段", self.main_window))
            batch = BatchCommand(commands, "导入音频", self.main_window)
            self.main_window.undo_stack.push(batch)
            self.audio_added.emit(file_path)
        else:
            if not audio_track:
                audio_track = Track(name="Audio", track_type="audio", height=120)
                self.project.tracks.insert(0, audio_track)
            audio_track.sequences.append(seq)
            self.refresh_tracks()
            self.audio_added.emit(file_path)
            self.data_changed.emit()

    def eventFilter(self, source, event):
        if event.type() == QEvent.Wheel:
            if event.modifiers() & Qt.ControlModifier:
                self.handle_zoom(event.angleDelta().y())
                return True
            elif event.modifiers() & Qt.ShiftModifier:
                self.handle_horizontal_scroll(event.angleDelta().y())
                return True
        return super().eventFilter(source, event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            self.handle_zoom(event.angleDelta().y())
            event.accept()
        elif event.modifiers() & Qt.ShiftModifier:
            self.handle_horizontal_scroll(event.angleDelta().y())
            event.accept()
        else:
            super().wheelEvent(event)

    def handle_zoom(self, delta):
        # Capture current playhead position to restore it after refresh
        current_beat = self.ruler.playhead_beat
        
        if delta > 0:
            self.pixels_per_beat *= 1.1
        else:
            self.pixels_per_beat /= 1.1
        
        self.pixels_per_beat = max(10, min(200, self.pixels_per_beat))
        self.timeline_scene.pixels_per_beat = self.pixels_per_beat
        self.audio_scene.pixels_per_beat = self.pixels_per_beat
        self.ruler.pixels_per_beat = self.pixels_per_beat
        
        self.refresh_tracks()
        self.ruler.update()
        
        # Restore playhead position and force background update
        self.set_playhead_pos(current_beat)
        self.timeline_view.viewport().update()
        self.audio_view.viewport().update()

    def handle_horizontal_scroll(self, delta):
        scroll_bar = self.timeline_view.horizontalScrollBar()
        scroll_bar.setValue(scroll_bar.value() - delta)
