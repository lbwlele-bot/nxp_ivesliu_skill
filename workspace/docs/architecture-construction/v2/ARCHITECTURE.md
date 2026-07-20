# NXP_v2 当前系统架构

## 1. 系统定位

`NXP_v2` 不是一个把所有资源、源码、工具和 case 都直接塞进 Git 的“大仓库”。
它是当前本机 NXP i.MX 板级开发系统的轻量控制面：

- `workspace/`
  放入口规则、技能定义和架构文档
- `support_level/`
  放重资源、共享基线、板级知识、case 过程记录和待归纳信息

它服务的不是单一项目，而是一套长期复用的嵌入式问题处理系统。
目标有两个：

1. 完成当前客户任务
2. 让执行中沉淀出的高价值信息持续进入系统

---

## 2. 总体设计思路

当前系统按“按 unresolved step 推进”的方式工作，而不是预设每次都走完整链路。

也就是说，系统不会默认每个问题都按：

`需求确认 -> 理解 -> 编译 -> 上板 -> 登录 -> 运行验证`

完整跑一遍。

它的真实工作方式是：

1. 先确认当前未解决步骤是什么
2. 再决定当前 owner 应落在哪一层
3. 只进入当前需要的 skill 和资源入口
4. 用日志和板状态反馈决定下一步
5. 在 case 中保留完整过程
6. 把高价值信息送到待归纳区，后续再吸收到正式系统

这个设计有几个核心目的：

- 避免把“命令”误当成“计划”
- 避免把“旧观察”误当成“当前事实”
- 避免把“资源目录”误当成“执行入口”
- 避免把“共享基线”直接污染成 case 工作区

---

## 3. 分层架构

### 3.1 入口控制层

入口控制层在：

- `workspace/AGENTS.md`

这一层负责：

- 规定系统怎么开工
- 规定当前有哪些主 skill
- 规定 case 和高价值信息应该落在哪里
- 规定共享基线、case、板级动作和 Git 边界的总规则

这一层不负责：

- 具体源码项目怎么用
- 具体工具怎么调用
- 具体编译命令
- 具体板级 recipe

### 3.2 认知与路由层

这一层由四个主 skill 组成：

- `understanding`
- `support`
- `compile`
- `board-exec`

它们不是按“技术域”任意切分，而是按“当前 unresolved step 的 owner”切分。

#### `understanding`

负责高阶理解和 owner 判断。

典型问题：

- 眼前这个现象到底在证明什么
- 当前问题属于构建、板级状态还是资源定位
- `flash.bin`、`uuu`、`M` 核启动之类问题的本质是什么

它不负责给路径、不负责给命令，也不负责具体执行。

#### `support`

负责资源入口和 owner 定位。

它回答：

- 本地有哪些资源
- 各资源放在哪里
- 它们分别承担什么角色
- 下一步该进哪个 README、USAGE 或 skill

它不负责具体编译步骤，也不负责板级动作判断。

#### `compile`

负责编译对象路由和最小依赖集合确认。

它回答：

- 我现在到底要编什么
- 这次依赖哪些源码、workspace、toolchain、firmware、SDK
- 哪些只是输入，哪些才是当前真正的构建入口

它不拥有板级状态判断，也不直接承载每个项目的完整操作手册。

#### `board-exec`

负责真实板子的状态推进。

它回答：

- 当前板状态是什么
- 目标状态是什么
- 当前允许做哪些下一步动作
- 该下沉到哪个工具文档或板级知识文档

它的核心不是“执行命令”，而是维护板级动态事实、目标状态和允许动作。

### 3.3 支撑资源层

支撑资源层在：

- `support_level/`

这一层是系统的共享资产面。
它本身不做决策，但为前面的 skill 提供稳定资源入口。

当前主要包括：

- `Image/`
  预下载镜像和可直接复用的烧写输入
- `SoC_material/`
  RM、原理图和硬件资料
