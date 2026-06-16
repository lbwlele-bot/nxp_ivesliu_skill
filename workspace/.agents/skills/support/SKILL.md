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
- 某个源码模块的操作手册

## 使用方式

1. 先在这层判断当前问题落在哪类资源
2. 再进入对应目录的 README 或工具/模块 `USAGE.md`
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

### `source_code/`

放共享源码基线。
这一层先回答：

- 有哪些模块
- 在什么位置
- 哪些已经收成长期模块入口
- 哪些还只是待继续拆分的旧资产

当前已收成长期模块入口的源码，简要包括：

- `imx-atf`
- `imx-mkimage`
- `imx-oei`
- `imx-optee-os`
- `imx-sm`
- `linux-imx`
- `mcuxsdk-core`
- `mcuxsdk-manifests`
- `meta-real-time-edge`
- `real-time-edge-linux`
- `real-time-edge-uboot`
- `uboot-imx`

目录层 `README.md` 负责说明这一层有哪些模块、模块放在哪里。
每个模块旁边的 `USAGE.md` 负责该模块自己的操作手册。

这一层当前还保留了：

- `modules/`
- `_to_absorb/`

其中 `modules/` 是现在的长期结构；
`_to_absorb/` 是从旧系统复制过来、还没完全拆进长期结构的资产。

只有当上层已经决定“这次要编译/复用哪个模块”时，
才进入对应模块目录并读取模块旁边的 `USAGE.md`。

### `m_freertos_sdk/`

放 `MCUX SDK / FreeRTOS SDK` 发布压缩包资产。
这一层关心的是：

- 当前有哪些 SDK 包
- 各自对应哪些板型 / 版本
- 它们放在什么位置

目录层 `README.md` 负责说明包的组织方式和使用边界。
这里放的是发布压缩包资产，不当成普通 Git 源码模块。

### `toolchain/`

放交叉编译工具链、SDK、编译环境输入。
目录层 `README.md` 负责说明这里有哪些工具链、它们怎么分层。

当前已经能看到的长期工具链包括：

- `aarch64-none-linux-gnu`
- `arm-none-eabi`
- `zephyr-sdk`

如果问题是在找编译链对应的主机侧工具链，先看这里。

### `firmware/`

放固定二进制输入，不和 `source_code/` 混。
目录层 `README.md` 负责说明这里有哪些固定输入、按什么维度组织。

当前按 SoC 分目录，已经有：

- `imx8dxl`
- `imx943`
- `imx95`

如果问题是在找 DDR firmware、ELE / AHAB 或其他固定 blob，先看这里。

### `work/`

放当前 case 的过程记录、日志、构建产物和临时修改。
这是 case 工作区，不是长期共享基线。

## 进入规则

- 找资源位置、已有资产、已有资料、已有工具 -> 留在 `support`
- 一旦已经明确要动某个源码模块 -> 进 `compile`
- 一旦已经要碰真实板子 -> 进 `board-exec`
