# imx95evk19

## 适用范围

- 板型：`i.MX95 19x19 LPDDR5 EVK`
- 当前主机：Ubuntu 本机
- 来源：旧 `imx95-generic-workflow` / `imx95-rte33-workflow` / `i.MX9` board-profile 已验证结论

## 当前 board-generic 默认认知

- 这块板先要明确区分：
  generic Linux
  还是 `RTE 3.3`
- 当 packaging target 会影响后续 owner 时，
  `flash_a55` 和 `flash_all` 必须保持显式
- 当前树里：
  `i.MX95` 还没有完全拆开的 validated deploy / boot / runtime leaves
  所以 board-level `uuu` / `bcu` / deploy / boot / verify 仍要先落在 board-generic router 语义上

## 已验证的 revision-sensitive 规则

- `i.MX95` 的 `flash.bin` 是 revision-sensitive
- `A0` / `B0` 不能猜
- 只要会影响：
  `OEI`
  firmware blob choice
  `mkimage REV=...`
  就把 silicon revision 当阻塞字段

## 已验证的 boot-firmware 形态

共享 board-level 打包形态仍是：

- `U-Boot`
- `ATF`
- `OEI`
- `SMFW`
- `imx-mkimage`
- firmware blobs

generic Linux 和 `RTE 3.3` 的真正差异，
主要在 secure-world delta 和 stack delta，
不是在“有没有这条板级打包链”。

## 已验证的 USB / transport 规则

- 在这块板上，不要先把 `uuu` 失败当成 artifact 证据
- 先确认板子 USB 数据线是直连主机
- hub 路径上的失败，不能直接当成镜像或打包问题

## 已验证的 `bcu -keep` / UART-mux 规则

- 在 `imx95evk19` 上，
  `bcu reset ... -keep` 可能把 `ft_fta_sel` 留在 `HIGH`
- 这会让第一路 FTDI runtime port 看起来像“假静音”
- 如果当前 workflow 需要第一路 runtime log，
  在 `-keep` 之后要优先恢复：
  `set_gpio ft_fta_sel 0 -board=imx95evk19`

这类现象不要误读成：

- `M` side 没起来
- Linux 没起来
- 镜像本身坏了

## 已验证的 generic Linux / `RTE 3.3` 分工

- board-level defaults 和 task routing：
  先看 `imx95` generic 语义
- `RTE 3.3` delta：
  留在 `imx95-rte33-*`
- 当前 validated `RTE 3.3` build-side `flash.bin` lane：
  `flash_all`
- 当前 validated generic Linux `flash.bin` lane：
  `flash_a55`

## 当前第一轮迁移后的 handoff 认知

- 如果任务是 board-level 入口、stack 还不清楚、或者还在判断 generic Linux vs `RTE 3.3`，
  先停留在 `i.MX95` board-generic routing
- 如果任务已经明确是 `RTE 3.3 flash.bin build`，
  再转到 build-side lane
- 如果任务是 `uuu` / `bcu` / deploy / boot / verify`，
  当前仍按 board-generic board-state-first 语义处理
