import json
import math
import os
from PySide6.QtWidgets import QMainWindow, QDockWidget, QDialog, QWidget, QVBoxLayout, QToolBar, QMenuBar, QStatusBar, QLabel, QFileDialog, QMessageBox
from PySide6.QtCore import Qt, QSettings
from .simulator import SimulatorWidget
from .track_window import TrackWindow
from .project_panel import ProjectPanel
from .source_panel import SourcePanel
from .properties_panel import PropertiesPanel
from .dialogs import RandomizationDialog, ExportSplitDialog
from core.models import Project, Track, Sequence, CurveType, Keyframe
import random
from PySide6.QtWidgets import QApplication

from PySide6.QtGui import QKeySequence, QShortcut

from core.exporter import GLSLExporter

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("激光秀设计软件 (Python版)")
        self.resize(1600, 900)
        
        # Load Stylesheet
        self.load_stylesheet()
        
        # Data
        self.project = Project()
        self.current_file_path = None
        self.is_modified = False
        
        # Central: Simulator
        self.simulator = SimulatorWidget()
        self.simulator.set_project(self.project) # Pass project to simulator
        self.setCentralWidget(self.simulator)
        
        # Docks
        self.create_docks()
        
        # Menu & Toolbar
        self.create_menu()
        
        # Status
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        # Connect Signals
        self.source_panel.selection_changed.connect(self.props_panel.set_source)
        self.props_panel.source_changed.connect(self.on_project_modified)
        self.props_panel.source_changed.connect(self.source_panel.refresh_list)
        
        # Track Window Signals
        self.track_window.track_deleted.connect(self.on_track_deleted)
        self.track_window.data_changed.connect(self.on_project_modified)
        
        # Connect seek to simulator auto-pause
        self.track_window.seek_requested.connect(self.simulator.on_seek_requested)
        
        # Playback Signals
        self.simulator.time_updated.connect(self.on_sim_time_updated)
        self.track_window.seek_requested.connect(self.on_track_seek)
        self.track_window.audio_added.connect(self.on_audio_added)
        
        # Auto-reload shader on source list change or property change
        self.source_panel.source_list_changed.connect(self.on_project_modified)
        self.source_panel.source_list_changed.connect(self.reload_shader_with_feedback)
        self.props_panel.source_changed.connect(self.reload_shader_with_feedback)

        # Settings Changed
        self.project_panel.settings_changed.connect(self.on_project_modified)
        self.project_panel.settings_changed.connect(self.on_project_settings_changed)
        
        # Automation Signals
        self.props_panel.request_automation.connect(self.create_automation_track)
        self.props_panel.request_random.connect(self.create_random_automation)
        
        # Shortcuts
        self.shortcut_reload = QShortcut(QKeySequence("Ctrl+R"), self)
        self.shortcut_reload.activated.connect(self.reload_shader_with_feedback)
        
        self.shortcut_esc = QShortcut(QKeySequence("Esc"), self)
        self.shortcut_esc.activated.connect(self.simulator.toggle_playback)
        
        self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_save.activated.connect(self.save_project)
        
        # Load UI State
        self.load_ui_state()

    def load_ui_state(self):
        settings = QSettings("LaserShowDesigner", "MainWindow")
        geometry = settings.value("geometry")
        state = settings.value("windowState")
        
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)

    def save_ui_state(self):
        settings = QSettings("LaserShowDesigner", "MainWindow")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())

    def on_track_deleted(self, track_name):
        self.on_project_modified()
        self.statusBar.showMessage(f"已删除轨道: {track_name}", 3000)

    def on_sim_time_updated(self, time_sec):
        if hasattr(self, 'track_window'):
            beat = (time_sec * self.project.bpm) / 60.0
            self.track_window.set_playhead_pos(beat)
            
        if hasattr(self, 'props_panel'):
            self.props_panel.refresh_values()

    def on_track_seek(self, beat):
        time_sec = (beat * 60.0) / self.project.bpm
        self.simulator.set_time(time_sec)

    def on_project_settings_changed(self):
        new_len = float(self.project.total_measures * self.project.beats_per_bar)
        
        for track in self.project.tracks:
            if track.track_type == "param":
                # Ensure sorted
                track.keyframes.sort(key=lambda k: k.time)
                if not track.keyframes: continue
                
                # Handle End Anchor Logic
                # Requirement: Move End Anchor to new length. 
                # If shrinking, delete intermediate KFs > new_len.
                
                # Assume last keyframe is the End Anchor
                end_anchor = track.keyframes.pop() 
                
                # Remove any keyframes that are now out of bounds (>= new_len)
                # Note: We use < because if a KF is exactly at new_len, it conflicts with End Anchor.
                track.keyframes = [k for k in track.keyframes if k.time < new_len]
                
                # Update and restore End Anchor
                end_anchor.time = new_len
                track.keyframes.append(end_anchor)

        if hasattr(self, 'track_window'):
            self.track_window.update_settings()
            self.track_window.refresh_tracks()

    def reload_shader_with_feedback(self):
        self.statusBar.showMessage("正在重载 Shader...", 0)
        QApplication.processEvents() # Force UI update
        success = self.simulator.reload_laser_shader()
        if success:
            self.statusBar.showMessage("Shader 重载成功", 3000)
        else:
            self.statusBar.showMessage("Shader 重载失败 (查看控制台)", 5000)

    def sort_tracks(self):
        # Sort tracks based on requirement:
        # 1. Source creation order (first param track creation time)
        # 2. Param type priority
        
        # Audio tracks usually on top or separate, let's keep them at top
        audio_tracks = [t for t in self.project.tracks if t.track_type == "audio"]
        param_tracks = [t for t in self.project.tracks if t.track_type == "param"]
        
        # Identify sources and their order based on current list (assuming append order is preservation of creation order)
        # But if we sort every time, we need a stable way to know "Source Order".
        # We can scan the current list to extract source order if it's not already broken.
        # Better: Group by source, preserving the order of *first appearance* of that source.
        
        source_order = []
        source_groups = {}
        
        for t in param_tracks:
            s_name = t.target_laser
            if s_name not in source_groups:
                source_order.append(s_name)
                source_groups[s_name] = []
            source_groups[s_name].append(t)
            
        # Param Priority List
        # type, pos(x,y,z), dir(x,y,z), color(r,g,b), brightness, thickness, divergence, attenuation, params(x,y,z,w)
        
        param_priority = [
            "type", 
            "pos.x", "pos.y", "pos.z",
            "dir.x", "dir.y", "dir.z",
            "color.r", "color.g", "color.b",
            "brightness",
            "thickness",
            "divergence",
            "attenuation",
            "params.x", "params.y", "params.z", "params.w"
        ]
        
        def get_param_index(track):
            p_name = track.target_param
            try:
                return param_priority.index(p_name)
            except ValueError:
                return 999 # Unknown params at end
                
        sorted_param_tracks = []
        for s_name in source_order:
            # Sort tracks within this source
            tracks = source_groups[s_name]
            tracks.sort(key=get_param_index)
            sorted_param_tracks.extend(tracks)
            
        self.project.tracks = audio_tracks + sorted_param_tracks

    def create_automation_track(self, source_name, param_name):
        track_name = f"{source_name}.{param_name}"
        # Check if exists
        for t in self.project.tracks:
            if t.name == track_name:
                self.statusBar.showMessage(f"轨道已存在: {track_name}", 3000)
                return
        
        # Determine ranges
        min_v, max_v = 0.0, 1.0
        
        check_name = param_name
        if param_name.startswith("offset_mode_"):
            check_name = param_name[12:]
            min_v, max_v = 0.0, 1.0
        elif param_name.startswith("offset_"):
            check_name = param_name[7:]
            # Offsets generally centered around 0
            if "pos" in check_name: min_v, max_v = -1000.0, 1000.0
            elif "dir" in check_name: min_v, max_v = -1.0, 1.0
            elif "color" in check_name: min_v, max_v = -255.0, 255.0
            elif "brightness" in check_name: min_v, max_v = -10.0, 10.0
            elif "thickness" in check_name: min_v, max_v = -100.0, 100.0
            elif "divergence" in check_name: min_v, max_v = -180.0, 180.0
            elif "attenuation" in check_name: min_v, max_v = -1.0, 1.0
            elif "params" in check_name: min_v, max_v = -50.0, 50.0
        elif param_name == "is_master":
             min_v, max_v = 0.0, 1.0
        else:
            if "pos" in param_name: min_v, max_v = -3000.0, 3000.0
            elif "dir" in param_name: min_v, max_v = -1.0, 1.0
            elif "color" in param_name: min_v, max_v = 0.0, 255.0
            elif "brightness" in param_name: min_v, max_v = 0.0, 10.0
            elif "thickness" in param_name: min_v, max_v = 0.0, 100.0
            elif "divergence" in param_name: min_v, max_v = 0.0, 180.0
            elif "attenuation" in param_name: min_v, max_v = 0.0, 1.0
            elif "params" in param_name: min_v, max_v = -50.0, 50.0
            elif "type" in param_name: min_v, max_v = 0.0, 4.0

        track = Track(name=track_name, track_type="param", target_laser=source_name, target_param=param_name, min_val=min_v, max_val=max_v)
        
        # Initialize default keyframes with Current Value
        current_val = 0.0
        # Find Source
        laser = None
        for l in self.project.lasers:
            if l.name == source_name:
                laser = l
                break
        
        if laser:
            if param_name == "is_master":
                current_val = 1.0 if laser.is_master else 0.0
            elif param_name.startswith("offset_mode_"):
                omp = laser.offset_mode_params
                real_pt = param_name[12:]
                idx = -1
                if real_pt == "pos.x": idx = 0
                elif real_pt == "pos.y": idx = 1
                elif real_pt == "pos.z": idx = 2
                elif real_pt == "dir.x": idx = 3
                elif real_pt == "dir.y": idx = 4
                elif real_pt == "dir.z": idx = 5
                elif real_pt == "color.r": idx = 6
                elif real_pt == "color.g": idx = 7
                elif real_pt == "color.b": idx = 8
                elif real_pt == "brightness": idx = 9
                elif real_pt == "thickness": idx = 10
                elif real_pt == "divergence": idx = 11
                elif real_pt == "attenuation": idx = 12
                elif real_pt == "params.x": idx = 13
                elif real_pt == "params.y": idx = 14
                elif real_pt == "params.z": idx = 15
                elif real_pt == "params.w": idx = 16
                
                if idx >= 0:
                     current_val = omp[idx]
            elif param_name.startswith("offset_"):
                op = laser.offset_params
                real_pt = param_name[7:]
                idx = -1
                if real_pt == "pos.x": idx = 0
                elif real_pt == "pos.y": idx = 1
                elif real_pt == "pos.z": idx = 2
                elif real_pt == "dir.x": idx = 3
                elif real_pt == "dir.y": idx = 4
                elif real_pt == "dir.z": idx = 5
                elif real_pt == "color.r": idx = 6
                elif real_pt == "color.g": idx = 7
                elif real_pt == "color.b": idx = 8
                elif real_pt == "brightness": idx = 9
                elif real_pt == "thickness": idx = 10
                elif real_pt == "divergence": idx = 11
                elif real_pt == "attenuation": idx = 12
                elif real_pt == "params.x": idx = 13
                elif real_pt == "params.y": idx = 14
                elif real_pt == "params.z": idx = 15
                elif real_pt == "params.w": idx = 16
                
                if idx >= 0:
                     val = op[idx]
                     if real_pt.startswith("color"): val *= 255.0
                     elif real_pt == "divergence": val = math.degrees(val)
                     current_val = val
            else:
                p = laser.params
                if param_name == "pos.x": current_val = p[0]
                elif param_name == "pos.y": current_val = p[1]
                elif param_name == "pos.z": current_val = p[2]
                elif param_name == "dir.x": current_val = p[3]
                elif param_name == "dir.y": current_val = p[4]
                elif param_name == "dir.z": current_val = p[5]
                elif param_name == "color.r": current_val = p[6] * 255.0
                elif param_name == "color.g": current_val = p[7] * 255.0
                elif param_name == "color.b": current_val = p[8] * 255.0
                elif param_name == "brightness": current_val = p[9]
                elif param_name == "thickness": current_val = p[10]
                elif param_name == "divergence": current_val = math.degrees(p[11])
                elif param_name == "attenuation": current_val = p[12]
                elif param_name == "params.x": current_val = p[13]
                elif param_name == "params.y": current_val = p[14]
                elif param_name == "params.z": current_val = p[15]
                elif param_name == "params.w": current_val = p[16]
                elif param_name == "type": current_val = float(laser.type)

        duration = float(self.project.total_measures * self.project.beats_per_bar)
        track.keyframes.append(Keyframe(0.0, current_val)) # Start
        track.keyframes.append(Keyframe(duration, current_val)) # End
        
        self.project.tracks.append(track)
        self.sort_tracks() # Sort after adding
        
        self.statusBar.showMessage(f"已创建轨道: {track_name}", 3000)
        
        self.on_project_modified()
        
        if hasattr(self, 'track_window'):
            self.track_window.refresh_tracks()

    def create_random_automation(self, source_name, param_name):
        dialog = RandomizationDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            track_name = f"{source_name}.{param_name}"
            
            # Find or Create Track
            track = None
            for t in self.project.tracks:
                if t.name == track_name:
                    track = t
                    break
            
            if not track:
                track = Track(name=track_name, track_type="param", target_laser=source_name, target_param=param_name)
                self.project.tracks.append(track)
            
            min_v = data["min"]
            max_v = data["max"]
            interval = data["interval"]
            smooth = data["smooth"]
            curve = CurveType.SMOOTH if smooth else CurveType.HOLD
            
            duration = 64.0
            seq = Sequence(start_time=0.0, duration=duration)
            
            current_time = 0.0
            while current_time <= duration:
                val = random.uniform(min_v, max_v)
                seq.add_keyframe(current_time, val, curve)
                current_time += interval
            
            track.sequences.append(seq)
                
            self.statusBar.showMessage(f"已生成随机自动化: {track_name}", 3000)
            
            self.on_project_modified()
            
            if hasattr(self, 'track_window'):
                self.track_window.refresh_tracks()

    def load_stylesheet(self):
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "resources", "dark_theme.qss")
        # Fix path resolution: __file__ is src/ui/main_window.py -> src/ui -> src -> src/resources/dark_theme.qss
        # actually relative to main_window.py: ../resources/dark_theme.qss
        try:
            # Try loading from absolute path based on known structure or relative
            # Let's try to find it relative to this file
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # .../src
            qss_path = os.path.join(base_dir, "resources", "dark_theme.qss")
            
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print(f"Failed to load stylesheet: {e}")
            # Fallback simple style
            self.setStyleSheet("QMainWindow { background-color: #333; color: white; }")

    def create_docks(self):
        # Track Window (Bottom) - Renamed from Timeline
        self.dock_timeline = QDockWidget("轨道窗", self)
        self.dock_timeline.setObjectName("dock_timeline")
        self.dock_timeline.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.track_window = TrackWindow(self.project)
        self.track_window.setMinimumHeight(400) # Set initial height to 2x (approx 400px, original likely ~200 default)
        self.dock_timeline.setWidget(self.track_window)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_timeline)
        
        # Project Management (Left Top)
        self.dock_project_mgr = QDockWidget("工程管理", self)
        self.dock_project_mgr.setObjectName("dock_project_mgr")
        self.dock_project_mgr.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.project_panel = ProjectPanel(self.project)
        self.dock_project_mgr.setWidget(self.project_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_project_mgr)

        # Source List (Left Bottom)
        self.dock_sources = QDockWidget("光源列表", self)
        self.dock_sources.setObjectName("dock_sources")
        self.dock_sources.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.source_panel = SourcePanel(self.project)
        self.dock_sources.setWidget(self.source_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_sources)
        
        # Properties (Right)
        self.dock_props = QDockWidget("属性面板", self)
        self.dock_props.setObjectName("dock_props")
        self.dock_props.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.props_panel = PropertiesPanel()
        self.props_panel.set_project(self.project)
        self.dock_props.setWidget(self.props_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_props)

    def set_snap(self, val):
        if hasattr(self, 'track_window'):
            self.track_window.set_snap_granularity(val)
            self.statusBar.showMessage(f"吸附已设置为: {val}拍", 2000)

    def on_project_modified(self):
        self.is_modified = True
        title = "激光秀设计软件 (Python版)"
        if self.current_file_path:
            title += f" - {os.path.basename(self.current_file_path)}"
        else:
            title += " - 未命名"
        title += " *"
        self.setWindowTitle(title)
        
        # Notify simulator that data changed
        if hasattr(self, 'simulator'):
            self.simulator.on_data_changed()

    def on_audio_added(self, file_path):
        self.simulator.load_audio(file_path)
        self.on_project_modified()

    def new_project(self):
        if self.is_modified:
            reply = QMessageBox.question(self, "保存工程", "当前工程有未保存的修改，是否保存？", 
                                         QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Yes:
                self.save_project()
                
        # Reset Project
        self.project = Project()
        self.current_file_path = None
        self.is_modified = False
        self.setWindowTitle("激光秀设计软件 (Python版)")
        
        self.simulator.set_project(self.project)
        self.project_panel.set_project(self.project)
        self.source_panel.set_project(self.project)
        self.track_window.set_project(self.project)
        self.props_panel.set_project(self.project)
        self.props_panel.set_source(None)
        
        self.reload_shader_with_feedback()
        self.track_window.refresh_tracks()
        self.source_panel.refresh_list()
        
    def open_project(self):
        if self.is_modified:
            reply = QMessageBox.question(self, "保存工程", "当前工程有未保存的修改，是否保存？", 
                                         QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Yes:
                self.save_project()
                
        file_path, _ = QFileDialog.getOpenFileName(self, "打开工程", "", "Laser Show Project (*.lss)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    new_project = Project.from_dict(data)
                    
                self.project = new_project
                self.current_file_path = file_path
                self.is_modified = False
                self.setWindowTitle(f"激光秀设计软件 (Python版) - {os.path.basename(file_path)}")
                
                self.simulator.set_project(self.project)
                self.project_panel.set_project(self.project)
                self.source_panel.set_project(self.project)
                self.track_window.set_project(self.project)
                self.props_panel.set_project(self.project)
                self.props_panel.set_source(None)
                
                self.reload_shader_with_feedback()
                self.track_window.refresh_tracks()
                self.source_panel.refresh_list()
                self.statusBar.showMessage(f"已加载工程: {file_path}", 3000)
                
            except Exception as e:
                QMessageBox.critical(self, "打开失败", f"无法加载工程文件:\n{e}")

    def save_project(self):
        if not self.current_file_path:
            file_path, _ = QFileDialog.getSaveFileName(self, "保存工程", "", "Laser Show Project (*.lss)")
            if not file_path:
                return
            if not file_path.endswith('.lss'):
                file_path += '.lss'
            self.current_file_path = file_path
            
        try:
            data = self.project.to_dict()
            with open(self.current_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
                
            self.is_modified = False
            self.setWindowTitle(f"激光秀设计软件 (Python版) - {os.path.basename(self.current_file_path)}")
            self.statusBar.showMessage(f"工程已保存: {self.current_file_path}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法保存工程文件:\n{e}")

    def export_glsl(self):
        # 1. Ask for split configuration
        dialog = ExportSplitDialog(self.project.total_measures, self)
        if dialog.exec() != QDialog.Accepted:
            return
            
        measures_per_file = dialog.get_data()
        
        # 2. Select Save Location (Base Name)
        file_path, _ = QFileDialog.getSaveFileName(self, "导出 GLSL", "laser_show.glsl", "GLSL Shader (*.glsl *.frag)")
        if not file_path:
            return
            
        base_dir = os.path.dirname(file_path)
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        
        try:
            exporter = GLSLExporter(self.project)
            total_measures = self.project.total_measures
            
            start_measure = 1
            exported_files = []
            
            while start_measure <= total_measures:
                end_measure = min(start_measure + measures_per_file - 1, total_measures)
                
                # Generate Code for Range
                project_code = exporter.export(start_measure, end_measure)
                
                # Construct Filename: base1-20.glsl
                out_name = f"{base_name}{start_measure}-{end_measure}.glsl"
                out_path = os.path.join(base_dir, out_name)
                
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(project_code)
                
                exported_files.append(out_name)
                start_measure += measures_per_file
                
            msg = f"已成功导出 {len(exported_files)} 个文件:\n"
            if len(exported_files) > 5:
                msg += "\n".join(exported_files[:5]) + "\n..."
            else:
                msg += "\n".join(exported_files)
                
            self.statusBar.showMessage(f"GLSL 批量导出完成", 3000)
            QMessageBox.information(self, "导出成功", msg)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "导出失败", f"导出过程中发生错误:\n{e}")

    def closeEvent(self, event):
        if self.is_modified:
            reply = QMessageBox.question(self, "退出", "当前工程有未保存的修改，是否保存？", 
                                         QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.Yes:
                self.save_project()
        
        self.save_ui_state()
        event.accept()

    def create_menu(self):
        menu = self.menuBar()
        
        # File
        file_menu = menu.addMenu("文件")
        file_menu.addAction("新建工程", self.new_project)
        file_menu.addAction("打开工程...", self.open_project)
        file_menu.addAction("保存工程", self.save_project)
        file_menu.addSeparator()
        file_menu.addAction("导出 GLSL...", self.export_glsl)
        file_menu.addAction("退出", self.close)
        
        # Edit
        edit_menu = menu.addMenu("编辑")
        edit_menu.addAction("撤销")
        edit_menu.addAction("重做")
        edit_menu.addSeparator()
        
        snap_menu = edit_menu.addMenu("轨道吸附颗粒度")
        snap_menu.addAction("1拍", lambda: self.set_snap(1.0))
        snap_menu.addAction("1/2拍", lambda: self.set_snap(0.5))
        snap_menu.addAction("1/4拍", lambda: self.set_snap(0.25))
        snap_menu.addAction("1/8拍", lambda: self.set_snap(0.125))
        
        # View
        view_menu = menu.addMenu("视图")
        view_menu.addAction(self.dock_timeline.toggleViewAction())
        view_menu.addAction(self.dock_project_mgr.toggleViewAction())
        view_menu.addAction(self.dock_sources.toggleViewAction())
        view_menu.addAction(self.dock_props.toggleViewAction())
        
        # Help
        help_menu = menu.addMenu("帮助")
        help_menu.addAction("关于")