- `board_knowledge/`
  已实测、可复用的板级操作知识
- `code_assets/`
  长期保留的代码资产
- `compile_targets/`
  编译对象入口
- `software_stacks/`
  跨项目的软件栈 / 软件线，例如 RTE 与 LF 家族、启动镜像内容差异
- `release_packages/`
  不可通过 Git 切版本的厂商 release 包
- `firmware/`
  DDR firmware、AHAB、固定 blob
- `linux_document/`
  BSP 官方文档
- `toolchain/`
  工具链和构建环境输入
- `tools/`
  主机侧工具入口
- `work/`
  每个 case 的完整过程记录
- `to_absorb/`
  待归纳的高价值信息

---

## 4. 代码与构建资产模型

`support_level/code_assets/` 当前分成两类：

### 4.1 `projects/`

放可按任务需要切换 ref 的单个 Git 源码项目或 manifest。

它的角色是：

- 作为长期共享代码基线
- 作为源码阅读、版本核对、角色判断的入口
- 作为后续 `compile` 下沉到具体项目 `USAGE.md` 的承接点

它不应该自动被当成当前 case 的直接构建目录。

当前代表性内容：

- 启动固件链：
  `imx-atf`、`imx-mkimage`、`imx-oei`、`imx-optee-os`、`imx-sm`、`uboot-imx`、`real-time-edge-uboot`
- Linux BSP 链：
  `linux-imx`、`real-time-edge-linux`、`meta-real-time-edge`
- M 核代码参考链：
  `mcuxsdk-core`、`mcuxsdk-manifests`
- Android 资产：
  `android`

特别强调：

- `mcuxsdk-core` 只是代码参考基线，不是默认 release 编译来源
- `mcuxsdk-manifests` 是 manifest / workspace 初始化入口，不是默认 release 编译来源
- `M` 核 SDK 编译的首选 release 包入口在 `release_packages/m_freertos_sdk/`
- `SCFW` porting kit release 包入口在 `release_packages/scfw/`

### 4.2 `software_stacks/`

放跨项目的软件栈 / 软件线说明。

它的角色是：

- 说明 `RTE 3.3`、`RTE 3.4` 这类软件线对 LF 家族的影响
- 说明软件线对 `flash.bin` 输入组成、源码 ref 和 release 包需求的影响
- 在进入 `compile_targets/flashbin/` 前给出软件栈身份判断入口

### 4.3 `workspaces/`

放只有整体协同才有意义的集成工作区。

它的角色是：

- 保留多仓协同关系
- 说明某条对象线为什么不能只看单个 repo
- 为 `compile` 提供 workspace 级入口

当前保留两个：

- `hmc-workspace`
  `heterogeneous-multicore / zsdk / mcuxsdk / .west` 的集成工作区
- `zephyr-workspace`
  当前本地默认的 Zephyr 工作区入口

特别强调：

- 共享 workspace 是共享基线，不是 case 工作目录
- 即使 workspace 里带着 `zephyr/`、`mcuxsdk/`，也不能自动推出“从这里开始编”
- `hmc-workspace` 和 `zephyr-workspace` 各自承担不同的对象线入口

### 4.4 `compile_targets/`

放“我要编什么”的对象入口。

这层不是源码层，而是编译路由层。
它把“资源在哪里”与“真正从哪里开始编”分开。

当前对象包括：

- `flashbin`
- `linux`
- `m_freertos_sdk`
- `zephyr`
- `a55_rtos`

### 4.5 `release_packages/`

放不可通过 Git checkout 切版本的厂商 release 包。

它的角色是：

- 长期保存用户提供或官方下载的 release 包
- 明确缺目标版本时要让用户提供或下载官方对应包
- 防止把 SDK / SCFW 这类 release 包误当成可切 ref 的源码树

当前代表性内容：

- `m_freertos_sdk/`
- `scfw/`

---

## 5. case 与系统生长

### 5.1 `work/<case>/`

