# serial-console

- 程序入口：`./serial-console`
- 工具角色：i.MX 板卡统一串口探测、捕获和交互入口
- 底层实现：`python3 + pyserial`
- 板型事实：`profiles/<board>/serial.yaml`
- 板型串口说明：`profiles/<board>/README.md`
- profile schema：`PROFILE_SCHEMA.md`

## 设计边界

工具层负责：

- 从 sysfs 识别 USB-UART 物理适配器
- 把同一个适配器的 `if00/if01/...` 聚合并按接口顺序排列
- 从工具包内的 `profiles/` 读取板型串口事实
- 校验已知板型要求的接口数量和必要 role
- 同时打开多个串口，全部成功后输出 `ALL PORTS READY`
- 分路抓取日志、断线重连、记录捕获状态
- 单路发送命令、打断 U-Boot、交互 shell

工具层不写死：

- 第几个 COM 对应哪个核或固件
- 某块板允许使用哪种 reset
- 串口有输出是否足以证明板子进入某个运行阶段

串口 role 和串口侧风险属于随工具发布的 board profile；完整 reset 能力、
boot mode 和运行阶段判断仍分别属于板级知识和 `board-exec`。

## 设备识别

不要把裸 `/dev/ttyUSB0` 当成稳定身份。

工具优先级是：

1. sysfs 中的 USB 物理设备和 interface number
2. `/dev/serial/by-id/...ifNN-port0`
3. profile 里的 `tty`，仅作为兼容 fallback

### 检测当前所有串口适配器

```bash
./serial-console probe
```

如果只有一个未知适配器，工具会列出它的接口顺序；如果有多个适配器，
使用输出中的 sysfs key、USB serial 或 VID:PID 选择：

```bash
./serial-console probe --adapter <adapter-id>
```

### 校验已知板型

```bash
./serial-console probe --board imx8dxlevk
```

检查内容包括：

- 适配器 VID:PID
- 预期接口数量
- role 对应的 `ifNN`
- 必要 role 是否存在
- profile 是 `verified`、`partial` 还是 `unknown`

必要端口缺失、接口数量不符或多个适配器无法消歧时返回非零。

`list` 保留为兼容的人读枚举命令：

```bash
./serial-console list --board imx8dxlevk
```

## 准备串口

对板型 profile 里的所有已知 role 重新设置串口参数：

```bash
./serial-console prepare \
  --board imx8dxlevk \
  --stop-modemmanager
```

也可以只准备指定 role：

```bash
./serial-console prepare \
  --board imx8dxlevk \
  --role m4 \
  --role a-core
```

`prepare` 只配置串口，不执行 reset。

## 同时抓取必要串口

已知板型默认读取 profile 中 `default_capture: true` 的 role：

```bash
./serial-console capture-set \
  --board imx8dxlevk \
  --log-dir logs \
  --name sd-boot \
  --timeout 90 \
  --prepare \
  --stop-modemmanager
```

执行顺序固定为：

1. 探测并校验物理适配器
2. 校验必要 role
3. 可选执行 `prepare`
4. 打开所有选定串口
5. 启动各路 reader
6. 输出 `ALL PORTS READY: ...; capture is active`
7. 由 `board-exec` 按板型规则安排 reset 或其它动作

对 `imx8dxlevk`，默认抓取：

- `m4`
- `a-core`
- `scfw`

每次生成：

```text
logs/sd-boot-m4.log
logs/sd-boot-a-core.log
logs/sd-boot-scfw.log
logs/sd-boot-serial-session.txt
logs/sd-boot-serial-session.yaml
```

自动化流程可以使用 READY 文件：

```bash
./serial-console capture-set \
  --board imx8dxlevk \
  --log-dir logs \
  --name sd-boot \
  --ready-file state/serial.ready
```

READY 文件是活动状态标记，不是历史结果：

- 新会话启动时先删除同路径的旧 READY，避免把上一次会话误判为本次就绪
- 所有选定端口成功打开、reader 启动后，写入 `state: active`、进程 PID、
  会话名、开始时间和 roles
- 捕获正常结束或被中断退出时删除 READY
- 最终结果以 `*-serial-session.yaml` 为准

进程被 `SIGKILL` 或主机掉电时，操作系统无法保证执行清理；下一次
`capture-set` 启动仍会先清除该路径。自动化程序应先启动本次
`capture-set`，再等待 READY 出现，不应只检查一个已有文件。

人工 reset 等外部动作可能经过对话或操作等待，捕获窗口应覆盖这段等待，
例如使用 `--timeout 600`。启动日志已经抓全后，可向进程发送 Ctrl-C 或
`SIGTERM`；工具会通知各 reader 停止、删除 READY，并照常生成 session
summary。不要使用 `SIGKILL` 结束正常捕获。

