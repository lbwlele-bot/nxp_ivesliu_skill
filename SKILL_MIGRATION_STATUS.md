# Skill Migration Status

这个文件记录：

- 旧系统 skill 哪些已经吸收到 `NXP_v2`
- 第一轮已经吸收到什么程度
- 当前源码整理已经做到哪一步
- 后面该按什么顺序收敛细节

## 已完成的骨架

这些已经在 `workspace/` 里落成了新骨架：

- `workspace/AGENTS.md`
  现在是启动总手册
- `understanding`
  作为理解层保留
- `support`
  作为资源/资料/源码/板级支撑层入口
- `compile`
  作为编译阶段框架
- `board-exec`
  作为板级执行阶段框架
- `support_level/board_knowledge/`
  作为板级操作支撑层

## 本轮源码整理已完成

当前源码与编译层已经先收成三类：

- `support_level/code_assets/projects/`
  标准源码资产
- `support_level/code_assets/workspaces/`
  工作区输入资产
- `support_level/compile_targets/`
  编译对象入口

当前已经落到 `code_assets/projects/` 的源码项目：

- `imx-atf`
- `imx-mkimage`
- `imx-oei`
- `imx-optee-os`
- `imx-sm`
- `linux-imx`
- `mcuxsdk-core`
- `meta-real-time-edge`
- `real-time-edge-linux`
- `real-time-edge-uboot`
- `uboot-imx`
- `android`

当前保留的工作区资产：

- `code_assets/workspaces/hmc-workspace`
- `code_assets/workspaces/zephyr-workspace`

当前已收编译对象：

- `flashbin`
- `linux`
- `m_freertos_sdk`
- `zephyr`
- `a55_rtos`

原则：

- 以后不再保留“统一源码总壳”这一层
- 长期方式是：
  `一个源码项目一个目录`
- 多模块集成源码保留在 `code_assets/workspaces/`
- 编译入口单独保留在 `compile_targets/`
- 目录形态是：
  `code_assets/projects/<project>/USAGE.md`
  `code_assets/projects/<project>/<real-source-tree>/`

## 本轮迁移主线

这次第一轮不是零散收 skill，
而是先收一条跨板的 `flash.bin` 家族主线。

第一轮覆盖范围：

- `i.MX93`
- `i.MX943`
- `i.MX95`
- `i.MX8DXL`

第一轮完成的事：

- 先把这几条旧 skill 里关于 `flash.bin`、`uuu`、`Fastboot relay`、`M` 核启动 owner 的共同抽象收出来
- 并把每块板、每个版本后续要收敛的 recipe 入口回填到源码项目 `USAGE.md`

## 旧 Skill 台账

到这里，旧系统里列出来的这些 skill，
都已经完成第一轮吸收。

下面保留台账，主要是为了后续逐条收敛细节时知道它们分别落到了哪里。

### 已处理到新骨架

- `workflow`
  已拆到 `workspace/AGENTS.md` + `understanding`

### i.MX8 本地 skill

- `imx8-family-intake`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 family-local intake、`i.MX8` 局部化、非 `flash` linker 默认和 DXL lane 的入口边界拆进本地骨架
- `imx8dxl-board-control`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：先把 `SDPS -> FB -> second-stage relay`、`flash_m4` 不是 first-stage image、以及串口/USB 观测强弱关系拆进 `support_level`
  当前已落点：`board_knowledge/imx8dxlevk/`
  当前已补强：`bcu` 禁用、`lsusb -> uuu -lsusb -> UART` 强信号顺序、fresh `SDPS` reset discipline、second-stage 后的 manual `SD boot` handoff

### i.MX9 家族/通用支撑

- `imx9-board-workflow`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 family intake / evidence priority / board-state-first / asset-work root / router 边界拆进 `AGENTS.md`、`support`、`compile`、`board-exec`
- `imx9-network-share`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 Linux-up 之后的 shared networking 分层顺序和边界拆进 `support`
- `imx9-rm-evidence`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 `RM` 作为 bounded secondary-evidence lane 的入口边界拆进 `support`
- `imx9-zephyr-host-bootstrap`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 Zephyr host bootstrap 的 owner 边界拆进 `compile` / `support`
- `self-improving-agent`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 failure notebook first 的规则拆进 `support` 和总手册

### i.MX93

- `imx93-generic-workflow`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 `i.MX93` board-generic router 的 task-lane / hardware-layer / handoff 边界拆进 `board_knowledge`
- `imx93-generic-host-check`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 host-only readiness 的 owner 边界拆进 `board_knowledge`
- `imx93-generic-deploy-cycle`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：先把 full image restore / FAT artifact replace / trusted 14x14 boot blob / runtime filename 边界拆进 `support_level`
  当前已落点：`board_knowledge/imx93evk14/`
- `imx93-generic-boot-verify`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：先把 `serial download` / `U-Boot` / Linux-up 的 proof owner 边界和 fallback / handoff 规则拆进 `support_level`
  当前已落点：`board_knowledge/imx93evk14/`
- `imx93-generic-login-verify`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：先把 Linux shell proof 的 owner 边界和最小 runtime proof 集合拆进 `support_level`
  当前已落点：`board_knowledge/imx93evk14/`
- `imx93-openclaw-install`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 OpenClaw 作为 Linux-up + SSH-up 之后的 app-layer lane 边界拆进 `board_knowledge`

### i.MX943

