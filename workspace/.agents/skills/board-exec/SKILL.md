---
name: board-exec
description: 板级执行阶段框架（在本机 Ubuntu 上做）。当任务处于“把产物弄上板并验证”阶段，需要烧写镜像、操作板控/串口工具、抓串口日志、看板子实际运行情况时，加载本技能。典型触发：用户说“烧板子”“烧写/刷镜像”“刷机”“下载镜像到板子”“uuu”“bcu”“烧卡”“进下载模式”“复位板子/切启动模式”“读串口”“抓串口/看串口日志”“上板验证”“板子起不来/卡住/不启动”。注意：这是板子物理操作专用，跟编译阶段无关，编译/出产物那部分在 compile。
---

# 板级执行阶段（本机 Ubuntu）

板子物理连在本机 Ubuntu，所以烧写、板控、串口、USB 枚举检查都在本机做。
本技能讲框架和工具职责；具体命令以后按工具和板型逐步补。
已经被实测证明可复用的板级知识，后续优先沉淀到 `../support_level/board_knowledge/`。
这层的目标不是记录“试过什么”，而是沉淀“以后做板级操作时可以直接复用什么”。

---

## 前提：先确认板子状态

上板前板子的物理状态必须清楚：

- 具体板型
- 芯片版本 / 封装 / DDR
- 当前 boot mode
- 目标存储
- USB 下载口是否接好
- UART 串口线是否接好
- 是否上电

这些在 `AGENTS.md` 的开工方式第 1 步里先确认齐，再动手。

---

## 板级状态机

`board-exec` 不只是“执行板级动作”。
它还必须维护当前板子的状态机，并且在每次板级动作后更新。

当前先保留一个通用骨架，后续再按板型细化：

- 板级公共状态
  - 板型 / `REV` / DDR
  - 当前是否上电
  - 当前 boot mode
  - 目标存储
  - USB 当前处于什么态：
    `not-visible` / `SDPS` / `SDPV` / `FB` / `unknown`
  - 当前主要串口是谁、是否有输出
  - 当前 unresolved step 是：
    `download`
    `deploy`
    `boot`
    `login`
    `runtime`
    `unknown`
- A 核状态
  - `ROM/download`
  - `U-Boot`
  - `Linux booting`
  - `Linux shell`
  - `unknown`
- M 核状态
  - 当前目标核是谁
  - 当前 payload 是什么
  - `not-loaded` / `loaded-not-proved` / `running-proved` / `unknown`

使用规则：

1. 任何板级动作前，先记录“当前状态”
2. 明确这次动作想把状态从哪里推进到哪里
3. 动作执行后，不允许沿用旧状态，必须重新探测并更新
4. 串口安静、`uuu` 成功、reset 成功，都不能直接跳过状态更新
5. 如果当前状态不足以支持下一步动作，先停下来补 probe，不硬推

这层的目标是：

- 不把命令当计划
- 不把旧观察当当前事实
- 不把某个局部成功误判成整板状态已经推进

---

## 工具在哪 + 各工具能干什么

板控/烧写/串口工具优先从这些位置找：

1. `../support_level/tools/`
2. `/home/ives/桌面/NXP/tools`
3. `PATH`

当前主机已确认：

- `uuu` 在 `PATH`，可直接执行
- `picocom` 在 `PATH`，可直接执行
- `bcu` 当前不在 `PATH`，长期入口在 `../support_level/tools/bcu/bcu`

工具能力总览：

- `uuu`
  镜像烧写、USB 下载态枚举、bootloader 临时下载
- `bcu`
  板控、复位、切启动模式、读取当前板控状态
- `picocom`
  读串口日志、进 U-Boot、做基础交互

如果某个工具当前还没正式落到 `support_level/tools/`，说明它现在来自共享旧根，不要假装已经迁移完成。

如果某块板已经在 `support_level/board_knowledge/` 下有实测结论，
优先使用那里的默认串口、默认下载态认知、基础进入方式和操作前提。

当前建议的工具入口是：

- `uuu`
  先读 `../support_level/tools/uuu/USAGE.md`
  再决定是否执行 `../support_level/tools/uuu/uuu`
- `bcu`
  先读 `../support_level/tools/bcu/USAGE.md`
  再决定是否执行 `../support_level/tools/bcu/bcu`

---

## 当前已吸收的关键 deploy / relay 边界

### 1. 先分 artifact class，再选 transport

先分：

- `raw_boot_image`
  例如：
  `flash.bin`
  `imx-boot-...-flash_a55`
  `imx-boot-...-flash_all`
- `fat_runtime_file`
  例如：
  `Image`
  `dtb`
  `.ko`

`raw_boot_image` 走 raw boot path，
不是 FAT 文件替换。

### 2. `uuu` 只拥有 transport，不拥有最终 runtime 证明

`uuu -b sd` / `uuu -b fat_write` 成功，
只说明 transport 和写入动作成立。

它不自动证明：

- Linux 一定能起
- 登录一定可行
- 某个 runtime owner 已经接管

### 3. 同样是 `uuu -b sd`，第一次 bring-up 和 live `FB` 复用不是同一回事

如果板子当前在 `SDPS`，
`uuu -b sd <flash.bin>` 更像是在建立：

- `SDPS -> U-Boot/Fastboot`

如果板子已经在 live `FB`，
同样命令更像是在：

- 复用已有 Fastboot session 再写

### 4. 某些第二阶段镜像只能在已建立的 relay 里使用

例如 `i.MX8DXL` 的 `flash_m4`。