每个 case 一个目录。

它不是单纯的临时构建目录，而是后续可回放、可交接、可抽取知识的完整过程容器。

每个 case 推荐最小结构：

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

至少应包含：

- 目标与输入版本
- 关键执行步骤与结论
- 原始日志
- 生成的产物、补丁、脚本、配置
- 面向客户的交接材料或其来源

后续如果需要生成交接包，应该能主要依赖 `work/<case>/` 恢复上下文。

### 5.2 `to_absorb/`

执行过程中遇到新的、可复用、有长期价值的信息，不应直接塞回正式 skill 或 README。

先放进：

- `support_level/to_absorb/`

并保留：

- 来源 case
- 证据或原始线索
- 可复用结论
- 后续建议吸收到哪一层

这层的目的不是存档噪声，而是把“当前交付”和“系统演化”拆开。

---

## 6. 共享基线与 case 工作区边界

当前系统非常强调这个边界。

### 6.1 共享基线允许做什么

可以在共享基线里做：

- 浏览源码
- 对比内容
- 核对版本
- 做可逆的 checkout / tag / branch 切换

### 6.2 共享基线不该承担什么

不要在共享基线里直接做：

- case patch
- case 构建
- 生成输出
- 运行态污染
- 长期保留临时脚本和临时日志

只要进入：

- 修改
- 编译
- 生成输出
- 面向某个 case 的临时派生

就应该转到：

- `support_level/work/<case>/`

---

## 7. 板级执行架构

系统对板级问题的理解不是“工具调用”，而是“状态推进”。

### 7.1 强信号优先

板级任务优先依赖：

- 已验证的板控状态
- USB 枚举身份
- 串口输出
- 旧日志

不能把沉默串口当作唯一真相源。

### 7.2 命令不是计划

在板级动作前，必须先明确：

- 当前状态
- 目标状态
- 允许的下一步动作

不能先想到一条命令，再倒推这条命令是不是计划。

### 7.3 烧写成功不等于运行态成立

把产物送到板上，只说明 transport/deploy 成立。
它不自动证明：

- 已到 U-Boot
- 已起 Linux
- 已登录
- M 核 payload 已接管

后续必须继续做阶段验证。

---

## 8. Git 边界

这个仓库是轻量视图，不是本机重资产镜像。

Git 里应该保留的是：

- 入口规则
- 架构文档
- 本地 skill
- 资源入口 README
- 板级知识 README
- 项目 `USAGE.md`

Git 里默认不保留的是：

- 镜像包
- SDK 压缩包内容
- toolchain 实体
- 外部下载的源码树本体
- firmware blob
- case 原始产物

也就是说，这个仓库保存的是“系统如何工作”，而不是“本机所有东西的备份”。

---

## 9. 推荐阅读顺序

如果是第一次理解当前系统，建议按这个顺序读：

1. `README.md`
2. `workspace/AGENTS.md`
3. `workspace/docs/architecture-construction/v2/ARCHITECTURE.md`
4. `support_level/README.md`
5. 对应主 skill：
   `understanding` / `support` / `compile` / `board-exec`

如果已经在做具体任务：

1. 先看 `workspace/AGENTS.md`
2. 按 unresolved step 进入对应 skill
3. 再下沉到 `support_level` 里的 README / `USAGE.md`

---

## 10. 当前系统最需要被记住的点

- 这是一个按 unresolved step 推进的系统，不是固定流水线系统
- `workspace/` 是轻量控制面，`support_level/` 是重资源与知识面
- `support` 负责找资源和 owner，`compile` 负责编译对象路由，`board-exec` 负责板级动态事实、目标状态和允许动作
- `code_assets` 负责共享代码基线，`compile_targets` 负责真正的编译入口
- `work/<case>/` 保留完整过程，`to_absorb/` 保留待归纳的高价值信息
- Git 只跟踪我们的规则和知识入口，不跟踪下载来的重资产本体
