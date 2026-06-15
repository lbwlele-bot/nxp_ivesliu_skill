# AGENTS.md — 本工作区常驻说明

这是用户**唯一固定使用**的工作区。每次新对话开场先读本文件，了解"这里是干什么的、
规矩是什么、该走哪个 skill"，再开始干活。具体怎么做的细节在各 skill 里（按需加载）。

## 当前迁移任务

这部分是临时迁移说明。
等整个 v2 架构彻底稳定后，这一节应从 `AGENTS.md` 删除。

当前状态：

- 旧系统 skill 资产的第一轮吸收已经完成
- 这里保留这段，不是因为第一轮还没做完，而是为了提醒后续 agent：
  v2 的长期结构已经定了
  后面做的是架构细化，不是再回到旧 skill 平移
- 仍然坚持：
  不把旧 skill 当成最终形态直接平移
  先按源码模块拆，再把可复用操作说明沉淀到模块旁边的 `USAGE.md`
- 当前源码长期形态是：
  `../support_level/source_code/modules/<module>/USAGE.md`
  `../support_level/source_code/modules/<module>/<real-source-tree>/`
- 从旧系统复制过来但还没拆清的源码资产，先放：
  `../support_level/source_code/_to_absorb/`
- 对 toolchain / firmware 这类非源码支撑资产，优先读：
  `../support_level/toolchain/README.md`
  `../support_level/firmware/README.md`
- 对 `m_freertos_sdk/`：
  它是 NXP SDK 发布压缩包资产，不是普通 clone 下来的源码基线
  先看本地已有版本
  没有目标版本时，不要自己上网下载，先找用户要

第一轮吸收已确定的长期主线：

1. 先从 `boot-firmware` / `flash.bin` 家族开始
2. 第一轮已覆盖范围：
   `imx93`
   `imx943`
   `imx95`
   `imx8dxl`
3. 这条链优先继续写实这些模块：
   `imx-mkimage`
   `imx-atf`
   `uboot-imx`
   `real-time-edge-uboot`
   `imx-oei`
   `imx-sm`
   `imx-optee-os`

迁移阶段额外规则：

- 遇到旧 skill，先判断它依赖哪些源码模块
- 先读模块 `USAGE.md`，再读真实源码
- 如果某资料还在 `_to_absorb/`，要明确说它仍在待拆，不当成稳定长期入口
- 在 v2 架构还没彻底细化稳定前，不要把旧系统的大而混的源码组织方式继续固化到新系统

## 这个工作区是干什么的

支撑 **NXP i.MX 系列嵌入式板级开发**的日常工作：承接客户需求 / bug，按
"需求确认 → 理解 → 编译出产物 → 上板烧写验证 → 看日志迭代"的主线把问题一步步做完。
目标有两层：完成客户需求；同时让这套 skill 体系能长期维护、生长。

本工作区（Codex，VS Code workspace）只放 skill 等轻量内容。任务的日志、产物、过程记录
放在同级 `../support_level/` 下的对应目录。

## 有哪些 skill，何时用

| skill | 何时用 |
|-------|--------|
| `understanding` | 理解层。用于沉淀会改变判断方式的高阶抽象，例如 `flash.bin` 的阶段角色、`uuu` 的状态迁移本质、`M` 核启动 owner 分层等。 |
| `support-level` | 找镜像/固件/手册/原理图/工具/源码——查它们各在哪、怎么用。 |
| `compile` | 编译阶段：理运行链路、定最小模块集合、在本机出产物/镜像。 |
| `board-exec` | 板级执行阶段：在本机烧写、抓串口、看板子运行，并维护板级状态机。 |

`compile` 与 `board-exec` 是主阶段分工，不是硬互斥。
默认按需读取，当前 unresolved step 落在哪一层，就以哪层为主。

## 开工方式

拿到一个客户需求，不要急着动手，也不要一口气闷头做完。
先按这个总手册推进，再按阶段进入下层 skill。

### 本地有哪些资源能用

先去 `support-level` 看本地共享资源：

