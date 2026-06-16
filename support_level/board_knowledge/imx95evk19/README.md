# imx95evk19

## 适用范围

- 板型：`i.MX95 19x19 LPDDR5 EVK`
- 当前主机：Ubuntu 本机
- 来源：旧 `i.MX95` 通用工作流、`rte33` 工作流和 `i.MX9` 板型资料中的已验证结论

## 当前板级默认认知

- 这块板先要明确区分：
  通用 Linux
  还是 `RTE 3.3`
- 当打包目标会影响后续判断时，
  `flash_a55` 和 `flash_all` 必须保持显式
- 当前树里：
  `i.MX95` 还没有完全拆开的已验证上板写入 / 启动 / 运行态细分文档
  所以 `uuu`、`bcu`、上板写入、启动、验证这些动作，当前仍先按板级总入口理解

## 已验证的 revision-sensitive 规则

- `i.MX95` 的 `flash.bin` 会受 revision 影响
- `A0` / `B0` 不能猜
- 只要会影响：
  `OEI`
  firmware blob 选择
  `mkimage REV=...`
  就把 silicon revision 当阻塞字段

## 已验证的启动固件形态

共享板级打包形态仍是：

- `U-Boot`
- `ATF`
- `OEI`
- `SMFW`
- `imx-mkimage`
- firmware blobs

通用 Linux 和 `RTE 3.3` 的真正差异，
主要在 安全世界 差异和软件栈差异，
不是在“有没有这条板级打包链”。

## 已验证的 USB / 传输规则

- 在这块板上，不要先把 `uuu` 失败当成 镜像证据
- 先确认板子 USB 数据线是直连主机
- hub 路径上的失败，不能直接当成镜像或打包问题

## 已验证的 `bcu -keep` / UART-mux 规则

- 在 `imx95evk19` 上，
  `bcu reset ... -keep` 可能把 `ft_fta_sel` 留在 `HIGH`
- 这会让第一路 FTDI 运行态串口看起来像“假静音”
- 如果当前工作流需要第一路运行态日志，
  在 `-keep` 之后要优先恢复：
  `set_gpio ft_fta_sel 0 -board=imx95evk19`

这类现象不要误读成：

- `M` side 没起来
- Linux 没起来
- 镜像本身坏了

## 已验证的通用 Linux / `RTE 3.3` 分工

- 板级默认动作和任务分流：
  先看 `imx95` 的通用语义
- `RTE 3.3` 差异项：
  留在 `imx95-rte33-*`
- 当前已验证 `RTE 3.3` 构建侧 `flash.bin` 路线：
  `flash_all`
- 当前已验证通用 Linux `flash.bin` 路线：
  `flash_a55`

## 当前第一轮迁移后的交接认知

- 如果任务是板级入口、软件栈还不清楚、或者还在判断通用 Linux vs `RTE 3.3`，
  先停留在 `i.MX95` 的板级总入口
- 如果任务已经明确是 `RTE 3.3 flash.bin build`，
  再转到构建侧
- 如果任务是 `uuu` / `bcu` / 上板写入 / 启动 / 验证`，
  当前仍按“先看板状态”的方式处理
