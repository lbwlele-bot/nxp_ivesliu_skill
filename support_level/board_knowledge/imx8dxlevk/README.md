# imx8dxlevk

## 适用范围

- 板型：`i.MX8DXL EVK`
- 当前主机：Ubuntu 本机
- 来源：旧 `imx8` 入口资料、`imx8dxl` 板控经验、本地 `i.MX8` 故障记录中的已验证结论
- manual-reset-only 只适用于 i.MX8DXL，不得传播到 i.MX93、i.MX943
  或其它板型。

## 默认识别

- 已验证 UART 适配器：
  `0403:6011 FT4232H`
- 机器可读串口映射：
  `serial.yaml`
- 已验证串口顺序：
  - 第 1 个 COM / `if00` / 通常 `ttyUSB0`：未作为当前默认运行日志口
  - 第 2 个 COM / `if01` / 通常 `ttyUSB1`：`M4`
  - 第 3 个 COM / `if02` / 通常 `ttyUSB2`：`U-Boot` / `Fastboot` / Linux early boot
  - 第 4 个 COM / `if03` / 通常 `ttyUSB3`：`SCFW`
- 已验证串口参数：
  `115200 8N1`

这里优先按 FT4232H 的 interface 顺序记忆和核对串口角色。
Linux 的裸 `ttyUSB*` 编号通常会和这个顺序一致，
但实操时仍优先用 `/dev/serial/by-id/...ifNN-port0`，
避免重新枚举后编号漂移。

## 下载态识别

- `lsusb` 看到：
  `1fc9:0147 FA Blank 8DXL`
  表示板子在 ROM USB download
- 此时 `uuu -lsusb` 应看到：
  `MX8DXL SDPS`
- 如果第一阶段基线成功把板子推进到下一阶段，
  `lsusb` 应转成：
  `1fc9:0152 USB download gadget`
  同时 `uuu -lsusb` 应进入 `FB`

## 当前工作方式

- 对新换的 `i.MX8DXL EVK`（LPDDR4，B0 芯片），
  已验证 `bcu` 可以控制 boot mode。
- `bcu` 需要使用 `sudo -n`；
  普通用户执行 `get_boot_mode` 可能报 `no ack received`。
- 当前允许的 BCU 命令只用于切 boot mode：
  - `sudo -n bcu init usb -board=imx8dxlevk`
  - `sudo -n bcu init sd -board=imx8dxlevk`
- i.MX8DXL 当前流程禁止使用 `bcu reset usb`、`bcu reset sd`
  或其它 `bcu reset` 变体。
- reset owner 固定为用户：
  先准备 M4/A-core/SCFW 三路串口捕获，再由用户手动按板上 RESET。
- 原因不是 `bcu reset` 命令一定返回失败，而是该动作会使 FT4232H
  串口短暂断开和重新枚举，早期 M4/SCFW 字节无法找回，并会让后续
  board-state 判断反复建立在不完整日志上。
- 这块板的 EEPROM 当前为空，`bcu` 会提示可写 EEPROM；
  `bcu eeprom -w -board=imx8dxlevk` 属于长期配置动作，需用户明确同意。
- 对旧板或未复测板，仍不要自动套用本条 BCU 结论。
- 如果 BCU 不可用，boot mode 改用板上拨码；reset 仍由用户手动按键。
- 当前状态主要靠：
  1. `lsusb`
  2. `uuu -lsusb`
  3. 已验证的 UART 现场证据
- 不要把 `bcu` 成功返回单独当作运行态证明；
  手动 reset 后仍需用 USB 枚举和串口 fresh probe 判断当前阶段。

## 已验证的主机侧串口纪律

对日志敏感的操作：

- 使用统一工具：
  `../../tools/serial-console/serial-console`
- 优先 `/dev/serial/by-id/...`
  而不是裸 `ttyUSB*`
- 先停 `ModemManager`
- 先把 FT4232H 四个口都重新强制回 `115200 8N1 raw`
- 第一条从全新 `SDPS` 开始的 `uuu -b sd` 之前，就应先把日志采集准备好

高风险误区：

- `ttyUSB*` 安静，不等于板子安静
- 如果 Windows 能看到 log、本机看不到，先查本机串口层

## 已验证的基础进入方式

### 第一阶段基线

从全新 `SDPS` 开始，已验证基线目标是：

- 先用已知可用的 `flash.bin`
- 把板子从 `SDPS` 带到当前 `FB`

对 `i.MX8DXL + lf-6.18.2-1.0.0`，
优先复用的基线根是：

- `validated-lf-6.18.2-1.0.0`

其中第一阶段基线是：

