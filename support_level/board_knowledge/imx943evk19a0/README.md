# imx943evk19a0

## 适用范围

- 板型：`i.MX943 EVK 19x19 A0`
- 当前主机：Ubuntu 本机
- 来源：旧 `i.MX943` 板控和工作流里的已验证板级结论

## 默认识别

- 默认 Linux / `U-Boot` console：
  `/dev/ttyUSB2`
- `/dev/ttyUSB3` 更偏向 `SM` / monitor console，不默认当 Linux shell
- 机器可读串口映射：
  `serial.yaml`
- 默认 `bcu` board token：
  `imx943evk19a0`

## 当前板控认知

- 当前 Ubuntu 路径里，`bcu` 是 `i.MX943` 板状态最强信号之一
- 板级连板快速判断时，强信号优先级是：
  1. `bcu`
  2. `uuu`
  3. 已验证串口证据
- 不要因为串口暂时安静，就覆盖掉更强的 `bcu` / `uuu` 结论

### 当前 A0 实物复测

2026-07-24 当前连接板的 FTDI EEPROM 明确报告：

- `NXP i.MX943 19x19 EVK Board Rev A0`
- `i.MX943 Rev A0`
- FTDI serial：`BE38C4`

使用 `imx943evk19b1` 会被 BCU 以 EEPROM revision mismatch 拒绝，因此
不能只按 PCB 颜色判断 A0/B1，也不能在 reset 动作上盲试两个 profile。

当前实物即使保持 SW7-1=ON 并重新上电，BCU 的 `remote_en`、`mode_dir`
和 `reset` GPIO 访问仍返回 `0xffffffff`，`bcu reset` 明确失败。
所以历史上验证过的 BCU reset 不能覆盖当前现场：

- BCU 仍可读 FTDI EEPROM并识别 A0
- 当前不能把 BCU reset 当成可用恢复动作
- 在 SW7/BCU GPIO 路径修复前，启动捕获使用物理重新上电
- 不通过写 EEPROM 伪装成 B1

BCU 硬件访问同样会接管 FT4232H `if01` 并留下未绑定状态。恢复：

```bash
sudo -n ../../tools/serial-console/serial-console recover --board imx943evk19a0
../../tools/serial-console/serial-console probe --board imx943evk19a0
```

## 已验证的基础进入方式

- 默认当前起始状态可以先假设：
  - `BOOT SWITCH`
  - 没有当前 USB 下载设备
  - serial candidates 可见
- 查询 boot mode / reset 时，优先显式带：
  `-board=imx943evk19a0`

## 已验证的高频操作前提

- 当前主机 `sudo` 的 `PATH` 不包含共享工具根
- 所以不要假设：
  `sudo -n bcu ...`
  一定能工作
- 更稳定的入口应是显式路径，例如：
  `sudo -n ../../tools/bcu/bcu ...`

## 已验证的恢复动作

- 已验证可把板子拉回正常 boot 路径的 reset 形态：
  `reset sd -board=imx943evk19a0`
- 这条路径可作为从任意混乱状态回到可控复位基线的默认恢复动作
  但仍要以当前 现场证据 为准
- 当前 A0 实物复测已经否定其现场前提：GPIO 路径失败时不得继续使用本条，
  应退回物理重新上电并保留 BCU 错误日志

## 当前串口映射

主板 FT4232H 固定枚举四个 interface：

- `if00`：无默认运行日志 role
- `if01`：BCU 板控通道，无默认运行日志 role
- `if02`：A-core，SPL/BL31/U-Boot/Linux
- `if03`：SMFW / SM Debug Monitor

2026-07-24 物理重新上电捕获结果：

- A-core：73658 bytes，无重连，Linux 6.12.34-rt11 到 login
- SM：103 bytes，无重连，看到 `Hello from SM` 和 `SM Debug Monitor`

当前没有连接外部 application M-core UART 转接板；这些 UART 不属于上述
主板四口 profile，也不作为本轮验收失败项。

## 已验证的异构核约束

- `m33_0` 默认是保留核，必须跑 `SMFW`
- 其余 `M33` 核才是当前 case 里可能允许触碰的目标核
- 在明确当前板子已经越过下载态并进入后续可控阶段前，不提前宣称某个 `M33` payload 已经可以接手
- 如果当前任务要起某个 `M33` payload，先说清：
  目标核
  payload
  预计由 `flash.bin`、`U-Boot` 还是 Linux 侧接手
  然后再进入对应后续动作

