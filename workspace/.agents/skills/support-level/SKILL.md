---
name: support-level
description: 支撑层资源索引。告诉 AI 当前 Ubuntu 本地都有哪些可复用的共享资源、各放在哪、怎么用。当需要找镜像/固件、找手册(RM)/原理图(SCH)、找板级操作时已经实测过的可复用知识、找 uuu/bcu/picocom 等工具、找源码/SDK/工具链、找 DDR firmware 或 AHAB 等固定二进制输入、或要定位当前 case 工作目录时，先查本技能定位资源，再动手。典型触发：“镜像在哪”“有没有现成固件”“手册/原理图在哪”“工具在哪”“源码/SDK 放哪了”“DDR firmware 在哪”“AHAB container 在哪”“这块板默认串口是哪一个”“这块板下载态一般长什么样”。
---

# 支撑层资源索引

支撑层是当前 `NXP_v2` 工作区共用的资源底座。
本机只保留一套主模型：

- 轻量内容在 `workspace/`
- 重资源在同级 `../support_level/`

当前支撑层根目录：

`/home/ives/桌面/NXP_v2/support_level`

当前已完成第一批长期资产复制：

- `tools/`
- `source_code/`
- `m_freertos_sdk/`
- `toolchain/`
- `Image/`
- `firmware/`
- `board_knowledge/`
- `SoC_material/i.MX93/RM/`
- `SoC_material/i.MX943/RM/`
- `SoC_material/i.MX95/RM/`

当前又补进了公开可下载的 RM：

- `SoC_material/i.MX91/RM/IMX91RM.pdf`
- `SoC_material/i.MX8M/RM/IMX8MDQLQRM.pdf`
- `SoC_material/i.MX8MM/RM/PREVIEW_IMX8MMRM.pdf`
- `SoC_material/i.MX8MN/RM/IMX8MNRM.pdf`
- `SoC_material/i.MX8MP/RM/PREVIEW_IMX8MPRM.pdf`
- `SoC_material/i.MX8ULP/RM/IMX8ULPRM.pdf`

---

## 当前目录模型

### 1. `Image/`

放预下载镜像、发布包、可直接复用的烧写输入。

用法：

- 用前先实地列目录，看当下到底有哪些版本
- 解压后如果只是只读复用，可以继续留在这里
- 如果要修改、裁剪、重打包或生成新输出，复制到 `work/<case>/` 再动

### 2. `SoC_material/`

放各 SoC 的资料：

- 原理图
- 硬件设计资料
- RM

查芯片信息时的优先级仍然是：

1. 先看代码
2. 再查 RM/原理图

### 3. `tools/`

放当前 v2 专用或本地化后的工具。

当前结构开始采用：

```text
tools/
  <tool>/
    USAGE.md
    <program-or-version-dir>
```

查找顺序：

1. 先看 `../support_level/tools/`
2. 如果这里还没补齐，再看共享工具根 `/home/ives/桌面/NXP/tools`
3. 再看 `PATH`

当前主机已确认：

- `uuu` 在 `PATH` 可直接用
- `picocom` 在 `PATH` 可直接用
- `bcu` 当前长期入口是 `../support_level/tools/bcu/bcu`

同时，`support_level/tools/` 已经复制了一份长期资产，可优先从这里使用。

当前已经收成工具目录的：

- `../support_level/tools/bcu/`
- `../support_level/tools/uuu/`

规则：

- 先读工具目录里的 `USAGE.md`
- 再执行对应程序
- 工具层只写稳定工具边界，不在工具 `USAGE.md` 里堆具体板型 recipe

### 4. `board_knowledge/`

放板级操作支撑层知识。
它不负责保存抽象理解，也不负责保存 RM 这类静态资料本体；
它负责保存那些会直接影响板子操作、并且已经被证明可复用的确定性知识。

这里适合放：

- 默认主 console 串口
- 默认 USB 下载态识别方式
- 已验证的基础进入方式
- 已验证的操作前提
- 已验证的高频注意事项

规则：

- 先测，再写
- 没有现场证据，不要放进来
- 资料可以提供线索，但只有实测定下来的结论才能放进来
- 一块板一个目录，逐步补齐