- `imx943-workflow`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 unified fast path router 边界拆进 `board_knowledge` 和 `board-exec`
- `imx943-host-check`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 host readiness 只负责 host、不负责 live truth 的边界拆进 `board_knowledge` 和 `board-exec`
- `imx943-bcu-ops`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：先把 board truth / mode-transition legality / reset baseline 拆进 `support_level`
  当前已落点：`board_knowledge/imx943evk19a0/`
- `imx943-uuu-ops`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：先把 `uuu` 只拥有 transport、不拥有 runtime proof，以及 `-b sd` / `-b fat_write` 的边界拆进 `support_level`
- `imx943-deploy`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：先把 `raw_boot_image` / `fat_runtime_file` 的 artifact class 边界拆进 `support_level`
- `imx943-boot-verify`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：先把 `serial download` / `U-Boot` / `Linux-ready` 的 proof owner 边界、以及 deploy 后何时才能交给 login 层拆进 `support_level`
  当前已落点：`board_knowledge/imx943evk19a0/` + `workspace/.agents/skills/board-exec/`
- `imx943-login-verify`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：先把 Linux shell proof 的 owner 边界、默认 console / 默认凭据 / 最小验证集拆进 `support_level`
  当前已落点：`board_knowledge/imx943evk19a0/` + `workspace/.agents/skills/board-exec/`
- `imx943-flashbin`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：先把旧 skill 的 `flashbin` 依赖、命令形态、产物边界和版本缺口写进相关源码项目 `USAGE.md`
- `imx943-linux`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 kernel-side artifact owner 边界拆进 `compile` / `linux-imx` / `real-time-edge-linux`
- `imx943-mcore-rtos`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 per-core payload contract 和 validated-version 边界拆进 `compile` / `mcuxsdk-core`
- `imx943-a55-rtos`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 `Zephyr on A55` vs released-core `RTE` 的 branch boundary 拆进 `compile`

### i.MX95

- `imx95-generic-workflow`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 board-generic router、generic Linux vs `RTE 3.3` split、direct-host USB、`ft_fta_sel` 风险拆进 `board_knowledge/imx95evk19/`
- `imx95-rte33-workflow`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 case-router 只增加 `RTE 3.3` delta、不占有 board-touching lane 的边界拆进 `board_knowledge/imx95evk19/` + `compile`
- `imx95-rte33-build-flashbin`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 `RTE secure-world delta`、`toolchain owner split`、`OEI revision identity`、`flash_all` 明确 owner 这些关键卡点写进相关模块 `USAGE.md` 和支撑层边界
  当前已落点：`code_assets/projects/imx-mkimage/`、`code_assets/projects/real-time-edge-uboot/`、`code_assets/projects/imx-atf/`、`code_assets/projects/imx-optee-os/`、`code_assets/projects/imx-oei/`、`code_assets/projects/imx-sm/`、`compile_targets/flashbin/`、`workspace/.agents/skills/compile/`、`support_level/toolchain/README.md`、`support_level/firmware/README.md`

### 窄辅助 build skill

- `real-time-edge-linux-build`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 reusable source baseline / tag mapping / toolchain mapping 的 helper 边界拆进 `real-time-edge-linux/USAGE.md`
- `real-time-edge-hmc-freertos-build`
  当前状态：已完成第一轮吸收
  第一轮吸收目标：把 heterogeneous-multicore / west workspace bootstrap 的 helper 边界拆进 `compile`

## 后续收敛方法

从现在开始，不再先按“skill 名字”直接塞到新系统里。
而是按下面这个顺序拆：

1. 先看旧 skill 真正依赖哪些源码项目
2. 把源码项目落到 `code_assets/projects/<project>/`
3. 在该项目旁边补 `USAGE.md`
4. 把“我要编什么”的入口拆到 `compile_targets/<target>/`
5. 再把旧 skill 里的可复用部分吸收到：
   `compile`
   `board-exec`
   `support`
   `understanding`
   或新的更窄 skill

## 当前结论

到这里，旧系统里列出来的这些 skill，
都已经完成了第一轮吸收。

这一轮的目标不是把每条旧 skill 都原样复制成新 skill，
而是先把它们的：

- owner 边界
- 入口条件
- 高风险字段
- handoff 关系
- stable source / tool / board facts

拆进当前 `NXP_v2` 骨架。

当前这一轮之后，`i.MX95 RTE 3.3 flash.bin` 已经先把：

- source owner
- toolchain split
- firmware root
- final package target
- secure-world acceptance

这些 build-side 边界落到 v2 骨架了。

同时，`i.MX93` 也已经先把：

- deploy owner
- boot-stage proof owner
- Linux shell proof owner

这三段的基础 handoff 边界接起来了。

另外，剩余这些旧 skill 的第一轮吸收也已完成：

- `i.MX95` board router / case router
- `i.MX943` host / Linux / `M-core RTOS` / `A55 RTOS`
- `i.MX93` board router / host check / OpenClaw app-layer
- `i.MX9` family router / network share / `RM` evidence / Zephyr bootstrap / failure reuse
- `Real-Time Edge Linux` / heterogeneous-multicore 窄 build helper

这条主线最容易先把下面这些源码项目写实：

- `imx-atf`
- `imx-mkimage`
- `uboot-imx`
- `real-time-edge-uboot`
- `imx-oei`
- `imx-sm`
- `imx-optee-os`

下一阶段就不再叫“迁移”了，
而是进入逐条细节收敛：

- 哪些 owner 还过宽
- 哪些 recipe 还只是边界说明、还没沉成可运行手册
- 哪些版本差异还需要按源码 ref / tag / branch 落实
- 哪些板级事实已经够稳定，可以继续下沉到更窄的模块 `USAGE.md`
