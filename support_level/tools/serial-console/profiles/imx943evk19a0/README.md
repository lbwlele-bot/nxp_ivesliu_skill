# i.MX943 19x19 A0 EVK Serial Profile

## Onboard FT4232H 映射

| 顺序 | Interface | 默认 role | 已验证输出 |
|---|---|---|---|
| 第 1 个 COM | `if00` | `first-com` | 未分配默认运行日志 |
| 第 2 个 COM | `if01` | `second-com` | BCU 板控，无默认运行日志 |
| 第 3 个 COM | `if02` | `a-core` | SPL、BL31、U-Boot、Linux |
| 第 4 个 COM | `if03` | `sm` | SMFW、SM Debug Monitor |

默认同时捕获 `a-core` 和 `sm`，参数为 `115200 8N1`。Linux shell 和
U-Boot 操作默认使用 `a-core`，不要把 `if03` 当作 Linux console。

主板 FT4232H 带每块板独立的 USB serial，工具使用 VID:PID、物理适配器和
interface 解析，不硬编码完整 by-id basename。

## Profile 边界

当前没有连接外部 application M-core UART 转接板。那些 UART 不属于主板
四口 profile，也不应根据主板四个 COM 的内容推测其 role。

板 revision 必须由 BCU EEPROM 等现场证据确认；PCB 颜色不能替代 A0/B1
识别。本 profile 只适用于 `imx943evk19a0`。

## BCU 影响

BCU 实际板控访问使用 FT4232H channel 1，即 `if01`，退出后可能留下未绑定
状态。BCU 操作结束后执行：

```bash
sudo -n ./serial-console recover --board imx943evk19a0
./serial-console probe --board imx943evk19a0
```

`recover` 不 reset 板子，也不改变 boot mode。当前 A0 实物的 BCU GPIO
reset 路径另有现场故障，串口工具不据此选择 reset 方法。

## 证据

- profile 验证日期：2026-07-24
- 来源 case：`2026-07-24-imx943evk19a0-serial-console-validation`
- `a-core`：73658 bytes，Linux 6.12.34-rt11 到 login
- `sm`：103 bytes，包含 `Hello from SM` 和 `SM Debug Monitor`
