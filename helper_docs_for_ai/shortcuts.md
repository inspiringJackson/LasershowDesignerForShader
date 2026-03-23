# LaserShowDesigner 快捷键指南

## 主窗口快捷键 (Main Window)
*定义位置：`src/ui/main_window.py`*

| 快捷键 | 功能描述 | 对应方法 |
| :--- | :--- | :--- |
| `Ctrl + R` | 重载 Shader | `reload_shader_with_feedback` |
| `Ctrl + S` | 保存项目 | `save_project` |
| `Ctrl + Z` | 撤销 | `undo_action` |
| `Ctrl + Y` | 重做 | `redo_action` |
| `Ctrl + Shift + Z` | 重做 (备用) | `redo_action_alt` |
| `Esc` | 切换播放/暂停 | `simulator.toggle_playback` |

## 模拟器视角导航 (Simulator View)
*定义位置：`src/ui/simulator.py`*

| 快捷键 | 功能描述 |
| :--- | :--- |
| `W` | 相机向前移动 |
| `S` | 相机向后移动 |
| `A` | 相机向左移动 |
| `D` | 相机向右移动 |
| `Space` (空格) | 相机向上移动 |
| `Shift` | 相机向下移动 |
| `Ctrl` (按住) | 相机移动加速 (3倍速) |
| `Esc` | 切换播放/暂停 |

## 时间轴操作 (Track Window)
*定义位置：`src/ui/track_window.py`*

| 组合键 | 功能描述 |
| :--- | :--- |
| `Ctrl + 鼠标滚轮` | 时间轴缩放 (Zoom in/out) |
| `Shift + 鼠标滚轮` | 时间轴横向滚动 (Horizontal Scroll) |
| `Ctrl + C` | 复制锚点参数（仅当选中一个锚点时生效） |
| `Ctrl + V` | 粘贴参数到所有当前选中的锚点 |
| `Ctrl + 鼠标左键点击` | 在同一轨道内多选/取消多选锚点 |
| `Shift + 鼠标左键点击` | 在同一轨道内批量选择两点之间的所有锚点 |
| `Shift + 鼠标左键拖拽` | 在拖拽锚点时锁定参数值（Y轴），仅允许水平改变时间位置 |