# Smart Car Path Planner

一个面向智能车视觉赛题的 16 x 12 栅格路径规划项目。它把“推箱子”规则改造成更接近比赛任务的工程模型：小车有方向、箱子和目标点需要编号匹配、102/103 需要先进行视觉识别路线规划，103 还加入可推动炸弹和炸墙机制。项目同时提供 PC 端 Python 求解器、OpenCV 截图识别、Tkinter 动画演示、原生 Android 地图编辑与跑图 APP，以及 STM32F304 固件导出思路。

[Latest APK Release](https://github.com/xianshengl487-star/smart-car-path-planner/releases/latest) · [Core logic](docs/CORE_LOGIC.md) · [Android source](android_native/) · [STM32 notes](embedded/stm32f304/) · [Optimization roadmap](OPTIMIZATION_ROADMAP.md)

> [!NOTE]
> 当前 Android APP 已打包上传到 GitHub Release。手机端可以自定义 101/102/103 地图并在本机跑规划逻辑，同时用扩展节点数、队列大小、动作长度、运行时间等限制来模拟 STM32F304 的资源约束。

## 项目亮点

- 16 x 12 竞赛风格地图，默认小车起点为第一列第五行，即内部坐标 `(row=5, col=1)`。
- 编号多箱规划：`B1 -> T1`、`B2 -> T2`、`B3 -> T3` 一一对应，箱子到达同号目标后消失，不再挡路。
- 102/103 支持识别阶段：小车先靠近箱子和目标点完成编号识别，再执行正式推箱路径。
- 103 支持炸弹：`X` 不需要识别；小车可推动炸弹，炸弹撞墙后爆炸并清除周围 3 x 3 内的非边界墙。
- 严格最短路径模式保留 A* 最优性，Android 端同时提供 STM32 风格的受限搜索模式。
- PC 端支持 OpenCV 识别程序生成图、比赛截图批处理、Tkinter 动画和 PNG 结果输出。
- 原生 Android APP 支持横屏地图编辑、逐步动画、播放/暂停、单步、x1/x2/x4/x8 快进。
- STM32F304 导出采用固定数组、1 字节动作、无动态分配，适合小 SRAM 单片机执行预规划动作。

## 规则模型

| Token | 含义 |
| --- | --- |
| `.` | 空白格 |
| `#` | 墙壁；边界墙不可被破坏 |
| `P` | 小车起点 |
| `E` | 101 简单导航模式终点 |
| `B1`, `B2`, ... | 编号箱子 |
| `T1`, `T2`, ... | 编号目标点 |
| `X` | 可推动炸弹 |

核心规则：

- 编号必须一一对应：存在 `B1` 就必须存在 `T1`，推错目标不算完成。
- 箱子到达同号目标后立刻从地图中消失，后续路径可以穿过该格。
- 小车是有方向的，转向、前进、推动都会计入动作序列。
- 102/103 的箱子和目标点需要先被小车靠近识别；炸弹不需要识别。
- 炸弹被推向空格时移动一格；被推向墙时在撞击墙格爆炸，清除周围 3 x 3 范围内的非边界墙。
- `D`、`*` 等早期调试符号已经废弃，解析器会主动拒绝。

## 关卡定义

| Level | Category | 目标 |
| --- | --- | --- |
| 101 | Cat 2 | 只推箱子；复杂度基准图，两个编号箱子，无识别预扫描，无炸弹 |
| 102 | Cat 2 | 地图复杂度与 101 接近，但小车需要先靠近箱子和目标点完成识别，再按编号推箱 |
| 103 | Cat 3 | 在 102 基础上增强复杂度，加入三个编号箱子和可推动炸弹 |

内置 Python 演示还保留 `--level 1/2/3` 三关：

- Level 1：直接读取代码内置编号地图求解，不走视觉识别。
- Level 2：生成关卡图像，用 OpenCV 识别出编号箱子和目标点后求解。
- Level 3：识别箱子/目标点，并叠加炸弹推送、撞墙爆炸、动态墙体变化。

## 系统结构

```text
.
├── planner/                  # Python A* 求解器、视觉识别、死锁剪枝、关卡定义
├── android_native/           # 原生 Android APP，含地图编辑器和 Java 规划核心
├── embedded/stm32f304/       # STM32F304 固件侧执行器说明与 C 核心
├── tests/                    # Python 单元测试、比赛截图测试、Android smoke 辅助
├── versions/                 # 优化迭代快照
├── 比赛关卡/                 # 本地比赛截图批处理输入
├── outputs/                  # 本地打包 APK、识别图、结果图、校验文件
├── main.py                   # PC 端主入口
├── map_editor.py             # PC 端 Tkinter 地图编辑器
├── export_stm32.py           # 导出 STM32 预规划动作
└── mcp_server.py             # Claude/Grok 可接入的本地 MCP 服务
```

## 快速开始

```powershell
cd "G:\路径规划"
python main.py --level 1 --no-gui
python main.py --level 2 --no-gui
python main.py --level 3 --no-gui
python main.py --all --no-gui
```

去掉 `--no-gui` 可以打开 Tkinter 动画演示：

```powershell
python main.py --all --delay 80
```

处理单张截图或批量比赛截图：

```powershell
python main.py --image "G:\路径规划\比赛关卡\example.png" --no-gui
python main.py --contest --no-gui --max-expanded 250000
```

打开 PC 端地图编辑器：

```powershell
python map_editor.py
```

## Android APP

`android_native/` 是原生 Android 项目，不是网页封装。手机端能力包括：

- 自定义 16 x 12 地图。
- 101/102/103 模板选择。
- 手机本地运行识别路线和推箱规划。
- 横屏逐格行驶动画。
- 播放/暂停、单步、x1/x2/x4/x8 快进。
- 地图合法性检查：边界墙、唯一 `P`、箱子和目标编号配对。
- 动作回放校验：验证移动、推箱、箱子消失、炸弹移动和爆炸结果。
- STM32 性能模拟：限制扩展节点数、最大队列、动作数和运行时间。

下载 APK：

- 最新 Release：[smart-car-path-planner/releases/latest](https://github.com/xianshengl487-star/smart-car-path-planner/releases/latest)
- 当前验证版：`SmartCarPlannerNative-validated-release-20260610-0923.apk`

本地重新打包：

```powershell
cd "G:\路径规划"
powershell -ExecutionPolicy Bypass -File .\package_android_app.ps1
```

Android 核心 smoke 测试：

```powershell
android_native\run_core_smoke.ps1
```

当前验证基线：

| 模式 | 101 | 102 | 103 |
| --- | ---: | ---: | ---: |
| strict shortest | 29 | 65 | 106 |
| stm32 relaxed | 29 | 65 | 106 |
| stm32 strict | - | - | 108 |

最近一次发布验证：`SmokeCore 12 passed, 0 failed`，`clean assembleDebug assembleRelease` 成功，Debug/Release APK 均通过 `apksigner`。

## STM32F304 集成

STM32F304 不运行完整 Python A*，推荐流程是 PC 端先求解并导出紧凑动作表，MCU 只执行固定动作和小范围局部 BFS。

```powershell
cd "G:\路径规划"
python export_stm32.py
```

生成文件：

- `embedded/generated/stm32_plans.h`
- `embedded/generated/stm32_memory_report.json`

固件侧使用：

- 复制 `embedded/stm32f304/planner_core.c`
- 复制 `embedded/stm32f304/planner_core.h`
- 复制 `embedded/generated/stm32_plans.h`
- 调用 `pp_runner_next()` 获取下一条固定大小命令
- 仅在局部修正场景调用 `pp_bfs_path()`

当前导出规模：

- 最大动作数：`106`
- 计划数据 Flash：约 `272 bytes`
- 运行 RAM：约 `968 bytes`
- 无 `malloc`、无递归、无 Python dict、无堆分配

## 算法概览

PC 端和 Android 端都围绕“方向小车 + 多箱状态”建模：

```text
state = player_pose + boxes_by_id + delivered_mask + bombs + dynamic_walls + recognized_mask
```

主要策略：

- 外层使用 A* 搜索推箱、推炸弹和识别动作。
- 内层使用方向 BFS 判断小车是否能到达某个推动姿态。
- 编号箱子使用固定目标匹配，避免普通 Sokoban 中的任意目标分配。
- 已送达箱子用 `delivered_mask` 移除，占用判断不再把它当障碍。
- 死锁剪枝包含角落、墙边线、动态箱子互堵等安全规则。
- 固定墙地图使用反向单箱 push-distance 启发式；炸弹仍可能改变墙体时退回安全下界。
- Android 受限模式用扩展节点、frontier、动作数和时间预算模拟 STM32 性能边界。

## OpenCV 视觉识别

Python 端支持两种视觉入口：

- 程序生成关卡 PNG，再按 16 x 12 网格切块识别颜色和编号。
- 批处理 `比赛关卡/` 中的比赛截图，自动忽略行列标签，只识别实际网格区域。

识别策略：

- 黄色区域识别为箱子。
- 蓝色区域识别为目标点。
- 小车起点强制对齐到 `(row=5, col=1)`。
- 若截图编号不可靠，先按读取顺序编号，再用小规模精确 A* 探测循环映射，最后回退到完整严格 A*。

本地 7 张比赛截图当前可全部求解，批处理时间约 22 秒。

## MCP 接入

本地 stdio MCP 服务可供 Claude Code / Grok Build 调用：

```powershell
cd "G:\路径规划"
.\run_mcp_server.bat
```

暴露工具：

- `list_levels`
- `solve_level`
- `render_level`
- `solve_contest_folder`

健康检查：

```powershell
claude mcp get smart-car-planner
grok mcp doctor smart-car-planner
```

> [!IMPORTANT]
> MCP 服务能把本项目的求解能力暴露给支持 MCP 的客户端，但不能直接“操控”外部 Grok 或 Claude 窗口；是否可用取决于对应客户端是否正确安装并启用该 MCP 服务。

## 验证命令

```powershell
cd "G:\路径规划"
python -m compileall -q .
python -m unittest discover -s tests -v
python main.py --all --no-gui
python main.py --contest --no-gui --max-expanded 250000
python export_stm32.py
android_native\run_core_smoke.ps1
```

Android 完整构建：

```powershell
$env:JAVA_HOME='C:\Program Files\Zulu\zulu-17'
$env:ANDROID_HOME='C:\Users\maoyaowei\AppData\Local\Android\Sdk'
$env:ANDROID_SDK_ROOT=$env:ANDROID_HOME
& 'C:\Users\maoyaowei\AppData\Local\BlockForgeStudio\gradle\gradle-8.14.4\bin\gradle.bat' -p 'G:\路径规划\android_native' clean assembleDebug assembleRelease
```

## 当前状态

这个项目已经完成从 PC 原型到手机端 APP、再到 STM32 执行模型的闭环：

- PC：适合调试算法、识别截图、生成动画和 benchmark。
- Android：适合现场改图、横屏跑图、观察动画和模拟单片机性能限制。
- STM32：适合执行 PC/手机侧规划好的紧凑动作序列。

后续优化方向记录在 [OPTIMIZATION_ROADMAP.md](OPTIMIZATION_ROADMAP.md)，包括模式数据库、双向宏搜索、安全死锁学习和嵌入式有界搜索。

更详细的算法与代码说明见 [docs/CORE_LOGIC.md](docs/CORE_LOGIC.md)。
