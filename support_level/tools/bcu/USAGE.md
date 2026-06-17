# bcu

- 程序入口：`./bcu`
- 当前版本：`bcu_1.1.128-0-ge7027dc`
- 工具角色：板控 / 复位 / 启动模式控制 / GPIO 辅助控制

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
./bcu version
./bcu -h
```

常见命令族：

```bash
./bcu get_boot_mode -board=<board>
./bcu set_boot_mode <BOOTMODE_NAME> -board=<board>
./bcu reset <BOOTMODE_NAME> -board=<board>
./bcu set_gpio <GPIO_NAME> 1 -board=<board>
./bcu set_gpio <GPIO_NAME> 0 -board=<board>
```

## 使用边界

- `bcu` 是板控工具，不是运行态验证工具
- `bcu` 能改变板状态，执行前必须先明确当前状态和目标状态
- `bcu` 文档这里只写工具稳定边界；具体到哪块板怎么用，要去对应板级知识
- `bcu` 的一个重要价值是把板子拉回可控态，但是否把它当默认恢复动作，取决于具体板型的已验证工作流

当前已拆进 `board_knowledge/` 的板型入口：

- `../../board_knowledge/imx943evk19a0/README.md`
- `../../board_knowledge/imx95evk19/README.md`

## 当前注意事项

- 工具帮助明确提示：通常应使用 `sudo` 或配置好 `udev`
- `-board=<board>` / `-auto` / `-id=` 这类选择项经常决定命令是否真正落到目标板
- `-keep` 这类参数会保留临时控制状态，使用后要明确是否需要收回
- 如果目标只是把卡住的板拉回“可重新判断、可重新操作”的基线，优先按板级文档里的已验证 reset / boot-mode 恢复动作做，不要临场发明新板控路径