- `../support_level/Image/`
- `../support_level/SoC_material/`
- `../support_level/board_knowledge/`
- `../support_level/tools/`
- `../support_level/linux_document/`
- `../support_level/source_code/`
- `../support_level/m_freertos_sdk/`
- `../support_level/toolchain/`
- `../support_level/firmware/`
- `../support_level/work/`

当前 v2 已完成第一批长期资产复制：

- `tools`
- `source_code`
- `m_freertos_sdk`
- `toolchain`
- `Image`
- `firmware`
- `SoC_material` 下现有 RM
- `board_knowledge` 下逐板沉淀的板级操作支撑知识

其中要特别区分：

- `source_code/`
  放按模块组织的共享源码基线
- `m_freertos_sdk/`
  放 NXP 发布的 SDK 压缩包资产
  不是普通 Git 源码树
  没有目标版本时先找用户要，不要自己上网下载

所以默认先查新的 `support_level/`。
旧根只在缺项追溯或核对来源时再回看。

### 办事步骤

#### 第 1 步：确认信息

接到需求先把下面信息核对清楚，缺哪条就直接问用户。

**A. 需求与资源**

- 目标结果，怎样算成功
- 软件栈和目标版本，要问到具体版本号
- 当前已有资源在哪：
  镜像、已有产物、源码、文档、工具、日志

**B. 板子物理状态**

- 具体是哪块板：
  芯片型号、流片版本、封装、DDR 类型
- 当前 boot mode
- 目标存储
- USB 下载口是否连到本机
- UART 串口线是否接好
- 是否需要网络
- 当前上电状态

信息不齐就停在这一步补齐，不往下走。

#### 第 2 步：建立或复用当前 case

当前任务的日志、产物、过程记录，默认放：

`../support_level/work/<日期-芯片-问题>/`

#### 第 3 步：理解需求

把大需求拆成可执行的小问题，先判断当前缺的是哪类：

- 缺资料 -> 先去 `support-level`
- 缺产物/镜像 -> 进 `compile`
- 缺板子状态或上板验证 -> 进 `board-exec`
- 缺抽象理解、问题定义、经验判断 -> 看 `understanding`

#### 第 4 步：编译

需要准备产物时，进入 `compile`。

#### 第 5 步：板级执行

产物就绪、要上板验证时，进入 `board-exec`。
这一步不是直接“动板子”，而是先进入板级状态机：

- 记录当前板状态
- 记录各核当前状态
- 明确目标状态
- 每次板级动作后动态更新状态

#### 第 6 步：用日志反馈，继续迭代

拿串口/运行日志当反馈定位问题。
需要改代码就回到第 3/4 步，形成闭环。

## 核心规矩

- 任何任务先按本文件推进，不要一上来就闷头做完——带着用户一步步推进，每步先对齐。
- 信息不全先问，不替用户猜芯片 / 版本 / 板卡状态 / 路径。
- 找镜像 / 资料 / 工具 / 源码先查 `support-level`，找不到再问用户，不编路径。
- `support_level/board_knowledge/` 不是泛知识库，而是板级操作支撑层。
- `board-exec` 里应维护板级状态机，不允许把“上一次看见什么”直接当成当前状态。
- 这里只有两类东西值得长期沉淀：静态资料索引入口；以及已经实测证明可复用的板级操作结论。
- 板级操作里那些“已经实测证明可复用”的知识，优先沉淀到 `support_level/board_knowledge/`，不要散落在 case 记录里。
- 破坏性操作（烧写、覆盖、改配置、装卸软件）动手前先确认；只读 / 查询类（看串口、读日志、grep 代码）可直接做。
- 共享源码基线默认只读；需要修改、构建、生成输出时，复制到当前 `work/<case>` 再动。
- 远端模型相关内容现在只作为旧经验参考，不再默认当成当前 v2 的执行前提。
- 默认用中文交流。

## 本机操作说明

当前没有单独的“主机操作 skill”。
本机 shell、路径核对、文件查看、`rg`/`find`/`ls` 这类普通操作，直接作为默认能力使用即可。
