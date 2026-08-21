# bcu

- 程序入口：`sudo -n ./bcu`
- 当前版本：`bcu_1.1.128-0-ge7027dc`
- 工具角色：板控 / 复位 / 启动模式控制 / GPIO 辅助控制

## 权限硬规则

本机执行任何 `bcu` 命令都必须使用：

```bash
sudo -n ./bcu <args>
```

包括版本、帮助、只读查询、boot mode、reset 和 GPIO 操作。

- 不先尝试普通用户执行
- `sudo -n` 失败时立即停止并报告权限问题
- 不回退到不带 `sudo` 的命令

## 板型身份默认从 EEPROM 读取

不再让 LLM 手工选择 `-board=<board>`。默认先执行：

```bash
sudo -n ./bcu lsftdi
sudo -n ./bcu eeprom -r -auto
```

使用规则：

1. `lsftdi` 必须明确只有一块 FTDI 板控设备。
2. 零块时阻断；多块时也阻断默认 `-auto`，先让用户确认目标实物。
3. EEPROM 读取成功必须同时输出 `Auto recognized the board`、
   `Board Info`、`SoC Info` 和 `done`。
4. 将自动识别出的 BCU board id、FTDI serial、board revision、SoC revision
   和 PMIC 完整展示给用户，并用该 board id 选择后续 board profile。
5. 某些设备会先打印 `Invalid EEPROM context`，但仍可以随后返回完整
   的 registered EEPROM 内容。不得因此自动执行 `-w`；`-w` 是长期写入动作。
6. 如果最终没有返回完整身份，说明该板 EEPROM 不能作为自动选择源。
   此时回退到已有 board profile 和用户确认，不由 LLM 自行猜测。

当前板状态和目标动作仍然要明确。动作类型包括：

- boot mode 查询
- boot mode 切换
- reset
- GPIO 辅助控制

## 典型命令形态

查版本或帮助：

```bash
sudo -n ./bcu version
sudo -n ./bcu -h
```

常见命令族：

```bash
sudo -n ./bcu get_boot_mode -auto
sudo -n ./bcu set_boot_mode <BOOTMODE_NAME> -auto
sudo -n ./bcu reset <BOOTMODE_NAME> -auto
sudo -n ./bcu set_gpio <GPIO_NAME> 1 -auto
sudo -n ./bcu set_gpio <GPIO_NAME> 0 -auto
```

`-auto` 在每次命令中重新从 EEPROM 确认板型，不依赖上一次对话或
LLM 记忆。它只适用于 `lsftdi` 已证明当前只有一块板控设备，
且 `eeprom -r -auto` 已返回完整身份的情况。

## 使用边界

- `bcu` 是板控工具，不是运行态验证工具
- `bcu` 能改变板状态，执行前必须先明确当前状态和目标状态
- BCU 与串口是否并发由板级知识决定，不能把某块板的限制传播到其它板：
  DXL 捕获 `m4/if01` 时禁止并发并使用人工 reset；如果明确排除 M4，
  当前 DXL 实物已验证可先捕获 `a-core/if02`、`scfw/if03` 再用 BCU reset
- 部分板卡的 BCU 与串口共用 FTDI；BCU 退出后要做串口 fresh probe。
  如果物理 interface 存在但未绑定驱动，使用 `serial-console recover`
- 影响来自实际 FTDI 板控访问，不只来自 reset：当前 BCU 使用
  `libftdi1` 的 FT4232H channel 1，已验证 `eeprom -r -auto`、
  `get_boot_mode -auto` 和 `reset` 都可能接管 `if01`；不访问板卡的
  `version` 不会影响 driver binding
- EEPROM 身份探测必须在串口捕获前完成。读取后先执行
  `serial-console recover`，再 `probe`，确认目标 role 全部存在后才能开始捕获
- 需要保留 reset 起始日志时，必须先启动 `capture-set`，等待所有
  reader 进入 `ALL PORTS READY`，之后才能执行 BCU reset
- `bcu` 文档这里只写工具稳定边界；具体到哪块板怎么用，要去对应板级知识
- `bcu` 的一个重要价值是把板子拉回可控态，但是否把它当默认恢复动作，取决于具体板型的已验证工作流

当前已拆进 `board_knowledge/` 的板型入口：

- `../../board_knowledge/imx943evk19a0/README.md`
- `../../board_knowledge/imx95evk19/README.md`

## 当前注意事项

- 当前工作区不使用普通用户 / udev 例外路径；固定使用 `sudo -n`
- 单板且 EEPROM 身份完整时默认使用 `-auto`；不把 LLM 手工填写的
  `-board=<board>` 当成板型证据
- EEPROM 缺失的旧板仍允许使用已经用户确认的显式 board profile
- 多板连接时不使用默认 `-auto`，必须先与用户确认目标 FTDI serial
- `-keep` 这类参数会保留临时控制状态，使用后要明确是否需要收回
- 如果目标只是把卡住的板拉回“可重新判断、可重新操作”的基线，优先按板级文档里的已验证 reset / boot-mode 恢复动作做，不要临场发明新板控路径
