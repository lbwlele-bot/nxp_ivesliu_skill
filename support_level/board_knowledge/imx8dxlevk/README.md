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
- BCU 和 `serial-console` 必须串行执行，不能并发 probe、prepare 或 capture。
  2026-07-24 实测并发探测连续 5/5 次只枚举到三个 FT4232H interface，
  固定丢失 `if01/M4`；BCU 结束后串口独占探测连续 5/5 次恢复四个 interface。
- BCU 命令结束后先执行 `udevadm settle` 并短暂等待，再做串口 fresh probe；
  只有 `if00-if03` 四个 interface 完整出现后才能开始捕获或要求用户 reset。
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
- 不与 BCU 并发；BCU 完成、udev settle 后重新确认四个 interface
- 等待用户手动 reset 的交互式捕获使用足够长的等待窗口；启动日志抓全后
  用 Ctrl-C 或 SIGTERM 让工具正常生成 session summary，不用 SIGKILL
- 第一条从全新 `SDPS` 开始的 `uuu -b sd` 之前，就应先把日志采集准备好

高风险误区：

- `ttyUSB*` 安静，不等于板子安静
- 如果 Windows 能看到 log、本机看不到，先查本机串口层

## M 核加载路径偏好

对 i.MX8QM、i.MX8QXP、i.MX8DXL 这一代 SCFW 平台，
当前工程先验是优先使用 early boot `flash.bin` 路径加载 M 核。

这是默认路线选择，不是能力判定：

- `bootaux` 和 Linux remoteproc loading 并非禁止使用
- 这些较早平台及部分 release 上，
  `flash.bin` 路径通常有更充分的组合验证
- 没有明确需求和当前板型/release 证据时，
  不主动把 loader 从 `flash.bin` 切到 `bootaux` 或 remoteproc loading
- 如果 case 明确需要其它 loader，先说明理由、支持证据和回退路径，
  再与工程师确认

Linux remoteproc attach-only 与 remoteproc loading 不是一回事。
M 核可以由 `flash.bin` 启动，
Linux 仍通过 attach 使用 resource table、virtio 和 RPMsg。

## 基线与历史案例的适用边界

i.MX8DXL 不存在脱离实物身份的单一全局基线。
每个新 case 必须先确认：

- silicon revision
- DDR 类型
- BSP/release
- boot image recipe
- M 核 loader
- 当前验证目标

当前实物和用户确认优先于历史案例。
历史 A1 板上验证过的镜像不能自动成为 B0 板的基线。

### 当前 B0 LPDDR4 case

2026-07-22 当前实物已确认为：

- silicon：B0
- DDR：LPDDR4
- BSP：`lf-6.18.2-1.0.0`
- recipe：`flash_linux_m4`
- M 核 loader：early boot `flash.bin`
- regression：不使用

同一身份下可用于对照和救援的官方 B0 镜像：

- `../../Image/i.MX8DXL-6.18.2-1.0.0/imx-boot-imx8dxlb0-lpddr4-evk-sd.bin-flash_linux_m4`
- SHA-256：
  `b256698c8505808fe219a124ebdb8d9d7482bbf01b5ea5509d07251d0d0afd2e`

该镜像是当前 B0 case 的参考输入，
不能因此推广成其它 revision、release 或 recipe 的默认基线。

### 历史 A1 case

下面的 A1 regression 镜像来自之前的 A1 实物和历史 FlexCAN/`flash_m4`
两阶段案例：

- `imx-boot-imx8dxla1-lpddr4-evk-sd_flash_regression_linux_m4.bin`

该历史案例曾使用：

```text
first-stage A1 regression flash.bin: SDPS -> FB
-> second-stage flash_m4 in the same FB session
-> switch to SD boot and reset
```

这条记录只保留为历史案例证据：

- 不适用于当前 B0 实物
- 不把 `regression` 或 `flash_m4` 两阶段流程当成 DXL 通用默认
- 未来重新使用 A1 板时仍要重新确认当前实物、release 和 recipe

## UUU 阶段证据

从全新 `SDPS` 执行 first-stage `uuu -b sd`
和在已有 `FB` 会话中执行后续写入不是同一个观察点。

- 验证新的 first-stage 链路时，默认先回到 fresh `SDPS`
- 只有当前 case 明确定义了 second-stage，
  且已有证据证明当前处于同一 `FB` 会话时，才复用该会话
- 如果板子已经在 `FB`，重跑同样命令不能重新证明 `SDPS -> FB`
- UUU 写入成功不能直接证明最终 SD boot 运行态成立

## 手动启动交接

完成当前 case 要求的 boot image 和 FAT 文件写入后：

- 先准备 M4、A-core、SCFW 三路捕获
- BCU 只切到 SD boot mode
- 用户手动按板上 RESET
- 再用 USB 枚举和三路运行日志验证实际启动结果

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

- 先锁定当前实物、DDR、recipe 和 loader，
  再选择同一身份的参考镜像和输入
- 先按当前实物芯片 revision 选择 AHAB，不能把旧 A1 EVK 的 AHAB
  默认套到 B0 板上
- 当前 B0 LPDDR4 EVK 已定位到 B0 AHAB：
  `../../firmware/imx8dxl/imx-seco-3.7.4/firmware/seco/mx8dxlb0-ahab-container.img`
- B0 AHAB SHA-256：
  `bbd13c802df44e3fa6c476a84a15ce680eaf3f5e8d1a6b367b670e67ce34c0f7`
- A1 regression 镜像只保留为历史案例证据，
  不参与当前 B0 case 的默认选择
- `SCFW` 文件名当前不带 A1/B0；使用前记录来源、hash，并用上板日志验证组合

## 注意事项

- 如果本地重新构建的 first-stage 镜像卡在 `SDPS`，
  先和当前实物身份匹配的已知可用参考镜像做 A/B
- 如果参考镜像和新图都在同一 `SDPS` 步骤超时，
  先怀疑下载链路或会话状态，不要先怪新镜像