## 已验证的连板快速路径

- 当前 `i.MX943` 已验证的板级默认链路是：
  `主机检查 -> bcu 板状态事实 -> uuu 传输 -> 启动阶段判断 -> 登录判断`
- 其中：
  - `bcu`
    负责板状态事实和模式切换是否合法
  - `uuu`
    负责 USB 传输
  - 启动与运行态判断
    负责判断到底停在 `serial download`、`U-Boot` 还是 Linux
- 不要把 上板写入 成功、`uuu` 成功或 reset 成功，直接当成 Linux 已经起来

## 已吸收：主机检查边界

- `主机检查` 只负责：
  主机系统路径
  工具是否就绪
  `sudo` / permissions
  串口候选口
  是否已经具备现场探测前提
- `主机检查` 不负责：
  当前 boot mode 事实
  reset 事实
  最终现场板状态事实

## 已吸收：编译侧链路认知

当前 `i.MX943` 已经在新骨架里分清：

- Linux kernel-side build
- `M-core RTOS`
- `A55 RTOS`

但这些链路负责的是构建、打包和 payload 约定，
不是板侧状态判断。

也就是说：

- 编译侧出产物
- 板侧判断当前到底到了哪一步

## 已验证的启动阶段判断边界

- `serial download`
  优先看当前 USB 下载态证据，例如 `SDPS` / `SDPV`
  不要等串口先说话才承认板子还在下载态
- `U-Boot`
  默认先在 `/dev/ttyUSB2` 抓验证
  看到 `Hit any key to stop autoboot`、`u-boot=>` 或等价 prompt，才算已经进入 `U-Boot`
- `Linux-ready`
  必须先看到明确的 Linux 启动证据，再把问题交给登录判断
  不要让登录判断反过来替启动判断做结论
- 如果 `U-Boot` 环境明显健康，优先走环境驱动的高层 boot path
  例如：
  `boot`
  或板上已验证的正常 boot 命令
- 只有环境坏了、目标就是手动控制、或高层 boot path 明显不成立时，才降到 `booti` 一类低层 direct boot

## 高频回退 / 交接规则

- 上板写入 或 reset 之后，如果串口安静，不要先怪串口
  先回头确认板子是不是其实还在 `serial download`，或者 USB download state 还没退掉
- 如果当前未解决的只有 Linux 登录，本层就该交给登录判断
- 如果当前未解决的还是：
  `serial download` 还是 `U-Boot`
  `U-Boot` 还是 Linux booting
  那就还停留在启动阶段判断，不要过早跳到登录层

## 已验证的 Linux 登录 / shell 验证边界

- `imx943` 的默认 Linux shell 验证 仍优先走 `/dev/ttyUSB2`
- `/dev/ttyUSB3` 不默认拿来跑 Linux login automation
- 当前实验室默认 Linux 凭据是：
  username `root`
  password `root`
  但如果现场运行态证据明确否定，就要跟着现场走
- 最小 shell 验证集合先收这三个：
  `uname -a`
  `cat /etc/os-release`
  `mount`
- 登录判断负责：
  找到实际可登录的串口
  进入 shell
  留下最小 运行态验证
- 登录判断不负责反过来判定板子是不是其实还停在 `U-Boot`
  如果这点还没定，就返回启动阶段判断

## JTAG 相关已验证动作

- JTAG bring-up 已验证板侧使能顺序：
  1. `eeprom -w -board=imx943evk19a0`
  2. `set_gpio fta_jtag_host_en 1 -board=imx943evk19a0`
- JTAG 收尾必须显式清理：
  1. `set_gpio fta_jtag_host_en 0 -board=imx943evk19a0`
  2. 再验证 `fta_jtag_host_en` 返回 `LOW`

## 注意事项

- 不要硬编码单一拨码默认值，优先跟随当前 `bcu` 现场提示
- 如果当前目标是进 `serial download`，先看 boot-mode 事实，再决定是否扩大排查
- `bcu` 负责板状态事实和模式切换是否合法，不负责上板写入传输或 Linux 登录判断
- `m33_0` 不是当前 case 可自由分配的通用核，不要把它和其余 `M33` 混成同一种可用资源
