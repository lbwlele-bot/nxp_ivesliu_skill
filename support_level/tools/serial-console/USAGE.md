# serial-console

- 程序入口：`./serial-console`
- 工具角色：统一串口入口，负责列串口、按板型角色解析串口、抓 log、发命令、自动打断 `U-Boot`
- 底层实现：`python3 + pyserial`

## 使用边界

`serial-console` 只负责串口工具能力，不保存板型事实。

它读取：

```text
../../board_knowledge/<board>/serial.yaml
```

来解析：

- 哪个 role 对应哪一路串口
- 默认 baudrate
- 是否优先 `/dev/serial/by-id`

具体板子的四口映射、默认 console、UART mux 风险、保留核约束，继续放在
`board_knowledge/<board>/README.md` 和 `serial.yaml`，不要写进工具。

## 常用命令

列出当前串口和某块板的 role 映射：

```bash
./serial-console list --board imx8dxlevk
```

对某块板的所有已知 role 套用串口参数：

```bash
./serial-console prepare --board imx8dxlevk --stop-modemmanager
```

抓取某个 role 的串口日志：

```bash
./serial-console capture --board imx8dxlevk --role a-core --log logs/a-core.log --timeout 30
```

发送命令并继续抓取短日志：

```bash
./serial-console send --board imx8dxlevk --role a-core --cmd 'printenv' --log logs/uboot.log
```

自动等待 `U-Boot` 三秒倒计时并发送回车：

```bash
./serial-console uboot-stop --board imx8dxlevk --role a-core --log logs/uboot-stop.log
```

进入交互串口：

```bash
./serial-console shell --board imx8dxlevk --role a-core --log logs/interactive.log
```

交互模式用 `Ctrl-]` 退出。

## 规则

- 默认优先使用 `board_knowledge/<board>/serial.yaml` 里的 role，不临场盲扫四个口
- 优先 `/dev/serial/by-id/*`，没有 by-id 时才回退到 profile 里的 `tty`
- `uboot-stop` 只在看到 `Hit any key to stop autoboot` 后发送回车
- `capture` / `send` / `uboot-stop` 的原始输出应写到当前 case 的 `logs/`
- `serial-console` 成功抓到或没抓到输出，都不单独证明板子状态；状态判断仍由 `board-exec` 结合 USB / 板控 / 串口证据完成

## 板型事实位置

当前已知 profile：

- `../../board_knowledge/imx8dxlevk/serial.yaml`
- `../../board_knowledge/imx93evk14/serial.yaml`
- `../../board_knowledge/imx943evk19a0/serial.yaml`
- `../../board_knowledge/imx95evk19/serial.yaml`
