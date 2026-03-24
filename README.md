# 激光秀设计软件 (Laser Show Designer)

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey.svg)

## 📖 项目简介
**Laser Show Designer** 是一款基于 Shader 的仿真激光秀设计与编排工具。本项目为创作者提供了一个现代化的桌面图形界面，允许用户通过多轨道时间轴、关键帧动画、音频同步等方式，轻松编排复杂的激光灯光效果。
设计完成后，软件能够将编排数据直接编译/导出为 GLSL (OpenGL Shading Language) 代码。导出的着色器代码可无缝集成到各种基于 Shader 的渲染引擎中（如 Minecraft 的光影包，或独立的 OpenGL/WebGL 项目），实现令人震撼的实时激光秀渲染。

## ✨ 功能特性
- **🎥 实时 3D 仿真预览**：内置基于 OpenGL 的实时渲染器，在编辑过程中即时预览激光光束、色彩、散射与移动效果。
- **⏱️ 多轨道时间轴编辑**：支持类似非编软件的时间轴视图，可独立控制激光器的位置、方向、颜色、亮度、厚度及自定义参数。
- **🔑 灵活的关键帧系统**：支持多种补间曲线类型（Smooth、Hold、Single Curve、Stairs、Pulse、Wave），通过张力(Tension)参数微调动画节奏。
- **🎵 音频同步**：支持导入音频文件（通过 Pygame/QMediaPlayer），让激光参数的律动能够与音乐节拍精准对齐。
- **🎛️ 属性与源管理**：集中管理所有激光源设备及其属性，支持通过表达式和自动化快速生成随机或规律性的动画。
- **📤 GLSL 代码导出**：一键将所有关键帧与曲线逻辑烘焙为高效的 GLSL 着色器函数（`drawLaserShow`），开箱即用。

## 🛠️ 技术架构
- **编程语言**：Python 3.11+
- **GUI 框架**：PySide6 (Qt for Python)，提供现代化、响应迅速的用户界面及深色主题。
- **图形与渲染**：
  - **PyOpenGL**：用于核心 3D 场景的实时渲染与 Shader 编译。
  - **NumPy**：处理底层矩阵运算与三维向量变换。
- **音频系统**：Pygame & QtMultimedia，处理跨平台的音频加载与时间轴同步播放。
- **打包分发**：PyInstaller 配合跨平台构建脚本（Windows 包含静默安装配置，macOS 支持打包为 DMG 镜像）。

## 📦 环境依赖与安装步骤

### 1. 开发环境配置
确保您的系统中已安装 Python 3.11 或更高版本。

```bash
# 1. 克隆项目到本地
git clone https://github.com/your-username/LaserShowDesigner.git
cd LaserShowDesigner

# 2. 创建并激活虚拟环境（推荐）
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. 安装依赖包
pip install -r requirements.txt
pip install pytest bandit pyinstaller pillow  # 构建与测试额外依赖

# 4. 运行应用
python src/main.py
```

### 2. 构建独立可执行文件
项目根目录提供了自动化构建脚本：
- **Windows**: 在 PowerShell 中运行 `.\build.ps1`，将在 `release/` 目录生成包含 `.exe` (或独立 zip) 的打包产物，并附带依赖扫描与测试。
- **macOS**: 运行 `./build_macos.sh`，将打包生成 macOS 支持的 `.dmg` 磁盘镜像文件（需要 Apple 开发者账户进行签名和公证配置）。

## 🕹️ 使用指南

1. **创建与管理激光源**：
   在界面的 "源管理器 (Source Panel)" 中，点击添加新的激光设备，并为其命名（如 `MasterLaser`）。
2. **编辑轨道**：
   在底部的时间轴 "Track Window" 中，选择对应的激光源，添加所需的控制参数轨道（例如 `pos.x`，`color.r`，`brightness` 等）。
3. **关键帧与曲线**：
   双击时间轴轨道即可添加关键帧。在右侧的 "属性面板 (Properties Panel)" 中，可以修改选中关键帧的数值、插值曲线类型（如 Smooth、Wave）及 Tension。
4. **音频对齐**：
   在时间轴导入音频文件，通过时间轴播放指针（Seek）预览对应时刻的激光效果。
5. **导出 GLSL**：
   编排满意后，点击 "导出" 或通过快捷键操作，软件会自动解析所有轨道，并生成包含 `drawLaserShow(vec3 cameraPos, vec3 viewDir, float maxViewDist, float time, vec3 targetPosUnused)` 入口函数的 `.glsl` 代码文件。

## 💡 核心 Shader 效果展示

导出的 GLSL 代码内置了极高效率的动画计算数学库，关键渲染逻辑涵盖：
- **光束求交与衰减**：利用视线向量与激光射线的最短距离，计算大气散射体积光。
- **曲线插值器**：内置 `interpolate_curve()` 函数，支持在 GPU 端直接还原软件中设计的复杂非线性数学动画（如阶梯、脉冲、三角波）。
- **时间系统**：自动将传入的外部环境 `time` 变量（如 Minecraft 中的太阳角度 `sunAngle`）映射为基于 BPM 的绝对节拍时间（`totalBeats`）。

```glsl
// 生成代码示例摘要
vec3 drawLaserShow(vec3 cameraPos, vec3 viewDir, float maxViewDist, float time, vec3 targetPosUnused) {
    const float BPM = 120.0;
    // ...时间换算逻辑...
    
    // 更新激光状态 (由关键帧系统生成)
    updateLasers(totalBeats, lasers);
    
    // 累加光束体积渲染色彩
    vec3 totalColor = vec3(0.0);
    for(int i=0; i<MAX_LASERS; i++) {
        totalColor += getLaserContribution(lasers[i], cameraPos, viewDir, maxViewDist, showTime);
    }
    return totalColor;
}
```

## 🤝 贡献指南
欢迎社区开发者共同完善 Laser Show Designer！
1. Fork 本仓库。
2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)。
3. 确保通过所有的单元测试和 Bandit 安全扫描 (`pytest tests/` & `bandit -r src/`)。
4. 提交您的修改 (`git commit -m 'Add some AmazingFeature'`)。
5. 推送到分支 (`git push origin feature/AmazingFeature`)。
6. 发起 Pull Request。

## 📄 许可证信息
本项目基于 **Apache License 2.0** 许可证开源。详情请参阅项目根目录下的 [LICENSE](LICENSE) 文件。
