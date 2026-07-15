# imx8dxlevk

## 适用范围

- 板型：`i.MX8DXL EVK`
- 当前主机：Ubuntu 本机
- 来源：旧 `imx8` 入口资料、`imx8dxl` 板控经验、本地 `i.MX8` 故障记录中的已验证结论

## 默认识别

- 已验证 UART 适配器：
  `0403:6011 FT4232H`
- 机器可读串口映射：
  `serial.yaml`
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
- 如果第一阶段基线成功把板子推进到下一阶段，
  `lsusb` 应转成：
  `1fc9:0152 USB download gadget`
  同时 `uuu -lsusb` 应进入 `FB`

## 当前工作方式

- 当前这块 `i.MX8DXL` 不使用 `bcu`
- reset / 启动拨码切换依赖用户手动操作
- 当前状态主要靠：
  1. `lsusb`
  2. `uuu -lsusb`
  3. 已验证的 UART 现场证据
- 不要把旧 `bcu` 痕迹继续当成当前默认流程

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
- 如果另一台机器能看到日志，本机看不到，
  先查主机串口层，不要先怪镜像

## 已验证的资产优先级

对 `i.MX8DXL + lf-6.18.2-1.0.0`：

- 先复用已验证的资产根
- 先复用已验证 `A1 AHAB`
- 不要重新去猜 `AHAB` / `SCFW` 组合

## 注意事项

- 如果本地重新构建的第一阶段回归镜像卡在 `SDPS`，
  先和已知可用基线做 A/B
- 如果基线和新图都在同一 `SDPS` 步骤超时，
  先怀疑下载链路或会话状态，不要先怪新镜像
