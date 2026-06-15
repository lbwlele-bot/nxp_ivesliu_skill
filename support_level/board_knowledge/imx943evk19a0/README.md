# imx943evk19a0

## 适用范围

- 板型：`i.MX943 EVK 19x19 A0`
- 当前主机：Ubuntu 本机
- 来源：旧 `imx943-bcu-ops` / `imx943-workflow` 已验证板级结论

## 默认识别

- 默认 Linux / `U-Boot` console：
  `/dev/ttyUSB2`
- `/dev/ttyUSB3` 更偏向 `SM` / monitor console，不默认当 Linux shell
- 默认 `bcu` board token：
  `imx943evk19a0`

## 当前板控认知

- 当前 Ubuntu 路径里，`bcu` 是 `i.MX943` 板状态最强信号之一
- 板级 connected-board fast path 的 strongest-signal 优先级是：
  1. `bcu`
  2. `uuu`
  3. validated serial evidence
- 不要因为串口暂时安静，就覆盖掉更强的 `bcu` / `uuu` 结论

## 已验证的基础进入方式

- 默认 live start 可以先假设：
  - `BOOT SWITCH`
  - 没有 active USB download device
  - serial candidates 可见
- 查询 boot mode / reset 时，优先显式带：
  `-board=imx943evk19a0`

## 已验证的高频操作前提

- 当前主机 `sudo` 的 `PATH` 不包含共享工具根
- 所以不要假设：
  `sudo -n bcu ...`
  一定能工作
- 更稳定的入口应是显式路径，例如：
  `../../tools/bcu/bcu`

## 已验证的恢复动作

- 已验证可把板子拉回正常 boot 路径的 reset 形态：
  `reset sd -board=imx943evk19a0`
- 这条路径可作为从任意混乱状态回到可控 reset baseline 的默认恢复动作
  但仍要以当前 live evidence 为准

## 已验证的 connected-board fast path

- 当前 `i.MX943` 已验证的板级默认链路是：
  `host-check -> bcu truth -> uuu transport -> boot-stage proof -> login proof`
- 其中：
  - `bcu`
    负责 board truth 和 mode-transition legality
  - `uuu`
    负责 USB transport
  - runtime proof
    负责判断到底停在 `serial download`、`U-Boot` 还是 Linux
- 不要把 deploy 成功、`uuu` 成功或 reset 成功，直接当成 Linux 已经起来

## 已吸收：host-check owner 边界

- `host-check` 只负责：
  host OS path
  tool readiness
  `sudo` / permissions
  serial candidates
  是否已经具备 live probe 前提
- `host-check` 不负责：
  当前 boot mode truth
  reset truth
  最终 live board truth

## 已吸收：compile-side lane 认知

当前 `i.MX943` 已经在新骨架里分清：

- Linux kernel-side build
- `M-core RTOS`
- `A55 RTOS`

但这些 lane 负责的是 build / package / payload contract，
不是 board-side truth。

也就是说：

- compile owner 出产物
- board-side owner 证明板子现在到底到了哪一步

## 已验证的 boot-stage proof 边界

- `serial download`
  优先看 active USB download evidence，例如 `SDPS` / `SDPV`
  不要等串口先说话才承认板子还在下载态
- `U-Boot`
  默认先在 `/dev/ttyUSB2` 抓 proof
  看到 `Hit any key to stop autoboot`、`u-boot=>` 或等价 prompt，才算 runtime owner 已进入 `U-Boot`
- `Linux-ready`
  必须先看到明确的 Linux boot evidence，再把问题交给 login proof
  不要让 login owner 反过来替 boot owner 判断“其实板子还停在 `U-Boot`”
- 如果 `U-Boot` 环境明显健康，优先走环境驱动的高层 boot path
  例如：
  `boot`
  或板上已验证的正常 boot 命令
- 只有环境坏了、目标就是手动控制、或高层 boot path 明显不成立时，才降到 `booti` 一类低层 direct boot

## 高频 fallback / handoff 规则

- deploy 或 reset 之后，如果串口安静，不要先怪串口
  先回头确认板子是不是其实还在 `serial download`，或者 USB download state 还没退掉
- 如果当前 unresolved 的只有 Linux login，本层就该交给 login proof owner
- 如果当前 unresolved 的还是：
  `serial download` 还是 `U-Boot`
  `U-Boot` 还是 Linux booting
  那就还停留在 boot-stage proof，不要过早跳到 login 层

## 已验证的 Linux login / shell proof 边界

- `imx943` 的默认 Linux shell proof 仍优先走 `/dev/ttyUSB2`
- `/dev/ttyUSB3` 不默认拿来跑 Linux login automation
- 当前实验室默认 Linux 凭据是：
  username `root`
  password `root`
  但如果 runtime evidence 明确否定，就要跟着现场走
- 最小 shell proof 集合先收这三个：
  `uname -a`
  `cat /etc/os-release`
  `mount`
- login proof owner 负责：
  找到实际可登录的串口
  进入 shell
  留下最小 runtime proof
- login proof owner 不负责反过来判定板子是不是其实还停在 `U-Boot`
  如果这点还没定，就返回 boot-stage proof

## JTAG 相关已验证动作

- JTAG bring-up 已验证板侧使能顺序：
  1. `eeprom -w -board=imx943evk19a0`
  2. `set_gpio fta_jtag_host_en 1 -board=imx943evk19a0`
- JTAG 收尾必须显式清理：
  1. `set_gpio fta_jtag_host_en 0 -board=imx943evk19a0`
  2. 再验证 `fta_jtag_host_en` 返回 `LOW`

## 注意事项

- 不要硬编码单一拨码默认值，优先跟随当前 `bcu` live prompt
- 如果当前目标是进 `serial download`，先看 boot-mode truth，再决定是否扩大排查
- `bcu` 负责 board truth 和 mode-transition legality，不负责 deploy transport 或 Linux login proof
