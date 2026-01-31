# Visual FSM Designer for FPGA 🚀

[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](https://github.com/YourUsername/Visual-FSM-Designer)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20MacOS-lightgrey.svg)]()
[![AI-Powered](https://img.shields.io/badge/AI--Collaboration-Gemini--3--Flash-blueviolet.svg)]()

> **"让状态机设计回归逻辑本质，而非繁琐的连线绘图。"**

**Visual FSM Designer** 是一款基于逻辑驱动的 FPGA 状态机可视化设计工具。它打破了传统“手动画图、手动写代码”的低效模式，通过结构化表格录入逻辑，实时生成无交叉的状态转移图，并自动导出 Verilog 代码。

---

## 🌟 核心特性

### 1. 逻辑驱动布局 (Logic-Driven Layout)
无需关心状态框放在哪里，线怎么绕。只需在表格中定义 `Source -> Destination`，程序通过 **Graphviz Dot** 算法自动计算最优拓扑路径，确保大规模状态机依然清晰可见。

### 2. 智能实时预览 (Real-time Preview)
- **实时绘图**：每一次按键修改都会立即触发图形渲染刷新。
- **自动补全**：内置智能词库，支持 `Tab` 键快速补全状态名。
- **冲突预警**：实时检测逻辑多驱动（同一状态下相同条件的多次跳转），冲突行自动标红提示。

### 3. 高可靠硬件代码生成 (Hardware-Ready Verilog)
- **纯时序设计 (Pure Sequential)**：生成的 Verilog 采用寄存器打拍输出风格，避免组合逻辑毛刺，对时序收敛极度友好。
- **状态编码可选**：
  - `Binary`: 紧凑型二进制编码。
  - `One-hot`: 极速独热码，适合高速 FPGA 设计。
  - `Gray`: 格雷码，降低状态跳转时的翻转率。
- **信号参数化**：自动提取输入/输出逻辑，生成 Parameter 定义段，方便模块集成。

### 4. 工程持久化
- 支持 `.json` 格式的工程保存与读取，方便团队间共享状态机逻辑设计。

---

## 🛠 技术架构

本工具采用经典 **MVC (Model-View-Controller)** 架构：
- **View**: 使用 `PySide6 (Qt for Python)` 构建的高性能 GUI。
- **Controller**: 包含冲突检测算法、编码转换引擎及代码生成模板。
- **Model**: 基于 JSON 的序列化数据结构。
- **Graph Engine**: 使用开源 `Graphviz` 作为后端图形布局算法。

---

## 🚀 快速开始 (Quick Start)

本项目提供两种运行方式：**封装发行版**（即插即用）及 **源码运行版**（适合二次开发）。

### 📦 方案 A：使用封装发布版 (推荐)
如果你下载的是从 [Releases](../../releases) 页面获取的 `.zip` 压缩包：
1. **解压** 压缩包至本地任意目录。
2. **运行环境**：确保 `FSM_Designer_V1.0.exe` 与 `graphviz_runtime` 文件夹处于**同一级目录**下。
3. **启动**：直接双击运行 `FSM_Designer_V1.0.exe`。
   > **注意**：封装版已内置最小化绘图引擎，你**无需**在电脑上安装 Python 或 Graphviz。

---

### 🐍 方案 B：使用源码运行 (开发者模式)
如果你希望直接运行 `.py` 源码，请按照以下步骤配置环境：

#### 1. 安装 Python 依赖库
在终端执行以下命令安装 GUI 框架及 Python 包装库：
```bash
pip install PySide6 graphviz
```

#### 2. 安装 Graphviz 绘图引擎
源码运行依赖系统级的 Graphviz 渲染器，请根据你的操作系统安装：
- **Windows**: 以管理员身份打开 PowerShell 执行 `winget install graphviz`，或从 [官网下载安装包](https://graphviz.org/download/)。
- **Linux (Ubuntu/Debian)**: `sudo apt install graphviz`
- **MacOS**: `brew install graphviz`
> **提示**：安装完成后，请确保 `dot` 命令已加入系统环境变量 PATH。

#### 3. 启动程序
在项目根目录下执行：
```bash
python fsm1_0_0.py
```

---

## 📖 使用指南

1. **信号定义**：在“信号参数定义”选项卡中定义你的输入、输出常量（如 `IDLE=2'b00`）。
2. **逻辑编写**：在“状态转移逻辑”表格中填写跳转关系。
   - 输入 `S_IDLE` 到 `S_WORK`。
   - 条件填写 `start == 1'b1`。
   - 动作填写 `po_en = 1'b1`。
3. **设置复位**：在上方下拉框选择你的 Reset 状态。
4. **生成代码**：点击“生成 Verilog”按钮，直接获取可用于工程的 `.v` 代码片段。

---

## 📅 版本记录

- **V1.0.0 (Stable)**
  - 修复了空单元格访问引发的 `NoneType` 崩溃问题。
  - 引入了 `safe_get_text` 健壮性机制。
  - 优化了 Tab 键自动补全的交互体验。
- **V0.7.0**
  - 增加格雷码与独热码自动计算功能。
  - 加入内置帮助系统与官方 101 序列检测器示例。
- **V0.1.0**
  - 完成核心架构开发与实时绘图链路。

---

## 🤝 贡献与参与

我们非常欢迎开发者加入这个开源项目！
1. **Fork** 本仓库。
2. 创建你的 **Feature 分支** (`git checkout -b feature/AmazingFeature`)。
3. **Commit** 你的修改 (`git commit -m 'Add some AmazingFeature'`)。
4. **Push** 到分支 (`git push origin feature/AmazingFeature`)。
5. 发起一个 **Pull Request**。

---

## 📜 许可证

本项目基于 **MIT License** 开源。鼓励自由修改、分发及使用。

---

## 💎 致谢

- 感谢 [Graphviz](https://graphviz.org/) 团队提供的卓越布局引擎。
- 本项目由 **Gemini AI** 协作完成，探索了 AI 与硬件设计辅助工具结合的新范式。

---
*如果你觉得这个工具有所帮助，请给仓库一个 ⭐ Star！*
