# i.MX8DXL EVK Serial Profile

## Onboard FT4232H 映射

| 顺序 | Interface | 默认 role | 已验证输出 |
|---|---|---|---|
| 第 1 个 COM | `if00` | `first-com` | 未分配默认运行日志 |
| 第 2 个 COM | `if01` | `m4` | M4 |
| 第 3 个 COM | `if02` | `a-core` | SPL、U-Boot、Fastboot、Linux |
| 第 4 个 COM | `if03` | `scfw` | SCFW |

默认同时捕获 `m4`、`a-core` 和 `scfw`，参数为 `115200 8N1`。
interface 顺序是稳定身份，`ttyUSB0-3` 只作现场提示。

## BCU Channel 1 冲突

当前 BCU 板控访问固定使用 FT4232H channel 1，即 USB `if01`。这与 DXL
的 M4 console 是同一 interface。`get_boot_mode`、boot-mode 操作和 reset
等实际板控访问都可能在退出后留下未绑定的 `if01`；这不是 DXL 特有的
USB 串口枚举故障，而是 BCU 接管 channel 1 后的主机驱动清理缺口。

DXL 上后果尤其明显：缺失 `if01` 就会直接缺失 M4 早期日志。因此：

1. BCU 与 `serial-console` 不并发运行。
2. 如果需要 BCU 切 boot mode，先完成 BCU 操作。
3. BCU 退出后执行 `recover`，fresh probe 必须重新看到 `if00-if03`。
4. 启动 M4、A-core、SCFW 三路捕获并等待 `ALL PORTS READY`。
5. 由用户手动按板上 RESET。

```bash
sudo -n ./serial-console recover --board imx8dxlevk
./serial-console probe --board imx8dxlevk
./serial-console capture-set \
  --board imx8dxlevk \
  --log-dir logs \
  --name sd-boot \
  --timeout 600 \
  --prepare \
  --stop-modemmanager
```

不要使用 BCU reset。`--reconnect` 只能继续捕获重新枚举后的数据，不能找回
断开期间已经输出的 M4 或 SCFW 早期字节。

## 主机侧注意事项

- `ModemManager` 可能干扰 FT4232H。
- `ttyUSB0`、`ttyUSB1` 曾出现静默回到 9600 的情况，捕获前应 prepare。
- Windows 能看到日志而当前主机看不到时，先检查 interface 驱动绑定和串口参数。
- 串口静默不能单独证明板子或固件没有运行。

## 证据

- profile 验证日期：2026-07-24
- 来源 case：`2026-07-23-imx8dxl-power-mode-ocram-suspend`
- 已验证 M4、A-core/Linux 和 SCFW 三路输出
