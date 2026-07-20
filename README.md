# NXP_v2

`NXP_v2` 是当前这台主机上 NXP i.MX 板级开发系统的轻量 Git 视图。

它不是源码大仓，也不是重资源备份仓。
它保存的是：

- 系统怎么开工
- 资源如何分层
- 各 skill 的 owner 和边界
- 代码资产、编译对象、板级知识的入口文档

真正的镜像、工具链、SDK、源码树本体、固件 blob 和 case 产物，仍保留在本机工作区里，不整体进 Git。

## 这个仓库解决什么问题

这套系统用来支撑 NXP i.MX 系列嵌入式板级开发中的日常工作，例如：

- 客户问题理解
- 资源定位
- 产物链路确认
- 镜像/固件准备
- 板级烧写与启动验证
- 串口和运行日志反馈
- case 过程沉淀
- 高价值信息吸收进长期系统

它的核心目标不是“把所有东西都放进仓库”，而是把复杂工作拆成稳定、可路由、可持续演化的系统。

## 先看哪里

如果你第一次接触这个系统，建议按下面顺序看：

1. [workspace/AGENTS.md](/home/ives/桌面/NXP_v2/workspace/AGENTS.md)
2. [workspace/docs/architecture-construction/v3/ARCHITECTURE.md](/home/ives/桌面/NXP_v2/workspace/docs/architecture-construction/v3/ARCHITECTURE.md)
3. [workspace/docs/architecture-construction/v3/CONSTRUCTION.md](/home/ives/桌面/NXP_v2/workspace/docs/architecture-construction/v3/CONSTRUCTION.md)
4. [support_level/README.md](/home/ives/桌面/NXP_v2/support_level/README.md)

如果你已经在处理具体任务：

1. 先看 [workspace/AGENTS.md](/home/ives/桌面/NXP_v2/workspace/AGENTS.md)
2. 按当前 unresolved step 进入对应 skill
3. 再下沉到 `support_level` 对应 README 或 `USAGE.md`

## 核心文档怎么分工

这三个文档不要混着看，它们分别回答不同问题：

- [workspace/AGENTS.md](/home/ives/桌面/NXP_v2/workspace/AGENTS.md)
  回答“拿到任务后，当前系统应该怎么开工、怎么推进、case 放哪、高价值信息放哪”。
- [workspace/docs/architecture-construction/v3/ARCHITECTURE.md](/home/ives/桌面/NXP_v2/workspace/docs/architecture-construction/v3/ARCHITECTURE.md)
  回答“当前这套系统为什么这样分层，以及第一步如何把稳定关系写成分布式 `RELATION.yaml`”。
- [workspace/docs/architecture-construction/v3/CONSTRUCTION.md](/home/ives/桌面/NXP_v2/workspace/docs/architecture-construction/v3/CONSTRUCTION.md)
  回答“怎样在关键目录旁边逐步增加机器可读关系，为未来 MCP resolver 提供可靠数据源”。

如果只是使用当前系统，优先读 `AGENTS` 和 `ARCHITECTURE`。
如果是想在另一台机器、另一个团队或另一个领域复刻这种体系，再读 `CONSTRUCTION`。

## 顶层结构

仓库主要分成两块：

- `workspace/`
  轻量控制面。放入口规则、skill 和长期设计文档。
- `support_level/`
  本机支撑资源面。放重资源入口、板级知识、代码资产入口、编译对象入口、case 和待归纳信息。

可以把它理解成：

- `workspace/` 决定“怎么走”
- `support_level/` 决定“东西在哪、各自干什么”

## workspace/ 是什么

`workspace/` 当前最重要的内容是：

- [AGENTS.md](/home/ives/桌面/NXP_v2/workspace/AGENTS.md)
  总入口规则
- [docs/README.md](/home/ives/桌面/NXP_v2/workspace/docs/README.md)
  长期设计文档入口
- [docs/architecture-construction/v3/ARCHITECTURE.md](/home/ives/桌面/NXP_v2/workspace/docs/architecture-construction/v3/ARCHITECTURE.md)
  当前系统架构说明
- [docs/architecture-construction/v3/CONSTRUCTION.md](/home/ives/桌面/NXP_v2/workspace/docs/architecture-construction/v3/CONSTRUCTION.md)
  当前分布式关系元数据施工计划
- `.agents/skills/understanding/SKILL.md`
  高阶理解层
- `.agents/skills/support/SKILL.md`
  资源入口层
- `.agents/skills/compile/SKILL.md`
  编译路由层
- `.agents/skills/board-exec/SKILL.md`
  板级执行路由层

这四个 skill 的分工不是按“技术爱好”切的，而是按当前未解决步骤的 owner 切的：

- `understanding`
  先判断问题本质和当前 owner
- `support`
  找资源、找入口、找下沉路径
- `compile`
  定位编译对象和最小依赖集合
- `board-exec`
  维护板级动态事实、目标状态和允许动作，推进真实板状态

## support_level/ 是什么

`support_level/` 是系统的支撑资源面。
当前主要包括：

- `Image/`
  预下载镜像和现成烧写输入
- `SoC_material/`
  RM、原理图和硬件资料
- `board_knowledge/`
  已实测可复用的板级知识
- `code_assets/`
  共享代码资产入口
- `compile_targets/`
  编译对象入口
- `software_stacks/`
  跨项目的软件栈 / 软件线，例如 RTE 与 LF 家族、启动镜像内容差异
- `release_packages/`
  不可通过 Git 切版本的厂商 release 包
- `firmware/`
  DDR firmware、AHAB、固定 blob
- `linux_document/`
  Linux BSP 官方文档
- `toolchain/`
  交叉编译工具链和环境输入