这种镜像不是 first-stage baseline，
而是 second-stage payload。
只有 baseline `flash.bin` 已经把板子带到 `FB`，
它才有意义。

### 5. transport 成功，不等于 boot-stage proof 已成立

`uuu` 成功、reset 成功、镜像写入成功，
都不能自动推出板子已经到了：

- `U-Boot`
- Linux
- 可登录状态

后面还要有独立的 runtime proof。

### 6. connected-board proof 至少要分三层

当前先在 `i.MX943` 落成的边界是：

- `serial download`
- `U-Boot`
- `Linux-ready`

也就是说，板级执行不能只分“烧成功 / 没烧成功”。
烧完之后，还要继续判断板子究竟停在哪一层。

### 7. boot-stage proof 和 login proof 不是一个 owner

如果当前 unresolved 的还是：

- 还在 `serial download`，还是已经进 `U-Boot`
- 还在 `U-Boot`，还是已经开始 Linux boot

那问题还属于 boot-stage proof。

只有当 Linux login 真的是最后一个 unresolved step 时，
才应该交给 login proof owner。

### 8. reused board 上串口安静时，先回头看强信号

如果 deploy / reset 之后串口安静，
不要先默认：

- 串口号错了
- 波特率错了
- 板子死了

先回头确认：

- 当前 boot mode / board truth
- 当前 USB download state
- 当前是不是还停在 `SDPS` / `SDPV` / `FB`

### 9. `U-Boot` 层优先走高层正常 boot path

如果 `U-Boot` 环境本身是健康的，
优先使用板上正常的环境驱动 boot 命令，
不要一上来就掉到 `booti` 这类低层 direct boot。

只有在下面这些情况下，才降到低层 boot path：

- 环境已经坏了
- 当前目标就是做手动控制
- 高层路径已经被证明不成立

### 10. Linux shell proof 也要有最小验证集

当板子已经被证明 close enough to Linux login 时，
login proof 不应该只停在“看起来能输账号密码”。

至少要留下最小 runtime proof，例如：

- `uname -a`
- `cat /etc/os-release`
- `mount`

并明确：

- 实际登录的是哪个串口
- 当前是 login prompt 还是已在 shell
- 这一步有没有把问题从 boot-stage proof 真正交接出去

### 11. host-check 只证明 host readiness

在 `i.MX93` / `i.MX943` / `i.MX95` 这些 lane 里，
host-check 负责：

- 工具是否存在
- `sudo` / 权限是否成立
- serial candidates 是否可见
- 是否具备 live probe 前提

它不负责：

- 当前 board truth
- 当前 boot mode
- 当前 runtime stage

### 12. network / app-layer 必须在 Linux-up 之后

像下面这些都不应抢在 boot/runtime lane 前面：

- host share networking
- board IP / DNS
- OpenClaw / Feishu / board-local app runtime

前提是：

- 板子已经被证明 Linux-up
- 当前 unresolved step 已经不是 `serial download` / `U-Boot` / login

### 13. `i.MX95` 当前仍保留 board-generic runtime 语义

`i.MX95` 第一轮吸收后的边界是：

- build-side `RTE 3.3 flash.bin` lane 已经拆出来
- 但 deploy / boot / verify 还没有像 `i.MX943` 那样完全拆成窄 leaves

所以对 `i.MX95`：

- board-level `uuu`
- `bcu`
- deploy
- boot
- verify

当前仍按 board-generic board-state-first 语义处理。

### 14. `i.MX95` 的两个高风险 board facts

- `A0` / `B0` 是 output-affecting 字段
- `bcu reset ... -keep` 可能把 `ft_fta_sel` 留在 `HIGH`，造成 runtime port 假静音

这两个点没排除前，
不要过早怪：

- `uuu`
- 镜像
- runtime payload

---

## 板级执行大致顺序

1. **先确认当前状态**
   明确当前板状态、各核状态、目标板状态、允许的下一步动作
2. **确认设备已枚举**
   看 USB 下载设备、串口设备、当前主机是否识别到板子
3. **烧写**
   把产物烧到目标存储
4. **切回目标启动模式并复位**
5. **抓串口日志**
6. **看现象 / 日志**
   判断启动到哪一步、是否符合预期
7. **更新状态机**
   把板状态和各核状态回写成新的当前状态

烧写是破坏性操作，动手前先确认目标存储和镜像。

---

## Ubuntu 下的常见工具形态

枚举 USB 下载设备：

```bash
uuu -lsusb
lsusb
```

看串口设备：

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

抓串口日志：

```bash
picocom -b 115200 /dev/ttyUSB0
```

实际串口号、波特率、板型差异，必须以当前板子的现场情况为准，不要硬套。

---

## 板级执行产出

- 烧了什么镜像、烧到哪、是否成功
- 板级状态机在动作前后分别是什么
- 串口日志关键片段、卡在哪个阶段
- 下一步该回到 `compile` 改产物，还是回到 `support-level` 查资料

边界：

- 本技能不负责编译
- 板级执行中若要查芯片/驱动事实，回到 `support-level`
- 当前还没有为每块板补齐 Ubuntu 实测 recipe 时，不要假装某条命令已经被验证
- 板级操作里一旦出现稳定、可复用、已经验证过的知识，应该回写到 `support_level/board_knowledge/`

---

## 待补全

- 各板型的默认串口映射和下载态识别
- `bcu`、`uuu`、`picocom` 的本机固定调用路径
- 典型异常恢复流程