- `imx-boot-imx8dxla1-lpddr4-evk-sd_flash_regression_linux_m4.bin`

### 第二阶段中继

`flash_m4` 不是第一阶段镜像。

它只应在：

- 第一阶段基线已经把板子带到当前 `FB`

之后，作为第二阶段 payload 写入。

不要把 `flash_m4` 直接当成从 `SDPS` 开始的独立基线。

## 已验证的复位规则

- 除了那个特例：
  第一阶段基线已经把板子带到当前 `FB`
  并且你就是要在同一 `FB` 会话里追加第二阶段 `flash_m4`
- 其它 `uuu` 操作默认都应该先回到全新 `SDPS`

也就是说：

- “第一次从 `SDPS` 开始的 `uuu -b sd`”
- 和“板子已经在 `FB` 时重跑 `uuu -b sd`”

不是同一个观察点。

## 已验证的高频注意事项

- 同样是 `uuu -b sd`：
  - 从全新 `SDPS` 开始
  - 和复用现有 `FB` 会话
  不是同一种证明
- 如果板子已经在 `FB`，重跑同样命令可能只是复用现有 Fastboot 会话
- 这时不要把结果误读成“又重新证明了一次 `SDPS -> FB`”

## 已验证的手动交接规则

第二阶段 `flash_m4` 写完以后：

- 需要手动切回 `SD boot`
- 需要手动 reset
- 然后再看 `M4` / `U-Boot` / `SCFW` 运行态日志

不要把当前 `FB` 会话里的写入成功，直接当成最终运行态已经验证

## 已验证的主机侧坑点

- `ModemManager` 会干扰 FT4232H 端口
- `ttyUSB0` / `ttyUSB1` 可能静默掉回 `9600`
- 不使用 BCU reset。该动作会使 FT4232H 串口短暂重新枚举；
  `--reconnect` 只能恢复后续抓取，无法找回物理断开期间已经输出的
  M4/SCFW 早期字节。
- 固定顺序是：先打开三路捕获，切换目标 boot mode，再由用户手动按
  板上 RESET。
- 如果另一台机器能看到日志，本机看不到，
  先查主机串口层，不要先怪镜像

## 当前 B0 LPDDR4 EVK 复测记录

2026-07-22 当前新板复测：

- `bcu init usb` 后可读回 `get_boot_mode: usb, hex value: 0x1`
- 历史测试曾证明 `bcu reset usb/sd` 能改变板状态，但该结论只保留为
  工具能力证据；自 2026-07-24 起不再作为 i.MX8DXL 操作 recipe。
- 当前 recipe 为 `bcu init usb/sd` 只切模式，随后用户手动按 RESET。
- 第 2 个 COM / `if01` / `ttyUSB1` 抓到 M4 输出：
  `RPMSG Link is up!`
- 第 3 个 COM / `if02` / `ttyUSB2` 抓到 SPL、U-Boot、Linux 和 login prompt
- 第 4 个 COM / `if03` / `ttyUSB3` 抓到 SCFW banner

SCFW 编译与第 4 个 COM：

- 当前 `scfw_export_mx8dxl_a0` porting kit 需基于它自带的 A0
  预编译对象链接，不能把空的 `R=B0` 输出目录当作完整源码包重建。
- 需传 `D=1 U=2`；`U=2` 选择 `LPUART_SC` / `if03` / 第 4 个 COM。
- 只传 `D=1` 不够；`U` 默认为 `0`，该路径下
  `board_get_debug_uart()` 返回 `NULL`，SCFW 可以正常启动但串口无输出。
- B0 芯片的硬约束仍是 imx-mkimage `REV=B0` 和
  `mx8dxlb0-ahab-container.img`，不与 SCFW porting kit 对象 revision 混用。

本轮原始记录在：

- `../../work/2026-07-22-imx8dxl-b0-lpddr4-bcu-bootmode/`

## 已验证的资产优先级

对 `i.MX8DXL + lf-6.18.2-1.0.0`：

- 先按当前实物芯片 revision 选择 AHAB，不能把旧 A1 EVK 的 AHAB
  默认套到 B0 板上
- 当前 B0 LPDDR4 EVK 已定位到 B0 AHAB：
  `firmware/imx8dxl/imx-seco-3.7.4/firmware/seco/mx8dxlb0-ahab-container.img`
- `SCFW` 文件名当前不带 A1/B0；使用前记录来源、hash，并用上板日志验证组合

## 注意事项

- 如果本地重新构建的第一阶段回归镜像卡在 `SDPS`，
  先和已知可用基线做 A/B
- 如果基线和新图都在同一 `SDPS` 步骤超时，
  先怀疑下载链路或会话状态，不要先怪新镜像
