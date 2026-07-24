# Serial Profile Schema

板型串口 profile 位于：

```text
support_level/board_knowledge/<board>/serial.yaml
```

profile 只保存板级串口事实。串口探测、捕获和交互逻辑属于
`support_level/tools/serial-console/serial-console`。

## Schema 2

```yaml
schema_version: 2
board: imx8dxlevk
profile_status: verified

adapter:
  name: FT4232H Quad HS USB-UART/FIFO IC
  usb_id: "0403:6011"
  interface_count: 4

baudrate: 115200
format: 8N1
prefer_by_id: true

ports:
  a-core:
    order: 3
    interface: if02
    by_id: usb-FTDI_Quad_RS232-HS-if02-port0
    tty: /dev/ttyUSB2
    description: Third COM; U-Boot and Linux console
    log_sources:
      - u-boot
      - linux
    default_capture: true
    required: true
    status: verified

evidence:
  verified_at: "2026-07-24"
  case: ../../work/<case>
  session: logs/<session>
```

## Profile 状态

`profile_status`：

- `verified`：适配器数量、接口数量和默认 role 映射已经完整验证
- `partial`：只确认了部分接口；未记录接口不得自动分配 role
- `unknown`：临时 discovery profile，没有任何板级角色结论

profile 状态描述整份映射的完整程度。

每个 port 的 `status` 描述这一条 role 映射自身的证据程度，目前允许：

- `verified`
- `partial`
- `unknown`

## Adapter 字段

- `name`：人读名称，不参与严格匹配
- `usb_id`：可选的 `VID:PID`
- `interface_count`：已确认的物理接口数量

只填写已经从实物确认的字段。

当 `interface_count` 存在时，`probe` 会严格核对；因此不能因为芯片名称包含
`Quad` 就在没有现场证据时随意填写 `4`。

## Port 字段

- `order`：接口在线材枚举中的一基顺序
- `interface`：稳定的 USB interface number，例如 `if02`
- `by_id`：已观察到的 udev by-id 名称
- `tty`：常见 tty 名，只作 fallback 和人读提示
- `description`：这一路的已验证用途
- `log_sources`：可能从该口输出的固件或软件阶段
- `default_capture`：默认是否加入 `capture-set`
- `required`：执行该 profile 时是否必须存在
- `status`：该映射的验证状态

`interface` 是主要机器身份，`ttyUSBn` 不是。

同一 profile 中 `order` 和 `interface` 都不能重复。

## Evidence

完整或新增映射必须能回到原始 case：

```yaml
evidence:
  verified_at: "YYYY-MM-DD"
  case: ../../work/<case>
  session: logs/<serial-session>
```

只有资料推测、历史印象或一次未保存的观察，不能升级为 `verified`。

新板首次 discovery 时：

1. 使用无 `--board` 的 `probe` 或 `capture-set`
2. 按 `port1/port2/...` 保存全部原始日志
3. 由用户确认板型和 role
4. 在 case 中保留证据
5. 再更新 `serial.yaml`

## Reset 边界

profile 可以记录串口侧风险，但 `serial-console` 不自行选择或执行 reset。

reset 能力属于板型和实物：

- i.MX8DXL 当前是 manual-reset-only
- 其它板必须按各自板级知识并与用户确认
- 某块板的 reset 结论不得传播到其它 SoC 或 EVK

## Schema 1 兼容

工具仍能读取旧的 role mapping：

```yaml
ports:
  a-core:
    by_id: ...
    tty: ...
```

旧 profile 缺少接口状态和完整度，按 `unknown` 处理。新增或修改 profile 应使用
schema 2。
