# imx8dxlevk

## 适用范围

- 板型：`i.MX8DXL EVK`
- 当前主机：Ubuntu 本机
- 来源：旧 `imx8-family-intake` / `imx8dxl-board-control` / 本地 i.MX8 failure notebook 已验证结论

## 默认识别

- 已验证 UART 适配器：
  `0403:6011 FT4232H`
- 已验证串口映射：
  - `ttyUSB1`：`M4`
  - `ttyUSB2`：`U-Boot` / `Fastboot` / Linux early boot
  - `ttyUSB3`：`SCFW`
- 已验证串口参数：
  `115200 8N1`

## 下载态识别

- `lsusb` 看到：
  `1fc9:0147 FA Blank 8DXL`
  表示板子在 ROM USB download
- 此时 `uuu -lsusb` 应看到：
  `MX8DXL SDPS`
- 如果第一阶段 baseline 成功 bring-up 到下一阶段，
  `lsusb` 应转成：
  `1fc9:0152 USB download gadget`
  同时 `uuu -lsusb` 应进入 `FB`

## 当前 active workspace 规则

- 这条 `i.MX8DXL` lane 当前不使用 `bcu`
- reset / boot-switch change 依赖用户手动操作
- live state 主要靠：
  1. `lsusb`
  2. `uuu -lsusb`
  3. validated UART evidence
- 不要把旧 `bcu` 痕迹继续当成当前默认流程

## 已验证的主机侧串口纪律

对 log-sensitive run：

- 优先 `/dev/serial/by-id/...`
  而不是裸 `ttyUSB*`
- 先停 `ModemManager`
- 先把 FT4232H 四个口都重新强制回 `115200 8N1 raw`
- 第一条从 fresh `SDPS` 开始的 `uuu -b sd` 之前，就应先把 capture arm 好

高风险误区：

- `ttyUSB*` 安静，不等于板子安静
- 如果 Windows 能看到 log、本机看不到，先查本机串口层

## 已验证的基础进入方式

### first-stage baseline

从 fresh `SDPS` 开始，已验证 baseline 目标是：

- 先用 known-good `flash.bin`
- 把板子从 `SDPS` 带到 live `FB`

对 `i.MX8DXL + lf-6.18.2-1.0.0`，
优先复用的 baseline 根是：

- `validated-lf-6.18.2-1.0.0`

其中 first-stage baseline 是：

- `imx-boot-imx8dxla1-lpddr4-evk-sd_flash_regression_linux_m4.bin`

### second-stage relay

`flash_m4` 不是 first-stage image。

它只应在：

- first-stage baseline 已经把板子带到 live `FB`

之后，作为 second-stage payload 写入。

不要把 `flash_m4` 直接当成从 `SDPS` 开始的独立 baseline。

## 已验证的 reset discipline

- 除了那个特例：
  first-stage baseline 已经把板子带到 live `FB`
  并且你就是要在同一 `FB` session 里追加 second-stage `flash_m4`
- 其它 `uuu` run 默认都应该先回到 fresh `SDPS`

也就是说：

- “第一次从 `SDPS` 开始的 `uuu -b sd`”
- 和“板子已经在 `FB` 时重跑 `uuu -b sd`”

不是同一个 observation point。

## 已验证的高频注意事项

- 同样是 `uuu -b sd`：
  - 从 fresh `SDPS` 开始
  - 和复用现有 `FB` session
  不是同一种证明
- 如果板子已经在 `FB`，重跑同样命令可能只是复用现有 Fastboot session
- 这时不要把结果误读成“又重新证明了一次 `SDPS -> FB`”

## 已验证的 manual handoff 规则

second-stage `flash_m4` 写完以后：

- 需要手动切回 `SD boot`
- 需要手动 reset
- 然后再看 `M4` / `U-Boot` / `SCFW` runtime log

不要把 live `FB` session 里的写入成功，直接当成最终 runtime 已经验证

## M4 构建相关已验证规则

- 除非明确要求 `NOR flash` 或其他 flash-linked lane，
  默认优先非 `flash` linker / build lane
- 名字里带：
  `flash_debug`
  `flash_release`
  `*_flash.ld`
  默认视为 flash-linked
- 名字里带：
  `debug`
  `release`
  `*_ram.ld`
  默认视为 RAM / TCM-loaded lane
- 对 `flash_m4`，
  优先标准目标：
  `make SOC=iMX8DXL REV=A1 flash_m4`
- 不要默认直接调用 `mkimage_imx8`

## 已验证的主机侧坑点

- `ModemManager` 会干扰 FT4232H 端口
- `ttyUSB0` / `ttyUSB1` 可能静默掉回 `9600`
- 如果另一台机器能看到日志，本机看不到，
  先查主机串口层，不要先怪镜像

## 已验证的资产优先级

对 `i.MX8DXL + lf-6.18.2-1.0.0`：

- 先复用 validated asset root
- 先复用已验证 `A1 AHAB`
- 不要重新去猜 `AHAB` / `SCFW` 组合

## 注意事项

- 如果 locally rebuilt 的 stage-0 regression image 卡在 `SDPS`，
  先和 known-good baseline 做 A/B
- 如果 baseline 和新图都在同一 `SDPS` 步骤超时，
  先怀疑下载链路或会话状态，不要先怪新镜像