### BCU 后恢复缺失 interface

部分板卡的 BCU 会临时接管 FTDI interface，退出后可能没有把该 interface
重新绑定给 Linux 串口驱动。此时 `probe` 会同时看到：

- profile 预期四个 interface，但只检测到三个
- 对应物理 USB interface 仍存在，但没有 serial driver

使用显式恢复命令：

```bash
sudo -n ./serial-console recover --board imx93evk14
./serial-console probe --board imx93evk14
```

`recover` 只处理当前 board profile 声明、物理存在且 driver 未绑定的
interface，并复用同一适配器其它 interface 已绑定的 driver。它不 reset
板子，也不改变 boot mode。

### 未知板型

不传 `--board` 时，工具选择一个物理适配器并捕获它的全部接口：

```bash
./serial-console capture-set \
  --log-dir logs \
  --name discovery \
  --timeout 60
```

日志 role 使用：

```text
port1
port2
port3
...
```

工具不会根据输出内容猜测哪个是 Linux、M 核或系统控制固件。
确认后的映射应由 case 证据进入 `profiles/<board>/serial.yaml`。

### 数据期望

串口成功打开但没有数据时，session 状态是 `empty`，不是 `data`。

要求某些 role 必须收到数据：

```bash
./serial-console capture-set \
  --board imx8dxlevk \
  --log-dir logs \
  --expect-data m4 \
  --expect-data a-core
```

要求全部选定 role 都有数据：

```bash
./serial-console capture-set \
  --board imx8dxlevk \
  --log-dir logs \
  --require-data
```

退出码：

- `0`：所有端口完成捕获；未声明数据期望的端口可以是 `empty`
- `1`：探测、打开、配置、断线恢复或必要端口检查失败
- `2`：声明必须有数据的 role 最终是 `empty`

## 单路操作

抓单路日志：

```bash
./serial-console capture \
  --board imx8dxlevk \
  --role a-core \
  --log logs/a-core.log \
  --timeout 30
```

要求单路必须收到数据并允许 USB 重新枚举后重连：

```bash
./serial-console capture \
  --board imx8dxlevk \
  --role m4 \
  --log logs/m4.log \
  --timeout 60 \
  --reconnect \
  --expect-data
```

发送命令：

```bash
./serial-console send \
  --board imx8dxlevk \
  --role a-core \
  --cmd 'printenv' \
  --log logs/uboot.log
```

打断 U-Boot：

```bash
./serial-console uboot-stop \
  --board imx8dxlevk \
  --role a-core \
  --log logs/uboot-stop.log
```

进入交互串口：

```bash
./serial-console shell \
  --board imx8dxlevk \
  --role a-core \
  --log logs/interactive.log
```

交互模式使用 `Ctrl-]` 退出。

## 捕获状态

每个 role 在 session 中有独立状态：

- `data`：端口打开且收到数据
- `empty`：端口打开，但捕获窗口内没有数据
- `disconnected`：捕获结束时仍未恢复连接
- `not-opened`：整个窗口内从未成功打开

同时记录：

- 第一次打开和第一字节时间
- 接收字节数
- 打开次数
- 断线次数
- 重连尝试次数
- 捕获结束时是否仍连接
- 最后一次错误

`--reconnect` 只能恢复重新枚举后的继续捕获，不能找回物理断开期间已经输出的字节。

## 板级规则

- `serial.yaml` 只记录已验证映射；未确认接口保持未命名
- `partial` profile 只使用已确认 role，不能补猜剩余接口
- reset 方式不由串口工具决定
- i.MX8DXL 需要 M4 早期日志时，BCU 退出后先恢复 `if01`，三路 READY 后
  由用户手动按 RESET
- i.MX8DXL 不需要 M4 日志时，可显式只捕获 `a-core` 和 `scfw`，两路
  READY 后使用已验证的 BCU reset
- 其它板不能直接继承 DXL 这个按观测 role 区分的 reset 规则
- 串口输出或静默都不能单独证明板状态，仍需 `board-exec` 结合 USB 和板控证据判断

## 当前 profile

- `profiles/imx8dxlevk/serial.yaml`：完整已验证
- `profiles/imx93evk14/serial.yaml`：完整已验证
- `profiles/imx943evk19a0/serial.yaml`：完整已验证
- `profiles/imx95evk19/serial.yaml`：部分映射

工具目录包含程序、profile、板型串口说明、schema 和测试。发布时应整体打包
`serial-console/`，不得只复制入口脚本。