- `tools/`
  主机侧工具入口
- `work/`
  每个 case 的完整过程记录
- `to_absorb/`
  待归纳的高价值信息

这里的文档不是为了“复制重资产内容”，而是为了回答：

- 本地有什么
- 放在哪里
- 各自负责什么
- 下一步该去哪一层

## code_assets/ 怎么理解

`support_level/code_assets/` 当前分成两类：

- `projects/`
  可按任务需要切 ref 的单个 Git 源码项目或 manifest
- `workspaces/`
  多仓协同才有意义的集成工作区

当前 `projects/` 的主要角色可以粗分为：

- 启动固件链：
  `imx-atf`、`imx-mkimage`、`imx-oei`、`imx-optee-os`、`imx-sm`、`uboot-imx`、`real-time-edge-uboot`
- Linux BSP 链：
  `linux-imx`、`real-time-edge-linux`、`meta-real-time-edge`
- M 核代码参考链：
  `mcuxsdk-core`
- Android 资产：
  `android`

当前 `workspaces/` 保留两个入口：

- `hmc-workspace`
  `heterogeneous-multicore / zsdk / mcuxsdk / .west` 的集成工作区
- `zephyr-workspace`
  当前本地默认的 Zephyr 工作区入口

特别强调两点：

1. `mcuxsdk-core` 只是代码参考，不是默认 release 编译入口  
   `M` 核 SDK 编译的首选 release 包入口始终是 `release_packages/m_freertos_sdk`。

2. 共享 workspace 不是 case 工作区  
   它们用来理解协同关系、核对版本和确认入口，不应默认直接承载 case 产物。

不可通过 Git 切版本的厂商 release 包，例如 `m_freertos_sdk` 和 `SCFW`，
放在 `support_level/release_packages/`。

## compile_targets/ 怎么理解

`support_level/compile_targets/` 放的不是源码，而是“我要编什么”的对象入口。

当前包括：

- `flashbin`
- `linux`
- `m_freertos_sdk`
- `zephyr`
- `a55_rtos`

正常使用顺序不是“直接进某个源码仓”，而是：

1. 先由 `compile` 判断当前对象
2. 再进入对应 `compile_targets/<target>/README.md`
3. 再下沉到需要的 `code_assets` 项目或 workspace

这样可以把：

- 资源位置
- 真实编译入口
- 依赖输入
- 不能直接拿来编的目录

区分开。

## case 和系统演化怎么做

### case

每个任务都应尽量落到：

- `support_level/work/<日期-芯片-问题>/`

每个 case 目录推荐最小结构：

- `README.md`
  目标、输入版本、成功判据、关键步骤、结论、交付项索引
- `records/`
  过程记录、步骤笔记、命令线索
- `logs/`
  串口日志、命令输出、运行日志、原始抓取
- `artifacts/`
  镜像、补丁、脚本、配置、打包结果
- `state/`
  跨 `compile -> board-exec` 推进时的 `handoff.yaml` 和 `ledger.yaml`

至少应保留：

- 目标与输入版本
- 关键步骤与中间结论
- 原始日志
- 生成的产物、补丁、脚本、配置
- 交接材料或其来源

这不是单纯的构建临时目录，而是后续可回放、可交接、可抽知识的完整过程容器。

### 系统生长

执行过程中出现新的、可复用、有长期价值的信息，不要立刻改正式 skill。

先放到：

- `support_level/to_absorb/`

并按最小模板保留：

- 来源 case
- 证据或原始线索
- 可复用结论
- 后续建议吸收到哪一层

这样当前交付和长期系统演化就不会混在一起。

## 使用这套系统时最重要的规则

### 1. 按 unresolved step 推进

不要预设每次都要走完整链路。
先判断当前未解决步骤是什么，再进入对应 skill。

### 2. support 先回答“东西在哪”

找镜像、资料、工具、源码、基线、SDK、workspace、case，都先走 `support`。
不要在入口层自己散乱遍历目录。

### 3. 共享基线和 case 工作区分开

共享基线可以做：

- 阅读
- 对比
- 版本核对
- 可逆 checkout / tag / branch 切换

只要进入：

- 修改
- 编译
- 生成输出
- case 临时派生

就应该转到 `work/<case>/`。

### 4. 板级任务按状态推进，不按命令推进

`board-exec` 的核心是维护：

- 当前板级动态事实
- 目标板状态
- 允许的下一步动作

不是先想到一条命令，再把命令当成计划。

### 5. Git 只保留轻量控制面

这个仓库默认只跟踪：

- 规则
- 架构
- skill
- README
- `USAGE.md`
- 板级知识入口

默认不跟踪：

- 下载来的镜像和 SDK
- toolchain 实体
- 源码树本体
- firmware blob
- case 产物

## 当前推荐读法

如果你要理解系统：

1. [README.md](/home/ives/桌面/NXP_v2/README.md)
2. [workspace/AGENTS.md](/home/ives/桌面/NXP_v2/workspace/AGENTS.md)
3. [workspace/docs/architecture-construction/v3/ARCHITECTURE.md](/home/ives/桌面/NXP_v2/workspace/docs/architecture-construction/v3/ARCHITECTURE.md)
4. [workspace/docs/architecture-construction/v3/CONSTRUCTION.md](/home/ives/桌面/NXP_v2/workspace/docs/architecture-construction/v3/CONSTRUCTION.md)
5. [support_level/README.md](/home/ives/桌面/NXP_v2/support_level/README.md)

如果你要开始做事：

1. 先看 `AGENTS.md`
2. 进入对应 skill
3. 再下沉到对应 README / `USAGE.md`
4. 把过程留在 `work/<case>/`
5. 把高价值信息留在 `to_absorb/`
