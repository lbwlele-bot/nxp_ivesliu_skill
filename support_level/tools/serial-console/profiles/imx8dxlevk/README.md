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

DXL 上后果尤其明显：缺失 `if01` 就会直接缺失 M4 早期日志。reset 规则应按
本次需要保留的串口证据区分。

### 需要 M4 早期日志

不能使用 BCU reset，也不能在捕获 `m4/if01` 时并发执行 BCU：

1. 如果需要 BCU 查询或切 boot mode，先完成 BCU 操作。
2. BCU 退出后执行 `recover`，fresh probe 必须重新看到 `if00-if03`。
3. 启动 M4、A-core、SCFW 三路捕获并等待 `ALL PORTS READY`。
4. 由用户手动按板上 RESET。

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

`--reconnect` 只能继续捕获重新绑定后的数据，不能找回 BCU 占用 `if01`
期间已经输出的 M4 早期字节。

### 不需要 M4 早期日志

如果验收只要求 A-core 和 SCFW，当前 B0 LPDDR4 实物已验证可以在这两路
捕获 READY 后使用 BCU reset：

```bash
./serial-console capture-set \
  --board imx8dxlevk \
  --role a-core \
  --role scfw \
  --log-dir logs \
  --name bcu-reset \
  --timeout 90 \
  --prepare

# 看到 ALL PORTS READY 后，在另一终端执行
sudo -n ../bcu/bcu reset -board=imx8dxlevk
```

2026-07-24 连续 3 次普通 reset 均抓到：

- `a-core/if02`：SPL、U-Boot、Linux，首轮到 login
- `scfw/if03`：SCFW banner 和启动统计
- 两路有效 session 均为 0 reconnect

该结果不证明 M4 早期日志完整，也不自动覆盖其它 DXL revision、实物或带
boot-mode 参数的 reset。BCU 退出后仍要 fresh probe；如果 `if01` 未绑定，
使用 `recover`。

## 主机侧注意事项

- `ModemManager` 可能干扰 FT4232H。
- `ttyUSB0`、`ttyUSB1` 曾出现静默回到 9600 的情况，捕获前应 prepare。
- Windows 能看到日志而当前主机看不到时，先检查 interface 驱动绑定和串口参数。
- 串口静默不能单独证明板子或固件没有运行。

## 证据

- profile 验证日期：2026-07-24
- 来源 case：`2026-07-23-imx8dxl-power-mode-ocram-suspend`
- 已验证 M4、A-core/Linux 和 SCFW 三路输出
- BCU reset 串口范围 case：
  `2026-07-24-imx8dxl-bcu-reset-serial-scope`
