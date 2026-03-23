# 撤销重做(Undo/Redo)功能操作整理

本文档汇总了在“激光秀设计工具”中，所有会修改核心工程数据(`Project`、`LaserSource`、`Track`、`Sequence`、`Keyframe` 等)并需要支持撤销和重做(Undo/Redo)功能的操作。

## 1. 工程全局设置 (Project Settings)
*(主要在 `ProjectPanel` 和 `MainWindow` 中触发)*
- **修改 BPM** (`bpm_spin` 值改变)
- **修改拍号 (Time Signature)** (`ts_combo` 文本改变)
- **修改工程长度 (Total Measures)** (`len_spin` 值改变)

## 2. 光源管理 (Laser Sources Management)
*(主要在 `SourcePanel` 中触发)*
- **新建光源 (Create Source)**：添加新的 `LaserSource` 到列表中。
- **复制光源 (Copy Source)**：深拷贝选中的 `LaserSource` 并重命名添加到列表中。
- **删除光源 (Delete Source)**：将选中的 `LaserSource` 从列表中移除。

## 3. 光源属性编辑 (Laser Source Properties)
*(主要在 `PropertiesPanel` 和 `ValidatedLineEdit` 中触发)*
- **基本属性修改**：
  - 修改光源名称 (Name)
  - 修改光源类型 (Type, 0-4)
- **主控/附属关系修改 (Master/Slave)**：
  - 开启/关闭“设为主控光源”开关 (is_master)
  - 选择/更改附属光源列表 (subordinate_ids / master_id 绑定解除)
- **变换参数修改 (Transform)**：
  - 修改位置 (Pos X/Y/Z)
  - 修改方向 (Dir X/Y/Z)
- **外观参数修改 (Appearance)**：
  - 修改颜色 (Color R/G/B)
  - 修改亮度 (Brightness)
  - 修改粗细/缩放 (Thickness)
  - 修改发散角 (Divergence)
  - 修改衰减 (Attenuation)
- **高级参数修改 (Params & Local Up)**：
  - 修改 Param X/Y/Z/W
  - 修改 Local Up X/Y/Z
- **偏移参数修改 (Offset Params)**：
  - 针对所有 Transform, Appearance, Params 等属性的对应 Offset 值修改。
- **偏移模式切换 (Offset Mode Params)**：
  - 切换各个属性的偏移模式 (自身叠加 vs 主控叠加)。

## 4. 轨道与自动化管理 (Tracks & Automation)
*(主要在 `TrackWindow`、`TrackHeaderWidget` 和 `MainWindow` 中触发)*
- **添加音频轨道**：导入音频并自动生成对应的音频 `Track` 和 `Sequence`。
- **创建自动化轨道**：从属性面板为某个参数(如位置、颜色等)创建新的参数 `Track`。
- **创建动态随机轨道**：生成带有随机关键帧序列的自动化 `Track`。
- **重命名轨道**：修改 `Track.name`。
- **删除轨道**：将指定的 `Track` 从工程中移除。
- **启用/禁用轨道 (Enable/Disable)**：切换 `Track.enabled` 状态。
- **设置参数范围 (Set Range)**：修改 `Track.min_val` 和 `Track.max_val`。
- **轨道折叠状态改变**。

## 5. 片段管理 (Sequences / Clips)
*(主要在 `ResizeHandle` 和 `BaseSequenceItem` 及其子类中触发)*
- **移动片段 (Move Sequence)**：水平拖拽改变片段的 `start_time`。
- **缩放/裁剪片段 (Resize Sequence)**：拖拽左右边缘改变片段的 `duration`（对于音频还包含 `audio_offset` 偏移量改变）。

## 6. 关键帧管理 (Keyframes)
*(主要在 `KeyframeItem`、`TensionHandleItem` 和 `TrackWindow` 中触发)*
- **添加关键帧**：在曲线或轨道上点击生成新的 `Keyframe`。
- **删除关键帧**：通过右键菜单删除 `Keyframe`。
- **移动关键帧 (Move Keyframe)**：拖拽改变关键帧的时间 (`time`) 和 参数值 (`value`)。
- **修改关键帧值**：通过双击/右键菜单输入精确值、或粘贴值修改 `value`。
- **修改曲线类型 (Curve Type)**：通过右键菜单改变当前关键帧所在线段的插值方式（如平滑、保持、单曲线、脉冲波等）。
- **修改曲线张力 (Tension)**：
  - 拖拽张力控制点（菱形手柄）改变 `tension`。
  - 通过右键菜单输入精确张力值、或粘贴张力值修改 `tension`。

---

> **设计建议：**
> 由于本软件数据主要集中在单一的 `Project` 模型树下，实现 Undo/Redo 建议采用 **命令模式 (Command Pattern)** 封装以上具体修改。