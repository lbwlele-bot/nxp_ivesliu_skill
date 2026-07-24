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

## 先读什么

先确认三件事：

1. 当前板型和 board id 是否明确
2. 当前板状态是否明确
3. 这次动作是在做：
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
sudo -n ./bcu get_boot_mode -board=<board>
sudo -n ./bcu set_boot_mode <BOOTMODE_NAME> -board=<board>
sudo -n ./bcu reset <BOOTMODE_NAME> -board=<board>
sudo -n ./bcu set_gpio <GPIO_NAME> 1 -board=<board>
sudo -n ./bcu set_gpio <GPIO_NAME> 0 -board=<board>
```

## 使用边界

- `bcu` 是板控工具，不是运行态验证工具
- `bcu` 能改变板状态，执行前必须先明确当前状态和目标状态
- 不与 `serial-console` 并发运行；部分板卡的 BCU 与 UART 共用 FTDI 设备，
  并发访问会造成串口 interface 暂时缺失。BCU 退出后等待 udev 稳定，再做
  串口 fresh probe；具体等待和完整性判据以板级知识为准
- `bcu` 文档这里只写工具稳定边界；具体到哪块板怎么用，要去对应板级知识
- `bcu` 的一个重要价值是把板子拉回可控态，但是否把它当默认恢复动作，取决于具体板型的已验证工作流

当前已拆进 `board_knowledge/` 的板型入口：

- `../../board_knowledge/imx943evk19a0/README.md`
- `../../board_knowledge/imx95evk19/README.md`

## 当前注意事项

- 当前工作区不使用普通用户 / udev 例外路径；固定使用 `sudo -n`
- `-board=<board>` / `-auto` / `-id=` 这类选择项经常决定命令是否真正落到目标板
- `-keep` 这类参数会保留临时控制状态，使用后要明确是否需要收回
- 如果目标只是把卡住的板拉回“可重新判断、可重新操作”的基线，优先按板级文档里的已验证 reset / boot-mode 恢复动作做，不要临场发明新板控路径