### 5. `linux_document/`

放 Linux BSP 官方文档，如：

- release note
- User's Guide
- 构建文档

要定某个 BSP 版本配套的固件、组件、偏移时，先看对应版本的 release note。

当前状态：

- 目录已预留
- 但旧长期资产根里还没有发现整理好的 Linux docs 包
- 暂时不要把 case 目录里零散文档直接当成长期 `linux_document` 资产

### 6. `source_code/`

放共享源码基线。

当前结构不是“顶层平铺一堆 repo”，而是：

```text
source_code/
  modules/
    <module>/
      USAGE.md
      <real-source-tree>/
  _to_absorb/
```

适合放：

- 内核/BSP 源码
- bootloader 相关源码
- 共享只读 repo

规则：

- 长期形态是“一个模块一个目录”
- 先读模块旁边的 `USAGE.md`，再进真实源码目录
- 只读查看、确认版本、grep，可以直接在这里做
- 要修改、构建、生成输出，复制到 `work/<case>/` 再动
- `_to_absorb/` 只表示旧资产待拆，不表示已经是合理长期结构

### 7. `m_freertos_sdk/`

放 M 核 FreeRTOS / MCUX SDK 相关源码与基线。

### 8. `toolchain/`

放交叉编译工具链、SDK、编译环境输入。

当前优先入口：

- `../support_level/toolchain/README.md`

### 9. `firmware/`

放固定二进制输入，不和 `source_code/` 混。

包括但不限于：

- DDR firmware
- ELE/AHAB container
- 其它带 EULA 或发布包形式提供的固定二进制

当前优先入口：

- `../support_level/firmware/README.md`

### 10. `work/`

放当前 case 的过程记录、日志、构建产物和临时修改。

命名建议：

`work/<日期-芯片-问题>/`

### 11. `RM` / bounded manual evidence

当代码、日志、当前资产都不足以回答 SoC 级问题时，
`RM` 是 support lane，不是 first truth source。

当前第一轮已吸收的边界是：

- 先 code / artifact / runtime
- 再 `RM`
- `RM` 进入后也应尽量 bounded retrieval
  而不是重新整本手翻

### 12. shared networking lane

对板子网络问题，
第一轮已吸收的默认顺序是：

- 先确认板子已进入 Linux
- 再看物理链路
- 再看 host shared Ethernet / uplink
- 再看 board IP / route
- 再看 public IP
- 最后才看 DNS 或 blocked-site access

如果板子还没 Linux-up，不要把网络问题和 boot 问题混成一个 lane。

### 13. failure reuse lane

对非显然、容易复现的失败，
当前第一轮已吸收的规则是：

- 先查 failure notebook
- 再看当前 owner skill / 本地支撑层
- 再做新一轮探索

failure notebook 适合放：

- symptom
- 容易误读的点
- 正确恢复顺序
- 下次 first check

### 14. host bootstrap / workspace bootstrap lane

像这些从 blank host 开始的事情，
第一轮已经吸收到 support-level 入口认知里：

- Zephyr host bootstrap
- `Real-Time Edge Linux` source bootstrap
- heterogeneous-multicore / west workspace bootstrap

它们的共同边界是：

- 先确认 reusable root
- 不在共享只读根里直接 build
- latest workspace 和 historical baseline 分开

---

## 现阶段补充规则

- 当前 `support_level/` 已有第一批长期资产，但用前仍然要实地看目录
- 如果当前资源还在旧共享根，可以临时复用，但要明确说明它来自旧根
- 当前最主要还没补齐的是 `linux_document/` 和 RM 之外的板资料
- `board_knowledge/` 里的结论必须来自实测，不接受纯猜测或只读文档得来的推断
- 对 `i.MX8DXL`、`i.MX8QXP`、`i.MX8QM`，当前官方公开直链还没补进本地
- 不要把 `firmware/` 和 `source_code/` 混在一起
- 不要把 vendor package 目录名直接当成唯一 SoC provenance
- 不要把 network / RM / app-layer 需求过早混进 boot-firmware 或 deploy lane
- 不确定某资源在不在、在哪，先查本索引，再实地找，找不到就问用户，不编路径
