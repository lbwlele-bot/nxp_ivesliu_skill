---
name: support
description: 支撑层资源入口。用于回答当前 `support_level/` 里有什么、各目录分别负责什么、资源在什么位置，以及下一步应该进入哪个目录说明、README、USAGE 或下层 skill。当需要找镜像、资料、工具、源码、SDK、toolchain、firmware 或当前 case 目录时，先查这里。
---

# 支撑层

当前支撑层根目录：

`/home/ives/桌面/NXP_v2/support_level`

这层主要负责：

- 当前支撑层里都有什么
- 这些资源分别负责什么
- 它们放在什么位置

这层不负责直接展开：

- 编译步骤
- 板级操作手册
- 具体主机现状
- 某个源码项目的操作手册

## 使用方式

1. 先在这层判断当前问题落在哪类资源
2. 再进入对应目录的 README 或工具/项目 `USAGE.md`
3. 如果问题已经从“找资源”变成“做编译”或“做板级动作”，切到 `compile` 或 `board-exec`

## 当前目录

### `Image/`

放预下载镜像、发布包、可直接复用的烧写输入。
这里更像“现成镜像资产层”，适合先回答：

- 当前本地有没有某块板可直接用的镜像包
- 这次拿来烧写或对比的镜像基线在哪

当前能看到的内容已经包括 `i.MX93`、`i.MX943`、`i.MX95` 的镜像包目录。

### `SoC_material/`

放各 SoC 的资料，例如：

- 原理图
- 硬件设计资料
- RM

这一层按 SoC 分目录。
当前已经有 `i.MX91`、`i.MX93`、`i.MX943`、`i.MX95`，以及多颗 `i.MX8` 系列芯片的资料目录。
如果问题落在“查芯片资料、查 RM、查板级硬件资料”，先从这里找。

### `tools/`

放当前长期保留的主机侧工具。
目录层 `README.md` 负责说明这层里有什么、各工具放在哪。
具体工具目录里的 `USAGE.md` 负责操作手册。

当前已经落进来的工具至少包括：

- `uuu`
- `bcu`
- `imx-rm`

也就是说，如果任务是在找板控工具、烧写工具或本地辅助小工具，先看这里。

### `board_knowledge/`

放已经被实测证明、后续可复用的板级操作知识。
目录层 `README.md` 负责说明板级知识怎么分布；
具体板目录里的 `README.md` 负责该板的事实、基线和风险。

当前已经有的板型目录包括：

- `imx8dxlevk`
- `imx93evk14`
- `imx943evk19a0`
- `imx95evk19`

如果问题是在判断某块板的默认串口、默认下载态、已知风险、板 revision 差异，就进这里。

### `linux_document/`

放 Linux BSP 官方文档，如 release note、User's Guide、构建文档。
它更偏资料层，不是源码层，也不是板级操作层。

### `code_assets/`

放长期保留的代码资产。
这一层先分清两件事：

- 当前看的到底是单个源码项目
- 还是只有整体协同才有意义的工作区

#### `code_assets/projects/`

放标准源码资产。
这一层先回答：

- 有哪些源码项目
- 在什么位置
- 能不能把它当成标准源码基线来读

当前已收进来的源码项目，简要包括：

- `imx-atf`
- `imx-mkimage`
- `imx-oei`
- `imx-optee-os`
- `imx-sm`
- `linux-imx`
- `mcuxsdk-core`
- `imx-scfw-porting-kit`
- `meta-real-time-edge`
- `real-time-edge-linux`
- `real-time-edge-uboot`
- `uboot-imx`
- `android`

目录层 `README.md` 负责说明这一层有哪些项目、项目放在哪里。
每个项目旁边的 `USAGE.md` 或 `README.md` 负责该项目自己的操作手册或说明文档。

这里默认只读：

- 可以浏览
- 可以对比
- 可以切 ref
- 不在这里直接做 case 构建

#### `code_assets/workspaces/`

放整体协同才有意义的工作区输入。
这一层先回答：

- 本地有哪些工作区
- 它们各自承担什么角色
- 哪些只是联动输入，不能自动等于“从这里编”

当前已经保留的工作区包括：

- `zephyr-workspace`
- `hmc-workspace`

如果任务只是查代码资产，优先留在 `code_assets/`；
如果任务已经变成“我要编什么”，切到 `compile`。

### `compile_targets/`

放编译对象入口说明。
这层不负责记录源码资产事实，
而是由 `compile` owner，用来回答：

- 我现在到底要编什么
- 对应依赖哪些源码资产、SDK、toolchain、firmware、workspace
- 哪些目录只是输入来源，不能直接拿来编

当前已收编译对象包括：

- `flashbin`
- `linux`
- `m_freertos_sdk`
- `zephyr`
- `a55_rtos`

### `m_freertos_sdk/`

放 `MCUX SDK / FreeRTOS SDK` 发布压缩包资产。
这一层关心的是：

- 当前有哪些 SDK 包
- 各自对应哪些板型 / 版本
- 它们放在什么位置

目录层 `README.md` 负责说明包的组织方式和使用边界。
这里放的是发布压缩包资产，不当成普通 Git 源码项目。

### `toolchain/`

放交叉编译工具链、SDK、编译环境输入。
目录层 `README.md` 负责说明这里有哪些工具链、它们怎么分层。

当前已经能看到的长期工具链包括：

- `aarch64-none-linux-gnu`
- `arm-none-eabi`
- `zephyr-sdk`

如果问题是在找编译链对应的主机侧工具链，先看这里。

### `firmware/`

放固定二进制输入，不和 `code_assets/projects/` / `code_assets/workspaces/` 混。
目录层 `README.md` 负责说明这里有哪些固定输入、按什么维度组织。

当前按 SoC 分目录，已经有：

- `imx8dxl`
- `imx943`
- `imx95`

如果问题是在找 DDR firmware、ELE / AHAB 或其他固定 blob，先看这里。

### `work/`

放当前 case 的过程记录、日志、构建产物和临时修改。
这是 case 工作区，不是长期共享基线。
每个 case 一个目录，后续如果要生成交接包，应能从这里还原完整过程。

### `to_absorb/`

放待归纳的高价值信息。
这里保留新发现的可复用信息及其来源 case，后续再决定吸收到哪一层。

## 进入规则

- 找资源位置、已有资产、已有资料、已有工具 -> 留在 `support`
- 一旦已经明确要编某个对象 -> 进 `compile`
- 一旦已经要碰真实板子 -> 进 `board-exec`
